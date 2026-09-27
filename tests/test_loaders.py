"""Layer 1 and Layer 2 data acceptance tests (implementation plan v5, section 9: Data)."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from lotline import loaders
from lotline.facts import facts_for, rule_facts
from lotline.loaders import (
    EXPECTED_COUNTS,
    SnapshotError,
    context_for,
    is_sfha,
    load_snapshot,
    lookup_pin,
    normalize_pin,
    optional_text,
    parse_bool,
    split_overlay,
)
from lotline.models import FIELD_SOURCE, ParcelFacts, Snapshot, TreasuryRecord, fact_id
from tests.conftest import BENEZET, CENTRE_10S5, GARFIELD, WALCOTT, edit_csv

# ---------------------------------------------------------------- universe counts


def test_treasury_has_96_unique_pins(snapshot: Snapshot) -> None:
    assert len(snapshot.treasury) == 96
    assert all(len(p) == 16 for p in snapshot.treasury)


def test_advert_has_77_pins(snapshot: Snapshot) -> None:
    assert len(snapshot.advert) == 77


def test_structure_and_vacant_counts_come_from_usedesc(snapshot: Snapshot) -> None:
    matched = snapshot.reconciliation.matched_pins
    structures = {p for p in matched if snapshot.treasury[p].is_structure}
    vacant = matched - structures
    assert (len(structures), len(vacant)) == (63, 14)
    assert all("VACANT" in snapshot.treasury[p].usedesc for p in vacant)


def test_parcel_facts_has_15_unique_records(snapshot: Snapshot) -> None:
    assert len(snapshot.parcels) == 15
    assert set(snapshot.parcels) <= set(snapshot.treasury)


def test_expected_counts_block_is_self_consistent() -> None:
    c = EXPECTED_COUNTS
    assert c["matched"] + c["unmatched_treasury"] == c["treasury"]
    assert c["advertised_structures"] + c["advertised_vacant"] == c["matched"]


def test_count_drift_raises(data_copy: Path) -> None:
    edit_csv(data_copy / loaders.ADVERT_FILE, lambda df: df.iloc[1:])
    with pytest.raises(SnapshotError, match="advertised: found 76, expected 77"):
        load_snapshot(data_copy)


# ---------------------------------------------------------------- schema and integrity


def test_missing_required_column_raises(data_copy: Path) -> None:
    edit_csv(data_copy / loaders.PARCEL_FACTS_FILE, lambda df: df.drop(columns=["fema_zone"]))
    with pytest.raises(SnapshotError, match=r"parcel_facts.csv: missing required column.*fema_zone"):
        load_snapshot(data_copy)


def test_duplicate_pin_raises(data_copy: Path) -> None:
    edit_csv(data_copy / loaders.TREASURY_FILE, lambda df: pd.concat([df, df.iloc[[0]]]))
    with pytest.raises(SnapshotError, match="duplicate PINs"):
        load_snapshot(data_copy)


def test_short_pin_raises(data_copy: Path) -> None:
    def truncate(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[0, "pin"] = df.loc[0, "pin"][:-2]
        return df

    edit_csv(data_copy / loaders.PARCEL_FACTS_FILE, truncate)
    with pytest.raises(SnapshotError, match="16-character"):
        load_snapshot(data_copy)


def test_pins_keep_leading_zeros(snapshot: Snapshot) -> None:
    assert BENEZET in snapshot.treasury and BENEZET in snapshot.parcels
    assert all(p.startswith("0") for p in snapshot.treasury)


@pytest.mark.parametrize(
    "name",
    [loaders.TREASURY_FILE, loaders.ADVERT_FILE, loaders.PARCEL_FACTS_FILE,
     loaders.DISTRICT_RULES_FILE, loaders.MANIFEST_FILE],
)
def test_missing_file_gives_clear_error(data_copy: Path, name: str) -> None:
    (data_copy / name).unlink()
    with pytest.raises(SnapshotError, match=f"Snapshot file missing: .*{name}"):
        load_snapshot(data_copy)


def test_loads_from_copy_of_data_dir(data_copy: Path, snapshot: Snapshot) -> None:
    assert load_snapshot(data_copy) == snapshot


def test_future_snapshot_date_rejected_only_when_today_given(data_copy: Path) -> None:
    assert load_snapshot(data_copy, today=date(2026, 9, 27)) is not None  # record_text fetched 2026-09-27
    with pytest.raises(SnapshotError, match="dated after"):
        load_snapshot(data_copy, today=date(2026, 9, 1))


# ---------------------------------------------------------------- normalization


@pytest.mark.parametrize("text", ["YES", "yes", "Y", "y", "true", "True", "TRUE", " Y "])
def test_true_spellings(text: str) -> None:
    assert parse_bool(text) is True


@pytest.mark.parametrize("text", ["NO", "no", "N", "n", "false", "False"])
def test_false_spellings(text: str) -> None:
    assert parse_bool(text) is False


@pytest.mark.parametrize("text", ["", "maybe", "unknown"])
def test_unrecognized_boolean_raises(text: str) -> None:
    with pytest.raises(SnapshotError):
        parse_bool(text, where="x")


def test_mixed_case_booleans_in_files_normalize_identically(
    data_copy: Path, snapshot: Snapshot
) -> None:
    swap = {"YES": "true", "no": "N", "Y": "yes", "N": "FALSE"}
    cols = ["slope25_layer", "undermined_layer", "landslide_prone_layer",
            "condemned_case_active", "possible_corner"]

    def recode(df: pd.DataFrame) -> pd.DataFrame:
        for c in cols:
            df[c] = df[c].map(lambda v: swap.get(v, v))
        return df

    edit_csv(data_copy / loaders.PARCEL_FACTS_FILE, recode)
    assert load_snapshot(data_copy).parcels == snapshot.parcels


def test_engine_inputs_are_typed(snapshot: Snapshot) -> None:
    bool_fields = ("condemned_case_active", "slope25", "undermined", "landslide_prone",
                   "fema_sfha", "possible_corner")  # fema_sfha may be None only for D/unrecognized
    for p in snapshot.parcels.values():
        assert isinstance(p, ParcelFacts)
        assert all(isinstance(getattr(p, f), bool) for f in bool_fields)
        assert isinstance(p.streets_within_30ft, tuple)
        assert isinstance(p.pli_unique_casefiles, int)
    for t in snapshot.treasury.values():
        assert isinstance(t, TreasuryRecord) and isinstance(t.total_tax_due, float)


@pytest.mark.parametrize("text", ["", "none", "None", "none found", "NONE FOUND", "  "])
def test_none_text_normalizes(text: str) -> None:
    assert optional_text(text) is None


def test_parenthesized_overlay_is_not_an_rco(snapshot: Snapshot) -> None:
    assert split_overlay("(45 ft max height overlay)") == (None, "45 ft max height overlay")
    assert split_overlay("Hill CDC") == ("Hill CDC", None)
    walcott = snapshot.parcels[WALCOTT]
    assert walcott.rco is None and walcott.other_overlay == "45 ft max height overlay"
    assert snapshot.parcels[BENEZET].rco is None  # "none found"
    assert snapshot.parcels[BENEZET].historic_district is None  # "none"
    assert snapshot.parcels[GARFIELD].historic_district == "Mexican War Streets Expansion"


@pytest.mark.parametrize(
    ("zone", "expected"),
    [("X", False), ("A (partial) + X", True), ("AE", True), ("VE", True), ("X500", False),
     ("X (shaded)", False), ("AH", True), ("AO", True), ("AR", True), ("A99", True), ("V", True),
     ("A (partial) + X (shaded)", True), ("D", None), ("D + X", None), ("AE + D", True),
     ("ZONE Q", None), ("Q", None), ("unknown", None), ("", None)],
)
def test_fema_sfha(zone: str, expected: bool | None) -> None:
    """Validated against the NFHL vocabulary; D (undetermined) and unrecognized codes are unknown."""
    assert is_sfha(zone) is expected


def test_fema_sfha_in_snapshot(snapshot: Snapshot) -> None:
    sfha = {p for p, f in snapshot.parcels.items() if f.fema_sfha}
    assert sfha == {p for p, f in snapshot.parcels.items() if f.fema_zone.startswith("A")}
    assert len(sfha) == 2


def test_streets_split(snapshot: Snapshot) -> None:
    assert snapshot.parcels[BENEZET].streets_within_30ft == ("Bronze St", "Benezet Ave", "Bench Way")


def test_blank_setbacks_stay_none(snapshot: Snapshot) -> None:
    h = snapshot.rules["H"]
    assert h.site_standard_blocks_dimensional is True
    assert h.min_lot_sf == 3200.0
    assert (h.front_setback_ft, h.rear_setback_ft, h.exterior_side_ft, h.interior_side_ft) == (
        None, None, None, None)
    riv = snapshot.rules["RIV-RM"]
    assert riv.min_lot_sf == 0.0
    assert (riv.front_setback_ft, riv.rear_setback_ft, riv.exterior_side_ft,
            riv.interior_side_ft) == (0.0, 5.0, 0.0, 0.0)
    assert snapshot.rules["R1A-VH"].min_lot_sf == 0.0  # a real zero is kept distinct from blank
    blockers = {d for d, r in snapshot.rules.items() if r.site_standard_blocks_dimensional}
    assert blockers == {"H"}


def test_rule_permissions_are_canonical(snapshot: Snapshot) -> None:
    for r in snapshot.rules.values():
        assert {r.single_unit_permission, r.two_unit_permission} <= {"P", "A", "S", "C", "PROHIBITED"}
    ui = snapshot.rules["UI"]
    assert ui.dimensions_applicable is False and ui.dimensional_citation is None


def test_manifest_loads_with_boolean_query_status(snapshot: Snapshot) -> None:
    m = snapshot.manifest
    assert all(isinstance(e.query_completed, bool) for e in m.values())
    assert set(FIELD_SOURCE.values()) <= set(m)
    assert m["city_advertisement"].snapshot_as_of == "2026-09-16"


def test_query_status_comes_from_manifest_not_constants(data_copy: Path) -> None:
    """G3-G5 inputs are data: flipping the manifest flips the loaded value."""
    def fail_fema(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[df["source_id"] == "fema_nfhl", "query_completed"] = "N"
        return df

    edit_csv(data_copy / loaders.MANIFEST_FILE, fail_fema)
    assert load_snapshot(data_copy).manifest["fema_nfhl"].query_completed is False


# ---------------------------------------------------------------- context and PIN lookup


def test_missing_district_row_gives_rule_none(data_copy: Path) -> None:
    edit_csv(data_copy / loaders.DISTRICT_RULES_FILE, lambda df: df[df["district"] != "RM-M"])
    snap = load_snapshot(data_copy)
    ctx = context_for(snap, CENTRE_10S5)
    assert ctx is not None and ctx.facts is not None and ctx.rule is None


def test_context_for_benezet(snapshot: Snapshot) -> None:
    ctx = context_for(snapshot, BENEZET)
    assert ctx is not None
    assert ctx.advert is not None and ctx.facts is not None
    assert ctx.rule is not None and ctx.rule.district == "R1D-L"
    assert not ctx.treasury.is_structure


def test_context_for_structure_has_no_parcel_facts(snapshot: Snapshot) -> None:
    pin = next(p for p in snapshot.reconciliation.matched_pins if snapshot.treasury[p].is_structure)
    ctx = context_for(snapshot, pin)
    assert ctx is not None and ctx.facts is None and ctx.treasury.is_structure


def test_context_for_unadvertised_has_no_advert(snapshot: Snapshot) -> None:
    ctx = context_for(snapshot, GARFIELD)
    assert ctx is not None and ctx.advert is None and ctx.facts is not None


def test_context_for_unknown_pin_is_none(snapshot: Snapshot) -> None:
    assert context_for(snapshot, "9999Z99999000000") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (BENEZET, BENEZET),
        (" 0131n00031000000 ", BENEZET),
        ("0131-N-00031", BENEZET),
        ("0131-N-00031-0000-00", BENEZET),
        ("131N31", BENEZET),
        ("0131 N 00031 0000 00", BENEZET),
        ("0088-G-00313-A", "0088G00313000A00"),
        ("0085-C-00270-B3", "0085C00270B00300"),
    ],
)
def test_lookup_pin_accepts_user_forms(snapshot: Snapshot, text: str, expected: str) -> None:
    assert lookup_pin(snapshot, text) == expected


@pytest.mark.parametrize("text", ["", "abc", "9999Z99999000000", "131N", "0088G00313", "0131-N"])
def test_lookup_pin_never_fabricates(snapshot: Snapshot, text: str) -> None:
    assert lookup_pin(snapshot, text) is None


def test_normalize_pin_is_pure_formatting() -> None:
    assert normalize_pin("9999z1") == "9999Z00001000000"
    assert normalize_pin("12345Z1") is None


# ---------------------------------------------------------------- Layer 2 facts


def test_facts_ids_unique_and_sourced(snapshot: Snapshot) -> None:
    for pin in snapshot.treasury:
        ctx = context_for(snapshot, pin)
        assert ctx is not None
        facts = facts_for(ctx)
        ids = [f.id for f in facts]
        assert len(ids) == len(set(ids)), pin
        for f in facts:
            assert f.id.startswith(f"{pin}:{f.field}:") and f.source in snapshot.manifest
            assert f.as_of == snapshot.manifest[f.source].snapshot_as_of


def test_facts_classes_and_conflict_groups(snapshot: Snapshot) -> None:
    ctx = context_for(snapshot, CENTRE_10S5)
    assert ctx is not None
    by_field = {f.field: f for f in facts_for(ctx)}
    assert by_field["assess_lotarea_sf"].id == fact_id(CENTRE_10S5, "assess_lotarea_sf")
    assert by_field["assess_lotarea_sf"].conflict_group == "lot_area"
    assert by_field["county_gis_area_sf"].conflict_group == "lot_area"
    assert by_field["county_gis_area_sf"].value == 4305.0
    assert by_field["usedesc"].conflict_group == "current_condition"
    assert by_field["condemned_case_active"].conflict_group == "current_condition"
    approx = {f.field for f in by_field.values() if f.evidence_class == "approximate"}
    assert approx == {"mbr_short_side_ft", "mbr_long_side_ft", "streets_within_30ft",
                      "possible_corner"}
    assert all(by_field[a].note for a in approx)
    assert {f.evidence_class for f in by_field.values()} == {"raw", "approximate"}


def test_structure_facts_have_no_parcel_fields(snapshot: Snapshot) -> None:
    pin = next(p for p in snapshot.treasury if snapshot.treasury[p].is_structure)
    ctx = context_for(snapshot, pin)
    assert ctx is not None
    assert "mbr_short_side_ft" not in {f.field for f in facts_for(ctx)}


def test_rule_facts_skip_none(snapshot: Snapshot) -> None:
    facts = rule_facts(snapshot.rules["H"], snapshot.manifest)
    fields = {f.field for f in facts}
    assert "front_setback_ft" not in fields and "min_lot_sf" in fields
    assert all(f.id == f"RULE:H:{f.field}" and f.district == "H" and f.pin is None for f in facts)
    assert all(f.evidence_class == "rule" and f.as_of == "2026-09-24" for f in facts)


def test_fixture_csvs_parse() -> None:
    """Sanity check that test-only fixtures exist for the reconciliation tests."""
    from tests.conftest import FIXTURES

    with open(FIXTURES / "expected_reconciliation.csv", newline="") as fh:
        assert len(list(csv.DictReader(fh))) == 96


# ---------------------------------------------------------------- rule provenance (Ord. 10-2025)


def test_rule_provenance_fields_loaded(snapshot: Snapshot) -> None:
    for r in snapshot.rules.values():
        assert r.rules_as_of == "2026-09-16"
        assert r.amended_by
    assert snapshot.rules["R2-H"].amended_by.startswith("Ord. 10-2025")
    assert snapshot.rules["R2-H"].dimensional_citation == "903.03.D.2"
    assert snapshot.rules["RIV-RM"].dimensional_citation == "905.04.E"
    fields = {f.field: f.value for f in rule_facts(snapshot.rules["P"], snapshot.manifest)}
    assert fields["rules_as_of"] == "2026-09-16" and "amended_by" in fields


def test_p_lnc_and_riv_rm_dimensions_encoded(snapshot: Snapshot) -> None:
    p, lnc = snapshot.rules["P"], snapshot.rules["LNC"]
    assert p.dimensions_encoded and p.dimensional_citation == "905.01.C"
    assert (p.min_lot_sf, p.front_setback_ft, p.rear_setback_ft, p.exterior_side_ft, p.interior_side_ft) == (
        3200.0, 30.0, 20.0, 20.0, 5.0)
    assert lnc.dimensions_encoded and lnc.dimensional_citation == "904.02.C"
    assert (lnc.min_lot_sf, lnc.front_setback_ft, lnc.rear_setback_ft, lnc.exterior_side_ft,
            lnc.interior_side_ft) == (0.0, 0.0, 20.0, 0.0, 0.0)
    assert snapshot.rules["RIV-RM"].dimensions_encoded is True


def test_rule_provenance_columns_optional(data_copy: Path) -> None:
    edit_csv(data_copy / loaders.DISTRICT_RULES_FILE,
             lambda df: df.drop(columns=["rules_as_of", "amended_by"]))
    r = load_snapshot(data_copy).rules["P"]
    assert r.rules_as_of is None and r.amended_by is None


def test_bad_rules_as_of_date_raises(data_copy: Path) -> None:
    def bad(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[df["district"] == "P", "rules_as_of"] = "Sept 2026"
        return df

    edit_csv(data_copy / loaders.DISTRICT_RULES_FILE, bad)
    with pytest.raises(SnapshotError, match="rules_as_of"):
        load_snapshot(data_copy)


def test_conditional_use_permission_accepted(data_copy: Path) -> None:
    def cond(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[df["district"] == "UI", "two_unit_permission"] = "c"
        return df

    edit_csv(data_copy / loaders.DISTRICT_RULES_FILE, cond)
    assert load_snapshot(data_copy).rules["UI"].two_unit_permission == "C"


# --- invalid measurements (0 -> unknown with a warning; negative -> error) ----


@pytest.mark.parametrize("column", ["assess_lotarea_sf", "county_gis_area_sf", "mbr_short_side_ft",
                                    "mbr_long_side_ft"])
def test_zero_measure_is_unknown_with_warning(data_copy: Path, column: str) -> None:
    def zero(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[df["pin"] == BENEZET, column] = "0"
        return df

    edit_csv(data_copy / loaders.PARCEL_FACTS_FILE, zero)
    snap = load_snapshot(data_copy)
    f = snap.parcels[BENEZET]
    assert getattr(f, column) is None
    unit = "sf" if column.endswith("_sf") else "ft"
    note = f"{loaders.PARCEL_FACTS_FILE} pin {BENEZET} {column}: 0 {unit} recorded; treated as unknown"
    assert f.load_warnings == (note,) and note in snap.load_warnings


@pytest.mark.parametrize("column", ["assess_lotarea_sf", "county_gis_area_sf", "mbr_short_side_ft"])
def test_negative_measure_raises(data_copy: Path, column: str) -> None:
    def neg(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[df["pin"] == BENEZET, column] = "-5"
        return df

    edit_csv(data_copy / loaders.PARCEL_FACTS_FILE, neg)
    with pytest.raises(SnapshotError, match="negative"):
        load_snapshot(data_copy)


@pytest.mark.parametrize("column", ["min_lot_sf", "front_setback_ft", "interior_side_ft"])
def test_negative_rule_value_raises_but_zero_is_kept(data_copy: Path, column: str) -> None:
    def neg(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[df["district"] == "R2-H", column] = "-1"
        return df

    edit_csv(data_copy / loaders.DISTRICT_RULES_FILE, neg)
    with pytest.raises(SnapshotError, match="negative"):
        load_snapshot(data_copy)


def test_zero_treasury_lotarea_is_unknown(snapshot: Snapshot) -> None:
    zero = [w for w in snapshot.load_warnings if w.startswith(loaders.TREASURY_FILE)]
    assert len(zero) == 2 and all(w.endswith("lotarea: 0 sf recorded; treated as unknown") for w in zero)
    for w in zero:
        pin = w.split(" pin ")[1].split(" ")[0]
        assert snapshot.treasury[pin].lotarea is None
    assert all(p.load_warnings == () for p in snapshot.parcels.values())


def test_unrecognized_fema_zone_loads_as_unknown(data_copy: Path) -> None:
    def zone_d(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[df["pin"] == BENEZET, "fema_zone"] = "D"
        return df

    edit_csv(data_copy / loaders.PARCEL_FACTS_FILE, zone_d)
    assert load_snapshot(data_copy).parcels[BENEZET].fema_sfha is None
