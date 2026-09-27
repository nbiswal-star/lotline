"""Pre-development cost worksheet: the user's assumptions, summed. Never a valuation.

Every default is either copied from a cited source (the City advertisement, the
Treasury record, or ``data/cost_assumptions.csv`` with source and date) or left
blank for the user to fill in. Nothing here invents a number, and nothing here
changes an engine outcome: the worksheet reads ``ScreeningResult`` and the
snapshot and returns display rows plus a plain sum of the values the user keeps.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from lotline.models import ConflictLevel, ScreeningResult, Snapshot, fact_id

COST_FILE = Path(__file__).resolve().parent.parent / "data" / "cost_assumptions.csv"

DISCLAIMER = ("Illustrative pre-development cash estimate using your assumptions — not an appraisal, "
              "bid recommendation or financial advice.")
BLOCKED_BANNER = ("Resolve records before estimating: a critical records conflict means LotLine has not "
                  "established what this parcel is. Any figure entered here rests on unresolved records.")
ENTER_ESTIMATE = "enter your estimate"


@dataclass(frozen=True)
class Assumption:
    key: str
    label: str
    default_usd: float | None
    applies_when: str  # "always" | "terrain_or_undermining" | "fema"
    role: str  # "row" | "reference"
    source: str | None
    source_date: str | None
    source_url: str | None
    note: str | None
    blank_label: str | None = None  # what a blank default means, e.g. "amount unknown: title search required"

    @property
    def cited(self) -> bool:
        return self.default_usd is not None and bool(self.source) and bool(self.source_date)


@dataclass(frozen=True)
class CostRow:
    key: str
    label: str
    default_usd: float | None  # None -> blank, "enter your estimate"
    basis: str  # citation text, or ENTER_ESTIMATE
    fact_ids: tuple[str, ...] = ()
    source_url: str | None = None
    note: str | None = None
    listed_because: str | None = None

    @property
    def cited(self) -> bool:
        return self.default_usd is not None


@dataclass(frozen=True)
class CostWorksheet:
    pin: str
    rows: tuple[CostRow, ...]
    blocked: bool  # critical conflict: show the worksheet under a banner
    notes: tuple[str, ...]  # recorded facts that are shown but not summed
    references: tuple[Assumption, ...]
    disclaimer: str = DISCLAIMER


def _num(value: str | None) -> float | None:
    value = (value or "").strip().replace(",", "").replace("$", "")
    if not value:
        return None
    number = float(value)
    if number < 0:
        raise ValueError("cost defaults must be non-negative")
    return number


def load_assumptions(path: Path = COST_FILE) -> dict[str, Assumption]:
    """Read the cited default table. Missing file -> no defaults (every row blank)."""
    try:
        with Path(path).open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    except OSError:
        return {}
    out: dict[str, Assumption] = {}
    for r in rows:
        a = Assumption(
            key=r["key"].strip(),
            label=r["label"].strip(),
            default_usd=_num(r.get("default_usd")),
            applies_when=(r.get("applies_when") or "always").strip(),
            role=(r.get("role") or "row").strip(),
            source=(r.get("source") or "").strip() or None,
            source_date=(r.get("source_date") or "").strip() or None,
            source_url=(r.get("source_url") or "").strip() or None,
            note=(r.get("note") or "").strip() or None,
            blank_label=(r.get("blank_label") or "").strip() or None,
        )
        # A default without a source and date is not used: blank beats uncited.
        if a.default_usd is not None and not a.cited:
            a = Assumption(**{**a.__dict__, "default_usd": None})
        out[a.key] = a
    return out


def _fact_value(result: ScreeningResult, fid: str) -> object:
    return next((f.value for f in result.facts if f.id == fid), None)


def _applies(a: Assumption, result: ScreeningResult) -> str | None:
    """Why the row is listed for this parcel, or None if it does not apply."""
    families = set(result.hazard_families)
    if a.applies_when == "always":
        return "listed for every advertised vacant lot"
    if a.applies_when == "terrain_or_undermining":
        hit = sorted(families & {"terrain", "undermining"})
        return f"screening layers flag {' and '.join(hit)}" if hit else None
    if a.applies_when == "fema":
        if "FEMA SFHA" in families:
            return "FEMA flood hazard area flagged in screening layers"
        if _fact_value(result, fact_id(result.pin, "fema_sfha")) is None and any(
                f.id == fact_id(result.pin, "fema_zone") for f in result.facts):
            return "FEMA flood zone undetermined in the checked layer"
        return None
    return None


def _money(v: float) -> str:
    return f"${v:,.2f}"


def worksheet(snapshot: Snapshot, result: ScreeningResult,
              assumptions: Mapping[str, Assumption] | None = None) -> CostWorksheet:
    """Rows for one screened parcel. Upset and demolition figures cite their fact IDs."""
    pin = result.pin
    table = load_assumptions() if assumptions is None else assumptions
    rows: list[CostRow] = []
    notes: list[str] = []

    adv = snapshot.advert.get(pin) if pin in snapshot.reconciliation.matched_pins else None
    if adv is not None:
        as_of = snapshot.manifest["city_advertisement"].snapshot_as_of if "city_advertisement" in snapshot.manifest else "unknown"
        rows.append(CostRow(
            key="upset",
            label="Upset price (opening bid; competitive bidding may go higher)",
            default_usd=adv.upset,
            basis=f"City Treasurer Sale advertisement, {as_of}",
            fact_ids=(fact_id(pin, "upset"),),
            listed_because="the opening bid at the Treasurer Sale",
        ))
    else:
        rows.append(CostRow(key="upset", label="Upset price (opening bid)", default_usd=None,
                            basis=ENTER_ESTIMATE, note="Parcel not matched in the City advertisement."))

    for a in table.values():
        if a.role != "row":
            continue
        because = _applies(a, result)
        if because is None:
            continue
        if a.default_usd is not None:
            basis = f"{a.source}, {a.source_date}"
        else:
            basis = a.blank_label or ENTER_ESTIMATE
        rows.append(CostRow(key=a.key, label=a.label, default_usd=a.default_usd, basis=basis,
                            source_url=a.source_url, note=a.note, listed_because=because))

    t = snapshot.treasury.get(pin)
    if t is not None:
        demo_id = fact_id(pin, "demo_cost_due")
        treasury_as_of = (snapshot.manifest["wprdc_treasury_sales"].snapshot_as_of
                          if "wprdc_treasury_sales" in snapshot.manifest else "unknown")
        if t.demo_cost_due > 0:
            rows.append(CostRow(
                key="demolition_lien",
                label="Demolition lien carried forward (if any survives the sale)",
                default_usd=None,
                basis=ENTER_ESTIMATE,
                fact_ids=(demo_id,),
                note=(f"Treasury record lists {_money(t.demo_cost_due)} demolition cost due "
                      f"(WPRDC Treasury Sales, {treasury_as_of}). A title examiner confirms whether "
                      "any of it survives the sale; enter that amount."),
                listed_because="demolition cost due is recorded for this parcel",
            ))
        else:
            notes.append(f"Treasury record lists {_money(t.demo_cost_due)} demolition cost due "
                         f"(WPRDC Treasury Sales, {treasury_as_of}; {demo_id}).")
    notes.append("Liens, including water claims, survive the Treasurer Sale; the upset price does "
                 "not include them.")
    notes.append("90-day redemption period after the sale: the prior owner may redeem, so money spent "
                 "before it ends is at risk. A timing risk, not a dollar figure.")

    blocked = any(c.level is ConflictLevel.CRITICAL for c in result.conflicts)
    references = tuple(a for a in table.values() if a.role == "reference" and a.cited)
    return CostWorksheet(pin=pin, rows=tuple(rows), blocked=blocked, notes=tuple(notes),
                         references=references)


def total(values: Iterable[float | None]) -> tuple[float, int]:
    """Sum of the filled values and how many were filled. Blank rows are not zero; they are skipped."""
    filled = [float(v) for v in values if v is not None]
    if any(v < 0 for v in filled):
        raise ValueError("costs must be non-negative")
    return round(sum(filled), 2), len(filled)


def total_line(values: Iterable[float | None], row_count: int) -> str:
    amount, filled = total(values)
    blank = row_count - filled
    tail = f"; {blank} row{'s' if blank != 1 else ''} left blank (not counted)" if blank else ""
    return f"{_money(amount)} from {filled} filled row{'s' if filled != 1 else ''}{tail}"
