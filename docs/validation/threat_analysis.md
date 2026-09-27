# Experiment 8: error and threat analysis

**Scope.** One frozen snapshot of one Pittsburgh Treasurer Sale: the Treasury pull dated 2026-09-24 and the City advertisement dated 2026-09-16. That gives 96 Treasury records, 77 advertised, 63 structures and 14 vacant lots. This is a qualitative analysis of how LotLine could be wrong. It is not a measured error rate. There is no independent ground truth for any parcel. The 15-parcel expected set was written by the team, so it measures conformance to the specification and nothing more.

**Definitions.** A *false advance* means one of two things: a lot LotLine advanced that informed diligence would not advance, or a lot that belongs in this family but would be advanced because the safeguard did not fire. A *false deferral* means the reverse: a lot placed in this family (deferred, excluded or routed) that informed diligence would have advanced. The "Detected by current tests?" column cites the tests that would catch the mechanism. In almost every case the tests check that LotLine follows its declared policy on the inputs it was given. **No test can check whether a public-record input is true on the ground.**

Cohort counts are from `uv run python -m evaluation.run` (Experiment 2). On the 14 advertised vacant lots: Advance 7, Defer: missing or conflicting records 3, Defer: site conditions unknown 3, Do not advance 1. Of the 96 Treasury records, 19 are routed out of universe and 63 are structures.

## Per outcome family

### Advance to staff review (7/14: Benezet, Wylie, Michigan 14N100, Michigan 15S66, Dearborn, Kemper, Saline)

| | Mechanism | Detected by current tests? | Real-world evidence that resolves it |
|---|---|---|---|
| **False advance** (most plausible) | **The short side of the minimum bounding rectangle (MBR) is not the frontage.** Width is computed as the MBR short side minus the side setbacks (`dimensions.compute_scenarios`). On an irregular, flag-shaped or rotated parcel, the MBR overstates the buildable width, so the dimensional score can come out as 2 when the real frontage is under 20 ft. | **No.** `tests/test_engine_units.py` and `tests/test_engine_labels.py::test_setback_screen` check the arithmetic on the recorded MBR. They cannot check that the MBR matches the actual lot shape. | Boundary survey, or the recorded plat or deed dimensions (licensed surveyor or County plat) |
| False advance | **The 30 ft corner heuristic misses a real corner.** `possible_corner` means two street centerlines lie within 30 ft of the parcel. A wide right-of-way can put a centerline more than 30 ft away. The lot is then scored only as interior, which is the optimistic single number. N4 in Experiment 6 shows what that assumption does. | **No** for the heuristic itself. The range logic is tested (`tests/test_engine_units.py::test_possible_corner_range_does_not_collapse`, `tests/test_engine_invariants.py::test_michigan_corner_range`). | County plat, a site visit, or a Zoning Administrator determination of frontage |
| False advance | **The slope25 screening layer is not the adopted Steep Slope Overlay (SS-O) map.** A layer gap (resolution, or a sliver below its threshold) leaves the terrain family unflagged. The environment score then stays at 2, the band is not capped at Conditional, and no §906.08 check is added. | **No.** The cap logic is tested (`tests/test_engine_units.py::test_slope25_caps_band_on_real_style_parcel`), but not the layer's coverage. | City SS-O map check, topographic survey, Zoning Administrator |
| False advance | **The assessment use description (usedesc) is stale.** The lot is recorded as VACANT while a structure is standing, and no PLI condemned case exists to raise the critical conflict. | **No.** The conflict fires only when a condemned case exists (`tests/test_engine_units.py`; memo case 1 in `tests/test_memo_cases.py`). | Site visit, current aerial imagery, PLI records |
| False advance | Questions outside the model: contextual setbacks (Ch. 925), legal access or paper streets, title (the sale does not clear it), utilities, and lot-of-record status where the records agree. | By design, these are listed as next checks rather than evaluated (`tests/test_engine_labels.py::test_next_checks_exact_order`). | Zoning Administrator, title examiner, DOMI, PWSA, surveyor |
| False advance | **Sale status changes after the snapshot** (the owner pays, redeems or obtains a court stay). | Partly. `tests/test_engine_units.py::test_stale_sale_status_source_warns` covers the stale-date warning. The pre-spend check "verify current advertised sale status" is always on the packet's check list. **Experiment 7 found that a Claude-assembled memo can omit it: it was present in 0/84 accepted memos.** It is not a mandatory memo claim. | City Treasurer / Real Estate Division |
| False deferral | This family does not defer. The nearest error is **mis-banding**: a slope25 sliver caps the band at Conditional (Kemper and Saline show "5 of 6: Conditional"), or a false `possible_corner` widens the range (Benezet 5–6). | Tested only for conformance. | Survey; SS-O map check |

### Defer: missing or conflicting records (3/14: Centre 10-S-5, Centre 10-R-108, Walcott)

