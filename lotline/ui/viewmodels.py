"""View models for the Streamlit app: pure functions of snapshot + engine results.

Rules: never compute a score, outcome, conflict, barrier or next check here.
Every decision-bearing string is copied from ``ScreeningResult``; raw parcel
facts are shown as recorded, with their sources. Ordering choices (outcome
groups, sale order) are presentation only and are documented on screen.
"""

from __future__ import annotations

import json
import csv
import io
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from lotline.engine import screen
from lotline.engine.checks import is_standard
from lotline.engine import policy
from lotline.engine.scoring import component_display
from lotline.loaders import DATA_DIR, context_for, lookup_pin
from lotline.models import (
    ComponentScore,
    ConflictLevel,
    Fact,
    NextCheck,
    Outcome,
    ScreeningResult,
    Snapshot,
    derived_fact_id,
)
from lotline.ui import text

DEMO_CONFIG_FILE = DATA_DIR / "demo_config.json"
ROUTING = (Outcome.OUT_OF_UNIVERSE, Outcome.STRUCTURE)

SOURCE_NAMES: dict[str, str] = {
    "wprdc_treasury_sales": "WPRDC Treasury Sales (open data)",
    "city_advertisement": "City Treasurer Sale advertisement",
    "treasurer_sale_regulations": "Treasurer Sale regulations",
    "county_assessments": "Allegheny County assessments",
    "county_parcels": "County parcels GIS (PASDA)",
    "city_zoning": "City zoning districts (GIS)",
    "landslide_prone": "City landslide-prone layer",
    "slope25": "City 25%+ slope layer",
    "undermined": "City undermined-areas layer",
    "fema_nfhl": "FEMA National Flood Hazard Layer",
    "pli_violations": "PLI code violations",
    "condemned_properties": "PLI condemned / dead-end properties",
    "rco_overlays": "Registered Community Organizations",
    "historic_overlays": "City historic districts",
    "zoning_code": "Pittsburgh Zoning Code (encoded rules)",
    "engine": "LotLine engine (derived)",
}


# --------------------------------------------------------------------------
# Small formatting helpers (no decisions)
# --------------------------------------------------------------------------


def short_pin(pin: str) -> str:
    """Map-block-lot form of a 16-character PIN, e.g. ``131-N-31``."""
    base = f"{int(pin[:4])}-{pin[4]}-{int(pin[5:10])}"
    supp = pin[10:14].lstrip("0")
    return f"{base}-{supp}" if supp else base


def fmt_value(value: object, unit: str | None = None) -> str:
    if value is None:
        return "none recorded"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (tuple, list)):
        return "; ".join(str(v) for v in value) if value else "none"
    if isinstance(value, float):
        if unit == "USD":
            return f"${value:,.2f}"
        shown = f"{value:,.0f}" if value.is_integer() else f"{value:,.2f}"
        return f"{shown} {unit}" if unit and unit not in ("ratio",) else shown
    if isinstance(value, int) and unit:
        return f"{value} {unit}"
    return str(value)


def _money(v: float | None) -> str:
    return "not recorded" if v is None else f"${v:,.2f}"


def _sf(v: float | None) -> str:
    return "not recorded" if v is None else f"{v:,.0f} sf"


def parcel_label(snapshot: Snapshot, pin: str) -> str:
    facts = snapshot.parcels.get(pin)
    t = snapshot.treasury[pin]
    loc = facts.location.split(" (")[0] if facts else t.address.split(",")[0].title()
    return f"{loc}, {t.neighborhood} ({short_pin(pin)})"


def snapshot_date(snapshot: Snapshot) -> str:
    entry = snapshot.manifest.get("wprdc_treasury_sales")
    return entry.snapshot_as_of if entry else "unknown"


def source_date(snapshot: Snapshot, source_id: str) -> str:
    entry = snapshot.manifest.get(source_id)
    return entry.snapshot_as_of if entry else "unknown"


def display_date(value: str) -> str:
    """Human-readable date for display; preserve unexpected source values."""
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return value
    return f"{parsed.month}/{parsed.day}/{parsed.year}"


