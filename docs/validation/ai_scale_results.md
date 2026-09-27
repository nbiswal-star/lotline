# AI record reader at citywide scale: results

<!-- GENERATED FILE: regenerate offline with the command below; do not edit by hand. -->

- Command: `uv run python -m evaluation.ai_scale --report` (reads cached model outputs; no API key or network needed)
- Protocol: [`ai_scale_protocol.md`](ai_scale_protocol.md) (registered before any model call; amendments dated)
- Sample fetched from WPRDC: 2026-09-27T11:03:02Z – 2026-09-27T11:03:13Z; seed 20260927
- Model: claude-opus-5; extraction passes cached: [1]
- **Status: development-set estimate of one derived parcel rule, not a benchmark.**

## Sample

| Stratum (reference) | Candidates | Screened (random order) | No PLI free text | Sampled |
|---|---|---|---|---|
| DEMOLISHED | 703 | 92 | 17 | 75 |
| NOT_DEMOLISHED | 2694 | 75 | 0 | 75 |

Reference: DEMOLISHED = completed COMPLETE/CITY FUNDED demolition permit, not on the condemned list, no later new-construction permit. NOT_DEMOLISHED = active condemned-list entry and no demolition permit of any status. Excluded as ambiguous before sampling: completed demo and on condemned list 117; condemned with noncompleted or partial demo permit 84; demo permit partial or not completed only 280; new construction after demo 59. Person-name screen dropped 7 text fields.

Casefiles per parcel given to the reader (cap 40): median 5, max 32.

## Headline: DEMOLISHED detection at parcel level (95% Wilson intervals)

n = 150 parcels (75 DEMOLISHED, 75 NOT_DEMOLISHED). Balanced sampling fixes prevalence at 50%, so precision here is not the precision at citywide prevalence.

| System | Precision | Recall | F1 | Specificity | TP/FP/FN/TN | Abstain (all parcels) |
|---|---|---|---|---|---|---|
| LotLine AI reader, k=1 (primary) | 30/30 = 100.0% [88.6%, 100.0%] | 30/75 = 40.0% [29.7%, 51.3%] | 0.571 | 75/75 = 100.0% [95.1%, 100.0%] | 30/0/45/75 | 37/150 = 24.7% [18.5%, 32.1%] |
| B1 keyword DEMOLITION_DONE | 33/39 = 84.6% [70.3%, 92.8%] | 33/75 = 44.0% [33.3%, 55.3%] | 0.579 | 69/75 = 92.0% [83.6%, 96.3%] | 33/6/42/69 | 23/150 = 15.3% [10.4%, 22.0%] |
| B2 structured (Vacant Lots type) + keyword | 35/48 = 72.9% [59.0%, 83.4%] | 35/75 = 46.7% [35.8%, 57.8%] | 0.569 | 62/75 = 82.7% [72.6%, 89.6%] | 35/13/40/62 | 17/150 = 11.3% [7.2%, 17.4%] |
| B3 recency + keyword (latest casefile) | 18/22 = 81.8% [61.5%, 92.7%] | 18/75 = 24.0% [15.8%, 34.8%] | 0.371 | 71/75 = 94.7% [87.1%, 97.9%] | 18/4/57/71 | 128/150 = 85.3% [78.8%, 90.1%] |
| B4 demolished/demolition/DP- rule | 46/61 = 75.4% [63.3%, 84.5%] | 46/75 = 61.3% [50.0%, 71.5%] | 0.676 | 60/75 = 80.0% [69.6%, 87.5%] | 46/15/29/60 | 89/150 = 59.3% [51.3%, 66.9%] |
| No reader (always abstain) | n/a (0/0) | 0/75 = 0.0% [0.0%, 4.9%] | 0.000 | 75/75 = 100.0% [95.1%, 100.0%] | 0/0/75/75 | 150/150 = 100.0% [97.5%, 100.0%] |
| AI secondary: demolition item is latest record | 18/18 = 100.0% [82.4%, 100.0%] | 18/75 = 24.0% [15.8%, 34.8%] | 0.387 | 75/75 = 100.0% [95.1%, 100.0%] | 18/0/57/75 | 38/150 = 25.3% [19.0%, 32.8%] |
| AI secondary: any demolition label | 44/44 = 100.0% [92.0%, 100.0%] | 44/75 = 58.7% [47.4%, 69.1%] | 0.739 | 75/75 = 100.0% [95.1%, 100.0%] | 44/0/31/75 | 34/150 = 22.7% [16.7%, 30.0%] |
| Keyword secondary: any demolition lexicon hit | 55/96 = 57.3% [47.3%, 66.7%] | 55/75 = 73.3% [62.4%, 82.0%] | 0.643 | 34/75 = 45.3% [34.6%, 56.6%] | 55/41/20/34 | 54/150 = 36.0% [28.8%, 43.9%] |