| | Mechanism | Detected by current tests? | Real-world evidence that resolves it |
|---|---|---|---|
| **False deferral** (most plausible) | **A PLI condemned case outlives a demolition.** The case stays active after the structure is gone, so a lot that really is vacant becomes Not scorable. All three deferrals in this family carry that critical conflict. In Experiment 6, N3 would have advanced Centre 10-R-108 at 6 of 6. | **No.** Tests confirm the conflict fires and withholds the score (`tests/test_engine_units.py`, memo case 1). They cannot tell a stale case from a live one. | PLI case status and inspection history, a site visit, demolition permit records |
| False deferral | **An area conflict comes from a record artifact.** The assessment lot area can predate a consolidation or subdivision, or the GIS polygon can include right-of-way. For Centre 10-S-5 the minimum (2,400 sf) falls between 1,672 sf and 4,305 sf. | Detection and severity are tested (`tests/test_engine_units.py::test_material_conflict_withholds_dimensional_only`, `test_area_gap_formulas`). Which record is right is not testable, and it is deliberately not resolved. | Deed and survey; County Real Estate |
| False deferral | **A LotLine tool gap, not a site problem.** For example, RIV-RM dimensions are not encoded, which withholds dimensional for Walcott (`tests/test_engine_invariants.py::test_riv_rm_dimensions_still_withheld`). | Yes. The limitation is declared and tested. | Encode the rules from §905/§911 with citations |
| False advance (safeguard misses) | **Both area sources are wrong in the same direction.** If both sources exceed the minimum while the deed area is below it, no conflict is raised and the lot can advance. | **No.** | Deed and survey |
| False advance | **There is no split-zoning or zone-disagreement detector.** `detect_conflicts` raises only current_condition, sale_universe and lot_area. The kind `zoning_split` is labeled in the memo layer but never raised. A parcel crossing a district boundary gets a single polygon district. On this snapshot, `zone` equals `zoning_polygon` on every prepared parcel. | **No.** | Zoning Administrator zoning verification letter |

### Defer: site conditions unknown (3/14: Banksville, Platt, Mossfield; all in the H (Hillside) district)

| | Mechanism | Detected by current tests? | Real-world evidence that resolves it |
|---|---|---|---|
| **False deferral** (most plausible) | **The survey-dependent Hillside exception (§911.04.A.69) could be grantable.** A contiguous area under 30% slope may exist, but LotLine defers every H lot until a survey shows it. That is conservative by design. | Tested as policy (`tests/test_engine_invariants.py::test_h_site_standard_barrier_names_clearing_cap`). The ground truth is not testable. | Topographic survey; Zoning Administrator pre-application meeting |
| False advance (safeguard misses) | **A lot is steep but not in an H district**, and the slope25 layer misses it (see the Advance family above). | **No** for layer coverage. | Topographic survey; SS-O map |
| False deferral | **The zoning polygon assigns H to a lot that is mostly in another district** (split zoning, see above). | **No.** | Zoning verification letter |

### Do not advance for housing under stated screening policy (1/14: McClure, UI district)

| | Mechanism | Detected by current tests? | Real-world evidence that resolves it |
|---|---|---|---|
| **False deferral** (most plausible) | **A district permission is miscoded in `data/district_rules.csv`**, or housing is reachable through a path the screening policy excludes (a variance or special exception, or a pending rezoning). | Partly. `tests/test_loaders.py::test_rule_permissions_are_canonical` checks the vocabulary, not whether the code is correct. Correctness rests on the citation audit (tier 1) and `docs/label_changes.md`. | Primary-source code check; Zoning Administrator; Zoning Board of Adjustment (ZBA) precedent |
| False advance | **The reverse miscoding:** a district that prohibits housing is coded P. | Same as above. | Same as above |

### (routing) Out of sale universe (19/96 Treasury records)

| | Mechanism | Detected by current tests? | Real-world evidence that resolves it |
|---|---|---|---|
| **False deferral / exclusion** (most plausible) | **PIN normalization mismatch** (leading zeros, or a supplement such as `0088G00313000A00`), or a lot added to the sale after the 2026-09-16 advertisement. | Yes for normalization on this snapshot (`tests/test_loaders.py::test_pins_keep_leading_zeros`, `tests/test_reconcile.py::test_runtime_reconciliation_matches_expected_labels`, `test_garfield_is_out_of_universe`). Later amendments cannot be tested. Experiment 1 re-derives the join independently. | Current City advertisement or amendment; City Treasurer |
| False advance / inclusion | **A lot is withdrawn after the advertisement** (paid, redeemed, or under a court order) and stays in the universe. | Partly: the stale-source warning and the pre-spend check exist (see Advance above); there is a price cross-check (`tests/test_reconcile.py::test_price_mismatch_detected`). | City Treasurer / Real Estate Division |

### (routing) Structure: vacant-land model not applicable (63/77 advertised)

