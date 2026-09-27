# LotLine handoff for Codex (written Sat Sep 26, 2026, evening ET)

> **Historical implementation handoff.** The P0 items below have been completed. For the authoritative final state and Claude takeover prompt, read `AGENTS.md`, `docs/STATUS.md`, and `docs/HANDOFF_FINAL_CLAUDE.md`.

This document records the implementation phase and its review method. It remains useful context, but it is no longer the current work queue.

## 0. Latest integrated review update (Sat Sep 26, 2026)

The P0 UI list and the subsequent three-judge review are complete in the current working tree. The integrated verification is **1,546 passed, exit 0; 0 memo violations across all 96 parcels; 10/10 adversarial/regression cases; unchanged 63/19/7/3/3/1 outcomes**.

Completed after the original handoff:

- Compare widget/card synchronization with AppTest coverage.
- Critical-conflict score suppression in packet, comparison and export.
- Short component reasons with full calculation expanders; plain-language zoning summaries.
- Snapshot-derived counts, dates and known rule limits; reason-specific Defer copy.
- Grouped memo display, compact citation drawer and deterministic summary.
- 1280-oriented triage columns; deterministic triage CSV and cited packet Markdown downloads.
- A standard current-advertisement pre-spend check owned by the City Treasurer / Real Estate Division.
- AI boundary hardened after an independent technical judge found semantic false accepts: Claude now returns only 6–12 unique IDs from immutable engine-approved claims. Mandatory status, score/abstention, conflict, withholding, principal-barrier and first-action claims cannot be omitted.
- Accurate in-window Codex disclosure, conditional Claude demo wording and a concrete hypothetical one-sale-cycle pilot plan.

Remaining submission blockers are external/recording work: live Claude verification is optional and requires `ANTHROPIC_API_KEY`; two timed spoken rehearsals, official-roster confirmation, final video/link, public-repository confirmation and form submission remain undone. The real 1280×800 fallback capture set is complete in `docs/fallback/`. Do not represent any remaining item as complete until it actually is.

---

## 1. Copy-paste prompt for Codex

> You are taking over **LotLine**, a working hackathon entry for the AI Horizons 2026 AI for Housing Hackathon (Challenge 1: Development Feasibility & Pro Forma Navigator, startup track). The goal is a **top-3 finish**. Submissions close **Sun Sep 27, 2026, 23:59 ET**. Judges watch a 3–5 minute demo video first, then look at the repo.
>
> The repo is at the repository root (GitHub `nbiswal-star/lotline`, branch `main`).
>
> 1. **Read these, in order:** `AGENTS.md` (hard rules), `docs/HANDOFF_CODEX.md` (this file: state, remaining work, review method), `docs/build_contract.md` (frozen product spec), `docs/implementation_plan_v5.md` (plan and acceptance tests), `docs/label_changes.md` (every rule and label change with citations), `docs/demo_script.md` (video script).
> 2. **Establish a baseline:** `export PATH="$HOME/.local/bin:$PATH"`, run `uv run pytest -q`, and confirm the exit code is 0. Run the verification script in §5. Start the app (`uv run streamlit run app.py`) and click through all four views at 1280px wide.
> 3. **Work the remaining-work list in §4 in priority order.** Keep each change small and verifiable. Commit only when the suite is green (check `$?`). Never push without the user's go-ahead.
> 4. **Review each milestone as three independent judges** (§6): housing-practice, technology/university and investor/startup. Each scores all six official criteria from 1 to 5, lists blockers with file:line evidence, and lists cheap high-value improvements. Fix blockers before moving on.
> 5. **Don't reopen decisions** recorded in §3 unless you have a primary-source citation showing one is wrong. If you do, record the change in `docs/label_changes.md`.
> 6. **Keep the product principle intact:** *the engine decides, Claude assembles, the checker enforces.* Claude selects immutable engine-approved claim IDs; it never computes, writes or overrides an outcome, score, conflict, next check or owner.
>
> When you finish a milestone, report: what changed, test count and exit code, the 96-parcel memo sweep result, the 10-case eval result, the judges' scores and blockers, and what's next.

---

## 2. What LotLine is, and what exists now

