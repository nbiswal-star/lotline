"""Typed records shared by loaders, engine, memo and UI.

This module is the contract between layers. Loaders produce these records;
the engine consumes them and returns ``ScreeningResult``. Nothing downstream
of the loaders sees raw CSV strings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


# --------------------------------------------------------------------------
# FEMA NFHL flood-zone vocabulary (shared by the loader and the engine)
# --------------------------------------------------------------------------

# SFHA (1% annual chance) zones.
_SFHA_ZONE = re.compile(r"^(A|AE|AH|AO|AR|A99|A\d{1,2}|V|VE|V\d{1,2}|AR/A[EHO0-9]*)$")
# Recognized zones outside the SFHA (X500, B and C are legacy notations).
_NON_SFHA_ZONES = frozenset({
    "X", "X (SHADED)", "SHADED X", "X500", "B", "C", "0.2 PCT ANNUAL CHANCE FLOOD HAZARD",
})
_PARTIAL = re.compile(r"\(?\s*PARTIAL\s*\)?")


def sfha_status(fema_zone: str) -> bool | None:
    """SFHA status of an NFHL zone string, validated against the zone vocabulary.

    Composite values such as "A (partial) + X" are split on "+", ",", ";" and
    "and". True if any part is an SFHA zone; otherwise None (unknown) if any
    part is zone D (flood hazard undetermined) or not a recognized NFHL code;
    otherwise False.
    """
    parts = [p for p in re.split(r"\+|,|;|\bAND\b", fema_zone.upper()) if p.strip()]
    if not parts:
        return None
    status: list[bool | None] = []
    for part in parts:
        z = re.sub(r"\s+", " ", _PARTIAL.sub(" ", part)).strip()
        if _SFHA_ZONE.match(z):
            status.append(True)
        elif z in _NON_SFHA_ZONES:
            status.append(False)
        else:  # zone D or an unrecognized code
            status.append(None)
    if any(s is True for s in status):
        return True
    if any(s is None for s in status):
        return None
    return False


# --------------------------------------------------------------------------
# Normalized inputs (produced by lotline.loaders)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ParcelFacts:
    """One row of data/parcel_facts.csv after loader normalization.

    Normalization rules (applied in the loader, never in the engine):
    - YES/yes/Y/true -> True; NO/no/N/false -> False.
    - blank, "none", "none found" -> None for optional text fields.
    - ``rco_overlay`` values in parentheses (e.g. "(45 ft max height overlay)")
      are overlay notes, not Registered Community Organizations: they go to
      ``other_overlay`` and ``rco`` is None.
    - ``fema_sfha`` is True when ``fema_zone`` contains a Special Flood Hazard
      Area zone (A, AE, AH, AO, AR, A99, V, VE ...), including "A (partial) + X";
      False when every part is a recognized non-SFHA zone (X, "X (shaded)", B, C);
      None (unknown) when the zone is D (undetermined) or not a recognized NFHL code.
    - Lot areas and bounding-rectangle sides of 0 are treated as unknown (None)
      and noted in ``load_warnings``; negative values are rejected.
    - ``streets_within_30ft`` is split on ";" and stripped.
    """

    pin: str
    location: str
    neighborhood: str
    zone: str
    zoning_polygon: str
    assess_lotarea_sf: float | None
    county_gis_area_sf: float | None
    mbr_short_side_ft: float | None
    mbr_long_side_ft: float | None
    upset_price: float | None
    assessed_land_value: float | None
    pli_unique_casefiles: int
    pli_open_or_in_court: int
    pli_latest_event: str | None
    condemned_case_active: bool
    condemned_case_created: str | None
    condemned_case_address: str | None
    rco: str | None
    other_overlay: str | None
    historic_district: str | None
    slope25: bool
    undermined: bool
    landslide_prone: bool
    fema_zone: str
    fema_sfha: bool | None  # None: zone D (undetermined) or unrecognized -> unknown
    streets_within_30ft: tuple[str, ...]
    possible_corner: bool
    # Load-time notes about values treated as unknown (e.g. "0 sf recorded").
    load_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class TreasuryRecord:
    """One WPRDC Treasury Sales record (96-row snapshot).

    Loaders must never select ``in_city_advert_2026_09_16``, ``advert_sale_no``
    or ``advert_match_method``; those are expected labels. Owner and
    change-notice fields are dropped (``ownerdesc`` is not loaded either).
    """

    pin: str
    address: str
    neighborhood: str
    ward: str
    sale_date: str
    total_tax_due: float
    demo_cost_due: float
    classdesc: str
    usedesc: str
    lotarea: float | None
    fm_land: float | None
    fm_bldg: float | None
    zon_code: str | None
    asof: str
    delq_prior_years: float | None
    pli_event_rows: float | None

    @property
    def is_structure(self) -> bool:
        """Vacancy is decided by assessment use description only."""
        return "VACANT" not in self.usedesc.upper()


@dataclass(frozen=True)
class AdvertRecord:
    """One row of the City advertisement dated 2026-09-16.

    Only these five columns may be loaded; ``pin_match`` and ``price_check``
    are recomputed at runtime.
    """

    sale_no: int
    account: str
    pin: str
    ad_address: str
    upset: float


@dataclass(frozen=True)
class DistrictRule:
    """One row of data/district_rules.csv. Blank numeric cells stay None."""

    district: str
    single_unit_permission: str  # "P" | "A" | "S" | "C" | "PROHIBITED"
    two_unit_permission: str
    min_lot_sf: float | None
    front_setback_ft: float | None
    rear_setback_ft: float | None
    exterior_side_ft: float | None
    interior_side_ft: float | None
    dimensions_applicable: bool
    dimensions_encoded: bool
    site_standard_blocks_dimensional: bool
    use_citation: str
    dimensional_citation: str | None
    site_standard: str | None
    # Rule provenance: code version the row was verified against (ecode360
    # "legislation through" date) and the amending ordinance, when recorded.
    rules_as_of: str | None = None
    amended_by: str | None = None


@dataclass(frozen=True)
class SourceEntry:
    source_id: str
    snapshot_as_of: str
    query_completed: bool
    local_artifact: str
    scope: str


@dataclass(frozen=True)
class Reconciliation:
    """Runtime match of Treasury candidates against the City advertisement."""

    treasury_count: int
    advertised_count: int
    matched_pins: frozenset[str]
    unmatched_treasury_pins: frozenset[str]  # in WPRDC, not advertised
    unmatched_advert_pins: frozenset[str]  # advertised, not in WPRDC
    price_check_pass: frozenset[str]  # advertised upset == Treasury total_tax_due
    price_check_fail: frozenset[str]


@dataclass(frozen=True)
class Snapshot:
    """Everything the app loads at startup, immutable."""

    treasury: dict[str, TreasuryRecord]
    advert: dict[str, AdvertRecord]
    parcels: dict[str, ParcelFacts]
    rules: dict[str, DistrictRule]
    manifest: dict[str, SourceEntry]
    reconciliation: Reconciliation
    # Load-time notes about values treated as unknown (e.g. a 0 sf Treasury lot area).
    load_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParcelContext:
    """All inputs the engine needs for one PIN."""

    pin: str
    treasury: TreasuryRecord
    advert: AdvertRecord | None  # None -> not in the City advertisement
    facts: ParcelFacts | None  # None -> no prepared parcel facts (e.g. structures)
    rule: DistrictRule | None  # None -> district rules not encoded
    manifest: dict[str, SourceEntry]


# --------------------------------------------------------------------------
# Flat fact records (Layer 2)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Fact:
    """Flat provenance record. ``id`` is ``PIN:field:source`` or ``RULE:district:field``."""

    id: str
    pin: str | None  # None for RULE: facts
    field: str
    value: object
    unit: str | None
    source: str  # source_id from source_manifest.csv
    as_of: str
    evidence_class: str  # "raw" | "derived" | "approximate" | "rule" | "untrusted_text"
    conflict_group: str | None = None
    district: str | None = None  # set for RULE: facts
    note: str | None = None  # derivation note for derived/approximate facts


# --------------------------------------------------------------------------
# Engine outputs (Layer 3)
# --------------------------------------------------------------------------


class Outcome(str, Enum):
    ADVANCE = "Advance to staff review"
    SIDE_YARD = "Potential side yard or stewardship"
    DEFER_RECORDS = "Defer: missing or conflicting records"
    DEFER_SITE = "Defer: site conditions unknown"
    DO_NOT_ADVANCE = "Do not advance for housing under stated screening policy"
    OUT_OF_UNIVERSE = "(routing) Out of sale universe"
    STRUCTURE = "(routing) Structure: vacant-land model not applicable"

    @property
    def reachable_in_v1(self) -> bool:
        return self is not Outcome.SIDE_YARD


class ConflictLevel(str, Enum):
    CRITICAL = "critical"
    MATERIAL = "material"
    DISCLOSE = "disclose"


@dataclass(frozen=True)
class Conflict:
    level: ConflictLevel
    kind: str  # "current_condition" | "lot_area" | "sale_universe" | "zoning_split" | "stale_source"
    fact_ids: tuple[str, ...]
    summary: str  # engine-authored, never selects a winning source
    affects: tuple[str, ...] = ()  # score components withheld, e.g. ("dimensional",)


@dataclass(frozen=True)
class DimensionalScenario:
    label: str  # "interior" | "corner"
    width_ft: float
    depth_ft: float
    score: int


@dataclass(frozen=True)
class ComponentScore:
    """A 0-2 component, possibly a range, withheld, or not applicable."""

    name: str  # "use" | "dimensional" | "environment"
    low: int | None
    high: int | None
    status: str  # "known" | "range" | "withheld" | "not_applicable"
    reason: str | None = None
    fact_ids: tuple[str, ...] = ()
    # Short plain-language reason used in the Partial display when withheld.
    short_reason: str | None = None


@dataclass(frozen=True)
class EaseResult:
    # e.g. "5-6 of 6: Apparently lower-discretion",
    # "5 of 6: Conditional (possible Steep Slope Overlay review, §906.08)",
    # "Partial: 3 of 4 known points; dimensional withheld (reason)", "Not scorable"
    display: str
    total_low: int | None
    total_high: int | None
    band: str | None


@dataclass(frozen=True)
class NextCheck:
    """An unresolved check with the human role that resolves it (escalation path)."""

    check: str  # canonical text, e.g. "contextual setbacks (Ch. 925)"
    owner: str  # e.g. "Zoning Administrator", "licensed surveyor", "title examiner"
    trigger: str  # why it is on the list ("base" or the rule that added it)


@dataclass
class ScreeningResult:
    pin: str
    outcome: Outcome
    conflicts: list[Conflict] = field(default_factory=list)
    use: ComponentScore | None = None
    dimensional: ComponentScore | None = None
    environment: ComponentScore | None = None
    scenarios: list[DimensionalScenario] = field(default_factory=list)
    setback_screen: str = "not computed"
    hazard_families: list[str] = field(default_factory=list)  # "terrain" | "undermining" | "FEMA SFHA"
    ease: EaseResult | None = None
    coverage: dict[str, bool] = field(default_factory=dict)  # G1..G5
    area_gap_pct: float | None = None
    area_gap_symmetric_pct: float | None = None
    upset_to_assessed_land: float | None = None
    barriers: list[str] = field(default_factory=list)
    next_checks: list[NextCheck] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def coverage_display(self) -> str:
        return f"{sum(self.coverage.values())}/{len(self.coverage)}" if self.coverage else "n/a"


# --------------------------------------------------------------------------
# Fact-ID convention (shared by facts builder, engine, memo and checker)
# --------------------------------------------------------------------------

# Which source_manifest.csv entry backs each normalized field.
FIELD_SOURCE: dict[str, str] = {
    # ParcelFacts
    "location": "county_assessments",
    "neighborhood": "county_assessments",
    "zone": "city_zoning",
    "zoning_polygon": "city_zoning",
    "assess_lotarea_sf": "county_assessments",
    "county_gis_area_sf": "county_parcels",
    "mbr_short_side_ft": "county_parcels",
    "mbr_long_side_ft": "county_parcels",
    "upset_price": "city_advertisement",
    "assessed_land_value": "county_assessments",
    "pli_unique_casefiles": "pli_violations",
    "pli_open_or_in_court": "pli_violations",
    "pli_latest_event": "pli_violations",
    "condemned_case_active": "condemned_properties",
    "condemned_case_created": "condemned_properties",
    "condemned_case_address": "condemned_properties",
    "rco": "rco_overlays",
    "other_overlay": "city_zoning",
    "historic_district": "historic_overlays",
    "slope25": "slope25",
    "undermined": "undermined",
    "landslide_prone": "landslide_prone",
    "fema_zone": "fema_nfhl",
    "fema_sfha": "fema_nfhl",
    "streets_within_30ft": "county_parcels",
    "possible_corner": "county_parcels",
    # TreasuryRecord
    "address": "wprdc_treasury_sales",
    "sale_date": "wprdc_treasury_sales",
    "total_tax_due": "wprdc_treasury_sales",
    "demo_cost_due": "wprdc_treasury_sales",
    "classdesc": "county_assessments",
    "usedesc": "county_assessments",
    "lotarea": "county_assessments",
    "fm_land": "county_assessments",
    "fm_bldg": "county_assessments",
    "delq_prior_years": "wprdc_treasury_sales",
    "ward": "wprdc_treasury_sales",
    "zon_code": "county_assessments",
    "asof": "county_assessments",
    "pli_event_rows": "pli_violations",
    # AdvertRecord
    "sale_no": "city_advertisement",
    "upset": "city_advertisement",
    "ad_address": "city_advertisement",
    "account": "city_advertisement",
}


def fact_id(pin: str, field_name: str, source: str | None = None) -> str:
    """``PIN:field:source``; source defaults to FIELD_SOURCE[field_name]."""
    return f"{pin}:{field_name}:{source or FIELD_SOURCE[field_name]}"


def rule_fact_id(district: str, field_name: str) -> str:
    return f"RULE:{district}:{field_name}"


def derived_fact_id(pin: str, name: str) -> str:
    """Engine-derived values, e.g. ``PIN:area_gap_pct:engine``."""
    return f"{pin}:{name}:engine"
