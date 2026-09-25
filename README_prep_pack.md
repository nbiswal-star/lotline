# LotLine prep pack (v6, updated Sept 24, 2026 after Codex round 3; data exploration only, no project code)

All from public sources online. No outreach needed.

## Files
| File | What it is |
|---|---|
| `LotLine_Hackathon_Plan_v6.pdf` | Final build plan |
| `build_contract.md` | Frozen spec: outcomes, conflict policy, score contract, flag tiles, comparison, adversarial cases, acceptance test, source manifest, storyboard |
| `advert_2026-09-16_reconciliation.csv` | The 77 advertised accounts normalized to PIN; 77/77 PIN matches, 77/77 upset price checks |
| `treasury_sale_2026-10-02_enriched.csv` | 96 WPRDC Treasury Sales records for the Oct 2, 2026 sale, joined to assessments (as of 2026-09-01), point-based zoning and landslide flags, and delinquency. New column `in_city_advert_2026_09_16` (77 Y, 19 N) reconciles against the City's official advertisement by normalized PIN, with upset price as a cross-check (`advert_sale_no`, `advert_match_method`). `pli_event_rows` is raw event rows. Use the golden set for unique casefile counts. |
| `golden_set_prescreen.csv` | Legacy audit/preparation artifact containing both facts and hand labels. It must never be loaded by application code. |
| `parcel_facts.csv` | Application-input facts for the 15 prepared parcels. It excludes advertisement-match results, interpreted zoning paths, scores, outcomes and expected checks. |
| `expected_labels.csv` | Hand-authored expected derivations, routing, scores, barriers and next checks for tests only. Application code must never load it. |
| `district_rules.csv` | Hand-authored, cited zoning-rule inputs keyed by district; loaded as district-level `RULE:` facts during the build. |
| `source_manifest.csv` | Frozen snapshot/query metadata used to derive evidence-coverage groups rather than hardcoding them. |
| `codex_review_prompt*.md` | Review prompts used |

## Headline findings (verified)
1. **Sale universe conflict:** WPRDC lists 96 records dated Oct 2, 2026; the City's "Available for Auction as of 9/16/2026" notice lists **77**. All 77 match WPRDC records by normalized PIN (account number minus the ward prefix), and all 77 upset prices agree; 19 WPRDC records are not advertised (18 structures plus Garfield Ave vacant lot). Advertised: 63 structure-classified, **14 vacant**. The undocumented `treasury_sale_flag` is not advertisement status (8 advertised parcels have N): do not use it.
2. **Parcel area conflicts:** County GIS vs assessment `LOTAREA`: Centre Ave 10-S-5 **4,305 vs 1,672 sf** (straddles RM-M 2,400 minimum); Kemper St 4,606 vs 10,276 (-55%); Mossfield 5,203 vs 7,636 (-32%, both above H 3,200 minimum); Centre Ave 10-R-108 2,129 vs 2,675 (-20%); Wylie 3,590 vs 3,115 (+15%).
3. **Current-condition conflicts:** three assessment "VACANT" parcels still have an **active condemned/dead-end case** associated with the parcel in PLI data (current site condition unverified; a case can outlive a demolition): Centre Ave 10-S-5 (listed as 2514 Centre Ave, created 2020-08-24, last inspection Fail), Centre Ave 10-R-108 (2021), Walcott St (2022).
4. **Treasurer Sale mechanics** (Oct 2, 2026 regulations): conveys only the taxing bodies' interest; does NOT divest mortgages, judgments, federal/state liens, water claims, assigned tax liens or other secured claims; 90-day redemption; "NO ONE SHOULD BID ... WHO HAS NOT HAD THE TITLE EXAMINED." Competitive; no Land Bank priority found (priority bidding is at Sheriff's Sale). The City's Side Yard Sale program is suspended since Oct 31, 2024.
5. Upset price vs assessed land value (median about 2.6x; Centre Ave 150x) is an **acquisition-burden indicator only**, not market value or feasibility.
6. 5 of 15 vacant records are landslide-prone (screening layer; not a slope determination).

