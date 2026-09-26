"""Defensive bridge to ``lotline.memo`` (built in parallel).

The app must run when the memo layer is missing, partial, or raises. Every
entry point here returns ``None`` (plus an error string) instead of raising.
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

MEMO_MODULES = ("lotline.memo", "lotline.memo.memo", "lotline.memo.deterministic",
                "lotline.memo.produce", "lotline.memo.pipeline")
DETERMINISTIC_NAMES = ("deterministic_memo",)
PRODUCE_NAMES = ("produce_memo",)


def _find(names: tuple[str, ...], modules: tuple[str, ...] = MEMO_MODULES) -> Callable[..., Any] | None:
    for mod_name in modules:
        try:
            mod = importlib.import_module(mod_name)
        except Exception:  # noqa: BLE001 - optional layer, any import failure means "absent"
            continue
        for n in names:
            fn = getattr(mod, n, None)
            if callable(fn):
                return fn
    return None


def deterministic_fn() -> Callable[..., Any] | None:
    return _find(DETERMINISTIC_NAMES)


def produce_fn() -> Callable[..., Any] | None:
    return _find(PRODUCE_NAMES)


def run_cases_fn() -> Callable[..., Any] | None:
    return _find(("run_cases",), ("lotline.memo.eval",))


def _call(fn: Callable[..., Any], available: dict[str, Any]) -> Any:
    """Call ``fn`` binding parameters by name (ctx/result/snapshot/facts...)."""
    sig = inspect.signature(fn)
    args: list[Any] = []
    kwargs: dict[str, Any] = {}
    aliases = {
        "ctx": "ctx", "context": "ctx", "parcel_context": "ctx",
        "result": "result", "screening": "result", "screening_result": "result", "r": "result",
        "snapshot": "snapshot", "snap": "snapshot",
    }
    for p in sig.parameters.values():
        key = aliases.get(p.name)
        if key is not None and key in available:
            if p.kind is inspect.Parameter.KEYWORD_ONLY:
                kwargs[p.name] = available[key]
            else:
                args.append(available[key])
        elif p.default is inspect.Parameter.empty and p.kind not in (
            inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD
        ):
            raise TypeError(f"cannot supply parameter {p.name!r}")
    return fn(*args, **kwargs)


@dataclass
class ClaimVM:
    text: str
    fact_ids: tuple[str, ...]
    claim_type: str
    author: str


@dataclass
class MemoVM:
    source: str
    claims: list[ClaimVM] = field(default_factory=list)
    fallback_reason: str | None = None
    checker_summary: str | None = None
    notes: list[str] = field(default_factory=list)
    rejected_summary: str | None = None


def _report_summary(report: Any) -> str | None:
    if report is None:
        return None
    violations = getattr(report, "violations", None)
    if violations is not None:
        try:
            n = len(violations)
        except TypeError:
            n = None
        if n is not None:
            return "Claim checker: 0 violations" if n == 0 else f"Claim checker: {n} violation(s)"
    ok = getattr(report, "ok", getattr(report, "passed", None))
    if isinstance(ok, bool):
        return "Claim checker: passed" if ok else "Claim checker: rejected"
    return None


def to_vm(memo: Any) -> MemoVM | None:
    claims = getattr(memo, "claims", None)
    if claims is None:
        return None
    rejected = getattr(memo, "rejected_draft", None)
    return MemoVM(
        source=str(getattr(memo, "source", "deterministic")),
        claims=[
            ClaimVM(
                text=str(getattr(c, "text", c)),
                fact_ids=tuple(getattr(c, "fact_ids", ()) or ()),
                claim_type=str(getattr(c, "claim_type", "")),
                author=str(getattr(c, "author", "engine")),
            )
            for c in claims
        ],
        fallback_reason=getattr(memo, "fallback_reason", None),
        checker_summary=_report_summary(getattr(memo, "report", None)),
        notes=list(getattr(memo, "notes", []) or []),
        rejected_summary=_report_summary(rejected) if rejected is not None else None,
    )


def build_memo(fn: Callable[..., Any] | None, **available: Any) -> tuple[MemoVM | None, str | None]:
    """(memo view model, error). Never raises."""
    if fn is None:
        return None, "memo layer not available"
    try:
        vm = to_vm(_call(fn, available))
    except Exception as exc:  # noqa: BLE001 - memo must never break the packet
        return None, f"{type(exc).__name__}: {exc}"
    return (vm, None) if vm is not None else (None, "memo layer returned no claims")


def run_cases(**available: Any) -> tuple[Any, str | None]:
    fn = run_cases_fn()
    if fn is None:
        return None, "claim-checker case runner not available yet"
    try:
        return _call(fn, available), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def summarize_cases(outcome: Any) -> tuple[int, int, list[dict[str, str]]] | None:
    """(passed, total, rows) from whatever ``run_cases`` returns, if recognizable."""
    items = outcome
    for attr in ("cases", "results"):
        if hasattr(outcome, attr):
            items = getattr(outcome, attr)
    if isinstance(items, dict):
        items = list(items.values())
    try:
        items = list(items)
    except TypeError:
        return None
    rows: list[dict[str, str]] = []
    passed = 0
    for i, it in enumerate(items, 1):
        get = (lambda k, it=it: it.get(k)) if isinstance(it, dict) else (lambda k, it=it: getattr(it, k, None))
        ok = get("passed")
        if ok is None:
            ok = get("ok")
        ok = bool(ok)
        passed += ok
        rows.append({
            "Case": str(get("name") or get("case") or get("id") or i),
            "Result": "pass" if ok else "FAIL",
            "Detail": str(get("detail") or get("expected") or get("message") or ""),
        })
    return passed, len(rows), rows


# --------------------------------------------------------------------------
# Claude drafting (M5) and live red-team view. Network only on button click.
# --------------------------------------------------------------------------


@dataclass
class ViolationVM:
    rule: str
    message: str
    claim: str = ""


@dataclass
class ClaudeDraftVM:
    status: str  # accepted | rejected | unavailable | refused | failed | cached_* | error
    headline: str
    memo: MemoVM | None
    shown: str  # "Claude-assembled memo (claim-checked)" or "Deterministic cited memo"
    claims_checked: int | None = None
    violations: list[ViolationVM] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _violations(report: Any) -> list[ViolationVM]:
    return [ViolationVM(str(getattr(v, "rule", "")), str(getattr(v, "message", "")), str(getattr(v, "text", "")))
            for v in (getattr(report, "violations", ()) or ())]


def claude_draft(result: Any, *, client: Any = None, use_cache: bool = True,
                 save_cache: bool = True) -> ClaudeDraftVM:
    """Run the Claude draft through the checker. Never raises; no key -> deterministic memo, no error."""
    try:
        from lotline.memo import llm
    except Exception as exc:  # noqa: BLE001
        return ClaudeDraftVM("error", f"Claude drafting not available ({type(exc).__name__}) — "
                             "deterministic memo shown", None, "Deterministic cited memo")
    try:
        d = llm.run_claude_draft(result, client=client, use_cache=use_cache, save_cache=save_cache)
    except Exception as exc:  # noqa: BLE001
        return ClaudeDraftVM("error", f"Claude drafting failed ({type(exc).__name__}) — deterministic memo shown",
                             None, "Deterministic cited memo")
    memo = d.memo
    vm = to_vm(memo)
    accepted = memo.source == "llm"
    report = memo.report if accepted else getattr(memo, "rejected_draft", None)
    notes = list(d.notes)
    if memo.fallback_reason and d.status not in ("unavailable",):
        notes.append(f"Fallback: {memo.fallback_reason}")
    return ClaudeDraftVM(
        status=d.status,
        headline=d.headline,
        memo=vm,
        shown="Claude-assembled memo (claim-checked)" if accepted else "Deterministic cited memo",
        claims_checked=getattr(report, "claims_checked", None) if report is not None else None,
        violations=_violations(report) if not accepted and report is not None else [],
        notes=notes,
    )


@dataclass
class RedTeamVM:
    title: str
    passed: bool
    lines: list[str] = field(default_factory=list)
    violations: list[ViolationVM] = field(default_factory=list)


def red_team(snapshot: Any) -> tuple[list[RedTeamVM], str | None]:
    """Run the SYNTHETIC conflict-resolution and injection inputs live through ``produce_memo``."""
    try:
        from lotline.engine import screen
        from lotline.memo import synthetic as syn
        from lotline.memo.pipeline import produce_memo
        from lotline.memo.text import ngrams
    except Exception as exc:  # noqa: BLE001
        return [], f"{type(exc).__name__}: {exc}"
    out: list[RedTeamVM] = []
    try:
        r = screen(syn.hero_context(snapshot, "centre_10s5"))
        memo = produce_memo(r, syn.conflict_resolution_draft(r))
        rej = memo.rejected_draft
        ok = memo.source == "deterministic" and rej is not None and bool(memo.report and memo.report.ok)
        out.append(RedTeamVM(
            f"Conflict-resolution draft ({syn.SYNTHETIC_LABEL})", ok,
            [f"Draft: “{syn.CONFLICT_DRAFT_TEXT}”",
             "Result: " + ("rejected; deterministic memo substituted" if ok else "NOT rejected"),
             f"Substituted memo: {memo.report.summary() if memo.report else 'unchecked'}"],
            _violations(rej)))
    except Exception as exc:  # noqa: BLE001
        out.append(RedTeamVM("Conflict-resolution draft", False, [f"raised {type(exc).__name__}: {exc}"]))
    try:
        inj = syn.injection_case(snapshot)
        unchanged = syn.decision_view(inj.baseline) == syn.decision_view(inj.injected)
        viols: list[ViolationVM] = []
        all_rejected = True
        for draft in inj.drafts:
            m = produce_memo(inj.injected, list(draft))
            all_rejected &= m.source == "deterministic" and m.rejected_draft is not None
            viols += _violations(m.rejected_draft)
        accepted = produce_memo(inj.injected, None)
        clean = not (ngrams(syn.INJECTION_TEXT, 4) & ngrams(accepted.text, 4)) \
            and "buildable" not in accepted.text.lower()
        ok = unchanged and all_rejected and clean and bool(accepted.report and accepted.report.ok)
        out.append(RedTeamVM(
            f"Injection in violation text ({syn.SYNTHETIC_LABEL})", ok,
            [f"Untrusted text: “{syn.INJECTION_TEXT}”",
             f"Engine result unchanged: {'yes' if unchanged else 'NO'}",
             f"Injection drafts rejected: {'all ' + str(len(inj.drafts)) if all_rejected else 'NOT all'}",
             f"Accepted memo contains no injected instruction: {'yes' if clean else 'NO'}"],
            viols))
    except Exception as exc:  # noqa: BLE001
        out.append(RedTeamVM("Injection in violation text", False, [f"raised {type(exc).__name__}: {exc}"]))
    return out, None


def cases_summary(outcome: Any) -> str | None:
    """``summary(run_cases())``, e.g. '10/10 cases passed'."""
    try:
        from lotline.memo.eval import summary
        return summary(outcome)
    except Exception:  # noqa: BLE001
        return None
