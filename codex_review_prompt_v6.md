# Review request (round 5): LotLine plan v6, final consistency pass before build

You gave v5 a GO (about 65% top-3 odds) and listed must-fix-Friday items. v6 applies all of them. This round is a **short confirmation pass**, not a redesign. Report only: (a) whether each round-4 item is resolved, (b) any new contradiction introduced by the v6 edits, (c) anything that would break the Saturday vertical slice. Label each issue must-fix-Friday, fix-during-build, or ignore. If everything is resolved, say so plainly.

**Files in `~/datasets/lotline_prep/` (read all; run read-only checks on the CSVs):**
- `LotLine_Hackathon_Plan_v6.pdf`
- `build_contract.md` (v6)
- `golden_set_prescreen.csv`
- `treasury_sale_2026-10-02_enriched.csv`
- `advert_2026-09-16_reconciliation.csv`
- `README_prep_pack.md`

Do not write application code (build window rule).

## Your round-4 items and what v6 did
1. **Environmental scoring vs CSV.** Now scored by three hazard families: terrain (landslide-prone OR slope25), undermining, FEMA SFHA; 2 = none, 1 = one, 0 = two or more. Slope25 cross-listed in the zoning tile, counted once. CSV adds `hazard_families`; Centre 10S5 environment now 1 (terrain).
2. **Wylie and Kemper outcomes.** Wylie, Kemper and Saline now "Defer: missing or conflicting records (rules not encoded)". Kemper's 55% area gap is Disclose-level; its dimensional component is withheld only because P-district dimensions are not encoded (score_notes states this).
3. **Dimensional boundaries.** 2 if envelope width >= 20 ft; 1 if >= 10 and < 20; 0 if < 10; unresolved corner shows the range of both scenarios (Benezet 1 to 2, Michigan 15S66 1 to 2, Dearborn 0 to 1).
4. **Evidence coverage defined.** Five Boolean groups: G1 assessment record AND County GIS polygon present; G2 district resolved AND use + dimensional rules encoded; G3 all four screening layers queried; G4 PLI violations and condemned datasets queried; G5 in City advertisement AND regulations captured. Conflicts are reported as confidence, not missing evidence. CSV column `evidence_coverage` recomputed; definition stored in `evidence_coverage_definition`. Result: 5/5 for most advertised lots; 4/5 for LNC, P, RIV-RM lots; Garfield 4/5 (not advertised).
5. **Schema/document drift.** `env_flags_checked_layers` renamed `landslide_prone_layer`; README `pli_count` references removed (field is `pli_event_rows`); PDF now says 10 adversarial/regression cases and "four screening outcomes plus routing states"; contract section 1 labels the seven values; acceptance test adds PIN search (Benezet PIN and an unknown PIN) and the Benezet vs Michigan comparison, with a target of items 1 to 5 working for Benezet and Centre by early Saturday afternoon.
6. **Sale-number types.** `advert_sale_no` cast to integer in the enriched CSV.
7. **Benezet framing.** "Clean-record, apparently lower-discretion example (not an acquisition recommendation); market demand and appraisal feasibility not evaluated"; assessed land value not foregrounded.
8. **Storyboard.** Adopted your timing (0:00 to 4:00); Dearborn/Rockland removed from the video, kept in app and README. Injection and stale-source cases marked SYNTHETIC FIXTURE; injection pass = engine result unchanged AND no injected instruction reflected in the memo. Kemper adversarial case rewritten to separate "disclosed gap" from "dimensions unencoded".

## Specific checks requested
1. Recompute every `score_environment_0to2` from `landslide_prone_layer`, `slope25_layer`, `undermined_layer`, `fema_zone` using the family rule; report any mismatch.
2. Recompute `evidence_coverage` from the stated definition; report any mismatch.
3. Check that every `screen_outcome_prelim` follows contract section 1 (especially lots in P, LNC, RIV-RM, H, UI).
4. Check `ease_result` totals and ranges add up from the component columns.
5. Confirm the PDF, contract and README now agree on: outcome count, adversarial case count, hero parcels, storyboard, environment rule, dimensional rule, evidence coverage.
6. Anything in the acceptance test that still cannot be verified objectively.

## What we want back (concise)
1. Round-4 items: resolved / not resolved, one line each.
2. New issues from v6 edits, labeled.
3. Results of the six checks.
4. Final GO / NO-GO and top-3 probability.
