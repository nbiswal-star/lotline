# Expected-label changes (rule verification, 2026-09-26)

`tests/fixtures/expected_labels.csv` holds hand-computed test labels. The engine never reads them. On 2026-09-26 the district rules in `data/district_rules.csv` were re-verified against the Pittsburgh Code on ecode360 (legislation through 2026-09-16) and Legistar. This page lists every label that changed and the code section behind each change.

## Rule provenance

- **§903.03 residential minimum lot sizes.** These come from Ord. No. 10-2025 (Council Bill 2025-1579). It was passed 2025-05-06 and took effect 2025-05-07. They are the current code, not a draft.
  - The ordinance also deleted every "minimum lot size per unit" (density) row.
  - LotLine therefore applies no per-unit density test.
  - No later amendment is in force: Bill 2026-0834 and Bill 2025-1545 are both held in Council.
- **New columns.** Every rule row now carries `rules_as_of` (2026-09-16) and `amended_by` (the history note).
- **Citation corrections:**
  - Residential rows cite the §903.03.x.2 tables.
  - H cites §905.02.C.
  - P cites §905.01.C.
  - LNC cites §904.02.C.
  - RIV-RM cites §905.04.E. It previously cited "908", which is Public Realm Districts.
- **Newly encoded dimensions:**
  - P (§905.01.C): minimum lot 3,200 sf; front 30, rear 20, exterior side 20, interior side 5 ft.
  - LNC (§904.02.C): minimum lot 0; front, exterior side and interior side none; rear 20 ft. The code requires the 20 ft rear setback only when the rear is not adjacent to a way. LotLine encodes it conservatively.
- **Still not encoded.** RIV-RM stays unencoded because its build-to zone and riparian buffer are not modelled.
- **H setbacks stay blank.** §905.02.C says "none", but H dimensional fit is withheld anyway by the §911.04.A.69 site standard. The rule's site-standard text now records "setbacks none per 905.02.C", the §911.04.A.69(b) clearing cap (the larger of 10% or 2,400 sf) and site plan review under §905.02.C.3.

## Engine text changes that affect labels

| Change | Citation |
|---|---|
| P parcels get the next check "site plan review (§905.01.D)" (owner: Zoning Administrator / Planning). | §905.01.D.1(a) |
| P parcels get the barrier "P (Parks and Open Space) district: single-unit detached is permitted by right under §911.02; site plan review applies". | §911.02; §905.01.D |
| LNC parcels get the next checks "site plan review (§904.02.D)" and "residential compatibility (Ch. 916)". | §904.02.D; Ch. 916 |
| The next checks "review Chapter 905.01 dimensions" and "review Chapter 904 dimensions" are removed, because those dimensions are now encoded. | §905.01.C; §904.02.C |
| RIV-RM text now reads "review §905.04.E (RIV-RM) dimensions" and "§905.04.E (RIV-RM) dimensions are not encoded". | §905.04.E |
| Hazard check texts are unchanged. Their triggers now cite the relevant sections. The slope and geotechnical review cites §906.08 (possible Steep Slope Overlay Planning Commission review) and §915.02 where slope25 overlaps, and §906.04 where the parcel is landslide-prone. The mine-subsidence review cites §906.05. | §906.04, §906.05, §906.08, §915.02 |
| The H site-standard barrier now names the clearing cap. | §911.04.A.69(b) |

## Label changes by parcel

The envelope is computed as follows:

- Interior width = MBR short side − 2 × interior side setback.
- Depth = MBR long side − front setback − rear setback.
- Width bands: 20 ft or more scores 2; 10 ft or more scores 1.
- Ease = use + dimensional + environment.

