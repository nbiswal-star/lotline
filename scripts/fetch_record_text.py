"""In-window data fetch: enforcement-record text for the 15 golden parcels.

Pulls every City of Pittsburgh PLI violation row and every condemned/dead-end
property row for the PINs in data/parcel_facts.csv from WPRDC (CKAN
``datastore_search``, POST with a JSON ``filters`` body; GET with filters is
refused by the portal) and writes data/record_text.csv in long format, one row
per (source record, text field), so every text field is individually citable.

Sources:
  PLI violations        https://data.wprdc.org/datastore/dump/70c06278-92c5-4040-ab28-17671866f81c
  Condemned properties  https://data.wprdc.org/datastore/dump/0a963f26-eb4b-4325-bbbc-3ddf6a871410
  PLI permits           https://data.wprdc.org/datastore/dump/f4d1177a-f597-4c32-8cbf-7885f56253f6
                        (filtered by ``parcel_num``, plus any demolition permit number cited
                        in the fetched PLI text, so a cited permit can be cross-checked in code)

Data minimization: no owner or person fields are kept (the condemned list's
``owner`` column is never written). Address fields are not written either; the
PIN identifies the parcel. Free-text findings are public inspector notes and
are stored as untrusted source text.

Identical texts are deduplicated per casefile and field, keeping the earliest
record date. Run: ``uv run python scripts/fetch_record_text.py``. It also
updates the ``record_text`` row of data/source_manifest.csv with today's date.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "record_text.csv"
MANIFEST = DATA / "source_manifest.csv"
API = "https://data.wprdc.org/api/3/action/datastore_search"

PLI_RESOURCE = "70c06278-92c5-4040-ab28-17671866f81c"
CONDEMNED_RESOURCE = "0a963f26-eb4b-4325-bbbc-3ddf6a871410"

PLI_TEXT_FIELDS = (
    "status", "case_file_type", "investigation_outcome", "investigation_findings",
    "violation_description", "violation_code_section", "violation_spec_instructions",
    "court_date", "docket_number", "court_decision",
)
PERMITS_RESOURCE = "f4d1177a-f597-4c32-8cbf-7885f56253f6"
PERMIT_TEXT_FIELDS = ("permit_type", "work_type", "status", "work_description")
PERMIT_REF = re.compile(r"\bDP-\d{4}-\d+\b")

CONDEMNED_TEXT_FIELDS = (
    "property_type", "inspection_status", "latest_inspection_result", "latest_inspection_score",
)
# Never written, whatever the portal returns.
DROPPED = {"owner", "owner_name", "contractor_name", "address", "zip_code", "latitude", "longitude"}

# Free-text notes that name a person (honorific or judge + name, "spoke with ...") or
# contain a word of the condemned-list owner name are dropped whole, never written.
PERSON_NAME = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr|Judge)\.?\s+[A-Z][a-z]+|\bspoke (?:with|to)\b", re.I)
PII_DROPPED: list[tuple[str, str, str]] = []

OUT_COLUMNS = ("source_id", "pin", "record_id", "record_date", "field", "text")


def fetch(resource: str, pin: str, *, key: str = "parcel_id") -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        body = json.dumps({"resource_id": resource, "filters": {key: pin},
                           "limit": 1000, "offset": offset}).encode()
        req = urllib.request.Request(API, data=body, headers={
            "Content-Type": "application/json", "User-Agent": "lotline-record-fetch"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.load(resp)["result"]
        batch = result["records"]
        rows += batch
        offset += len(batch)
        if not batch or offset >= result.get("total", 0):
            return rows


def _text(v: object) -> str:
    if v is None:
        return ""
    return " ".join(str(v).split())


RAW_COUNTS: dict[tuple[str, str], int] = {}


def names_person(text: str, owner_words: set[str]) -> bool:
    if PERSON_NAME.search(text):
        return True
    words = {w.upper() for w in re.findall(r"[A-Za-z]{4,}", text)}
    return bool(words & owner_words)


def owner_words(pin: str) -> set[str]:
    """Owner-name words from the condemned list, kept in memory only to screen notes."""
    words: set[str] = set()
    for r in fetch(CONDEMNED_RESOURCE, pin):
        words |= {w.upper() for w in re.findall(r"[A-Za-z]{4,}", str(r.get("owner") or ""))}
    return words - {"CITY", "PITTSBURGH", "COUNTY", "ALLEGHENY", "AUTHORITY", "HOUSING", "ESTATE", "TRUST"}


def pli_rows(pin: str) -> list[dict]:
    # Earliest dated row first; undated rows last, so a deduplicated text keeps a real date.
    raw = sorted(fetch(PLI_RESOURCE, pin),
                 key=lambda r: (not r.get("investigation_date"), r.get("investigation_date") or "", r["_id"]))
    screen = owner_words(pin)
    RAW_COUNTS[("pli", pin)] = len(raw)
    out: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for r in raw:
        cf = _text(r.get("casefile_number")) or f"PLI-ROW-{r['_id']}"
        date = _text(r.get("investigation_date"))[:10]
        for f in PLI_TEXT_FIELDS:
            t = _text(r.get(f))
            if not t or (cf, f, t) in seen:
                continue
            if names_person(t, screen):
                PII_DROPPED.append((pin, cf, f))
                seen.add((cf, f, t))
                continue
            seen.add((cf, f, t))
            out.append({"source_id": "pli_violations", "pin": pin, "record_id": cf,
                        "record_date": date, "field": f, "text": t})
    return out


def condemned_rows(pin: str) -> list[dict]:
    raw = fetch(CONDEMNED_RESOURCE, pin)
    RAW_COUNTS[("cond", pin)] = len(raw)
    out: list[dict] = []
    for r in raw:
        rid = f"COND-{r['_id']}"
        date = _text(r.get("create_date"))[:10]
        for f in CONDEMNED_TEXT_FIELDS:
            if f in DROPPED:
                continue
            t = _text(r.get(f))
            if t:
                out.append({"source_id": "condemned_properties", "pin": pin, "record_id": rid,
                            "record_date": date, "field": f, "text": t})
    return out


def permit_rows(pin: str, cited: set[str]) -> list[dict]:
    """Permits recorded on the parcel plus demolition permits its PLI text cites."""
    raw = {r["permit_id"]: r for r in fetch(PERMITS_RESOURCE, pin, key="parcel_num")}
    for pid in sorted(cited - set(raw)):
        for r in fetch(PERMITS_RESOURCE, pid, key="permit_id"):
            raw.setdefault(pid, r)
    RAW_COUNTS[("permits", pin)] = len(raw)
    out: list[dict] = []
    for pid, r in sorted(raw.items()):
        date = _text(r.get("issue_date"))[:10]
        for f in PERMIT_TEXT_FIELDS:
            t = _text(r.get(f))
            if t:
                out.append({"source_id": "pli_permits", "pin": pin, "record_id": pid,
                            "record_date": date, "field": f, "text": t})
    return out


def update_manifest(today: str, n_rows: int, n_pins: int) -> None:
    with MANIFEST.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
        fields = list(rows[0].keys())
    entry = {"source_id": "record_text", "snapshot_as_of": today, "query_completed": "Y",
             "local_artifact": OUT.name,
             "scope": (f"PLI violation, condemned-property and PLI permit text fields for {n_pins} golden parcels "
                       f"({n_rows} rows); untrusted source text for the AI evidence reader; "
                       "never read by the engine")}
    rows = [r for r in rows if r["source_id"] != "record_text"] + [entry]
    with MANIFEST.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    started = datetime.now(timezone.utc)
    with (DATA / "parcel_facts.csv").open(newline="") as fh:
        pins = [r["pin"] for r in csv.DictReader(fh)]
    rows: list[dict] = []
    print(f"fetch started {started.isoformat(timespec='seconds')} from {API}")
    for pin in pins:
        p, c = pli_rows(pin), condemned_rows(pin)
        cited = {m for r in p for m in PERMIT_REF.findall(r["text"])}
        d = permit_rows(pin, cited)
        print(f"{pin}: pli rows {RAW_COUNTS[('pli', pin)]:3d} -> text rows {len(p):3d} ({len({r['record_id'] for r in p})} casefiles); "
              f"condemned rows {RAW_COUNTS[('cond', pin)]} -> text rows {len(c)}; "
              f"permits {RAW_COUNTS[('permits', pin)]} -> text rows {len(d)}")
        rows += p + c + d
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    for pin, cf, f in PII_DROPPED:
        print(f"dropped (names a person): {pin} {cf} {f}")
    today = datetime.now().date().isoformat()
    update_manifest(today, len(rows), len(pins))
    print(f"wrote {len(rows)} rows to {OUT.relative_to(ROOT)}; manifest record_text as of {today}; "
          f"finished {datetime.now(timezone.utc).isoformat(timespec='seconds')}")


if __name__ == "__main__":
    sys.exit(main())