Best baseline by F1 (declared comparison): **B4 demolished/demolition/DP- rule**. AI-vs-best disagreements: AI only | ref DEMOLISHED: 6, B4 only | ref DEMOLISHED: 22, B4 only | ref NOT_DEMOLISHED: 15.

Secondary: STRUCTURE_PRESENT prediction against NOT_DEMOLISHED.

| System | Precision | Recall |
|---|---|---|
| LotLine AI reader, k=1 (primary) | 55/83 = 66.3% [55.6%, 75.5%] | 55/75 = 73.3% [62.4%, 82.0%] |
| B1 keyword DEMOLITION_DONE | 57/88 = 64.8% [54.4%, 73.9%] | 57/75 = 76.0% [65.2%, 84.2%] |
| B2 structured (Vacant Lots type) + keyword | 55/85 = 64.7% [54.1%, 74.0%] | 55/75 = 73.3% [62.4%, 82.0%] |

Prediction distribution by stratum (D = DEMOLISHED, P = STRUCTURE_PRESENT, A = ABSTAIN):

| System | Reference DEMOLISHED | Reference NOT_DEMOLISHED |
|---|---|---|
| LotLine AI reader, k=1 (primary) | D 30 / P 28 / A 17 | D 0 / P 55 / A 20 |
| B1 keyword DEMOLITION_DONE | D 33 / P 31 / A 11 | D 6 / P 57 / A 12 |
| B2 structured (Vacant Lots type) + keyword | D 35 / P 30 / A 10 | D 13 / P 55 / A 7 |
| B3 recency + keyword (latest casefile) | D 18 / P 0 / A 57 | D 4 / P 0 / A 71 |
| B4 demolished/demolition/DP- rule | D 46 / P 0 / A 29 | D 15 / P 0 / A 60 |

## Automatically checkable metrics (pass 1)

| Metric | Value |
|---|---|
| Reader status per parcel | ok 150 |
| Proposed items (all parcels) | 1174 |
| Verification pass rate (verified / proposed) | 1151/1174 = 98.0% [97.1%, 98.7%] |
| Verified-item rejection rate | 23/1174 = 2.0% [1.3%, 2.9%] |
| Verified items whose model label was withheld (lexicon disagreed → `unverified_label`) | 179 |
| Verified demolition-done items shown | 39 |
| Wrong-and-shown rate (demolition-done items on NOT_DEMOLISHED parcels / all shown) | 0/39 = 0.0% [0.0%, 9.0%] |

Per-layer rejection counts (first failing verifier check per proposed item; enables offline ablation):

| Verifier check | Items dropped |
|---|---|
| too_long | 13 |
| not_on_boundary | 7 |
| unknown_record | 2 |
| too_short | 1 |

Verified item labels: enforcement_or_court_status 555, structure_present 225, structure_removed_or_demolished 66, unverified_label 179, vacant_lot_condition 126.

## Cost and latency (pass 1, per parcel)

| Measure | Value |
|---|---|
| Wall-clock latency (s), successful calls | mean 8.0, p95 11.5, max 16.0 |
| Input tokens | mean 6362, p95 15779, max 26619 |
| Output tokens (incl. thinking) | mean 803, p95 1252, max 1639 |
| Cost (USD at $5/$25 per M tokens) | mean 0.052, p95 0.101, max 0.153 |
| Total spend, all cached passes (USD) | 7.78 |

## Blinding check: does the input text itself mention demolition or a permit?

