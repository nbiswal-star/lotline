"""Layer 2: flatten normalized records into provenance-carrying ``Fact`` records.

Every normalized input field becomes one ``Fact`` with a stable id
(``PIN:field:source`` or ``RULE:district:field``). Missing values are kept as
``value=None`` facts for parcel fields: "checked, nothing recorded" is itself
evidence the memo may cite. Rule facts skip None values (blank rule cells mean
"not applicable/unknown", not a value).

Engine-derived facts (area gap, envelopes, scores) are produced by the engine.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import fields

from lotline.models import (
    FIELD_SOURCE,
    AdvertRecord,
    DistrictRule,
    Fact,
    ParcelContext,
    ParcelFacts,
    SourceEntry,
    TreasuryRecord,
    fact_id,
    rule_fact_id,
)

RULE_SOURCE = "zoning_code"

# Treasury/advert fields whose source is not (or not uniquely) given by
# FIELD_SOURCE. ``neighborhood`` is listed because the Treasury record carries
# its own WPRDC neighborhood, distinct from the parcel-facts assessment one;
# an explicit source keeps both fact ids unique.
TREASURY_SOURCE_OVERRIDES: dict[str, str] = {
    "neighborhood": "wprdc_treasury_sales",
    "ward": "wprdc_treasury_sales",
    "zon_code": "county_assessments",
    "asof": "county_assessments",
    "pli_event_rows": "pli_violations",
}
ADVERT_SOURCE_OVERRIDES: dict[str, str] = {"account": "city_advertisement"}

UNITS: dict[str, str] = {
    "assess_lotarea_sf": "sf",
    "county_gis_area_sf": "sf",
    "lotarea": "sf",
    "min_lot_sf": "sf",
    "mbr_short_side_ft": "ft",
    "mbr_long_side_ft": "ft",
    "front_setback_ft": "ft",
    "rear_setback_ft": "ft",
    "exterior_side_ft": "ft",
    "interior_side_ft": "ft",
    "upset_price": "USD",
    "upset": "USD",
    "assessed_land_value": "USD",
    "total_tax_due": "USD",
    "demo_cost_due": "USD",
    "fm_land": "USD",
    "fm_bldg": "USD",
    "delq_prior_years": "years",
    "pli_unique_casefiles": "cases",
    "pli_open_or_in_court": "cases",
    "pli_event_rows": "rows",
}

CONFLICT_GROUPS: dict[str, str] = {
    "assess_lotarea_sf": "lot_area",
    "county_gis_area_sf": "lot_area",
    "usedesc": "current_condition",
    "condemned_case_active": "current_condition",
}

# Geometry heuristics computed from the County GIS polygon during data prep.
APPROXIMATE_NOTES: dict[str, str] = {
    "mbr_short_side_ft": (
        "Short side of the minimum bounding rectangle of the County GIS polygon "
        "(EPSG:2272); approximates lot width, not a surveyed dimension."
    ),
    "mbr_long_side_ft": (
        "Long side of the minimum bounding rectangle of the County GIS polygon "
        "(EPSG:2272); approximates lot depth, not a surveyed dimension."
    ),
    "streets_within_30ft": (
        "Street centerlines within 30 ft of the County GIS polygon; proximity only, "
        "not legal frontage or access."
    ),
    "possible_corner": (
        "Geometry heuristic from nearby street centerlines; corner-lot status is "
        "not established."
    ),
}


def _as_of(manifest: Mapping[str, SourceEntry], source: str) -> str:
    entry = manifest.get(source)
    if entry is None:
        raise KeyError(f"source {source!r} is not in source_manifest.csv")
    return entry.snapshot_as_of


# Source fields that must hold an ISO date. Anything else found there is free text from a public
# source: it is kept for provenance but classed as untrusted, so no memo quotes it and no model can
# select it as a claim (see lotline/memo/deterministic.py).
DATE_FIELDS = frozenset({"pli_latest_event", "condemned_case_created"})
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _evidence_class(name: str, value: object, approximate: bool) -> str:
    if name in DATE_FIELDS and value is not None and not (isinstance(value, str) and _ISO_DATE.match(value)):
        return "untrusted_text"
    return "approximate" if approximate else "raw"


def _record_facts(
    pin: str,
    record: ParcelFacts | TreasuryRecord | AdvertRecord,
    manifest: Mapping[str, SourceEntry],
    overrides: Mapping[str, str],
) -> list[Fact]:
    out: list[Fact] = []
    for f in fields(record):
        if f.name in ("pin", "load_warnings"):  # load notes surface as engine warnings
            continue
        source = overrides.get(f.name) or FIELD_SOURCE[f.name]
        note = APPROXIMATE_NOTES.get(f.name)
        out.append(
            Fact(
                id=fact_id(pin, f.name, source),
                pin=pin,
                field=f.name,
                value=(value := getattr(record, f.name)),
                unit=UNITS.get(f.name),
                source=source,
                as_of=_as_of(manifest, source),
                evidence_class=_evidence_class(f.name, value, bool(note)),
                conflict_group=CONFLICT_GROUPS.get(f.name),
                note=note,
            )
        )
    return out


def facts_for(ctx: ParcelContext) -> list[Fact]:
    """Raw and approximate facts for one parcel: Treasury, advertisement, parcel facts."""
    out = _record_facts(ctx.pin, ctx.treasury, ctx.manifest, TREASURY_SOURCE_OVERRIDES)
    if ctx.advert is not None:
        out += _record_facts(ctx.pin, ctx.advert, ctx.manifest, ADVERT_SOURCE_OVERRIDES)
    if ctx.facts is not None:
        out += _record_facts(ctx.pin, ctx.facts, ctx.manifest, {})
    return out


def rule_facts(rule: DistrictRule, manifest: Mapping[str, SourceEntry] | None = None) -> list[Fact]:
    """``RULE:district:field`` facts for one district; None values are skipped.

    Pass ``ctx.manifest`` so ``as_of`` carries the zoning-code snapshot date;
    without it ``as_of`` is "unrecorded".
    """
    as_of = _as_of(manifest, RULE_SOURCE) if manifest is not None else "unrecorded"
    return [
        Fact(
            id=rule_fact_id(rule.district, f.name),
            pin=None,
            field=f.name,
            value=getattr(rule, f.name),
            unit=UNITS.get(f.name),
            source=RULE_SOURCE,
            as_of=as_of,
            evidence_class="rule",
            district=rule.district,
        )
        for f in fields(rule)
        if f.name != "district" and getattr(rule, f.name) is not None
    ]
