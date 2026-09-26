"""Engine conformance against tests/fixtures/expected_labels.csv (all 15 prepared parcels).

Labels are test data only; the engine never reads them.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from lotline.engine import conflict_level, screen
from lotline.engine.scoring import component_display
from lotline.loaders import context_for

LABELS = Path(__file__).parent / "fixtures" / "expected_labels.csv"
ROWS = list(csv.DictReader(LABELS.open(newline="")))
IDS = [r["pin"] for r in ROWS]


@pytest.fixture(scope="module")
def results(snapshot):
    return {r["pin"]: screen(context_for(snapshot, r["pin"])) for r in ROWS}


def _split(text: str, sep: str = ";") -> list[str]:
    return [] if text in ("", "none") else [t.strip() for t in text.split(sep)]


# Barrier and check texts may contain ";" (e.g. Treasurer Sale terms), so those
# two label columns are separated by " | ".
LIST_SEP = " | "


def test_fifteen_rows():
    assert len(ROWS) == 15 and len(set(IDS)) == 15


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_outcome(row, results):
    # Labels write routing states without the "(routing) " prefix used by models.Outcome.
    got = results[row["pin"]].outcome.value.removeprefix("(routing) ")
    assert got == row["expected_screen_outcome"]


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_hazard_families(row, results):
    assert results[row["pin"]].hazard_families == _split(row["expected_hazard_families"])


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_component_scores(row, results):
    r = results[row["pin"]]
    assert component_display(r.use) == row["expected_use_score"]
    assert component_display(r.dimensional) == row["expected_dimensional_score"]
    assert component_display(r.environment) == row["expected_environment_score"]


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_ease_display(row, results):
    assert results[row["pin"]].ease.display == row["expected_ease_result"]


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_evidence_coverage(row, results):
    assert results[row["pin"]].coverage_display == row["expected_evidence_coverage"]


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_conflict_level(row, results):
    assert conflict_level(results[row["pin"]]) == row["expected_conflict_level"]


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_setback_screen(row, results):
    assert results[row["pin"]].setback_screen == row["expected_base_setback_screen"]


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_area_gap_pct(row, results):
    got = results[row["pin"]].area_gap_pct
    assert got is not None and round(got) == round(float(row["expected_area_gap_pct"]))


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_upset_to_assessed_land(row, results):
    assert results[row["pin"]].upset_to_assessed_land == pytest.approx(
        float(row["expected_upset_to_assessed_land"]), abs=1e-9
    )


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_next_checks_exact_order(row, results):
    r = results[row["pin"]]
    assert [c.check for c in r.next_checks] == _split(row["expected_unresolved_checks"], LIST_SEP)
    assert all(c.owner and c.trigger for c in r.next_checks)


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_barriers(row, results):
    """Exact, in order, for all 15 rows."""
    assert results[row["pin"]].barriers == _split(row["expected_barriers"], LIST_SEP)


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_every_defer_names_its_missing_or_conflicting_input(row, results):
    r = results[row["pin"]]
    if r.outcome.value.startswith("Defer"):
        assert r.barriers and r.next_checks
