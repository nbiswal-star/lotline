"""View models for the AI reader panels. Presentation only; the AI never decides.

The three AI readers (record reader, Ask LotLine, variance precedents) live in
``lotline.ai``. This adapter imports them lazily and defensively: if a module or
function is missing, the panel is hidden or shows a plain "unavailable" line, and
the rest of the packet is unaffected. Every call is wrapped so a reader failure
can never break the app. No network is used unless the user clicks, except that
a cached, re-verified record digest is shown automatically (cache only: the
client passed for that read refuses any network request).
"""

from __future__ import annotations

import importlib
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

UNAVAILABLE_READER = "AI reader unavailable (no API key / offline) — raw record text is in Provenance."
HUMAN_RESOLVER = "Evidence for the human resolver — LotLine does not change its decision based on AI output."
PRINCIPLE = "Claude reads the record. Rules decide. Code verifies source identity and every displayed quote."
OFFLINE_NOTE = "No API key? Everything except the AI readers works offline."
PRECEDENT_NOTE = "Similar case — not a prediction."
RELIEF_BANNER = "Possible relief path (not a determination) — confirm with the Zoning Administrator."


def module(name: str, *attrs: str) -> Any | None:
    """Import ``lotline.ai.<name>`` if present and exposing ``attrs``; else None."""
    try:
        mod = importlib.import_module(f"lotline.ai.{name}")
    except Exception:  # noqa: BLE001 - a missing or broken reader just hides its panel
        return None
    return mod if all(callable(getattr(mod, a, None)) for a in attrs) else None


def credentials() -> bool:
    try:
        from lotline.ai.client import credentials_available
        return bool(credentials_available())
    except Exception:  # noqa: BLE001
        return False


class _Refuse:
    """Stands in for ``client.beta.messages``: any request raises AIUnavailable (cache-only reads)."""

    def create(self, *args: object, **kwargs: object) -> None:
        try:
            from lotline.ai.client import AIUnavailable
        except Exception:  # noqa: BLE001
            raise RuntimeError("cache only") from None
        raise AIUnavailable("cache only: no request made")


class CacheOnlyClient:
    def __init__(self) -> None:
        self.beta = type("Beta", (), {"messages": _Refuse()})()
        self.messages = _Refuse()


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _tuple(v: Any) -> tuple:
    if v is None:
        return ()
    if isinstance(v, (list, tuple, set, frozenset)):
        return tuple(v)
    return (v,)


# --------------------------------------------------------------------------
# Record reader
# --------------------------------------------------------------------------


@dataclass
class EvidenceItemVM:
    record_id: str
    source: str
    date: str
    field: str
    quote: str
    indicates: str
    relevance: str
    currency: str | None
    corroboration: str | None


@dataclass
class EvidenceVM:
    status: str
    items: list[EvidenceItemVM] = field(default_factory=list)
    record_count: int = 0
    rejected_count: int = 0
    reason: str | None = None
    resolver_note: str | None = None
    lines: list[str] = field(default_factory=list)
    model: str | None = None
    created_at: str | None = None
    elapsed_s: float | None = None
    cached: bool = False

    @property
    def verified(self) -> bool:
        return self.status in ("verified", "cached_verified")

    @property
    def counter(self) -> str:
        n, m, k = self.record_count, len(self.items), self.rejected_count
        return (f"Claude read {n} record{'s' if n != 1 else ''}; {m} item{'s' if m != 1 else ''} "
                f"verified; {k} rejected")

    @property
    def timing(self) -> str | None:
        if self.elapsed_s is None:
            return None
        base = f"Claude read {self.record_count} record{'s' if self.record_count != 1 else ''} in {self.elapsed_s:.1f} s"
        return base + (" (cached, re-verified now)" if self.cached else "")


def _currency_label(v: Any) -> str | None:
    if v in (None, ""):
        return None
    s = str(v)
    low = s.lower()
    if low in ("latest", "latest_record", "current"):
        return "latest record"
    if low in ("superseded", "possibly_superseded", "later_record_exists"):
        return "older dated entry; later records also exist"
    return s.replace("_", " ")


