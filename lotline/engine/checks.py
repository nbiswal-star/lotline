"""Deterministic barriers and unresolved next checks (implementation plan section 5).

Every NextCheck names the human role that resolves it (escalation path).
Order is fixed: corner, base checks, conflict checks, unencoded-dimension
check, district review checks (policy.DISTRICT_REVIEW_CHECKS), hazard checks
(triggers cite §906.04/§906.05/§906.08/§915.02), community and historic. Routing-only records get route-relevant steps only.
"""

from __future__ import annotations

from dataclasses import dataclass

from lotline.models import Conflict, ConflictLevel, NextCheck, Outcome, ParcelContext

from . import policy
from .dimensions import DimensionalResult
from .hazards import FEMA_SFHA, TERRAIN, UNDERMINING

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

BASE_CHECKS: tuple[str, ...] = (CONTEXTUAL, SURVEY, TITLE, LEGAL_ACCESS, UTILITIES, MARKET)
NO_HOUSING_BASE: tuple[str, ...] = (ZONING_TABLE, NON_HOUSING, TITLE, LEGAL_ACCESS, UTILITIES)

OWNERS: dict[str, str] = {
    CORNER: "licensed surveyor / County plat",
    CONTEXTUAL: "Zoning Administrator",
    SURVEY: "PA-licensed surveyor",
    TITLE: "title examiner (liens incl. water claims survive the sale)",
    LEGAL_ACCESS: "title examiner / City Law",
    UTILITIES: "PWSA & utility providers",
    MARKET: "certified appraiser",
    DEED_AREA: "County Real Estate + surveyor",
    SITE_CONDITION: "PLI (condemned-case status) + site visit",
    SLOPE: "geotechnical engineer",
    MINE: "PA DEP Bureau of Mine Safety / MSI",
    FLOOD: "City floodplain administrator",
    HISTORIC: "Historic Review Commission",
    VERIFY_ADVERT: "City Treasurer / Real Estate Division",
    PRICE_RECONCILE: "City Treasurer / Real Estate Division",
    ZONING_TABLE: "Zoning Administrator",
    NON_HOUSING: "acquisition staff / City Planning",
    STRUCTURE_REVIEW: "acquisition staff; PLI for condemnation/demolition records",
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


def _kinds(conflicts: list[Conflict], level: ConflictLevel) -> set[str]:
    return {c.kind for c in conflicts if c.level is level}


def _dims_unencoded(ctx: ParcelContext) -> bool:
    r = ctx.rule
    return r is None or (r.dimensions_applicable and not r.dimensions_encoded)


def _dims_label(ctx: ParcelContext) -> str:
    r = ctx.rule
    if r is None:
        district = ctx.facts.zoning_polygon if ctx.facts else ctx.treasury.zon_code
        return f"{district} district rules"
    return f"§{r.dimensional_citation} ({r.district})" if r.dimensional_citation else f"{r.district}-district"


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


def _district_review_checks(ctx: ParcelContext) -> list[NextCheck]:
    """Code-required district reviews (policy.DISTRICT_REVIEW_CHECKS), data-driven by district."""
    rule, facts = ctx.rule, ctx.facts
    if rule is None:
        return []
    recorded = () if facts is None else (facts.assess_lotarea_sf, facts.county_gis_area_sf)
    areas = [a for a in recorded if a is not None]
    out: list[NextCheck] = []
    for check, owner, trigger, min_area in policy.DISTRICT_REVIEW_CHECKS.get(rule.district, ()):
        if min_area is not None and areas and max(areas) < min_area:
            continue
        out.append(NextCheck(check=check, owner=owner, trigger=trigger))
    return out


def _nc(check: str, trigger: str, owner: str | None = None) -> NextCheck:
    return NextCheck(check=check, owner=owner or OWNERS[check], trigger=trigger)


def next_checks(i: CheckInputs) -> list[NextCheck]:
    ctx, facts = i.ctx, i.ctx.facts
    if i.outcome is Outcome.OUT_OF_UNIVERSE:
        return [_nc(VERIFY_ADVERT, "routing: not in the City advertisement")]
    if i.outcome is Outcome.STRUCTURE:
        return [_nc(STRUCTURE_REVIEW, "routing: assessment indicates a structure")]

    out: list[NextCheck] = []
    no_housing = i.outcome is Outcome.DO_NOT_ADVANCE
    if facts is not None and facts.possible_corner and not no_housing:
        out.append(_nc(CORNER, "possible_corner"))
    out.extend(_nc(c, "base") for c in (NO_HOUSING_BASE if no_housing else BASE_CHECKS))

    critical = _kinds(i.conflicts, ConflictLevel.CRITICAL)
    material = _kinds(i.conflicts, ConflictLevel.MATERIAL)
    if "sale_universe" in critical:
        out.append(_nc(PRICE_RECONCILE, "conflict: sale_universe"))
    if "lot_area" in material or "lot_area" in critical:
        out.append(_nc(DEED_AREA, "conflict: lot_area (material)"))
    if "current_condition" in critical:
        out.append(_nc(SITE_CONDITION, "condemned_case_active"))
    if _dims_unencoded(ctx) and not no_housing:
        out.append(
            _nc(f"review {_dims_label(ctx)} dimensions", "rule: dimensions_encoded=N", DIMENSIONS_OWNER)
        )
    if not no_housing:
        out.extend(_district_review_checks(ctx))
    for fam in i.hazard_families:
        out.append(_nc(HAZARD_CHECKS[fam], _hazard_trigger(fam, ctx)))
    if facts is not None and facts.rco:
        out.append(
            _nc(COMMUNITY, "rco", f"{facts.rco} (Registered Community Organization; contact, not endorsement)")
        )
    if facts is not None and facts.historic_district:
        out.append(_nc(HISTORIC, f"historic: {facts.historic_district}"))
    return out


def _hazard_barrier(families: list[str]) -> str | None:
    if not families:
        return None
    names = [HAZARD_BARRIER_NAMES[f] for f in families]
    if len(names) == 1:
        return f"{names[0]} screening overlap"
    joined = ", ".join(names[:-1]) + " and " + names[-1]
    return f"{joined} screening overlaps"


def barriers(i: CheckInputs) -> list[str]:
    """Principal barriers, blocking items first.

    Hazard overlaps are omitted when the parcel is already stopped by a
    critical conflict or a use prohibition (they stay in hazard families and
    next checks). Disclose-level conflicts change no decision and are not
    barriers (they appear in conflicts and the memo).
    """
    ctx, rule = i.ctx, i.ctx.rule
    if i.outcome is Outcome.OUT_OF_UNIVERSE:
        return [f"not in the City advertisement dated {i.advertisement_date}"]
    if i.outcome is Outcome.STRUCTURE:
        return [
            f"assessment classifies the parcel as a structure ({ctx.treasury.usedesc}); "
            "vacant-land model not applicable"
        ]
    out: list[str] = []
    critical = _kinds(i.conflicts, ConflictLevel.CRITICAL)
    if "current_condition" in critical:
        out.append("current site condition is unverified")
    if "sale_universe" in critical:
        out.append("advertised upset price and Treasury tax due disagree")
    for c in i.conflicts:
        if c.kind == "lot_area" and c.level is ConflictLevel.MATERIAL and rule and rule.min_lot_sf is not None:
            out.append(f"area records cross the {rule.min_lot_sf:.0f} sf minimum")
    if i.outcome is Outcome.DO_NOT_ADVANCE and rule is not None:
        out.append(f"neither single-unit nor two-unit housing is permitted in {rule.district}")
    elif ctx.facts is None:
        out.append("prepared parcel records are missing")
    elif _dims_unencoded(ctx):
        out.append(f"{_dims_label(ctx)} dimensions are not encoded")
    elif rule is not None and rule.site_standard_blocks_dimensional:
        out.append(f"site standard requires survey: {rule.site_standard or 'site standard'}")

    dim = i.dimensional
    if dim.area_conforms is False and rule is not None and rule.min_lot_sf is not None:
        out.append(f"lot area is below the {rule.min_lot_sf:.0f} sf minimum in all sources")
    elif dim.component.status in ("known", "range") and dim.scenarios:
        interior = dim.scenarios[0]
        corner = dim.scenarios[1] if len(dim.scenarios) > 1 else None
        if corner is not None and corner.score == 0 < interior.score:
            out.append(f"corner status may reduce the illustrative width below {policy.WIDTH_PARTIAL_FT:g} ft")
        elif corner is not None and corner.score < interior.score:
            out.append("corner/frontage status remains unverified")
        elif interior.score == 1:
            out.append("narrow illustrative envelope")
        elif interior.score == 0:
            out.append(f"illustrative envelope narrower than {policy.WIDTH_PARTIAL_FT:g} ft")

    blocked = bool(critical) or i.outcome is Outcome.DO_NOT_ADVANCE
    caveat = policy.DISTRICT_CAVEATS.get(rule.district) if rule is not None else None
    if caveat and i.outcome is not Outcome.DO_NOT_ADVANCE:
        out.append(caveat)
    hz = _hazard_barrier(i.hazard_families)
    if hz and not blocked:
        out.append(hz)
    return out