def display_date_long(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return value
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def sale_date(snapshot: Snapshot) -> str:
    dates = {record.sale_date for record in snapshot.treasury.values()}
    return next(iter(dates)) if len(dates) == 1 else "unknown"


def outcome_meaning(snapshot: Snapshot, result: ScreeningResult) -> str:
    """Reason-specific display meaning, using engine state without revising it."""
    if result.outcome is Outcome.OUT_OF_UNIVERSE:
        advert_date = display_date(source_date(snapshot, "city_advertisement"))
        return ("Listed in the open-data Treasury feed but not in the City advertisement dated "
                f"{advert_date}, so it is outside this sale as advertised.")
    if result.outcome is not Outcome.DEFER_RECORDS:
        return text.OUTCOME_MEANING[result.outcome]

    critical = [c for c in result.conflicts if c.level is ConflictLevel.CRITICAL]
    if critical:
        return ("A critical public-record conflict prevents whole-parcel scoring. Resolve the named "
                "record or current-condition conflict before staff review continues.")
    material = [c for c in result.conflicts if c.level is ConflictLevel.MATERIAL]
    if material:
        affected = ", ".join(dict.fromkeys(a for c in material for a in c.affects)) or "affected"
        return (f"A material public-record conflict withholds the {affected} component. Resolve the "
                "named source disagreement before staff review continues.")
    withheld = next((c for c in (result.use, result.dimensional, result.environment)
                     if c is not None and c.status == "withheld"), None)
    if withheld is not None:
        reason = withheld.short_reason or withheld.reason or "required input is missing"
        return (f"The {withheld.name} component is withheld: {reason}. Complete the named next check "
                "before staff review continues.")
    return text.OUTCOME_MEANING[result.outcome]


def snapshot_dates(snapshot: Snapshot) -> list[tuple[str, str]]:
    m = snapshot.manifest
    pairs = [
        ("Treasury list", "wprdc_treasury_sales"),
        ("City advertisement", "city_advertisement"),
        ("Assessments", "county_assessments"),
        ("County parcels", "county_parcels"),
        ("City GIS & PLI", "city_zoning"),
    ]
    return [(label, m[sid].snapshot_as_of) for label, sid in pairs if sid in m]


def trigger_plain(trigger: str) -> str:
    if trigger in text.TRIGGER_PLAIN:
        return text.TRIGGER_PLAIN[trigger]
    if trigger.startswith("routing: "):
        return trigger.removeprefix("routing: ").capitalize()
    return trigger


def first_specific_check(result: ScreeningResult) -> NextCheck | None:
    """First parcel-specific check (not a standard check); else the first check."""
    for nc in result.next_checks:
        if not is_standard(nc):
            return nc
    return result.next_checks[0] if result.next_checks else None


# --------------------------------------------------------------------------
# Screening all records
# --------------------------------------------------------------------------


def screen_all(snapshot: Snapshot, today: date | None = None) -> dict[str, ScreeningResult]:
    out: dict[str, ScreeningResult] = {}
    for pin in snapshot.treasury:
        ctx = context_for(snapshot, pin)
        assert ctx is not None
        out[pin] = screen(ctx, today=today)
    return out


def all_warnings(results: Mapping[str, ScreeningResult]) -> list[str]:
    return sorted({w for r in results.values() for w in r.warnings})


# --------------------------------------------------------------------------
# Demo config
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DemoConfig:
    parcels: dict[str, str]  # key -> canonical PIN (only entries that resolved)
    captions: dict[str, str]
    default_packet: str | None
    compare_default: tuple[str, str] | None
    hero_buttons: tuple[str, ...]


def load_demo_config(snapshot: Snapshot, path: Path = DEMO_CONFIG_FILE) -> DemoConfig:
    """Resolve configured parcels against the snapshot; mismatches are dropped."""
    try:
        raw = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        raw = {}
    parcels: dict[str, str] = {}
    captions: dict[str, str] = {}
    for key, spec in (raw.get("parcels") or {}).items():
        pin = lookup_pin(snapshot, str(spec.get("pin", "")))
        if pin is None:
            continue
        facts = snapshot.parcels.get(pin)
        loc, nbhd = spec.get("location"), spec.get("neighborhood")
        if facts is not None and (
            (loc and not facts.location.startswith(loc)) or (nbhd and facts.neighborhood != nbhd)
        ):
            continue
        parcels[key] = pin
        if spec.get("caption"):
            captions[pin] = str(spec["caption"])
    pair = [parcels.get(k) for k in raw.get("compare_default", [])]
    compare = (pair[0], pair[1]) if len(pair) == 2 and all(pair) else None
    return DemoConfig(
        parcels=parcels,
        captions=captions,
        default_packet=parcels.get(raw.get("default_packet", "")),
        compare_default=compare,  # type: ignore[arg-type]
        hero_buttons=tuple(k for k in raw.get("hero_buttons", []) if k in parcels),
    )


# --------------------------------------------------------------------------
# View 1: sale pipeline
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Funnel:
    treasury: int
    advertised: int
    pins_matched: int
    prices_agree: int
    not_advertised: int
    advert_not_in_treasury: int
    structures: int
    vacant: int


def funnel(snapshot: Snapshot, results: Mapping[str, ScreeningResult]) -> Funnel:
    rec = snapshot.reconciliation
    return Funnel(
        treasury=rec.treasury_count,
        advertised=rec.advertised_count,
        pins_matched=len(rec.matched_pins),
        prices_agree=len(rec.price_check_pass),
        not_advertised=sum(r.outcome is Outcome.OUT_OF_UNIVERSE for r in results.values()),
        advert_not_in_treasury=len(rec.unmatched_advert_pins),
        structures=sum(r.outcome is Outcome.STRUCTURE for r in results.values()),
        vacant=sum(r.outcome not in ROUTING for r in results.values()),
    )


def _outcome_rank(o: Outcome) -> int:
    return text.OUTCOME_ORDER.index(o)


def vacant_pins(snapshot: Snapshot, results: Mapping[str, ScreeningResult]) -> list[str]:
    """Advertised vacant lots in triage order: outcome group, then sale number."""
    pins = [p for p, r in results.items() if r.outcome not in ROUTING]

    def key(p: str) -> tuple[int, int, str]:
        adv = snapshot.advert.get(p)
        return (_outcome_rank(results[p].outcome), adv.sale_no if adv else 10**6, p)

    return sorted(pins, key=key)


TRIAGE_COLUMNS = (
    "Sale #", "Parcel", "Outcome", "Development Ease",
    "Evidence", "Principal barrier", "First parcel-specific check", "Who resolves it",
)


def triage_rows(snapshot: Snapshot, results: Mapping[str, ScreeningResult]) -> list[dict[str, object]]:
    rows = []
    for pin in vacant_pins(snapshot, results):
        r = results[pin]
        f = snapshot.parcels.get(pin)
        adv = snapshot.advert.get(pin)
        nc = first_specific_check(r)
        rows.append({
            "pin": pin,
            "Sale #": adv.sale_no if adv else None,
            "Parcel": ((f.location.split(" (")[0] if f else snapshot.treasury[pin].address)
                       + f" · {snapshot.treasury[pin].neighborhood}"),
            "Outcome": text.OUTCOME_SHORT[r.outcome],
            "Development Ease": r.ease.display if r.ease else "n/a",
            "Evidence": r.coverage_display,
            "Principal barrier": r.barriers[0] if r.barriers else "none listed",
            "First parcel-specific check": nc.check if nc else "",
            "Who resolves it": nc.owner if nc else "",
        })
    return rows


def outcome_counts(results: Mapping[str, ScreeningResult]) -> list[tuple[Outcome, int]]:
    counts = {o: 0 for o in text.OUTCOME_ORDER}
    for r in results.values():
        counts[r.outcome] += 1
    return [(o, n) for o, n in counts.items() if n and o not in ROUTING]


def routed_rows(
    snapshot: Snapshot, results: Mapping[str, ScreeningResult], outcome: Outcome
) -> list[dict[str, object]]:
    """Routed records: address, class, reason. No owner data is loaded or shown."""
    rows = []
    for pin, r in results.items():
        if r.outcome is not outcome:
            continue
        t = snapshot.treasury[pin]
        rows.append({
            "PIN": short_pin(pin),
            "Address": t.address,
            "Neighborhood": t.neighborhood,
            "Class": t.classdesc,
            "Assessment use": t.usedesc,
            "Reason": r.barriers[0] if r.barriers else text.OUTCOME_MEANING[outcome],
        })
    return sorted(rows, key=lambda d: (str(d["Neighborhood"]), str(d["Address"])))


# --------------------------------------------------------------------------
# View 2: parcel packet
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ComponentVM:
    name: str
    label: str
    value: str  # engine component_display: "2", "1-2", "withheld", "n/a"
    status: str
    status_plain: str
    short_reason: str
    reason: str
    withheld: bool


@dataclass(frozen=True)
class ConflictVM:
    level: str
    kind: str
    summary: str  # engine text, verbatim
    affects: tuple[str, ...]
    fact_ids: tuple[str, ...]


@dataclass(frozen=True)
class TileVM:
    key: str
    title: str
    rows: list[tuple[str, str]]
    flags: list[str]
    unknown: str


@dataclass(frozen=True)
class AreaVM:
    assessment_sf: str
    county_gis_sf: str
    minimum_sf: str | None
    gap_pct: str
    gap_formula: str
    symmetric_pct: str
    symmetric_formula: str


@dataclass
class PacketVM:
    pin: str
    pin_short: str
    title: str
    neighborhood: str
    address: str
    outcome: Outcome
    outcome_label: str
    outcome_meaning: str
    tone: str
    routing: bool
    conflicts: list[ConflictVM] = field(default_factory=list)
    ease_display: str = "n/a"
    ease_band: str | None = None
    components: list[ComponentVM] = field(default_factory=list)
    coverage: list[tuple[str, str, bool]] = field(default_factory=list)
    coverage_display: str = "n/a"
    tiles: list[TileVM] = field(default_factory=list)
    treasurer_sale: bool = False
    acquisition: list[tuple[str, str]] = field(default_factory=list)
    barriers: list[str] = field(default_factory=list)
    next_checks: list[dict[str, str]] = field(default_factory=list)
    provenance: list[dict[str, str]] = field(default_factory=list)
    area: AreaVM | None = None
    warnings: list[str] = field(default_factory=list)
    caption: str | None = None
    hazard_families: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NotFound:
    query: str
    message: str


def not_found_message(snapshot: Snapshot) -> str:
    return f"PIN not found in snapshot dated {snapshot_date(snapshot)}"


def resolve_query(snapshot: Snapshot, query: str) -> str | NotFound:
    pin = lookup_pin(snapshot, query)
    if pin is None:
        return NotFound(query=query, message=not_found_message(snapshot))
    return pin


def _component_vm(c: ComponentScore) -> ComponentVM:
    return ComponentVM(
        name=c.name,
        label=text.COMPONENT_LABEL.get(c.name, c.name),
        value=component_display(c),
        status=c.status,
        status_plain=text.COMPONENT_STATUS_PLAIN.get(c.status, c.status),
        short_reason=c.short_reason or c.reason or "Reason not recorded",
        reason=c.reason or "",
        withheld=c.status == "withheld",
    )


def _fact(result: ScreeningResult, fid: str) -> Fact | None:
    return next((f for f in result.facts if f.id == fid), None)


def _area_vm(snapshot: Snapshot, pin: str, result: ScreeningResult) -> AreaVM | None:
    f = snapshot.parcels.get(pin)
    if f is None or result.area_gap_pct is None:
        return None
    gap = _fact(result, derived_fact_id(pin, "area_gap_pct"))
    sym = _fact(result, derived_fact_id(pin, "area_gap_symmetric_pct"))
    rule = context_for(snapshot, pin).rule  # type: ignore[union-attr]
    return AreaVM(
        assessment_sf=_sf(f.assess_lotarea_sf),
        county_gis_sf=_sf(f.county_gis_area_sf),
        minimum_sf=_sf(rule.min_lot_sf) if rule and rule.min_lot_sf is not None else None,
        gap_pct=f"{result.area_gap_pct:+.1f}%",
        gap_formula=(gap.note if gap and gap.note else "(county_gis_area - assessment_lotarea) / assessment_lotarea"),
        symmetric_pct=f"{result.area_gap_symmetric_pct:.1f}%",
        symmetric_formula=(sym.note if sym and sym.note else "|a - b| / max(a, b)"),
    )


def _tiles(snapshot: Snapshot, pin: str, result: ScreeningResult) -> list[TileVM]:
    ctx = context_for(snapshot, pin)
    assert ctx is not None
    f, rule, t = ctx.facts, ctx.rule, ctx.treasury
    if f is None:
        return []

    # Zoning
    z_rows: list[tuple[str, str]] = []
    district = f.zoning_polygon
    if t.zon_code and t.zon_code != f.zoning_polygon:
        district += f" (assessment record lists {t.zon_code})"
    z_rows.append(("District (zoning map)", district))
    z_rows.append(("Housing use path (§911.02)", result.use.reason if result.use and result.use.reason
                   else "district rules not encoded"))
    area = f"Assessment {_sf(f.assess_lotarea_sf)} · County GIS {_sf(f.county_gis_area_sf)}"
    if rule is not None and rule.min_lot_sf is not None:
        area += f" · district minimum {_sf(rule.min_lot_sf)}"
    elif rule is not None and not rule.dimensions_encoded:
        area += " · district minimum not encoded in v1"
    z_rows.append(("Lot area (both sources)", area))
    z_rows.append(("Base-setback screen", result.setback_screen))
    overlays = [o for o in (f.other_overlay,) if o]
    if f.slope25:
        overlays.append("25%+ slope layer overlaps: steep-slope standards may apply (§906.08; counted once, under environment)")
    if rule is not None and rule.site_standard_summary:
        sentences = [s.strip() for s in rule.site_standard_summary.split(". ") if s.strip()]
        if not f.slope25:
            sentences = [s for s in sentences if "§906.08" not in s]
        summary = ". ".join(sentences)
        if summary and not summary.endswith("."):
            summary += "."
        if summary:
            overlays.append(f"Site standards: {summary}")
    z_rows.append(("Overlays & site standards", "; ".join(overlays) if overlays else "none recorded"))
    z_flags = [c.summary for c in result.conflicts if c.kind == "lot_area"]

    # Environmental
    e_rows = [
        ("Landslide-prone", fmt_value(f.landslide_prone)),
        ("25%+ slope", fmt_value(f.slope25)),
        ("Undermined", fmt_value(f.undermined)),
        ("FEMA flood zone", f.fema_zone + (" (Special Flood Hazard Area)" if f.fema_sfha else "")),
        ("Hazard families flagged", ", ".join(result.hazard_families)
         if result.hazard_families else "none (no overlap in the checked screening layers)"),
    ]
    e_flags = [f"{fam} flagged in screening layers" for fam in result.hazard_families]

    # Infrastructure
    i_rows = [
        ("Streets within 30 ft", ", ".join(f.streets_within_30ft) if f.streets_within_30ft else "none found"),
        ("Possible corner lot", "yes (geometry heuristic; unverified)" if f.possible_corner
         else "no indication (geometry heuristic)"),
    ]
    i_flags = ["Corner/frontage status unverified"] if f.possible_corner else []

    # Policy / acquisition route
    p_rows: list[tuple[str, str]] = []
    if t.delq_prior_years is not None:
        p_rows.append(("Tax delinquency", f"{t.delq_prior_years:g} prior years"))
    p_rows.append(("Registered Community Organization", f"{f.rco} (contact for community review; not endorsement)"
                   if f.rco else "none recorded"))
    p_rows.append(("Historic district", f.historic_district or "none recorded"))
    p_rows.append(("PLI code cases", f"{f.pli_unique_casefiles} case files; {f.pli_open_or_in_court} open or in court"))
    if f.condemned_case_active:
        cond = "active condemned/dead-end case"
        if f.condemned_case_created:
            cond += f" (created {f.condemned_case_created}"
            cond += f", address {f.condemned_case_address})" if f.condemned_case_address else ")"
        p_rows.append(("Condemned / dead-end", cond))
    else:
        p_rows.append(("Condemned / dead-end", "no active case recorded"))
    p_flags = [c.summary for c in result.conflicts if c.kind == "current_condition"]

    return [
        TileVM("zoning", "Zoning", z_rows, z_flags, text.TILE_UNKNOWN["zoning"]),
        TileVM("environmental", "Environmental", e_rows, e_flags, text.TILE_UNKNOWN["environmental"]),
        TileVM("infrastructure", "Infrastructure", i_rows, i_flags, text.TILE_UNKNOWN["infrastructure"]),
        TileVM("policy", "Policy / acquisition route", p_rows, p_flags, text.TILE_UNKNOWN["policy"]),
    ]


def provenance_rows(result: ScreeningResult) -> list[dict[str, str]]:
    rows = []
    for f in result.facts:
        rows.append({
            "Fact ID": f.id,
            "Field": f.field,
            "Value": fmt_value(f.value, f.unit),
            "Source": SOURCE_NAMES.get(f.source, f.source),
            "As of": f.as_of,
            "Evidence class": f.evidence_class,
            "Conflict group": f.conflict_group or "",
            "Note": f.note or "",
        })
    # Conflict-group facts first so the disagreement is visible at the top.
    return sorted(rows, key=lambda r: (r["Conflict group"] == "",))


def next_check_rows(result: ScreeningResult) -> list[dict[str, str]]:
    return [
        {"Check": nc.check, "Who resolves it": nc.owner, "Reason listed": trigger_plain(nc.trigger),
         "Standard": ("pre-spend" if nc.trigger == policy.CURRENT_SALE_STATUS_TRIGGER else
                      "yes" if is_standard(nc) else "no")}
        for nc in result.next_checks
    ]


def packet(
    snapshot: Snapshot, results: Mapping[str, ScreeningResult], pin: str,
    captions: Mapping[str, str] | None = None,
) -> PacketVM:
    r = results[pin]
    t = snapshot.treasury[pin]
    f = snapshot.parcels.get(pin)
    routing = r.outcome in ROUTING
    vm = PacketVM(
        pin=pin,
        pin_short=short_pin(pin),
        title=f.location if f else t.address.split(",")[0].title(),
        neighborhood=t.neighborhood,
        address=t.address,
        outcome=r.outcome,
        outcome_label=r.outcome.value,
        outcome_meaning=outcome_meaning(snapshot, r),
        tone=text.OUTCOME_TONE[r.outcome],
        routing=routing,
        conflicts=[ConflictVM(c.level.value, c.kind, c.summary, c.affects, c.fact_ids) for c in r.conflicts],
        ease_display=r.ease.display if r.ease else "n/a",
        ease_band=r.ease.band if r.ease else None,
        barriers=list(r.barriers),
        next_checks=next_check_rows(r),
        provenance=provenance_rows(r),
        warnings=list(r.warnings),
        caption=(captions or {}).get(pin),
        hazard_families=list(r.hazard_families),
    )
    if routing:
        return vm
    vm.components = [_component_vm(c) for c in (r.use, r.dimensional, r.environment) if c is not None]
    labels = text.COVERAGE_PLAIN
    vm.coverage = [(g, labels.get(g, g), ok) for g, ok in r.coverage.items()]
    vm.coverage_display = r.coverage_display
    vm.tiles = _tiles(snapshot, pin, r)
    adv = snapshot.advert.get(pin) if pin in snapshot.reconciliation.matched_pins else None
    vm.treasurer_sale = adv is not None
    if adv is not None:
        land = f.assessed_land_value if f else t.fm_land
        vm.acquisition = [
            ("Upset price (opening bid)", _money(adv.upset)),
            ("Assessed land value", _money(land)),
        ]
        if r.upset_to_assessed_land is not None:
            vm.acquisition.append((
                "Upset ÷ assessed land value",
                f"{r.upset_to_assessed_land:g}× — {text.ACQUISITION_BURDEN_NOTE}",
            ))
    vm.area = _area_vm(snapshot, pin, r)
    return vm


def lot_options(snapshot: Snapshot, results: Mapping[str, ScreeningResult]) -> list[tuple[str, str]]:
    return [(p, parcel_label(snapshot, p)) for p in vacant_pins(snapshot, results)]


def packet_markdown(snapshot: Snapshot, result: ScreeningResult, packet_vm: PacketVM) -> str:
    """Deterministic, handoff-ready packet; never exports UI checkbox state as verified."""
    p = packet_vm
    lines = [
        f"# LotLine screening packet: {p.title}",
        "",
        f"PIN: {p.pin_short}  ",
        f"Neighborhood: {p.neighborhood}  ",
        "Snapshot: " + " · ".join(f"{label} {value}" for label, value in snapshot_dates(snapshot)),
        "",
        f"## Outcome\n\n{p.outcome_label}\n\n{p.outcome_meaning}",
        "",
        f"## Development Ease\n\n{p.ease_display}",
    ]
    critical = any(c.level == "critical" for c in p.conflicts)
    if critical:
        lines += ["", "Component values are withheld because a critical conflict prevents whole-parcel scoring."]
    else:
        for component in p.components:
            lines.append(f"- {component.label}: {component.value} — {component.reason}")
    lines += ["", f"Evidence coverage: {p.coverage_display}", "", "## Records conflicts"]
    if p.conflicts:
        for conflict in p.conflicts:
            ids = ", ".join(conflict.fact_ids) or "none"
            lines.append(f"- {conflict.level.title()}: {conflict.summary} Citations: {ids}")
    else:
        lines.append("- None identified by the engine.")
    lines += ["", "## Principal barriers"]
    lines += [f"{i}. {barrier}" for i, barrier in enumerate(p.barriers, 1)] or ["- None listed by the engine."]
    lines += ["", "## Unresolved checks (not yet verified)"]
    for check in p.next_checks:
        lines.append(f"- [ ] {check['Check']} — {check['Who resolves it']} — {check['Reason listed']}")

    from lotline.memo.deterministic import deterministic_memo
    memo = deterministic_memo(result)
    lines += ["", "## Deterministic cited memo"]
    for claim in memo.claims:
        citations = ", ".join(claim.fact_ids) or "no fact ID (caveat)"
        lines.append(f"- {claim.text}  ")
        lines.append(f"  Citations: {citations}")
    lines += [
        "", "## Limits", "",
        "Decision support only — not legal, financial, title, survey or zoning advice.",
        "Screening layers are not geotechnical or flood determinations. Contextual setbacks, utilities, "
        "legal access, title, market demand, appraisal and community-plan alignment are not established.",
        "Sale status may change by payment or court order; verify it before incurring costs.",
    ]
    return "\n".join(lines) + "\n"


def triage_csv(snapshot: Snapshot, results: Mapping[str, ScreeningResult]) -> str:
    """CSV handoff of engine-rendered triage rows, preserving no-ranking framing."""
    rows = triage_rows(snapshot, results)
    output = io.StringIO()
    fields = ["Framing", *TRIAGE_COLUMNS]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({"Framing": "Triage, not ranking", **row})
    return output.getvalue()


# --------------------------------------------------------------------------
# View 3: compare
# --------------------------------------------------------------------------

COMPARE_ROWS = ("Outcome", "Development Ease", "Components", "Evidence coverage",
                "Principal barrier", "Next check")


def compare_columns(
    snapshot: Snapshot, results: Mapping[str, ScreeningResult], pins: Iterable[str]
) -> dict[str, dict[str, str]]:
    """{parcel label: {row: value}} with exactly the contract's comparison rows."""
    out: dict[str, dict[str, str]] = {}
    for pin in pins:
        r = results[pin]
        comps = [c for c in (r.use, r.dimensional, r.environment) if c is not None]
        critical = any(c.level is ConflictLevel.CRITICAL for c in r.conflicts)
        nc = first_specific_check(r)
        out[parcel_label(snapshot, pin)] = {
            "Outcome": r.outcome.value,
            "Development Ease": r.ease.display if r.ease else "n/a",
            "Components": ("Not shown: critical conflict prevents parcel scoring" if critical else
                           ", ".join(f"{c.name} {component_display(c)}" for c in comps) or "n/a (routed)"),
            "Evidence coverage": r.coverage_display,
            "Principal barrier": r.barriers[0] if r.barriers else "none listed",
            "Next check": f"{nc.check} ({nc.owner})" if nc else "none listed",
        }
    return out


def _families(r: ScreeningResult) -> str:
    return ", ".join(r.hazard_families) if r.hazard_families else "no hazard family"


def difference_line(
    snapshot: Snapshot, results: Mapping[str, ScreeningResult], pin_a: str, pin_b: str
) -> str:
    """One line built only from engine fields: hazard families, corner range, conflicts, outcome."""
    a, b = results[pin_a], results[pin_b]
    na = parcel_label(snapshot, pin_a).split(" (")[0].split(",")[0]
    nb = parcel_label(snapshot, pin_b).split(" (")[0].split(",")[0]
    if na == nb:
        na, nb = f"{na} ({short_pin(pin_a)})", f"{nb} ({short_pin(pin_b)})"
    parts: list[str] = []
    if pin_a == pin_b:
        return "Same parcel selected twice."
    if set(a.hazard_families) != set(b.hazard_families):
        parts.append(f"screening layers flag {_families(a)} for {na} vs {_families(b)} for {nb}")
        if a.environment is not None and b.environment is not None:
            parts.append(f"environment component {component_display(a.environment)} vs "
                         f"{component_display(b.environment)}")
    ra = a.dimensional is not None and a.dimensional.status == "range"
    rb = b.dimensional is not None and b.dimensional.status == "range"
    if ra and rb:
        parts.append("both have unverified corner status, so dimensional fit is a range for both")
    elif ra or rb:
        parts.append(f"{na if ra else nb} has unverified corner status (dimensional range)")
    wa = a.dimensional is not None and a.dimensional.status == "withheld"
    wb = b.dimensional is not None and b.dimensional.status == "withheld"
    if wa != wb:
        who, comp = (na, a.dimensional) if wa else (nb, b.dimensional)
        parts.append(f"{who} has dimensional withheld ({comp.reason})")  # type: ignore[union-attr]
    la = {c.level for c in a.conflicts if c.level is not ConflictLevel.DISCLOSE}
    lb = {c.level for c in b.conflicts if c.level is not ConflictLevel.DISCLOSE}
    if la != lb:
        for name, levels in ((na, la), (nb, lb)):
            if levels:
                parts.append(f"{name} has a {' and '.join(sorted(l.value for l in levels))} record conflict")
    if a.outcome is not b.outcome:
        parts.append(f"outcomes differ ({a.outcome.value} vs {b.outcome.value})")
    if not parts:
        return "The engine reports the same outcome, hazard families, corner status and conflict level for both."
    joined = "; ".join(parts)
    return joined[0].upper() + joined[1:] + "."


# --------------------------------------------------------------------------
# View 4: integrity
# --------------------------------------------------------------------------


def source_rows(snapshot: Snapshot) -> list[dict[str, str]]:
    return [
        {
            "Source": SOURCE_NAMES.get(e.source_id, e.source_id),
            "Source ID": e.source_id,
            "As of": e.snapshot_as_of,
            "Queried": "yes" if e.query_completed else "no",
            "Local artifact": e.local_artifact,
            "Scope": e.scope,
        }
        for e in snapshot.manifest.values()
    ]


def evidence_class_counts(results: Mapping[str, ScreeningResult], pins: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in pins:
        for f in results[p].facts:
            counts[f.evidence_class] = counts.get(f.evidence_class, 0) + 1
    return counts