## Rule matrix (per Codex check of current §911.02 and §903/905; hand-verify Friday)
| District | Single-unit detached | Two-unit | Dimensions |
|---|---|---|---|
| R1D, R1A | P | Prohibited (use variance) | 903.03: L 3,000 sf, 30/30/30/5; H 1,200, 15/15/15/5; VH 0, 5/15/5/5; 40 ft/3 st |
| R2 | P | P | same as above |
| RM-M | P | P | 2,400 sf; 25/25/25/10; 55 ft/4 st |
| H | A (Administrator Exception) + 911.04.A.69 (structure on contiguous area under 30% slope, soil/access/utility conditions) | Prohibited | 905.02: 3,200 sf min, no ordinary setbacks, 40 ft/3 st, 50% max disturbance, site plan review |
| P | P (905.01 site plan review) | Prohibited | 905.01 |
| LNC | P | P | Ch. 904 (not encoded) |
| UI | Prohibited | Prohibited | n/a |
| RIV-RM | Prohibited | P | Ch. 908 (not encoded) |

§921.04.A: vacant lot in separate ownership from abutting lots on the applicable date: Administrator Exception for single-unit, or ZBA special exception for another conforming use; dimensions "to the extent practicable"; only intensities meeting setbacks allowed. Contextual front setbacks (Ch. 925) and attached/party-wall exceptions are flagged, not computed.

## ZBA precedent cards (freeze these two)
- **Kendall St, Zone 58 of 2026** (application BDA-2025-09345), Upper Lawrenceville, H, 20x100 vacant: use variance for two-unit **denied** 2026-06-18. Board: "less financially rewarding" is not hardship; neighbors single-family. PDF: `.../zoning-board-of-adjustment/kendall-street-58-of-2026.pdf`
- **Rockland Ave, Zone 96 of 2026** (BDA-2026-02055), Beechview, R1D-H, 30x100: two-unit use variance **denied**; 5 ft exterior side setback variance **approved**, 2026-08-18. PDF: `.../zoning-board-of-adjustment/rockland-avenue-96-of-2026.pdf`

## Practitioner voice (public sources; phrase carefully)
- PLB Task Force report (Jan 2026, figures preliminary): 13,770 parcels need intervention; a **modeled** eradication scenario processes about 2,790 a year at $32 to 35M a year (not an adopted or funded plan); Sheriff acquisition about $7,300 average; quiet title about $2,000; data quality "continue[s] to limit strategic planning."
- PLB non-competitive disposition policy: side yards only to adjacent owner-occupants, max two, lots ineligible for independent development.
- Hill District Vacant Property Strategy (**2013** report): 2,308 vacant lots (45.4%); 52% of vacant land recommended for green uses; Centre business district is a development focus area; Centre between Kirkpatrick and Junilla flagged for additional planning. Do not generalize to every Centre Ave parcel.
- Bill 2025-1545 (ADUs, parking, IZ bonus): Held in Council as of Sept 24, 2026.

## Source register (snapshot Sept 24, 2026)
| Source | ID / URL |
|---|---|
| City Treasury Sales (WPRDC) | resource `6b2aa631-26e0-4d02-abe0-7fb87707210c` |
| City advertisement 9/16/2026 | pittsburghpa.gov/files/assets/city/v/2/finance/documents/real-estate-forms/available-for-auction-9-16-2026.pdf |
| Treasurer Sale regulations 10/2/2026 | pittsburghpa.gov/files/assets/city/v/3/finance/documents/real-estate-forms/regulations-10-2-26-pdf.pdf |
| Assessments API | `65855e14-549e-4992-b5be-d629afc676fa` |
| County parcels (GIS area, geometry) | maps.pasda.psu.edu/arcgis/rest/services/pasda/AlleghenyCounty/MapServer/25 ("Parcels 20260921"; query with `outSR=2272` for feet) |
| City delinquency | `ed0d1550-c300-4114-865c-82dc7c23235b` |
| PLI violations | `70c06278-92c5-4040-ab28-17671866f81c` (aggregate by `casefile_number`) |
| Condemned properties | `0a963f26-eb4b-4325-bbbc-3ddf6a871410` |
| City-owned properties | `e1dcee82-9179-4306-8167-5891915b62a7` |
| Zoning GeoJSON | `6127f35e-f36b-4a53-80b3-f4409609e9df` (field `zon_new`) |
| Landslide-prone GeoJSON | `b5b45ac6-f8ef-4805-b4e4-fc7c63fb4075` |
| FEMA NFHL | hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer |
| Code | ecode360 903 `45474194`, 905 `45474542`, 911 `45476784`, 921 `45479031`, 925 `45479734` |
| PLB Task Force | pghlandbank.org/wp-content/uploads/2026/01/2025-2698-PLB-Task-Force-Report-Recommendations-1.pdf |
| PLB non-competitive policy | pghlandbank.org/wp-content/uploads/2023/03/PLB-Non-competitive-004-2.pdf |
| Hill District strategy (2013) | hilldistrict.org/wp-content/uploads/2024/03/hill-district-vacant-property-study-final-report-for-consensus-group.pdf |
| Bill 2025-1545 | pittsburgh.legistar.com (GUID C15553FF-85B6-480E-ACFF-53F40EF99EA9) |

