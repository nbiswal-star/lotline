"""One-off data hygiene step (written in-window, Sat Sep 26 2026).

1. Moves prepared advertisement-match answer keys out of app-loaded files into
   tests/fixtures/expected_reconciliation.csv, so runtime reconciliation cannot
   read them even by accident.
2. Drops household-identifying columns (homestead flag, owner category, deed
   type/price/date) from the Treasury snapshot: routing needs only
   classdesc/usedesc, and the data-minimization rule says keep nothing else.

Idempotent: re-running on already-split files is a no-op.
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TREASURY = ROOT / "data" / "treasury_sale_2026-10-02_enriched.csv"
ADVERT = ROOT / "data" / "advert_2026-09-16_reconciliation.csv"
EXPECTED = ROOT / "tests" / "fixtures" / "expected_reconciliation.csv"

TREASURY_KEYS = ["in_city_advert_2026_09_16", "advert_sale_no", "advert_match_method"]
ADVERT_KEYS = ["pin_match", "price_check"]
HOUSEHOLD = ["homestead", "ownerdesc", "saledate", "saleprice", "saledesc"]


def main() -> None:
    treasury = pd.read_csv(TREASURY, dtype=str, keep_default_na=False)
    advert = pd.read_csv(ADVERT, dtype=str, keep_default_na=False)
    if not set(TREASURY_KEYS) <= set(treasury.columns):
        print("already split; nothing to do")
        return
    expected = treasury[["pin", *TREASURY_KEYS]].merge(
        advert[["pin", *ADVERT_KEYS]], on="pin", how="left"
    )
    expected.to_csv(EXPECTED, index=False)
    treasury.drop(columns=TREASURY_KEYS + HOUSEHOLD).to_csv(TREASURY, index=False)
    advert.drop(columns=ADVERT_KEYS).to_csv(ADVERT, index=False)
    print(f"wrote {EXPECTED.relative_to(ROOT)} ({len(expected)} rows)")


if __name__ == "__main__":
    main()
