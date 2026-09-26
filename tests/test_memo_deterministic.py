"""Deterministic cited memo: zero checker violations for every parcel in the snapshot."""

from __future__ import annotations

import re

import pytest

from lotline.engine import screen
from lotline.loaders import context_for
from lotline.memo import deterministic as det
from lotline.memo.checker import check
from lotline.memo.outputs import fact_universe
from lotline.models import Outcome, Snapshot
from tests.conftest import BENEZET, CENTRE_10S5, GARFIELD


@pytest.fixture(scope="module")
def results(snapshot: Snapshot):
    return {pin: screen(context_for(snapshot, pin)) for pin in snapshot.treasury}


def test_every_parcel_memo_passes_checker(results, snapshot: Snapshot) -> None:
    failures = {}
    for pin, r in results.items():
        rep = check(det.deterministic_memo(r).claims, r)
        if not rep.ok:
            failures[pin] = [(v.rule, v.message) for v in rep.violations]
    assert not failures
    assert len(results) == 96


def test_all_prepared_parcels_screened_and_clean(results, snapshot: Snapshot) -> None:
    assert len(snapshot.parcels) == 15
    for pin in snapshot.parcels:
        memo = det.deterministic_memo(results[pin])
        assert check(memo.claims, results[pin]).ok
        assert memo.source == "deterministic" and memo.claims


def test_every_non_caveat_claim_cites_existing_facts(results) -> None:
    for r in results.values():
        u = fact_universe(r)
        for c in det.deterministic_memo(r).claims:
            assert c.author == "engine"
            if c.claim_type != "caveat":
                assert c.fact_ids, c
            assert all(f in u for f in c.fact_ids), c


def test_required_caveats_on_screened_parcels(results) -> None:
    for r in results.values():
        texts = [c.text for c in det.deterministic_memo(r).claims]
        assert det.DECISION_SUPPORT in texts
        if r.outcome not in (Outcome.OUT_OF_UNIVERSE, Outcome.STRUCTURE):
            for required in (det.ENVIRONMENT_CAVEAT, det.SETBACK_CAVEAT, det.MARKET_CAVEAT):
                assert required in texts
            assert "no overlap in the checked screening layers" in " ".join(texts)
            assert "market demand and appraisal not evaluated" in " ".join(texts).lower()


def test_conflict_summaries_cite_every_group_fact(results) -> None:
    for r in results.values():
        claims = det.deterministic_memo(r).claims
        for conflict in r.conflicts:
            s = [c for c in claims if c.claim_type == "conflict_summary" and c.text == conflict.summary]
            assert len(s) == 1 and set(conflict.fact_ids) <= set(s[0].fact_ids)


def test_every_next_check_has_owner_in_memo(results) -> None:
    for r in results.values():
        text = det.deterministic_memo(r).text
        for nc in r.next_checks:
            assert f"Next check: {nc.check} (owner: {nc.owner})." in text


def test_engine_display_strings_verbatim(results) -> None:
    for r in results.values():
        text = det.deterministic_memo(r).text
        assert r.outcome.value in text
        if r.outcome not in (Outcome.OUT_OF_UNIVERSE, Outcome.STRUCTURE) and r.ease:
            assert r.ease.display in text


def test_routing_only_memos_are_route_only(results) -> None:
    routed = [r for r in results.values() if r.outcome in (Outcome.OUT_OF_UNIVERSE, Outcome.STRUCTURE)]
    assert routed
    for r in routed:
        memo = det.deterministic_memo(r)
        types = {c.claim_type for c in memo.claims}
        assert "score" not in types and "conflict_summary" not in types
        assert not re.search(r"Development Ease|of 6\b", memo.text)


def test_no_forbidden_language_anywhere(results) -> None:
    for r in results.values():
        low = det.deterministic_memo(r).text.lower()
        for bad in ("buildable", "environmentally clear", "will be sold", "the lot is vacant", "was demolished"):
            assert bad not in low


def test_centre_memo_refuses_certainty(results) -> None:
    r = results[CENTRE_10S5]
    text = det.deterministic_memo(r).text
    assert "Current site condition is unverified." in text
    assert "Not scorable" in text
    assert not re.search(r"\b\d\s*(?:-\s*\d\s*)?of 6\b", text)
    assert not re.search(r"\bconform(s|ing)\b|\bsubstandard\b", text, re.I)


def test_benezet_memo_shows_range_and_coverage(results) -> None:
    text = det.deterministic_memo(results[BENEZET]).text
    assert "5-6 of 6" in text and "use 2, dimensional 1-2, environment 2" in text
    assert "Evidence coverage: 5/5" in text
    assert "if corner" in text


def test_garfield_is_route_only(results) -> None:
    text = det.deterministic_memo(results[GARFIELD]).text
    assert "not in the City advertisement dated 2026-09-16" in text


def test_unknown_pin_memo_has_no_facts() -> None:
    memo = det.unknown_pin_memo("9999Z99999", "2026-09-24")
    assert memo.pin == "" and all(not c.fact_ids for c in memo.claims)
    assert "PIN not found in snapshot dated 2026-09-24" in memo.text


def test_engine_claim_texts_cover_memo(results) -> None:
    r = results[CENTRE_10S5]
    texts = det.engine_claim_texts(r)
    assert all(c.text in texts for c in det.deterministic_memo(r).claims)
