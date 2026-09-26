"""Deterministic barriers and unresolved next checks (implementation plan section 5).

Every NextCheck names the human role that resolves it (escalation path).
Order is by decision impact (policy.DECISION_IMPACT_ORDER, Round 3): each
barrier and parcel-specific check is tagged with a category and the list is
stable-sorted, so the first barrier (the principal barrier) and the first
parcel-specific check are the most consequential. Standard checks (trigger
"base", with Treasurer Sale terms after title for advertised parcels) always
follow every parcel-specific check. Hazard check triggers cite
§906.04/§906.05/§906.08/§915.02. Routing-only records get route-relevant
steps only.

Every Defer carries at least one barrier and one next check naming the
missing or conflicting input.
"""

from __future__ import annotations

from dataclasses import dataclass

from lotline.models import ComponentScore, Conflict, ConflictLevel, NextCheck, Outcome, ParcelContext

from . import policy
from .conflicts import area_gap, large_gap
from .dimensions import SETBACK_NAMES, DimensionalResult, depth_band, valid_area, width_band
from .hazards import FEMA_SFHA, TERRAIN, UNDERMINING, effective_sfha, layer_names

# --- canonical check texts ---------------------------------------------------
CORNER = "corner/frontage status"
CONTEXTUAL = "contextual setbacks (Ch. 925)"
SURVEY = "survey"
TITLE = "title"
LEGAL_ACCESS = "legal access"
UTILITIES = "utilities"
MARKET = "market demand/appraisal"
DEED_AREA = "deed and record-area reconciliation"
SITE_CONDITION = "current site-condition verification"
SLOPE = "slope and geotechnical review"
MINE = "mine-subsidence review"
FLOOD = "floodplain determination"
COMMUNITY = "community-review applicability"
HISTORIC = "historic review applicability"
VERIFY_ADVERT = "verify the current City advertisement before proceeding"
PRICE_RECONCILE = "reconcile advertised upset price with Treasury tax due"
ZONING_TABLE = "confirm current zoning/use table"
NON_HOUSING = "evaluate non-housing reuse"
STRUCTURE_REVIEW = "structure-specific review outside the vacant-land model"
PARCEL_RECORDS = "assemble parcel records (assessment, County GIS polygon, screening layers)"
GEOMETRY = "parcel geometry (bounding-rectangle sides)"
LAYER_REQUERY = "re-run screening layer query"
SETBACK_RULE = "confirm district setbacks"
MIN_LOT_RULE = "confirm district minimum lot size"

BASE_CHECKS: tuple[str, ...] = (policy.CURRENT_SALE_STATUS_CHECK, CONTEXTUAL, SURVEY, TITLE,
                               LEGAL_ACCESS, UTILITIES, MARKET)
NO_HOUSING_BASE: tuple[str, ...] = (policy.CURRENT_SALE_STATUS_CHECK, ZONING_TABLE, NON_HOUSING,
                                   TITLE, LEGAL_ACCESS, UTILITIES)

OWNERS: dict[str, str] = {
    CORNER: "licensed surveyor / County plat",
    CONTEXTUAL: "Zoning Administrator",
    SURVEY: "PA-licensed surveyor",
    TITLE: "title examiner or attorney",
    LEGAL_ACCESS: "title examiner + DOMI (right-of-way, paper streets)",
    UTILITIES: "PWSA & utility providers",
    MARKET: "certified appraiser",
    DEED_AREA: "County Real Estate + licensed surveyor",
    SITE_CONDITION: "PLI (condemned-case status) + site visit",
    SLOPE: "geotechnical engineer",
    MINE: "PA DEP Bureau of Abandoned Mine Reclamation / Mine Subsidence Insurance + geotechnical engineer",
    FLOOD: "City floodplain administrator",
    HISTORIC: "Historic Review Commission",
    VERIFY_ADVERT: "City Treasurer / Real Estate Division",
    PRICE_RECONCILE: "City Treasurer / Real Estate Division",
    ZONING_TABLE: "Zoning Administrator",
    NON_HOUSING: "acquisition staff / City Planning",
    STRUCTURE_REVIEW: "acquisition staff; PLI for condemnation/demolition records",
    PARCEL_RECORDS: "acquisition staff (data preparation)",
    GEOMETRY: "County GIS / licensed surveyor",
    LAYER_REQUERY: "acquisition staff (GIS data refresh)",
    SETBACK_RULE: "Zoning Administrator",
    MIN_LOT_RULE: "Zoning Administrator",
    policy.CURRENT_SALE_STATUS_CHECK: policy.CURRENT_SALE_STATUS_OWNER,
}
DIMENSIONS_OWNER = "Zoning Administrator"

