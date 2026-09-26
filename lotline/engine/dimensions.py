"""Dimensional fit: illustrative base-setback envelope, data-driven from DistrictRule.

Interior width = short side - 2 x interior side; corner width = short side -
exterior side - interior side; depth = long side - front - rear; all clamped
at 0. Blank setbacks are unknown and withhold the component (never 0).
"""

from __future__ import annotations

from dataclasses import dataclass

from lotline.models import (
    ComponentScore,
    Conflict,
    DimensionalScenario,
    DistrictRule,
    ParcelFacts,
    derived_fact_id,
    fact_id,
    rule_fact_id,
)

from . import policy
from .conflicts import material_affects


@dataclass(frozen=True)
class DimensionalResult:
    component: ComponentScore
    scenarios: list[DimensionalScenario]
    setback_screen: str
    # True: conforms in all sources; False: below the minimum in all sources;
    # None: not established (conflict, missing source or rules not encoded).
    area_conforms: bool | None = None


def width_score(width_ft: float, depth_ft: float) -> int:
    """LotLine screening assumption bands (policy.WIDTH_FULL_FT / WIDTH_PARTIAL_FT)."""
    if depth_ft <= 0:
        return 0
    if width_ft >= policy.WIDTH_FULL_FT:
        return 2
    if width_ft >= policy.WIDTH_PARTIAL_FT:
        return 1
    return 0


def _missing_setbacks(rule: DistrictRule, corner: bool) -> list[str]:
    needed = ["front_setback_ft", "rear_setback_ft", "interior_side_ft"]
    if corner:
        needed.append("exterior_side_ft")
    return [name for name in needed if getattr(rule, name) is None]


def compute_scenarios(
    short_ft: float, long_ft: float, rule: DistrictRule, possible_corner: bool
) -> list[DimensionalScenario]:
    """Interior scenario always; corner scenario too when corner status is unresolved."""
    depth = max(0.0, long_ft - rule.front_setback_ft - rule.rear_setback_ft)
    interior_w = max(0.0, short_ft - 2 * rule.interior_side_ft)
    out = [DimensionalScenario("interior", interior_w, depth, width_score(interior_w, depth))]
    if possible_corner:
        corner_w = max(0.0, short_ft - rule.exterior_side_ft - rule.interior_side_ft)
        out.append(DimensionalScenario("corner", corner_w, depth, width_score(corner_w, depth)))
    return out


def _ft(x: float) -> str:
    return f"{round(x):d}"


def format_setback_screen(scenarios: list[DimensionalScenario], *, withheld_for_area: bool) -> str:
    """e.g. "Illustrative only: interior 39x51 ft; if corner 14x51 ft"."""
    if not scenarios:
        return "not computed"
    about = "about " if withheld_for_area else ""
    parts = []
    for s in scenarios:
        if s.label == "interior":
            parts.append(f"interior {about}{_ft(s.width_ft)}x{_ft(s.depth_ft)} ft")
        elif round(s.width_ft) <= 0:
            parts.append("if corner about 0 ft wide")
        else:
            parts.append(f"if corner {about}{_ft(s.width_ft)}x{_ft(s.depth_ft)} ft")
    text = "Illustrative only: " + "; ".join(parts)
    if withheld_for_area:
        text += "; withheld because area conflicts"
    return text


def _withheld(reason: str, ids: tuple[str, ...] = ()) -> DimensionalResult:
    return DimensionalResult(
        ComponentScore("dimensional", None, None, "withheld", reason, ids), [], "not computed"
    )


