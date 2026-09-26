"""Pipeline: accept only clean drafts; any model or parse failure yields the deterministic memo."""

from __future__ import annotations

import json

import pytest

from lotline.engine import screen
from lotline.loaders import context_for
from lotline.memo import synthetic as syn
from lotline.memo.pipeline import (
    LLMOutputError,
    approved_claim_catalog,
    llm_payload,
    parse_llm_json,
    produce_memo,
    produce_memo_from_llm,
    produce_memo_from_text,
    required_engine_claims,
)
from lotline.models import ScreeningResult, Snapshot, derived_fact_id
from tests.conftest import BENEZET, CENTRE_10S5


@pytest.fixture(scope="module")
def benezet(snapshot: Snapshot) -> ScreeningResult:
    return screen(context_for(snapshot, BENEZET))


@pytest.fixture(scope="module")
def centre(snapshot: Snapshot) -> ScreeningResult:
    return screen(context_for(snapshot, CENTRE_10S5))


def good_json(r: ScreeningResult) -> str:
    return json.dumps({"claim_ids": list(approved_claim_catalog(r))[:6]})


BAD_TEXTS = [
    "", "   ", "not json", "[", '[{"text": "x", "fact_ids": ["a"], "claim_type": "fact"}', "[]", "{}",
    '{"claims": []}', '[{"fact_ids": [], "claim_type": "fact"}]', '[{"text": "x", "claim_type": "fact"}]',
    '[{"text": "x", "fact_ids": "a:b:c", "claim_type": "fact"}]', '[{"text": "x", "fact_ids": [1], "claim_type": "fact"}]',
    '[{"text": "x", "fact_ids": [], "claim_type": "opinion"}]', '["just a string"]', "null",
]


@pytest.mark.parametrize("text", BAD_TEXTS)
def test_parse_rejects_malformed_empty_truncated(text) -> None:
    with pytest.raises(LLMOutputError):
        parse_llm_json(text, benezet)


@pytest.mark.parametrize("text", BAD_TEXTS)
def test_malformed_output_falls_back(benezet, text) -> None:
    memo = produce_memo_from_text(benezet, text)
    assert memo.source == "deterministic" and memo.report is not None and memo.report.ok
    assert memo.fallback_reason and "model output unusable" in memo.fallback_reason


def test_parse_resolves_only_engine_approved_atoms(benezet) -> None:
    claims = parse_llm_json(good_json(benezet), benezet)
    assert len(claims) == 6 and all(c.author == "engine" for c in claims)
    assert len(parse_llm_json("```json\n" + good_json(benezet) + "\n```", benezet)) == 6


def test_clean_draft_accepted_with_required_engine_claims(benezet) -> None:
    memo = produce_memo_from_text(benezet, good_json(benezet))
    assert memo.source == "llm" and memo.report.ok and memo.rejected_draft is None
    assert any(c.author == "engine" and c.text.startswith("Decision support only") for c in memo.claims)


def test_conflict_resolution_fixture_rejected(centre) -> None:
    memo = produce_memo(centre, syn.conflict_resolution_draft(centre))
    assert memo.source == "deterministic"
    rules = memo.rejected_draft.by_rule()
    assert "NO_SOURCE_SELECTION" in rules and "FORBIDDEN_WORDS" in rules
    assert memo.report.ok
    assert syn.CONFLICT_DRAFT_TEXT not in memo.text


def test_timeout_and_errors_fall_back(benezet) -> None:
    def timeout(_payload):
        raise TimeoutError("model timed out")

    def boom(_payload):
        raise ConnectionError("network down")

    for fn in (timeout, boom, lambda _p: None, lambda _p: 42):
        memo = produce_memo_from_llm(benezet, fn)
        assert memo.source == "deterministic" and memo.report.ok


def test_no_llm_configured_gives_deterministic(benezet) -> None:
    memo = produce_memo_from_llm(benezet, None)
    assert memo.source == "deterministic" and memo.fallback_reason == "no model draft"


