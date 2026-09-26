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


def _cap(band: str, cap: str) -> str:
    """The lower-discretion of ``band`` and ``cap`` (policy.BANDS is ordered best first)."""
    order = [name for _, _, name in policy.BANDS]
    return band if order.index(band) >= order.index(cap) else cap


def partial_display(known_low: int, known_high: int, known_max: int,
                    withheld: list[ComponentScore]) -> str:
    """e.g. "Partial: 2 of 4 known points; dimensional withheld (reason)".

    "2 of 4 known points" = the scored total out of the points available from the
    components that could be scored; each withheld component is named with its reason.
    """
    parts = [f"Partial: {_span(known_low, known_high)} of {known_max} known points"]
    for c in withheld:
        if c.status == "not_applicable":
            parts.append(f"{c.name} not applicable")
        else:
            parts.append(f"{c.name} withheld ({c.short_reason or 'reason not recorded'})")
    return "; ".join(parts)


def ease_result(
    outcome: Outcome,
    components: list[ComponentScore | None],
    *,
    critical: bool,
    caps: list[tuple[str, str]] | None = None,
) -> EaseResult:
    """``caps``: (highest band allowed, reason) pairs from policy.BAND_CAPS that apply."""
    if outcome in (Outcome.OUT_OF_UNIVERSE, Outcome.STRUCTURE):
        return EaseResult(NOT_APPLICABLE, None, None, None)
    if critical:
        return EaseResult(NOT_SCORABLE, None, None, None)
    if outcome is Outcome.DO_NOT_ADVANCE:
        return EaseResult(DO_NOT_ADVANCE_DISPLAY, None, None, None)
    present = [c for c in components if c is not None]
    applicable = [c for c in present if c.status != "not_applicable"]
    known = [c for c in applicable if c.status in ("known", "range")]
    low = sum(c.low for c in known)
    high = sum(c.high for c in known)
    if len(known) < len(applicable) or len(applicable) < 3:
        # Partial: no total and no band.
        withheld = [c for c in present if c.status not in ("known", "range")]
        return EaseResult(partial_display(low, high, 2 * len(known), withheld), None, None, None)
    band_low, band_high = band_for(low), band_for(high)
    applied: list[str] = []
    for cap, reason in caps or ():
        capped_low, capped_high = _cap(band_low, cap), _cap(band_high, cap)
        if (capped_low, capped_high) != (band_low, band_high):
            applied.append(reason)
        band_low, band_high = capped_low, capped_high
    if band_low == band_high:
        band = band_low
        text = band
    else:
        band = f"{band_low} to {band_high}"
        text = f"band spans {band}"
    if applied:
        text += f" ({'; '.join(applied)})"
    return EaseResult(f"{_span(low, high)} of {policy.MAX_TOTAL}: {text}", low, high, band)


def components_summary(use: ComponentScore | None, dim: ComponentScore | None, env: ComponentScore | None) -> str:
    """e.g. "use 2, dimensional 1-2, environment 2"."""
    return ", ".join(
        f"{name} {component_display(c)}"
        for name, c in (("use", use), ("dimensional", dim), ("environment", env))
    )