def digest_vm(d: Any, *, elapsed_s: float | None = None, cached: bool | None = None,
              evidence_mod: Any = None) -> EvidenceVM:
    status = str(_get(d, "status", "unavailable"))
    rejected = _get(d, "rejected", ())
    rejected_count = rejected if isinstance(rejected, int) else len(_tuple(rejected))
    items = []
    if status in ("verified", "cached_verified"):
        for it in _tuple(_get(d, "items", ())):
            items.append(EvidenceItemVM(
                record_id=str(_get(it, "record_id", "")),
                source=str(_get(it, "source_id", "") or ""),
                date=str(_get(it, "record_date", "") or "date not recorded"),
                field=str(_get(it, "field", "") or ""),
                quote=str(_get(it, "quote", "")),
                indicates=str(_get(it, "indicates", "") or ""),
                relevance=str(_get(it, "relevance", "") or ""),
                currency=_currency_label(_get(it, "currency")),
                corroboration=(str(_get(it, "corroboration")) if _get(it, "corroboration") else None),
            ))
    note, lines = None, []
    if evidence_mod is not None:
        try:
            fn = getattr(evidence_mod, "resolver_note", None)
            note = fn(d) if callable(fn) else None
        except Exception:  # noqa: BLE001
            note = None
        try:
            fn = getattr(evidence_mod, "digest_lines", None)
            lines = list(fn(d)) if callable(fn) else []
        except Exception:  # noqa: BLE001
            lines = []
    stored = _get(d, "elapsed_s", None)
    return EvidenceVM(
        status=status, items=items,
        record_count=int(_get(d, "record_count", 0) or 0),
        rejected_count=int(rejected_count),
        reason=_get(d, "reason"), resolver_note=note, lines=lines,
        model=_get(d, "model"), created_at=str(_get(d, "created_at") or "") or None,
        elapsed_s=elapsed_s if elapsed_s is not None else (float(stored) if stored is not None else None),
        cached=status == "cached_verified" if cached is None else cached,
    )


def cached_evidence(pin: str, snapshot: Any) -> EvidenceVM | None:
    """Cache-only digest (no network). None when the reader is missing or has nothing cached."""
    mod = module("evidence", "evidence_digest")
    if mod is None:
        return None
    try:
        d = mod.evidence_digest(pin, snapshot, client=CacheOnlyClient(), use_cache=True, save_cache=False)
    except Exception:  # noqa: BLE001
        return None
    vm = digest_vm(d, evidence_mod=mod)
    return vm if vm.status in ("cached_verified", "verified", "no_records") else None


def read_evidence(pin: str, snapshot: Any) -> EvidenceVM:
    """User clicked: run the reader (may call Claude). Never raises."""
    mod = module("evidence", "evidence_digest")
    if mod is None:
        return EvidenceVM(status="unavailable", reason="record reader not installed")
    if not credentials():
        cached = cached_evidence(pin, snapshot)
        return cached or EvidenceVM(status="unavailable", reason="no API key configured")
    start = time.perf_counter()
    try:
        d = mod.evidence_digest(pin, snapshot)
    except Exception as exc:  # noqa: BLE001
        return EvidenceVM(status="unavailable", reason=type(exc).__name__)
    elapsed = time.perf_counter() - start
    status = str(_get(d, "status", ""))
    return digest_vm(d, elapsed_s=None if status == "cached_verified" else elapsed, evidence_mod=mod)


def evidence_available() -> bool:
    return module("evidence", "evidence_digest") is not None


def keyword_hits(pin: str, snapshot: Any) -> list[str]:
    """Frozen no-AI lexicon baseline; never reads evaluation labels."""
    mod = module("evidence", "keyword_baseline")
    if mod is None:
        return []
    try:
        return list(mod.keyword_baseline(pin, snapshot))
    except Exception:  # noqa: BLE001 - comparison must never break the packet
        return []


# --------------------------------------------------------------------------
# Ask LotLine
# --------------------------------------------------------------------------

FRAME_LABEL = {
    "why_deferred": "Why deferred",
    "why_outcome": "Why this outcome",
    "what_next": "What next",
    "next": "What next",
    "rule": "What a rule says",
    "what_a_rule_says": "What a rule says",
    "investment_advice": "Declined: investment advice",
    "declined_investment_advice": "Declined: investment advice",
}


@dataclass
class SentenceVM:
    text: str
    fact_ids: tuple[str, ...]
    code_refs: tuple[str, ...]


@dataclass
class AnswerVM:
    question: str
    status: str
    frame: str | None
    sentences: list[SentenceVM]
    violations: list[str]
    reason: str | None
    model: str | None


def frame_label(frame: Any) -> str | None:
    if not frame:
        return None
    key = str(frame).strip()
    return FRAME_LABEL.get(key.lower().replace(" ", "_").replace(":", ""), key.replace("_", " ").capitalize())


def suggested_questions() -> list[str]:
    mod = module("ask", "ask")
    if mod is None:
        return []
    try:
        return [str(q) for q in getattr(mod, "SUGGESTED_QUESTIONS", ())][:6]
    except Exception:  # noqa: BLE001
        return []


def ask_available() -> bool:
    return module("ask", "ask") is not None


def _violation_text(v: Any) -> str:
    rule = _get(v, "rule")
    if rule:
        msg = _get(v, "message")
        return f"{rule}: {msg}" if msg else str(rule)
    return str(v)


def answer_vm(a: Any, question: str) -> AnswerVM:
    return AnswerVM(
        question=str(_get(a, "question", question) or question),
        status=str(_get(a, "status", "unavailable")),
        frame=frame_label(_get(a, "frame")),
        sentences=[SentenceVM(str(_get(s, "text", "")), tuple(str(x) for x in _tuple(_get(s, "fact_ids"))),
                              tuple(str(x) for x in _tuple(_get(s, "code_refs"))))
                   for s in _tuple(_get(a, "sentences", ()))],
        violations=[_violation_text(v) for v in _tuple(_get(a, "violations", ()))],
        reason=_get(a, "reason"),
        model=_get(a, "model"),
    )