**Pitch.** For the Oct 2, 2026 Pittsburgh Treasurer Sale, the open-data feed lists 96 parcels but the City advertises 77. LotLine does the following:
- reconciles the two lists at runtime by PIN, with price checks;
- routes out 63 structures;
- screens the 14 advertised vacant lots into cited packets. Each packet has a transparent Development Ease score (0–6, always shown with its components), separate evidence coverage (5 groups), four flag tiles (zoning, environmental, infrastructure, policy/acquisition route), plain-language barriers, and next checks routed to named human owners.

It refuses to score through conflicting public records. For example, Centre Ave 10-S-5 is 1,672 sf in the assessment and 4,305 sf in County GIS, on either side of the 2,400 sf minimum, and it is "vacant" but has an active condemned case.

**Outcomes on the 14 vacant lots:**

| Outcome | Count |
|---|---|
| Advance to staff review | 7 (Benezet, Dearborn, Michigan ×2, Wylie, Saline, Kemper) |
| Defer: records conflict | 3 (Centre ×2, Walcott) |
| Defer: site conditions | 3 (Hillside/H lots) |
| Do not advance for housing | 1 (McClure, UI district) |

The other 82 records split into 63 structures and 19 not advertised.

**Architecture and file map:**

| Path | Role |
|---|---|
| `lotline/models.py` | Shared typed records, the `Outcome` enum and the fact-ID convention (`PIN:field:source`, `RULE:district:field`, `PIN:name:engine`) |
| `lotline/loaders.py` | Snapshot loading with `usecols` allowlists, normalization and startup assertions (96/77/19/63/14/15); `load_snapshot`, `context_for`, `lookup_pin` |
| `lotline/reconcile.py` | Runtime account→PIN normalization and price check |
| `lotline/facts.py` | Flat cited facts |
| `lotline/engine/` | Deterministic engine (`screen(ctx) -> ScreeningResult`): routing, conflicts, use, dimensions, hazards, coverage, scoring, checks, staleness, derived facts. `policy.py` holds every threshold and vocabulary |
| `lotline/memo/` | `deterministic.py` (cited memo); `checker.py` (12 semantic rules); `pipeline.py` (engine-approved claim catalog, claim-ID resolution, mandatory adverse/action claims, checker and fallback); `llm.py` (Claude claim-ID assembly); `synthetic.py` (labeled red-team inputs); `eval.py` (`run_cases()` gives "10/10 cases passed") |
| `lotline/ui/` + `app.py` | Streamlit views: Sale pipeline (funnel and 14-lot triage board), Parcel packet, Compare, Integrity. `viewmodels.py` holds pure functions; `text.py` holds copy |
| `data/` | Prepared public-source snapshot (pre-event data prep, disclosed in the README) plus `demo_config.json` |
| `tests/` | About 1,536 tests: loaders, reconciliation, boundaries, engine labels, invariants, properties, memo, LLM (fake client), UI view models, AppTest smoke tests |
| `scripts/split_answer_keys.py` | In-window data-hygiene script (moves answer keys to fixtures, drops household columns) |

**Claude integration** (`lotline/memo/llm.py`): Claude returns only 6–12 unique IDs from an engine-approved claim catalog. The server resolves immutable text, type and citations; inserts mandatory outcome, score/abstention, conflict, withheld-component, principal-barrier and first-action claims; then reruns the checker. Refusal, truncation, malformed/unknown/duplicate IDs, API errors, a missing key or any checker violation fall back to the deterministic memo. **It has never been run live**, because the machine has no API key. Only accepted selections are cached and re-checked on load.

---

## 3. Decisions already made (don't reopen without a primary source)