| | Mechanism | Detected by current tests? | Real-world evidence that resolves it |
|---|---|---|---|
| **False deferral / exclusion** (most plausible) | **usedesc is stale the other way:** a demolished structure is still recorded as a structure, so a lot that really is vacant is never screened. | **No.** Vacancy is decided by usedesc alone (`tests/test_loaders.py::test_structure_and_vacant_counts_come_from_usedesc`). | Demolition permits, PLI records, a site visit |
| False advance / inclusion | A structure recorded as VACANT enters the vacant-lot model (see the stale usedesc row under Advance). | **No**, unless a condemned case exists. | Site visit |

## Cross-cutting mechanisms

| Mechanism | Effect | Detected by current tests? | Evidence that resolves it |
|---|---|---|---|
| **The RCO field mixes in overlay notes.** The source `rco_overlay` column holds both Registered Community Organization (RCO) names and overlay notes. The loader moves values in parentheses to `other_overlay`. An overlay name without parentheses would still be shown as an RCO contact. | Affects only the community-review contact and its next check, never a score. | Partly (`tests/test_loaders.py::test_parenthesized_overlay_is_not_an_rco`). | City RCO registry |
| **Free text in a raw source field reached approved memo claims (fixed).** The deterministic memo used to quote `pli_latest_event` word for word. It was latent, because every value in the frozen snapshot is an ISO date. | Before the fix, in SYNTHETIC probes: benign-sounding fabricated owner/utility text was accepted on the Claude path (11/14 lots), and hostile text made the fallback memo fail its own check (14/14). Engine decisions never changed. | `tests/test_evaluation_adversarial.py::test_raw_source_text_cannot_reach_accepted_memo` (now a passing regression test). | Fixed in `lotline/facts.py`: a non-ISO value in a date field is classed `untrusted_text`, never quoted and not selectable. |
| **Checker-only gap.** When LLM-authored prose goes straight to `produce_memo`, the checker accepts a permission inversion ("Two-unit housing is permitted in R1D-L.") and fabricated owner or utility sentences. This cannot happen through the live protocol, because `parse_llm_json` returns only engine-authored catalog claims. | None at runtime today. It would matter if a free-text path were ever added. | Recorded as `xfail` in `tests/test_evaluation_adversarial.py::test_checker_rejects_permission_inversion_prose`. | None needed while the ID-only protocol stands |
| **Upstream extraction is not reproducible.** The queries that built the prepared snapshots were not kept. | Any extraction error is inherited silently. | **No.** | Re-pull from the WPRDC, County and City sources with retained queries (Experiment 9) |

## What the 14-parcel cohort cannot show

- **Error rates.** No lot has an independent outcome label. The expected labels were written by the team, and n = 14 is too small for a rate (one error moves the rate by 7 percentage points).
- **Whether the inputs are true on the ground.** Nothing here checks frontage, corner status, slope, current condition or title. The tests check that the declared policy was applied faithfully to the recorded inputs.
- **Coverage of rare states.** The real cohort has no undetermined FEMA zone, no failed layer query and no missing area source. Those states appear only as SYNTHETIC perturbations (Experiments 5 and 6), which say nothing about how often they occur.
- **Usefulness.** Whether a packet changes a practitioner's decision, or saves time, is untested.
- **Generalization** to other sales, other cities, structures or other parcel types.

## Smallest defensible prospective study (proposed, not run)

**Design.** A pre-registered, blinded agreement-and-timing pilot at the next City of Pittsburgh Treasurer Sale.

1. **Pre-register** before the next advertisement is published (for example on OSF). Record the hypotheses, the frozen LotLine commit and policy, the primary and secondary measures, the adjudication rules and the analysis script.
2. **Units.** Every advertised vacant lot in the next sale. If that is fewer than about 20, pool two consecutive sales. LotLine packets are generated and hashed before any practitioner sees a lot.
3. **Raters.** Two or more acquisition practitioners (for example land-bank or CDC acquisition staff) who have not seen LotLine outputs. Each rater independently classifies each lot as advance, defer (naming the blocker) or do not advance, using only public records. Each rater then re-screens a randomized half of the lots with the LotLine packet: a crossover by lot, with order counterbalanced.
4. **Primary measure.** Disposition agreement between LotLine and each rater, and between the raters. Report raw n/N and Cohen's kappa with a 95% confidence interval. Separately, for each lot LotLine advances, record whether the rater identified a disqualifying issue. For each deferral, record whether the rater confirmed the named blocker.
5. **Secondary measures.** Time to decision per lot, with and without the packet. Whether the rater found any conflict or missing input that LotLine did not flag.
6. **Adjudication.** A third expert resolves each discordant lot using the real-world evidence named above: a Zoning Administrator letter, a site visit, the PLI case status, and a survey or plat where available. Record who was right and why, including cases where LotLine was wrong.
7. **Honest framing.** With roughly 20 to 40 lots this is a feasibility and calibration pilot, not a powered accuracy study. The confidence intervals will be wide and must be reported as they are. A 6 to 12 month follow-up on advanced lots can test whether the named blockers were the ones that actually stopped or slowed acquisition. That follow-up is the first real outcome evidence LotLine would have.
