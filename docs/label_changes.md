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

## Round 2: judge review (2026-09-26)

Three judges (technical, housing practitioner, investor) reviewed the engine. The lead approved a consolidated fix list. This section records every engine rule change and every label change it caused.

### Label file format

The `expected_barriers` and `expected_unresolved_checks` columns are now separated by ` | ` instead of `;`. Some texts contain semicolons, such as the Treasurer Sale terms check and the H barrier. `test_barriers` is now exact, in order, for all 15 rows. Previously 6 rows were only checked for key content.

### Engine rule changes

| # | Change | Where |
|---|---|---|
| A1 | Loader: a lot area or bounding-rectangle side of 0 becomes unknown (None) and adds a load warning ("0 sf recorded; treated as unknown"). A negative area, side, setback or minimum raises `SnapshotError`. The engine also treats any area ≤ 0 as unknown, so it never scores one. The real snapshot has two Treasury structures with lotarea 0. They are now None, with warnings in `Snapshot.load_warnings`. | loaders.py; dimensions.valid_area |
| A2 | No Advance while any component (use, dimensional, environment) is withheld. Such a parcel routes to Defer: missing or conflicting records. | routing.py |
| A3 | FEMA zones are validated against the NFHL vocabulary (`models.sfha_status`). Zone D, and any unrecognized code, is unknown, so environment is withheld. The engine re-validates `fema_zone` even for records built outside the loader. | models.py; hazards.effective_sfha |
| A4 | Every Defer names its missing or conflicting input in at least one barrier and one next check. This covers a missing area source, missing geometry, a blank setback (including the exterior side on a possible corner), a blank minimum, a failed layer query, an undetermined FEMA zone, an unrecognized permission code and missing parcel records. | checks.py |
| A6 | Removed the `except ImportError` fallback. Price tolerance lives only in reconcile.py and is re-exported by policy.py; conflicts.py reuses `reconcile.prices_agree`. The per-unit density code (DensityRule, `two_unit_density_ok`) is removed. | engine/__init__.py; use.py |
| A7 | A minimum of 0 is described as "no minimum lot size". Every area has thousands separators. New Partial format: "Partial: 2 of 4 known points; dimensional withheld (reason)". | scoring.py; conflicts.py; checks.py |
| A8 | Each scenario scores min(width band, depth band), both on the 20/10 ft thresholds. This is a LotLine screening assumption. It changes no real-parcel score: every real depth is 23 ft or more. | policy.py; dimensions.py |
| B9 | A slope25 overlap caps the band at Conditional (policy.BAND_CAPS) and appends "(possible Steep Slope Overlay review, §906.08)". The cap adds a reason only when it lowers the band. | scoring.py; policy.py |
| B10 | P district: the factual §911.02 caveat is replaced by a risk barrier (confirm park, greenway or open-space designation or use). A new next check, "open-space / greenway designation" (owner: City Planning, open space & parks planning), carries the §911.02 note in its trigger. | policy.py |
| B11 | A disclose-level area gap of 25% or more (directional or symmetric) adds "deed and record-area reconciliation" (owner: County Real Estate + licensed surveyor) and a barrier stating the gap. The score is unchanged. | checks.py |
| B12 | H district: the barrier is now plain language, with no raw CSV text. A new next check is "Administrator Exception for single-unit (§911.04.A.69)" (owner: Zoning Administrator). | policy.py |
| B13 | A lot area below a positive district minimum in any source adds "lot-of-record eligibility (§921.04.A)…" (owner: Zoning Administrator + County deed records). When all sources agree the lot is below the minimum, the barrier reads "records agree the lot is below the N sf district minimum; §921.04.A lot-of-record path requires Zoning Administrator review". | checks.py |
| B14 | Every advertised parcel, structures included, gets the Treasurer Sale terms next check (90-day redemption; claims not divested). The owner is "title examiner or attorney". The title owner string is now simply "title examiner or attorney". | checks.py; policy.py |
| B15 | When upset / assessed land ≥ 3.0, the barrier "upset price is N× assessed land value (acquisition-burden indicator only, not market value)" is added. | checks.py |
| B16 | Owners: legal access is "title examiner + DOMI (right-of-way, paper streets)". Mine subsidence is "PA DEP Bureau of Abandoned Mine Reclamation / Mine Subsidence Insurance + geotechnical engineer". | checks.py |
| B17 | RIV-RM barrier: "LotLine does not yet model RIV-RM dimensions (§905.04.E); this is a tool limitation, not a records problem". The outcome value is unchanged. | policy.py |

### Decisions and deviations

- **Kemper "area disagreement is disclosed".** The engine is changed to match the label's intent, applied consistently. Any disclose-level gap of 25% or more is now a barrier that states the gap and that no score changes. Kemper (55%) and Mossfield (32%) both get it. Before, only Kemper's label carried a gap barrier, and the engine emitted none for either parcel.
- **Records agree the lot is below the minimum (B13).** The outcome stays "Defer: missing or conflicting records". The other outcomes do not fit:
  - "Defer: site conditions unknown" is about survey-dependent site standards.
  - "Do not advance" would be wrong, because §921.04.A says the Zoning Administrator "shall approve" single-unit use for a qualifying lot.
  - "Advance" would break the contract's conformity condition.
  Eligibility turns on County deed records (separate ownership, and vacant when the code applied), which LotLine does not hold. "Missing records" is therefore accurate, and the barrier says the records agree. No real parcel reaches this path. Centre Ave 10S5 is below the minimum in one source only and is critical anyway.
