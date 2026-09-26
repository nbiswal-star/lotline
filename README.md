# LotLine

**A development feasibility navigator that catches conflicting public records before anyone acts on a tax-sale lot.**

AI Horizons 2026 AI for Housing Hackathon · Challenge 1: Development Feasibility & Pro Forma Navigator · Startup track

> **Decision support only.** LotLine is a screening aid for staff review. It is not legal, financial, title, survey or zoning advice, and it never states that a parcel is buildable. Every packet ends in named human checks.

**The problem, in one real sale.** For the City Treasurer Sale on October 2, 2026, the open-data feed lists **96** parcels but the City advertises **77**. Of those, 63 are structures and **14** are vacant lots. One "vacant" lot measures 1,672 sq ft in the assessment record and 4,305 sq ft in County GIS, on opposite sides of its 2,400 sq ft zoning minimum. Three "vacant" lots still have active condemned/dead-end cases attached. A tool that scores whichever field it loads first gets these wrong; LotLine detects the conflict and refuses to score through it.

**What it does.** Enter a parcel ID (PIN) and get a cited screening packet: a transparent Development Ease score (0 to 6, always with its components), separate evidence coverage, zoning / environmental / infrastructure / policy flags, the principal barrier, and an exact list of next checks, each assigned to the human who resolves it (surveyor, title examiner, Zoning Administrator, PLI, geotechnical engineer). It triages; staff prioritize.

**Who it is for.** A public-interest acquisition analyst (Land Bank, URA, a CDC, or a City agency) screening a tax-sale list before committing title and survey work. The pilot path we propose: a Pittsburgh Land Bank or CDC acquisitions team, with the snapshot refreshed before each Treasurer Sale advertisement. This is a proposal; LotLine has no affiliation with the City, URA, PLB or any agency.

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
- **OpenAI Codex**: used before the build to review the plan and to help restructure the prepared CSVs (data preparation only).
- **Claude (Anthropic API)**: runtime memo narration behind a deterministic claim checker (added during the build).

## Libraries

Python 3.12, Streamlit, pandas, anthropic, pytest (dependencies are locked in `uv.lock`).

## How to run

Requires [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 and the locked dependencies).

```bash
uv run streamlit run app.py      # opens http://localhost:8501; works fully offline
uv run pytest -q                 # full test suite
```

Optional: set `ANTHROPIC_API_KEY` to let the memo panel draft a narrative with Claude. The draft is shown only if the deterministic claim checker accepts it; otherwise, and whenever the key, network or model is unavailable, the deterministic cited memo is shown. Nothing else uses the network.

## How it works

**The LLM writes; the engine decides; the checker enforces.**

1. **Immutable snapshots** (`lotline/loaders.py`). Cached CSVs are loaded with explicit column allowlists and validated at startup (schemas, unique PINs, dates, and the universe counts 96 / 77 / 19 / 63 / 14). Answer-key columns cannot be selected, and test labels are never read by the app.
2. **Runtime reconciliation** (`lotline/reconcile.py`). The City advertisement is matched to the WPRDC list by normalized PIN, with the upset price as a cross-check.
3. **Flat, cited facts** (`lotline/facts.py`). Every value becomes a fact `PIN:field:source` with its source and as-of date. District rules become `RULE:district:field` facts.
4. **Deterministic engine** (`lotline/engine/`). Pure functions own routing, conflict detection (critical / material / disclose), use entitlement, the illustrative setback screen, hazard families, evidence coverage, the Development Ease result, barriers and next checks. All thresholds live in `lotline/engine/policy.py`. Unknown inputs are withheld, never scored as zero.
5. **Memo and claim checker** (`lotline/memo/`). A deterministic cited memo is always available. An optional Claude draft must pass every checker rule: each claim cites facts of the active parcel, numbers match those facts, code sections are on a versioned allowlist, status agrees with the engine, and forbidden words are rejected. The draft also may not pick a side in a records conflict, may not author conflict summaries, must qualify approximate facts, and may not echo instructions found in source text. One violation rejects the whole draft.
6. **Streamlit UI** (`app.py`, `lotline/ui/`) renders engine output only. It has four views: sale pipeline and triage, parcel packet, compare, and integrity.

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
- **Approximate:** envelope widths and depths use each parcel's minimum bounding rectangle and base setbacks. Corner status and nearby streets come from a 30 ft proximity heuristic. These are shown as an "illustrative base-setback screen", never as a buildable envelope.
- **Synthetic (labeled in the app):** the three integrity fixtures. These are a memo draft that picks a side in a conflict, an injected instruction in violation text, and a stale-source snapshot. They exist only to show that the checker and engine fail safely.

## Limitations

- **Decision support only.** LotLine is not legal, title, survey, financial, appraisal or zoning advice. "Advance to staff review" means an apparent lower-discretion zoning path worth staff time. It does not mean the lot is buildable or a good acquisition.
- **Scope of v1.** It covers the vacant lots in one Treasurer Sale (14 advertised vacant parcels from a 96-record list). The 63 advertised structures are routed out, and a model for them is future work. Sheriff's Sale and Land Bank inventories are not loaded.
- **Not evaluated:** contextual front setbacks (Ch. 925), attached and party-wall options, utility capacity and laterals, legal access, title, market demand and appraisal, and community-plan alignment. Each appears as a named next check, not a score.
- **Screening layers are not determinations.** Slope, landslide, undermining and flood overlaps come from public GIS layers. We could not verify whether the slope layer matches the Steep Slope Overlay (§906.08) map, so the tool says "possible review".
- **RIV-RM dimensions are not modeled.** This is a gap in the tool, and it says so.
- **Records can disagree, and LotLine does not resolve that.** When assessment and County GIS areas, or assessment use and condemned-case records, disagree in a way that matters, the parcel is not scored through the conflict. The sources are shown side by side, and the conflict routes to a human check.
- **Small, hand-labeled test set.** The expected labels (15 parcels) were written by the same team that wrote the specification. They prove conformance to the spec, not legal ground truth.
- **Snapshots go stale.** Sale status can change by payment or court order. The snapshot must be refreshed before each advertisement, and startup checks fail loudly if the universe counts change.
