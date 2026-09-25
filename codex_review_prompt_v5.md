# Review request (round 4): LotLine plan v5 + build contract, AI for Housing Hackathon, Pittsburgh

You gave v4 a GO with four must-fix items. v5 applies them, adds live polygon checks, changes the positive hero, and freezes the spec in a build contract. This is the **final pre-build check** before Saturday 9:00am ET. Keep it short: confirm what is now correct, and flag only issues that would cost judging points or break the demo. For each issue, label it must-fix-Friday, fix-during-build, or ignore.

Hats: civic tech engineer (Pittsburgh open data, 39h solo builds), housing practitioner (Pittsburgh zoning, Land Bank, CDCs), responsible AI researcher.

**Files in `~/datasets/lotline_prep/` (read all; run read-only checks on CSVs):**
- `LotLine_Hackathon_Plan_v5.pdf`
- `build_contract.md` (the frozen spec: outcomes, conflict policy, score contract, flag tiles, comparison, 10 adversarial cases, acceptance test, source manifest, storyboard, drop order)
- `golden_set_prescreen.csv` (15 vacant records, now with polygon zoning, RCO, historic, slope25, undermined, FEMA, streets within 30 ft, corner status, base-setback screen, component scores, ease result)
- `treasury_sale_2026-10-02_enriched.csv` (96 rows; `in_city_advert_2026_09_16`, `advert_sale_no`, `advert_match_method`, `pli_event_rows`)
- `advert_2026-09-16_reconciliation.csv` (77 accounts normalized to PIN; `pin_match`, `price_check`)
- `README_prep_pack.md`

If you have web access, spot-check doubtful facts and cite URLs. Do not write application code (build window rule).

## Constraints (unchanged)
Build window Sat Sep 26 9:00am to Sun Sep 27 11:59pm ET; Startup track; judging on Problem Value, User Fit & Usability, Technical Execution, Data & AI Integrity, Actionability, Continuation Potential. Challenge 1 requires parcel ID input (single or compare), a Development Ease Score, plain-language barriers, and flags across zoning / environmental / infrastructure / policy. 3 to 5 minute screen-recorded demo. No outreach possible. Likely solo builder with Cursor and LLM coding tools.

## Your v4 must-fixes and what v5 did
1. **Envelope overconfidence** → renamed "illustrative base-setback screen" with interior and corner cases; corner status field added ("POSSIBLE corner: verify" when two named streets lie within 30 ft of the parcel polygon). Dimensional component becomes a range when corner status is unverified.
2. **50% rule** → decision-impact policy: Critical (sale-universe mismatch, incompatible current-condition records, suspected wrong parcel) = parcel not scorable; Material (crosses controlling threshold or changes a component) = withhold only that component; Disclose (gap > 10%, no decision change).
3. **Condemned wording** → "Assessment classifies the parcel as vacant, while an active condemned/dead-end case remains associated with the parcel/address. Current site condition is unverified."
4. **Price-only reconciliation** → advertisement account numbers normalized to PIN (drop "1" + 2-digit ward; rebuild suffix); 77/77 PIN matches and 77/77 upset price checks.
Also fixed: §911.02 cited for use permission (§903 only for dimensions); Garfield advert flag normalized to N; Dearborn "relief likely" removed; `pli_count` renamed `pli_event_rows` and cast to integer; area gap formula documented (symmetric gap also displayed); "recurring development friction"; "each weekly dataset refresh ahead of a scheduled sale".