HAZARD_CHECKS = {TERRAIN: SLOPE, UNDERMINING: MINE, FEMA_SFHA: FLOOD}
HAZARD_BARRIER_NAMES = {TERRAIN: "terrain", UNDERMINING: "undermining", FEMA_SFHA: "FEMA"}


@dataclass(frozen=True)
class CheckInputs:
    ctx: ParcelContext
    outcome: Outcome
    conflicts: list[Conflict]
    dimensional: DimensionalResult
    hazard_families: list[str]
    advertisement_date: str
    environment: ComponentScore | None = None
    unqueried_layers: tuple[str, ...] = ()
    upset_to_assessed_land: float | None = None


def _kinds(conflicts: list[Conflict], level: ConflictLevel) -> set[str]:
    return {c.kind for c in conflicts if c.level is level}


def _dims_unencoded(ctx: ParcelContext) -> bool:
    r = ctx.rule
    return r is None or (r.dimensions_applicable and not r.dimensions_encoded)


def _dims_label(ctx: ParcelContext) -> str:
    r = ctx.rule
    if r is None:
        return f"{_district(ctx)} district rules"
    return f"§{r.dimensional_citation} ({r.district})" if r.dimensional_citation else f"{r.district}-district"


def _district(ctx: ParcelContext) -> str:
    if ctx.rule is not None:
        return ctx.rule.district
    return (ctx.facts.zoning_polygon if ctx.facts else ctx.treasury.zon_code) or "unresolved"


def _areas(ctx: ParcelContext) -> list[float | None]:
    f = ctx.facts
    return [] if f is None else [valid_area(f.assess_lotarea_sf), valid_area(f.county_gis_area_sf)]


def _below_min_any(ctx: ParcelContext) -> bool:
    """Some recorded lot area is below a positive district minimum (§921.04.A may apply)."""
    rule = ctx.rule
    if rule is None or not rule.min_lot_sf:
        return False
    return any(a is not None and a < rule.min_lot_sf for a in _areas(ctx))


def _missing_area_sources(ctx: ParcelContext) -> list[str]:
    if ctx.facts is None:
        return []
    return [n for n, a in zip(("assessment", "County GIS"), _areas(ctx), strict=True) if a is None]


def _dim_needs_inputs(ctx: ParcelContext) -> bool:
    """Dimensional fit is evaluated for this parcel (so its inputs matter)."""
    r = ctx.rule
    return (
        ctx.facts is not None and r is not None and r.dimensions_applicable
        and r.dimensions_encoded and not r.site_standard_blocks_dimensional
    )


def _missing_setbacks(ctx: ParcelContext) -> list[str]:
    r, f = ctx.rule, ctx.facts
    if not _dim_needs_inputs(ctx) or r is None or f is None:
        return []
    needed = ["front_setback_ft", "rear_setback_ft", "interior_side_ft"]
    if f.possible_corner:
        needed.append("exterior_side_ft")
    return [n for n in needed if getattr(r, n) is None]


def _geometry_missing(ctx: ParcelContext) -> bool:
    f = ctx.facts
    return _dim_needs_inputs(ctx) and f is not None and (
        valid_area(f.mbr_short_side_ft) is None or valid_area(f.mbr_long_side_ft) is None
    )


