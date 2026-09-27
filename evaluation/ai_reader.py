"""Retrospective AI-reader comparison against a declared no-AI keyword baseline.

The team recorded the relevance labels before inspecting these cached outputs
according to the run log, but committed them afterward; this is not a
preregistered or independent test set. They are read only here, never by the
application. The unit of scoring is a distinct public record id, not an
extracted quote: multiple verified quotes from one record do not inflate
retrieval counts.
"""

from __future__ import annotations

import csv
from collections import defaultdict

from evaluation.common import Checks, FIXTURES_DIR, Section, frac, md_table, scope_note, snapshot
from lotline.ai.evidence import cached_digest, keyword_baseline


REFERENCE = FIXTURES_DIR / "record_relevance.csv"


def _reference() -> dict[str, dict[str, bool]]:
    with REFERENCE.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(line for line in fh if not line.startswith("#")))
    out: dict[str, dict[str, bool]] = defaultdict(dict)
    for row in rows:
        out[row["pin"]][row["record_id"]] = row["relevant"] == "Y"
    return dict(out)


def _counts(predicted: set[str], relevant: set[str], universe: set[str]) -> dict[str, int]:
    return {
        "tp": len(predicted & relevant),
        "fp": len(predicted - relevant),
        "fn": len(relevant - predicted),
        "tn": len(universe - relevant - predicted),
    }


def _ratio(n: int, d: int) -> str:
    return frac(n, d) + (f" ({n / d:.1%})" if d else "")


def run() -> Section:
    snap = snapshot()
    reference = _reference()
    checks = Checks()
    parcel_rows = []
    details = []
    totals = {"ai": defaultdict(int), "keyword": defaultdict(int)}
    all_cached = True

    for pin in sorted(reference):
        labels = reference[pin]
        universe = {r.record_id for r in snap.record_text.get(pin, ())}
        relevant = {rid for rid, yes in labels.items() if yes}
        digest = cached_digest(pin, snap)
        all_cached &= digest is not None and digest.status == "cached_verified"
        ai_ids = ({i.record_id for i in digest.items}
                  if digest is not None and digest.status == "cached_verified" else set())
        kw_ids = set(keyword_baseline(pin, snap))
        ai = _counts(ai_ids, relevant, universe)
        kw = _counts(kw_ids, relevant, universe)
        for key in ("tp", "fp", "fn", "tn"):
            totals["ai"][key] += ai[key]
            totals["keyword"][key] += kw[key]
        parcel_rows.append((
            pin, len(universe), len(relevant),
            f"{ai['tp']}/{len(relevant)}", ai["fp"], ai["fn"],
            f"{kw['tp']}/{len(relevant)}", kw["fp"], kw["fn"],
            digest.agreement if digest else "not run",
        ))
        details.append({
            "pin": pin,
            "universe": sorted(universe),
            "relevant": sorted(relevant),
            "ai_ids": sorted(ai_ids),
            "keyword_ids": sorted(kw_ids),
            "ai": ai,
            "keyword": kw,
            "status": digest.status if digest else "not run",
            "agreement": digest.agreement if digest else None,
            "verified_items": len(digest.items) if digest else 0,
            "rejected_items": digest.rejected if digest else 0,
            "elapsed_s": digest.elapsed_s if digest else None,
        })
        checks.check(
            f"reference covers the loaded record universe for {pin}",
            set(labels) == universe,
            f"reference {len(labels)}, loaded {len(universe)}",
        )
        checks.check(
            f"AI surfaced only loaded record ids for {pin}",
            ai_ids <= universe,
            f"surfaced {len(ai_ids)} of {len(universe)}",
        )

    ai_t, kw_t = totals["ai"], totals["keyword"]
    relevant_n = ai_t["tp"] + ai_t["fn"]
    ai_pred_n = ai_t["tp"] + ai_t["fp"]
    kw_pred_n = kw_t["tp"] + kw_t["fp"]
    checks.check("verified caches exist for every labeled parcel", all_cached,
                 f"{sum(d['status'] == 'cached_verified' for d in details)}/{len(details)}")
    # Frozen before inspecting live results: the AI must recover at least as many
    # labeled relevant records and surface fewer irrelevant record ids than grep.
    checks.check("development-set observation: AI matches recall with fewer false positives than B1",
                 ai_t["tp"] >= kw_t["tp"] and ai_t["fp"] < kw_t["fp"],
                 f"AI TP/FP {ai_t['tp']}/{ai_t['fp']}; keyword TP/FP {kw_t['tp']}/{kw_t['fp']}")

    summary_rows = [
        ("Claude + exact-quote verifier", _ratio(ai_t["tp"], relevant_n),
         _ratio(ai_t["tp"], ai_pred_n), ai_t["fp"], ai_t["fn"]),
        ("Keyword/lexicon baseline (no AI)", _ratio(kw_t["tp"], relevant_n),
         _ratio(kw_t["tp"], kw_pred_n), kw_t["fp"], kw_t["fn"]),
    ]
    markdown = "\n\n".join([
        "The reference contains team judgments recorded before the team inspected these cached outputs, "
        "according to the run log, but committed afterward. It is not preregistered. "
        "It covers only the current-condition conflict records in this snapshot. Record-level "
        "precision and recall below are retrospective conformance measures, not model accuracy "
        "or general reliability.",
        md_table(["Method", "Relevant-record recall", "Record precision", "False positives", "Misses"],
                 summary_rows, sort=False),
        md_table(["PIN", "Records", "Relevant", "AI TP/N", "AI FP", "AI FN",
            "Keyword TP/N", "Keyword FP", "Keyword FN", "Repeated-run tuple consistency"],
                 parcel_rows, sort=False),
        checks.markdown(),
        scope_note(
            "This compares retrieval on a tiny, team-labeled, post-build Pittsburgh cohort. "
            "It shows whether constrained Claude retrieval reduces manual record triage relative "
            "to this declared keyword baseline. It does not establish analyst time savings, "
            "decision quality, cross-sale performance or external validity."
        ),
    ])
    return Section(
        id="ai_reader",
        title="AI enforcement-record reader versus no-AI keyword baseline",
        markdown=markdown,
        data={"parcels": details, "totals": {k: dict(v) for k, v in totals.items()}},
        verdict_inputs={
            "labeled_parcels": len(reference),
            "labeled_records": sum(len(x) for x in reference.values()),
            "relevant_records": relevant_n,
            "ai_tp": ai_t["tp"], "ai_fp": ai_t["fp"], "ai_fn": ai_t["fn"],
            "keyword_tp": kw_t["tp"], "keyword_fp": kw_t["fp"], "keyword_fn": kw_t["fn"],
        },
        assertions=checks.items,
    )
