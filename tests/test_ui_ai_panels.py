"""AppTest smoke for the AI reader panels, cost worksheet, freshness check and map.

Each AI panel is exercised with a fake ``lotline.ai.*`` module injected into
``sys.modules`` (no network, no key), in both the unavailable and the verified
state, plus the module-missing state where the panel must hide.
"""

from __future__ import annotations

import json
import sys
import types
from dataclasses import dataclass, field

import pytest
from streamlit.testing.v1 import AppTest

from lotline import refresh
from lotline.ui import ai_panels
from tests.conftest import BENEZET, CENTRE_10S5, REPO_ROOT

APP = str(REPO_ROOT / "app.py")
QUOTE = "STRUCTURE CONDEMNED - UNSAFE, OPEN TO TRESPASS"


def _texts(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [e.value for e in at.error] + [w.value for w in at.warning]
    parts += [i.value for i in at.info] + [c.value for c in at.caption]
    parts += [str(getattr(x, "label", "")) for x in at.expander]
    return "\n".join(str(p) for p in parts)


@dataclass(frozen=True)
class FakeItem:
    record_id: str
    source_id: str
    record_date: str
    field: str
    quote: str
    indicates: str
    relevance: str
    currency: str = "latest"
    corroboration: str | None = "no demolition permit on file after this record"


@dataclass(frozen=True)
class FakeDigest:
    pin: str
    status: str
    items: tuple = ()
    rejected: tuple = ()
    record_count: int = 0
    reason: str | None = None
    model: str | None = "claude-opus-5"
    created_at: str = "2026-09-27T04:00:00Z"


def _evidence_module(status_when_cached: str) -> types.ModuleType:
    mod = types.ModuleType("lotline.ai.evidence")

    def evidence_digest(pin, snapshot, *, client=None, use_cache=True, save_cache=True):
        if status_when_cached == "cached_verified":
            return FakeDigest(pin, "cached_verified", (FakeItem("CND-2024-001", "condemned_properties",
                                                               "2024-05-01", "violation_description", QUOTE,
                                                               "structure present", "current condition"),),
                              ("dropped paraphrase",), record_count=3)
        return FakeDigest(pin, "unavailable", reason="no API key configured")

    mod.evidence_digest = evidence_digest
    mod.digest_lines = lambda d: [f"{i.record_id}: {i.quote}" for i in d.items]
    mod.resolver_note = lambda d: ("Records disagree on current condition; a PLI site check resolves it."
                                   if d.items else None)
    return mod


@dataclass(frozen=True)
class FakeSentence:
    text: str
    fact_ids: tuple = ()
    code_refs: tuple = ()


@dataclass(frozen=True)
class FakeAnswer:
    question: str
    status: str
    sentences: tuple = ()
    violations: tuple = ()
    reason: str | None = None
    model: str | None = None
    frame: str | None = None


def _ask_module(status: str) -> types.ModuleType:
    mod = types.ModuleType("lotline.ai.ask")
    mod.SUGGESTED_QUESTIONS = ("Why is this lot deferred?", "What should I check first?")

    def ask(question, result, *, client=None):
        if status == "answered":
            return FakeAnswer(question, "answered", (FakeSentence(
                "The outcome is " + result.outcome.value + ".", (f"{result.pin}:screen_outcome:engine",),
                ("921.04.A",)),), frame="why_deferred")
        if status == "rejected":
            return FakeAnswer(question, "rejected", violations=("uncited_sentence",))
        if status == "declined":
            return FakeAnswer(question, "declined", reason="investment advice is outside decision support",
                              frame="investment_advice")
        return FakeAnswer(question, "unavailable", reason="no API key configured")

    mod.ask = ask
    return mod


@dataclass(frozen=True)
class FakeRelief:
    kind: str
    description: str
    outcome: str
    quote: str


@dataclass(frozen=True)
class FakeCard:
    slug: str
    case_number: str
    address: str
    district: str
    decision_date: str
    lot_description: str
    reliefs: tuple
    rationale_quote: str
    source_url: str
    verified: bool = True
    extracted_by: str = "claude"
    rejected_fields: tuple = ()


@dataclass(frozen=True)
class FakePath:
    trigger: str
    path: str
    code_ref: str
    code_quote: str
    precedents: tuple = ()
    counts: tuple = (2, 3)


def _precedents_module() -> types.ModuleType:
    mod = types.ModuleType("lotline.ai.precedents")
    card = FakeCard("zba-1", "ZBA 123 of 2024", "100 Example St", "R1D-L", "2024-06-01", "undersized lot",
                    (FakeRelief("dimensional variance", "lot size", "Granted", "the lot is a lot of record"),),
                    "hardship arises from the lot's size", "https://example.org/zba-123.pdf")
    mod.load_cards = lambda: [card]
    mod.precedents_for = lambda result, *, cards=None: [(card, "same district family, same relief type")]
    mod.relief_paths = lambda result: [FakePath("Lot area below district minimum", "Lot of record",
                                                "§921.04.A", "a lot of record may be used", (card,))]
    return mod


@pytest.fixture
def no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    import lotline.ai.client as client
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(client, "credentials_available", lambda: False)


def _packet(pin_button: str | None = None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    at.radio(key="view").set_value("Parcel packet").run()
    if pin_button:
        at.button(key=pin_button).click().run()
    assert not at.exception, at.exception
    return at


def test_panels_hidden_when_modules_missing(monkeypatch, no_key) -> None:
    for name in ("evidence", "ask", "precedents"):
        monkeypatch.setitem(sys.modules, f"lotline.ai.{name}", None)
    at = _packet("hero_centre")
    body = _texts(at)
    assert "AI record reader" not in body and "Ask LotLine" not in body
    assert "variance precedents" not in body.lower()
    assert "Pre-development cost worksheet" in body  # the rest of the packet is intact


def test_evidence_unavailable_without_key(monkeypatch, no_key) -> None:
    monkeypatch.setitem(sys.modules, "lotline.ai.evidence", _evidence_module("unavailable"))
    at = _packet("hero_centre")
    assert "AI record reader" in _texts(at)
    assert ai_panels.HUMAN_RESOLVER in _texts(at)
    at.button(key=f"btn_evidence_{CENTRE_10S5}").click().run()
    assert not at.exception, at.exception
    assert ai_panels.UNAVAILABLE_READER in _texts(at)


def test_cached_evidence_renders_items(monkeypatch, no_key) -> None:
    monkeypatch.setitem(sys.modules, "lotline.ai.evidence", _evidence_module("cached_verified"))
    at = _packet("hero_centre")
    body = _texts(at)
    assert QUOTE in body and "CND-2024-001" in body
    assert "quote verified against source text" in body
    assert "Claude read 3 records; 1 item verified; 1 rejected" in body
    assert "cached, re-verified now" in body
    assert "latest record" in body and "Permit corroboration" in body
    assert "a PLI site check resolves it" in body
    # Benezet has no conflict: the reader sits in the Policy tile area, still rendered.
    at.button(key="hero_benezet").click().run()
    assert not at.exception, at.exception
    assert QUOTE in _texts(at)


@pytest.mark.parametrize("status,expect", [
    ("answered", "every sentence verified"),
    ("rejected", "failed verification (rules: uncited_sentence); showing the engine packet instead"),
    ("declined", "investment advice is outside decision support"),
    ("unavailable", "Ask LotLine unavailable"),
])
def test_ask_states(monkeypatch, no_key, status, expect) -> None:
    monkeypatch.setitem(sys.modules, "lotline.ai.ask", _ask_module(status))
    at = _packet()
    assert "Ask LotLine" in _texts(at)
    at.button(key=f"askchip_{BENEZET}_0").click().run()
    assert not at.exception, at.exception
    body = _texts(at)
    assert expect in body
    if status == "answered":
        assert f"{BENEZET}:screen_outcome:engine" in body and "921.04.A" in body
        assert "Why deferred" in body
    if status == "declined":
        assert "Declined: investment advice" in body


def test_precedents_in_zoning_tile(monkeypatch, no_key) -> None:
    monkeypatch.setitem(sys.modules, "lotline.ai.precedents", _precedents_module())
    at = _packet("hero_centre")
    body = _texts(at)
    assert "ZBA 123 of 2024" in body and "quotes verified" in body
    assert ai_panels.PRECEDENT_NOTE in body and ai_panels.RELIEF_BANNER in body
    assert "1 granted / 1 decided" in body and "2 granted / 3 decided" in body
    assert "a lot of record may be used" in body


def test_cost_worksheet_and_tickets() -> None:
    at = _packet()
    body = _texts(at)
    assert "Pre-development cost worksheet" in body
    assert "not an appraisal, bid recommendation or financial advice" in body
    assert "amount unknown: title search required" in body
    assert at.number_input(key=f"cost_{BENEZET}_quiet_title").value == 2000
    assert at.number_input(key=f"cost_{BENEZET}_survey").value is None
    at.number_input(key=f"cost_{BENEZET}_survey").set_value(1500.0).run()
    assert not at.exception, at.exception
    assert "from 3 filled rows" in _texts(at)
    assert "Internal task ticket (not sent anywhere)" in _texts(at)
    at.button(key="hero_centre").click().run()
    assert "Resolve records before estimating" in " ".join(e.value for e in at.error)
    # Critical parcels still hide component values.
    assert "Component values are not shown because a critical conflict" in _texts(at)


def test_freshness_panel(monkeypatch) -> None:
    def offline(url, body, timeout):
        raise OSError("offline")

    monkeypatch.setattr(refresh, "_urllib_fetch", offline)
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    at.radio(key="view").set_value("Integrity").run()
    at.button(key="btn_refresh").click().run()
    assert not at.exception, at.exception
    assert "Can't reach WPRDC; snapshot unchanged." in _texts(at)

    from lotline.loaders import load_snapshot
    snap = load_snapshot()
    recs = [{"pin": p, "treasury_sale_date": t.sale_date, "total_tax_due": t.total_tax_due + (1 if i == 0 else 0),
             "demo_cost_due": t.demo_cost_due} for i, (p, t) in enumerate(snap.treasury.items())]
    monkeypatch.setattr(refresh, "_urllib_fetch",
                        lambda u, b, t: json.dumps({"success": True, "result": {"records": recs}}).encode())
    at.button(key="btn_refresh").click().run()
    assert not at.exception, at.exception
    assert "vs live now: 1 change" in _texts(at)


def test_pipeline_map_and_header(no_key) -> None:
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    assert not at.exception, at.exception
    assert at.get("deck_gl_json_chart"), "parcel map missing"
    body = _texts(at)
    assert ("Claude reads the record. Rules decide. "
            "Code verifies source identity and every displayed quote.") in body
    assert "Everything except the AI readers works offline" in body
    assert "All 96 open-data records" in body
    for bad in ("buildable", "environmentally clear", "will be sold"):
        assert bad not in body.lower()
