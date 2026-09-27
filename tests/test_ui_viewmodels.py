"""UI view models: correct rows from engine output, no invented values."""

from __future__ import annotations

import re
import csv
import io
from datetime import date
from pathlib import Path

import pytest

from lotline.models import Outcome, ScreeningResult, Snapshot
from lotline.ui import memo_adapter, text
from lotline.ui import viewmodels as vm
from tests.conftest import BENEZET, CENTRE_10S5, REPO_ROOT

MICHIGAN_15S66 = "0015S00066000000"
WALCOTT = "0042D00039000000"
PIN_LITERAL = re.compile(r"(?<![0-9A-Za-z])\d{4}[A-Z]\d{5}[0-9A-Z]{4}\d{2}(?![0-9A-Za-z])")


@pytest.fixture(scope="module")
def results(snapshot: Snapshot) -> dict[str, ScreeningResult]:
    return vm.screen_all(snapshot, today=date(2026, 9, 26))


def test_funnel_counts(snapshot, results) -> None:
    f = vm.funnel(snapshot, results)
    assert (f.treasury, f.advertised, f.pins_matched, f.prices_agree) == (96, 77, 77, 77)
    assert (f.not_advertised, f.structures, f.vacant, f.advert_not_in_treasury) == (19, 63, 14, 0)


def test_triage_board_has_14_lots_grouped_by_outcome(snapshot, results) -> None:
    rows = vm.triage_rows(snapshot, results)
    assert len(rows) == 14
    assert all(set(vm.TRIAGE_COLUMNS) <= set(r) for r in rows)
    ranks = [text.OUTCOME_ORDER.index(results[r["pin"]].outcome) for r in rows]
    assert ranks == sorted(ranks), "board must be grouped by outcome, not neighborhood"
    for r in rows:
        res = results[r["pin"]]
        assert r["Development Ease"] == res.ease.display  # verbatim engine display
        assert r["Evidence"] == res.coverage_display
        assert r["Principal barrier"] == res.barriers[0]
        assert r["Outcome"] == text.OUTCOME_SHORT[res.outcome]
        assert res.outcome not in vm.ROUTING
        assert res.next_checks and r["First parcel-specific check"] and r["Who resolves it"]


def test_routed_rows_have_no_owner_fields(snapshot, results) -> None:
    out = vm.routed_rows(snapshot, results, Outcome.OUT_OF_UNIVERSE)
    struct = vm.routed_rows(snapshot, results, Outcome.STRUCTURE)
    assert (len(out), len(struct)) == (19, 63)
    for row in out + struct:
        assert not any("owner" in k.lower() for k in row)
        assert row["Reason"]


def test_benezet_packet(snapshot, results) -> None:
    p = vm.packet(snapshot, results, BENEZET)
    assert p.outcome is Outcome.ADVANCE and not p.routing
    assert p.ease_display == results[BENEZET].ease.display
    assert p.coverage_display == "5/5" and len(p.coverage) == 5
    assert [t.key for t in p.tiles] == ["zoning", "environmental", "infrastructure", "policy"]
    assert [t.unknown for t in p.tiles] == [
        "Contextual setbacks (Ch. 925) not evaluated",
        "Screening layers only; not a geotechnical or flood determination",
        "Utility capacity, laterals and legal access not established",
        "Community plan alignment not evaluated",
    ]
    assert p.treasurer_sale
    assert [c["Check"] for c in p.next_checks] == [nc.check for nc in results[BENEZET].next_checks]
    assert all(c["Who resolves it"] for c in p.next_checks)
    assert [c["Standard"] for c in p.next_checks].count("pre-spend") == 1
    assert len(p.provenance) == len(results[BENEZET].facts)
    assert all(c.short_reason for c in p.components)
    zoning = next(t for t in p.tiles if t.key == "zoning")
    site_standards = next(value for label, value in zoning.rows if label == "Overlays & site standards")
    assert "per-unit density" not in site_standards
    assert "§906.08" not in site_standards  # Benezet has no slope25 overlap.


def test_centre_packet_conflicts_verbatim(snapshot, results) -> None:
    r = results[CENTRE_10S5]
    p = vm.packet(snapshot, results, CENTRE_10S5)
    assert p.ease_display == r.ease.display and r.ease.total_low is None
    assert [c.summary for c in p.conflicts] == [c.summary for c in r.conflicts]
    assert any(c.level == "critical" for c in p.conflicts)
    dim = next(c for c in p.components if c.name == "dimensional")
    assert dim.withheld
    assert p.area is not None
    assert (p.area.assessment_sf, p.area.county_gis_sf) == ("1,672 sf", "4,305 sf")
    # Conflict-group facts are first in provenance.
    assert p.provenance[0]["Conflict group"]
    assert p.outcome_meaning.startswith("A critical public-record conflict")


def test_unknown_pin_path(snapshot) -> None:
    res = vm.resolve_query(snapshot, "9999-Z-99999")
    assert isinstance(res, vm.NotFound)
    assert res.message == f"PIN not found in snapshot dated {vm.snapshot_date(snapshot)}"
    assert isinstance(vm.resolve_query(snapshot, "not a pin"), vm.NotFound)