| Decision | Why | Evidence |
|---|---|---|
| Minimum lot sizes R1D-L 3,000 / R1D-H 1,200 / R2-H 1,200 / RM-M 2,400 sf; no VH minimum; per-unit density repealed | Enacted law, not a draft | Ord. No. 10-2025 (Bill 2025-1579), eff. 2025-05-07; ecode360 through 2026-09-16 (`docs/label_changes.md`) |
| P and LNC dimensions encoded (§905.01.C, §904.02.C); RIV-RM not modeled (§905.04.E) and labeled a tool gap | Verified code text | `docs/label_changes.md` |
| Single-unit is P in the P (Parks) district, so Saline and Kemper advance, but with an open-space designation check and a band cap (possible Steep Slope Overlay review, §906.08) | Follows the code; practitioner risk surfaced as a check, not invented policy | §911.02 use table; judge round 2 |
| slope25 overlap caps the band at "Conditional" | Planning Commission review is discretionary | §906.08 |
| No Advance while any score component is withheld; unknown FEMA zone means environment withheld | Abstention principle | Tech judge round 2 |
| Disclose-level area gap of 25% or more adds deed reconciliation (no score change) | Kemper 55%, Mossfield 32% | Housing judge round 2 |
| Triage, not ranking: no cross-neighborhood ranking | Scores aren't comparable across markets | Spec §3 |
| Kept out of the video: Saline and Kemper (Parks) | Avoid the "build in a park" reading | Investor judge |
| Presenter on the video title card: **Nibedita Biswal**; commits under Nibedita Biswal | User instruction | |
| Refusal fallbacks enabled (`fallbacks: "default"`) for Claude calls | Anthropic SDK guidance for Opus 5 | `lotline/memo/llm.py` |

---

## 4. Remaining work (priority order)

### P0: finish the in-progress UI polish (see §7 for the exact status of each item)
The lead reviewed the app in Chrome at 1280px and found these issues:
1. **Compare:** both selectboxes display "Wylie Ave" while the cards show Benezet and Michigan. Make the selectbox values match their cards, and add an AppTest.
2. **Decision-impact ordering:** the first barrier and first next check must be the most consequential. The order is critical conflict → material / below-minimum → use prohibition / unencoded / missing → H site standard → hazards → Parks designation → large disclosed gap → acquisition burden → corner. Base checks and Treasurer Sale terms go last. For example, Michigan 15-S-66's principal barrier should be terrain + undermining, not corner. Update the labels and add a "Round 3" section to `docs/label_changes.md`.
3. **Not-scorable consistency:** for critical-conflict parcels, show no component numbers in the UI (the memo checker already enforces this).
4. **Copy:** remove "buildable" from the UI copy, including the outcome meaning "It is not a finding that the lot is buildable…".
5. **Stale limits:** Integrity "Known limits" says P/LNC/RIV-RM are not encoded; only RIV-RM is. Derive this from `snapshot.rules`, and audit the other hardcoded text. Remove the literal "summary(run_cases()):" line.
6. **Defer meaning:** make the "Defer: missing or conflicting records" meaning specific to the actual reason (critical vs material vs tool gap vs missing input vs below minimum).
7. **Long reasons:** use `ComponentScore.short_reason` in the cards and put the full reason in an expander.
8. **Memo readability:** group the memo into sections, show citations compactly (full fact IDs in an expander), and add a deterministic summary line. Keep 0 violations across all 96 parcels.
9. **Triage board fit:** make it fit 1280px with no horizontal scroll (outcome, ease, coverage, principal barrier, first next check and owner all visible).
10. **Citation style:** normalize "Section 911.02" to "§911.02" in engine text.
11. **Zoning tile:** add a plain-language `site_standard_summary` column to `data/district_rules.csv`, and show it instead of the raw rule text.

### P1: judge round on the integrated build (M2–M6) plus the video script
Run the three judges (§6) and fix their blockers. Previous rounds' scores ranged from 3 to 5 per criterion. The weakest are **User Fit & Usability (3)** and **Continuation Potential (3)**, so the polish and a credible pilot/owner story matter most.

### P2: live Claude verification (needs the user's `ANTHROPIC_API_KEY`)
1. Assemble with Claude on Benezet and on Centre 10-S-5. Confirm each claim-ID selection is **accepted** by the checker, or read the fallback reason and tune `SYSTEM_PROMPT`. Never loosen the catalog, mandatory claims or checker.
2. Let the app cache one accepted selection per demo parcel, for the recording. It is labeled on screen as cached and re-checked.

### P3: deliverables (Sunday)
1. Commit `docs/demo_script.md` (the presenter is Nibedita Biswal).
2. Save fallback screenshots and clips for every scene to `docs/fallback/`.
3. Run the full regression again, test offline start (network off), model timeout and malformed-response behavior, and an unknown PIN.
4. Final README pass: every claim must match the app. The Integrity panel shows raw counts only ("10/10 cases passed").
5. Hold two timed rehearsals, then record. Runtime 3:45–3:55. The video must open with the hackathon name and the team.
6. Before submitting: make the repo **public**, confirm there are no keys (`grep -rn "sk-ant" . --exclude-dir=.venv --exclude-dir=.git` finds only the fake string in `tests/test_memo_llm.py`), fill in the Google Form (team members, track, description, video, repo, data sources, AI tool disclosure: Claude Code, Codex, Claude API; attestation).

