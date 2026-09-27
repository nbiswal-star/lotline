"""Citywide evaluation of the AI enforcement-record reader against structured public data.

Protocol written before model calls according to recorded timestamps, with dated amendments:
docs/validation/ai_scale_protocol.md. It was not externally registered.
Inputs (from ``scripts/fetch_scale_sample.py``): data/validation_scale/{reference,records,sample}.csv.

    uv run python -m evaluation.ai_scale --run [--pass N]   # live: one extraction call per parcel
    uv run python -m evaluation.ai_scale --report           # offline: re-verify cached outputs, write report

The live run reuses the app's reader unchanged (``SYSTEM``, ``SCHEMA``, ``build_prompt``,
``call_structured`` at effort "medium", ``verify_items`` / ``digest_from_runs``); this module
only adapts the record structure and adds one pass per call. Raw model outputs are cached in
data/validation_scale/model_outputs.jsonl, so the report reproduces offline without a key.
The model never sees permit or condemned-list data.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import statistics
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from evaluation.common import REPO_ROOT, Checks, Section, md_table
from evaluation.ai_scale_frozen_evidence import (  # verifier version that produced the cache
    DEMOLITION_DONE,
    normalize,
    LATEST,
    LEXICON,
    SCHEMA,
    SYSTEM,
    build_prompt,
    digest_from_runs,
    verify_items,
)
from lotline.models import RecordText

DATA = REPO_ROOT / "data" / "validation_scale"
OUTPUTS = DATA / "model_outputs.jsonl"
NOTES = DATA / "error_notes.csv"
REPORT = REPO_ROOT / "docs" / "validation" / "ai_scale_results.md"
RESULTS_JSON = DATA / "results.json"
COMMAND = "uv run python -m evaluation.ai_scale --report"

SEED = 20260927
PRICE_IN, PRICE_OUT = 5.00, 25.00  # USD per million tokens, claude-opus-5 list price
BUDGET_USD = 15.0
WORKERS = 6

B4_PATTERN = re.compile(r"\bdemolished\b|\bdemolition\b|\bDP-\d{4}-\d+\b", re.I)
CONTEXT_DONE = re.compile(
    r"\b(?:property|structure|building|house)\s+(?:is|was|has been)\s+"
    r"(?:demolished|razed|removed|torn down|gone)\b|"
    r"\b(?:demolition|demo)\s+(?:is |was |has been )?(?:complete|completed|finished)\b|"
    r"\b(?:demolished|razed|torn down)\b",
    re.I,
)
CONTEXT_NOT_DONE = re.compile(
    r"\b(?:not|never)\b.{0,35}\b(?:demolished|razed|removed|torn down)\b|"
    r"\b(?:must|needs?|should|scheduled|selected|ordered|planned|proposed|awaiting|permit(?:ted)?)\b"
    r".{0,55}\b(?:demolish(?:ed)?|demolition|razed|removed|torn down)\b|"
    r"\b(?:repair(?:ed)?|rehabilitat(?:e|ed))\s+(?:or|/)\s+demolish(?:ed)?\b|"
    r"\bto be\s+(?:demolished|razed|removed|torn down)\b",
    re.I,
)
PERMIT_REF = re.compile(r"\bDP-\d{4}-\d+\b")
DEMO = "DEMOLISHED"
PRESENT = "STRUCTURE_PRESENT"
ABSTAIN = "ABSTAIN"
STRUCT_REMOVED = "structure_removed_or_demolished"


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------


def load_reference() -> list[dict[str, str]]:
    with (DATA / "reference.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_records() -> dict[str, tuple[RecordText, ...]]:
    out: dict[str, list[RecordText]] = defaultdict(list)
    with (DATA / "records.csv").open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[r["pin"]].append(RecordText(
                source_id=r["source_id"], pin=r["pin"], record_id=r["record_id"],
                record_date=r["record_date"] or None, field=r["field"], text=r["text"]))
    return {k: tuple(v) for k, v in out.items()}


def load_sample_meta() -> dict[str, str]:
    with (DATA / "sample.csv").open(newline="", encoding="utf-8") as fh:
        return {r["key"]: r["value"] for r in csv.DictReader(fh)}


def load_outputs(path: Path = OUTPUTS) -> dict[int, dict[str, dict[str, Any]]]:
    """Latest cached line per (pass, pin)."""
    out: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[int(row["pass"])][row["pin"]] = row
    return out


def run_order(reference: list[dict[str, str]]) -> list[str]:
    """Interleave strata so a budget stop leaves both strata equally covered."""
    by = defaultdict(list)
    for r in reference:
        by[r["stratum"]].append(r["pin"])
    a, b = by[DEMO], by["NOT_DEMOLISHED"]
    order: list[str] = []
    for i in range(max(len(a), len(b))):
        order += ([a[i]] if i < len(a) else []) + ([b[i]] if i < len(b) else [])
    return order


# --------------------------------------------------------------------------
# Live run
# --------------------------------------------------------------------------


class _UsageClient:
    """Pass-through to the real client that records the last response's usage."""

    def __init__(self, real: Any) -> None:
        self._real = real
        self.usage: dict[str, int] | None = None
        self.messages = self

    def create(self, **kwargs: Any) -> Any:
        resp = self._real.messages.create(**kwargs)
        u = getattr(resp, "usage", None)
        self.usage = {"input_tokens": getattr(u, "input_tokens", 0) or 0,
                      "output_tokens": getattr(u, "output_tokens", 0) or 0}
        return resp


def cost(usage: dict[str, int] | None) -> float:
    if not usage:
        return 0.0
    return usage["input_tokens"] / 1e6 * PRICE_IN + usage["output_tokens"] / 1e6 * PRICE_OUT


def live_run(pass_no: int, limit: int | None = None) -> None:
    from lotline.ai.client import AIOutputError, AIUnavailable, call_structured, make_client

    reference = load_reference()
    records = load_records()
    cached = load_outputs()
    spent = sum(cost(r.get("usage")) for p in cached.values() for r in p.values())
    todo = [p for p in run_order(reference) if cached.get(pass_no, {}).get(p, {}).get("status") != "ok"]
    if limit:
        todo = todo[:limit]
    print(f"pass {pass_no}: {len(todo)} parcels to run; spend so far ${spent:.2f}")
    lock = threading.Lock()
    state = {"spent": spent, "stopped": False, "done": 0, "in_flight": 0}
    per_call_est = [0.15]

    def one(pin: str) -> None:
        with lock:
            projected = state["spent"] + state["in_flight"] * per_call_est[0]
            if state["stopped"] or projected + per_call_est[0] > BUDGET_USD:
                state["stopped"] = True
                return
            state["in_flight"] += 1
        client = _UsageClient(make_client(timeout_s=300.0))
        prompt = build_prompt(pin, records[pin])
        start = time.perf_counter()
        row: dict[str, Any] = {"pin": pin, "pass": pass_no}
        try:
            resp = call_structured(SYSTEM, prompt, SCHEMA, client=client, effort="medium")
            row.update(status="ok", raw=resp.data, model=resp.model, request_id=resp.request_id)
        except (AIUnavailable, AIOutputError) as exc:
            row.update(status="error", error=str(exc), raw=None, model=None, request_id=None)
        except Exception as exc:  # noqa: BLE001 - recorded, never hidden
            row.update(status="error", error=f"{type(exc).__name__}", raw=None, model=None, request_id=None)
        row["elapsed_s"] = round(time.perf_counter() - start, 2)
        row["usage"] = client.usage
        row["created_at"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        with lock:
            state["in_flight"] -= 1
            state["spent"] += cost(client.usage)
            state["done"] += 1
            done = [cost(client.usage)] if client.usage else []
            if done:
                per_call_est[0] = max(per_call_est[0] * 0.8 + done[0] * 0.2, done[0])
            with OUTPUTS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            print(f"  [{state['done']}/{len(todo)}] {pin} {row['status']} {row['elapsed_s']}s "
                  f"${cost(client.usage):.3f} total ${state['spent']:.2f}", flush=True)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(one, todo))
    if state["stopped"]:
        print(f"STOPPED by budget rule (${BUDGET_USD}); spend ${state['spent']:.2f}")
    print(f"pass {pass_no} finished; cumulative spend ${state['spent']:.2f}")


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def pct(k: int, n: int) -> str:
    if n == 0:
        return "n/a (0/0)"
    lo, hi = wilson(k, n)  # type: ignore[misc]
    return f"{k}/{n} = {k / n:.1%} [{lo:.1%}, {hi:.1%}]"