def _hazard_trigger(fam: str, ctx: ParcelContext) -> str:
    """Trigger text for a hazard check, citing the overlay sections that apply."""
    base = f"hazard: {fam}"
    facts = ctx.facts
    if facts is None:
        return base
    refs: list[str] = []
    if fam == TERRAIN:
        if facts.slope25:
            refs.append(policy.TERRAIN_SLOPE_TRIGGER)
        if facts.landslide_prone:
            refs.append(policy.TERRAIN_LANDSLIDE_TRIGGER)
    elif fam == UNDERMINING:
        refs.append(policy.UNDERMINING_TRIGGER)
    return f"{base} ({'; '.join(refs)})" if refs else base


def _district_review_checks(ctx: ParcelContext) -> list[tuple[str, NextCheck]]:
    """Code-required district reviews (policy.DISTRICT_REVIEW_CHECKS), data-driven by district.

    Returns (decision-impact category, check) pairs (policy.DISTRICT_REVIEW_CATEGORY).
    """
    rule = ctx.rule
    if rule is None:
        return []
    areas = [a for a in _areas(ctx) if a is not None]
    out: list[tuple[str, NextCheck]] = []
    for check, owner, trigger, min_area in policy.DISTRICT_REVIEW_CHECKS.get(rule.district, ()):
        if min_area is not None and areas and max(areas) < min_area:
            continue
        category = policy.DISTRICT_REVIEW_CATEGORY.get(check, "district_procedure")
        out.append((category, NextCheck(check=check, owner=owner, trigger=trigger)))
    return out


def _nc(check: str, trigger: str, owner: str | None = None) -> NextCheck:
    return NextCheck(check=check, owner=owner or OWNERS[check], trigger=trigger)


def _sale_terms(ctx: ParcelContext) -> NextCheck:
    return NextCheck(
        check=policy.SALE_TERMS_CHECK.format(sale_date=ctx.treasury.sale_date),
        owner=policy.SALE_TERMS_OWNER,
        trigger=policy.SALE_TERMS_TRIGGER,
    )


def is_standard(nc: NextCheck) -> bool:
    """A standard check for every advertised lot (base checks, Treasurer Sale terms)."""
    return nc.trigger in policy.STANDARD_TRIGGERS


def _by_impact(tagged: list[tuple[str, object]]) -> list:
    """Stable sort of (category, item) pairs by policy.DECISION_IMPACT_ORDER."""
    return [item for _, item in sorted(tagged, key=lambda t: policy.impact_rank(t[0]))]


def _fema_unknown(i: CheckInputs) -> bool:
    f = i.ctx.facts
    return f is not None and effective_sfha(f) is None and "fema_nfhl" not in i.unqueried_layers


