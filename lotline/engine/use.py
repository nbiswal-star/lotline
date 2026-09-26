"""Use entitlement: best of the single-unit and two-unit paths (0-2)."""

from __future__ import annotations

from lotline.models import ComponentScore, DistrictRule, rule_fact_id

from . import policy


def permission_score(code: str | None) -> int | None:
    """Score for a permission code; None when the code is not in the vocabulary."""
    if code is None:
        return None
    return policy.PERMISSION_SCORES.get(code.strip().upper())


def two_unit_density_ok(rule: DistrictRule, areas_sf: tuple[float | None, ...]) -> bool | None:
    """Optional per-unit density limit (``min_lot_per_unit_sf``, not in v1 rules).

    True/False when the smaller recorded area does/does not support two units;
    True when the rule has no per-unit density attribute; None when areas are
    unknown so the limit cannot be evaluated.
    """
    per_unit = getattr(rule, "min_lot_per_unit_sf", None)
    if per_unit is None:
        return True
    known = [a for a in areas_sf if a is not None]
    if not known:
        return None
    return min(known) >= 2 * float(per_unit)


def score_use(rule: DistrictRule | None, areas_sf: tuple[float | None, ...] = ()) -> ComponentScore:
    if rule is None:
        return ComponentScore(
            name="use", low=None, high=None, status="withheld",
            reason="district rules not encoded; use path not evaluated",
        )
    single = permission_score(rule.single_unit_permission)
    two = permission_score(rule.two_unit_permission)
    ids = (
        rule_fact_id(rule.district, "single_unit_permission"),
        rule_fact_id(rule.district, "two_unit_permission"),
    )
    if single is None or two is None:
        bad = rule.single_unit_permission if single is None else rule.two_unit_permission
        return ComponentScore(
            name="use", low=None, high=None, status="withheld",
            reason=f"permission code {bad!r} is not in the screening vocabulary", fact_ids=ids,
        )
    density = two_unit_density_ok(rule, areas_sf)
    if density is not None and getattr(rule, "min_lot_per_unit_sf", None) is not None:
        ids = ids + (rule_fact_id(rule.district, "min_lot_per_unit_sf"),)
    if density is False:
        two_low = two_high = 0
    elif density is None:
        two_low, two_high = 0, two  # density unknown: two-unit path may or may not be available
    else:
        two_low = two_high = two
    low, high = max(single, two_low), max(single, two_high)

    def path(code: str) -> str:
        return policy.PERMISSION_LABELS.get(code.strip().upper(), code)

    reason = (
        f"{rule.district} (Section {rule.use_citation}): single-unit {path(rule.single_unit_permission)}; "
        f"two-unit {path(rule.two_unit_permission)}"
    )
    if density is False:
        reason += "; smaller recorded lot area does not support two units under the per-unit density rule"
    elif density is None:
        reason += "; per-unit density for two units not evaluated (lot area unknown)"
    return ComponentScore(
        name="use", low=low, high=high, status="known" if low == high else "range",
        reason=reason, fact_ids=ids,
    )


def housing_prohibited(use: ComponentScore) -> bool:
    """Neither housing path permitted (known 0, not a range and not unknown)."""
    return use.status == "known" and use.high == 0