def f1(tp: int, fp: int, fn: int) -> str:
    d = 2 * tp + fp + fn
    return f"{2 * tp / d:.3f}" if d else "n/a"


def _any(recs: tuple[RecordText, ...], pat: re.Pattern[str]) -> list[RecordText]:
    return [r for r in recs if pat.search(r.text)]


def _latest_casefile(recs: tuple[RecordText, ...]) -> tuple[RecordText, ...]:
    latest: dict[str, str] = defaultdict(str)
    for r in recs:
        latest[r.record_id] = max(latest[r.record_id], r.record_date or "")
    if not latest:
        return ()
    top = max(latest, key=lambda cf: (latest[cf], cf))
    return tuple(r for r in recs if r.record_id == top)


def _contextual_completion(recs: tuple[RecordText, ...]) -> bool:
    """Strong deterministic comparator: completion language minus modal/negated clauses."""
    for rec in recs:
        for clause in re.split(r"(?<=[.!?;])\s+|[\r\n]+", rec.text):
            if CONTEXT_DONE.search(clause) and not CONTEXT_NOT_DONE.search(clause):
                return True
    return False


def baselines(recs: tuple[RecordText, ...]) -> dict[str, str]:
    present = bool(_any(recs, LEXICON["structure_present"]))
    b1 = DEMO if _any(recs, DEMOLITION_DONE) else (PRESENT if present else ABSTAIN)
    vacant_lot_type = any(r.field == "case_file_type" and r.text.strip().lower() == "vacant lots" for r in recs)
    b2 = DEMO if (vacant_lot_type or _any(recs, DEMOLITION_DONE)) else (PRESENT if present else ABSTAIN)
    b3 = DEMO if _any(_latest_casefile(recs), DEMOLITION_DONE) else ABSTAIN
    b4 = DEMO if _any(recs, B4_PATTERN) else ABSTAIN
    b5 = DEMO if _contextual_completion(recs) else ABSTAIN
    kw_s2 = DEMO if _any(recs, LEXICON[STRUCT_REMOVED]) else ABSTAIN
    return {"B1": b1, "B2": b2, "B3": b3, "B4": b4, "B5": b5,
            "KW-S2": kw_s2, "NONE": ABSTAIN}


def _f1_value(c: dict[str, int]) -> float:
    den = 2 * c["tp"] + c["fp"] + c["fn"]
    return 2 * c["tp"] / den if den else 0.0


def paired_bootstrap(systems: dict[str, dict[str, str]], truth: dict[str, str],
                     left: str, right: str, n_boot: int = 4000) -> dict[str, str]:
    """Stratified paired parcel bootstrap; percentile CIs for left-minus-right deltas."""
    strata = [[p for p in sorted(truth) if truth[p] == label] for label in (DEMO, "NOT_DEMOLISHED")]
    rng = random.Random(SEED + 41)
    draws: dict[str, list[float]] = {"precision": [], "recall": [], "f1": [], "discordance": []}
    for _ in range(n_boot):
        sample = [rng.choice(group) for group in strata for _ in range(len(group))]
        vals = []
        for system in (left, right):
            tp = sum(systems[system][p] == DEMO and truth[p] == DEMO for p in sample)
            fp = sum(systems[system][p] == DEMO and truth[p] != DEMO for p in sample)
            fn = sum(systems[system][p] != DEMO and truth[p] == DEMO for p in sample)
            c = {"tp": tp, "fp": fp, "fn": fn}
            vals.append((tp / (tp + fp) if tp + fp else 1.0, tp / (tp + fn), _f1_value(c),
                         fp / len(strata[1])))
        for key, a, b in zip(draws, vals[0], vals[1], strict=True):
            draws[key].append(a - b)
    return {key: f"{statistics.mean(v):+.3f} [{_q(v, .025):+.3f}, {_q(v, .975):+.3f}]"
            for key, v in draws.items()}


@dataclass
class AIRead:
    status: str  # ok | error | not_run | rejected
    items: tuple  # verified EvidenceItems (single run or combined)
    proposed: int
    reasons: tuple[str, ...]
    label_withheld: int


def ai_read(pin: str, recs: tuple[RecordText, ...], rows: list[dict[str, Any] | None],
            mode: str = "single") -> AIRead:
    runs = [r["raw"] for r in rows if r and r.get("status") == "ok" and isinstance(r.get("raw"), dict)]
    if not runs:
        status = "not_run" if all(r is None for r in rows) else "error"
        return AIRead(status, (), 0, (), 0)
    checks = [verify_items(raw, pin, recs) for raw in runs]
    proposed = sum(c.total for c in checks)
    reasons = tuple(x for c in checks for x in c.reasons)
    withheld = sum(c.label_disagreements for c in checks)
    if mode == "union":
        seen, items = set(), []
        for c in checks:
            for i in c.items:
                key = (i.record_id, i.field, i.record_date, i.quote, i.indicates)
                if key not in seen:
                    seen.add(key)
                    items.append(i)
        return AIRead("ok", tuple(items), proposed, reasons, withheld)
    d = digest_from_runs(pin, recs, runs, status_ok="verified", model=None, created_at=None)
    if d.status == "rejected":
        return AIRead("rejected", (), proposed, reasons, withheld)
    return AIRead("ok", d.items, proposed, reasons, withheld)


def _demo_done_items(read: AIRead) -> list:
    return [i for i in read.items if i.indicates == STRUCT_REMOVED and DEMOLITION_DONE.search(i.quote)]


def ai_predictions(read: AIRead) -> dict[str, str]:
    done = _demo_done_items(read)
    present = any(i.indicates == "structure_present" for i in read.items)
    fallback = PRESENT if present else ABSTAIN
    return {
        "AI": DEMO if done else fallback,
        "AI-S1": DEMO if any(i.currency == LATEST for i in done) else fallback,
        "AI-S2": DEMO if any(i.indicates == STRUCT_REMOVED for i in read.items) else fallback,
    }


def confusion(preds: dict[str, str], truth: dict[str, str], cls: str = DEMO, ref: str = DEMO) -> dict[str, int]:
    tp = sum(1 for p in truth if preds[p] == cls and truth[p] == ref)
    fp = sum(1 for p in truth if preds[p] == cls and truth[p] != ref)
    fn = sum(1 for p in truth if preds[p] != cls and truth[p] == ref)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": len(truth) - tp - fp - fn}


