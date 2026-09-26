"""Decision-impact conflict detection (build contract section 2).

Summaries are engine-authored and never select a winning source. Each
Conflict lists the fact_ids of every fact in its group; ``conflict_group_id``
names the group so facts can be tagged with it.
"""

from __future__ import annotations

from dataclasses import dataclass

from lotline.models import (
    Conflict,
    ConflictLevel,
    ParcelContext,
    derived_fact_id,
    fact_id,
    rule_fact_id,
)

from . import policy

_LEVEL_ORDER = {ConflictLevel.CRITICAL: 0, ConflictLevel.MATERIAL: 1, ConflictLevel.DISCLOSE: 2}


def conflict_group_id(kind: str) -> str:
    """Conflict-group name carried on Fact.conflict_group (matches lotline.facts tagging)."""
    return kind


# --------------------------------------------------------------------------
# Lot area
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AreaGap:
    assess_sf: float
    gis_sf: float
    pct: float  # (gis - assess) / assess * 100
    symmetric_pct: float  # |a - b| / max(a, b) * 100


def area_gap(assess_sf: float | None, gis_sf: float | None) -> AreaGap | None:
    """Directional and symmetric gaps; None when either value is missing or non-positive."""
    if assess_sf is None or gis_sf is None or assess_sf <= 0 or gis_sf <= 0:
        return None
    pct = (gis_sf - assess_sf) / assess_sf * 100.0
    sym = abs(assess_sf - gis_sf) / max(assess_sf, gis_sf) * 100.0
    return AreaGap(assess_sf, gis_sf, pct, sym)


def threshold_between(a: float, b: float, minimum: float | None) -> bool:
    """True when the sources fall on opposite sides of the minimum (conformity differs)."""
    if minimum is None:
        return False
    lo, hi = sorted((a, b))
    return lo < minimum <= hi


def _area_fact_ids(ctx: ParcelContext) -> tuple[str, ...]:
    ids = [
        fact_id(ctx.pin, "assess_lotarea_sf"),
        fact_id(ctx.pin, "county_gis_area_sf"),
        fact_id(ctx.pin, "lotarea"),  # Treasury copy of the assessment lot area
        derived_fact_id(ctx.pin, "area_gap_pct"),
        derived_fact_id(ctx.pin, "area_gap_symmetric_pct"),
    ]
    if ctx.rule is not None and ctx.rule.min_lot_sf is not None:
        ids.append(rule_fact_id(ctx.rule.district, "min_lot_sf"))
    return tuple(ids)


def lot_area_conflict(ctx: ParcelContext) -> Conflict | None:
    """Material when the controlling minimum lies between the sources; disclose when gap > 10%."""
    if ctx.facts is None:
        return None
    gap = area_gap(ctx.facts.assess_lotarea_sf, ctx.facts.county_gis_area_sf)
    if gap is None:
        return None
    rule = ctx.rule
    minimum = rule.min_lot_sf if rule is not None else None
    district = rule.district if rule is not None else ctx.facts.zoning_polygon
    head = (
        f"Assessment lot area is {gap.assess_sf:,.0f} sf and County GIS polygon area is "
        f"{gap.gis_sf:,.0f} sf (gap {gap.pct:+.0f}% relative to the assessment value; "
        f"symmetric {gap.symmetric_pct:.0f}%)."
    )
    if threshold_between(gap.assess_sf, gap.gis_sf, minimum):
        return Conflict(
            level=ConflictLevel.MATERIAL,
            kind="lot_area",
            fact_ids=_area_fact_ids(ctx),
            summary=(
                f"{head} The {minimum:,.0f} sf {district} minimum lies between the two values. "
                "Sources disagree on lot area; conformity requires deed/survey review."
            ),
            affects=("dimensional",),
        )
    if abs(gap.pct) <= policy.DISCLOSE_GAP_PCT:
        return None
    if minimum is None:
        if rule is not None and rule.dimensions_applicable and not rule.dimensions_encoded:
            tail = (
                f"{district}-district dimensions are not evaluated (not encoded in v1), so no "
                "threshold crossing is evaluated."
            )
        else:
            tail = f"No minimum lot area is encoded for {district}; no threshold crossing is evaluated."
    else:
        lo = min(gap.assess_sf, gap.gis_sf)
        if lo > minimum:
            tail = f"Both sources exceed the {minimum:,.0f} sf minimum."
        elif lo == minimum:
            tail = f"Both sources meet or exceed the {minimum:,.0f} sf minimum."
        else:
            tail = f"Both sources are below the {minimum:,.0f} sf minimum."
    return Conflict(
        level=ConflictLevel.DISCLOSE,
        kind="lot_area",
        fact_ids=_area_fact_ids(ctx),
        summary=f"{head} Area records disagree (disclosed); no score change. {tail}",
        affects=(),
    )