## Build-day data notes
- CKAN `datastore_search` works via POST with JSON filters; GET with long filters returns 403; `datastore_search_sql` disabled. Snapshot to Parquet; no live calls in the demo.
- PASDA parcel service is in NAD83 degrees by default; request `outSR=2272` (PA South, US feet) for areas and widths.
- The enriched 96-row CSV keeps point-derived zoning and landslide fields; the 15 golden-set parcels are already polygon-checked (zoning, slope25, undermined, FEMA, historic, RCO). No recomputation needed for the demo.
- Drop `CHANGENOTICEADDRESS*` and owner fields; `OWNERDESC` is a category only.

## v5 additions (Codex round 3 fixes, verified live Sept 24)
- Polygon intersections (County parcel polygons vs City GIS): zoning polygon matches the point result for all 15; no split zones found.
- New flags: **slope25** overlaps Michigan 15S66, Centre 10S5, Mossfield, Platt, Banksville, Saline, Kemper; **undermined** overlaps Michigan 15S66, Michigan 14N100, Wylie, Platt; **FEMA zone A** partially on Banksville and McClure; Garfield Ave is in the **Mexican War Streets Expansion** historic district. Registered Community Organizations (RCO) found for most lots (use as the community-review contact, not as endorsement).
- **Possible corner lots** (two named streets within 30 ft): Michigan 15S66, Benezet, Dearborn. Envelopes are now an "illustrative base-setback screen" with interior and corner cases.
- **Hero change:** Benezet St (R1D-L, no overlaps in checked layers, areas agree) is the positive hero at "5 to 6 of 6, pending corner check". Michigan 15S66 drops to "3 to 4 of 6: Conditional" (slope25 + undermined + possible corner).
- Use-path citations now point to 911.02; 903 is cited for dimensions only. Dearborn "relief likely" removed.

## v6 additions (Codex round 4)
- Environmental score now counts three hazard families: terrain (landslide-prone OR slope25), undermining, FEMA SFHA. Slope25 is cross-listed in zoning/site review but counted once.
- Dimensional bands: 2 if width >= 20 ft; 1 if >= 10 and < 20; 0 if < 10; unresolved corner shows a range.
- Evidence coverage is a Boolean test over five groups (see `evidence_coverage_definition` in the golden set). Conflicts lower confidence; they are not counted as missing evidence.
- Wylie, Kemper and Saline move to "Defer: missing or conflicting records (rules not encoded)". Kemper's 55% area gap is Disclose-level.
- Legacy `env_flags_checked_layers` renamed `landslide_prone_layer`; `advert_sale_no` cast to integer.
- Video drops the Dearborn/Rockland segment; the card stays in the app and README.

## v7 (final, Codex round 5 GO)
- Outcome taxonomy: seven output values (five screening states, two routing states).
- Evidence G2 counts UI as covered because dimensions are not applicable.
- Partial scores use "Partial: x of 4 known"; Dearborn shows a band that spans two categories.
- Benezet acceptance lists the exact unresolved checks.
- **Stop revising. Build.**

## Implementation authority

`implementation_plan_v5.md` supersedes the earlier storyboards and implementation sequencing in the plan PDF and `build_contract.md`. The frozen product facts and scoring contract remain controlling; v5 controls build order, runtime reconciliation, test-data separation, safety fixtures and demo timing.

The four prepared CSVs above were restructured with Codex assistance from the verified golden set, source register and hand-reviewed rule matrix before the build window. They are data preparation and expected test data, not application code. No reusable transformation script was created. Runtime application logic, tests and loaders must be written after Saturday 09:00.
