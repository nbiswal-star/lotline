# LotLine

### Know which tax-sale lots are worth your title money, and which ones the records can't agree on.

**LotLine is an AI-assisted, multimodal feasibility navigator.** It reads messy property histories, checks them against real parcel imagery, and shows housing analysts what must be resolved before paid diligence begins.

AI Horizons 2026 AI for Housing Hackathon · Challenge 1: Development Feasibility & Pro Forma Navigator · Startup track · Team: Nibedita Biswal & Premics

![LotLine's sale pipeline, from 96 open-data records to 14 advertised vacant lots](docs/fallback/01-pipeline.png)

> **Decision support only.** LotLine is a screening aid for staff review. It is not legal, financial, title, survey or zoning advice. Every packet ends in named human checks.

---

## Try it in 5 minutes (for judges)

You need [uv](https://docs.astral.sh/uv/). It installs Python 3.12 and the locked dependencies for you. Run everything from the repository root.

```bash
git clone https://github.com/nbiswal-star/lotline.git
cd lotline
uv sync                                   # one-time install
uv run streamlit run app.py --server.port 8501
```

Open **http://localhost:8501** and follow this path:

1. **Sale pipeline** (the default view) shows the funnel **96 → 77 → 63 + 14**. Scroll down to the triage board: **7 advance · 3 defer (site) · 3 defer (records) · 1 not for housing**.
2. Click **Parcel packet**, then click **Centre Ave (10-S-5)**. You'll see:
   - two conflict banners, with the score withheld (**Not scorable**);
   - the **Multimodal cross-check**: a real aerial image with the County parcel outlined in yellow;
   - the **AI record reader**, which quotes the 2025 PLI note "Property is demolished" beside a condemned-list record that still says *Active*.

   LotLine shows both records and refuses to pick one.
3. Click **Benezet St (131-N-31)** and scroll to **Ask LotLine**. Try *"Could I build a two-family house here?"*, then *"Is this a good investment?"*. The second is declined. Ask LotLine needs an API key; see below.
4. Click **Integrity** for the evidence: problem scale, the measured AI delta, and the full 96-parcel multimodal audit.

Press **Ctrl-C** in the terminal to stop the app.

### With or without an Anthropic API key

To enable live AI, create a file named `.env` in the repository root containing `ANTHROPIC_API_KEY=sk-ant-…` (it is git-ignored), then restart the app. To prove the offline path, run `LOTLINE_OFFLINE=1 uv run streamlit run app.py`.

| | Without a key | With a key |
|---|---|---|
| Pipeline, triage, packets, scores, conflicts, next checks, cited memos, downloads, Compare, Integrity | ✅ Fully works | ✅ |
| AI record reader | ✅ Verified cached reads for 9 demo and conflict parcels, labeled **cached · re-verified** | ✅ Live re-reads, labeled **live · verified** |
| Parcel-image observer | ✅ Cached, hash-checked reads for **all 96** parcels | ✅ Live re-runs |
| Semantic labels on record quotes | ⚠️ Withheld ("judge unavailable") | ✅ Checked by a second model pass |
| Ask LotLine | ❌ Unavailable | ✅ Live, verified answers |
| Tests and scientific evaluation | ✅ `uv run pytest -q` and `uv run python -m evaluation.run` run fully offline | ✅ |

Whether or not a key is present, the deterministic engine makes every decision. AI output never changes an outcome or a score.

---

## The problem

Housing acquisition teams don't get one clean parcel record. They get dated, sometimes contradictory assessment fields, parcel geometry, zoning rules, sale notices, condemnation cases, permits and aerial imagery. In the **October 2, 2026 Pittsburgh Treasurer Sale** snapshot:

- **96** parcels are in the open-data feed, but the City advertises **77**. Of those, **63** are structures and **14** are vacant lots.
- The engine advances **7** vacant lots to staff review, defers **3** for site evidence and **3** for record conflicts, and marks **1** as not advancing for housing.
- One "vacant" lot measures **1,672 sq ft** in one official record and **4,305 sq ft** in another, on opposite sides of its 2,400 sq ft zoning minimum. LotLine shows both and withholds the score.
- Citywide, **536** parcels are in both the vacant-assessment set (22,354) and the active-condemned set (2,895). That's a reconciliation workload, not proof of present site condition.

## How it works: AI reads, rules decide, code verifies

```text
records + cited rules ──> deterministic engine ──> outcome, score, barriers, next checks
          │
          ├──> Claude text reader ──> source-verified evidence candidates ──┐
          └──> parcel image + outline ──> bounded visual observations ─────┤
                                                                          └──> human review, never an engine override
```

Claude does four bounded jobs. It never makes the parcel decision.

| AI role | What Claude does | What code guarantees |
|---|---|---|
| **Enforcement-record reader** | Finds event-bearing passages in years of orders, inspections, court notes and permits | Every record ID, date, field and quote is rechecked verbatim. Unsupported labels are withheld |
| **Parcel-image observer** | Looks at a real aerial image with the County parcel outlined | Only enum categories come back. The schema is validated, and image and prompt are hashed. The observer has no access to engine decisions |
| **Ask LotLine** | Interprets a plain-language question | Answers are built only from engine-authored claims and verbatim code excerpts. Out-of-scope questions are declined |
| **Memo selector** | Chooses and orders engine-approved claims | Anything malformed falls back to the deterministic cited memo |

## Multimodal parcel audit

Every one of the **96** sale-feed parcels gets a real Esri World Imagery view with its Allegheny County parcel polygon overlaid. Each image is content-hashed to its cached Claude read. That read is a schema-constrained observation, which code compares with the verified records and the assessment class. The result is visual support, a review-worthy tension, or an abstention.

![Full-cohort multimodal audit: outlined parcel imagery, bounded observations, repeatability and limitations](docs/fallback/11-multimodal.png)

| Result | Value |
|---|---:|
| Valid bounded visual reads | **96/96** |
| Footprint categories | **3 clearly visible · 48 not visible · 45 unclear** |
| Records-versus-image review flags | **36/96** (**29** of them on structure-routed records) |
| Same footprint category across two runs | **93/96** |
| Flags / abstentions across runs | **35–36** / **44–45** |

The value is the discrepancy queue. Without the visual model, the system does **no pixel analysis**, so a person has to open every image. With it, all 96 get the same coarse screen, and the discordant cases become named review items. Centre Avenue stays unresolved even after image review. The imagery does **not** establish vacancy, demolition, structural condition or boundaries on the ground. Its acquisition date is unavailable, and the yellow line is County geometry, not a survey. Full details are in [section 11 of the scientific evaluation](docs/validation/results.md).

## The measured AI delta, honestly

On a balanced **150-parcel** development sample, a frozen Claude reader made **0/75** demolition assertions that conflicted with the active-condemned proxy. The best pre-call rule (B4) made **15/75**. But B4 found more true demolitions (46/75 vs 30/75) and scored a higher **F1: .676 vs .571**. Claude traded recall and F1 for proxy precision.

This supports a conservative precision advantage, **not** LLM necessity or superiority, predictive accuracy, or proof of present site condition. The image study has no site-truth labels, and alternatives like building-footprint overlays remain unevaluated.

![Centre Avenue: both records shown, score withheld](docs/fallback/03-centre.png)

## Reproduce the science

```bash
uv run pytest -q                   # 1904 passed, 1 xfailed
uv run python -m evaluation.run    # 11 sections; writes docs/validation/results.md
```

Everything runs offline from committed snapshots and verified caches. Results are in [`docs/validation/results.md`](docs/validation/results.md). The write-up is in [`docs/scientific_validation.md`](docs/scientific_validation.md).

## Who it's for, and the pilot

It's for acquisition analysts at a Land Bank, redevelopment authority, CDC or public agency who screen a sale list before committing title, survey and specialist-review money. LotLine triages; staff decide.

**Proposed pilot (hypothesis, not a result):**
- **Price:** a one-sale-cycle agency license at **$2,500**, with CDC access at **$500**.
- **Metrics:** analyst hours to a review-ready shortlist, and title or survey spending avoided on unresolved lots.
- LotLine has **no affiliation** with the City, URA, Pittsburgh Land Bank or any agency.

## Limitations

- **Decision support only.** "Advance to staff review" means an apparent lower-discretion zoning path worth staff time. It is not approval and not an acquisition recommendation.
- **Scope:** one Treasurer Sale. 14 vacant lots are screened for development; all 96 records get the non-decisional visual audit.
- **Not evaluated:** contextual setbacks (Ch. 925), utilities, legal access, title, appraisal and market demand. Each becomes a named next check.
- **Screening layers are not determinations.** The RIV-RM riparian buffer uses County shoreline geometry with an uncertainty band, not a survey.
- **Imagery:** acquisition date unknown. It can't show foundations, fill or legal boundaries.
- **Records can disagree:** LotLine never picks a winner. It withholds the score and names who resolves the conflict.
- **Small labeled sets:** the 15 hand-labeled parcels measure conformance to our own spec, not ground truth.
- **Snapshots go stale:** sale status can change by payment or court order.

## Data sources

All public, with snapshot dates shown in the app and in `data/source_manifest.csv`:

- WPRDC Treasury Sales (2026-09-24)
- City advertisement "Available for Auction as of 9/16/2026"
- Treasurer Sale regulations and Act 171 of 1984
- Allegheny County assessments (2026-09-01) and parcels (PASDA, 2026-09-21)
- County parcel geometry plus Esri World Imagery (retrieved 2026-09-27; acquisition date unavailable)
- PLI violations, permits and condemned properties
- City GIS zoning and hazard layers
- FEMA NFHL
- Pittsburgh Zoning Code (current through 2026-09-16), with Ord. 10-2025
- ZBA decisions (Kendall St, Rockland Ave)
- Pittsburgh Land Bank Task Force report

Rule values and label changes are cited in `docs/label_changes.md`.

## Built during the hackathon: disclosures

- **Timeline:** the build ran Sat Sep 26, 09:00 ET to Sun Sep 27, 2026.
- **Pre-event preparation was data only, not code.** Committed in the first commit, as allowed by the rules:
  - the prepared CSVs in `data/` and `tests/fixtures/expected_labels.csv`;
  - the planning documents in that first commit (`docs/prep/` is historical and never loaded by the app).

  The pre-event exploration queries were ad hoc and not kept. All loaders, engine logic, AI readers and tests were written in the build window. `scripts/split_answer_keys.py` (written in-window) moved answer-key columns into test fixtures and dropped household-identifying fields; no owner names are stored.
- **AI tools used:**
  - **Claude Code** (coding assistant during the build);
  - **OpenAI Codex** (plan review and CSV restructuring before the build; review, testing and implementation during it);
  - **Claude API** at runtime (optional), for the four bounded roles above.

  Model output never changes routing, outcomes or scores.
- **Stack:** Python 3.12, Streamlit, pandas, anthropic, pytest (locked in `uv.lock`).

## Repository map

| Path | What's there |
|---|---|
| `app.py`, `lotline/ui/` | Streamlit app (renders engine output only) |
| `lotline/engine/` | Deterministic engine; all thresholds are in `policy.py` |
| `lotline/ai/`, `lotline/memo/` | Bounded AI readers, claim checker, deterministic memo |
| `data/` | Cited public-record snapshots, imagery and verified AI caches |
| `evaluation/`, `docs/validation/` | Scientific evaluation and results |
| `docs/` | Build contract, demo script and runbook, fallback screenshots |
| `tests/` | Test suite (test-only labels never reach the app) |
