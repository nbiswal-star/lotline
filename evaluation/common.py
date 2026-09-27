"""Shared helpers for the evaluation experiments.

Everything here is deterministic: tables are sorted with stable keys, numbers
are formatted explicitly, and nothing depends on wall-clock time or dict
iteration order that is not itself fixed by the input files.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
VALIDATION_DIR = REPO_ROOT / "docs" / "validation"

# Named real parcels used as bases for in-memory perturbations. PIN literals are
# allowed here (evaluation code, not app code); each is cross-checked against its
# location text when used, so a wrong PIN fails loudly instead of silently.
PARCELS: dict[str, tuple[str, str]] = {
    "benezet": ("0131N00031000000", "Benezet St"),
    "michigan_15s66": ("0015S00066000000", "Michigan St"),
    "michigan_14n100": ("0014N00100000000", "Michigan St"),
    "dearborn": ("0050K00227000000", "Dearborn St"),
    "centre_10s5": ("0010S00005000000", "Centre Ave"),
    "centre_10r108": ("0010R00108000000", "Centre Ave"),
    "walcott": ("0042D00039000000", "Walcott St"),
    "wylie": ("0010L00127000000", "Wylie Ave"),
    "mossfield": ("0081R00122000000", "Mossfield St"),
    "saline": ("0088R00001000000", "Saline St"),
    "kemper": ("0088G00313000A00", "Kemper St"),
    "mcclure": ("0075S00108000000", "McClure Ave"),
}


@dataclass
class Section:
    """One experiment's output.

    ``markdown`` is the rendered section body (without the H2 title);
    ``data`` is a JSON-serializable record of every number in the section;
    ``verdict_inputs`` holds the handful of values a reader needs to judge the
    related hypothesis; ``assertions`` lists internal checks
    (``{"name", "passed", "detail"}``). ``status`` is "ok", "failed" (an
    assertion did not hold) or "NOT RUN: <reason>".
    """

    id: str
    title: str
    markdown: str
    data: dict[str, Any] = field(default_factory=dict)
    verdict_inputs: dict[str, Any] = field(default_factory=dict)
    assertions: list[dict[str, Any]] = field(default_factory=list)
    status: str = "ok"

    @property
    def all_passed(self) -> bool:
        return self.status == "ok" and all(a.get("passed") for a in self.assertions)


class Checks:
    """Collects named internal assertions without raising (the report shows them all)."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def check(self, name: str, passed: bool, detail: str = "") -> bool:
        self.items.append({"name": name, "passed": bool(passed), "detail": detail})
        return bool(passed)

    @property
    def all_passed(self) -> bool:
        return all(a["passed"] for a in self.items)

    def markdown(self) -> str:
        n = len(self.items)
        ok = sum(a["passed"] for a in self.items)
        rows = [
            ("PASS" if a["passed"] else "**FAIL**", a["name"], a["detail"]) for a in self.items
        ]
        return f"Internal assertions: **{ok}/{n} held.**\n\n" + md_table(
            ["Result", "Assertion", "Detail"], rows, sort=False
        )


# --------------------------------------------------------------------------
# Snapshot and engine access (cached: the snapshot is immutable)
# --------------------------------------------------------------------------


@lru_cache(maxsize=1)
def snapshot():
    from lotline.loaders import load_snapshot

    return load_snapshot()


def context(pin: str):
    from lotline.loaders import context_for

    ctx = context_for(snapshot(), pin)
    if ctx is None:
        raise KeyError(f"PIN {pin} not in the Treasury snapshot")
    return ctx


def named_context(name: str):
    """ParcelContext for a named real parcel, verifying its location text."""
    pin, location = PARCELS[name]
    ctx = context(pin)
    got = ctx.facts.location if ctx.facts is not None else ctx.treasury.address
    if location.lower() not in got.lower():
        raise AssertionError(f"{name}: PIN {pin} has location {got!r}, expected {location!r}")
    return ctx


def screen_all() -> dict[str, Any]:
    """Screen every Treasury record; keys sorted by PIN."""
    from lotline.engine import screen
    from lotline.loaders import context_for

    snap = snapshot()
    return {pin: screen(context_for(snap, pin)) for pin in sorted(snap.treasury)}