| Stratum | n | Any DP- permit ref | Cites the reference permit id | Any demolition lexicon hit | Any demolition-done wording |
|---|---|---|---|---|---|
| DEMOLISHED | 75 | 15/75 = 20.0% [12.5%, 30.4%] | 14/75 = 18.7% [11.5%, 28.9%] | 55/75 = 73.3% [62.4%, 82.0%] | 33/75 = 44.0% [33.3%, 55.3%] |
| NOT_DEMOLISHED | 75 | 3/75 = 4.0% [1.4%, 11.1%] | n/a | 41/75 = 54.7% [43.4%, 65.4%] | 6/75 = 8.0% [3.7%, 16.4%] |

## Temporal overlap (DEMOLISHED parcels; recall)

| PLI text timing vs first demolition permit | n | AI | B1 | B2 | B4 |
|---|---|---|---|---|---|
| some PLI record dated on/after first demolition permit issue | 64 | 30/64 = 46.9% [35.2%, 58.9%] | 31/64 = 48.4% [36.6%, 60.4%] | 33/64 = 51.6% [39.6%, 63.4%] | 41/64 = 64.1% [51.8%, 74.7%] |
| all PLI records dated before first demolition permit issue | 11 | 0/11 = 0.0% [0.0%, 25.9%] | 2/11 = 18.2% [5.1%, 47.7%] | 2/11 = 18.2% [5.1%, 47.7%] | 5/11 = 45.5% [21.3%, 72.0%] |

## Demolition-date agreement

The permits data carries no completion date, so the earliest qualifying permit issue date is used. For 30 AI true positives, (earliest verified demolition-done record date − permit issue date) in days: median 30, IQR [12, 150], 0 dated before the permit issue date, 29 within a year after it.

## AI vs keyword (B1) disagreements

| PIN | Reference | Who says DEMOLISHED | AI outcome | Evidence (record, date, field, quote) |
|---|---|---|---|---|
| 0014K00080000000 | NOT_DEMOLISHED | B1 only | correct | CF-PLI-2026-025567 (None, violation_spec_instructions): “perty. Or secure a demolition permit and have the structure demolished. Apply for building permit or demolition permit online at https://onestoppgh.pittsburghpa” |
| 0044H00261000000 | NOT_DEMOLISHED | B1 only | correct | CF-PLI-2026-048221 (None, violation_spec_instructions): “Structure must be repaired or demolished. The case will be closed once all permits for repairs or demolition are completed. Apply for and obtain permits online” |
| 0046J00292000000 | NOT_DEMOLISHED | B1 only | correct | CF-PLI-2026-018143 (None, violation_spec_instructions): “upancy of the structure until repaired to make habitable or demolished, acquire permits at www.OneStopPgh.gov or in person at 412 BLVD of the Allies M-F 9AM-3PM” |
| 0070J00078000000 | DEMOLISHED | B1 only | wrong | CF-PLI-2021-036530 (2021-11-09, investigation_findings): “Violations still exist, property has not been razed or repaired” |
| 0174E00071000000 | DEMOLISHED | B1 only | wrong | CF-PLI-2023-009664 (2023-04-24, investigation_findings): “This structure needs to be repaired or demolished.” |
| 0174H00099000000 | NOT_DEMOLISHED | B1 only | correct | CF-PLI-2024-016660 (2024-04-12, investigation_findings): “This structure needs to be repaired or demolished, before further damage occurs.” |
| 0174K00097000000 | DEMOLISHED | B1 only | wrong | CF-PLI-2020-000960 (2020-07-16, investigation_findings): “condemned on 5-21-2018,out on city demo,to be razed” |
| 0174K00119000000 | NOT_DEMOLISHED | B1 only | correct | CF-PLI-2026-016933 (2026-03-31, investigation_findings): “Structure unsafe. Needs repaired/or demolished.” |
| 0231K00159000000 | NOT_DEMOLISHED | B1 only | correct | CF-PLI-2023-055217 (2023-11-15, investigation_findings): “This structure needs to be repaired or demolished. (Rear porch)” |

## Error analysis (10 of 45 AI errors, fixed-seed sample)

