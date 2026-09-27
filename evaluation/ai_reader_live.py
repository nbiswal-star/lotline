"""Live repeated runs of the enforcement-record reader and judge (makes Claude calls).

Not part of ``evaluation.run`` (which is offline). Run once to refresh the recorded
repeats; ``evaluation/ai_reader.py`` then re-verifies every recorded raw output offline.

    uv run python -m evaluation.ai_reader_live --reps 5            # labeled parcels
    uv run python -m evaluation.ai_reader_live --write-caches      # also refresh app caches from rep 1

Each repetition makes ``RUNS`` (3) reader calls with the production prompt and one judge
call over the union of verified items. The legacy setting (two runs, exact-tuple
intersection) and a single run are replayed offline from the first runs of the same
repetition, so the settings are compared on paired model outputs. Token usage and
latency come from each API response. Model prose is stored only as the raw JSON the
reader and judge returned; credentials are never written.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.common import DATA_DIR, FIXTURES_DIR, snapshot
from lotline.ai import evidence as ev
from lotline.ai.client import AIOutputError, AIUnavailable, call_structured, make_client

REPEATS_PATH = DATA_DIR / "ai_cache" / "reader_repeats.json"


def labeled_pins() -> list[str]:
    path = FIXTURES_DIR / "record_relevance.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(line for line in fh if not line.startswith("#")))
    return sorted({r["pin"] for r in rows})


def one_rep(pin: str, rep: int) -> dict[str, Any]:
    snap = snapshot()
    records = ev._records(snap, pin)
    prompt = ev.build_prompt(pin, records)
    rec = ev._UsageRecorder(make_client())
    out: dict[str, Any] = {"pin": pin, "rep": rep,
                           "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
    runs: list[Any] = []
    model = None
    start = time.perf_counter()
    try:
        for _ in range(ev.RUNS):
            resp = call_structured(ev.SYSTEM, prompt, ev.SCHEMA, client=rec, effort="medium")
            runs.append(resp.data)
            model = resp.model
    except (AIUnavailable, AIOutputError) as exc:
        return {**out, "error": str(exc), "runs": runs, "usage": rec.calls}
    out.update(model=model, elapsed_s=round(time.perf_counter() - start, 1), usage=rec.calls, runs=runs,
               k=ev.RUNS, combine="union")
    base = ev.digest_from_runs(pin, records, runs, status_ok="verified", model=model,
                               created_at=out["created_at"], combine="union")
    cands = ev.judge_candidates(base.items)
    if cands:
        try:
            verdicts, meta = ev.run_judge(cands)
            out["judge"] = {**meta, "verdicts": ev._verdict_rows(verdicts)}
        except (AIUnavailable, AIOutputError) as exc:
            out["judge"] = {"error": str(exc), "verdicts": []}
    else:
        out["judge"] = {"judged": 0, "usage": [], "verdicts": []}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--pins", nargs="*", default=None)
    ap.add_argument("--write-caches", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    pins = args.pins or labeled_pins()
    jobs = [(pin, rep) for rep in range(1, args.reps + 1) for pin in pins]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda j: one_rep(*j), jobs))
    existing: dict[str, Any] = {}
    if REPEATS_PATH.exists() and args.pins:
        existing = json.loads(REPEATS_PATH.read_text(encoding="utf-8"))
    reps = [r for r in existing.get("repeats", []) if r["pin"] not in pins] + results
    reps.sort(key=lambda r: (r["pin"], r["rep"]))
    payload = {"model_prompt_sha256": ev.hashlib.sha256((ev.SYSTEM + ev.JUDGE_SYSTEM).encode()).hexdigest(),
               "runs_per_rep": ev.RUNS, "repeats": reps}
    REPEATS_PATH.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {REPEATS_PATH.relative_to(Path.cwd()) if REPEATS_PATH.is_relative_to(Path.cwd()) else REPEATS_PATH}"
          f": {len(results)} repetitions, {sum('error' in r for r in results)} errors")
    if args.write_caches:
        for r in results:
            if r["rep"] == 1 and "error" not in r:
                data = {k: r[k] for k in ("pin", "model", "created_at", "elapsed_s", "k", "combine", "usage",
                                          "runs")}
                if r.get("judge") and "error" not in r["judge"]:
                    data["judge"] = r["judge"]
                ev._write_cache(r["pin"], data)
        print("refreshed caches from repetition 1")


if __name__ == "__main__":
    main()
