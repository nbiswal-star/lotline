# LotLine live status and Codex handoff (read this first)

**Written:** Sun Sep 27, early morning ET, by Claude, whose session was ending. **Code freeze:** Sun 15:00 ET. **Submission:** Sun 23:59 ET.
**Finish line:** a demo that runs completely error-free, plus detailed context for recording the video.

## Where everything is

| Location | What |
|---|---|
| `main` (GitHub `anitksahu/lotline`) | Last green state: engine, app, memo and checker, validation suite, runbook, submission payload, vetted AI plan and shared Claude client. 1,677 tests passed, exit 0, at `6d8104d` and later |
| Branch `wip/ai-readers` (pushed) | Snapshot of the **in-progress AI build**, taken at handoff. It may be red. All four builders were stopped mid-task by a usage limit and left no status notes, so start by running the tests and reading each module against `docs/AI_PLAN.md`. The same files are uncommitted in the local working tree at `~/Downloads/lotline-main` |
| `docs/AI_PLAN.md` | **The AI forward plan**: capabilities A1–A3, relief paths and task tickets, the vetting decisions and verification requirements. Treat it as the spec for the remaining work |
| `.env` (local only, git-ignored) | A working Anthropic API key is configured and was verified with a live `claude-opus-5` call. Never print, log or commit it |

## Copy-paste prompt for Codex

