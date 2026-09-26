"""Development Ease result: total, range, partial, or not scorable.

Unknown components are withheld, never scored 0; ranges never collapse.
"""

from __future__ import annotations

from lotline.models import ComponentScore, EaseResult, Outcome

from . import policy

NOT_SCORABLE = "Not scorable"
DO_NOT_ADVANCE_DISPLAY = "Do not advance for housing"
NOT_APPLICABLE = "n/a"


def component_display(c: ComponentScore | None) -> str:
    """"2", "1-2", "withheld", "n/a"."""
    if c is None or c.status == "not_applicable":
        return NOT_APPLICABLE
    if c.status == "withheld" or c.low is None or c.high is None:
        return "withheld"
    return f"{c.low}" if c.low == c.high else f"{c.low}-{c.high}"


def band_for(total: int) -> str:
    for lo, hi, name in policy.BANDS:
        if lo <= total <= hi:
            return name
    raise ValueError(f"total {total} outside 0-{policy.MAX_TOTAL}")


def _span(low: int, high: int) -> str:
    return f"{low}" if low == high else f"{low}-{high}"


def ease_result(
    outcome: Outcome,
    components: list[ComponentScore | None],
    *,
    critical: bool,
) -> EaseResult:
    if outcome in (Outcome.OUT_OF_UNIVERSE, Outcome.STRUCTURE):
        return EaseResult(NOT_APPLICABLE, None, None, None)
    if critical:
        return EaseResult(NOT_SCORABLE, None, None, None)
    if outcome is Outcome.DO_NOT_ADVANCE:
        return EaseResult(DO_NOT_ADVANCE_DISPLAY, None, None, None)
    applicable = [c for c in components if c is not None and c.status != "not_applicable"]
    known = [c for c in applicable if c.status in ("known", "range")]
    low = sum(c.low for c in known)
    high = sum(c.high for c in known)
    if len(known) < len(applicable) or len(applicable) < 3:
        # Partial: no total and no band.
        return EaseResult(f"Partial: {_span(low, high)} of {2 * len(known)} known", None, None, None)
    band_low, band_high = band_for(low), band_for(high)
    if band_low == band_high:
        band = band_low
        text = band
    else:
        band = f"{band_low} to {band_high}"
        text = f"band spans {band}"
    return EaseResult(f"{_span(low, high)} of {policy.MAX_TOTAL}: {text}", low, high, band)


def components_summary(use: ComponentScore | None, dim: ComponentScore | None, env: ComponentScore | None) -> str:
    """e.g. "use 2, dimensional 1-2, environment 2"."""
    return ", ".join(
        f"{name} {component_display(c)}"
        for name, c in (("use", use), ("dimensional", dim), ("environment", env))
    )
