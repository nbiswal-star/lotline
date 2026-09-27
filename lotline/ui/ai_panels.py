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

import concurrent.futures
import importlib
import re
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
LIVE_TIMEOUT_S = 45.0  # wall clock for one live reader click; then the cached verified read is shown
LIVE_LABEL = "live · verified"
CACHED_LABEL = "cached · re-verified now"
UNVERIFIED_DISPLAY = "label not verified — quote only"
WITHHELD_DISPLAY = {
    "unverified_label": UNVERIFIED_DISPLAY,
    "label withheld: judge unsure": "label withheld (judge unsure) — quote only",
    "label withheld: judge unavailable": "label withheld (judge not run) — quote only",
}
LATEST_CURRENCY = "latest record for this lot"


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
    indicates_code: str = ""


def indicates_phrase(code: str, evidence_mod: Any = None) -> str:
    """Plain wording for a label code (never a raw code on screen)."""
    if not code:
        return ""
    if code in WITHHELD_DISPLAY:
        return WITHHELD_DISPLAY[code]
    table = getattr(evidence_mod, "INDICATES_PHRASE", None) if evidence_mod is not None else None
    if isinstance(table, Mapping) and code in table:
        return str(table[code])
    return code.replace("_", " ")


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
    raw: Any = None  # the verified digest itself (for Ask LotLine and evidence-prompted checks)
    headline: str | None = None
    checks: list[Any] = field(default_factory=list)  # evidence_checks.EvidenceCheck
    live_failure: str | None = None  # why a live read fell back to the cached read

    @property
    def verified(self) -> bool:
        return self.status in ("verified", "cached_verified")

    @property
    def source_label(self) -> str | None:
        if not self.verified:
            return None
        return CACHED_LABEL if self.cached else LIVE_LABEL

    @property
    def counter(self) -> str:
        n, m, k = self.record_count, len(self.items), self.rejected_count
        return (f"Claude read {n} record{'s' if n != 1 else ''}; {m} item{'s' if m != 1 else ''} "
                f"verified; {k} rejected")

    @property
    def timing(self) -> str | None:
        n = self.record_count
        recs = f"{n} record{'s' if n != 1 else ''}"
        if self.cached:
            when = _short_date(self.created_at)
            if self.elapsed_s is not None and when:
                return f"cached read (re-verified now); originally read in {self.elapsed_s:.1f} s on {when}"
            return "cached read (re-verified now)"
        if self.elapsed_s is None:
            return None
        return f"Claude read {recs} in {self.elapsed_s:.1f} s"