> You are taking over **LotLine** (AI Horizons 2026 AI for Housing Hackathon, Challenge 1, startup track; goal: top 3). Code freeze is Sun Sep 27 15:00 ET; the submission deadline is 23:59 ET. The repo is `~/Downloads/lotline-main`, remote `anitksahu/lotline`.
>
> Read, in order: `AGENTS.md` (hard rules: the engine decides, no AI prose without verification, no answer keys in the app, no PIN literals, forbidden words, offline fallback, **no AI attribution in commits**), this file, `docs/AI_PLAN.md` (the vetted spec), `docs/RECORDING_RUNBOOK.md`, and `docs/demo_script.md`.
>
> **Strategic context.** The user and all three reviewers agreed that the earlier build looked like "a rules engine with AI garnish". The remaining work makes Claude do the real work: **reading the unstructured public record**, with code verifying every AI claim and the engine still deciding. The headline demo moment is Centre Ave 10-S-5. Its PLI record `CF-PLI-2024-060362` (2025-01-02) says "Demo permit issued. DP-2024-13867. Property is demolished. No violation. Case withdrawn from court.", while the condemned-properties list still shows an active case. The engine refuses to score. The AI reader surfaces this quote-verified evidence, cross-checked against the permit data, for the human resolver, and routes the case to a PLI close-out check.
>
> **Step 1: bring the in-progress work to green.** The local working tree (also on branch `wip/ai-readers`) holds partly finished modules. Run `export PATH="$HOME/.local/bin:$PATH"; uv run pytest -q; echo $?` and `uv run python -m evaluation.run`. Finish, or fix, each workstream below against `docs/AI_PLAN.md`:
> 1. **A1 enforcement-record reader.** `scripts/fetch_record_text.py`, `data/record_text.csv` (PLI violations, condemned properties and PLI permits text for the 15 prepared lots, all untrusted text), and `lotline/ai/evidence.py`.
>    - API: `evidence_digest(pin, snapshot, *, client=None, use_cache=True, save_cache=True) -> EvidenceDigest`, plus `digest_lines` and `resolver_note`.
>    - Verification in code: exact-substring quotes of at least 8 tokens on clause boundaries; a clipped-negation guard; code-assigned dates and a latest/superseded `currency` tag; a lexicon check on the `indicates` label; two passes that must agree; injection rejection; demolition-permit `corroboration` from the permits data.
>    - Cache: `data/ai_cache/evidence/`, re-verified on load.
>    - Evaluation: `evaluation/ai_reader.py`, with recall against the pre-run labels in `tests/fixtures/record_relevance.csv`, an AI vs `keyword_baseline` comparison, and verification counts as n/N.
>    - Tests: `tests/test_ai_evidence.py`. The engine must never read the record text.
> 2. **A2 Ask LotLine.** `data/code_excerpts.json` (verbatim cited code excerpts), `lotline/ai/ask.py` and `lotline/ai/verify.py`. Claude chooses a fixed **answer frame** and selects **engine claim IDs plus verbatim code quotes**. **No model prose reaches users.** Permission answers always route to the Zoning Administrator. Out-of-scope questions get a categorized decline. Include 4 scripted `SUGGESTED_QUESTIONS`, verified live. Tests: `tests/test_ai_ask.py`.
> 3. **A3 ZBA precedents and required-relief paths.** `scripts/fetch_zba.py`, `data/zba/`, `lotline/ai/precedents.py`: quote-verified cards (case number, date, relief kind, verbatim outcome); honest granted/decided counts; `relief_paths(result)` (engine trigger → deterministic path table → verified code quote → precedents). Tests: `tests/test_ai_precedents.py`.
> 4. **UI.** `app.py`, `lotline/ui/ai_panels.py`, `panels.py`, `tickets.py`, `geo.py`, `lotline/costs.py`, `lotline/refresh.py`, `data/cost_assumptions.csv`:
>    - AI record reader at the top of the conflict packets, with a "Claude read N records in X s" counter, verified-quote badges and "the record says…" wording;
>    - the Ask LotLine panel with frames and chips;
>    - precedents and relief paths in the Zoning tile;
>    - internal task tickets (templated, never sent);
>    - a sale-specific cost worksheet;
>    - a read-only live drift check against WPRDC;
>    - an offline-safe outcome map;
>    - the header line "Claude reads the record. Rules decide. Code verifies every AI claim."
>
> **Step 2: live AI runs** (the key is in `.env`). Run evidence digests for all 15 lots, the scripted Ask questions on Benezet and Centre, and ZBA extraction and relief paths. Save **only verified** caches, then confirm the app shows them offline with the key removed from its environment (`env -u ANTHROPIC_API_KEY uv run --offline streamlit run app.py`).
>
> **Step 3: verification gate.** All of these must hold:
> - pytest exits 0;
> - `evaluation.run` exits 0, including the AI-reader section;
> - the 96-record memo sweep shows 0 violations, and `run_cases` passes 10/10;
> - a browser pass at 1280×800 over every view and the new AI panels shows no errors;
> - the unknown PIN `9999-X-9999` shows only the dated not-found message.
>
> **Step 4: science and review.**
> - Write `docs/scientific_validation.md` with an H1–H6 verdict table (`supported within scope` / `not supported` / `inconclusive`), plus the AI-reader results, clearly labeled retrospective internal validation. The numbers are in `docs/validation/results.md`.
> - Run three independent judge reviews (housing practice, university/responsible AI, investor). Each scores PV/UF/TE/DAI/ACT/CP out of 5 and gives CLEAR or BLOCK. Fix the blockers.
>
> **Step 5: demo package.** Rewrite `docs/demo_script.md` and `docs/RECORDING_RUNBOOK.md` around the AI-first beats in `docs/AI_PLAN.md`:
>
> | Time | Beat |
> |---|---|
> | 0:00–0:08 | Title card (presenter **Nibedita Biswal**) |
> | 0:08–0:25 | Problem: 96 vs 77 |
> | 0:25–1:00 | The AI reads Centre's records: verified demolition quote plus permit cross-check |
> | 1:00–1:35 | Rules refuse to score (1,672 vs 4,305 sf vs 2,400); the AI finding attaches to the PLI next check |
> | 1:35–1:50 | Task ticket |
> | 1:50–2:15 | Triage 7/3/3/1, with the map |
> | 2:15–2:45 | Ask LotLine on Benezet: a cited answer plus one decline |
> | 2:45–3:10 | Integrity n/N and a deliberate rejection |
> | 3:10–3:50 | Pilot and business: Land Bank/URA per-sale license; metrics are analyst hours and title/survey dollars avoided; proposed, no affiliation |
>
> Also:
> - Update the README first screen with the tagline: "LotLine's AI reads every public record on a tax-sale lot, quotes what matters, and stops analysts from spending title money on lots whose records disagree." Add an AI section.
> - Re-capture `docs/fallback/*.png` for the changed screens.
> - Update `docs/SUBMISSION_PAYLOAD.md` (AI disclosure: Claude Code, Codex, runtime Claude API as reader and assembler).
>
> **Step 6: ship.** Commit only green trees, with **no AI co-author trailers**. Merge the work to `main` with a normal fast-forward or merge (no history rewriting, no force-push). Push with the user's authorization and update this file. The user makes the repo public, uploads the video and submits the form; roster and attestation are theirs.
>
> **If time runs short, cut in this order:** the drift check, then the map, then the cost worksheet, then task tickets, then A3 counts. Never cut A1 (the headline), the verification rules or the offline fallback.

## Known facts to keep straight

- **Outcomes on the 14 advertised vacant lots:** 7 Advance, 3 Defer (records conflict), 3 Defer (site, Hillside), 1 Do not advance. The other 82 records: 63 structures and 19 not advertised.
- **Validation (committed):**
  - independent cohort agreement 77/77;
  - missingness: 0/105 advanced, negative controls 42/42 unchanged;
  - sensitivity 28/28 boundary pairs as declared;
  - memo protocol: 0 semantic false accepts in 862 runs.
- **Honest findings to report:** the prose checker alone accepts some hostile prose (38/136), which is why runtime never shows model prose. The expected labels are team-authored (conformance, not accuracy). Upstream extraction is not reproducible from the repo.
- **Presenter** on the title card: Nibedita Biswal. **Commit identity:** Anit Kumar Sahu <anit.sahu@gmail.com>.
- The API key was pasted into a chat transcript. Remind the user to **rotate it after the hackathon**.
