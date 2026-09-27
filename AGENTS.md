# AGENTS.md: standing rules for any coding agent working on LotLine

LotLine is our entry to the **AI Horizons 2026 AI for Housing Hackathon**, Challenge 1 (Development Feasibility & Pro Forma Navigator), startup track. The goal is a **top-3 finish**. The build window closes **Sun Sep 27, 2026, 23:59 ET**. **Live status: `docs/STATUS.md` (read first).** The final-mile method is in `docs/HANDOFF_CLAUDE.md`. `docs/HANDOFF_CODEX.md` is the earlier implementation-phase record.

## Commands

```bash
export PATH="$HOME/.local/bin:$PATH"     # uv lives here
uv run pytest -q                          # full suite; must exit 0 before any commit
uv run streamlit run app.py               # app on http://localhost:8501 (offline)
```

After `pytest`, check the **exit code** (`echo $?`). Piping it through `tail` once hid a failure and a red commit got in.

## Hard rules (the spec and the hackathon rules depend on these)

1. **Test labels never reach the app.** Application code (`app.py`, `lotline/`) must never read `tests/fixtures/expected_labels.csv`, `tests/fixtures/expected_reconciliation.csv` or `docs/prep/golden_set_prescreen.csv`. It also must never select the answer-key columns `in_city_advert_2026_09_16`, `advert_sale_no`, `advert_match_method`, `pin_match`, `price_check` or `sale_flag`. `tests/test_boundaries.py` enforces this. Don't weaken it.
2. **No 16-character PIN literals** in `app.py` or `lotline/`. Demo parcels come from `data/demo_config.json`. The word "fixtures" must not appear in `lotline/` sources (a boundary test checks this; synthetic inputs live in `lotline/memo/synthetic.py`).
3. **The engine decides.** Outcomes, scores, conflicts, barriers and next checks come only from `lotline/engine/` (pure functions, with thresholds in `lotline/engine/policy.py`). The UI renders engine output; it never computes. The LLM never decides.
4. **Unknown is never scored as 0.** Withhold, show "Partial", and route to a named next check. Never advance a parcel with any withheld component.
5. **Never resolve a records conflict in prose.** Show both sources. The critical current-condition wording in `docs/build_contract.md` §2 is verbatim.
6. **Forbidden words** in UI, memo and video: "buildable", "environmentally clear", "will be sold", and any sentence choosing a winning source. Say "apparent lower-discretion zoning path" and "no overlap in the checked screening layers".
7. **Offline first.** The app must start and work with no network and no API key. Claude (`lotline/memo/llm.py`, model `claude-opus-5`) runs only when the user clicks, behind the claim checker, with the deterministic memo as fallback.
8. **Every rule value is cited data**, in `data/district_rules.csv`. Any change to a rule or to `tests/fixtures/expected_labels.csv` must be recorded with its reason and citation in `docs/label_changes.md`.
9. **Decision-support framing everywhere.** The tool is never legal, financial, title, survey or zoning advice.

## Git

- Identity (repo-local): `Anit Kumar Sahu <anit.sahu@gmail.com>`. Remote: `git@github.com:anitksahu/lotline.git`, branch `main`.
- Commits show only the human contributor. Never add `Co-Authored-By:` trailers or other AI attribution to commit messages. AI use is disclosed in the README instead, as the hackathon requires.
- Commit only on a green suite. Write clear messages. Don't rewrite history, don't force-push, and don't push without the user's go-ahead.
- Commit history must stay intact from kickoff; the organizers check it.
