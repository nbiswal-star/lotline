"""Smoke tests: every view renders with no exceptions (streamlit AppTest, offline)."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from lotline.engine import screen
from lotline.loaders import context_for, load_snapshot, lookup_pin
from lotline.ui.viewmodels import short_pin
from tests.conftest import BENEZET, CENTRE_10S5, REPO_ROOT

MICHIGAN_15S66 = "0015S00066000000"

APP = str(REPO_ROOT / "app.py")
SNAP = load_snapshot()


def _result(pin: str):
    return screen(context_for(SNAP, pin))


def _texts(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [e.value for e in at.error] + [w.value for w in at.warning]
    parts += [i.value for i in at.info] + [c.value for c in at.caption]
    return "\n".join(str(p) for p in parts)


@pytest.fixture
def at() -> AppTest:
    app = AppTest.from_file(APP, default_timeout=60)
    app.run()
    assert not app.exception, app.exception
    return app


def test_pipeline_view(at: AppTest) -> None:
    body = _texts(at)
    assert "Decision support only" in body
    assert "PIN match 77/77" in body and "price check 77/77" in body
    assert "Triage, not ranking" in body
    assert len(at.dataframe) >= 1


def test_benezet_packet(at: AppTest) -> None:
    at.radio(key="view").set_value("Parcel packet").run()
    assert not at.exception, at.exception
    body = _texts(at)
    assert "Benezet St" in body
    r = _result(BENEZET)
    assert r.ease.display in body
    assert r.coverage_display in body
    for unknown in ("Contextual setbacks (Ch. 925) not evaluated",
                    "Screening layers only; not a geotechnical or flood determination",
                    "Utility capacity, laterals and legal access not established",
                    "Community plan alignment not evaluated"):
        assert unknown in body
    assert "Act 171 of 1984" in body
    assert "Before incurring costs" in body


def test_centre_packet(at: AppTest) -> None:
    at.radio(key="view").set_value("Parcel packet").run()
    at.button(key="hero_centre").click().run()
    assert not at.exception, at.exception
    r = _result(CENTRE_10S5)
    errors = " ".join(e.value for e in at.error)
    for c in r.conflicts:
        if c.level.value == "critical":
            assert c.summary in errors  # engine summary shown verbatim
        elif c.level.value == "material":
            assert any(c.summary in w.value for w in at.warning)
    assert r.ease.display in _texts(at)
    assert "Component values are not shown because a critical conflict" in _texts(at)
    assert "Multimodal cross-check" in _texts(at)
    assert "Image does not resolve the record evidence" in _texts(at)


def test_structure_routing_packet_has_visual_audit(at: AppTest) -> None:
    structure_pin = next(pin for pin, item in SNAP.treasury.items() if item.is_structure)
    at.radio(key="view").set_value("Parcel packet").run()
    at.text_input(key="pin_text").input(short_pin(structure_pin)).run()
    assert not at.exception, at.exception
    body = _texts(at)
    assert "routed record; not screened" in body
    assert "Multimodal cross-check" in body


def test_unknown_pin(at: AppTest) -> None:
    at.radio(key="view").set_value("Parcel packet").run()
    at.text_input(key="pin_text").input("9999-Z-12345").run()
    assert not at.exception, at.exception
    date = SNAP.manifest["wprdc_treasury_sales"].snapshot_as_of
    assert [e.value for e in at.error] == [f"PIN not found in snapshot dated {date}"]
    body = _texts(at)
    assert "Development Ease (0–6)" not in body and "Flags by area" not in body


def test_pin_search_opens_packet(at: AppTest) -> None:
    at.radio(key="view").set_value("Parcel packet").run()
    at.text_input(key="pin_text").input("15-S-66").run()
    assert not at.exception, at.exception
    assert _result(lookup_pin(SNAP, "15-S-66")).ease.display in _texts(at)


def test_compare_view(at: AppTest) -> None:
    at.radio(key="view").set_value("Compare").run()
    assert not at.exception, at.exception
    body = _texts(at)
    assert "What explains the difference" in body
    assert "Benezet St" in body and "Michigan St" in body
    assert at.selectbox(key="cmp_select_a").value == BENEZET
    assert at.selectbox(key="cmp_select_b").value == MICHIGAN_15S66

    # A changed widget value and its rendered card must stay in sync.
    at.selectbox(key="cmp_select_a").set_value(CENTRE_10S5).run()
    assert not at.exception, at.exception
    assert at.selectbox(key="cmp_select_a").value == CENTRE_10S5
    assert "Centre Ave" in _texts(at)


def test_integrity_view(at: AppTest) -> None:
    at.radio(key="view").set_value("Integrity").run()
    body = _texts(at)
    assert "Measured AI delta" in body
    assert "0/75" in body and "15/75" in body
    assert "frozen one-pass reader" in body
    assert "Engine outcomes are unchanged" in body
    assert "Multimodal delta" in body
    assert "29 structure-routed records" in body
    assert any(metric.label == "Vision abstentions" and metric.value == "45" for metric in at.metric)
    assert "93/96" in body
    assert not at.exception, at.exception
    assert "The engine decides; Claude assembles; the checker enforces." in _texts(at)
    assert "not encoded: **none**" in _texts(at)
    assert "summary(run_cases())" not in _texts(at)
