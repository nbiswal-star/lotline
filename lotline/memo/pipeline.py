"""Memo pipeline: check an LLM draft, accept it only if clean, else fall back.

Seam for M5 (the Anthropic call): build the request with ``llm_payload``,
send it however you like, and hand the raw text (or the exception) to
``produce_memo_from_llm``. Any failure (timeout, network, malformed or
truncated JSON, a single checker violation) yields the deterministic memo.
"""

from __future__ import annotations

import json
import hashlib
from collections.abc import Callable, Iterable

from lotline.memo.allowlist import DEFAULT_ALLOWLIST, SectionAllowlist
from lotline.memo.checker import check
from lotline.memo.claims import Claim, Memo
from lotline.memo.deterministic import (
    decision_support_claim,
    deterministic_memo,
    warning_claims,
)
from lotline.memo.outputs import fact_universe
from lotline.models import Fact, ScreeningResult


class LLMOutputError(ValueError):
    """The model output could not be resolved to approved claims."""


MIN_SELECTED_CLAIMS = 6
MAX_SELECTED_CLAIMS = 12


def _claim_id(claim: Claim) -> str:
    raw = json.dumps([claim.text, claim.claim_type, list(claim.fact_ids)], separators=(",", ":"))
    return "claim_" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def approved_claim_catalog(result: ScreeningResult) -> dict[str, Claim]:
    """Stable, engine-authored atoms Claude may select and order; no free text is accepted."""
    out: dict[str, Claim] = {}
    for claim in deterministic_memo(result).claims:
        cid = _claim_id(claim)
        if cid in out and out[cid] != claim:  # pragma: no cover - cryptographic collision guard
            raise RuntimeError("approved claim id collision")
        out[cid] = claim
    return out


def parse_llm_json(text: str, result: ScreeningResult) -> list[Claim]:
    """Resolve ``{"claim_ids": [...]}`` against this result's approved claim catalog.

    Claude never supplies prose, claim types, citations, or authorship. Unknown or
    duplicate ids and selections outside the 6–12 claim contract fail closed.
    """
    if not isinstance(text, str) or not text.strip():
        raise LLMOutputError("empty model output")
    body = text.strip()
    if body.startswith("```"):
        body = body.strip("`")
        body = body.split("\n", 1)[1] if "\n" in body else ""
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise LLMOutputError(f"malformed or truncated JSON: {exc}") from exc
    ids = data.get("claim_ids") if isinstance(data, dict) else None
    if not isinstance(ids, list) or not all(isinstance(cid, str) for cid in ids):
        raise LLMOutputError("expected claim_ids as a list of strings")
    if not MIN_SELECTED_CLAIMS <= len(ids) <= MAX_SELECTED_CLAIMS:
        raise LLMOutputError(f"expected {MIN_SELECTED_CLAIMS} to {MAX_SELECTED_CLAIMS} claim_ids")
    if len(ids) != len(set(ids)):
        raise LLMOutputError("claim_ids must be unique")
    catalog = approved_claim_catalog(result)
    unknown = [cid for cid in ids if cid not in catalog]
    if unknown:
        raise LLMOutputError(f"unknown approved claim id: {unknown[0]}")
    return [catalog[cid] for cid in ids]


def required_engine_claims(result: ScreeningResult, draft: Iterable[Claim]) -> list[Claim]:
    """Mandatory engine claims that cannot be omitted by an AI selection."""
    draft = list(draft)
    present = {c.text for c in draft if c.author == "engine"}
    deterministic = deterministic_memo(result).claims
    mandatory: list[Claim] = [decision_support_claim(), *warning_claims(result)]

    # Outcome, score/coverage, and every conflict or withheld component remain visible
    # even if the model selects only favorable atoms.
    mandatory += [c for c in deterministic if c.claim_type in ("status", "score", "conflict_summary")]
    for component in (result.use, result.dimensional, result.environment):
        if component is not None and component.status == "withheld":
            mandatory += [c for c in deterministic
                          if any(fid.endswith(f":{component.name}_reason:engine") for fid in c.fact_ids)]

    # Principal barrier and first parcel-specific next check are required action anchors.
    barrier = next((c for c in deterministic if any(":barrier_1:engine" in fid for fid in c.fact_ids)), None)
    if barrier is not None:
        mandatory.append(barrier)
    from lotline.engine.checks import is_standard
    specific_index = next((i for i, nc in enumerate(result.next_checks) if not is_standard(nc)), None)
    if specific_index is None and result.next_checks:
        specific_index = 0
    if specific_index is not None:
        needle = f":next_check_{specific_index + 1}:engine"
        next_claim = next((c for c in deterministic if any(needle in fid for fid in c.fact_ids)), None)
        if next_claim is not None:
            mandatory.append(next_claim)

    out = [c for c in mandatory if c.text not in present]
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    unique: list[Claim] = []
    for claim in out:
        key = (claim.text, claim.claim_type, claim.fact_ids)
        if key not in seen:
            seen.add(key)
            unique.append(claim)
    return unique