def next_checks(i: CheckInputs) -> list[NextCheck]:
    """Parcel-specific checks by decision impact (policy.DECISION_IMPACT_ORDER), then standard checks."""
    ctx, facts = i.ctx, i.ctx.facts
    if i.outcome is Outcome.OUT_OF_UNIVERSE:
        return [_nc(VERIFY_ADVERT, "routing: not in the City advertisement")]
    if i.outcome is Outcome.STRUCTURE:
        out = [NextCheck(policy.CURRENT_SALE_STATUS_CHECK, policy.CURRENT_SALE_STATUS_OWNER,
                         policy.CURRENT_SALE_STATUS_TRIGGER),
               _nc(STRUCTURE_REVIEW, "routing: assessment indicates a structure")]
        if ctx.advert is not None:
            out.append(_sale_terms(ctx))
        return out

    tagged: list[tuple[str, NextCheck]] = []

    def add(category: str, nc: NextCheck) -> None:
        tagged.append((category, nc))

    no_housing = i.outcome is Outcome.DO_NOT_ADVANCE
    if facts is not None and facts.possible_corner and not no_housing:
        add("corner_frontage", _nc(CORNER, "possible_corner"))
    for c in NO_HOUSING_BASE if no_housing else BASE_CHECKS:
        trigger = policy.CURRENT_SALE_STATUS_TRIGGER if c == policy.CURRENT_SALE_STATUS_CHECK else "base"
        add("standard", _nc(c, trigger))
        if c == TITLE and ctx.advert is not None:
            add("standard", _sale_terms(ctx))

    critical = _kinds(i.conflicts, ConflictLevel.CRITICAL)
    material = _kinds(i.conflicts, ConflictLevel.MATERIAL)
    if "current_condition" in critical:
        add("critical_conflict", _nc(SITE_CONDITION, "condemned_case_active"))
    if "sale_universe" in critical:
        add("critical_conflict", _nc(PRICE_RECONCILE, "conflict: sale_universe"))

    gap = area_gap(*_areas(ctx)) if facts is not None else None
    missing_area = _missing_area_sources(ctx)
    if "lot_area" in critical:
        add("critical_conflict", _nc(DEED_AREA, "conflict: lot_area (material)"))
    elif "lot_area" in material:
        add("material_conflict", _nc(DEED_AREA, "conflict: lot_area (material)"))
    elif large_gap(gap):
        add("area_gap", _nc(DEED_AREA, f"disclose-level area gap >= {policy.LARGE_GAP_PCT:g}% (no score change)"))
    elif missing_area and _dim_needs_inputs(ctx):
        add("missing_input", _nc(DEED_AREA, f"lot area missing from the {' and '.join(missing_area)} record"))

    # Missing-input checks (name the input that is missing).
    if facts is None:
        add("missing_input", _nc(PARCEL_RECORDS, "prepared parcel records missing"))
    if ctx.rule is not None and i.outcome is not Outcome.DO_NOT_ADVANCE:
        use_codes = (ctx.rule.single_unit_permission, ctx.rule.two_unit_permission)
        if any(c.strip().upper() not in policy.PERMISSION_SCORES for c in use_codes):
            add("rules_not_encoded", _nc(ZONING_TABLE, "rule: permission code not in the screening vocabulary"))
    if _geometry_missing(ctx):
        add("missing_input", _nc(GEOMETRY, "parcel geometry (bounding-rectangle sides) missing"))
    missing_sb = _missing_setbacks(ctx)
    if missing_sb:
        names = ", ".join(SETBACK_NAMES[m] for m in missing_sb)
        corner = "; exterior side is needed because the lot may be a corner" if "exterior_side_ft" in missing_sb else ""
        add("rules_not_encoded", _nc(f"{SETBACK_RULE}: {names} ({_dims_label(ctx)})",
                                     f"rule: blank setback ({', '.join(missing_sb)}){corner}", OWNERS[SETBACK_RULE]))
    if _dim_needs_inputs(ctx) and ctx.rule is not None and ctx.rule.min_lot_sf is None:
        add("rules_not_encoded", _nc(f"{MIN_LOT_RULE} ({_dims_label(ctx)})", "rule: blank min_lot_sf",
                                     OWNERS[MIN_LOT_RULE]))
    if i.unqueried_layers and facts is not None:
        add("missing_input", _nc(f"{LAYER_REQUERY} ({layer_names(i.unqueried_layers)})",
                                 "source manifest: query_completed=N", OWNERS[LAYER_REQUERY]))

    if _below_min_any(ctx) and not no_housing:
        add("below_minimum", NextCheck(check=policy.LOT_OF_RECORD_CHECK, owner=policy.LOT_OF_RECORD_OWNER,
                                       trigger="lot area below the district minimum in at least one source"))
    if _dims_unencoded(ctx) and not no_housing:
        add("rules_not_encoded",
            _nc(f"review {_dims_label(ctx)} dimensions", "rule: dimensions_encoded=N", DIMENSIONS_OWNER))
    if not no_housing:
        tagged.extend(_district_review_checks(ctx))
    for fam in i.hazard_families:
        add("hazard", _nc(HAZARD_CHECKS[fam], _hazard_trigger(fam, ctx)))
    if _fema_unknown(i) and FEMA_SFHA not in i.hazard_families:
        add("missing_input",
            _nc(FLOOD, f"FEMA zone {facts.fema_zone!r} undetermined or unrecognized"))  # type: ignore[union-attr]
    if facts is not None and facts.rco:
        add("community_historic",
            _nc(COMMUNITY, "rco", f"{facts.rco} (Registered Community Organization; contact, not endorsement)"))
    if facts is not None and facts.historic_district:
        add("community_historic", _nc(HISTORIC, f"historic: {facts.historic_district}"))
    return _by_impact(tagged)


