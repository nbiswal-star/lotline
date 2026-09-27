# LotLine live status (read this first if you are picking up the work)

**Last updated:** Sun Sep 27, ~01:45 ET. **Code freeze:** Sun 15:00 ET. **Submission deadline:** Sun 23:59 ET.
The finish line is a demo that runs completely error-free, plus detailed context for recording the video.

## Done and pushed (`main`)

- Deterministic engine, reconciliation (96 → 77 → 63 + 14), four-view Streamlit app, cited memo, 12-rule checker, and offline fallback.
- Retrospective validation suite: `uv run python -m evaluation.run` writes `docs/validation/results.md` (all sections pass). Threat analysis is in `docs/validation/threat_analysis.md`.
- Recording runbook (`docs/RECORDING_RUNBOOK.md`), submission payload draft (`docs/SUBMISSION_PAYLOAD.md`), and the vetted AI plan (`docs/AI_PLAN.md`).
- Git history carries no AI co-author trailers (user instruction; see `AGENTS.md`).

## In progress (parallel builders, per `docs/AI_PLAN.md`)

| Workstream | Files | State |
|---|---|---|
| A1 Enforcement-record reader: PLI violations, condemned properties and permits text; quote-verified evidence; permit cross-check; AI-vs-keyword evaluation | `scripts/fetch_record_text.py`, `data/record_text.csv`, `lotline/ai/evidence.py`, `lotline/loaders.py`, `lotline/models.py`, `evaluation/ai_reader.py`, `tests/test_ai_evidence.py`, `tests/fixtures/record_relevance.csv` | building |
| A2 Ask LotLine: Claude selects verified atoms into fixed answer frames; no model prose | `data/code_excerpts.json`, `lotline/ai/ask.py`, `lotline/ai/verify.py`, `tests/test_ai_ask.py` | building |
| A3 ZBA precedents and required-relief paths | `scripts/fetch_zba.py`, `data/zba/`, `lotline/ai/precedents.py`, `tests/test_ai_precedents.py` | building |
| UI: AI panels, task tickets, sale-specific cost worksheet, live drift check, outcome map | `app.py`, `lotline/ui/*`, `lotline/costs.py`, `lotline/refresh.py`, `data/cost_assumptions.csv`, `tests/test_ui_*` | building |

## Blocker (owner: the user)

**Anthropic API key.** Every AI reader needs it for real outputs, cached demo results and the video. Put it in the git-ignored `.env` at the repo root:
```
ANTHROPIC_API_KEY=sk-ant-...
```
`lotline/ai/client.py` loads it automatically. Without it the AI panels show "unavailable" and everything else works.

## After the builders land (in order)

1. Integrate: run the full suite (exit 0), `evaluation.run` (exit 0) and the 96-record memo sweep (0 violations); do the browser pass at 1280×800 in every view.
2. Live AI runs with the key: evidence digests for the 3 conflict lots plus Benezet and Michigan; the 4 scripted Ask questions; ZBA extraction. Save verified caches, then re-verify them offline.
3. Write `docs/scientific_validation.md`, with the H1–H6 verdict table plus AI-reader results (recall vs team labels, AI vs keyword baseline, verification n/N).
4. Run the three-judge review on the integrated build and fix the blockers.
5. Rewrite `docs/demo_script.md` and the runbook around the AI-first beats (from the investor review in `docs/AI_PLAN.md`); update the README (tagline, AI section, pilot and business).
6. Final commit and push; update this file.