| PIN | Type | Reference | Latest text | Evidence | Analyst note (written after results) |
|---|---|---|---|---|---|
| 0007F00098000001 | FN | permit DP-2023-13547 issued 2023-10-24 | latest PLI 2023-12-29 | no demolition wording in input | Temporal/content gap: only fire-safety and sidewalk casefiles; text never describes the building's condition or removal. No reader could infer demolition from this input. |
| 0009N00198000000 | FN | permit DP-2024-13889 issued 2025-03-10 | latest PLI 2023-11-13 | no demolition wording in input | Temporal: latest PLI text (2023-11) predates the demolition permit (issued 2025-03). The record cannot yet say demolished. |
| 0015G00106000000 | FN | permit DP-2021-08310 issued 2021-05-18 | latest PLI 2021-09-09 | no demolition wording in input | Lexicon-gate loss: the model surfaced 'PROPERTY WAS RAISED NO LONGER VIEWED AS AN UNSAFE STRUCTURE' (misspelled razed) with a demolition label; the verifier withheld the label because the lexicon has no match, so the parcel rule did not fire. |
| 0035C00113000000 | FN | permit DP-2023-15432 issued 2023-09-12 | latest PLI 2026-02-19 | CF-PLI-2023-046185 (2023-09-22, investigation_findings): “n front of property. Property is scheduled on a city funded demolition.” | Ordered, not done: text says 'scheduled on a city funded demolition' (2023-09); later casefiles are weeds/court with no completion statement. Correct not to assert demolition from this text; reference is later than the text's news. |
| 0044D00182000000 | FN | permit DP-2021-10348 issued 2022-10-19 | latest PLI 2022-08-29 | CF-PLI-2022-034204 (2022-08-29, investigation_findings): “DP-2021-10348” | Ordered, not done: 'ORDERED FOR CITY-FUNDED DEMOLITION'; latest finding 2022-08 predates the permit (2022-10). Temporal. |
| 0055H00023000000 | FN | permit DP-2024-05119 issued 2024-04-30 | latest PLI 2024-07-09 | CF-PLI-2024-023382 (2024-05-15, investigation_findings): “n January. Top floor extensive damage. Property owners have demolition permit.” | Rule-regex loss: verified demolition items exist ('House is down, land covered in hay, waiting to pass final demolition inspection'; 'Demolition Permit - Completed') but none matches DEMOLITION_DONE ('demolished\|razed\|demolition completed'). The any-demolition-label secondary rule catches it. |
| 0057C00162000A00 | FN | permit DP-2021-11317 issued 2022-09-02 | latest PLI 2022-11-02 | CF-PLI-2022-036043 (2022-11-02, investigation_findings): “property on city demolition schedule with red sticker applied and work crew onsite (252 & 254 as well). Debris will be removed thru Friday 11/4/22” | In progress: 'work crew onsite' on the city demolition schedule (2022-11); no completion statement in text. Reasonable abstention on 'done'; the model did label it demolition. |
| 0091J00015000000 | FN | permit DP-2025-09132 issued 2026-01-20 | latest PLI 2023-02-03 | no demolition wording in input | Temporal: latest PLI text 2023-02 (board-up completed); permit issued 2026-01. Text describes a standing, boarded structure. |
| 0174K00106000000 | FN | permit DP-2019-11167 issued 2019-12-12 | latest PLI 2022-06-01 | no demolition wording in input | Implicit only: 2019 permit, later texts are weeds cases ('Property was cut down & clear'). Vacant-lot condition without the word demolition; model labelled vacant_lot_condition, not demolition. |
| 0231F00208000000 | FN | permit DP-2022-13776 issued 2023-10-02 | latest PLI 2023-08-11 | CF-PLI-2023-014444 (2023-04-27, investigation_findings): “Selected for City Funded Demolition” | In progress: 'City Funded Demo. In progress to be torn down.' (2023-04), latest 2023-08 'still exists'; permit issued 2023-10. Text ends before completion. |

## Self-consistency

Only one extraction pass was run (k=1). The app's two-run intersection rule was not applied, so verified items here passed provenance/quote/lexicon checks but not repeated-run consistency.

## Exploratory (post hoc): demolition labels withheld by the lexicon gate

Not pre-registered; found during error analysis. Parcels where the model labelled a verbatim quote `structure_removed_or_demolished` but the verifier withheld the label because the keyword lexicon did not match: 10 DEMOLISHED vs 0 NOT_DEMOLISHED parcels.

