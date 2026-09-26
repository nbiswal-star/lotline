"""Engine-derived values as Fact records, plus provenance completion.

Derived facts use ``derived_fact_id`` (``PIN:name:engine``) and evidence class
"derived" or "approximate" with a derivation note.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from lotline.models import (
    FIELD_SOURCE,
    Fact,
    ParcelContext,
    SourceEntry,
    derived_fact_id,
)

from . import policy

ENGINE_SOURCE = "engine"
RULE_SOURCE = "zoning_code"


def _latest_as_of(manifest: Mapping[str, SourceEntry], sources: Iterable[str]) -> str:
    dates = [manifest[s].snapshot_as_of for s in sources if s in manifest]
    return max(dates) if dates else "unrecorded"


def derived_fact(
    ctx: ParcelContext,
    name: str,
    value: object,
    *,
    unit: str | None,
    note: str,
    inputs: Iterable[str],
    evidence_class: str = "derived",
) -> Fact:
    return Fact(
        id=derived_fact_id(ctx.pin, name),
        pin=ctx.pin,
        field=name,
        value=value,
        unit=unit,
        source=ENGINE_SOURCE,
        as_of=_latest_as_of(ctx.manifest, inputs),
        evidence_class=evidence_class,
        note=note,
    )


def upset_to_assessed_land(ctx: ParcelContext) -> float | None:
    """Upset price / assessed land value, 1 decimal. Acquisition-burden indicator only."""
    upset = ctx.facts.upset_price if ctx.facts and ctx.facts.upset_price is not None else (
        ctx.advert.upset if ctx.advert else None
    )
    land = ctx.facts.assessed_land_value if ctx.facts else None
    if upset is None or not land:
        return None
    return round(upset / land, 1)


# --------------------------------------------------------------------------
# Provenance completion: every id the engine cites must exist in result.facts
# --------------------------------------------------------------------------


def backfill_fact(ctx: ParcelContext, fid: str) -> Fact | None:
    """Build a raw/rule fact for a cited id that no upstream builder emitted."""
    parts = fid.split(":")
    if len(parts) != 3:
        return None
    if parts[0] == "RULE":
        _, district, name = parts
        rule = ctx.rule
        if rule is None or rule.district != district or not hasattr(rule, name):
            return None
        value = getattr(rule, name)
        entry = ctx.manifest.get(RULE_SOURCE)
        return Fact(
            id=fid, pin=None, field=name, value=value, unit=None, source=RULE_SOURCE,
            as_of=entry.snapshot_as_of if entry else "unrecorded", evidence_class="rule",
            district=district,
            note="blank in district_rules.csv: unknown/not applicable, never zero" if value is None else None,
        )
    pin, name, source = parts
    if pin != ctx.pin or source == ENGINE_SOURCE:
        return None
    for record in (ctx.facts, ctx.treasury, ctx.advert):
        if record is not None and hasattr(record, name):
            entry = ctx.manifest.get(source)
            return Fact(
                id=fid, pin=pin, field=name, value=getattr(record, name), unit=None,
                source=source, as_of=entry.snapshot_as_of if entry else "unrecorded",
                evidence_class="raw",
            )
    return None


AREA_GAP_NOTE = (
    "(county_gis_area_sf - assess_lotarea_sf) / assess_lotarea_sf x 100; neither source is "
    "treated as correct"
)
AREA_SYM_NOTE = "|a - b| / max(a, b) x 100 over assessment and County GIS areas"
RATIO_NOTE = (
    "upset price / assessed land value; acquisition-burden indicator only, not market value "
    "or feasibility"
)
ENVELOPE_NOTE = (
    "Illustrative base-setback envelope from approximate bounding-rectangle sides. "
    + policy.DIMENSIONAL_ASSUMPTION
)
AREA_INPUTS = (FIELD_SOURCE["assess_lotarea_sf"], FIELD_SOURCE["county_gis_area_sf"])