def _short_date(iso: Any) -> str | None:
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(iso or ""))
    return m.group(1) if m else None


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
        raw_items = _tuple(_get(d, "items", ()))
        latest_ids = {str(_get(it, "record_id", "")) for it in raw_items
                      if str(_get(it, "currency", "") or "") == LATEST_CURRENCY}
        for it in raw_items:
            code = str(_get(it, "indicates", "") or "")
            currency = _currency_label(_get(it, "currency"))
            date = str(_get(it, "record_date", "") or "date not recorded")
            if str(_get(it, "currency", "") or "") == LATEST_CURRENCY and len(latest_ids) > 1:
                # Several records share the latest date: none of them is "the" latest record.
                currency = f"latest date on file ({date}), shared by {len(latest_ids)} records"
            items.append(EvidenceItemVM(
                record_id=str(_get(it, "record_id", "")),
                source=str(_get(it, "source_id", "") or ""),
                date=date,
                field=str(_get(it, "field", "") or ""),
                quote=str(_get(it, "quote", "")),
                indicates=indicates_phrase(code, evidence_mod),
                relevance=str(_get(it, "relevance", "") or ""),
                currency=currency,
                corroboration=(str(_get(it, "corroboration")) if _get(it, "corroboration") else None),
                indicates_code=code,
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
        raw=d if status in ("verified", "cached_verified") else None,
        headline=headline(items) if status in ("verified", "cached_verified") else None,
        checks=evidence_checks(d),
    )


_DEMOLITION_DONE = re.compile(r"\bdemolished\b|\brazed\b|\bdemolition (?:has been |was )?completed\b", re.I)


def headline(items: list[EvidenceItemVM]) -> str | None:
    """The most decision-relevant verified quote and the structured record it contradicts (both shown).

    Deterministic: the latest-dated PLI quote reporting a completed demolition, and an Active
    condemned-properties status. LotLine does not choose between them.
    """
    demo = sorted((i for i in items if i.source == "pli_violations"
                   and i.indicates_code == "structure_removed_or_demolished"
                   and _DEMOLITION_DONE.search(i.quote) and i.date[:1].isdigit()),
                  key=lambda i: (i.date, i.record_id), reverse=True)
    cond = next((i for i in items if i.source == "condemned_properties"
                 and re.fullmatch(r"\s*active\s*", i.quote, re.I)), None)
    parts = []
    if demo:
        d = demo[0]
        parts.append(f"PLI record {d.record_id} ({d.date}): “{d.quote}”")
    if cond is not None:
        parts.append(f"the condemned-properties list record {cond.record_id} ({cond.date}) still shows "
                     f"status “{cond.quote.strip()}”")
    if not parts:
        return None
    if len(parts) == 2:
        return f"{parts[0]} — {parts[1]}. Both are shown; LotLine does not choose between them."
    return parts[0][0].upper() + parts[0][1:] + "."


def evidence_checks(d: Any) -> list[Any]:
    """Evidence-prompted checks (lotline.ai.evidence_checks); empty if the module is missing."""
    try:
        from lotline.ai.evidence_checks import evidence_checks as fn
        return list(fn(d))
    except Exception:  # noqa: BLE001 - never break the packet
        return []


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


def record_count(pin: str, snapshot: Any) -> int:
    """Distinct enforcement records on file for this parcel (for the in-progress message)."""
    try:
        return len({r.record_id for r in getattr(snapshot, "record_text", {}).get(pin, ())})
    except Exception:  # noqa: BLE001
        return 0


def _live_client() -> Any:
    from lotline.ai.client import make_client
    client = make_client(LIVE_TIMEOUT_S)
    try:
        return client.with_options(max_retries=0)
    except Exception:  # noqa: BLE001
        return client


def _with_fallback(pin: str, snapshot: Any, reason: str) -> EvidenceVM:
    cached = cached_evidence(pin, snapshot)
    if cached is not None and cached.verified:
        cached.live_failure = reason
        return cached
    return EvidenceVM(status="unavailable", reason=reason)


def read_evidence(pin: str, snapshot: Any, *, timeout_s: float = LIVE_TIMEOUT_S) -> EvidenceVM:
    """User clicked: a live Claude read (fresh, not the cache) within ``timeout_s``. Never raises.

    On no key, offline mode, a timeout, an API failure or a rejected reading, the cached verified
    read is re-verified and shown instead (labeled as cached), so the panel is never blank.
    """
    mod = module("evidence", "evidence_digest")
    if mod is None:
        return EvidenceVM(status="unavailable", reason="record reader not installed")
    if not credentials():
        cached = cached_evidence(pin, snapshot)
        return cached or EvidenceVM(status="unavailable", reason="no API key configured")
    start = time.perf_counter()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        fut = pool.submit(lambda: mod.evidence_digest(pin, snapshot, client=_live_client(), use_cache=False))
        d = fut.result(timeout=timeout_s)
    except concurrent.futures.TimeoutError:
        return _with_fallback(pin, snapshot, f"live read exceeded {timeout_s:.0f} s")
    except Exception as exc:  # noqa: BLE001
        return _with_fallback(pin, snapshot, f"live read failed ({type(exc).__name__})")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    elapsed = time.perf_counter() - start
    status = str(_get(d, "status", ""))
    if status not in ("verified", "cached_verified", "no_records"):
        return _with_fallback(pin, snapshot, f"live read {status}" + (f": {_get(d, 'reason')}" if _get(d, "reason") else ""))
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
    "use_permission": "Can this use be built here",
    "direct_answer_from_engine": "Answer from the engine packet",
    "decline_out_of_scope": "Outside LotLine's scope",
    "record_evidence": "What the enforcement record says",
}
DECLINE_REASON = {
    "investment_advice": "Investment advice is outside LotLine's scope",
    "market_value": "Market value and price are outside LotLine's scope",
    "legal_determination": "Legal, title and zoning determinations are outside LotLine's scope",
    "outside_snapshot": "That is not established by this parcel's screening records",
    "other": "That is outside what this parcel's screening packet answers",
    "empty question": "Type a question about this parcel",
}
ANSWER_SOURCE_LABEL = {
    "live": "live · verified",
    "cached": "cached answer · re-verified now",
    "record_evidence": "record evidence · quote-verified",
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
    source: str | None = None
    elapsed_s: float | None = None
    created_at: str | None = None

    @property
    def source_label(self) -> str | None:
        if self.status not in ("answered", "declined") or not self.source:
            return None
        base = ANSWER_SOURCE_LABEL.get(self.source, self.source)
        if self.source == "live" and self.elapsed_s is not None:
            return f"{base} · {self.elapsed_s:.1f} s"
        return base

    @property
    def decline_text(self) -> str:
        r = self.reason or "other"
        return DECLINE_REASON.get(r, r.replace("_", " "))


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
        return [str(q) for q in getattr(mod, "SUGGESTED_QUESTIONS", ())][:8]
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
        source=_get(a, "source"),
        elapsed_s=_get(a, "elapsed_s"),
        created_at=_get(a, "created_at"),
    )


def ask_question(question: str, result: Any, evidence: Any = None) -> AnswerVM:
    """Ask LotLine. ``evidence`` is the parcel's verified record digest, when one is loaded."""
    mod = module("ask", "ask")
    if mod is None:
        return AnswerVM(question, "unavailable", None, [], [], "Ask LotLine is not installed", None)
    try:
        try:
            a = mod.ask(question, result, evidence=evidence)
        except TypeError:  # an older ask() without the evidence keyword
            a = mod.ask(question, result)
        return answer_vm(a, question)
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
    caution: str | None = None


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


def relief_paths(result: Any, evidence: Any = None) -> list[ReliefPathVM] | None:
    mod = module("precedents", "relief_paths")
    if mod is None:
        return None
    try:
        try:
            paths = mod.relief_paths(result, evidence=evidence)
        except TypeError:  # an older relief_paths() without the evidence keyword
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
            caution=(str(_get(p, "caution")) if _get(p, "caution") else None),
        ))
    return out
