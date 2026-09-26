"""Use entitlement: best of the single-unit and two-unit paths (0-2).

No per-unit density test: Ord. 10-2025 repealed the §903.03 per-unit density
minimums, so the two-unit path depends only on the district permission.
"""

from __future__ import annotations

from lotline.models import ComponentScore, DistrictRule, rule_fact_id

from . import policy


def permission_score(code: str | None) -> int | None:
    """Score for a permission code; None when the code is not in the vocabulary."""
    if code is None:
        return None
    return policy.PERMISSION_SCORES.get(code.strip().upper())


def score_use(rule: DistrictRule | None) -> ComponentScore:
    if rule is None:
        return ComponentScore(
            name="use", low=None, high=None, status="withheld",
            reason="district rules not encoded; use path not evaluated",
            short_reason="district rules not encoded",
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
            short_reason="permission code not recognized",
        )
    score = max(single, two)

    def path(code: str) -> str:
        return policy.PERMISSION_LABELS.get(code.strip().upper(), code)

    reason = (
        f"{rule.district} (§{rule.use_citation}): single-unit {path(rule.single_unit_permission)}; "
        f"two-unit {path(rule.two_unit_permission)}"
    )
    return ComponentScore(name="use", low=score, high=score, status="known", reason=reason, fact_ids=ids,
                          short_reason=_use_short(rule, single, two, path))


def _use_short(rule: DistrictRule, single: int, two: int, path) -> str:
    """Concise use reason (<= 90 chars): the best housing path, or none."""
    if max(single, two) == 0:
        return "no housing use permitted"
    if single == two:
        return f"single- and two-unit {path(rule.single_unit_permission)}"
    best, code = ("single-unit", rule.single_unit_permission) if single > two else (
        "two-unit", rule.two_unit_permission)
    return f"{best} {path(code)}"


def housing_prohibited(use: ComponentScore) -> bool:
    """Neither housing path permitted (known 0, not a range and not unknown)."""
    return use.status == "known" and use.high == 0
