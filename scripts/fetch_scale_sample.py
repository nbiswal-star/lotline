"""Draw the citywide AI-reader evaluation sample (protocol: docs/validation/ai_scale_protocol.md).

Writes, under data/validation_scale/:

* ``reference.csv``  one row per sampled parcel: stratum (reference label) and the structured
  permit / condemned-list facts that define it. Never shown to the model.
* ``records.csv``    long-format PLI violation text for the sampled parcels (model input), same
  shape as data/record_text.csv. No owner, contractor, address or coordinates.
* ``sample.csv``     sampling frame summary: per-stratum candidates, exclusions, screened,
  eligible and sampled counts, seed and fetch timestamps.

Run: ``uv run python scripts/fetch_scale_sample.py`` (network; ~2-4 minutes).
"""

from __future__ import annotations

import csv
import json
import random
import re
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "validation_scale"
API = "https://data.wprdc.org/api/3/action/datastore_search"

PLI = "70c06278-92c5-4040-ab28-17671866f81c"
PERMITS = "f4d1177a-f597-4c32-8cbf-7885f56253f6"
CONDEMNED = "0a963f26-eb4b-4325-bbbc-3ddf6a871410"

SEED = 20260927
PER_STRATUM = 75
MAX_RECORDS = 40
BATCH = 25
FULL_DEMO = {"COMPLETE DEMOLITION", "CITY FUNDED DEMOLITION"}

PLI_TEXT_FIELDS = (
    "status", "case_file_type", "investigation_outcome", "investigation_findings",
    "violation_description", "violation_code_section", "violation_spec_instructions",
    "court_date", "docket_number", "court_decision",
)
FREE_TEXT = ("investigation_findings", "violation_description", "violation_spec_instructions")
PLI_FIELDS = "parcel_id,casefile_number,investigation_date," + ",".join(PLI_TEXT_FIELDS)
PERSON_NAME = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr|Judge)\.?\s+[A-Z][a-z]+|\bspoke (?:with|to)\b", re.I)
OWNER_STOP = {"CITY", "PITTSBURGH", "COUNTY", "ALLEGHENY", "AUTHORITY", "HOUSING", "ESTATE", "TRUST"}