**Official timeline:** code freeze is recommended at Sun 15:00 ET. The form closes at 23:59 ET with no extensions.

### Nice to have (only if P0–P3 are done)
- Show a Zoning Board of Adjustment precedent card in the zoning tile for Kendall St (H) and Rockland Ave (R1D-H). The data is in `docs/prep/README_prep_pack.md`, and a static card is fine.
- Add CI (a GitHub Actions workflow running pytest with the network off).

---

## 5. How to verify (run after every change)

```bash
export PATH="$HOME/.local/bin:$PATH"
uv run pytest -q; echo "exit=$?"            # must be 0
uv run python - <<'EOF'
from lotline.loaders import load_snapshot, context_for
from lotline.engine import screen
from lotline.memo.pipeline import produce_memo
from lotline.memo.eval import run_cases, summary
from collections import Counter
s = load_snapshot(); bad = 0; oc = Counter()
for p in s.treasury:
    r = screen(context_for(s, p)); oc[r.outcome.value] += 1
    m = produce_memo(r, None)
    if m.report is not None and not m.report.ok:
        bad += 1; print("VIOLATION", p, m.report.summary())
print("memo violations:", bad)            # must be 0
print(dict(oc))                           # 63 structure, 19 out, 7 advance, 3+3 defer, 1 do-not-advance
print(summary(run_cases()))               # must be 10/10 cases passed
EOF
```

Then check in a browser at 1280×800:
- **Pipeline:** the funnel reads 96 → 77 (77/77 PIN and price) → 63 structures + 14 vacant. The board has 14 rows, grouped by outcome.
- **Packet 131-N-31 (Benezet):** "5-6 of 6", four tiles, and next checks with owners.
- **Packet 10-S-5 (Centre):** red critical banner, amber material banner, "Not scorable", and no component numbers.
- **Unknown PIN `9999-X-9999`:** only "PIN not found in snapshot dated 2026-09-24".
- **Compare:** Benezet vs Michigan 15-S-66, with the "What explains the difference" line.
- **Integrity:** "10/10 cases passed · runs offline", and the red-team section shows the rejection and injection results.

---

## 6. How to review: three independent judges per milestone

The official judging is asynchronous, with at least 3 judges per project drawn from housing practice, universities, technology and investment. All six criteria are official, with no published weights. Score each 1–5:

1. **Problem Value:** does it address a costly, frequent or consequential housing bottleneck?
2. **User Fit & Usability:** is it intuitive, in plain language, and practical for planners, small developers, nonprofits and community partners?
3. **Technical Execution:** does the working demo reliably do its core tasks?
4. **Data & AI Integrity:** are sources, statutes and assumptions cited? Does it avoid PII, handle model uncertainty, and give a clear human-in-the-loop escalation path?
5. **Actionability:** does it directly speed up real decisions, rather than presenting abstract analytics?
6. **Continuation Potential:** is there a credible pilot, maintenance or ownership path (County, City Planning, URA, PHFA, Land Bank, CDCs)?

Mandatory eligibility checks:
- New code only, written after Sat 09:00 ET, with commit history intact.
- Working repo, a 3–5 minute video that opens with the hackathon name and the team, documentation, citations, and a limitations statement.
- Decision-support framing throughout.
- AI tools disclosed.
- Not a thin wrapper around an AI product.

Run each judge **independently**, in separate sessions or subagents, and don't let them see each other's output. Each one reads the relevant code, runs the app and scripts, and outputs:
```
PERSONA / MILESTONE
SCORES: PV x/5 · UF x/5 · TE x/5 · DAI x/5 · ACT x/5 · CP x/5
BLOCKERS (file:line evidence)
HIGH-VALUE IMPROVEMENTS (cheap)
RISKS TO WATCH
```