| PIN | Parcel | Field | Old | New | Basis |
|---|---|---|---|---|---|
| 0088R00001000000 | Saline St (P) | outcome | Defer: missing or conflicting records | Advance to staff review | §905.01.C; §911.02 (single-unit P) |
| | | dimensional | withheld | 2 (width 103 − 2×5 = 93 ft) | §905.01.C |
| | | setback screen | not computed | Illustrative only: interior 93x171 ft (depth 221 − 30 − 20) | §905.01.C |
| | | ease | Partial: 3 of 4 known | 5 of 6: Apparently lower-discretion (2 + 2 + 1) | build contract §3 |
| | | coverage | 4/5 | 5/5 (G2: use and dimensions encoded) | |
| | | area conformity | n/a | 21,780 and 21,095 sf, both ≥ 3,200 | §905.01.C |
| | | barriers | "P-district dimensions are not encoded"; terrain | P-district caveat; terrain screening overlap | |
| | | checks | "review Chapter 905.01 dimensions" | "site plan review (§905.01.D)" | §905.01.D |
| 0088G00313000A00 | Kemper St (P) | outcome | Defer: missing or conflicting records | Advance to staff review | §905.01.C |
| | | dimensional | withheld | 2 (width 67 − 10 = 57 ft; depth 73 − 50 = 23 ft) | §905.01.C |
| | | setback screen | not computed | Illustrative only: interior 57x23 ft | |
| | | ease | Partial: 3 of 4 known | 5 of 6: Apparently lower-discretion | |
| | | coverage | 4/5 | 5/5 | |
| | | conflict | disclose | disclose (unchanged). The 55% gap (10,276 vs 4,606 sf) crosses no threshold because both sources are ≥ 3,200. | §905.01.C |
| | | barriers and checks | as for Saline | as for Saline | |
| 0010L00127000000 | Wylie Ave (LNC) | outcome | Defer: missing or conflicting records | Advance to staff review | §904.02.C; §911.02 (single-unit and two-unit P) |
| | | dimensional | withheld | 2 (width 46 ft; no side setbacks) | §904.02.C |
| | | setback screen | not computed | Illustrative only: interior 46x74 ft (94 − 0 − 20) | |
| | | ease | Partial: 3 of 4 known | 5 of 6: Apparently lower-discretion (2 + 2 + 1) | |
| | | coverage | 4/5 | 5/5 | |
| | | conflict | disclose | disclose (unchanged). There is no lot minimum. | |
| | | barriers | "Chapter 904 dimensions are not encoded"; undermining | undermining screening overlap | |
| | | checks | "review Chapter 904 dimensions" | "site plan review (§904.02.D)"; "residential compatibility (Ch. 916)" | §904.02.D; Ch. 916 |
| 0010R00108000000 | Centre Ave (LNC) | outcome | Defer: missing or conflicting records | unchanged (critical conflict: current site condition unverified) | build contract §1–2 |
| | | dimensional | withheld | 2 (width 36 ft) | §904.02.C |
| | | setback screen | not computed | Illustrative only: interior 36x79 ft (99 − 0 − 20) | |
| | | ease | Not scorable | Not scorable (unchanged, because of the critical conflict) | |
| | | coverage | 4/5 | 5/5 | |
| | | barriers | "…; Chapter 904 dimensions are not encoded" | "current site condition is unverified" | |
| | | checks | "review Chapter 904 dimensions" | "site plan review (§904.02.D)" (area 2,675 sf in one source is ≥ 2,400); "residential compatibility (Ch. 916)" | §904.02.D |
| 0042D00039000000 | Walcott St (RIV-RM) | barriers and checks | "Chapter 908 …" | "§905.04.E (RIV-RM) dimensions are not encoded" / "review §905.04.E (RIV-RM) dimensions" | §905.04.E |
| | | outcome, ease, coverage | | unchanged (Defer, Not scorable, 4/5) | |
| 0081R00122000000, 0034A00290000000, 0016N00110000000 | H parcels | barriers | site standard requires survey | adds "clearing cap max(10% or 2400 sf) per 911.04.A.69(b)" | §911.04.A.69(b) |

No other label changed. The minimum lot sizes, setbacks and permissions for R1D-L, R1D-H, R1A-VH, R2-H, RM-M, H and UI are the same as before. Removing the density test changes no outcome:

- The R2-H lots (2,562–3,141 sf) meet the 1,200 sf minimum.
- The RM-M lot at Centre Ave 10S5 (1,672 vs 4,305 sf) still straddles the 2,400 sf minimum. It stays Defer because of its critical conflicts.

## Open policy note

Advancing the two P-district parcels follows from the code: single-unit detached is permitted by right in P (§911.02), and the §905.01.C dimensions are met. Whether a Parks-district parcel should be advanced for housing is a policy choice for staff, not a code requirement. LotLine therefore shows the factual P-district caveat and does not invent a deferral.