def _post(body: dict) -> dict:
    data = json.dumps(body).encode()
    for attempt in range(4):
        try:
            req = urllib.request.Request(API, data=data, headers={
                "Content-Type": "application/json", "User-Agent": "lotline-eval-scale"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)["result"]
        except Exception:  # noqa: BLE001 - transient portal errors
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def fetch_all(resource: str, filters: dict, fields: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        r = _post({"resource_id": resource, "filters": filters, "fields": fields,
                   "limit": 5000, "offset": offset, "sort": "_id asc"})
        rows += r["records"]
        offset += len(r["records"])
        if not r["records"] or offset >= r.get("total", 0):
            return rows


def _t(v: object) -> str:
    return "" if v is None else " ".join(str(v).split())


def build_frame() -> tuple[dict, dict, dict]:
    demo = fetch_all(PERMITS, {"permit_type": "Demolition Permit"},
                     "permit_id,work_type,status,issue_date,parcel_num")
    newc = fetch_all(PERMITS, {"permit_type": "BUILDING", "work_type": "NEW CONSTRUCTION"},
                     "permit_id,issue_date,parcel_num")
    cond = fetch_all(CONDEMNED, {}, "_id,parcel_id,inspection_status,create_date,owner")
    by_parcel: dict[str, list[dict]] = defaultdict(list)
    for p in demo:
        by_parcel[_t(p["parcel_num"])].append(p)
    newc_by: dict[str, list[str]] = defaultdict(list)
    for p in newc:
        newc_by[_t(p["parcel_num"])].append(_t(p["issue_date"])[:10])
    condemned: dict[str, dict] = {}
    owners: dict[str, set[str]] = defaultdict(set)
    for c in cond:
        pid = _t(c["parcel_id"])
        if _t(c.get("inspection_status")).lower() == "active":
            condemned.setdefault(pid, {"create_date": _t(c["create_date"])[:10], "row": c["_id"]})
        owners[pid] |= {w.upper() for w in re.findall(r"[A-Za-z]{4,}", _t(c.get("owner")))} - OWNER_STOP

    excluded = defaultdict(int)
    demolished: dict[str, dict] = {}
    for pid, permits in by_parcel.items():
        qual = [p for p in permits if p["status"] == "Completed" and p["work_type"] in FULL_DEMO]
        if len(pid) != 16:
            excluded["bad_parcel_id"] += 1
            continue
        if not qual:
            if pid not in condemned:
                excluded["demo_permit_partial_or_not_completed_only"] += 1
            continue
        if pid in condemned:
            excluded["completed_demo_and_on_condemned_list"] += 1
            continue
        first = min(_t(p["issue_date"])[:10] for p in qual)
        if any(d and d >= first for d in newc_by.get(pid, [])):
            excluded["new_construction_after_demo"] += 1
            continue
        qual.sort(key=lambda p: _t(p["issue_date"]))
        demolished[pid] = {"permit_ids": ";".join(p["permit_id"] for p in qual),
                           "first_issue": first, "last_issue": _t(qual[-1]["issue_date"])[:10],
                           "work_types": ";".join(sorted({p["work_type"] for p in qual}))}
    not_demolished: dict[str, dict] = {}
    for pid, c in condemned.items():
        if len(pid) != 16:
            excluded["bad_parcel_id"] += 1
            continue
        if pid in by_parcel:
            if not any(p["status"] == "Completed" and p["work_type"] in FULL_DEMO for p in by_parcel[pid]):
                excluded["condemned_with_noncompleted_or_partial_demo_permit"] += 1
            continue
        not_demolished[pid] = {"condemned_create_date": c["create_date"]}
    return ({"DEMOLISHED": demolished, "NOT_DEMOLISHED": not_demolished}, dict(excluded), owners)


def pli_records(rows: list[dict], owner_words: set[str], dropped: list) -> list[dict]:
    rows = sorted(rows, key=lambda r: (not r.get("investigation_date"), _t(r.get("investigation_date")), r["_id"]))
    by_cf: dict[str, list[dict]] = defaultdict(list)
    latest: dict[str, str] = {}
    seen: set[tuple[str, str, str]] = set()
    for r in rows:
        cf = _t(r.get("casefile_number")) or f"PLI-ROW-{r['_id']}"
        date = _t(r.get("investigation_date"))[:10]
        latest[cf] = max(latest.get(cf, ""), date)
        for f in PLI_TEXT_FIELDS:
            t = _t(r.get(f))
            if not t or (cf, f, t) in seen:
                continue
            seen.add((cf, f, t))
            words = {w.upper() for w in re.findall(r"[A-Za-z]{4,}", t)}
            if PERSON_NAME.search(t) or (words & owner_words):
                dropped.append((cf, f))
                continue
            by_cf[cf].append({"record_id": cf, "record_date": date, "field": f, "text": t})
    keep = sorted(by_cf, key=lambda cf: (latest.get(cf, ""), cf), reverse=True)[:MAX_RECORDS]
    return [row for cf in keep for row in by_cf[cf]]


def main() -> None:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    frame, excluded, owners = build_frame()
    frame_done = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    sampled: dict[str, list[str]] = {}
    records_out: list[dict] = []
    stats: dict[str, dict] = {}
    dropped: list = []
    for stratum in ("DEMOLISHED", "NOT_DEMOLISHED"):
        cands = sorted(frame[stratum])
        rng.shuffle(cands)
        taken: list[str] = []
        screened = ineligible = 0
        i = 0
        while len(taken) < PER_STRATUM and i < len(cands):
            batch = cands[i:i + BATCH]
            i += BATCH
            rows = fetch_all(PLI, {"parcel_id": batch}, "_id," + PLI_FIELDS)
            grouped: dict[str, list[dict]] = defaultdict(list)
            for r in rows:
                grouped[_t(r["parcel_id"])].append(r)
            for pid in batch:
                if len(taken) >= PER_STRATUM:
                    break
                screened += 1
                recs = pli_records(grouped.get(pid, []), owners.get(pid, set()), dropped)
                if not any(r["field"] in FREE_TEXT for r in recs):
                    ineligible += 1
                    continue
                taken.append(pid)
                records_out += [{"source_id": "pli_violations", "pin": pid, **r} for r in recs]
        sampled[stratum] = taken
        stats[stratum] = {"candidates": len(cands), "screened": screened,
                          "ineligible_no_free_text": ineligible, "sampled": len(taken)}
        print(f"{stratum}: candidates {len(cands)}, screened {screened}, "
              f"ineligible {ineligible}, sampled {len(taken)}")
    finished = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with (OUT / "records.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=("source_id", "pin", "record_id", "record_date", "field", "text"))
        w.writeheader()
        w.writerows(records_out)
    with (OUT / "reference.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=("pin", "stratum", "demo_permit_ids", "demo_first_issue",
                                           "demo_last_issue", "demo_work_types", "condemned_create_date"))
        w.writeheader()
        for stratum, pins in sampled.items():
            for pid in pins:
                f = frame[stratum][pid]
                w.writerow({"pin": pid, "stratum": stratum,
                            "demo_permit_ids": f.get("permit_ids", ""),
                            "demo_first_issue": f.get("first_issue", ""),
                            "demo_last_issue": f.get("last_issue", ""),
                            "demo_work_types": f.get("work_types", ""),
                            "condemned_create_date": f.get("condemned_create_date", "")})
    with (OUT / "sample.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["key", "value"])
        rows = [("seed", SEED), ("per_stratum_target", PER_STRATUM), ("max_records_per_parcel", MAX_RECORDS),
                ("fetch_started_utc", started), ("frame_fetched_utc", frame_done),
                ("fetch_finished_utc", finished), ("pli_resource", PLI), ("permits_resource", PERMITS),
                ("condemned_resource", CONDEMNED), ("text_fields_dropped_person_screen", len(dropped))]
        rows += [(f"excluded_{k}", v) for k, v in sorted(excluded.items())]
        for stratum, s in stats.items():
            rows += [(f"{stratum}_{k}", v) for k, v in s.items()]
        w.writerows(rows)
    print(f"excluded: {excluded}; person-screen dropped {len(dropped)} fields; "
          f"records rows {len(records_out)}; wrote {OUT}")


if __name__ == "__main__":
    main()
