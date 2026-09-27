"""Checks prompted by the record evidence: extra human checks derived from verified quotes.

This module is NOT part of the engine. The engine's outcome, scores, barriers and next checks
never read record text or AI output. What this module adds is a short list of *additional*
checks for the human resolver, each derived deterministically from items of a verified
``EvidenceDigest`` (every item is an exact, code-verified quote from a PLI or condemned-property
record) and each citing the record ids and quotes that prompted it:

* (a) a structure is described on the lot (structure present, or removed/demolished):
  §921.04.A's lot-of-record path applies only if the lot was vacant on the date the Code became
  applicable to it, so the resolver must confirm that condition first;
* (b) a quote mentions a City-funded demolition or a lien: a demolition / municipal lien search.

A site-condition trigger counts an item only when its displayed, verified semantic label is a
structure label. A quote whose label was withheld (lexicon/judge disagreement or judge
unavailable) cannot be promoted again by a keyword match. No model-written prose is used; every
string shown is a fixed template plus verified record ids, years and quotes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

STRUCTURE_LABELS = frozenset({"structure_present", "structure_removed_or_demolished"})
VERIFIED = frozenset({"verified", "cached_verified"})
CONDITION_SOURCES = frozenset({"pli_violations", "pli_permits", "condemned_properties"})

LOT_OF_RECORD_KEY = "lot_of_record_vacancy"
LIEN_KEY = "demolition_lien_search"

LOT_OF_RECORD_TEXT = ("Confirm the lot was vacant on the date the Code became applicable "
                      "(§921.04.A lot-of-record condition); PLI records describe a structure")
LOT_OF_RECORD_OWNER = "Zoning Administrator + County deed/plat records"
LIEN_TEXT = "Demolition / municipal lien search"
LIEN_OWNER = "title examiner + City Law / Treasurer"
SECTION_TITLE = "Checks prompted by the record evidence (AI-read, quote-verified)"
SECTION_NOTE = ("Derived by code from verified record quotes; they add checks for the resolver and never "
                "change LotLine's outcome, score or the engine's next checks.")
RELIEF_PATH_SUFFIX = ("PLI records describe a structure on this parcel — the lot-of-record condition "
                      "must be confirmed first")

CITY_FUNDED = re.compile(r"\bcity[- ]funded\b", re.I)
LIEN = re.compile(r"\bliens?\b", re.I)
DEMOLITION_DONE = re.compile(r"\bdemolished\b|\brazed\b|\bdemolition (?:has been |was )?completed\b", re.I)


@dataclass(frozen=True)
class EvidenceRef:
    record_id: str
    date: str  # record date, or "date not recorded"
    source: str
    quote: str


@dataclass(frozen=True)
class EvidenceCheck:
    key: str
    check: str
    owner: str
    reason: str  # what prompted it, citing record ids
    refs: tuple[EvidenceRef, ...]


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for n in names:
        v = obj.get(n) if isinstance(obj, dict) else getattr(obj, n, None)
        if v not in (None, ""):
            return v
    return default


def _items(digest: Any) -> list[Any]:
    if digest is None or str(_get(digest, "status", default="")) not in VERIFIED:
        return []
    return list(_get(digest, "items", default=()) or ())


def _ref(item: Any) -> EvidenceRef:
    return EvidenceRef(record_id=str(_get(item, "record_id", default="")),
                       date=str(_get(item, "record_date", "date", default="date not recorded")),
                       source=str(_get(item, "source_id", "source", default="")),
                       quote=str(_get(item, "quote", default="")))


def _structure_item(item: Any) -> bool:
    if str(_get(item, "source_id", "source", default="")) not in CONDITION_SOURCES:
        return False
    label = str(_get(item, "indicates", default=""))
    return label in STRUCTURE_LABELS


def structure_refs(digest: Any) -> list[EvidenceRef]:
    """Verified items that describe a structure on the lot (present or removed/demolished)."""
    return [_ref(i) for i in _items(digest) if _structure_item(i)]


def _year(date: str) -> str | None:
    m = re.match(r"(\d{4})-\d{2}-\d{2}", date or "")
    return m.group(1) if m else None


def _demolition_year(refs: list[EvidenceRef]) -> str | None:
    years = [y for r in refs if DEMOLITION_DONE.search(r.quote) and (y := _year(r.date))]
    return max(years) if years else None


def _ids(refs: list[EvidenceRef]) -> str:
    ids = list(dict.fromkeys(r.record_id for r in refs))
    return ", ".join(ids)


def lot_of_record_text(digest: Any) -> str | None:
    refs = structure_refs(digest)
    if not refs:
        return None
    year = _demolition_year(refs)
    return LOT_OF_RECORD_TEXT + (f" (demolished {year})" if year else "")


def evidence_checks(digest: Any) -> list[EvidenceCheck]:
    """Extra checks prompted by a verified digest; empty unless the digest is verified."""
    out: list[EvidenceCheck] = []
    refs = structure_refs(digest)
    if refs:
        out.append(EvidenceCheck(
            key=LOT_OF_RECORD_KEY, check=lot_of_record_text(digest) or LOT_OF_RECORD_TEXT,
            owner=LOT_OF_RECORD_OWNER,
            reason=f"verified record quotes describe a structure ({_ids(refs)})", refs=tuple(refs)))
    lien = [_ref(i) for i in _items(digest)
            if CITY_FUNDED.search(str(_get(i, "quote", default=""))) or LIEN.search(str(_get(i, "quote", default="")))]
    if lien:
        what = ("a City-funded demolition" if any(CITY_FUNDED.search(r.quote) for r in lien) else "")
        if any(LIEN.search(r.quote) for r in lien):
            what = f"{what} and a lien" if what else "a lien"
        out.append(EvidenceCheck(
            key=LIEN_KEY, check=LIEN_TEXT, owner=LIEN_OWNER,
            reason=f"verified record quotes mention {what} ({_ids(lien)})", refs=tuple(lien)))
    return out


def ticket_rows(checks: list[EvidenceCheck]) -> list[dict[str, str]]:
    """Rows shaped like the packet's next-check rows (for the task-ticket picker)."""
    return [{"Check": c.check, "Who resolves it": c.owner,
             "Reason listed": f"prompted by record evidence: {c.reason}", "Standard": "evidence"}
            for c in checks]
