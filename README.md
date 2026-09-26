# LotLine

**A development feasibility navigator that catches conflicting public records before anyone acts on a tax-sale lot.**

AI Horizons 2026 AI for Housing Hackathon · Challenge 1: Development Feasibility & Pro Forma Navigator · Startup track

> **Decision support only.** LotLine is a screening aid for staff review. It is not legal, financial, title, survey or zoning advice, and it never states that a parcel is buildable. Every packet ends in named human checks.

**The problem, in one real sale.** For the City Treasurer Sale on October 2, 2026, the open-data feed lists **96** parcels but the City advertises **77**. Of those, 63 are structures and **14** are vacant lots. One "vacant" lot measures 1,672 sq ft in the assessment record and 4,305 sq ft in County GIS, on opposite sides of its 2,400 sq ft zoning minimum. Three "vacant" lots still have active condemned/dead-end cases attached. A tool that scores whichever field it loads first gets these wrong; LotLine detects the conflict and refuses to score through it.

**What it does.** Enter a parcel ID (PIN) and get a cited screening packet: a transparent Development Ease score (0 to 6, always with its components), separate evidence coverage, zoning / environmental / infrastructure / policy flags, the principal barrier, and an exact list of next checks, each assigned to the human who resolves it (surveyor, title examiner, Zoning Administrator, PLI, geotechnical engineer). It triages; staff prioritize.

**Who it is for.** A public-interest acquisition analyst (Land Bank, URA, a CDC, or a City agency) screening a tax-sale list before committing title and survey work. The pilot path we propose: a Pittsburgh Land Bank or CDC acquisitions team, with the snapshot refreshed before each Treasurer Sale advertisement. This is a proposal; LotLine has no affiliation with the City, URA, PLB or any agency.

## Status

Work in progress (build started Sat Sep 26, 2026, 09:00 ET).

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

## Sources, limitations, how to run

To be completed during the build.
