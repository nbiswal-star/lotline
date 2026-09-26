"""Engine outputs the memo may cite, as flat ``Fact`` records.

The engine already emits derived facts for scores, outcome and coverage.
Barriers, next checks, conflict summaries, warnings and component reasons
live on ``ScreeningResult`` as plain fields; this module exposes them as
``PIN:<name>:engine`` facts (evidence class "derived") so memo claims can
cite them like any other fact. Nothing here computes a decision: every value
is copied verbatim from the engine result.
"""

from __future__ import annotations

from lotline.models import Fact, ScreeningResult, derived_fact_id

ENGINE_SOURCE = "engine"


def _fact(result: ScreeningResult, name: str, value: object, note: str,
          evidence_class: str = "derived", conflict_group: str | None = None) -> Fact:
    return Fact(
        id=derived_fact_id(result.pin, name),
        pin=result.pin,
        field=name,
        value=value,
        unit=None,
        source=ENGINE_SOURCE,
        as_of="engine output",
        evidence_class=evidence_class,
        conflict_group=conflict_group,
        note=note,
    )


def barrier_id(pin: str, i: int) -> str:
    return derived_fact_id(pin, f"barrier_{i + 1}")


def next_check_id(pin: str, i: int) -> str:
    return derived_fact_id(pin, f"next_check_{i + 1}")


def warning_id(pin: str, i: int) -> str:
    return derived_fact_id(pin, f"warning_{i + 1}")


def conflict_id(pin: str, kind: str) -> str:
    return derived_fact_id(pin, f"conflict_{kind}")


def reason_id(pin: str, component: str) -> str:
    return derived_fact_id(pin, f"{component}_reason")


SETBACK_SCREEN = "setback_screen"


def engine_output_facts(result: ScreeningResult) -> list[Fact]:
    out: list[Fact] = []
    for i, b in enumerate(result.barriers):
        out.append(_fact(result, f"barrier_{i + 1}", b, "engine barrier (verbatim)"))
    for i, nc in enumerate(result.next_checks):
        out.append(_fact(result, f"next_check_{i + 1}", f"{nc.check} | owner: {nc.owner}",
                         f"engine next check (trigger: {nc.trigger})"))
    for i, w in enumerate(result.warnings):
        out.append(_fact(result, f"warning_{i + 1}", w, "engine warning (verbatim)"))
    for c in result.conflicts:
        # Deliberately not tagged with the conflict group: citing the engine's
        # conflict record is how a claim refers to the conflict, not a value in it.
        out.append(_fact(result, f"conflict_{c.kind}", f"{c.level.value}: {c.summary}",
                         "engine conflict record (verbatim)"))
    for comp in (result.use, result.dimensional, result.environment):
        if comp is not None and comp.reason:
            out.append(_fact(result, f"{comp.name}_reason", comp.reason, "engine component reason (verbatim)"))
    if result.setback_screen and result.setback_screen != "not computed":
        out.append(_fact(result, SETBACK_SCREEN, result.setback_screen,
                         "illustrative base-setback screen (engine, verbatim)", evidence_class="approximate"))
    return out


def fact_universe(result: ScreeningResult, extra: list[Fact] | tuple[Fact, ...] = ()) -> dict[str, Fact]:
    """Every fact a claim about ``result`` could cite: engine facts, engine outputs, then extras.

    ``extra`` (e.g. a catalog of all district rule facts, or other parcels'
    facts) is included so the checker can say *why* a citation is invalid
    (other parcel, other district) instead of only "not found".
    """
    out: dict[str, Fact] = {}
    for f in list(result.facts) + engine_output_facts(result) + list(extra):
        out.setdefault(f.id, f)
    return out