@pytest.mark.parametrize("query", [BENEZET, "131-N-31", "131N31", "0131-N-00031-0000-00", " 0131N00031000000 "])
def test_pin_forms_resolve(snapshot, query) -> None:
    assert vm.resolve_query(snapshot, query) == BENEZET


def test_demo_config_resolves_heroes(snapshot) -> None:
    cfg = vm.load_demo_config(snapshot)
    assert cfg.default_packet == BENEZET
    assert cfg.compare_default == (BENEZET, MICHIGAN_15S66)
    assert cfg.parcels["centre"] == CENTRE_10S5


def test_demo_config_drops_mismatched_entries(snapshot, tmp_path: Path) -> None:
    bad = tmp_path / "cfg.json"
    bad.write_text('{"parcels": {"x": {"pin": "131-N-31", "location": "Elsewhere Rd"}}, "default_packet": "x"}')
    cfg = vm.load_demo_config(snapshot, bad)
    assert cfg.parcels == {} and cfg.default_packet is None
    assert vm.load_demo_config(snapshot, tmp_path / "missing.json").parcels == {}


def test_compare_columns(snapshot, results) -> None:
    cols = vm.compare_columns(snapshot, results, [BENEZET, MICHIGAN_15S66])
    assert len(cols) == 2
    for label, rows in cols.items():
        assert tuple(rows) == vm.COMPARE_ROWS
    b = next(v for k, v in cols.items() if "Benezet" in k)
    assert b["Development Ease"] == results[BENEZET].ease.display
    line = vm.difference_line(snapshot, results, BENEZET, MICHIGAN_15S66)
    for fam in results[MICHIGAN_15S66].hazard_families:
        assert fam in line
    assert line.endswith(".")

    centre = vm.compare_columns(snapshot, results, [CENTRE_10S5])
    centre_rows = next(iter(centre.values()))
    assert centre_rows["Components"].startswith("Not shown: critical conflict")


def test_riv_rm_zoning_tile_uses_legal_distinctions_not_engine_conventions(snapshot, results) -> None:
    packet = vm.packet(snapshot, results, WALCOTT)
    zoning = next(tile for tile in packet.tiles if tile.key == "zoning")
    rows = dict(zoning.rows)
    assert "no stated district minimum" in rows["Lot area (both sources)"]
    assert "district minimum 0" not in rows["Lot area (both sources)"]
    use = rows["Housing use path (§911.02)"]
    assert "single-unit detached prohibited" in use
    assert "attached housing not evaluated" in use


def test_dates_and_rule_limits_come_from_snapshot(snapshot) -> None:
    assert vm.source_date(snapshot, "city_advertisement") == snapshot.manifest["city_advertisement"].snapshot_as_of
    assert vm.sale_date(snapshot) == next(iter(snapshot.treasury.values())).sale_date


def test_packet_export_is_deterministic_and_suppresses_critical_scores(snapshot, results) -> None:
    benezet = vm.packet(snapshot, results, BENEZET)
    export = vm.packet_markdown(snapshot, results[BENEZET], benezet)
    assert "Unresolved checks (not yet verified)" in export
    assert "Deterministic cited memo" in export and "Citations:" in export
    assert "Decision support only" in export

    centre = vm.packet(snapshot, results, CENTRE_10S5)
    critical = vm.packet_markdown(snapshot, results[CENTRE_10S5], centre)
    assert "Component values are withheld because a critical conflict" in critical
    assert "Use: 2" not in critical and "Environment: 1" not in critical
    for forbidden in ("environmentally clear", "will be sold"):
        assert forbidden not in export.lower() and forbidden not in critical.lower()


def test_triage_export_preserves_engine_order_and_no_ranking(snapshot, results) -> None:
    exported = vm.triage_csv(snapshot, results)
    lines = exported.splitlines()
    assert len(lines) == 15
    assert "Triage, not ranking" in exported
    parsed = list(csv.DictReader(io.StringIO(exported)))
    assert [row["Parcel"] for row in vm.triage_rows(snapshot, results)] == [row["Parcel"] for row in parsed]


def test_short_pin_roundtrip(snapshot) -> None:
    for pin in snapshot.treasury:
        assert vm.resolve_query(snapshot, vm.short_pin(pin)) == pin


def test_source_rows_cover_manifest(snapshot) -> None:
    rows = vm.source_rows(snapshot)
    assert {r["Source ID"] for r in rows} == set(snapshot.manifest)


def test_memo_adapter_never_raises() -> None:
    def boom(result):
        raise RuntimeError("model down")

    memo_vm, err = memo_adapter.build_memo(boom, result=object())
    assert memo_vm is None and "model down" in err
    assert memo_adapter.build_memo(None)[0] is None


@pytest.mark.parametrize("path", [REPO_ROOT / "app.py", *sorted((REPO_ROOT / "lotline" / "ui").glob("*.py"))],
                         ids=lambda p: p.name)
def test_no_pin_literals_in_ui(path: Path) -> None:
    assert not PIN_LITERAL.findall(path.read_text())