- **H barrier wording.** The approved text said "a buildable area under 30% slope". It now says "a contiguous area under 30% slope for the house". The memo checker forbids "buildable", and §911.04.A.69(a) itself says "contiguous area of the lot less than thirty (30) percent in existing slope".
- **Sale terms citation.** The text reads "Act 171 of 1984 sec. 304". With "§304", the memo claim checker read the reference as a Pittsburgh Code section and failed it against the section allowlist.
- **Partial format.** "Partial: 2 of 4 known points; dimensional withheld (reason)" keeps the `Partial: X of Y known` prefix, so the memo checker can still parse it. "known points" makes clear that Y counts points from the components that could be scored, not components.
- **Michigan 15S66.** The slope25 cap applies, but the band is already Conditional (3–4), so no reason is appended.

### Label changes by parcel

| PIN | Parcel | Field | Old | New | Basis |
|---|---|---|---|---|---|
| All 14 advertised | | checks | … title; legal access … | adds "Treasurer Sale terms: 90-day redemption; mortgages, judgments, water claims and other secured claims are not divested (2026-10-02 regulations; Act 171 of 1984 sec. 304)" after "title" | B14 |
| 0015S00066000000 | Michigan 15S66 | barriers | "terrain and undermining screening overlaps; corner status unverified" | "corner/frontage status remains unverified \| terrain and undermining screening overlaps" (the engine's fixed wording and order; the label had drifted) | A5 |
| 0014N00100000000 | Michigan 14N100 | barriers | narrow; undermining | adds "upset price is 8.0× assessed land value (…)" | B15 |
| 0010S00005000000 | Centre 10S5 | barriers | "…cross the 2400 sf minimum" | "…cross the 2,400 sf minimum" and adds "upset price is 149.9× …" | A7, B15 |
| | | checks | | adds "lot-of-record eligibility (§921.04.A): …" (1,672 sf < 2,400 in the assessment record) | B13 |
| 0010R00108000000 | Centre 10R108 | barriers | site condition | adds "upset price is 3.0× …" | B15 |
| 0042D00039000000 | Walcott (RIV-RM) | barriers | "§905.04.E (RIV-RM) dimensions are not encoded" | "LotLine does not yet model RIV-RM dimensions (§905.04.E); this is a tool limitation, not a records problem" and adds "upset price is 4.5× …" | B17, B15 |
| 0010L00127000000 | Wylie (LNC) | barriers | undermining | adds "upset price is 8.0× …" before it | B15 |
| 0081R00122000000 | Mossfield (H) | ease | Partial: 2 of 4 known | Partial: 2 of 4 known points; dimensional withheld (survey-dependent site standard, §911.04.A.69) | A7 |
| | | barriers | raw §911.04.A.69 text | plain H barrier; "lot-area records disagree by 32% (…); both exceed the 3,200 sf minimum, so no score change"; "terrain screening overlap" (the engine always listed it; the label omitted it) | B12, B11 |
| | | checks | | adds "deed and record-area reconciliation" (32% gap) and "Administrator Exception for single-unit (§911.04.A.69)" | B11, B12 |
| 0034A00290000000 | Platt (H) | ease | Partial: 1 of 4 known | Partial: 1 of 4 known points; dimensional withheld (…) | A7 |
| | | barriers / checks | raw text | plain H barrier; adds the Administrator Exception check | B12 |
| 0016N00110000000 | Banksville (H) | ease / barriers / checks | as for Platt | as for Platt | A7, B12 |
| 0088R00001000000 | Saline (P) | ease | 5 of 6: Apparently lower-discretion | 5 of 6: Conditional (possible Steep Slope Overlay review, §906.08) | B9 (slope25) |
| | | barriers | P caveat (§911.02) | "Parks and Open Space (P) district: confirm whether the lot is designated or used as park, greenway or open space before pursuing housing" | B10 |
| | | checks | | adds "open-space / greenway designation" before the site plan review | B10 |
| 0088G00313000A00 | Kemper (P) | ease | 5 of 6: Apparently lower-discretion | 5 of 6: Conditional (possible Steep Slope Overlay review, §906.08) | B9 |
| | | barriers | P caveat; "area disagreement is disclosed" | P risk barrier; "lot-area records disagree by 55% (assessment 10,276 sf vs County GIS 4,606 sf); both exceed the 3,200 sf minimum, so no score change" | B10, B11 |
| | | checks | | adds "deed and record-area reconciliation" and "open-space / greenway designation" | B11, B10 |

No outcome, component score, coverage, conflict level, hazard family or setback screen changed on any of the 15 rows. Every outcome is unchanged.

## Round 3: decision-impact ordering (2026-09-26)

The UI shows the first barrier as the "principal barrier" and the first parcel-specific next check on the triage board and in Compare. Before Round 3 both lists followed a fixed construction order, so for Michigan 15S66 the principal barrier was the unverified corner, while the terrain and undermining overlaps (which lower the environment score and trigger §906.08/§906.05 reviews) came second. Both lists are now ordered by decision impact.

**Rule.** Every barrier and next check is tagged with one category and the list is stable-sorted by `policy.DECISION_IMPACT_ORDER` (data, in `lotline/engine/policy.py`); ties keep their previous order:

1. critical conflicts (current condition, sale universe)
2. material conflicts (lot area crosses the minimum)
3. records agree the lot is below the minimum; §921.04.A lot-of-record check
4. use prohibition
5. rules not encoded (tool gap: district dimensions, blank setback/minimum, unrecognized permission code)
6. missing or invalid inputs (parcel records, geometry, lot area, layer query, undetermined FEMA zone)
7. survey-dependent site standards (H, §911.04.A.69, including the Administrator Exception check)
8. hazard-family overlaps (terrain, undermining, FEMA)
9. narrow or shallow illustrative envelope
10. Parks / open-space designation (P)
11. large disclose-level area gap (deed and record-area reconciliation)
12. acquisition burden (upset ≥ 3× assessed land value)
13. corner / frontage status unverified
14. procedural district reviews (site plan review, Ch. 916 compatibility)
15. community-review and historic-review applicability
16. standard checks: the base checks (trigger "base") and the Treasurer Sale terms check, in their existing order (sale terms after title). These are never parcel-specific and always come last.

**Rationale.** A critical conflict stops scoring altogether, so nothing else matters until it is resolved. Conflicts and below-minimum records decide whether the lot conforms at all; a use prohibition or a tool gap decides whether LotLine can screen it; missing inputs withhold a component. Survey-dependent site standards and hazard overlaps lower scores and trigger code reviews; Parks designation and a large disclosed gap are policy/records questions that change no score; acquisition burden is an indicator only; corner status only narrows an illustrative envelope range. Procedural reviews apply to every lot of that district and size, so they follow the parcel-specific risks.

**No outcome, score, coverage, conflict level, hazard family or setback screen changed.** Only the order of `expected_barriers` and `expected_unresolved_checks` changed (same items; the test asserts exact order for all 15 rows). The UI's "first parcel-specific check" now also skips the Treasurer Sale terms check, which is a standard check.

| PIN | Parcel | Principal barrier (new) | First parcel-specific check (new) |
|---|---|---|---|
| 0015S00066000000 | Michigan 15S66 | terrain and undermining screening overlaps (was corner) | slope and geotechnical review (was corner/frontage status) |
| 0131N00031000000 | Benezet | corner/frontage status remains unverified (unchanged) | corner/frontage status (unchanged) |
| 0014N00100000000 | Michigan 14N100 | undermining screening overlap (was narrow envelope) | mine-subsidence review |
| 0010S00005000000 | Centre 10S5 | current site condition is unverified (unchanged) | current site-condition verification |
| 0010L00127000000 | Wylie (LNC) | undermining screening overlap (was acquisition burden) | mine-subsidence review |
| 0081R00122000000 | Mossfield (H) | H site standard (unchanged); terrain now before the 32% gap | Administrator Exception (§911.04.A.69) |
| 0088R00001000000, 0088G00313000A00 | Saline, Kemper (P) | terrain screening overlap (was Parks designation) | slope and geotechnical review |
| 0075S00108000000 | UI parcel | unchanged | floodplain determination |

Other rows: the same items moved behind parcel-specific checks (base checks last). Before Round 3, on every parcel without a possible corner, the UI's "first parcel-specific check" was the Treasurer Sale terms check, because its trigger is not "base"; it is now treated as a standard check.

### Related engine text changes (Round 3)

- The use reason cites sections as "§911.02" (was "Section 911.02"), matching every other engine text. No label contains it.
- Every scored component now carries a concise `short_reason` (≤ 90 characters) used by the UI card; the full reason stays in `reason`.
- `data/district_rules.csv` gains an optional `site_standard_summary` column (plain-language, cited) for display; the raw `site_standard` text is kept as provenance.

## Round 4: current-sale pre-spend gate (2026-09-26)

Every advertised parcel now includes the standard next check **"verify current advertised sale status before incurring costs"**, owned by **City Treasurer / Real Estate Division**. It is the first item inside the standard-check group; parcel-specific checks remain ordered by decision impact above that group. This check operationalizes the existing frozen-snapshot warning that advertised status may change by payment or court order before the sale.

The check was added to the 14 advertised rows in `tests/fixtures/expected_labels.csv`. The one record routed out because it is not in the advertisement retains its existing advertisement-verification routing check. No outcome, score, coverage, conflict, barrier, hazard family or parcel-specific check changed.

**Basis:** City advertisement dated 2026-09-16; the snapshot/staleness policy in `docs/build_contract.md` §§6 and 8; Treasurer Sale status can change before the recorded sale date. This is a workflow safeguard, not a new zoning or sale-law rule.