## New live checks (County parcel polygons from PASDA "Parcels 20260921" intersected with City GIS layers on services1.arcgis.com/YZCmUqbcsUpOKfj7 and FEMA NFHL layer 28)
- Polygon zoning equals point zoning for all 15; no split districts found.
- `PGHWebSlope25` overlaps: Michigan 15S66, Centre 10S5, Mossfield, Platt, Banksville, Saline, Kemper.
- `PGHWebUndermined` overlaps: Michigan 15S66, Michigan 14N100, Wylie, Platt.
- FEMA zone A partial: Banksville, McClure. All others zone X.
- Historic: Garfield Ave in Mexican War Streets Expansion (not advertised anyway).
- RCO overlays found for most lots (shown as community-review contact only).
- Streets within 30 ft: Michigan 15S66 (Estella Ave, Michigan St, Zelda Way, Arcadia Way); Benezet (Bronze St, Benezet Ave, Bench Way); Dearborn (N Winebiddle St, Dearborn St, Alhambra Way); Michigan 14N100 (Michigan St, Bolivar Way); Centre 10S5 (Centre Ave).

## Resulting changes
- **Positive hero is now Benezet St (0131N00031000000)**: R1D-L, 5,500 vs 5,327 sf, ~49x111 ft, no overlap in checked layers, no PLI casefiles, upset $1,433.76, land value $1,600. Score "5 to 6 of 6" (use 2, dimensional 1 to 2 pending corner check, environment 2). Interior envelope ~39x51 ft; if corner ~14x51 ft.
- Michigan 15S66 drops to "3 to 4 of 6: Conditional" (slope25 + undermined; possible corner; corner envelope ~13x70 ft).
- Michigan 14N100: 4/6 Conditional (17 ft interior width; undermined; demolition lien).
- Dearborn: 4 to 5 of 6 (20 ft; possible corner could leave ~0 ft width).
- Kemper: no longer whole-parcel not scorable; dimensional withheld only (material area conflict), use and environment still scored.
- Centre 10S5 remains the refusal hero: critical (vacant vs active condemned case) + material (1,672 vs 4,305 sf straddles 2,400).

## Score contract (from build_contract.md)
Use entitlement 0-2 (P=2, A/S=1, prohibited=0); dimensional fit 0-2 (2 = conforms in all sources and interior envelope width >= 20 ft; 1 = conforms but width 10-20 ft, or corner unverified and corner case < 20 ft; 0 = < 10 ft or below minimum in all sources; withheld on material conflict or unencoded rules); checked environmental layers 0-2 (2 no overlap in landslide-prone, slope25, undermined, FEMA SFHA; 1 one overlap; 0 two+). Numeric total with components always shown; ranges when a component is a range; "Partial: x of 4 known" when withheld; band (5-6 Apparently lower-discretion, 3-4 Conditional, 0-2 Difficult) only when all known. Evidence coverage x of 5 groups.

## Demo path (v5)
Reconciliation 96/77/19 → triage (63 structures routed, 14 vacant) → Benezet packet (4 tiles, 5 to 6 of 6) → Centre refusal → compare Benezet vs Michigan 15S66 → memo + claim checker blocks a conflict-resolving sentence + injection no effect → Dearborn with Rockland card (context) → real vs approximate vs mocked.

## Questions
1. Is Benezet a strong enough positive hero given its very low land value ($1,600) and edge-of-city location, or will judges read it as "the tool only likes worthless lots"? If weak, which parcel or framing is better?
2. Is the 30 ft named-street heuristic for "possible corner" acceptable as a flag, and is treating any "Way" (alley) as non-frontage correct in Pittsburgh zoning terms (e.g., does an alley create an exterior side yard)?
3. Is counting slope25 and undermined overlaps as environmental flags defensible, given these are City screening layers? Should slope25 instead live under zoning (steep-slope standards) to avoid double counting with landslide-prone?
4. Any contradiction between `build_contract.md`, the PDF, the README and the CSVs?
5. Anything in the acceptance test or adversarial cases that is untestable or ambiguous?
6. Final top-3 probability and the single biggest execution risk for a solo builder.

## What we want back (concise)
1. Confirm / reject each of the four v4 must-fixes as resolved.
2. Remaining issues, ranked and labeled.
3. CSV and cross-document consistency check results.
4. Answers to the six questions.
5. Final top-3 probability.
6. Anything to change in the 4-minute storyboard.
