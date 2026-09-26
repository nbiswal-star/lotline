# LotLine

**A development feasibility navigator that catches conflicting public records before anyone acts on a tax-sale lot.**

AI Horizons 2026 AI for Housing Hackathon · Challenge 1: Development Feasibility & Pro Forma Navigator · Startup track

> **Decision support only.** LotLine is a screening aid for staff review. It is not legal, financial, title, survey or zoning advice, and it never states that a parcel is buildable.

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
The manual split, district rules, source manifest, polygon zoning, slope25, undermining, FEMA, historic, RCO, street-proximity and approximate geometry fields came from pre-event exploration of public sources. No reusable transformation script existed before kickoff; all loaders, engine logic and tests are written during the build window.

## AI tool disclosure

- **Claude Code (Claude Opus 5.5)**: coding assistant used during the build.
- **OpenAI Codex**: used before the build to review the plan and to help restructure the prepared CSVs (data preparation only).
- **Claude (Anthropic API)**: runtime memo narration behind a deterministic claim checker (added during the build).

## Libraries

Python 3.12, Streamlit, pandas, anthropic, pytest (dependencies are locked in `uv.lock`).

## Sources, limitations, how to run

To be completed during the build.