| PIN | Reference | AI primary prediction | Withheld quote |
|---|---|---|---|
| 0004E00206000000 | DEMOLISHED | DEMOLISHED | House was tore down and sidewalk was cleared. |
| 0014L00003000000 | DEMOLISHED | DEMOLISHED | Violations have been corrected structure and weeds removed. |
| 0015G00106000000 | DEMOLISHED | STRUCTURE_PRESENT | PROPERTY WAS RAISED NO LONGER VIEWED AS AN UNSAFE STRUCTURE |
| 0042P00155000001 | DEMOLISHED | ABSTAIN | Provide documentation of materials removal off-site, void cleaned, fill materials, and site restoration. |
| 0046G00052000000 | DEMOLISHED | DEMOLISHED | Void property is contracted to be demoed |
| 0056F00103000000 | DEMOLISHED | STRUCTURE_PRESENT | Building is gone, no graffiti |
| 0124K00264000000 | DEMOLISHED | STRUCTURE_PRESENT | This property has been torn down. |
| 0125F00053000000 | DEMOLISHED | ABSTAIN | Utility pole was removed. |
| 0174B00109000000 | DEMOLISHED | STRUCTURE_PRESENT | This CF is no longer valid. This structure has been torn down! |
| 0232A00032000000 | DEMOLISHED | STRUCTURE_PRESENT | The violation(s) were corrected. The structure was torn down. |

## Verifier-version sensitivity

Primary scoring uses `evaluation/ai_scale_frozen_evidence.py`, a frozen copy of the app verifier that produced the cached outputs (app file as of 06:55 ET; pass 1 ran 07:07–07:10 ET). The app's `lotline/ai/evidence.py` changed at 07:11 ET (union-of-k, entailment judge, new verifier layers). Re-verifying the same cached pass-1 outputs with the current app verifier (k=1, no judge call):

| Verifier | Precision | Recall | F1 | TP/FP/FN/TN |
|---|---|---|---|---|
| frozen (primary) | 30/30 = 100.0% [88.6%, 100.0%] | 30/75 = 40.0% [29.7%, 51.3%] | 0.571 | 30/0/45/75 |
| current app (sha256 de70a8782aeb…) | 30/30 = 100.0% [88.6%, 100.0%] | 30/75 = 40.0% [29.7%, 51.3%] | 0.571 | 30/0/45/75 |

System prompt and schema identical between versions: True. Per-parcel user prompt differs for 1/150 parcels (the current app withholds more records as instruction-like), so the current app would not send exactly the cached input there.

## Calibrated confidence (protocol Amendment 3)

Parcel-level logistic calibrator (L2 λ=1.0) fitted on 90 calibration parcels, evaluated on 60 held-out parcels (split by parcel, stratified, seed 20260927). k-run agreement is unavailable (k=1); permit corroboration is excluded (leakage); no entailment judge exists. Artifact: `data/calibration/reader_calibration.json`. Diagram: [`ai_scale_reliability.png`](ai_scale_reliability.png).

| Feature | Coefficient | Mean (DEMOLISHED) | Mean (NOT_DEMOLISHED) |
|---|---|---|---|
| demo_done | +0.953 | 0.4 | 0 |
| log_demo_items | +2.272 | 0.519 | 0 |
| log_present_items | -0.411 | 0.698 | 0.873 |
| demo_in_latest | +0.786 | 0.32 | 0 |
| intercept | -0.326 |  |  |

| Held-out scorer | ECE (5 bins) [bootstrap 95% CI] | Brier [bootstrap 95% CI] |
|---|---|---|
| calibrated (logistic, 4 features) | 0.093 [0.044, 0.184] | 0.139 [0.105, 0.176] |
| raw binary AI decision (1.0 / 0.0) | 0.250 [0.150, 0.367] | 0.250 [0.150, 0.367] |
| constant 0.5 (sample prevalence) | 0.000 [0.000, 0.150] | 0.250 [0.250, 0.250] |

Reliability table, held-out (bin, n, mean predicted, observed share DEMOLISHED):

*calibrated (logistic, 4 features)*

| Bin | n | Mean predicted | Observed |
|---|---|---|---|
| [0.0, 0.2) | 0 | — | — |
| [0.2, 0.4) | 27 | 0.307 | 0.185 |
| [0.4, 0.6) | 15 | 0.419 | 0.467 |
| [0.6, 0.8) | 0 | — | — |
| [0.8, 1.0] | 18 | 0.911 | 1 |

*raw binary AI decision (1.0 / 0.0)*

