"""The ten contract regression/adversarial cases, as shown in the integrity panel."""

from __future__ import annotations

import pytest

from lotline.memo import synthetic as syn
from lotline.memo.eval import run_cases, summary
from lotline.models import Snapshot
from tests.conftest import BENEZET, CENTRE_10S5, GARFIELD


@pytest.fixture(scope="module")
def cases(snapshot: Snapshot):
    return run_cases(snapshot)


def test_ten_cases_all_pass(cases) -> None:
    failed = {c.number: [l for l, ok in c.checks if not ok] for c in cases if not c.passed}
    assert not failed
    assert [c.number for c in cases] == list(range(1, 11))
    assert summary(cases) == "10/10 cases passed"


def test_synthetic_cases_are_labeled(cases) -> None:
    assert {c.number for c in cases if c.synthetic} == {6, 8, 10}
    assert all("SYNTHETIC" in c.title for c in cases if c.synthetic)


def test_every_case_checks_something(cases) -> None:
    assert all(len(c.checks) >= 3 for c in cases)


def test_hero_parcels_selected_from_data(snapshot: Snapshot) -> None:
    assert syn.find_pin(snapshot, "benezet") == BENEZET
    assert syn.find_pin(snapshot, "centre_10s5") == CENTRE_10S5
    assert syn.find_pin(snapshot, "garfield") == GARFIELD


def test_crashing_case_counts_as_failed(snapshot: Snapshot, monkeypatch) -> None:
    from lotline.memo import eval as ev

    def boom(_s):
        raise RuntimeError("x")

    monkeypatch.setattr(ev, "CASES", (boom,) + ev.CASES[1:])
    res = ev.run_cases(snapshot)
    assert not res[0].passed and summary(res) == "9/10 cases passed"
