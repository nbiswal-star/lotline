# LotLine

**Claude searches loaded enforcement histories and cross-checks real parcel imagery against dated records before analysts decide whether to begin paid diligence.**

AI Horizons 2026 AI for Housing Hackathon · Challenge 1: Development Feasibility & Pro Forma Navigator · Startup track

![LotLine's offline sale pipeline, from 96 open-data records to 14 advertised vacant lots](docs/fallback/01-pipeline.png)

> **Decision support only.** LotLine is a screening aid for staff review. It is not legal, financial, title, survey or zoning advice, and it never states that a parcel has final development approval. Every packet ends in named human checks.

**Why AI—and what happens without it.** Enforcement histories arrive as heterogeneous free text: orders, inspections, court notes, demolition permits and condemnation status can describe different moments in a property's history. Claude performs semantic retrieval: it proposes event-bearing passages, while code accepts only source-matched IDs, dates, fields and exact quotes and withholds unsupported labels. In a balanced development sample of 150 parcels randomly sampled within two eligible Pittsburgh proxy strata, the frozen `k=1` AI reader made **0/75 demolition assertions discordant with the active-condemned/no-demolition-permit stratum**; the highest-F1 pre-call simple rule (B4) made **15/75**. The AI traded recall for precision: its primary rule found 30/75 permit-reference demolitions, versus 46/75 for B4. A stronger post-hoc contextual deterministic rule (B5) made 2/75 proxy-discordant assertions and found 35/75, with higher F1 than AI (.625 versus .571). The result supports a conservative precision edge, not LLM necessity or overall superiority. This is a development-set estimate of one derived rule—not a benchmark, proof of present site condition, causal time-savings result or citywide predictive claim. The current live reader adds three-run union and a same-model entailment check; that newer configuration has not been evaluated at this scale. The deterministic engine makes the identical parcel decision with or without Claude.

**The problem, at city scale and in one real sale.** An exact parcel-ID join of committed public-source snapshots finds **536 Pittsburgh parcels** in both the County's 22,354-parcel vacant-assessment set and the City's 2,895 unique active-condemned parcel IDs. That is a records-overlap count—not present site condition—but it quantifies the reconciliation workload. For the City Treasurer Sale on October 2, 2026, the open-data feed lists **96** parcels but the City advertises **77**. Of those, 63 are structures and **14** are vacant lots. One "vacant" lot measures 1,672 sq ft in the assessment record and 4,305 sq ft in County GIS, on opposite sides of its 2,400 sq ft zoning minimum. Three "vacant" lots still have active condemned/dead-end cases attached. A tool that scores whichever field it loads first gets these wrong; LotLine detects the conflict and refuses to score through it.

**Multimodal evidence, not decoration.** Every one of the 96 sale-feed parcels has source-cached real aerial context with the target County parcel polygon outlined and a hash-bound Claude read. Claude can return only four coarse visual categories—structure-like footprint, surface cover, street context and image quality—plus a fixed limitation vocabulary. The current run abstained as `unclear` on 45 images and produced 36 human-review flags where the assessment says structure but no clear footprint is visible. Across two consecutive runs, exact footprint categories agreed on 93/96 parcels; total flags varied 35–36 and abstentions 44–45, while the same 29 structure-routed records were flagged. These are record-discordance flags, not image labels or proof of vacancy/demolition. Centre remains unresolved; Benezet and Michigan are visually consistent with vacant-land records. The records-only engine performs no pixel analysis; Claude supplies a working zero-shot proof of concept without task-specific labels. Handcrafted computer vision, open building-footprint overlays and task-specific detectors remain unevaluated alternatives. This study does not establish that learned vision—or an LLM—is necessary or superior. Source attribution and the unavailable acquisition date remain visible, and visual output cannot change routing, an outcome or a score.

![Centre Avenue conflict handling: both records shown, score withheld](docs/fallback/03-centre.png)

**What it found.** Of the 14 advertised vacant lots, LotLine advances **7 to staff review**, each with a named list of checks and who resolves them. It **refuses to score 3** because their public records conflict, sends **3 Hillside lots to survey** before any score, and flags **1** as not zoned for housing. The other 63 advertised parcels are routed out as structures, and the 19 open-data records that are not in the City advertisement are routed out of the sale universe. Nothing is silently dropped.

**What it does.** Enter a parcel ID (PIN) and get a cited screening packet: a transparent Development Ease score (0 to 6, always with its components), separate evidence coverage, zoning / environmental / infrastructure / policy flags, the principal barrier, and an exact list of next checks, each assigned to the human who resolves it (surveyor, title examiner, Zoning Administrator, PLI, geotechnical engineer). It triages; staff prioritize.

**Who it is for.** A public-interest acquisition analyst (Land Bank, URA, a CDC, or a City agency) screening a tax-sale list before committing title and survey work. The pilot path we propose: a Pittsburgh Land Bank or CDC acquisitions team, with the snapshot refreshed before each Treasurer Sale advertisement. This is a proposal; LotLine has no affiliation with the City, URA, PLB or any agency.

**Proposed one-sale-cycle pilot and buyer (hypothetical; no agency participation is implied).** A Land Bank or URA acquisitions team would buy a per-sale-cycle license; CDC access would be subsidized. The initial pricing hypothesis is **$2,500 per sale cycle for an agency team and $500 for a CDC**, tested rather than assumed in discovery. One acquisitions analyst owns the screening queue, while a data steward refreshes the public-source snapshot when the City publishes the advertisement. The pilot measures (1) analyst hours from advertisement to a review-ready shortlist, (2) title and survey dollars not yet committed on lots with unresolved record conflicts, and (3) packets accepted without a missing owner or next check. City Planning/Zoning, PLI, the Treasurer/Real Estate Division, County Real Estate, and licensed specialists remain escalation partners—not LotLine operators. These buyers, prices and savings are proposals to test; LotLine has no agency affiliation and has not measured willingness to pay or cost savings.

## Status

Built during the AI Horizons 2026 AI for Housing Hackathon (Sat Sep 26, 09:00 ET to Sun Sep 27, 2026).

## Repository layout

| Path | Contents |
|---|---|
| `lotline/` | Application code (written during the build window) |
| `data/` | Prepared, cited snapshot inputs loaded by the app |
| `tests/` | Test suite; `tests/fixtures/expected_labels.csv` is test-only and never loaded by the app |
| `docs/` | Frozen spec (`build_contract.md`) and implementation plan |
| `docs/prep/` | Pre-event data-exploration artifacts (plan PDF, prep-pack notes, legacy golden set — never loaded by the app) |

## Pre-event data preparation (disclosure)

Per the hackathon rules, ideas and data exploration may precede kickoff; code may not. The following were prepared **before** the build window as data, not code, and are committed as-is in the first commit:
`data/parcel_facts.csv`, `data/district_rules.csv`, `data/source_manifest.csv`, `data/treasury_sale_2026-10-02_enriched.csv`, `data/advert_2026-09-16_reconciliation.csv`, `tests/fixtures/expected_labels.csv`, and everything in `docs/`.
After kickoff, `scripts/split_answer_keys.py` (written in-window) moved the prepared advertisement-match columns out of the app-loaded CSVs into `tests/fixtures/expected_reconciliation.csv` and dropped household-identifying columns (homestead flag, owner category, deed type/price/date) from the Treasury snapshot. No owner names are stored.
Pre-event exploration queries (CKAN, ArcGIS, PASDA) were run ad hoc and were not kept; no code from them is in this repository. Files in `docs/prep/` are historical and may reference earlier file names (e.g. a v6 plan PDF, review prompts that are not included, and advertisement columns that now live in test fixtures).

The manual split, district rules, source manifest, polygon zoning, slope25, undermining, FEMA, historic, RCO, street-proximity and approximate geometry fields came from pre-event exploration of public sources. No reusable transformation script existed before kickoff; all loaders, engine logic and tests are written during the build window.

## AI tool disclosure

- **Claude Code (Claude Opus 5.5)**: coding assistant used during the build.
- **OpenAI Codex**: used before the build to review the plan and restructure prepared CSVs, and during the build to review, test and implement parts of the application and documentation.
- **Claude (Anthropic API)**: optional runtime reader for unstructured enforcement records, bounded question router over engine-authored claims and cited code excerpts, memo claim selector, and enum-only observer of parcel imagery. Model output never changes routing, an engine outcome or score.

## Libraries

Python 3.12, Streamlit, pandas, anthropic, pytest (dependencies are locked in `uv.lock`).

## How to run

Requires [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 and the locked dependencies).

```bash
uv run streamlit run app.py      # opens http://localhost:8501; works fully offline
uv run pytest -q                 # full test suite
```

Optional: set `ANTHROPIC_API_KEY` to run the record reader, Ask LotLine and cited memo assembly. Verified record-reader caches keep the headline demo available offline. When the key, network or model is unavailable, deterministic screening and memo output remain available.

## How it works

**Claude reads the record. Rules decide. Code verifies source identity, recorded dates and every displayed quote.**

1. **Immutable snapshots** (`lotline/loaders.py`). Cached CSVs are loaded with explicit column allowlists and validated at startup (schemas, unique PINs, dates, and the universe counts 96 / 77 / 19 / 63 / 14). Answer-key columns cannot be selected, and test labels are never read by the app.
2. **Runtime reconciliation** (`lotline/reconcile.py`). The City advertisement is matched to the WPRDC list by normalized PIN, with the upset price as a cross-check.
3. **Flat, cited facts** (`lotline/facts.py`). Every value becomes a fact `PIN:field:source` with its source and as-of date. District rules become `RULE:district:field` facts.
4. **Deterministic engine** (`lotline/engine/`). Pure functions own routing, conflict detection (critical / material / disclose), use entitlement, the illustrative setback screen, hazard families, evidence coverage, the Development Ease result, barriers and next checks. All thresholds live in `lotline/engine/policy.py`. Unknown inputs are withheld, never scored as zero.
5. **Verified AI readers** (`lotline/ai/`). The enforcement reader searches longitudinal record prose for event-bearing quotes; exact IDs, fields, dates and quotes are rechecked, and unsupported semantic labels are withheld. The current live reader unions proposals from three same-model runs, exposes how many runs proposed each quote, and applies a same-model entailment check; recurrence is reported, not required for inclusion. Code may attach an exact structured status field from an AI-surfaced condemned record as deterministic enrichment. Ask LotLine maps natural questions to fixed answer frames, engine claim IDs and verbatim code excerpts; no model-written prose reaches the UI. ZBA extraction is secondary and is not used to predict approval.
6. **Bounded multimodal cross-check** (`lotline/ai/visual.py`). All 96 sale-feed parcels have real imagery paired with a County parcel outline. Claude returns enum-only visual observations; code validates the vocabulary, rechecks cached image hashes, and compares the result with verified record semantics and the assessment class. An image may corroborate, challenge or fail to resolve the records, but never validates or changes the engine decision. The full-cohort audit and records-only counterfactual are reproduced in validation section 11.
7. **Memo and claim checker** (`lotline/memo/`). A deterministic cited memo is always available. Claude may optionally select and order immutable engine-approved claim IDs. Unknown, duplicate, malformed or rejected selections fall back to the deterministic memo.
8. **Streamlit UI** (`app.py`, `lotline/ui/`) renders engine output only. It has four views: sale pipeline and triage, parcel packet, compare, and integrity.

## Data sources

All sources are public. Snapshot dates are shown in the app and recorded in `data/source_manifest.csv`.

| Source | Identifier | As of |
|---|---|---|
| City Treasury Sales (WPRDC) | resource `6b2aa631-26e0-4d02-abe0-7fb87707210c` | pulled 2026-09-24 |
| City advertisement "Available for Auction as of 9/16/2026" | pittsburghpa.gov/files/assets/city/v/2/finance/documents/real-estate-forms/available-for-auction-9-16-2026.pdf | 2026-09-16 |
| Treasurer Sale regulations for the 10/2/2026 sale | pittsburghpa.gov/files/assets/city/v/3/finance/documents/real-estate-forms/regulations-10-2-26-pdf.pdf | 2026-10-02 sale |
| Second Class City Treasurer's Sale and Collection Act | Act of Oct. 11, 1984, P.L. 876, No. 171 | |
| Allegheny County assessments (WPRDC) | `65855e14-549e-4992-b5be-d629afc676fa` | ASOFDATE 2026-09-01 |
| Allegheny County parcels (PASDA) | "Parcels 20260921", EPSG:2272 | 2026-09-21 |
| Allegheny County OPENDATA parcel geometry + Esri World Imagery | County polygon queried 2026-09-27; imagery acquisition date unavailable | retrieved 2026-09-27 |
| City delinquency, PLI violations, condemned properties (WPRDC) | `ed0d1550-…`, `70c06278-…`, `0a963f26-…` | 2026-09-24 |
| City GIS: zoning, slope 25%+, undermined, landslide-prone, historic, RCO | services1.arcgis.com/YZCmUqbcsUpOKfj7; WPRDC `6127f35e-…`, `b5b45ac6-…` | 2026-09-24 |
| FEMA National Flood Hazard Layer | hazards.fema.gov NFHL layer 28 | 2026-09-24 |
| Pittsburgh Zoning Code (ecode360) | Ch. 903, 904, 905, 906, 911, 915, 921, 925 | current through 2026-09-16 |
| Minimum lot size amendment | Ord. No. 10-2025 (Bill 2025-1579), eff. 2025-05-07 | |
| ZBA decisions | Kendall St (Zone 58 of 2026), Rockland Ave (Zone 96 of 2026) | 2026-06-18, 2026-08-18 |
| Pittsburgh Land Bank Task Force report | pghlandbank.org (Jan 2026; figures preliminary) | |

Zoning-rule values and every change to the hand-authored test labels are documented with citations in `docs/label_changes.md`.

## What is real, derived, approximate and synthetic

- **Real:** all parcel, sale, assessment, enforcement and screening-layer values, taken from the public sources above as of the dates shown.
- **Derived:** reconciliation, area gaps, conflict levels, score components, coverage, outcomes, barriers and next checks. The deterministic engine computes these at runtime.
- **Approximate:** envelope widths and depths use each parcel's minimum bounding rectangle and base setbacks. Corner status and nearby streets come from a 30 ft proximity heuristic. These are shown as an "illustrative base-setback screen", never as a final development envelope.
- **Synthetic (labeled in the app):** the three integrity fixtures. These are a memo draft that picks a side in a conflict, an injected instruction in violation text, and a stale-source snapshot. They exist only to show that the checker and engine fail safely.

## Limitations

- **Decision support only.** LotLine is not legal, title, survey, financial, appraisal or zoning advice. "Advance to staff review" means an apparent lower-discretion zoning path worth staff time. It does not mean the lot has development approval or is a good acquisition.
- **Scope of v1.** The development-screening model covers the 14 advertised vacant parcels in one 96-record Treasurer Sale feed. The 63 advertised structures are routed out of that model, but all 96 records receive the separate non-decisional visual–record audit. Sheriff's Sale and Land Bank inventories are not loaded.
- **Not evaluated:** contextual front setbacks (Ch. 925), attached and party-wall options, utility capacity and laterals, legal access, title, market demand and appraisal, and community-plan alignment. Each appears as a named next check, not a score.
- **Screening layers are not determinations.** Slope, landslide, undermining and flood overlaps come from public GIS layers. We could not verify whether the slope layer matches the Steep Slope Overlay (§906.08) map, so the tool says "possible review".
- **RIV-RM is an approximate screen.** §905.04.E dimensional standards are encoded, including the 125 ft riparian buffer. River distance uses a cached County shoreline polygon plus a conservative uncertainty band; it is not the Code's 710 ft contour or a survey, so every RIV-RM packet routes confirmation to the Zoning Administrator and a licensed surveyor.
- **Records can disagree, and LotLine does not resolve that.** When assessment and County GIS areas, or assessment use and condemned-case records, disagree in a way that matters, the parcel is not scored through the conflict. The sources are shown side by side, and the conflict routes to a human check.
- **Small, hand-labeled test set.** The expected labels (15 parcels) were written by the same team that wrote the specification. They prove conformance to the spec, not legal ground truth.
- **Snapshots go stale.** Sale status can change by payment or court order. The snapshot must be refreshed before each advertisement, and startup checks fail loudly if the universe counts change.