# --------------------------------------------------------------------------
# Current condition
# --------------------------------------------------------------------------


def current_condition_conflict(ctx: ParcelContext) -> Conflict | None:
    """Assessment VACANT use description plus an active condemned/dead-end case."""
    if ctx.facts is None or ctx.treasury.is_structure or not ctx.facts.condemned_case_active:
        return None
    ids = [
        fact_id(ctx.pin, "usedesc"),
        fact_id(ctx.pin, "condemned_case_active"),
    ]
    if ctx.facts.condemned_case_created is not None:
        ids.append(fact_id(ctx.pin, "condemned_case_created"))
    if ctx.facts.condemned_case_address is not None:
        ids.append(fact_id(ctx.pin, "condemned_case_address"))
    return Conflict(
        level=ConflictLevel.CRITICAL,
        kind="current_condition",
        fact_ids=tuple(ids),
        summary=policy.CURRENT_CONDITION_WORDING,
        affects=("ease_total",),
    )


# --------------------------------------------------------------------------
# Sale universe
# --------------------------------------------------------------------------


def sale_universe_conflict(ctx: ParcelContext) -> Conflict | None:
    """Advertised record whose upset price disagrees with the Treasury tax due.

    A PIN that is simply absent from the advertisement is a routing state
    (Out of sale universe), not a conflict.
    """
    if ctx.advert is None:
        return None
    if abs(ctx.advert.upset - ctx.treasury.total_tax_due) <= policy.PRICE_TOLERANCE_USD + 1e-9:
        return None
    return Conflict(
        level=ConflictLevel.CRITICAL,
        kind="sale_universe",
        fact_ids=(fact_id(ctx.pin, "upset"), fact_id(ctx.pin, "total_tax_due")),
        summary=(
            f"The City advertisement lists an upset price of ${ctx.advert.upset:,.2f} while the "
            f"Treasury record lists total tax due of ${ctx.treasury.total_tax_due:,.2f}. The "
            "sale-universe records disagree; sale status requires confirmation."
        ),
        affects=("ease_total",),
    )


# --------------------------------------------------------------------------


def detect_conflicts(ctx: ParcelContext) -> list[Conflict]:
    found = [
        current_condition_conflict(ctx),
        sale_universe_conflict(ctx),
        lot_area_conflict(ctx),
    ]
    return sorted((c for c in found if c is not None), key=lambda c: _LEVEL_ORDER[c.level])


def highest_level(conflicts: list[Conflict]) -> str:
    """"critical" | "material" | "disclose" | "none"."""
    if not conflicts:
        return "none"
    return min(conflicts, key=lambda c: _LEVEL_ORDER[c.level]).level.value


def has_critical(conflicts: list[Conflict]) -> bool:
    return any(c.level is ConflictLevel.CRITICAL for c in conflicts)


def material_affects(conflicts: list[Conflict], component: str) -> list[Conflict]:
    return [c for c in conflicts if c.level is ConflictLevel.MATERIAL and component in c.affects]