def _hazard_barrier(families: list[str]) -> str | None:
    if not families:
        return None
    names = [HAZARD_BARRIER_NAMES[f] for f in families]
    if len(names) == 1:
        return f"{names[0]} screening overlap"
    joined = ", ".join(names[:-1]) + " and " + names[-1]
    return f"{joined} screening overlaps"


def _sf(x: float) -> str:
    return f"{x:,.0f}"


def _envelope_barrier(dim: DimensionalResult) -> tuple[str, str] | None:
    """(decision-impact category, barrier text) for the illustrative envelope, if any."""
    if dim.component.status not in ("known", "range") or not dim.scenarios or dim.area_conforms is False:
        return None
    interior = dim.scenarios[0]
    corner = dim.scenarios[1] if len(dim.scenarios) > 1 else None
    if corner is not None and corner.score == 0 < interior.score:
        return ("corner_frontage",
                f"corner status may reduce the illustrative width below {policy.WIDTH_PARTIAL_FT:g} ft")
    if corner is not None and corner.score < interior.score:
        return ("corner_frontage", "corner/frontage status remains unverified")
    shallow = depth_band(interior.depth_ft) < width_band(interior.width_ft)
    if interior.score == 1:
        return ("dimensional_envelope", "shallow illustrative envelope" if shallow else "narrow illustrative envelope")
    if interior.score == 0:
        if shallow:
            return ("dimensional_envelope", f"illustrative envelope shallower than {policy.DEPTH_PARTIAL_FT:g} ft")
        return ("dimensional_envelope", f"illustrative envelope narrower than {policy.WIDTH_PARTIAL_FT:g} ft")
    return None