def ask_question(question: str, result: Any) -> AnswerVM:
    mod = module("ask", "ask")
    if mod is None:
        return AnswerVM(question, "unavailable", None, [], [], "Ask LotLine is not installed", None)
    try:
        return answer_vm(mod.ask(question, result), question)
    except Exception as exc:  # noqa: BLE001
        return AnswerVM(question, "unavailable", None, [], [], type(exc).__name__, None)


# --------------------------------------------------------------------------
# Variance precedents and relief paths
# --------------------------------------------------------------------------


@dataclass
class ReliefVM:
    kind: str
    outcome: str
    description: str
    quote: str


@dataclass
class PrecedentVM:
    slug: str
    case_number: str
    address: str
    district: str
    decision_date: str
    lot_description: str
    reliefs: list[ReliefVM]
    rationale_quote: str
    source_url: str
    verified: bool
    match_note: str


@dataclass
class ReliefPathVM:
    trigger: str
    path: str
    code_ref: str
    code_quote: str
    precedents: list[str]
    counts: str | None


def outcome_counts_line(outcomes: list[str]) -> str | None:
    """"n granted / N decided" from the verified relief outcomes shown (display tally only)."""
    low = [o.lower() for o in outcomes if o]
    granted = sum("grant" in o and "not granted" not in o for o in low)
    denied = sum(("den" in o or "not granted" in o) for o in low)
    decided = granted + denied
    return f"{granted} granted / {decided} decided" if decided else None


def _precedent_vm(card: Any, match_note: str) -> PrecedentVM:
    return PrecedentVM(
        slug=str(_get(card, "slug", "")),
        case_number=str(_get(card, "case_number", "") or ""),
        address=str(_get(card, "address", "") or ""),
        district=str(_get(card, "district", "") or ""),
        decision_date=str(_get(card, "decision_date", "") or "date not recorded"),
        lot_description=str(_get(card, "lot_description", "") or ""),
        reliefs=[ReliefVM(str(_get(r, "kind", "") or ""), str(_get(r, "outcome", "") or ""),
                          str(_get(r, "description", "") or ""), str(_get(r, "quote", "") or ""))
                 for r in _tuple(_get(card, "reliefs", ()))],
        rationale_quote=str(_get(card, "rationale_quote", "") or ""),
        source_url=str(_get(card, "source_url", "") or ""),
        verified=bool(_get(card, "verified", False)),
        match_note=str(match_note or ""),
    )


def precedents(result: Any) -> tuple[list[PrecedentVM], str | None] | None:
    """(matched verified cards, "n granted / N decided") or None when the module is missing."""
    mod = module("precedents", "precedents_for")
    if mod is None:
        return None
    try:
        cards = mod.load_cards() if callable(getattr(mod, "load_cards", None)) else None
        matched = mod.precedents_for(result, cards=cards) if cards is not None else mod.precedents_for(result)
    except Exception:  # noqa: BLE001
        return None
    vms = []
    for entry in matched or ():
        card, match_note = (entry if isinstance(entry, tuple) and len(entry) == 2 else (entry, ""))
        vm = _precedent_vm(card, match_note)
        if vm.verified:
            vms.append(vm)
    return vms, outcome_counts_line([r.outcome for v in vms for r in v.reliefs])


def _counts_text(c: Any) -> str | None:
    if c is None:
        return None
    if isinstance(c, str):
        return c
    if isinstance(c, Mapping):
        g, n = c.get("granted"), c.get("decided", c.get("total"))
        if g is not None and n is not None:
            return f"{g} granted / {n} decided"
        return ", ".join(f"{k} {v}" for k, v in c.items())
    if isinstance(c, (tuple, list)) and len(c) == 2:
        return f"{c[0]} granted / {c[1]} decided"
    g, n = getattr(c, "granted", None), getattr(c, "decided", None)
    return f"{g} granted / {n} decided" if g is not None and n is not None else str(c)


def relief_paths(result: Any) -> list[ReliefPathVM] | None:
    mod = module("precedents", "relief_paths")
    if mod is None:
        return None
    try:
        paths = mod.relief_paths(result)
    except Exception:  # noqa: BLE001
        return None
    out = []
    for p in paths or ():
        precs = []
        for c in _tuple(_get(p, "precedents", ())):
            if isinstance(c, str):
                precs.append(c)
            else:
                card = c[0] if isinstance(c, tuple) else c
                precs.append(str(_get(card, "case_number", "") or _get(card, "slug", "")))
        out.append(ReliefPathVM(
            trigger=str(_get(p, "trigger", "") or ""), path=str(_get(p, "path", "") or ""),
            code_ref=str(_get(p, "code_ref", "") or ""), code_quote=str(_get(p, "code_quote", "") or ""),
            precedents=[x for x in precs if x], counts=_counts_text(_get(p, "counts")),
        ))
    return out
