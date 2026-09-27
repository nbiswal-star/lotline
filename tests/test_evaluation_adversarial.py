"""Experiments 6 and 7: naive-comparator ablation and adversarial language fidelity (no network)."""

from __future__ import annotations

import json

import pytest

from evaluation import ablation
from evaluation import adversarial as adv
from evaluation.common import named_context
from lotline.engine import screen
from lotline.memo import llm
from lotline.memo.claims import Claim
from lotline.memo.pipeline import produce_memo
from lotline.models import rule_fact_id

HEROES = ("benezet", "centre_10s5", "michigan_15s66")


@pytest.fixture(scope="module")
def env():
    ctxs = [named_context(k) for k in (*HEROES, "wylie", "walcott")]
    return adv._env(ctxs)


# --------------------------------------------------------------------------
# Experiment 7: every adversarial case falls back or is semantically faithful
# --------------------------------------------------------------------------


@pytest.mark.parametrize("key", HEROES)
@pytest.mark.parametrize("case", adv.CASES, ids=lambda c: c.id)
def test_runtime_case_falls_back_or_is_faithful(key: str, case: adv.Case, env) -> None:
    out = adv.run_case(case, named_context(key), env)
    assert out.engine_unchanged, f"{case.id}: engine ScreeningResult changed"
    assert not (out.accepted and out.faults), f"{case.id}: SEMANTIC FALSE ACCEPT {out.faults}"
    assert out.accepted == (case.expect == "accept"), f"{case.id}: status {out.status}"
    assert not out.faults, out.faults  # fallback memos pass their own check too


@pytest.mark.parametrize("key", ("benezet", "centre_10s5"))
def test_cache_cases_fail_closed(key: str, env) -> None:
    rows = adv.cache_cases(named_context(key), env)
    assert {r.case for r in rows} == set(adv.CACHE_EXPECT)
    for r in rows:
        assert r.engine_unchanged
        assert not (r.accepted and r.faults), (r.case, r.faults)
        assert r.accepted == (adv.CACHE_EXPECT[r.case] == "accept"), (r.case, r.status)


def test_injection_in_untrusted_text_cannot_move_engine_or_memo() -> None:
    data = adv.evaluate(pins=[named_context("benezet").pin])
    for row in data["inj_rows"]:
        assert row["decisions_unchanged"] and row["payload_tagged_untrusted"]
        assert row["valid_selection_accepted"] and not row["faults"]
        assert row["injection_selection_fell_back"]


@pytest.mark.parametrize("key", HEROES)
def test_oracle_has_power(key: str) -> None:
    from lotline.memo.claims import Memo
    from lotline.memo.deterministic import deterministic_memo

    r = screen(named_context(key))
    memo = deterministic_memo(r)
    assert adv.semantic_faults(memo, r) == []  # negative control
    no_status = Memo(r.pin, [c for c in memo.claims if c.claim_type != "status"], "llm")
    assert "engine outcome missing" in adv.semantic_faults(no_status, r)
    spiked = Memo(r.pin, [*memo.claims, Claim(adv.PERMISSION_INVERSION, (), "fact", "engine")], "llm")
    assert any("non-engine" in f or "payload" in f for f in adv.semantic_faults(spiked, r))


def test_llm_payload_is_id_selection_only() -> None:
    r = screen(named_context("centre_10s5"))
    kwargs = llm.request_kwargs(r)
    schema = kwargs["output_config"]["format"]["schema"]
    assert set(schema["properties"]) == {"claim_ids"}
    assert schema["properties"]["claim_ids"]["minItems"] == 6 and schema["properties"]["claim_ids"]["maxItems"] == 12


# --------------------------------------------------------------------------
# Recorded findings (not runtime-reachable / latent). xfail documents the gap without
# hiding it; if a later fix closes the gap the test starts passing (strict=False).
# --------------------------------------------------------------------------


@pytest.mark.xfail(strict=False, reason="checker-layer gap: LLM-authored permission inversion prose is not "
                   "rejected by the checker; unreachable at runtime because parse_llm_json only returns "
                   "engine-authored catalog claims")
def test_checker_rejects_permission_inversion_prose() -> None:
    ctx = named_context("benezet")
    r = screen(ctx)
    d = ctx.rule.district
    claim = Claim(f"Two-unit housing is permitted in {d}.", (rule_fact_id(d, "two_unit_permission"),), "fact", "llm")
    assert produce_memo(r, [claim]).source == "deterministic"


# Regression for a gap this experiment found: free text in a date field (pli_latest_event) used to be
# quoted into an approved claim. lotline/facts.py now classes non-ISO values in date fields as
# untrusted_text, which the memo never quotes and the model cannot select.
def test_raw_source_text_cannot_reach_accepted_memo() -> None:
    rows = adv.raw_field_probe(named_context("benezet"), {})
    assert rows and all(r["engine_decisions_unchanged"] for r in rows)
    assert not any(r["llm_accepted"] and r["faults"] for r in rows)


# --------------------------------------------------------------------------
# Experiment 6: naive comparators diverge from LotLine where expected
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def comparison():
    return ablation.compare()


def _row(comparison, short: str):
    return next(r for r in comparison["rows"] if f"({short})" in r["parcel"])


def test_naive_policies_diverge_on_centre_10s5(comparison) -> None:
    row = _row(comparison, "10-S-5")
    base = row["lotline"]
    assert base["outcome"] == "DEFER_RECORDS" and not base["numeric"]
    assert base["components"]["dimensional"] == "withheld"
    # N1: one area source -> the material area conflict disappears and dimensional becomes a known 0.
    n1 = row["N1"]
    assert "conflict not detected: material:lot_area" in n1["divergences"]
    assert n1["view"]["components"]["dimensional"] == "0"
    # N3: condemned case ignored -> critical conflict gone; the lot is no longer "Not scorable".
    n3 = row["N3"]
    assert "conflict not detected: critical:current_condition" in n3["divergences"]
    assert n3["view"]["score"].startswith("abstain (Partial")
    # N2 keeps critical abstention, N4 has no corner state here: neither advances.
    assert not row["N2"]["view"]["advance"] and not row["N4"]["divergences"]


def test_n3_would_advance_two_lots_if_condition_records_are_ignored(comparison) -> None:
    # Completing RIV-RM dimensions made Walcott otherwise scorable; the ablation
    # now exposes the same unsafe effect there as on the second Centre lot.
    for short in ("10-R-108", "42-D-39"):
        row = _row(comparison, short)
        assert not row["lotline"]["advance"] and row["N3"]["view"]["advance"]
    assert comparison["counts"]["N3"]["naive_advances_lotline_not"] == 2


def test_n4_collapses_corner_ranges(comparison) -> None:
    for short in ("131-N-31", "15-S-66", "50-K-227"):
        row = _row(comparison, short)
        assert "-" in row["lotline"]["score"] and "range collapsed to a single number" in row["N4"]["divergences"]


def test_n2_unknown_as_zero_advances_synthetic_unknowns_lotline_never_does(comparison) -> None:
    for key, c in comparison["synthetic_counts"].items():
        assert c["lotline_advance"] == 0, key
        assert c["n2_advances_lotline_not"] > 0, key
    assert comparison["counts"]["N2"]["naive_advances_lotline_not"] == 0  # real cohort: no flips


def test_ablation_section_assertions_hold_and_serialize() -> None:
    section = ablation.run()
    assert section.assertions and all(a["passed"] for a in section.assertions)
    json.dumps(section.data)
    assert "What this does and does not show" in section.markdown