def barriers(i: CheckInputs) -> list[str]:
    """Principal barriers, ordered by decision impact (policy.DECISION_IMPACT_ORDER).

    The first barrier is the principal barrier: critical conflicts, then
    material conflicts and below-minimum records, use prohibition, rules not
    encoded, missing inputs, survey-dependent site standards, hazard overlaps,
    envelope limits, Parks/open-space designation, large disclose-level area
    gap, acquisition burden, corner/frontage status. Hazard overlaps are
    omitted when the parcel is already stopped by a critical conflict or a use
    prohibition (they stay in hazard families and next checks).
    """
    ctx, rule = i.ctx, i.ctx.rule
    if i.outcome is Outcome.OUT_OF_UNIVERSE:
        return [f"not in the City advertisement dated {i.advertisement_date}"]
    if i.outcome is Outcome.STRUCTURE:
        return [
            f"assessment classifies the parcel as a structure ({ctx.treasury.usedesc}); "
            "vacant-land model not applicable"
        ]
    tagged: list[tuple[str, str]] = []

    def add(category: str, text: str) -> None:
        tagged.append((category, text))

    critical = _kinds(i.conflicts, ConflictLevel.CRITICAL)
    if "current_condition" in critical:
        add("critical_conflict", "current site condition is unverified")
    if "sale_universe" in critical:
        add("critical_conflict", "advertised upset price and Treasury tax due disagree")
    for c in i.conflicts:
        if c.kind == "lot_area" and c.level is ConflictLevel.MATERIAL and rule and rule.min_lot_sf is not None:
            add("material_conflict", f"area records cross the {_sf(rule.min_lot_sf)} sf minimum")

    if i.outcome is Outcome.DO_NOT_ADVANCE and rule is not None:
        add("use_prohibition", f"neither single-unit nor two-unit housing is permitted in {rule.district}")
    elif ctx.facts is None:
        add("missing_input", "prepared parcel records are missing")
    elif rule is None:
        add("rules_not_encoded", f"{_district(ctx)} district rules are not encoded in LotLine; this is a tool "
            "limitation, not a records problem")
    elif _dims_unencoded(ctx):
        cite = f" (§{rule.dimensional_citation})" if rule.dimensional_citation else ""
        add("rules_not_encoded", policy.UNENCODED_DIMENSIONS_BARRIER.format(district=rule.district, cite=cite))
    elif rule is not None and rule.site_standard_blocks_dimensional:
        add("site_standard", policy.SITE_STANDARD_BARRIERS.get(
            rule.district, policy.SITE_STANDARD_GENERIC_BARRIER.format(district=rule.district)))
    if (rule is not None and i.outcome is not Outcome.DO_NOT_ADVANCE
            and any(c.strip().upper() not in policy.PERMISSION_SCORES
                    for c in (rule.single_unit_permission, rule.two_unit_permission))):
        add("rules_not_encoded",
            f"{rule.district} use permission is not in the screening vocabulary; use path not established")

    # Other missing inputs, each named.
    if _geometry_missing(ctx):
        add("missing_input", "parcel geometry (bounding-rectangle sides) is missing; dimensional fit withheld")
    missing_sb = _missing_setbacks(ctx)
    if missing_sb:
        names = ", ".join(SETBACK_NAMES[m] for m in missing_sb)
        reason_text = " (needed because the lot may be a corner)" if "exterior_side_ft" in missing_sb else ""
        add("rules_not_encoded",
            f"{_district(ctx)} {names} setback is not encoded{reason_text}; dimensional fit withheld")
    if _dim_needs_inputs(ctx) and rule is not None and rule.min_lot_sf is None:
        add("rules_not_encoded", f"{rule.district} minimum lot size is not encoded; dimensional fit withheld")
    missing_area = _missing_area_sources(ctx)
    if missing_area and _dim_needs_inputs(ctx) and not _missing_setbacks(ctx) and not _geometry_missing(ctx):
        add("missing_input", f"lot area is missing from the {' and '.join(missing_area)} record; "
            "conformity in all sources not established")
    if i.unqueried_layers and ctx.facts is not None:
        add("missing_input", f"environmental screening incomplete: {layer_names(i.unqueried_layers)} layer query "
            "did not complete; environment withheld")
    elif _fema_unknown(i):
        add("missing_input", f"FEMA flood zone {ctx.facts.fema_zone!r} is undetermined or not a recognized NFHL "  # type: ignore[union-attr]
            "zone; environment withheld")

    dim = i.dimensional
    if dim.area_conforms is False and rule is not None and rule.min_lot_sf:
        add("below_minimum", policy.BELOW_MINIMUM_BARRIER.format(minimum=_sf(rule.min_lot_sf)))

    blocked = bool(critical) or i.outcome is Outcome.DO_NOT_ADVANCE
    risk = policy.DISTRICT_RISK_BARRIERS.get(rule.district) if rule is not None else None
    if risk and not blocked:
        add("parks_open_space", risk)

    gap = area_gap(*_areas(ctx)) if ctx.facts is not None else None
    disclose_only = not any(c.kind == "lot_area" and c.level is not ConflictLevel.DISCLOSE for c in i.conflicts)
    if gap is not None and large_gap(gap) and disclose_only:
        pct = max(abs(gap.pct), gap.symmetric_pct)
        tail = ""
        if rule is not None and rule.min_lot_sf == 0:
            tail = f"; {rule.district} has no minimum lot size, so no score change"
        elif rule is not None and rule.min_lot_sf and min(gap.assess_sf, gap.gis_sf) >= rule.min_lot_sf:
            tail = f"; both exceed the {_sf(rule.min_lot_sf)} sf minimum, so no score change"
        add("area_gap", f"lot-area records disagree by {pct:.0f}% (assessment {_sf(gap.assess_sf)} sf vs "
            f"County GIS {_sf(gap.gis_sf)} sf){tail}")

    env = _envelope_barrier(dim)
    if env:
        add(*env)

    ratio = i.upset_to_assessed_land
    if ratio is not None and ratio >= policy.ACQUISITION_BURDEN_RATIO:
        add("acquisition_burden", f"upset price is {ratio:.1f}× assessed land value "
            "(acquisition-burden indicator only, not market value)")

    hz = _hazard_barrier(i.hazard_families)
    if hz and not blocked:
        add("hazard", hz)
    return _by_impact(tagged)
