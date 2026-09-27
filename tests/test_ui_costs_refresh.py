"""Cost worksheet, live-freshness check, map points and task tickets: pure functions."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from lotline import costs, refresh
from lotline.loaders import DATA_DIR
from lotline.models import Outcome
from lotline.ui import geo, tickets
from lotline.ui import viewmodels as vm
from tests.conftest import BENEZET, CENTRE_10S5

MICHIGAN_15S66 = "0015S00066000000"


@pytest.fixture(scope="module")
def results(snapshot):
    return vm.screen_all(snapshot, today=date(2026, 9, 26))


# ---------------------------------------------------------------- costs


def test_every_default_is_cited_or_blank() -> None:
    table = costs.load_assumptions()
    assert table["quiet_title"].default_usd == 2000 and table["quiet_title"].cited
    assert "Task Force" in table["quiet_title"].source and table["quiet_title"].source_date == "2026-01"
    for a in table.values():
        assert a.default_usd is None or a.cited, a.key


def test_uncited_default_is_dropped(tmp_path: Path) -> None:
    p = tmp_path / "c.csv"
    p.write_text("key,label,default_usd,applies_when,role,source,source_date,source_url,note\n"
                 "survey,Survey,1500,always,row,,,,\n")
    assert costs.load_assumptions(p)["survey"].default_usd is None
    assert costs.load_assumptions(tmp_path / "missing.csv") == {}


def test_benezet_worksheet(snapshot, results) -> None:
    ws = costs.worksheet(snapshot, results[BENEZET])
    rows = {r.key: r for r in ws.rows}
    assert not ws.blocked
    assert rows["upset"].default_usd == snapshot.advert[BENEZET].upset
    assert rows["upset"].fact_ids == (f"{BENEZET}:upset:city_advertisement",)
    assert rows["upset"].fact_ids[0] in {f.id for f in results[BENEZET].facts}
    assert rows["quiet_title"].default_usd == 2000
    assert rows["surviving_liens"].default_usd is None
    assert rows["surviving_liens"].basis == "amount unknown: title search required"
    for key in ("title_exam", "survey", "holding"):
        assert rows[key].default_usd is None and rows[key].basis == costs.ENTER_ESTIMATE
    # Benezet has no hazard family: no geotechnical or flood rows (no filler).
    assert "geotechnical" not in rows and "flood_determination" not in rows
    assert any("90-day redemption" in n for n in ws.notes)
    assert any("demolition cost due" in n for n in ws.notes)
    assert [r.key for r in ws.references] == ["sheriff_reference"]


def test_hazard_rows_follow_engine_families(snapshot, results) -> None:
    r = results[MICHIGAN_15S66]
    rows = {x.key for x in costs.worksheet(snapshot, r).rows}
    assert ("geotechnical" in rows) == bool({"terrain", "undermining"} & set(r.hazard_families))
    fema = replace(r, hazard_families=["FEMA SFHA"])
    rows = {x.key for x in costs.worksheet(snapshot, fema).rows}
    assert "flood_determination" in rows and "geotechnical" not in rows


def test_critical_conflict_blocks(snapshot, results) -> None:
    ws = costs.worksheet(snapshot, results[CENTRE_10S5])
    assert ws.blocked and "Resolve records before estimating" in costs.BLOCKED_BANNER


def test_demolition_lien_row_when_recorded(snapshot, results) -> None:
    pin = next(p for p, t in snapshot.treasury.items() if t.demo_cost_due > 0)
    r = results[pin]
    ws = costs.worksheet(snapshot, r)
    row = next(x for x in ws.rows if x.key == "demolition_lien")
    assert row.default_usd is None and row.fact_ids == (f"{pin}:demo_cost_due:wprdc_treasury_sales",)
    assert f"${snapshot.treasury[pin].demo_cost_due:,.2f}" in row.note


def test_total_skips_blanks() -> None:
    assert costs.total([1433.76, None, 2000.0, None]) == (3433.76, 2)
    assert costs.total([]) == (0, 0)
    assert costs.total_line([100.0, None], 2) == "$100.00 from 1 filled row; 1 row left blank (not counted)"
    with pytest.raises(ValueError):
        costs.total([-1.0])


def test_worksheet_does_not_change_engine_result(snapshot, results) -> None:
    before = results[BENEZET]
    snap = repr(before)
    costs.worksheet(snapshot, before)
    assert repr(before) == snap


# ---------------------------------------------------------------- refresh


def _live(snapshot, mutate=None) -> list[dict]:
    recs = [{"pin": p, "treasury_sale_date": t.sale_date + "T00:00:00", "total_tax_due": t.total_tax_due,
             "demo_cost_due": t.demo_cost_due} for p, t in snapshot.treasury.items()]
    return mutate(recs) if mutate else recs


def _fetch(records, calls=None):
    def fetch(url: str, body: bytes, timeout: float) -> bytes:
        if calls is not None:
            calls.append((url, json.loads(body), timeout))
        return json.dumps({"success": True, "result": {"records": records}}).encode()
    return fetch


def test_refresh_no_changes_and_request_shape(snapshot) -> None:
    calls: list = []
    rep = refresh.check_live(snapshot, _fetch(_live(snapshot), calls),
                             now=datetime(2026, 9, 27, 5, 0, tzinfo=timezone.utc))
    assert rep.status == "ok" and rep.changes == () and rep.live_count == 96
    assert rep.headline == f"Snapshot {snapshot.manifest['wprdc_treasury_sales'].snapshot_as_of} vs live now: 0 changes"
    url, body, timeout = calls[0]
    assert url == refresh.API_URL and timeout == 10
    assert body["resource_id"] == "6b2aa631-26e0-4d02-abe0-7fb87707210c" and body["limit"] == 2000


def test_refresh_detects_changes(snapshot) -> None:
    pins = sorted(snapshot.treasury)

    def mutate(recs):
        recs = [r for r in recs if r["pin"] != pins[0]]  # removed
        recs.append({"pin": "0999Z00001000000", "treasury_sale_date": "2026-10-02", "total_tax_due": 10.0})
        for r in recs:
            if r["pin"] == pins[1]:
                r["total_tax_due"] = r["total_tax_due"] + 5
            if r["pin"] == pins[2]:
                r["treasury_sale_date"] = "2026-11-06"
        return recs

    rep = refresh.check_live(snapshot, _fetch(_live(snapshot, mutate)))
    kinds = {(c.pin, c.kind) for c in rep.changes}
    assert kinds == {(pins[0], "removed"), ("0999Z00001000000", "added"),
                     (pins[1], "total_tax_due"), (pins[2], "sale_date")}
    assert rep.headline.endswith("4 changes")
    rows = refresh.change_rows(rep)
    assert {r["Change"] for r in rows} == {"PIN removed", "PIN added", "Total tax due changed", "Sale date changed"}


@pytest.mark.parametrize("fetch", [
    lambda u, b, t: (_ for _ in ()).throw(OSError("no route")),
    lambda u, b, t: b"not json",
    lambda u, b, t: json.dumps({"success": False}).encode(),
])
def test_refresh_offline_is_graceful(snapshot, fetch) -> None:
    rep = refresh.check_live(snapshot, fetch)
    assert rep.status == "offline" and rep.headline == "Can't reach WPRDC; snapshot unchanged."
    assert rep.changes == ()


def test_refresh_never_writes_data(snapshot) -> None:
    before = {p.name: p.stat().st_mtime_ns for p in DATA_DIR.iterdir()}
    refresh.check_live(snapshot, _fetch(_live(snapshot)))
    assert {p.name: p.stat().st_mtime_ns for p in DATA_DIR.iterdir()} == before


# ---------------------------------------------------------------- map


def test_map_points_cover_all_records(snapshot, results) -> None:
    coords = geo.load_coordinates()
    pts = geo.map_points(snapshot, results, coords)
    assert len(pts) == 96
    counts = geo.family_counts(pts)
    assert counts["out"] == 19 and counts["structure"] == 63
    assert counts["advance"] == sum(r.outcome is Outcome.ADVANCE for r in results.values())
    assert all(40.2 < p.lat < 40.7 and -80.3 < p.lon < -79.7 for p in pts)
    assert geo.FAMILY_STYLE["out"][1][3] == 0  # hollow
    assert pts[-1].family == "advance"  # screened lots drawn on top


def test_map_coordinates_missing_file(tmp_path: Path) -> None:
    assert geo.load_coordinates(tmp_path) == {}


# ---------------------------------------------------------------- tickets


def test_ticket_is_templated(snapshot, results) -> None:
    p = vm.packet(snapshot, results, BENEZET)

    class Ev:
        record_id, date, source, quote = "PLI-1", "2025-01-02", "pli_violations", "VACANT LOT OVERGROWN"

    md = tickets.ticket_markdown(check=p.next_checks[0], parcel_title=p.title, pin=p.pin, pin_short=p.pin_short,
                                 address=p.address, outcome=p.outcome_label, sale_date="2026-10-02",
                                 snapshot_label="Treasury list 2026-09-24", evidence=[Ev()])
    assert p.next_checks[0]["Check"] in md and p.next_checks[0]["Who resolves it"] in md
    assert "Due before:** 2026-10-01" in md
    assert "PLI-1" in md and "“VACANT LOT OVERGROWN”" in md
    assert tickets.TICKET_LABEL in md
    assert tickets.due_before("2026-10-05") == "2026-10-02"  # Monday sale -> Friday