def _q(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    return s[min(len(s) - 1, max(0, math.ceil(q * len(s)) - 1))]


def _days(a: str, b: str) -> int | None:
    try:
        return (date.fromisoformat(a) - date.fromisoformat(b)).days
    except (TypeError, ValueError):
        return None


def load_notes() -> dict[str, str]:
    if not NOTES.exists():
        return {}
    with NOTES.open(newline="", encoding="utf-8") as fh:
        return {r["pin"]: r["note"] for r in csv.DictReader(line for line in fh if not line.startswith("#"))}


def _clip(text: str, n: int = 160) -> str:
    t = " ".join(text.split()).replace("|", "/")
    return t if len(t) <= n else t[: n - 1] + "…"


def compute() -> dict[str, Any]:
    reference = load_reference()
    records = load_records()
    outputs = load_outputs()
    meta = load_sample_meta()
    truth = {r["pin"]: r["stratum"] for r in reference}
    ref_by = {r["pin"]: r for r in reference}
    pins = sorted(truth)
    passes = sorted(outputs)
    p1 = outputs.get(1, {})

    systems: dict[str, dict[str, str]] = defaultdict(dict)
    reads: dict[str, AIRead] = {}
    per_parcel = []
    for pin in pins:
        recs = records.get(pin, ())
        read = ai_read(pin, recs, [p1.get(pin)])
        reads[pin] = read
        for k, v in {**ai_predictions(read), **baselines(recs)}.items():
            systems[k][pin] = v
        if len(passes) >= 2:
            rows = [outputs[p].get(pin) for p in passes]
            systems[f"AI-union-k{len(passes)}"][pin] = ai_predictions(ai_read(pin, recs, rows, "union"))["AI"]
            systems[f"AI-intersect-k{len(passes)}"][pin] = ai_predictions(ai_read(pin, recs, rows))["AI"]
        per_parcel.append(pin)

    # --- headline metrics
    order = ["AI", "B1", "B2", "B3", "B4", "B5", "NONE", "AI-S1", "AI-S2", "KW-S2"] + \
        [k for k in systems if k.startswith("AI-union") or k.startswith("AI-intersect")]
    labels = {
        "AI": "LotLine AI reader, k=1 (primary)", "B1": "B1 keyword DEMOLITION_DONE",
        "B2": "B2 structured (Vacant Lots type) + keyword", "B3": "B3 recency + keyword (latest casefile)",
        "B4": "B4 demolished/demolition/DP- rule", "NONE": "No reader (always abstain)",
        "B5": "B5 contextual completion rule (post hoc; negation/modal rejection)",
        "AI-S1": "AI secondary: demolition item is latest record", "AI-S2": "AI secondary: any demolition label",
        "KW-S2": "Keyword secondary: any demolition lexicon hit",
    }
    metrics = {}
    for s in order:
        c = confusion(systems[s], truth)
        n_pos = c["tp"] + c["fn"]
        n_pred = c["tp"] + c["fp"]
        abstain = sum(1 for p in pins if systems[s][p] == ABSTAIN)
        metrics[s] = {**c, "precision": pct(c["tp"], n_pred), "recall": pct(c["tp"], n_pos),
                      "f1": f1(c["tp"], c["fp"], c["fn"]), "abstain": pct(abstain, len(pins)),
                      "specificity": pct(c["tn"], c["tn"] + c["fp"]),
                      "f1_value": (2 * c["tp"] / (2 * c["tp"] + c["fp"] + c["fn"])) if n_pos + n_pred else 0.0}
    best = max(("B1", "B2", "B3", "B4", "B5"), key=lambda s: (metrics[s]["f1_value"], s))
    paired = paired_bootstrap(systems, truth, "AI", best)

    present_rows = []
    for s in ("AI", "B1", "B2"):
        c = confusion(systems[s], truth, PRESENT, "NOT_DEMOLISHED")
        present_rows.append((labels[s], pct(c["tp"], c["tp"] + c["fp"]), pct(c["tp"], c["tp"] + c["fn"])))

    # --- abstention by stratum
    abst_rows = []
    for s in ("AI", "B1", "B2", "B3", "B4", "B5"):
        row = [labels[s]]
        for st in (DEMO, "NOT_DEMOLISHED"):
            ps = [p for p in pins if truth[p] == st]
            dist = Counter(systems[s][p] for p in ps)
            row.append(f"D {dist[DEMO]} / P {dist[PRESENT]} / A {dist[ABSTAIN]}")
        abst_rows.append(tuple(row))

    # --- verifier stats (pass 1)
    ok = [p for p in pins if reads[p].status in ("ok", "rejected")]
    proposed = sum(reads[p].proposed for p in ok)
    rejected = sum(len(reads[p].reasons) for p in ok)
    verified = sum(len(reads[p].items) for p in ok)
    reason_counts = Counter(r for p in ok for r in reads[p].reasons)
    withheld = sum(reads[p].label_withheld for p in ok)
    status_counts = Counter(reads[p].status for p in pins)
    demo_items = [(p, i) for p in ok for i in _demo_done_items(reads[p])]
    wrong_shown = [(p, i) for p, i in demo_items if truth[p] != DEMO]
    indicates_counts = Counter(i.indicates for p in ok for i in reads[p].items)

    # --- cost / latency
    rows1 = [p1[p] for p in pins if p in p1]
    lat = [r["elapsed_s"] for r in rows1 if r.get("status") == "ok"]
    tin = [r["usage"]["input_tokens"] for r in rows1 if r.get("usage")]
    tout = [r["usage"]["output_tokens"] for r in rows1 if r.get("usage")]
    costs = [cost(r.get("usage")) for r in rows1 if r.get("usage")]
    all_cost = sum(cost(r.get("usage")) for p in outputs.values() for r in p.values())
    models = sorted({r.get("model") for r in rows1 if r.get("model")})

    # --- permit mention in input text (blinding check)
    mention_rows = []
    for st in (DEMO, "NOT_DEMOLISHED"):
        ps = [p for p in pins if truth[p] == st]
        any_dp = sum(1 for p in ps if _any(records.get(p, ()), PERMIT_REF))
        cites_ref = sum(1 for p in ps if st == DEMO and any(
            pid in r.text for pid in ref_by[p]["demo_permit_ids"].split(";") if pid for r in records.get(p, ())))
        demo_word = sum(1 for p in ps if _any(records.get(p, ()), LEXICON[STRUCT_REMOVED]))
        done_word = sum(1 for p in ps if _any(records.get(p, ()), DEMOLITION_DONE))
        mention_rows.append((st, len(ps), pct(any_dp, len(ps)),
                             pct(cites_ref, len(ps)) if st == DEMO else "n/a",
                             pct(demo_word, len(ps)), pct(done_word, len(ps))))

    # --- temporal overlap stratification (DEMOLISHED only)
    temporal_rows = []
    for label, cond in (("some PLI record dated on/after first demolition permit issue", True),
                        ("all PLI records dated before first demolition permit issue", False)):
        ps = [p for p in pins if truth[p] == DEMO and (any(
            (r.record_date or "") >= ref_by[p]["demo_first_issue"] for r in records.get(p, ())) == cond)]
        row = [label, len(ps)]
        for s in ("AI", "B1", "B2", "B4"):
            row.append(pct(sum(1 for p in ps if systems[s][p] == DEMO), len(ps)))
        temporal_rows.append(tuple(row))

    # --- demolition date accuracy
    gaps = []
    for p in pins:
        if truth[p] == DEMO and systems["AI"][p] == DEMO:
            dates = sorted(i.record_date for i in _demo_done_items(reads[p]) if i.record_date)
            if dates:
                g = _days(dates[0], ref_by[p]["demo_first_issue"])
                if g is not None:
                    gaps.append(g)

    # --- disagreements AI vs B1 and vs best baseline
    def _kw_evidence(p: str, pat: re.Pattern[str]) -> str:
        hits = _any(records.get(p, ()), pat)
        if not hits:
            return "—"
        h = hits[0]
        m = pat.search(h.text)
        s = max(0, m.start() - 60) if m else 0
        return f"{h.record_id} ({h.record_date}, {h.field}): “{_clip(h.text[s:s + 160])}”"

    def _ai_evidence(p: str) -> str:
        items = _demo_done_items(reads[p])
        if not items:
            return f"no verified demolition-done item (status {reads[p].status}; {len(reads[p].items)} verified items)"
        i = items[0]
        return f"{i.record_id} ({i.record_date}, {i.field}): “{_clip(i.quote)}”"

    disagreements = []
    for p in pins:
        a, b = systems["AI"][p] == DEMO, systems["B1"][p] == DEMO
        if a != b:
            disagreements.append((p, truth[p], "AI only" if a else "B1 only",
                                  "correct" if (a if truth[p] == DEMO else not a) else "wrong",
                                  _ai_evidence(p) if a else _kw_evidence(p, DEMOLITION_DONE)))
    best_dis = Counter()
    for p in pins:
        a, b = systems["AI"][p] == DEMO, systems[best][p] == DEMO
        if a != b:
            best_dis[("AI only" if a else f"{best} only", truth[p])] += 1

    # --- error sample (fixed seed)
    errors = [p for p in pins if (systems["AI"][p] == DEMO) != (truth[p] == DEMO)]
    rng = random.Random(SEED)
    sample_err = sorted(rng.sample(errors, min(10, len(errors))))
    notes = load_notes()
    err_rows = []
    for p in sample_err:
        kind = "FP" if systems["AI"][p] == DEMO else "FN"
        evidence = _ai_evidence(p) if kind == "FP" else (
            _kw_evidence(p, B4_PATTERN) if _any(records.get(p, ()), B4_PATTERN) else "no demolition wording in input")
        ref = ref_by[p]
        refdesc = (f"permit {ref['demo_permit_ids']} issued {ref['demo_first_issue']}" if truth[p] == DEMO
                   else f"condemned since {ref['condemned_create_date']}, no demolition permit")
        latest = max((r.record_date or "" for r in records.get(p, ())), default="")
        err_rows.append((p, kind, refdesc, f"latest PLI {latest}", evidence, notes.get(p, "(not yet annotated)")))

    # --- self-consistency (if ≥2 passes)
    agreement = None
    if len(passes) >= 2:
        dist = Counter()
        pred_agree = 0
        n_both = 0
        for p in pins:
            rows = [outputs[q].get(p) for q in passes]
            if not all(r and r.get("status") == "ok" for r in rows):
                continue
            n_both += 1
            keyed = []
            for r in rows:
                c = verify_items(r["raw"], p, records.get(p, ()))
                keyed.append({(i.record_id, i.field, i.record_date, i.quote, i.indicates) for i in c.items})
            both, either = set.intersection(*keyed), set.union(*keyed)
            ratio = len(both) / len(either) if either else 1.0
            dist["1.0 (identical)" if ratio == 1 else "≥0.5" if ratio >= 0.5 else "<0.5"] += 1
            preds = [ai_predictions(ai_read(p, records.get(p, ()), [r]))["AI"] for r in rows]
            pred_agree += len(set(preds)) == 1
        agreement = {"parcels": n_both, "tuple_jaccard": dict(dist), "prediction_agree": pred_agree}

    calib = calibration(pins, truth, reads, records, systems["AI"])
    withheld_demo = []  # exploratory (post hoc): model said "demolished", lexicon gate withheld the label
    for p in pins:
        row = p1.get(p)
        if not row or row.get("status") != "ok":
            continue
        shown = {i.quote for i in reads[p].items if i.indicates == "unverified_label"}
        qs = sorted({normalize(it.get("quote", "")) for it in row["raw"].get("items", [])
                     if isinstance(it, dict) and it.get("indicates") == STRUCT_REMOVED
                     and normalize(it.get("quote", "")) in shown})
        if qs:
            withheld_demo.append((p, truth[p], systems["AI"][p], _clip(qs[0], 110)))
    current = current_app_verifier(pins, truth, records, p1)
    layer_ablation = current_app_layer_ablation(pins, truth, records, p1)

    return {
        "calib": calib, "current": current, "layer_ablation": layer_ablation,
        "withheld_demo": withheld_demo,
        "meta": meta, "pins": pins, "truth": truth, "systems": {k: dict(v) for k, v in systems.items()},
        "labels": labels, "order": order, "metrics": metrics, "best": best, "present_rows": present_rows,
        "abst_rows": abst_rows, "status_counts": dict(status_counts), "proposed": proposed,
        "rejected": rejected, "verified": verified, "reason_counts": dict(reason_counts),
        "withheld": withheld, "demo_items": len(demo_items), "wrong_shown": len(wrong_shown),
        "wrong_shown_examples": [(p, i.record_id, i.record_date, _clip(i.quote)) for p, i in wrong_shown[:5]],
        "indicates_counts": dict(indicates_counts),
        "latency": lat, "tin": tin, "tout": tout, "costs": costs, "all_cost": all_cost, "models": models,
        "passes": passes, "mention_rows": mention_rows, "temporal_rows": temporal_rows, "gaps": gaps,
        "disagreements": disagreements, "best_dis": {f"{k[0]} | ref {k[1]}": v for k, v in best_dis.items()},
        "err_rows": err_rows, "n_errors": len(errors), "agreement": agreement, "paired": paired,
        "n_records": {p: len({r.record_id for r in records.get(p, ())}) for p in pins},
    }


def current_app_verifier(pins: list[str], truth: dict[str, str], records: dict[str, tuple[RecordText, ...]],
                         p1: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Sensitivity: the app's *current* verifier (lotline.ai.evidence) on the same cached pass-1 outputs.

    No new model calls. The app module changes over time, so this is labelled with its hash.
    """
    import hashlib

    try:
        import lotline.ai.evidence as cur
    except Exception as exc:  # noqa: BLE001
        return {"error": type(exc).__name__}
    try:
        digest = hashlib.sha256(Path(cur.__file__).read_bytes()).hexdigest()[:12]
        prompt_diff = sum(cur.build_prompt(p, records.get(p, ())) != build_prompt(p, records.get(p, ()))
                          for p in pins)
        system_same = cur.SYSTEM == SYSTEM and cur.SCHEMA == SCHEMA
        preds, proposed, verified = {}, 0, 0
        for p in pins:
            row = p1.get(p)
            if not row or row.get("status") != "ok":
                preds[p] = ABSTAIN
                continue
            d = cur.digest_from_runs(p, records.get(p, ()), [row["raw"]], status_ok="verified",
                                     model=None, created_at=None)
            items = d.items if d.status == "verified" else ()
            verified += len(items)
            proposed += d.rejected + len(items)
            done = [i for i in items if i.indicates == STRUCT_REMOVED and cur.DEMOLITION_DONE.search(i.quote)]
            preds[p] = DEMO if done else ABSTAIN
        c = confusion(preds, truth)
        return {"sha": digest, "prompt_diff": prompt_diff, "system_same": system_same, **c,
                "precision": pct(c["tp"], c["tp"] + c["fp"]), "recall": pct(c["tp"], c["tp"] + c["fn"]),
                "f1": f1(c["tp"], c["fp"], c["fn"])}
    except Exception as exc:  # noqa: BLE001 - app API drift is reported, never hidden
        return {"error": f"{type(exc).__name__}: {exc}"}


def current_app_layer_ablation(
    pins: list[str], truth: dict[str, str], records: dict[str, tuple[RecordText, ...]],
    p1: dict[str, dict[str, Any]],
) -> list[tuple[str, str, str, str, str]]:
    """Replay cached raw proposals with one deterministic verifier layer disabled at a time.

    This evaluates the current verifier on the frozen k=1 proposals without an entailment-judge
    call. It is a genuine counterfactual code ablation, but not an evaluation of the live k=3 stack.
    """
    try:
        import lotline.ai.evidence as cur
    except Exception as exc:  # noqa: BLE001
        return [(f"unavailable: {type(exc).__name__}", "—", "—", "—", "—")]

    def score(off: frozenset[str]) -> tuple[dict[str, int], int]:
        preds: dict[str, str] = {}
        shown = 0
        for pin in pins:
            row = p1.get(pin)
            if not row or row.get("status") != "ok":
                preds[pin] = ABSTAIN
                continue
            d = cur.digest_from_runs(
                pin, records.get(pin, ()), [row["raw"]], status_ok="verified",
                model=None, created_at=None, judge=False, off=off,
            )
            items = d.items if d.status == "verified" else ()
            shown += len(items)
            done = [i for i in items if i.indicates == STRUCT_REMOVED and cur.DEMOLITION_DONE.search(i.quote)]
            preds[pin] = DEMO if done else ABSTAIN
        return confusion(preds, truth), shown

    rows = []
    for label, off in [("all deterministic layers", frozenset())] + [
        (f"without {layer}", frozenset({layer}))
        for layer in ("provenance", "substring", "boundary", "negation", "attribution",
                      "injection", "lexicon", "permit")
    ]:
        c, shown = score(off)
        rows.append((label, f"{c['tp']}/{c['fp']}/{c['fn']}/{c['tn']}",
                     f1(c["tp"], c["fp"], c["fn"]), str(shown), ""))
    base_fp = int(rows[0][1].split("/")[1])
    return [(label, counts, score_f1, shown, f"{int(counts.split('/')[1]) - base_fp:+d}")
            for label, counts, score_f1, shown, _ in rows]


# --------------------------------------------------------------------------
# Calibration (protocol Amendment 3)
# --------------------------------------------------------------------------

CALIB_JSON = REPO_ROOT / "data" / "calibration" / "reader_calibration.json"
RELIABILITY_PNG = REPO_ROOT / "docs" / "validation" / "ai_scale_reliability.png"
FEATURES = ("demo_done", "log_demo_items", "log_present_items", "demo_in_latest")
FEATURE_DEFS = {
    "demo_done": "1 if >=1 verified structure_removed_or_demolished item whose quote matches DEMOLITION_DONE",
    "log_demo_items": "ln(1 + number of verified items labelled structure_removed_or_demolished)",
    "log_present_items": "ln(1 + number of verified items labelled structure_present)",
    "demo_in_latest": "1 if a verified demolition-labelled item is from the parcel's most recent casefile",
}
LAMBDA = 1.0
N_BINS = 5
N_BOOT = 2000


def parcel_features(read: AIRead, recs: tuple[RecordText, ...]) -> dict[str, float]:
    latest = _latest_casefile(recs)
    latest_id = latest[0].record_id if latest else None
    demo = [i for i in read.items if i.indicates == STRUCT_REMOVED]
    return {
        "demo_done": 1.0 if _demo_done_items(read) else 0.0,
        "log_demo_items": math.log1p(len(demo)),
        "log_present_items": math.log1p(sum(1 for i in read.items if i.indicates == "structure_present")),
        "demo_in_latest": 1.0 if any(i.record_id == latest_id for i in demo) else 0.0,
    }


def split(pins: list[str], truth: dict[str, str]) -> tuple[list[str], list[str]]:
    rng = random.Random(SEED)
    cal, held = [], []
    for st in (DEMO, "NOT_DEMOLISHED"):
        ps = sorted(p for p in pins if truth[p] == st)
        rng.shuffle(ps)
        k = round(0.6 * len(ps))
        cal += ps[:k]
        held += ps[k:]
    return sorted(cal), sorted(held)


def fit_logistic(X: list[list[float]], y: list[int], lam: float = LAMBDA) -> tuple[float, list[float]]:
    import numpy as np

    A = np.hstack([np.ones((len(X), 1)), np.array(X, dtype=float)])
    t = np.array(y, dtype=float)
    w = np.zeros(A.shape[1])
    pen = np.eye(A.shape[1]) * lam
    pen[0, 0] = 0.0
    for _ in range(100):
        p = 1 / (1 + np.exp(-A @ w))
        g = A.T @ (p - t) + pen @ w
        H = A.T @ (A * (p * (1 - p))[:, None]) + pen
        step = np.linalg.solve(H, g)
        w -= step
        if np.max(np.abs(step)) < 1e-10:
            break
    return float(w[0]), [float(v) for v in w[1:]]


def predict(intercept: float, coefs: list[float], x: list[float]) -> float:
    z = intercept + sum(c * v for c, v in zip(coefs, x))
    return 1 / (1 + math.exp(-z))


def ece(probs: list[float], ys: list[int], bins: int = N_BINS) -> float:
    total = 0.0
    for b in range(bins):
        idx = [i for i, p in enumerate(probs) if (b / bins <= p < (b + 1) / bins) or (b == bins - 1 and p == 1.0)]
        if idx:
            conf = sum(probs[i] for i in idx) / len(idx)
            acc = sum(ys[i] for i in idx) / len(idx)
            total += len(idx) / len(probs) * abs(conf - acc)
    return total


def brier(probs: list[float], ys: list[int]) -> float:
    return sum((p - y) ** 2 for p, y in zip(probs, ys)) / len(ys)


def reliability(probs: list[float], ys: list[int], bins: int = N_BINS) -> list[tuple]:
    rows = []
    for b in range(bins):
        idx = [i for i, p in enumerate(probs) if (b / bins <= p < (b + 1) / bins) or (b == bins - 1 and p == 1.0)]
        if idx:
            rows.append((f"[{b / bins:.1f}, {(b + 1) / bins:.1f}{']' if b == bins - 1 else ')'}", len(idx),
                         round(sum(probs[i] for i in idx) / len(idx), 3), round(sum(ys[i] for i in idx) / len(idx), 3)))
        else:
            rows.append((f"[{b / bins:.1f}, {(b + 1) / bins:.1f}{']' if b == bins - 1 else ')'}", 0, "—", "—"))
    return rows


def boot_ci(probs: list[float], ys: list[int], fn: Any) -> tuple[float, float]:
    rng = random.Random(SEED)
    n = len(ys)
    vals = []
    for _ in range(N_BOOT):
        idx = [rng.randrange(n) for _ in range(n)]
        vals.append(fn([probs[i] for i in idx], [ys[i] for i in idx]))
    vals.sort()
    return vals[int(0.025 * N_BOOT)], vals[int(0.975 * N_BOOT) - 1]


def calibration(pins: list[str], truth: dict[str, str], reads: dict[str, AIRead],
                records: dict[str, tuple[RecordText, ...]], ai_pred: dict[str, str]) -> dict[str, Any] | None:
    if any(reads[p].status == "not_run" for p in pins):
        return None
    feats = {p: parcel_features(reads[p], records.get(p, ())) for p in pins}
    y = {p: int(truth[p] == DEMO) for p in pins}
    cal, held = split(pins, truth)
    intercept, coefs = fit_logistic([[feats[p][f] for f in FEATURES] for p in cal], [y[p] for p in cal])
    yh = [y[p] for p in held]
    systems = {
        "calibrated (logistic, 4 features)": [predict(intercept, coefs, [feats[p][f] for f in FEATURES]) for p in held],
        "raw binary AI decision (1.0 / 0.0)": [1.0 if ai_pred[p] == DEMO else 0.0 for p in held],
        "constant 0.5 (sample prevalence)": [0.5 for _ in held],
    }
    out_rows, rel = [], {}
    for name, probs in systems.items():
        e, b = ece(probs, yh), brier(probs, yh)
        elo, ehi = boot_ci(probs, yh, ece)
        blo, bhi = boot_ci(probs, yh, brier)
        out_rows.append((name, f"{e:.3f} [{elo:.3f}, {ehi:.3f}]", f"{b:.3f} [{blo:.3f}, {bhi:.3f}]"))
        rel[name] = reliability(probs, yh)
    cal_probs = systems["calibrated (logistic, 4 features)"]
    item_rows = Counter()
    for p in pins:
        latest = {}
        for r in records.get(p, ()):
            latest[r.record_id] = max(latest.get(r.record_id, ""), r.record_date or "")
        rank = {cf: i for i, cf in enumerate(sorted(latest, key=lambda c: (latest[c], c), reverse=True))}
        for i in reads[p].items:
            if i.indicates == STRUCT_REMOVED:
                bucket = "latest casefile" if rank.get(i.record_id) == 0 else "older casefile"
                item_rows[(bucket, "DEMOLISHED" if y[p] else "NOT_DEMOLISHED")] += 1
    return {
        "features": FEATURES, "intercept": intercept, "coefs": coefs, "n_cal": len(cal), "n_held": len(held),
        "rows": out_rows, "reliability": rel, "held_probs": cal_probs, "held_y": yh,
        "raw_probs": systems["raw binary AI decision (1.0 / 0.0)"],
        "item_rows": sorted((k[0], k[1], v) for k, v in item_rows.items()),
        "feature_means": {f: (round(statistics.mean(feats[p][f] for p in pins if y[p]), 3),
                              round(statistics.mean(feats[p][f] for p in pins if not y[p]), 3)) for f in FEATURES},
    }


def write_calibration_artifacts(c: dict[str, Any], meta: dict[str, str]) -> None:
    CALIB_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "reader-calibration-v1",
        "created": "2026-09-27",
        "model": "claude-opus-5 via lotline.ai.evidence (k=1 extraction, effort medium)",
        "target": "P(City data record a completed demolition | reader output) for a parcel that is either "
                  "a completed-demolition parcel or an active condemned structure (protocol docs/validation/ai_scale_protocol.md)",
        "form": "logistic: p = 1 / (1 + exp(-(intercept + sum(coef_i * feature_i))))",
        "intercept": round(c["intercept"], 6),
        "coefficients": {f: round(v, 6) for f, v in zip(c["features"], c["coefs"])},
        "feature_definitions": FEATURE_DEFS,
        "excluded_features": {
            "k_run_agreement": "unavailable: k=1 (budget rule)",
            "entailment_judge": "not present in lotline/ai/evidence.py at registration",
            "permit_corroboration": "excluded: reference is permit-derived (leakage); not in the PLI-only input",
        },
        "l2_lambda": LAMBDA,
        "n_calibration": c["n_cal"], "n_heldout": c["n_held"],
        "split": f"by parcel, stratified, random.Random({SEED}), 60/40",
        "heldout_metrics": {name: {"ece_5bin": ev, "brier": bv} for name, ev, bv in c["rows"]},
        "prevalence_note": "Fitted on a balanced 50/50 sample. For a population with prevalence pi, add "
                           "ln(pi / (1 - pi)) to the intercept before applying.",
        "limits": "n=90 calibration / 60 held-out parcels; one city; extreme strata only; reference noise "
                  "(permit status is not a completion date; condemned list can lag). Evidence for a human "
                  "reviewer; never a site-condition fact.",
        "sample_fetched_utc": meta.get("fetch_finished_utc"),
    }
    CALIB_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_reliability_png(c: dict[str, Any]) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001 - optional; report still regenerates without it
        return False
    fig, ax = plt.subplots(figsize=(5.2, 5.0), dpi=150)
    ax.plot([0, 1], [0, 1], color="#9a9a9a", lw=1, ls="--", label="perfect calibration")
    styles = {"calibrated (logistic, 4 features)": ("#2a6fdb", "o", (8, -4)),
              "raw binary AI decision (1.0 / 0.0)": ("#d9731a", "s", (-44, -16))}
    for name, (color, marker, offset) in styles.items():
        pts = [(r[2], r[3], r[1]) for r in c["reliability"][name] if r[1]]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color, marker=marker, ms=8, lw=2, label=name,
                clip_on=False, zorder=3)
        for x, yv, n in pts:
            ax.annotate(f"n={n}", (x, yv), textcoords="offset points", xytext=offset, fontsize=8, color="#444")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Predicted P(demolished)")
    ax.set_ylabel("Observed share demolished (City permit data)")
    ax.set_title(f"Reader reliability, held-out parcels (n={c['n_held']})", fontsize=10)
    ax.grid(color="#e6e6e6", lw=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(RELIABILITY_PNG)
    plt.close(fig)
    return True


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

DISCUSSION_FILE = DATA / "discussion.md"


def render(r: dict[str, Any]) -> str:
    m, L = r["metrics"], r["labels"]
    n = len(r["pins"])
    n_demo = sum(1 for p in r["pins"] if r["truth"][p] == DEMO)
    meta = r["meta"]

    def stat(v: list[float], fmt: str) -> str:
        if not v:
            return "n/a"
        return f"mean {format(statistics.mean(v), fmt)}, p95 {format(_q(v, 0.95), fmt)}, max {format(max(v), fmt)}"

    lines = [
        "# AI record reader at citywide scale: results",
        "",
        "<!-- GENERATED FILE: regenerate offline with the command below; do not edit by hand. -->",
        "",
        f"- Command: `{COMMAND}` (reads cached model outputs; no API key or network needed)",
        "- Protocol: [`ai_scale_protocol.md`](ai_scale_protocol.md) (written before model calls according to recorded timestamps; not externally registered)",
        f"- Sample fetched from WPRDC: {meta.get('fetch_started_utc')} – {meta.get('fetch_finished_utc')}; seed {meta.get('seed')}",
        f"- Model: {', '.join(r['models']) or 'n/a'}; extraction passes cached: {r['passes'] or 'none'}",
        "- **Status: development-set estimate of one derived parcel rule, not a benchmark.**",
        "",
        "## Sample",
        "",
        md_table(["Stratum (reference)", "Candidates", "Screened (random order)", "No PLI free text", "Sampled"], [
            (st, meta.get(f"{st}_candidates"), meta.get(f"{st}_screened"),
             meta.get(f"{st}_ineligible_no_free_text"), meta.get(f"{st}_sampled"))
            for st in (DEMO, "NOT_DEMOLISHED")], sort=False),
        "",
        "Reference: DEMOLISHED = completed COMPLETE/CITY FUNDED demolition permit, not on the condemned list, "
        "no later new-construction permit. NOT_DEMOLISHED = active condemned-list entry and no demolition permit "
        "of any status. Excluded as ambiguous before sampling: " + "; ".join(
            f"{k.removeprefix('excluded_').replace('_', ' ')} {v}" for k, v in sorted(meta.items()) if k.startswith("excluded_"))
        + f". Person-name screen dropped {meta.get('text_fields_dropped_person_screen')} text fields.",
        "",
        f"Casefiles per parcel given to the reader (cap 40): median {statistics.median(r['n_records'].values()):.0f}, "
        f"max {max(r['n_records'].values())}.",
        "",
        "## Headline: DEMOLISHED detection at parcel level (95% Wilson intervals)",
        "",
        f"n = {n} parcels ({n_demo} DEMOLISHED, {n - n_demo} NOT_DEMOLISHED). Balanced sampling fixes prevalence at "
        "50%, so precision here is not the precision at citywide prevalence.",
        "",
        md_table(["System", "Precision", "Recall", "F1", "Specificity", "TP/FP/FN/TN", "Abstain (all parcels)"], [
            (L[s], m[s]["precision"], m[s]["recall"], m[s]["f1"], m[s]["specificity"],
             f"{m[s]['tp']}/{m[s]['fp']}/{m[s]['fn']}/{m[s]['tn']}", m[s]["abstain"]) for s in r["order"]], sort=False),
        "",
        f"Strongest baseline by F1 in this development analysis: **{L[r['best']]}**. "
        "B5 is post hoc; B1–B4 were timestamped before calls. AI-vs-best disagreements: "
        + (", ".join(f"{k}: {v}" for k, v in sorted(r["best_dis"].items())) or "none") + ".",
        "",
        "Paired stratified parcel bootstrap (4,000 resamples), AI minus the best simple baseline. "
        "Intervals are descriptive development-set uncertainty, not external-validity intervals:",
        "",
        md_table(["Metric delta", "Mean [2.5%, 97.5%]"],
                 [(k, v) for k, v in r["paired"].items()], sort=False),
        "",
        "Secondary: STRUCTURE_PRESENT prediction against NOT_DEMOLISHED.",
        "",
        md_table(["System", "Precision", "Recall"], r["present_rows"], sort=False),
        "",
        "Prediction distribution by stratum (D = DEMOLISHED, P = STRUCTURE_PRESENT, A = ABSTAIN):",
        "",
        md_table(["System", "Reference DEMOLISHED", "Reference NOT_DEMOLISHED"], r["abst_rows"], sort=False),
        "",
        "## Automatically checkable metrics (pass 1)",
        "",
        md_table(["Metric", "Value"], [
            ("Reader status per parcel", ", ".join(f"{k} {v}" for k, v in sorted(r["status_counts"].items()))),
            ("Proposed items (all parcels)", r["proposed"]),
            ("Verification pass rate (verified / proposed)", pct(r["verified"], r["proposed"])),
            ("Verified-item rejection rate", pct(r["rejected"], r["proposed"])),
            ("Verified items whose model label was withheld (lexicon disagreed → `unverified_label`)", r["withheld"]),
            ("Verified demolition-done items shown", r["demo_items"]),
            ("Wrong-and-shown rate (demolition-done items on NOT_DEMOLISHED parcels / all shown)",
             pct(r["wrong_shown"], r["demo_items"])),
        ], sort=False),
        "",
        "First-failing verifier checks (descriptive rejection counts, not a counterfactual layer ablation):",
        "",
        md_table(["Verifier check", "Items dropped"], sorted(r["reason_counts"].items(), key=lambda kv: (-kv[1], kv[0])),
                 sort=False) if r["reason_counts"] else "No proposed item was rejected.",
        "",
        "Counterfactual verifier-layer ablation on the cached k=1 raw proposals, using the current "
        "deterministic verifier without an entailment-judge call. Each row disables exactly one layer:",
        "",
        md_table(["Replay", "TP/FP/FN/TN", "F1", "Items shown", "FP change"],
                 r["layer_ablation"], sort=False),
        "",
        "Verified item labels: " + ", ".join(f"{k} {v}" for k, v in sorted(r["indicates_counts"].items())) + ".",
        "",
    ]
    if r["wrong_shown_examples"]:
        lines += ["Wrong-and-shown examples (verified demolition-done quote on a parcel the City data record as a "
                  "active-condemned/no-demolition-permit proxy):", "",
                  md_table(["PIN", "Record", "Date", "Quote"], r["wrong_shown_examples"], sort=False), ""]
    lines += [
        "## Cost and latency (pass 1, per parcel)",
        "",
        md_table(["Measure", "Value"], [
            ("Wall-clock latency (s), successful calls", stat(r["latency"], ".1f")),
            ("Input tokens", stat(r["tin"], ".0f")),
            ("Output tokens (incl. thinking)", stat(r["tout"], ".0f")),
            ("Cost (USD at $5/$25 per M tokens)", stat(r["costs"], ".3f")),
            ("Total spend, all cached passes (USD)", f"{r['all_cost']:.2f}"),
        ], sort=False),
        "",
        "## Blinding check: does the input text itself mention demolition or a permit?",
        "",
        md_table(["Stratum", "n", "Any DP- permit ref", "Cites the reference permit id",
                  "Any demolition lexicon hit", "Any demolition-done wording"], r["mention_rows"], sort=False),
        "",
        "## Temporal overlap (DEMOLISHED parcels; recall)",
        "",
        md_table(["PLI text timing vs first demolition permit", "n", "AI", "B1", "B2", "B4"], r["temporal_rows"], sort=False),
        "",
        "## Demolition-date agreement",
        "",
        ("The permits data carries no completion date, so the earliest qualifying permit issue date is used. "
         f"For {len(r['gaps'])} AI true positives, (earliest verified demolition-done record date − permit issue date) "
         f"in days: median {statistics.median(r['gaps']):.0f}, IQR "
         f"[{_q(r['gaps'], 0.25):.0f}, {_q(r['gaps'], 0.75):.0f}], "
         f"{sum(1 for g in r['gaps'] if g < 0)} dated before the permit issue date, "
         f"{sum(1 for g in r['gaps'] if 0 <= g <= 365)} within a year after it."
         if r["gaps"] else "No AI true positive carried a dated demolition-done item."),
        "",
        "## AI vs keyword (B1) disagreements",
        "",
        md_table(["PIN", "Reference", "Who says DEMOLISHED", "AI outcome", "Evidence (record, date, field, quote)"],
                 r["disagreements"], sort=False) if r["disagreements"] else "None.",
        "",
        f"## Error analysis ({len(r['err_rows'])} of {r['n_errors']} AI errors, fixed-seed sample)",
        "",
        md_table(["PIN", "Type", "Reference", "Latest text", "Evidence", "Analyst note (written after results)"],
                 r["err_rows"], sort=False) if r["err_rows"] else "No AI errors.",
        "",
    ]
    if r["agreement"]:
        a = r["agreement"]
        lines += ["## Self-consistency across passes", "",
                  f"Parcels with all passes successful: {a['parcels']}. Verified-tuple Jaccard distribution: "
                  + ", ".join(f"{k}: {v}" for k, v in sorted(a["tuple_jaccard"].items()))
                  + f". Parcel prediction identical across passes: {pct(a['prediction_agree'], a['parcels'])}.", ""]
    else:
        lines += ["## Self-consistency", "",
                  "Only one extraction pass was run (k=1). The current app's three-run union and same-model "
                  "entailment check were not applied, so this study does not estimate live-runtime stability or "
                  "performance.", ""]
    wd = r["withheld_demo"]
    lines += ["## Exploratory (post hoc): demolition labels withheld by the lexicon gate", "",
              "Post hoc; found during error analysis. Parcels where the model labelled a verbatim quote "
              "`structure_removed_or_demolished` but the verifier withheld the label because the keyword lexicon "
              f"did not match: {sum(1 for x in wd if x[1] == DEMO)} DEMOLISHED vs "
              f"{sum(1 for x in wd if x[1] != DEMO)} NOT_DEMOLISHED parcels.", ""]
    if wd:
        lines += [md_table(["PIN", "Reference", "AI primary prediction", "Withheld quote"], wd, sort=False), ""]
    cur = r.get("current")
    if cur:
        lines += ["## Verifier-version sensitivity", "",
                  "Primary scoring uses `evaluation/ai_scale_frozen_evidence.py`, a frozen copy of the app verifier "
                  "that produced the cached outputs (app file as of 06:55 ET; pass 1 ran 07:07–07:10 ET). The app's "
                  "`lotline/ai/evidence.py` changed at 07:11 ET (union-of-k, entailment judge, new verifier layers). "
                  "Re-verifying the same cached pass-1 outputs with the current app verifier (k=1, no judge call):", ""]
        if "error" in cur:
            lines += [f"Not computable against the current app module: {cur['error']}.", ""]
        else:
            lines += [md_table(["Verifier", "Precision", "Recall", "F1", "TP/FP/FN/TN"], [
                ("frozen (primary)", m["AI"]["precision"], m["AI"]["recall"], m["AI"]["f1"],
                 f"{m['AI']['tp']}/{m['AI']['fp']}/{m['AI']['fn']}/{m['AI']['tn']}"),
                (f"current app (sha256 {cur['sha']}…)", cur["precision"], cur["recall"], cur["f1"],
                 f"{cur['tp']}/{cur['fp']}/{cur['fn']}/{cur['tn']}")], sort=False), "",
                f"System prompt and schema identical between versions: {cur['system_same']}. Per-parcel user "
                f"prompt differs for {cur['prompt_diff']}/{len(r['pins'])} parcels (the current app withholds more "
                "records as instruction-like), so the current app would not send exactly the cached input there.", ""]
    c = r.get("calib")
    if c:
        lines += [
            "## Calibrated confidence (protocol Amendment 3)",
            "",
            f"Parcel-level logistic calibrator (L2 λ={LAMBDA}) fitted on {c['n_cal']} calibration parcels, "
            f"evaluated on {c['n_held']} held-out parcels (split by parcel, stratified, seed {SEED}). "
            "k-run agreement is unavailable (k=1); permit corroboration is excluded (leakage); no entailment judge exists. "
            "Artifact: `data/calibration/reader_calibration.json`. Diagram: "
            "[`ai_scale_reliability.png`](ai_scale_reliability.png).",
            "",
            md_table(["Feature", "Coefficient", "Mean (DEMOLISHED)", "Mean (NOT_DEMOLISHED)"], [
                (f, f"{v:+.3f}", c["feature_means"][f][0], c["feature_means"][f][1])
                for f, v in zip(c["features"], c["coefs"])] + [("intercept", f"{c['intercept']:+.3f}", "", "")],
                sort=False),
            "",
            md_table(["Held-out scorer", "ECE (5 bins) [bootstrap 95% CI]", "Brier [bootstrap 95% CI]"],
                     c["rows"], sort=False),
            "",
            "Reliability table, held-out (bin, n, mean predicted, observed share DEMOLISHED):",
            "",
        ]
        for name in ("calibrated (logistic, 4 features)", "raw binary AI decision (1.0 / 0.0)"):
            lines += [f"*{name}*", "", md_table(["Bin", "n", "Mean predicted", "Observed"], c["reliability"][name],
                                                sort=False), ""]
        lines += ["Item level (descriptive, all parcels): verified demolition-labelled items by casefile recency "
                  "and parcel reference.", "",
                  md_table(["Item casefile", "Parcel reference", "Items"], c["item_rows"], sort=False), ""]
    if DISCUSSION_FILE.exists():
        lines += [DISCUSSION_FILE.read_text(encoding="utf-8").rstrip(), ""]
    return "\n".join(lines).rstrip() + "\n"


def write_report(path: Path = REPORT) -> dict[str, Any]:
    r = compute()
    path.write_text(render(r), encoding="utf-8")
    if r.get("calib") and path == REPORT:
        write_calibration_artifacts(r["calib"], r["meta"])
        write_reliability_png(r["calib"])
    return r


def run() -> Section:
    """Harness section: offline, from cached outputs only."""
    r = compute()
    checks = Checks()
    m = r["metrics"]
    checks.check("cached pass-1 output exists for every sampled parcel",
                 r["status_counts"].get("not_run", 0) == 0, f"{r['status_counts']}")
    checks.check("no-reader control never predicts DEMOLISHED", m["NONE"]["tp"] + m["NONE"]["fp"] == 0)
    md = "\n\n".join([
        f"Citywide development-set estimate (n={len(r['pins'])} parcels, reference = City permit and "
        "condemned-list data, not team labels). Full report: `docs/validation/ai_scale_results.md`.",
        md_table(["System", "Precision", "Recall", "F1"], [
            (r["labels"][s], m[s]["precision"], m[s]["recall"], m[s]["f1"])
            for s in ("AI", "B1", "B2", "B3", "B4", "B5")],
            sort=False),
        checks.markdown(),
    ])
    return Section(id="ai_scale", title="AI reader at citywide scale vs structured public reference",
                   markdown=md, data={k: r["metrics"][k] for k in ("AI", "B1", "B2", "B3", "B4", "B5")},
                   verdict_inputs={"n": len(r["pins"]), "best_baseline": r["best"]}, assertions=checks.items)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--pass", dest="pass_no", type=int, default=1)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)
    if args.run:
        live_run(args.pass_no, args.limit)
    if args.report or not args.run:
        r = write_report()
        RESULTS_JSON.write_text(json.dumps({k: r[k] for k in ("metrics", "status_counts", "reason_counts", "best",
                                                             "proposed", "rejected", "verified", "wrong_shown",
                                                             "demo_items", "gaps", "all_cost", "agreement")},
                                           indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
        m = r["metrics"]
        for s in ("AI", "B1", "B2", "B3", "B4", "B5"):
            print(f"{s:5} P {m[s]['precision']:32} R {m[s]['recall']:32} F1 {m[s]['f1']}")
        print(f"wrote {REPORT.relative_to(REPO_ROOT)}; spend ${r['all_cost']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
