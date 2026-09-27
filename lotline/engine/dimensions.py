"""Dimensional fit: illustrative base-setback envelope, data-driven from DistrictRule.

Interior width = short side - 2 x interior side; corner width = short side -
exterior side - interior side; depth = long side - front - rear; all clamped
at 0. Each scenario scores min(width band, depth band) (policy.py). Blank
setbacks are unknown and withhold the component (never 0). A lot area that is
missing or not positive is unknown and is never scored.
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


def band_score(ft: float, full: float = policy.WIDTH_FULL_FT, partial: float = policy.WIDTH_PARTIAL_FT) -> int:
    """2 at or above ``full``, 1 at or above ``partial``, else 0."""
    if ft >= full:
        return 2
    if ft >= partial:
        return 1
    return 0


def width_band(width_ft: float) -> int:
    return band_score(width_ft, policy.WIDTH_FULL_FT, policy.WIDTH_PARTIAL_FT)


def depth_band(depth_ft: float) -> int:
    return band_score(depth_ft, policy.DEPTH_FULL_FT, policy.DEPTH_PARTIAL_FT)


def envelope_score(width_ft: float, depth_ft: float) -> int:
    """LotLine screening assumption: min(width band, depth band) (see policy.py)."""
    return min(width_band(width_ft), depth_band(depth_ft))


def valid_area(sf: float | None) -> float | None:
    """A recorded lot area, or None when missing or not positive (never scored)."""
    return sf if sf is not None and sf > 0 else None


SETBACK_NAMES = {
    "front_setback_ft": "front",
    "rear_setback_ft": "rear",
    "interior_side_ft": "interior side",
    "exterior_side_ft": "exterior side",
}


AREA_SOURCE_NAMES = ("assessment", "County GIS")


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
    out = [DimensionalScenario("interior", interior_w, depth, envelope_score(interior_w, depth))]
    if possible_corner:
        corner_w = max(0.0, short_ft - rule.exterior_side_ft - rule.interior_side_ft)
        out.append(DimensionalScenario("corner", corner_w, depth, envelope_score(corner_w, depth)))
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


def _envelope_short(scenarios: list[DimensionalScenario]) -> str:
    """Concise envelope reason (<= 90 chars), e.g. "envelope about 23 x 70 ft; if corner about 13 ft wide"."""
    interior = scenarios[0]
    text = f"illustrative envelope about {_ft(interior.width_ft)} x {_ft(interior.depth_ft)} ft"
    if len(scenarios) > 1:
        text += f"; if corner about {_ft(scenarios[1].width_ft)} ft wide"
    return text


def _withheld(reason: str, ids: tuple[str, ...] = (), short: str | None = None) -> DimensionalResult:
    return DimensionalResult(
        ComponentScore("dimensional", None, None, "withheld", reason, ids, short_reason=short),
        [], "not computed",
    )


def score_dimensional(
    pin: str,
    facts: ParcelFacts | None,
    rule: DistrictRule | None,
    conflicts: list[Conflict],
) -> DimensionalResult:
    if rule is None:
        return _withheld("district rules not encoded; dimensional fit not evaluated",
                         short="district rules not encoded")
    d = rule.district
    if not rule.dimensions_applicable:
        return DimensionalResult(
            ComponentScore(
                "dimensional", None, None, "not_applicable",
                f"housing dimensions not applicable in {d} because neither housing use is permitted",
                (rule_fact_id(d, "dimensions_applicable"),),
                short_reason="not applicable: no housing use permitted",
            ),
            [],
            "not computed",
        )
    if not rule.dimensions_encoded:
        cite = f" (§{rule.dimensional_citation})" if rule.dimensional_citation else ""
        return _withheld(
            f"{d}-district dimensions{cite} are not encoded in v1 (LotLine tool limitation)",
            (rule_fact_id(d, "dimensions_encoded"),),
            short=f"{d} dimensions not modelled by LotLine",
        )
    if rule.site_standard_blocks_dimensional:
        also = (
            "; sources also disagree on lot area across the district minimum (material conflict)"
            if material_affects(conflicts, "dimensional")
            else ""
        )
        short = policy.SITE_STANDARD_SHORT.get(d, policy.SITE_STANDARD_GENERIC_SHORT)
        return _withheld(
            f"site standard requires survey ({short}){also}",
            (rule_fact_id(d, "site_standard_blocks_dimensional"), rule_fact_id(d, "site_standard")),
            short=short,
        )
    if facts is None:
        return _withheld("prepared parcel records missing", short="parcel records missing")
    if valid_area(facts.mbr_short_side_ft) is None or valid_area(facts.mbr_long_side_ft) is None:
        return _withheld("parcel geometry (bounding-rectangle sides) not available",
                         short="parcel geometry missing")
    missing = _missing_setbacks(rule, facts.possible_corner)
    if missing:
        names = ", ".join(SETBACK_NAMES[m] for m in missing)
        corner = " (needed because the lot may be a corner)" if "exterior_side_ft" in missing else ""
        return _withheld(
            f"{d} setback(s) not encoded: {', '.join(missing)} (blank is unknown, not zero){corner}",
            tuple(rule_fact_id(d, m) for m in missing),
            short=f"{d} {names} setback not encoded",
        )
    if rule.min_lot_sf is None:
        return _withheld(f"{d} minimum lot area not encoded", (rule_fact_id(d, "min_lot_sf"),),
                         short=f"{d} minimum lot area not encoded")

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
                short_reason=f"lot-area records cross the {rule.min_lot_sf:,.0f} sf minimum",
            ),
            scenarios,
            format_setback_screen(scenarios, withheld_for_area=True),
        )
    areas = (valid_area(facts.assess_lotarea_sf), valid_area(facts.county_gis_area_sf))
    if any(a is None for a in areas):
        which = " and ".join(
            name for name, a in zip(AREA_SOURCE_NAMES, areas, strict=True) if a is None
        )
        return DimensionalResult(
            ComponentScore(
                "dimensional", None, None, "withheld",
                f"lot area missing from the {which} record{'s' if ' and ' in which else ''}; conformity in all sources not established",
                ids,
                short_reason=f"lot area missing from the {which} record{'s' if ' and ' in which else ''}",
            ),
            scenarios,
            format_setback_screen(scenarios, withheld_for_area=True).replace(
                "area conflicts", "a lot-area source is missing"
            ),
        )
    screen = format_setback_screen(scenarios, withheld_for_area=False)
    if min(areas) < rule.min_lot_sf:  # type: ignore[type-var]
        return DimensionalResult(
            ComponentScore(
                "dimensional", 0, 0, "known",
                f"lot area is below the {rule.min_lot_sf:,.0f} sf {d} minimum in all sources",
                ids,
                short_reason=f"below the {rule.min_lot_sf:,.0f} sf minimum in all sources",
            ),
            scenarios,
            screen,
            area_conforms=False,
        )
    low = min(s.score for s in scenarios)
    high = max(s.score for s in scenarios)
    detail = "; ".join(
        f"{s.label} envelope about {_ft(s.width_ft)} ft wide x {_ft(s.depth_ft)} ft deep scores {s.score}"
        for s in scenarios
    )
    reason = f"{detail}. {policy.DIMENSIONAL_ASSUMPTION}"
    if len(scenarios) > 1:
        reason = f"corner status unverified, range shown: {reason}"
    return DimensionalResult(
        ComponentScore("dimensional", low, high, "known" if low == high else "range", reason, ids,
                       short_reason=_envelope_short(scenarios)),
        scenarios,
        screen,
        area_conforms=True,
    )
