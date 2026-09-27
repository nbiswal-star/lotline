# Pre-registered protocol: citywide evaluation of the AI enforcement-record reader

- **Registered:** 2026-09-27T11:01Z (07:01 ET), before any sample was drawn and before any model call for this study.
- **Frozen:** this file is not edited after results exist. Any departure is recorded in a dated "Deviations" section appended at the end.
- **Code:** `scripts/fetch_scale_sample.py` (sample + reference), `evaluation/ai_scale.py` (model run, scoring, report).
- **Results:** `docs/validation/ai_scale_results.md`.

## 1. Question

Existing AI-reader evidence (`evaluation/ai_reader.py`) uses ~15 sale parcels and team-authored relevance labels. This study asks a narrower but independently checkable question at larger scale:

> Given only a parcel's PLI violation free text, does the LotLine reader (Claude proposal + deterministic quote verifier) surface verified evidence that the structure was demolished, for parcels that structured City permit data independently record as demolished — and does it avoid doing so for parcels that City data record as still-standing condemned structures? How does it compare with a keyword rule on the same text?

The reference is structured public data. The team writes no labels.

## 2. Data sources (WPRDC CKAN `datastore_search`, POST JSON)

| Role | Resource | Fields used |
|---|---|---|
| Model/baseline input | PLI violations `70c06278-92c5-4040-ab28-17671866f81c` | `parcel_id`, `casefile_number`, `investigation_date`, `status`, `case_file_type`, `investigation_outcome`, `investigation_findings`, `violation_description`, `violation_code_section`, `violation_spec_instructions`, `court_date`, `docket_number`, `court_decision` (the same field list the app's record fetcher uses) |
| Reference | PLI permits `f4d1177a-f597-4c32-8cbf-7885f56253f6` | `permit_id`, `permit_type`, `work_type`, `status`, `issue_date`, `parcel_num` |
| Reference | Condemned/dead-end properties `0a963f26-eb4b-4325-bbbc-3ddf6a871410` | `parcel_id`, `inspection_status`, `create_date` |

Feasibility notes from schema exploration (no outcome data inspected): the permits resource has 1,300 `Demolition Permit` rows (2019-06 onward; statuses Completed/Issued/Expired/Revoked/other; work types COMPLETE, CITY FUNDED, PARTIAL). The condemned list has 3,569 rows, all `inspection_status = Active`. PLI violations (~644k rows, from 2020-06) are fetched per parcel with a POST `filters: {"parcel_id": [...]}` list; the full table is not enumerated. Owner, contractor, address and coordinate fields are never written.

## 3. Reference labels (per parcel)

- **DEMOLISHED:** ≥1 permit with `permit_type = "Demolition Permit"`, `status = "Completed"`, `work_type ∈ {COMPLETE DEMOLITION, CITY FUNDED DEMOLITION}`.
- **NOT_DEMOLISHED:** parcel is on the condemned/dead-end list (`inspection_status = Active`, i.e. a condemned structure is recorded) AND has **no** `Demolition Permit` of any status or work type.

**Exclusions (ambiguous by declared rule; counted and reported):**
1. Completed-demolition parcel that is also on the condemned list (records conflict).
2. Completed-demolition parcel with a `BUILDING` / `NEW CONSTRUCTION` permit issued on or after the earliest qualifying demolition permit's issue date (a structure may exist again).
3. Parcels whose demolition permits are only partial, or only non-completed (Issued/Expired/Revoked/other) and not on the condemned list — neither label.
4. Parcel ids that are not 16 characters.

Parcels in neither class are outside the population.

## 4. Population and sampling

Population = parcels meeting a reference label **and** having ≥1 PLI violation row with non-empty `investigation_findings`, `violation_description` or `violation_spec_instructions` (after the person-name screen in §5).

Sampling: each stratum's candidate parcel ids are sorted, then shuffled with `random.Random(20260927)`. Candidates are checked for PLI eligibility in shuffled order (batches of 25); the first **75 eligible** per stratum are taken (equivalent to a simple random sample without replacement from the eligible population). Total cap 150 parcels. Screened-but-ineligible counts are reported.

## 5. Model input construction (blinding)

- The model and the keyword baseline see **only PLI violation text fields** listed in §2. No permit or condemned-list data are in the input.
- Record = PLI casefile. Per parcel, keep the **40 casefiles with the most recent `investigation_date`** (max over rows); identical texts are deduplicated per (casefile, field), keeping the earliest dated row (same rule as `scripts/fetch_record_text.py`).
- Free-text fields that match the app fetcher's person-name pattern (honorific/judge + name, "spoke with/to") or contain a word of the condemned-list owner name are dropped whole and never written.
- The free text may itself mention demolition or a permit number (e.g. "DP-2024-…"). This is allowed (it is real-world reading) and **reported**: share of parcels whose input text contains any `DP-YYYY-N` reference, and whether it cites the reference permit id.

## 6. Systems compared (same input per parcel)

(a) **LotLine AI reader**: exactly `lotline.ai.evidence.SYSTEM`, `SCHEMA`, `build_prompt(pin, records)` and `call_structured(..., effort="medium")` with the app's model (`claude-opus-5`), then `digest_from_runs(...)` verification. **One extraction call per parcel**; the app's second consistency run is skipped for cost/time (single-run verification is therefore weaker than the app's two-run rule; this is stated in the results).

(b) **Keyword baseline (no AI)** using the app's own regexes (`lotline.ai.evidence.DEMOLITION_DONE`, `LEXICON`) over all input text fields.

(c) **No reader**: always abstains.

Parcel-level prediction, three classes (DEMOLISHED / STRUCTURE_PRESENT / ABSTAIN):

- **AI primary:** DEMOLISHED if ≥1 verified item with `indicates = structure_removed_or_demolished` (label survived the verifier's lexicon check) whose quote matches `DEMOLITION_DONE` (reports demolition as done — the same rule `resolver_note` uses to tell a human the record describes demolition). Else STRUCTURE_PRESENT if ≥1 verified item with `indicates = structure_present`. Else ABSTAIN (including verifier status `rejected`, API failure, or not run).
- **Keyword primary:** DEMOLISHED if any input text field matches `DEMOLITION_DONE`; else STRUCTURE_PRESENT if any field matches `LEXICON["structure_present"]`; else ABSTAIN.

Secondary (reported, not headline):
- AI-S1 "currency latest": primary AND the item's `currency == "latest record for this lot"`.
- AI-S2 "any demolition label": ≥1 verified `structure_removed_or_demolished` item (no done-regex requirement).
- KW-S2: any field matches `LEXICON["structure_removed_or_demolished"]` (includes "demolition", "demo", DP- refs; flags ordered/pending demolition too).

## 7. Metrics

All proportions with 95% Wilson intervals.
- DEMOLISHED detection: precision, recall, F1 (F1 point estimate only). ABSTAIN and STRUCTURE_PRESENT count as "not DEMOLISHED".
- Secondary: STRUCTURE_PRESENT precision/recall against NOT_DEMOLISHED.
- Abstention rate per system and stratum.
- Verified-item rejection rate: rejected items / proposed items (and reasons).
- AI-vs-keyword disagreement cases (parcel, record ids, quotes).
- Latency per parcel (wall-clock of the call), tokens in/out, cost at $5 / $25 per million input/output tokens.
- Error analysis: up to 10 AI errors (FP and FN, fixed-seed selection), each explained.
- Pre-declared stratification: DEMOLISHED parcels split by whether any input PLI record is dated on/after the earliest qualifying permit issue date (temporal overlap).
- Missing model outputs are scored as ABSTAIN (intention-to-treat); the per-protocol count is also given.

No success threshold is set for the AI; this is a descriptive comparison. It is not registered as an assertion in the main evaluation harness unless it regenerates offline from cached outputs.

## 8. Budget and stop rule

≤150 parcels, one call each. Cost is tracked from `response.usage`; the run stops before the next call if cumulative estimated spend exceeds **$15**. Raw model outputs are cached to `data/validation_scale/model_outputs.jsonl`; the report is regenerated offline from that cache (`uv run python -m evaluation.ai_scale --report`).

## 9. Known threats (declared in advance)

- **Reference noise:** permit "Completed" is not a final-inspection date; the condemned list can lag a demolition done under a pre-2019 permit or without a permit; a demolished lot may be rebuilt without a NEW CONSTRUCTION permit in the window.
- **Temporal mismatch:** PLI text starts 2020-06; permits start 2019-06. A demolition before any PLI text exists can only be inferred from later vacant-lot notes.
- **Selection bias:** strata are extreme cases (completed demolition vs. active condemnation). Balanced 75/75 sampling fixes prevalence at 50%; precision at citywide prevalence would differ. Results do not transfer to ordinary parcels.
- **Construct:** the reader is designed to surface quotes for a human, not to classify parcels; this study measures one derived parcel rule.

## Amendment 1 (registered 2026-09-27 ~11:03Z, concurrently with the sample fetch and before any model call)

Added on external methods review. It changes no population, reference or sampling rule; the sample fetch (11:03:02–11:03:13Z) ran concurrently, and no model output existed. (Timestamp corrected from an earlier typed "11:04Z" before any results.)

1. **Framing.** This is a development-set estimate of one derived parcel rule, not a benchmark.
2. **Stronger baselines**, all on the same PLI-only input (non-PLI structured sources — permits and the condemned list — are the reference and are never available to any system, so "structured" means PLI's own structured fields):
   - **B1 keyword (primary baseline):** the §6 keyword rule (`DEMOLITION_DONE` on any field).
   - **B2 structured+keyword:** DEMOLISHED if any casefile has `case_file_type = "Vacant Lots"` (a structured PLI signal of a lot without a building) OR any field matches `DEMOLITION_DONE`.
   - **B3 recency+keyword:** only the fields of the single most recent casefile (max `investigation_date`); DEMOLISHED if they match `DEMOLITION_DONE`.
   - KW-S2 (any `LEXICON["structure_removed_or_demolished"]` hit) stays as a secondary high-recall rule.
   The headline reports the AI against the **best** baseline by F1, not only against B1.
3. **Self-consistency.** Pass 1 (k=1) runs on all sampled parcels and is the primary AI prediction. A second extraction pass runs only if cumulative spend after pass 1 plus the projected cost of pass 2 is ≤ $15. If it runs, report the per-parcel exact-tuple agreement distribution and, as a secondary rule, the app's two-run intersection (`digest_from_runs` over both runs). Otherwise report k=1 and say so.
4. **Cost/latency:** tokens, cost and wall-clock latency per parcel reported as mean and p95.
5. **Automatically checkable metrics:** verification pass rate (verified items / proposed items), abstention rate, and **wrong-and-shown rate** = verified demolition-done items shown on NOT_DEMOLISHED parcels / all verified demolition-done items shown.
6. **Per-layer rejection counts:** for every proposed item, the verifier's first failing check (`verify_items` reason codes) and the lexicon label-withholding count are stored so a layer ablation can be computed offline from the cache.

## Amendment 2 (registered 2026-09-27T11:04Z, after the sample fetch, before any model call; no outcome inspected)

1. **Baseline B4 (record-flagging rule from the AI-delta review):** at record level it flags a record if it comes from a non-PLI structured source (none exist in this PLI-only input), OR its text says demolished/demolition or cites `DP-\d{4}-\d+`, OR it is the parcel's latest PLI record. The "latest record" clause adds a record to review but asserts nothing, so the parcel-level prediction is: DEMOLISHED if any field matches `\bdemolished\b|\bdemolition\b|\bDP-\d{4}-\d+\b`. B4 is reported with B1–B3 and is eligible to be the "best baseline".
2. **Demolition-date accuracy:** for DEMOLISHED parcels the AI predicts as DEMOLISHED, compare the record date of the earliest verified demolition-done item (dates come from the record, never the model) with the reference permit date. The permits data carries **no final/completion date**; the earliest qualifying permit `issue_date` is used and the gap (days) is reported as a distribution, not as correct/incorrect.
3. **k:** the union-of-k reader has not landed in `lotline/ai/evidence.py` at registration time (file unchanged since 06:55 ET; `RUNS = 2`, intersection rule). The primary AI prediction is therefore **k=1**. If budget allows further passes, union-of-k and intersection-of-k over the cached passes are computed offline as secondary rules and labelled as such.

## Amendment 3 (registered 2026-09-27T11:10Z: calibrated confidence; after pass-1 model outputs were cached, before any AI metric, prediction or verified item was inspected)

State at registration: pass 1 (k=1) has run on all 150 parcels (spend $7.78, 0 errors); the report has not been generated on model outputs and no AI prediction has been looked at. Baseline metrics (B1–B4) were seen in a code dry run with no model outputs.

1. **k stays 1.** The Amendment-1 rule allows pass 2 only if pass-1 spend plus projected pass-2 spend ≤ $15; projected total is $7.78 × 2 ≈ $15.56, so **pass 2 is not run**. The k-run agreement fraction feature is therefore unavailable (constant at k=1) and is reported as such.
2. **Entailment judge:** not present in `lotline/ai/evidence.py` at registration; not a feature.
3. **Permit corroboration:** excluded from features — the reference is permit-derived (leakage), and the evaluation input contains no permit records, so it would be constant anyway.
4. **Target:** parcel-level y = 1 if reference DEMOLISHED, 0 if NOT_DEMOLISHED; the calibrated quantity is P(reference DEMOLISHED | reader output).
5. **Features (parcel level, from pass-1 verified items only; no baselines, no reference data):**
   - `demo_done`: 1 if the primary AI rule fires (≥1 verified `structure_removed_or_demolished` item whose quote matches `DEMOLITION_DONE`);
   - `log_demo_items`: log(1 + number of verified items labelled `structure_removed_or_demolished`);
   - `log_present_items`: log(1 + number of verified items labelled `structure_present`);
   - `demo_in_latest`: 1 if a verified demolition-labelled item comes from the parcel's most recent casefile (recency rank 0).
   Logged for description at item level too (not fitted): lexicon agreement (label withheld or not), recency rank of the item's casefile, quote length, number of verified items on the parcel.
6. **Split:** by parcel, stratified by reference label, `random.Random(20260927)`: 60% calibration (45 + 45), 40% held-out (30 + 30).
7. **Calibrator:** L2-regularised logistic regression (λ = 1.0 on coefficients, intercept unpenalised; Newton iterations; deterministic) on the 4 features, fitted on the calibration split only. Monotone in each feature's fitted direction; kept small because n = 90.
8. **Held-out report:** reliability table (5 equal-width bins) and PNG diagram `docs/validation/ai_scale_reliability.png`; ECE (5 bins) with percentile bootstrap 95% CI (2,000 parcel resamples, fixed seed); Brier score with bootstrap CI. Comparators: (i) uncalibrated raw score = the binary primary AI decision (1.0/0.0) — the raw k-run agreement fraction is unavailable at k=1; (ii) constant 0.5 (sample prevalence).
9. **Artifact:** `data/calibration/reader_calibration.json` — version, date, n, split, feature definitions, coefficients, intercept, λ, held-out metrics, and a prior-shift note: the sample is balanced (50% prevalence), so for a population with prevalence π the logit must be shifted by log(π / (1 − π)).
10. **Limits declared:** n = 60 held-out parcels, one city, extreme strata, reference noise (§9); not a clinical-grade calibration.

## Deviations (recorded 2026-09-27, after results)

1. **Verifier version frozen for scoring.** §6 says "the same verification code". `lotline/ai/evidence.py` changed at 07:11 ET, after pass 1 ran (07:07–07:10 ET), adding union-of-k, an entailment judge and new verifier layers. The system prompt and schema did not change. Primary scoring uses `evaluation/ai_scale_frozen_evidence.py`, a verbatim copy of the 06:55 ET module that produced the cached outputs. The report also re-scores the same outputs with the current app verifier as a sensitivity row. At the time of writing, the parcel-level metrics were identical.
2. **Post-hoc exploratory table.** The table of demolition labels withheld by the lexicon gate was added after error analysis and is labelled as post hoc in the results. The error notes and the discussion were also written after results.
3. **Amendment 1 timestamp** was corrected from a typed "11:04Z" to "~11:03Z, concurrent with the sample fetch" before any result existed.
4. **Reliability PNG** requires matplotlib, which is not a project dependency. `uv run --with matplotlib python -m evaluation.ai_scale --report` writes it. Without matplotlib the report and calibration JSON still regenerate and the PNG is left unchanged.