def score_dimensional(
    pin: str,
    facts: ParcelFacts | None,
    rule: DistrictRule | None,
    conflicts: list[Conflict],
) -> DimensionalResult:
    if rule is None:
        return _withheld("district rules not encoded; dimensional fit not evaluated")
    d = rule.district
    if not rule.dimensions_applicable:
        return DimensionalResult(
            ComponentScore(
                "dimensional", None, None, "not_applicable",
                f"housing dimensions not applicable in {d} because neither housing use is permitted",
                (rule_fact_id(d, "dimensions_applicable"),),
            ),
            [],
            "not computed",
        )
    if not rule.dimensions_encoded:
        cite = f" (§{rule.dimensional_citation})" if rule.dimensional_citation else ""
        return _withheld(
            f"{d}-district dimensions{cite} are not encoded in v1",
            (rule_fact_id(d, "dimensions_encoded"),),
        )
    if rule.site_standard_blocks_dimensional:
        also = (
            "; sources also disagree on lot area across the district minimum (material conflict)"
            if material_affects(conflicts, "dimensional")
            else ""
        )
        return _withheld(
            f"site standard requires survey: {rule.site_standard or 'site standard'}{also}",
            (rule_fact_id(d, "site_standard_blocks_dimensional"), rule_fact_id(d, "site_standard")),
        )
    if facts is None or facts.mbr_short_side_ft is None or facts.mbr_long_side_ft is None:
        return _withheld("parcel geometry (bounding-rectangle sides) not available")
    missing = _missing_setbacks(rule, facts.possible_corner)
    if missing:
        return _withheld(
            f"{d} setback(s) not encoded: {', '.join(missing)} (blank is unknown, not zero)",
            tuple(rule_fact_id(d, m) for m in missing),
        )
    if rule.min_lot_sf is None:
        return _withheld(f"{d} minimum lot area not encoded")

    scenarios = compute_scenarios(
        facts.mbr_short_side_ft, facts.mbr_long_side_ft, rule, facts.possible_corner
    )
    setbacks = ["front_setback_ft", "rear_setback_ft", "interior_side_ft"]
    if facts.possible_corner:
        setbacks.append("exterior_side_ft")
    ids = (
        fact_id(pin, "mbr_short_side_ft"),
        fact_id(pin, "mbr_long_side_ft"),
        fact_id(pin, "assess_lotarea_sf"),
        fact_id(pin, "county_gis_area_sf"),
        rule_fact_id(d, "min_lot_sf"),
        *(rule_fact_id(d, s) for s in setbacks),
        *(derived_fact_id(pin, f"envelope_{s.label}_width_ft") for s in scenarios),
    )
    if facts.possible_corner:
        ids = ids + (fact_id(pin, "possible_corner"),)

    if material_affects(conflicts, "dimensional"):
        return DimensionalResult(
            ComponentScore(
                "dimensional", None, None, "withheld",
                f"sources disagree on lot area across the {rule.min_lot_sf:,.0f} sf minimum "
                "(material conflict); conformity requires deed/survey review",
                ids,
            ),
            scenarios,
            format_setback_screen(scenarios, withheld_for_area=True),
        )
    areas = (facts.assess_lotarea_sf, facts.county_gis_area_sf)
    if any(a is None for a in areas):
        return DimensionalResult(
            ComponentScore(
                "dimensional", None, None, "withheld",
                "lot area missing from a source; conformity in all sources not established", ids,
            ),
            scenarios,
            format_setback_screen(scenarios, withheld_for_area=True).replace(
                "area conflicts", "a lot-area source is missing"
            ),
        )
    screen = format_setback_screen(scenarios, withheld_for_area=False)
    if min(areas) < rule.min_lot_sf:
        return DimensionalResult(
            ComponentScore(
                "dimensional", 0, 0, "known",
                f"lot area is below the {rule.min_lot_sf:,.0f} sf {d} minimum in all sources",
                ids,
            ),
            scenarios,
            screen,
            area_conforms=False,
        )
    low = min(s.score for s in scenarios)
    high = max(s.score for s in scenarios)
    detail = "; ".join(f"{s.label} width about {_ft(s.width_ft)} ft scores {s.score}" for s in scenarios)
    reason = f"{detail}. {policy.DIMENSIONAL_ASSUMPTION}"
    if len(scenarios) > 1:
        reason = f"corner status unverified, range shown: {reason}"
    return DimensionalResult(
        ComponentScore("dimensional", low, high, "known" if low == high else "range", reason, ids),
        scenarios,
        screen,
        area_conforms=True,
    )