- **Housing-practice judge** (former Pittsburgh City Planning, URA or PHFA staff who has screened Treasurer Sale parcels). Checks domain correctness against the code (Ch. 903/904/905/906/911/915/921/925, Act 171 of 1984), safe wording, whether each next check routes to the right human, and whether an acquisitions office would use the tool.
- **Technology/university judge** (software engineer turned responsible-AI researcher). Checks correctness and edge cases, tests that could actually fail, determinism, provenance, abstention, the separation of labels from app code, offline and failure behavior, prompt-injection resistance, and code quality.
- **Investor/startup judge** (Pittsburgh civic-tech investor). Checks the video and README first screen, problem value, pilot and owner path, clarity of the narrative in 3–5 minutes, and whether the product says something useful rather than only refusing.

Judges can be wrong. Before changing a frozen rule, verify domain claims against primary sources (ecode360, Legistar, the City regulations PDF). Round 1 refuted several claims about "draft" minimum lot sizes.

---

## 7. Status of the in-progress polish at handoff

At the handoff commit the full suite is green (1536 passed, exit 0), all 96 parcels show 0 memo violations, and the 10 cases pass 10/10. Nothing has been checked in a browser since the ordering change, so start with §5.

| # | Item | Status | What remains / where |
|---|---|---|---|
| 2 | Decision-impact ordering | **DONE** | `policy.DECISION_IMPACT_ORDER`, `impact_rank()`, `STANDARD_TRIGGERS`, `SALE_TERMS_TRIGGER`; `checks.py` sorts barriers and checks and exposes `is_standard(nc)`. Labels regenerated (same items, new order). The rationale is in `docs/label_changes.md` Round 3. Michigan 15-S-66 now leads with terrain + undermining. |
| 10 | "§911.02" citation style | **DONE** | `lotline/engine/use.py` |
| 7 | Short reasons in cards | **PARTIAL** | The engine fills `ComponentScore.short_reason` (≤90 chars). Still to do: add `short_reason` to `ComponentVM` in `lotline/ui/viewmodels.py`, and have `render_scores` in `app.py` show it, with the full reason in a "How this was computed" expander. |
| 11 | Plain-language zoning tile | **PARTIAL** | `data/district_rules.csv` has a `site_standard_summary` column (all 10 districts), and it is loaded as the optional `DistrictRule.site_standard_summary`. Still to do: `viewmodels._tiles` should show the summary instead of the raw `site_standard`, drop the "density repealed" note, and show the §906.08 slope sentence only when slope25 overlaps. |
| 1 | Compare selectbox bug | NOT STARTED | Suggested fix: stop pre-seeding widget keys `cmp_a`/`cmp_b` in session state; keep the chosen PIN under a separate key, pass an explicit `index=`, and sync with `on_change`. Add an AppTest (default and after a change). |
| 3 | No component numbers on Not-scorable parcels | NOT STARTED | `app.py` ease card and compare cards |
| 4 | Remove "buildable" from UI copy | NOT STARTED | `OUTCOME_MEANING[ADVANCE]` in `lotline/ui/text.py` |
| 5 | Hardcoded facts to derive from data | NOT STARTED | Known-limits list in `app.py` (wrongly lists P/LNC); pipeline subheader "From 96 … to 14"; picker label "one of the 14 …"; "(9/16/2026)" in the funnel and in `OUTCOME_MEANING[OUT_OF_UNIVERSE]`; `TREASURER_SALE_BADGE` / `TREASURER_SALE_CITATION` sale dates; stale `CONTRACT_CASES` case 4 text ("P-district rules not encoded"); remove the "summary(run_cases())" caption |
| 6 | Reason-specific Defer meaning | NOT STARTED | Select the sentence from the `ScreeningResult` conflicts and component statuses |
| 8 | Memo readability | NOT STARTED | Grouped sections, compact citations, summary line. A new summary claim must be added to `engine_claim_texts` (used by `deterministic_memo`), or ENGINE_AUTHENTIC rejects it. Keep 0 violations across all 96 parcels. |
| 9 | Triage board fits 1280px | NOT STARTED | `st.column_config` widths; merge location and neighborhood; narrow Sale # |

Also not yet committed before this handoff, and now included in it: the README outcome-count paragraph ("What it found"), `docs/demo_script.md`, and this file plus `AGENTS.md`.

The session ended because of a usage limit, not because of a known defect.