def advertised_vacant_pins() -> list[str]:
    snap = snapshot()
    return sorted(
        p for p in snap.reconciliation.matched_pins if not snap.treasury[p].is_structure
    )


def parcel_label(pin: str) -> str:
    """Short human label: location · neighborhood (short PIN)."""
    snap = snapshot()
    f = snap.parcels.get(pin)
    t = snap.treasury[pin]
    loc = f.location.split(" (")[0] if f is not None else t.address.split(",")[0].title()
    return f"{loc} · {t.neighborhood} ({short_pin(pin)})"


def short_pin(pin: str) -> str:
    """0131N00031000000 -> 131-N-31 (supplement kept when non-zero)."""
    map_no, block, lot, supp = pin[:4].lstrip("0"), pin[4], pin[5:10].lstrip("0"), pin[10:14]
    s = f"{map_no}-{block}-{lot}"
    return s + (f"-{supp.lstrip('0')}" if supp.strip("0") else "")


# --------------------------------------------------------------------------
# Output fingerprints (what "an output changed" means in sensitivity tests)
# --------------------------------------------------------------------------


def component_text(c) -> str:
    """known 2 / range 1-2 / withheld / n.a. (status-explicit)."""
    if c is None:
        return "absent"
    if c.status == "known":
        return f"known {c.low}"
    if c.status == "range":
        return f"range {c.low}-{c.high}"
    if c.status == "not_applicable":
        return "n.a."
    return "withheld"


def fingerprint(result) -> dict[str, Any]:
    """Decision-relevant outputs of a ScreeningResult as comparable plain values.

    The provenance fact list is deliberately excluded (it changes with any input
    value by design); every decision output is included.
    """
    return {
        "outcome": result.outcome.value,
        "conflicts": tuple((c.level.value, c.kind, c.affects) for c in result.conflicts),
        "use": component_text(result.use),
        "dimensional": component_text(result.dimensional),
        "environment": component_text(result.environment),
        "ease": result.ease.display if result.ease else None,
        "hazard_families": tuple(result.hazard_families),
        "coverage": result.coverage_display,
        "setback_screen": result.setback_screen,
        "area_gap_pct": result.area_gap_pct,
        "upset_to_assessed_land": result.upset_to_assessed_land,
        "barriers": tuple(result.barriers),
        "next_checks": tuple((n.check, n.owner) for n in result.next_checks),
        "next_check_triggers": tuple(n.trigger for n in result.next_checks),
        "warnings": tuple(result.warnings),
    }


def changed_keys(a: Mapping[str, Any], b: Mapping[str, Any]) -> list[str]:
    return sorted(k for k in a if a[k] != b.get(k))


# --------------------------------------------------------------------------
# Deterministic formatting
# --------------------------------------------------------------------------


def _cell(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, (list, tuple)):
        return "; ".join(_cell(x) for x in v) if v else "—"
    s = str(v)
    return s.replace("|", "\\|").replace("\n", " ")


def md_table(headers: Sequence[str], rows: Iterable[Sequence[Any]], *, sort: bool = True) -> str:
    """GitHub-flavoured Markdown table; rows sorted by their rendered cells when ``sort``."""
    rendered = [[_cell(v) for v in r] for r in rows]
    if sort:
        rendered.sort()
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rendered]
    return "\n".join(out)


def frac(n: int, d: int) -> str:
    return f"{n}/{d}"


def to_jsonable(obj: Any) -> Any:
    """Recursively convert dataclasses, enums, tuples, sets and paths to JSON types."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Mapping):
        return {str(k): to_jsonable(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (set, frozenset)):
        return sorted(to_jsonable(v) for v in obj)
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


def dumps(obj: Any) -> str:
    return json.dumps(to_jsonable(obj), sort_keys=True, indent=2, ensure_ascii=False)


def scope_note(text: str) -> str:
    """The mandatory "What this does and does not show" paragraph."""
    return f"**What this does and does not show.** {text}"
