"""Runtime reconciliation: Treasury (96) vs City advertisement (77)."""

from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from lotline import loaders
from lotline.loaders import load_snapshot
from lotline.models import Snapshot
from lotline.reconcile import (
    account_pin_mismatches,
    account_to_pin,
    account_ward,
    normalize_supplement,
    prices_agree,
    reconcile,
)
from tests.conftest import BENEZET, FIXTURES, GARFIELD, edit_csv


def _expected_rows() -> list[dict[str, str]]:
    with open(FIXTURES / "expected_reconciliation.csv", newline="") as fh:
        return list(csv.DictReader(fh))


def test_headline_counts(snapshot: Snapshot) -> None:
    r = snapshot.reconciliation
    assert (r.treasury_count, r.advertised_count) == (96, 77)
    assert len(r.matched_pins) == 77
    assert len(r.unmatched_treasury_pins) == 19
    assert r.unmatched_advert_pins == frozenset()
    assert len(r.price_check_pass) == 77 and r.price_check_fail == frozenset()


def test_every_account_normalizes_to_its_pin(snapshot: Snapshot) -> None:
    assert account_pin_mismatches(snapshot.advert) == frozenset()


def test_runtime_reconciliation_matches_expected_labels(snapshot: Snapshot) -> None:
    rows = _expected_rows()
    assert {r["pin"] for r in rows} == set(snapshot.treasury)
    for row in rows:
        pin = row["pin"]
        advertised = row["in_city_advert_2026_09_16"] == "Y"
        assert (pin in snapshot.reconciliation.matched_pins) is advertised, pin
        if advertised:
            assert snapshot.advert[pin].sale_no == int(row["advert_sale_no"])
            assert row["pin_match"] == "True"
            assert (pin in snapshot.reconciliation.price_check_pass) is (row["price_check"] == "True")
        else:
            assert pin not in snapshot.advert
            assert row["advert_sale_no"] == ""


def test_garfield_is_out_of_universe(snapshot: Snapshot) -> None:
    assert GARFIELD in snapshot.reconciliation.unmatched_treasury_pins
    assert BENEZET in snapshot.reconciliation.matched_pins


@pytest.mark.parametrize(
    ("account", "pin"),
    [
        ("1040027H00144011200", "0027H00144011200"),  # full 6-char supplement+card
        ("1040027L00182 00", "0027L00182000000"),  # blank supplement
        ("1140085C00270B3 00", "0085C00270B00300"),  # letter + digits
        ("1140088G00313A 00", "0088G00313000A00"),  # letter only
        ("1310131N00031 00", BENEZET),
        ("  1310131n00031 00 ", BENEZET),
    ],
)
def test_account_to_pin(account: str, pin: str) -> None:
    assert account_to_pin(account) == pin


@pytest.mark.parametrize("account", ["", "0131N00031000000", "2310131N00031 00", "1310131N00031"])
def test_account_to_pin_rejects_malformed(account: str) -> None:
    assert account_to_pin(account) is None


def test_account_ward() -> None:
    assert account_ward("1040027L00182 00") == "4"
    assert account_ward("garbage") is None


@pytest.mark.parametrize(
    ("supp", "out"), [("", "0000"), ("12", "0012"), ("B3", "B003"), ("A", "000A"), ("AB12", "AB12"),
                      ("ABCDE", None), ("3B", None)],
)
def test_normalize_supplement(supp: str, out: str | None) -> None:
    assert normalize_supplement(supp) == out


def test_price_tolerance() -> None:
    assert prices_agree(100.00, 100.01)
    assert not prices_agree(100.00, 100.02)


def test_price_mismatch_detected(snapshot: Snapshot) -> None:
    advert = dict(snapshot.advert)
    advert[BENEZET] = replace(advert[BENEZET], upset=advert[BENEZET].upset + 5)
    r = reconcile(snapshot.treasury, advert)
    assert r.price_check_fail == frozenset({BENEZET})
    assert BENEZET in r.matched_pins


def test_bad_account_is_not_matched(snapshot: Snapshot) -> None:
    advert = dict(snapshot.advert)
    advert[BENEZET] = replace(advert[BENEZET], account="1310131N00032 00")
    r = reconcile(snapshot.treasury, advert)
    assert BENEZET not in r.matched_pins
    assert BENEZET in r.unmatched_advert_pins and BENEZET in r.unmatched_treasury_pins


def test_account_mismatch_fails_startup(data_copy: Path) -> None:
    def corrupt(df: pd.DataFrame) -> pd.DataFrame:
        df.loc[df["pin"] == BENEZET, "account"] = "1310131N00032 00"
        return df

    edit_csv(data_copy / loaders.ADVERT_FILE, corrupt)
    with pytest.raises(loaders.SnapshotError, match="account_pin_mismatches: found 1"):
        load_snapshot(data_copy)


def test_reconcile_is_pure(snapshot: Snapshot) -> None:
    assert reconcile(snapshot.treasury, snapshot.advert) == snapshot.reconciliation
    assert reconcile(snapshot.treasury, snapshot.advert) == snapshot.reconciliation