def test_llm_output_accepted_when_clean(benezet) -> None:
    memo = produce_memo_from_llm(benezet, lambda payload: good_json(benezet))
    assert memo.source == "llm"


@pytest.mark.parametrize("claim", [
    {"text": "The parcel is undermined.", "field": "undermined", "claim_type": "fact"},
    {"text": "Single-unit housing is prohibited in this district.", "field": "single_unit_permission",
     "claim_type": "fact"},
    {"text": "The parcel has utility service.", "field": "screen_outcome", "claim_type": "fact"},
    {"text": "Next check: the Mayor must inspect the site (owner: Mayor).", "field": "screen_outcome",
     "claim_type": "next_check"},
])
def test_free_text_false_claims_cannot_enter_model_pipeline(benezet, claim) -> None:
    fact = next(f for f in llm_payload(benezet)["facts"] if f["field"] == claim["field"])
    raw = json.dumps({"claims": [{"text": claim["text"], "fact_ids": [fact["id"]],
                                  "claim_type": claim["claim_type"]}]})
    memo = produce_memo_from_text(benezet, raw)
    assert memo.source == "deterministic"
    assert "expected claim_ids" in (memo.fallback_reason or "")
    assert claim["text"] not in memo.text


def test_unknown_duplicate_and_cross_parcel_claim_ids_fail_closed(benezet, centre) -> None:
    valid = list(approved_claim_catalog(benezet))[:6]
    bad_payloads = [
        {"claim_ids": [f"claim_unknown_{i}" for i in range(6)]},
        {"claim_ids": [valid[0]] * 6},
        {"claim_ids": list(approved_claim_catalog(centre))[:6]},
    ]
    for payload in bad_payloads:
        memo = produce_memo_from_text(benezet, json.dumps(payload))
        assert memo.source == "deterministic" and memo.report and memo.report.ok


def test_mandatory_adverse_and_action_claims_cannot_be_omitted(centre) -> None:
    catalog = approved_claim_catalog(centre)
    mandatory = required_engine_claims(centre, [])
    mandatory_text = {c.text for c in mandatory}
    optional_ids = [cid for cid, c in catalog.items() if c.text not in mandatory_text]
    selected = (optional_ids + list(catalog))[:6]
    memo = produce_memo_from_text(centre, json.dumps({"claim_ids": selected}))
    assert memo.source == "llm" and mandatory_text <= {c.text for c in memo.claims}
    assert any(c.claim_type == "conflict_summary" for c in memo.claims)
    assert any("withheld" in c.text.lower() for c in memo.claims)


def test_every_snapshot_result_has_selectable_catalog(snapshot: Snapshot) -> None:
    for pin in snapshot.treasury:
        result = screen(context_for(snapshot, pin))
        catalog = approved_claim_catalog(result)
        assert len(catalog) >= 6
        assert len(catalog) == len(set(catalog))


def test_payload_contains_only_approved_facts_and_delimits_untrusted(snapshot: Snapshot) -> None:
    inj = syn.injection_case(snapshot)
    payload = llm_payload(inj.injected)
    ids = {f["id"] for f in payload["facts"]}
    assert all(i.startswith((inj.injected.pin, "RULE:")) for i in ids)
    assert len(payload["approved_claims"]) >= 6
    untrusted = [f for f in payload["facts"] if f["evidence_class"] == "untrusted_text"]
    assert untrusted and all(str(f["value"]).startswith("<untrusted_source_text>") for f in untrusted)
    json.dumps(payload)  # serializable


def test_stale_fixture_warning_and_no_will_be_sold(snapshot: Snapshot) -> None:
    r = screen(syn.stale_context(snapshot))
    assert any("sale status may have changed by payment or court order" in w for w in r.warnings)
    for draft in syn.stale_drafts(r):
        memo = produce_memo(r, draft)
        assert memo.source == "deterministic" and "FORBIDDEN_WORDS" in memo.rejected_draft.by_rule()
        assert "sale status may have changed by payment or court order" in memo.text
        assert "will be sold" not in memo.text.lower()
