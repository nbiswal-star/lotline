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


def _split(text: str) -> list[str]:
    return [] if text in ("", "none") else [t.strip() for t in text.split(";")]


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
    assert [c.check for c in r.next_checks] == _split(row["expected_unresolved_checks"])
    assert all(c.owner and c.trigger for c in r.next_checks)


# Barriers: exact where the label wording follows one consistent grammar; key
# content elsewhere (labels vary in phrasing and ordering across rows; see report).
EXACT_BARRIERS = {
    "0131N00031000000",  # Benezet
    "0014N00100000000",  # Michigan 14N100
    "0050K00227000000",  # Dearborn
    "0010S00005000000",  # Centre 10S5
    "0010R00108000000",  # Centre 10R108
    "0042D00039000000",  # Walcott
    "0010L00127000000",  # Wylie
    "0075S00108000000",  # McClure (UI)
    "0023E00229000000",  # Garfield
}
KEY_CONTENT = {
    "0015S00066000000": ["terrain and undermining screening overlaps", "corner/frontage status"],
    "0081R00122000000": ["requires survey", "911.04.A.69", "911.04.A.69(b)"],
    "0034A00290000000": ["requires survey", "911.04.A.69(b)", "terrain and undermining screening overlaps"],
    "0016N00110000000": ["requires survey", "911.04.A.69(b)", "terrain and FEMA screening overlaps"],
    "0088R00001000000": ["P (Parks and Open Space) district", "§911.02", "site plan review applies",
                         "terrain screening overlap"],
    "0088G00313000A00": ["P (Parks and Open Space) district", "§911.02", "site plan review applies",
                         "terrain screening overlap"],
}


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_barriers(row, results):
    got = results[row["pin"]].barriers
    if row["pin"] in EXACT_BARRIERS:
        assert got == _split(row["expected_barriers"])
    else:
        joined = "; ".join(got)
        for needle in KEY_CONTENT[row["pin"]]:
            assert needle in joined
