"""Reproduce the citywide overlap behind LotLine's problem-scale claim.

The network fetch is intentionally separate from the offline report:

    uv run python -m evaluation.problem_scale --fetch
    uv run python -m evaluation.problem_scale --report

``--fetch`` downloads only public parcel identifiers and the fields needed to
define the two sets.  ``--report`` uses the committed snapshot and needs no
network access.  No address or owner field is requested or stored.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.common import REPO_ROOT, md_table

DATA = REPO_ROOT / "data" / "problem_scale"
REPORT = REPO_ROOT / "docs" / "validation" / "problem_scale.md"
API = "https://data.wprdc.org/api/3/action/datastore_search"
ASSESSMENT_RESOURCE = "65855e14-549e-4992-b5be-d629afc676fa"
CONDEMNED_RESOURCE = "0a963f26-eb4b-4325-bbbc-3ddf6a871410"
CITY_CODES = tuple(f"{ward:03d}" for ward in range(101, 133))
PAGE_SIZE = 5000


def _post(body: dict[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(body).encode()
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                API,
                data=encoded,
                headers={"Content-Type": "application/json", "User-Agent": "lotline-problem-scale"},
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.load(response)
            if not payload.get("success"):
                raise RuntimeError("WPRDC returned success=false")
            return payload["result"]
        except Exception:  # noqa: BLE001 - retry transient public-portal failures
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def _fetch_all(body: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = _post({**body, "limit": PAGE_SIZE, "offset": offset})
        records = page["records"]
        rows.extend(records)
        offset += len(records)
        if not records or offset >= int(page.get("total", 0)):
            return rows


def _clean(value: Any) -> str:
    return "" if value is None else " ".join(str(value).split())


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def fetch() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    assessment_rows: list[dict[str, str]] = []
    for code in CITY_CODES:
        rows = _fetch_all({
            "resource_id": ASSESSMENT_RESOURCE,
            "fields": "PARID,MUNICODE,MUNIDESC,USEDESC,ASOFDATE",
            "filters": {"MUNICODE": code},
            "q": "VACANT",
            "sort": "PARID asc",
        })
        for row in rows:
            cleaned = {key: _clean(row.get(key)) for key in
                       ("PARID", "MUNICODE", "MUNIDESC", "USEDESC", "ASOFDATE")}
            # q searches the whole record. Retain only the declared assessment-use construct.
            if "VACANT" not in cleaned["USEDESC"].upper():
                continue
            if "PITTSBURGH" not in cleaned["MUNIDESC"].upper():
                raise ValueError(f"municipality code {code} is not Pittsburgh: {cleaned['MUNIDESC']!r}")
            assessment_rows.append(cleaned)

    condemned_raw = _fetch_all({
        "resource_id": CONDEMNED_RESOURCE,
        "fields": "parcel_id,inspection_status,create_date",
        "filters": {"inspection_status": "Active"},
        "sort": "parcel_id asc,create_date asc",
    })
    condemned_rows = [
        {key: _clean(row.get(key)) for key in ("parcel_id", "inspection_status", "create_date")}
        for row in condemned_raw
        if _clean(row.get("inspection_status")).casefold() == "active"
    ]

    assessment_rows.sort(key=lambda row: (row["PARID"], row["MUNICODE"], row["USEDESC"]))
    condemned_rows.sort(key=lambda row: (row["parcel_id"], row["create_date"]))
    _write_csv(DATA / "assessment_vacant.csv",
               ("PARID", "MUNICODE", "MUNIDESC", "USEDESC", "ASOFDATE"), assessment_rows)
    _write_csv(DATA / "active_condemned.csv",
               ("parcel_id", "inspection_status", "create_date"), condemned_rows)

    metadata = {
        "fetch_started_utc": started,
        "fetch_finished_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "assessment_resource": ASSESSMENT_RESOURCE,
        "condemned_resource": CONDEMNED_RESOURCE,
        "city_municipality_codes": list(CITY_CODES),
        "assessment_query": "MUNICODE each of 101..132; q=VACANT; retain USEDESC containing VACANT",
        "condemned_query": "inspection_status exact Active",
        "assessment_rows": len(assessment_rows),
        "condemned_rows": len(condemned_rows),
    }
    (DATA / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                                         encoding="utf-8")
    print(f"wrote {len(assessment_rows)} assessment rows and {len(condemned_rows)} condemned rows")


def _read_csv(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report() -> dict[str, Any]:
    assessment = _read_csv("assessment_vacant.csv")
    condemned = _read_csv("active_condemned.csv")
    meta = json.loads((DATA / "metadata.json").read_text(encoding="utf-8"))

    vacant_ids = {row["PARID"] for row in assessment if len(row["PARID"]) == 16}
    condemned_ids = {row["parcel_id"] for row in condemned if len(row["parcel_id"]) == 16}
    overlap = vacant_ids & condemned_ids
    uses = Counter(row["USEDESC"] for row in assessment if row["PARID"] in vacant_ids)
    as_of = sorted({row["ASOFDATE"] for row in assessment if row["ASOFDATE"]})
    duplicates = len(condemned) - len(condemned_ids)

    pct_vacant = 100 * len(overlap) / len(vacant_ids) if vacant_ids else 0
    pct_condemned = 100 * len(overlap) / len(condemned_ids) if condemned_ids else 0
    lines = [
        "# Pittsburgh vacant-assessment × active-condemnation overlap",
        "",
        "<!-- Generated by: uv run python -m evaluation.problem_scale --report -->",
        "",
        f"**Result.** **{len(overlap):,}** Pittsburgh parcels appear in both the County assessment "
        f"vacant-use set and the City active-condemned list. That is **{len(overlap):,}/{len(vacant_ids):,} "
        f"({pct_vacant:.1f}%)** of vacant-assessed parcels and **{len(overlap):,}/{len(condemned_ids):,} "
        f"({pct_condemned:.1f}%)** of unique active-condemned parcel IDs in the downloaded City list.",
        "",
        "| Set | Rows | Unique valid parcel IDs | Definition |",
        "|---|---:|---:|---|",
        f"| County vacant assessment | {len(assessment):,} | {len(vacant_ids):,} | Municipality codes "
        "101–132; municipality description contains Pittsburgh; assessment use description contains `VACANT` |",
        f"| City active-condemned list | {len(condemned):,} | {len(condemned_ids):,} | "
        "`inspection_status = Active` |",
        f"| Intersection | — | **{len(overlap):,}** | Exact 16-character parcel-ID join |",
        "",
        f"Assessment snapshot date(s): {', '.join(as_of) or 'not reported'}. Fetch completed: "
        f"{meta['fetch_finished_utc']}. The active-condemned source contains {duplicates:,} duplicate "
        "rows by parcel ID; the overlap uses unique IDs.",
        "",
        "## Assessment-use composition",
        "",
        md_table(["Assessment use", "Rows"], [(use, count) for use, count in uses.items()]),
        "",
        "## Reproducibility and construct limits",
        "",
        "The committed CSV files are the exact minimal rows used for this join, so the reported count "
        "regenerates offline. The fetch command re-queries mutable public datasets and can change later. "
        "No owner or address field is requested or stored.",
        "",
        "This is an operational records-overlap count—not a count of unsafe buildings, demolition "
        "candidates, development opportunities or present-day site conditions. Assessment land-use "
        "coding and condemnation status can lag reality; `Active` means ongoing investigation in the "
        "source metadata. A parcel in both sets still requires current-condition, title, survey, zoning "
        "and environmental checks. The overlap does not establish that AI is needed or that LotLine "
        "saves time or money.",
        "",
        "## Source record",
        "",
        f"- County assessment datastore resource: `{ASSESSMENT_RESOURCE}`",
        f"- City condemned-properties datastore resource: `{CONDEMNED_RESOURCE}`",
        f"- `assessment_vacant.csv` SHA-256: `{_sha256(DATA / 'assessment_vacant.csv')}`",
        f"- `active_condemned.csv` SHA-256: `{_sha256(DATA / 'active_condemned.csv')}`",
        f"- Network refresh: `uv run python -m evaluation.problem_scale --fetch`",
        f"- Offline regeneration: `uv run python -m evaluation.problem_scale --report`",
        "",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    result = {
        "assessment_rows": len(assessment),
        "vacant_unique": len(vacant_ids),
        "condemned_rows": len(condemned),
        "condemned_unique": len(condemned_ids),
        "overlap_unique": len(overlap),
        "overlap_pct_vacant": round(pct_vacant, 1),
        "overlap_pct_condemned": round(pct_condemned, 1),
        "assessment_as_of": as_of,
        "fetch_finished_utc": meta["fetch_finished_utc"],
    }
    (DATA / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                                        encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--fetch", action="store_true")
    group.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.fetch:
        fetch()
        report()
    else:
        report()


if __name__ == "__main__":
    main()
