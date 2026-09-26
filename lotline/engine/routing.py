"""Deterministic routing precedence (implementation plan section 4, build contract section 1).

1. Not in the City advertisement            -> Out of sale universe
2. Structure indicated (assessment usedesc) -> Structure routing
3. Critical conflict                         -> Defer: missing or conflicting records
4. Neither housing use permitted             -> Do not advance for housing
5. Required district dimensions unencoded    -> Defer: missing or conflicting records
6. Site standard needs survey                -> Defer: site conditions unknown
7. Otherwise                                 -> Advance (only if lot area conforms in all sources)

Step 7 honours the contract's Advance condition ("lot area conforms in all
sources"): a material area conflict, a missing area source, or area below the
minimum in all sources routes to Defer: missing or conflicting records.
"""

from __future__ import annotations

from dataclasses import dataclass

from lotline.models import ComponentScore, Outcome


@dataclass(frozen=True)
class RoutingInputs:
    advertised: bool
    is_structure: bool
    critical_conflict: bool
    has_parcel_facts: bool
    use: ComponentScore
    rule_encoded: bool  # a district rule row exists
    dimensions_applicable: bool
    dimensions_encoded: bool
    site_standard_blocks: bool
    dimensional: ComponentScore
    area_conforms: bool | None  # lot area conforms to the district minimum in all sources


@dataclass(frozen=True)
class Route:
    outcome: Outcome
    step: int
    reason: str


def route(i: RoutingInputs) -> Route:
    if not i.advertised:
        return Route(Outcome.OUT_OF_UNIVERSE, 1, "not in the City advertisement")
    if i.is_structure:
        return Route(Outcome.STRUCTURE, 2, "assessment use description indicates a structure")
    if i.critical_conflict:
        return Route(Outcome.DEFER_RECORDS, 3, "critical conflict")
    if i.use.status == "known" and i.use.high == 0:
        return Route(Outcome.DO_NOT_ADVANCE, 4, "neither single-unit nor two-unit housing is permitted")
    if not i.has_parcel_facts:
        return Route(Outcome.DEFER_RECORDS, 5, "prepared parcel records missing")
    if not i.rule_encoded:
        return Route(Outcome.DEFER_RECORDS, 5, "district rules not encoded")
    if i.dimensions_applicable and not i.dimensions_encoded:
        return Route(Outcome.DEFER_RECORDS, 5, "district dimensions not encoded")
    if i.site_standard_blocks:
        return Route(Outcome.DEFER_SITE, 6, "site standard requires survey")
    if i.use.status not in ("known", "range"):
        return Route(Outcome.DEFER_RECORDS, 5, "use path not established")
    dim = i.dimensional
    if dim.status == "withheld":
        return Route(Outcome.DEFER_RECORDS, 5, f"dimensional fit withheld: {dim.reason}")
    if i.area_conforms is not True:
        return Route(Outcome.DEFER_RECORDS, 5, "lot area does not conform to the district minimum in all sources")
    return Route(Outcome.ADVANCE, 7, "housing use permitted; no critical conflict; lot area conforms in all sources")
