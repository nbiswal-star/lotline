# Scientific validation: what the evidence supports

**Scope.** This is retrospective internal validation of a decision-support method on one dated Pittsburgh Treasurer Sale snapshot. The evaluated construct is conformance to LotLine's declared screening policy: source reconciliation, selective abstention under conflict or missingness, bounded score uncertainty, and explicit human routing. It is not total development feasibility, legal or zoning ground truth, financial viability, predictive performance, or external validation.

Reproduce the complete artifact with:

```bash
uv run python -m evaluation.run
```

The command writes the parcel-level tables, denominators, exceptions, assertions, hashes and limitations to `docs/validation/results.md` and `docs/validation/results.json`.

## Hypothesis verdicts

| Hypothesis | Verdict | Observed evidence | Boundary of the claim |
|---|---|---|---|
| H1 — cohort reconstruction | supported within scope | An evaluation-only join reconstructed 96 source records, 77 advertised records, 19 routed non-advertised records, 63 structures and 14 vacant lots; PIN and price checks agreed 77/77; 2 disclosed exception rows and 0 unexpected exceptions. | Both joins use the same committed snapshots; upstream extraction and source completeness are not independently reproduced. |
| H2 — conflict-sensitive abstention | supported within scope | All 3 critical-conflict parcels leaked 0 scores; no parcel with a withheld component advanced; the 14-lot outcome matrix is 7 / 3 / 3 / 1. | Detects only conflicts represented in loaded sources and declared policy. |
| H3 — unknown is not zero | supported within scope | Across 105 single-input missingness injections on 7 advancing parcels: 0/105 advanced, 0/105 created a known zero, 105/105 withheld the expected component, and 42/42 negative controls were unchanged. | Simultaneous missingness and wrong-but-present values are not exhaustively tested. |
| H4 — policy traceability and boundary behavior | supported within scope | 28/28 declared adjacent boundary pairs changed only the permitted downstream outputs; every runtime rule value is cited data or explicit policy. | This tests implementation of thresholds, not whether the policy thresholds are normatively correct. |
| H5 — language-layer fidelity | supported within scope | Runtime claim-ID protocol and cache produced 0 semantic false accepts in 862 enumerated checks; engine results changed in 0 model-behavior cases. Free prose alone accepted 38/136 hostile statements, which is why runtime never accepts model prose. | Enumerated synthetic attacks are not an estimate of real-model reliability. |
| H6 — structural actionability | supported within scope | Every one of 14 screened lots had a named first resolver; missingness injections named the affected input and an owner in 105/105 cases. | Presence is established; practitioner correctness, usability and time savings require a pilot. |

## AI-native claim and no-AI counterfactual

The AI contribution is not the parcel decision. It is semantic retrieval from changing, heterogeneous public-record prose. Claude proposes passages about physical condition, demolition, permits, condemnation and enforcement; deterministic code checks record identity, field, recorded date, exact quote, quote boundaries, clipped negation, instruction-like text and permit references, and neutrally notes when later-dated records exist. It does not establish semantic supersession or temporal truth. A semantic label is displayed only when a deterministic lexicon supports it. Two same-model runs must reproduce each model-proposed `(record, field, date, quote, label, relevance)` tuple. Code may then attach the exact loaded `Active` status from an AI-surfaced condemned record; that structured companion is deterministic enrichment and is outside the repeated-run denominator. Repeated-run consistency is not independent confirmation or probability of truth.

On the current development audit set—21 records on 3 conflict parcels, with 12 team-labeled relevant records—the verified Claude reader returned 12/12 relevant and 0 irrelevant record IDs. A declared no-AI keyword/lexicon scan returned 12/12 relevant and 9 irrelevant IDs (precision 12/21). The engine outcome is identical under both methods; the difference is the evidence-review workload and the delivery of exact dated quotes rather than a list of keyword hits.

This result is promising but not a model benchmark. The labels are team-authored, the cohort is tiny, the keyword baseline is not budget-matched, and the same parcels influenced development. Therefore it establishes only retrospective conformance and a demo counterfactual. It does not establish model necessity, external validity, analyst time saved or superior decision quality.

## Scripted live-model smoke run

`uv run python scripts/run_live_ai_smoke.py` records status/frame metadata—never model prose or credentials—to `docs/validation/live_ai_smoke.json`. On the recorded 2026-09-27 run with `claude-opus-5`, 12/12 scripted demo question–parcel attempts were answered or safely declined, and 5/5 adversarial or out-of-scope attempts were rejected or declined. This is a scripted smoke run, not a frozen benchmark or validation result. The same artifact records 6/8 usable cached ZBA cards; the two failed extractions remain unavailable, and the convenience set is neither an approval-rate sample nor a prediction base.

## AI safety findings that changed the implementation

- Exact quotation proves provenance, not meaning. A discovered false accept allowed a neutral exact quote to inherit a demolition label. The verifier now assigns `unverified_label` whenever deterministic semantic support is absent or disagrees, and derives relevance independently.
- Same-record overlap overstated stability. Retention now requires exact semantic-tuple recurrence, and the UI/docs call it repeated-run consistency rather than independent agreement.
- ZBA relief enums did not prove relief meaning. Relief kinds are now checked against scoped deterministic patterns. A dedicated regression test rejects a dimensional-setback decision mislabeled as a use variance.
- ZBA precedent extraction remains secondary. Eight hand-selected decisions cannot support an approval rate or prediction claim; cards are examples, not forecasts.

## Threats and smallest defensible next study

The strongest remaining threat is selection and labeling bias. Before the next sale, freeze prompts, verifier, strong budget-matched baselines and output limits; then have two practitioners label entire parcels blind to model output. Compare a structured/recency parser, BM25 or TF-IDF retrieval, unconstrained extraction as a safety ablation, and the verified reader. Report record- and event-level TP/FP/FN, critical-conflict-pair recall, exact-tuple stability, wrong accepted outputs conditional on acceptance, refusal/error states, tokens, latency and dated cost. Split by parcel, never by fields from the same record. Report every disagreement and raw numerator/denominator; do not claim general accuracy from the current sample.

For Ask LotLine, freeze at least 30 independently written question–parcel pairs spanning paraphrases, misspellings, multi-intent, underspecified and out-of-scope questions, plus 30 adversarial questions. Compare with a deterministic router and BM25 retrieval over the same approved claim/excerpt corpus. Report wrong accepted answers over accepted answers, not only over all attempts.

## Reproducibility and claim discipline

The engine and evaluation are deterministic in process, with byte-identical serialized results across two runs and a recorded result hash. `uv.lock` is committed. Application code is mechanically barred from test labels and golden-set answer columns. The app works without a key; verified caches are rechecked against current source text before display. Upstream public-source extraction is not reproducible from this repository and is stated as such. All findings remain limited to the dated snapshot and must be refreshed and revalidated for another sale.