| Bin | n | Mean predicted | Observed |
|---|---|---|---|
| [0.0, 0.2) | 45 | 0 | 0.333 |
| [0.2, 0.4) | 0 | — | — |
| [0.4, 0.6) | 0 | — | — |
| [0.6, 0.8) | 0 | — | — |
| [0.8, 1.0] | 15 | 1 | 1 |

Item level (descriptive, all parcels): verified demolition-labelled items by casefile recency and parcel reference.

| Item casefile | Parcel reference | Items |
|---|---|---|
| latest casefile | DEMOLISHED | 30 |
| older casefile | DEMOLISHED | 36 |

## Discussion (written 2026-09-27 after the results above; not pre-registered)

**What this shows.**

- **Precision is where the AI reader differs from grep.** On 150 randomly sampled parcels scored against City permit and condemned-list data (no team labels), the primary AI rule never asserted a completed demolition on a standing condemned structure: 0/75 false positives, precision 30/30 (95% CI 88.6–100%). The frozen keyword rule B1 applies the same "demolished/razed/completed" regex to the same text. It had equal recall within noise (33/75 vs 30/75) but 6 false positives. All six are inspector boilerplate such as "must be repaired or demolished" or "has not been razed or repaired". Reading context, not the regex, removes them. On the automatically checkable side, 0/39 verified "demolition done" quotes were shown on a NOT_DEMOLISHED parcel.
- **On F1, the best simple baseline wins.** B4 (any "demolished", "demolition" or DP- reference) reaches F1 0.676 against the AI's 0.571: recall 61% vs 40%, with 15 false positives vs 0. The pre-registered headline comparison is therefore not an AI win on F1. The two systems trade recall against precision. For LotLine's use, a quote shown to a human resolver as demolition evidence, a false positive is the costlier error. That judgment is the team's and is not something this study measured.
- **Recall is limited by the record and by the verifier, not only by the model.** Of the 45 AI misses, many parcels have no text that could say "demolished": 11 DEMOLISHED parcels have no PLI text dated on or after the permit, and several more have only unrelated casefiles (fire safety, sidewalks). The exploratory table shows a second limit. In 5 missed parcels the model correctly surfaced "torn down", "building is gone" or "PROPERTY WAS RAISED", but the deterministic lexicon gate withheld the label. Across all 150 parcels, a withheld demolition label occurred only on DEMOLISHED parcels. The secondary "any verified demolition label" rule (AI-S2) reaches 44/75 recall at 44/44 precision. It was declared before results, but it is secondary and is not promoted here.
- **Verification rarely fires on real text.** 98% of proposed items passed provenance/quote checks. Of the 23 rejections, most were over-long or off-boundary quotes. The lexicon label gate, not quote verification, is the layer with real effect (179 labels withheld).
- **Cost is small.** $0.052 per parcel on average (p95 $0.10), 8 s mean latency, $7.78 in total for 150 parcels at k=1.
- **Calibration.** A 4-feature logistic calibrator fitted on 90 parcels gives held-out ECE 0.09 and Brier 0.14, against 0.25/0.25 for treating the binary AI decision as a probability. A constant 0.5 has near-zero ECE on this balanced sample but the same Brier 0.25. That is why Brier, not ECE alone, is the useful comparison. The fitted model is exported for offline use with a prevalence-shift note.

**What it does not show.**

- **Reference noise.** "Completed" permit status is not a completion date, and the permits data has no final-inspection date. The condemned list can lag real demolitions, and a demolished lot can be rebuilt without a NEW CONSTRUCTION permit in the window. We excluded 540 ambiguous parcels by declared rules, which makes the task cleaner than real use.
- **Temporal mismatch.** PLI text and permits cover different periods. A reader of text cannot know about a demolition that happened after the last inspection note, and 11/75 DEMOLISHED parcels are in that situation.
- **Selection bias.** The strata are extremes (completed demolition vs. active condemnation), sampled 50/50. Precision at citywide prevalence, and behaviour on ordinary parcels, are not estimated.
- **Single run.** k=1 by the budget rule, so repeated-run consistency and the app's newer union-of-k and entailment-judge path are untested at scale. The current app verifier gives identical parcel metrics on the cached outputs.
- **Post-hoc elements.** The error notes, this discussion and the lexicon-gate table were written after seeing results. Every other metric and rule was fixed in the protocol or its dated amendments before any model output was inspected.
- **One city and one model**, one prompt, one day's snapshot. This is a development-set estimate, not a benchmark.