def produce_memo(
    result: ScreeningResult,
    draft_claims: list[Claim] | None,
    *,
    allowlist: SectionAllowlist = DEFAULT_ALLOWLIST,
    catalog: Iterable[Fact] = (),
    insert_required: bool = True,
) -> Memo:
    """Accept a draft only if the checker finds zero violations; otherwise deterministic memo."""
    fallback = deterministic_memo(result)
    fallback.report = check(fallback.claims, result, allowlist=allowlist, catalog=catalog)
    if not draft_claims:
        fallback.fallback_reason = "no model draft"
        return fallback
    try:
        claims = list(draft_claims)
        if insert_required:
            claims = claims + required_engine_claims(result, claims)
        report = check(claims, result, allowlist=allowlist, catalog=catalog)
    except Exception as exc:  # noqa: BLE001 - any checker/draft failure falls back
        fallback.fallback_reason = f"draft could not be checked: {type(exc).__name__}: {exc}"
        return fallback
    if report.ok:
        return Memo(pin=result.pin, claims=claims, source="llm", report=report)
    fallback.rejected_draft = report
    fallback.fallback_reason = f"draft rejected: {report.summary()}"
    return fallback


def produce_memo_from_llm(
    result: ScreeningResult,
    llm_call: Callable[[dict], str] | None,
    **kw,
) -> Memo:
    """M5 seam: ``llm_call(payload) -> raw text``. Timeouts/errors/malformed JSON all fall back."""
    if llm_call is None:
        return produce_memo(result, None, **kw)
    try:
        raw = llm_call(llm_payload(result))
        draft = parse_llm_json(raw, result)
    except Exception as exc:  # noqa: BLE001 - model failure must never break the packet
        memo = produce_memo(result, None, **kw)
        memo.fallback_reason = f"model output unusable: {type(exc).__name__}: {exc}"
        return memo
    return produce_memo(result, draft, **kw)


def produce_memo_from_text(result: ScreeningResult, text: str, **kw) -> Memo:
    return produce_memo_from_llm(result, lambda _payload: text, **kw)


LLM_INSTRUCTIONS = (
    "Select and order 6 to 12 unique claim_id values from approved_claims. Return only "
    '{"claim_ids": [str, ...]}. Never invent or edit prose, citations, owners, outcomes, or scores. '
    "Prefer a balanced memo: status, score or abstention, adverse evidence, principal barrier, "
    "first next check, and caveat. Mandatory engine claims are inserted even if omitted."
)


def llm_payload(result: ScreeningResult) -> dict:
    """Approved engine claims plus supporting facts; Claude returns claim ids only."""
    facts = []
    for f in fact_universe(result).values():
        value = f.value
        if f.evidence_class == "untrusted_text":
            value = f"<untrusted_source_text>{value}</untrusted_source_text>"
        facts.append({"id": f.id, "field": f.field, "value": value if isinstance(value, (str, int, float, bool)) or value is None
                      else str(value), "unit": f.unit, "evidence_class": f.evidence_class,
                      "conflict_group": f.conflict_group})
    approved = approved_claim_catalog(result)
    required = {c.text for c in required_engine_claims(result, [])}
    return {
        "instructions": LLM_INSTRUCTIONS,
        "pin": result.pin,
        "outcome": result.outcome.value,
        "ease": result.ease.display if result.ease else None,
        "approved_claims": [
            {"claim_id": cid, "text": c.text, "claim_type": c.claim_type,
             "fact_ids": list(c.fact_ids), "required": c.text in required}
            for cid, c in approved.items()
        ],
        "facts": facts,
    }
