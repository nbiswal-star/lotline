# LotLine final-mile handoff for Claude

> **Historical handoff.** The authoritative current state is `docs/STATUS.md`; the concise takeover prompt is `docs/HANDOFF_FINAL_CLAUDE.md`.

## Current takeover state — 2026-09-27 final science pass

**Pushed milestone:** `9cf4b4f62df7c0de13fffc535bd97ce2af226692` on `origin/main` (`Merge AI-native evidence readers and scientific validation`). The history-preserving merge has parents `b7a47b4` and `6d062f4`.

**Final independent review at that milestone:**

- Housing practice: **CLEAR** — PV 5 · UF 5 · TE 5 · DAI 5 · ACT 5 · CP 5.
- Startup/investor: **CLEAR** — PV 5 · UF 5 · TE 5 · DAI 5 · ACT 5 · CP 4.
- Principal AI science: **SCIENCE: CLEAR** — PV 5 · UF 4 · TE 5 · DAI 5 · ACT 5 · CP 4.

**Verification:** 1,816 passed, 1 expected failure, exit 0; all nine evaluation sections and assertions held; 0 memo violations / 96; 10/10 integrity cases. A credential-free `uv run --offline streamlit run app.py` launch bound successfully on localhost and `/_stcore/health` returned `ok`. The static headless browser did not complete Streamlit's websocket render (it remained on the loading skeleton), so rely on the passing AppTest coverage and perform the final interactive 1280×800 recording check manually.

The AI-reader milestone has replaced the older "claim ordering" narrative. Start with `AGENTS.md`, `README.md`, `docs/scientific_validation.md`, `docs/AI_PLAN.md`, and `docs/demo_script.md`; treat older statements later in this file as historical where they conflict.

Current implementation and observed live results:

- **A1 is the headline:** Claude retrieves event-bearing passages from heterogeneous PLI, permit and condemned-property text. Code checks record/field/recorded-date identity, exact quote provenance, boundaries, clipped negation, instruction-like content and permit references; it only notes later-dated records and does not establish semantic supersession or temporal truth. Unsupported semantic labels become `unverified_label`; relevance is derived in code. Two same-model runs must reproduce each model-proposed `(record, field, date, quote, label, relevance)` tuple. A deterministic exact `Active` status companion may be attached from an AI-surfaced condemned record outside that recurrence denominator. Never describe the runs as independent confirmation.
- **No-AI counterfactual:** on the team-labeled development audit (21 records, 3 conflict parcels, 12 labeled relevant), verified Claude retrieval returned TP/FP/FN 12/0/0; the declared keyword scan returned 12/9/0. This is retrospective internal conformance on development data, not accuracy, external validity, proof of model necessity, or measured time savings.
- **A2 live smoke:** all 12 suggested-question runs across Benezet and Centre answered or safely declined; five adversarial/out-of-scope questions were declined or rejected, with no accepted model prose. Ask LotLine selects fixed frames, engine claim IDs and exact code excerpts; it does not write prose. The reproducible status/frame record is `docs/validation/live_ai_smoke.json`; this is a scripted smoke run, not validation.
- **A3 is secondary:** after semantic relief-kind verification, only 6/8 selected ZBA decisions produced usable cached cards. Do not headline it, infer approval propensity, or call it a validated precedent base. Relief paths remain deterministic and cards say they are not predictions.
- **Scientific gate:** `uv run python -m evaluation.run` passes all nine sections; `docs/scientific_validation.md` contains H1–H6 verdicts, threats and the next-study design. The latest full suite before this handoff was 1,815 passed, 1 expected failure, exit 0; rerun after any change.
- **Live caches:** verified evidence caches for 9 parcels and verified ZBA caches are under `data/ai_cache/`; every load re-verifies against committed source text. No API key is stored. Do not commit or print credentials.

Your remaining assignment is review and demo completion, not production infrastructure:

1. Re-run the full suite, evaluation, memo sweep, 10/10 cases, secret scan and offline app.
2. Inspect every AI panel at 1280×800, especially Centre's cached evidence, the AI-vs-no-AI expander, Benezet Ask LotLine and rejected/declined states. Capture replacement fallback frames for changed screens.
3. Audit the demo narration against actual screen values. Keep the scientific limitations on screen; do not strengthen claims.
4. Run three independent final judges. The responsible-AI judge must explicitly return `SCIENCE: CLEAR`. Treat any semantic/provenance blocker as release-blocking.
5. If the code milestone is already committed and pushed, do not rewrite it. Make only green, focused follow-up commits. Push after each major cleared milestone; never force-push.
6. Leave human-only evidence explicitly open: two spoken timed rehearsals, final video playback by a second person, roster/eligibility confirmation, making the repository public, video upload and form attestation/submission.

The demo's central sentence is: **Claude reads messy longitudinal records and proposes evidence; code verifies provenance and recorded dates; deterministic rules abstain; a named human resolves meaning.**

**Status date:** 2026-09-26 ET  
**Submission deadline:** Sun Sep 27, 2026, 23:59 ET  
**Goal:** a top-3 finish in the AI Horizons 2026 AI for Housing Hackathon, Challenge 1, startup track  
**Repository:** `nbiswal-star/lotline`, branch `main`

This is the authoritative handoff for the remaining **scientific validation**, review, recording and submission work. Read `AGENTS.md` first. `docs/HANDOFF_CODEX.md` records the earlier implementation phase and is useful history, but its old P0 list is superseded by this file.

**Priority:** LotLine is a hackathon research/demo prototype, not an industrial production release. The application is already engineered and tested. Do not spend the remaining window on deployment architecture, scale, observability, service reliability or production process. Spend the majority of remaining analytical effort on whether the method, evidence, experiments and claims are scientifically defensible. Repository publication and form mechanics are eligibility checks, not the intellectual center of the project.

## Copy-paste takeover prompt

> You are the final-mile owner for **LotLine**, an entry in the AI Horizons 2026 AI for Housing Hackathon, Challenge 1 (Development Feasibility & Pro Forma Navigator), startup track. The objective is a **top-3 finish**, not minimum compliance. The deadline is **Sun Sep 27, 2026, 23:59 ET**.
>
> Work autonomously and persist to the real outcome. Start by reading, in order:
>
> 1. `AGENTS.md` — hard product, safety, testing and Git rules.
> 2. `docs/HANDOFF_CLAUDE.md` — current state, milestones and exit criteria.
> 3. `docs/build_contract.md` — frozen product contract.
> 4. `docs/demo_script.md` and `docs/fallback/README.md` — the submission narrative and verified backup media.
> 5. `README.md`, `docs/label_changes.md`, and the amendment at the end of `docs/implementation_plan_v5.md`.
>
> Do not assume the handoff is correct. Re-establish every material claim from the data, cited rules, code, experiments and running app. Review the whole method, not only the latest diff. Treat tests as engineering evidence, not scientific validation. Preserve the central invariant: **the engine decides; Claude assembles; the checker enforces.** Runtime Claude may select only immutable engine-approved claim IDs. It never writes or changes outcomes, scores, conflicts, citations, next checks or owners.
>
> Execute milestones M0–M5 below in order. Use three independent review perspectives—housing practice, university/data-science and responsible technology, and startup/investment—at M1 and once more before publication if any material code, domain rule or narrative claim changes. M2–M5 use their explicit evidence gates; do not burn the submission window on redundant reviews. Fix every genuine blocker, rerun the complete verification, and re-review the integrated result. Do not weaken a test, checker, abstention rule or product boundary to make a review pass.
>
> Never claim a manual or external action is complete without evidence. Timed spoken rehearsals, team-roster confirmation, video upload, repository visibility and form submission require actual verification. If credentials or human action are unavailable, finish everything else and report the exact blocker, owner and next action.
>
> Keep all work within the hackathon scope and preserve commit history. Before any commit: full suite green with exit code 0, zero memo violations across all 96 parcels, 10/10 integrity cases, clean diff check and no leaked secrets. Use the repository identity `Nibedita Biswal <nbiswal@andrew.cmu.edu>`. Do not rewrite history or force-push. Push only with current user authorization.
>
> At handoff completion, report evidence—not confidence: commit and remote SHA, test count and exit code, memo sweep, outcome counts, integrity result, browser checks, three judge verdicts, public/logged-out link checks, video runtime/link, form confirmation, and any remaining blocker with its owner.

## Current verified state

The following was true immediately before this handoff was written. Verify it again rather than trusting it:

- `main` and `origin/main` pointed to `fa5d10ffa7ad14a0780613dc41ccb47fbd31cc82` after two final implementation commits:
  - `b7df5d5` — harden memo boundary and finish the top-three UI workflow.
  - `fa5d10f` — add final demo fallback assets.
- Full suite: **1,546 passed, exit 0**.
- Deterministic memo sweep: **0 violations across all 96 records**.
- Integrity suite: **10/10 cases passed**.
- Outcomes remained: **63 structures routed out, 19 outside the advertisement, 7 advance to staff review, 3 defer for records conflict, 3 defer for site conditions, 1 do not advance for housing**.
- Three independent final judges—housing, technology/responsible AI, and startup/investor—each returned **CLEAR FOR PUSH**.
- All nine PNGs in `docs/fallback/` were opened and verified at 1280×800. They cover the title, pipeline, Benezet score, Benezet checks, Centre abstention, comparison, integrity, memo and pilot.
- The app was started offline and exercised through all four views. The capture server and browser were stopped afterward.
- The GitHub repository existed and received the final commits, but its visibility was **private** when last checked. Public/logged-out verification remains mandatory.
- The only secret-scan match was the deliberately fake authentication-error string in `tests/test_memo_llm.py`.
- No `ANTHROPIC_API_KEY` was available. A live Claude call is optional; the deterministic path is the intended safe recording path unless both demo parcels pass the checker live.
- The two timed spoken rehearsals, final video, official roster confirmation, video upload and submission form were not complete.

## Scientific thesis and evaluation contract

### Thesis

Public-record disagreement and missing site information create false precision in parcel-screening tools. LotLine tests a specific alternative: a provenance-preserving deterministic screening method that **selectively abstains**, represents bounded uncertainty and routes unresolved questions to named human experts before paid diligence.

The scientific contribution is not a claim that LotLine predicts development success. It is a testable workflow claim:

1. a dated sale cohort can be reconciled reproducibly across heterogeneous public sources;
2. decision-changing conflicts and missing inputs can be detected before a score is emitted;
3. deterministic policy logic can produce traceable results and explicit uncertainty instead of opaque ranking;
4. a constrained language layer can select and order immutable claims without changing the underlying decision state. Any readability or comprehension benefit remains an untested prospective hypothesis.

### Units, reference standards and scope

- **Source cohort:** 96 records in the frozen WPRDC Treasurer Sales snapshot.
- **Advertised cohort:** 77 records reconciled to the City advertisement.
- **Primary analytic cohort:** 14 advertised vacant lots; the 63 advertised structures are deliberately outside the vacant-land model.
- **Reference artifacts:** cited statutes/rules and source snapshots; a 15-parcel hand-labeled conformance set; invariant/property tests; synthetic adversarial cases.
- **Scope:** internal validity and specification conformance for one dated Pittsburgh sale. There is no independent prospective outcome dataset and no basis for claims of predictive accuracy, causal impact, financial return or cross-city generalization.
- **Reproducibility boundary:** the repository can reproduce reconciliation and screening from the committed prepared snapshots. The pre-event public-source extraction and transformation queries were ad hoc and were not retained, so source-to-snapshot reproduction is not established. A prospective refresh pipeline is future validation work.

### Retrospective post-build validation hypotheses

These structured audit questions were formulated after the application was developed and the cohort results were known. They are not preregistered and cannot support confirmatory statistical claims. Freeze their wording and the evaluation protocol before the final validation run, disclose the confirmation-bias risk, and report supporting and disconfirming evidence:

- **H1 — Cohort reproducibility:** the two sale sources reconcile to 77/77 advertised records by normalized parcel identity, with 77/77 price cross-checks, while retaining all 19 non-advertised source records as explicitly routed observations.
- **H2 — Conflict-sensitive abstention:** every critical conflict represented by the declared detection policy in the frozen cohort and synthetic cases withholds whole-parcel scoring, shows both loaded sources and produces a named resolver; no such parcel leaks a component score through UI, comparison, memo or export. This does not establish detection of conflicts absent from the loaded sources or declared policy.
- **H3 — Missingness and uncertainty:** unknown inputs are never treated as zero; unresolved corner status produces a bounded score range; withheld components prevent advancement.
- **H4 — Policy traceability:** every rule-dependent output traces to cited data or a declared engine policy, and perturbations across a policy boundary change only the outputs mechanically downstream in the declared dependency graph.
- **H5 — Language-layer fidelity:** across all 96 records and adversarial cases, memo assembly cannot introduce, omit or invert mandatory decision facts; malformed or hostile model behavior fails closed to the deterministic memo.
- **H6 — Structural actionability completeness:** every engine-raised conflict, barrier, withheld input or decision-blocking condition maps to an explicit next check and accountable human role, including the current-sale pre-spend gate. Declared out-of-scope topics need not each create a check. Presence is a structural measure; correctness and usefulness of the assigned owner require independent practitioner review or pilot evidence.

### Required evidence hierarchy

Report results in four separate tiers so judges cannot confuse them:

1. **Primary-source validity:** rule/source citation audit and cohort reconstruction.
2. **Internal method validity:** deterministic invariants, threshold/sensitivity tests, leakage controls and full-cohort error analysis.
3. **Adversarial robustness:** counterexamples, injection, malformed model output and unsafe-ablation comparisons.
4. **External validity:** currently unproven; specify the prospective expert review and next-sale pilot needed to establish it.

Never present 1,546 passing tests as “accuracy.” Never use the team-authored expected labels as independent ground truth.

## Non-negotiable product boundaries

These are release blockers, not preferences:

1. Application code must never read answer keys or pre-event golden labels. Keep `tests/test_boundaries.py` strong.
2. No 16-character PIN literal may enter `app.py` or `lotline/`. Demo parcels come from `data/demo_config.json`.
3. Only pure functions in `lotline/engine/` decide outcomes, scores, conflicts, barriers and next checks. The UI renders; the model assembles.
4. Unknown is withheld, never converted to zero. No parcel advances with a withheld score component.
5. Never resolve conflicting records in prose. Show both sources, withhold as required and name the human resolver.
6. UI, memo and video must avoid the forbidden claims in `AGENTS.md`. Use the exact safer wording required there.
7. The complete product works without network access or an API key. Model failure always returns the deterministic cited memo.
8. Rule values live in cited data. Any rule or expected-label change requires a cited entry in `docs/label_changes.md`.
9. Decision-support framing must remain explicit. This is not legal, financial, title, survey, appraisal or zoning advice.
10. Preserve the runtime AI protocol: 6–12 unique approved claim IDs; server-side resolution; mandatory adverse/status/action claims; deterministic checking; fail-closed fallback.

## Milestone runbook

### Final-day priority and time budget

- **By Sun Sep 27, 15:00 ET:** freeze product code. Scientific evaluation artifacts and accurate narrative corrections may continue; optional product features may not.
- **By 19:00 ET:** target a complete submission with working public-repository and video links, leaving time for upload, permissions or form repair.
- **After 19:00 ET:** no optional features, live-model tuning or repeated audits. Work only on recording, upload, accessibility, broken links, form completion or a true submission blocker.
- Optional live Claude verification is always subordinate to a complete deterministic-offline submission.

### M0 — Reproduce the baseline

Do this before changing anything:

```bash
export PATH="$HOME/.local/bin:$PATH"
git status --short --branch
git log --oneline --decorate -8
uv run pytest -q
pytest_exit=$?
echo "pytest_exit=$pytest_exit"
test "$pytest_exit" -eq 0
git diff --check
```

Check the pytest process exit code directly. Then run:

```bash
uv run python - <<'PY'
from collections import Counter
from lotline.engine import screen
from lotline.loaders import context_for, load_snapshot
from lotline.memo.eval import run_cases, summary
from lotline.memo.pipeline import produce_memo

snapshot = load_snapshot()
outcomes = Counter()
violations = []
for pin in snapshot.treasury:
    result = screen(context_for(snapshot, pin))
    outcomes[result.outcome.value] += 1
    memo = produce_memo(result, None)
    if memo.report is not None and not memo.report.ok:
        violations.append((pin, memo.report.summary()))
print("outcomes:", dict(outcomes))
print("memo violations:", violations)
print("integrity:", summary(run_cases()))
PY
```

At M0, locate the official organizer submission-form URL and verify its closing time, authentication owner and required fields. If the URL or account owner is unavailable, surface that dependency immediately while continuing every unblocked task.

Start the app under a genuinely network-unavailable condition and inspect it at exactly 1280×800. Remove all supported Anthropic credential paths from the app process, do not click the optional Claude action, and block outbound network access. Confirm all four views and both downloads still work. “No API key” by itself is not an offline test. Also confirm:

- Pipeline: 96 → 77, with 77/77 PIN and price reconciliation, then 63 structures + 14 vacant lots; all triage headers visible.
- Benezet: 5–6 of 6; components and evidence are distinct; the current advertised-sale status check comes before spending; every check has an owner.
- Centre: both critical and material conflicts; “Not scorable”; no component values in packet, comparison or export.
- Compare: selector labels match the rendered cards; Benezet versus Michigan explains the difference.
- Integrity: 10/10; rejection and injection defenses visible; no stale raw implementation language.
- Unknown PIN: a dated not-found message and no inferred result.
- Both downloads: cited Markdown packet and deterministic triage CSV; critical parcels leak no score or component values.

**M0 exit:** baseline reproduced, or every discrepancy recorded with command/output and file evidence.

### M1 — Scientific validation and whole-system audit

This is the primary remaining milestone. Do not spend it polishing infrastructure. Produce a concise `docs/scientific_validation.md` and a reproducible evaluation command or script that reports the evidence below from source data and engine output. Generated tables must state their cohort and denominator.

Review the entire implementation, not just smoke paths:

- **Domain and policy:** validate the encoded zoning and sale-rule claims against the cited primary sources already recorded in `data/district_rules.csv`, `data/source_manifest.csv`, `docs/build_contract.md` and `docs/label_changes.md`. Do not browse for speculative reinterpretations when a frozen, cited decision already exists.
- **Engine:** trace every outcome family, conflict severity, withheld component, barrier ordering and next-check owner. Test invariants rather than examples alone.
- **Data boundary:** inspect loader allowlists, answer-key separation, PII exclusions, source dates, count assertions and PIN handling.
- **AI safety:** adversarially exercise unknown/duplicate/malformed IDs, omissions, refusals, truncation, timeouts, stale cache, permission inversion, fabricated facts, source-winning prose and prompt injection. All must fail closed without altering engine decisions.
- **UI and exports:** compare every displayed/exported decision field to the corresponding engine result. Check 1280×800 legibility, keyboard/basic accessibility, loading/error states and current snapshot wording.
- **Narrative:** verify README, app, demo script, screenshots and pilot slide agree on counts, capabilities, limitations, AI use, affiliations and what is hypothetical.
- **Repository:** preserve kickoff history, validate authorship/timestamps, dependency lock, offline install/run instructions, license if required by the event, and absence of secrets or generated junk.

#### Scientific and evidentiary validity gate

This is not only an engineering review. Audit whether the evidence supports the claims being made:

- **Research question and construct validity:** state precisely what is evaluated—deterministic conformance to the declared screening policy on a frozen public-records snapshot. Development Ease is a policy-defined screening construct, not total development feasibility, financial viability, market attractiveness, a causal effect or legal ground truth.
- **Provenance and reproducibility:** trace every committed input, rule, derived value and as-of date; reproduce the 96 → 77 → 63 + 14 cohort construction from the frozen snapshots; verify the locked environment and commands allow an independent reviewer to reproduce results after dependency installation. Explicitly disclose that upstream source extraction is not reproducible from this repository.
- **Label integrity and leakage:** prove application code cannot read expected labels or golden-set columns. Explain that the small hand-labeled set was created by the same team and therefore measures specification conformance, not independent real-world accuracy.
- **Measurement and uncertainty:** verify that missingness is distinguished from a measured zero, range scores preserve corner-status uncertainty, evidence coverage is not conflated with lot quality, and record conflicts cause abstention rather than imputation or source selection.
- **Sensitivity and boundary analysis:** exercise values immediately around encoded policy thresholds, area-gap severity bands, staleness boundaries and score-band caps. Confirm conclusions change only where the declared policy says they should.
- **Error analysis:** review every non-advance/defer family and all 14 advertised vacant parcels, not only aggregate pass counts. Report false-accept risks, false-deferral risks and which questions still require fieldwork, title work, survey, appraisal, utilities or market analysis.
- **External validity:** clearly limit findings to the dated Pittsburgh Treasurer Sale snapshot. Do not generalize performance to other sales, cities, parcel types or structures without new validation.
- **Claim discipline:** distinguish observed source facts, deterministic derivations, approximate geometry, synthetic red-team inputs and hypothetical pilot assumptions. No benchmark number may imply predictive accuracy unless its denominator, reference labels and limitations are shown.

Run and document these experiments:

1. **Cohort reconstruction:** independently recompute 96 / 77 / 19 / 63 / 14 from the two frozen inputs and report reconciliation exceptions, not only totals. Do not use production `reconcile()` as the sole oracle: implement an independent evaluation-only join or row-audit the source pairs and list exception rows.
2. **Outcome and abstention matrix:** report every one of the 14 vacant parcels by outcome, conflict class, score status/range, withheld component, principal barrier and first resolver. Aggregate only after showing parcel-level traceability.
3. **Reference-label conformance:** report exact agreements and disagreements against the 15-parcel expected set by field. Label this *team-authored specification conformance*, never accuracy. Explain each mismatch rather than hiding it in a mean.
4. **Boundary sensitivity:** on in-memory or temporary evaluation copies only, perturb each consequential numerical threshold immediately below, at and above its boundary—including area-gap levels, minimum lot area, staleness and score-band caps—and demonstrate the minimal expected downstream change.
5. **Missingness/uncertainty tests:** on in-memory or temporary evaluation copies only, inject unknown FEMA, district, area and corner states; report whether the method withholds, ranges or routes correctly. Include negative controls where known values remain unchanged.
6. **Unsafe comparator/ablation:** treat these as post-hoc illustrative stress tests, not unbiased benchmarks. Before inspecting results, freeze each evaluation-only algorithm, including exact source-selection, missing-value and disposition rules. Compare LotLine with clearly labeled naive policies such as “take the first area source” or “convert unknown to zero”; use declared synthetic perturbations where the 14 real parcels lack the relevant missing state. Show parcel-level divergences and raw denominators. Never rewrite committed snapshots, engine policy, district rules or expected labels; never ship these policies in application code; never imply they represent a commercial competitor or support superiority, causal or generalization claims.
7. **Adversarial language fidelity:** on temporary inputs only, replay false source selection, permission inversion, fabricated owner/utility claims, prompt injection, unknown/duplicate claim IDs, omissions, refusal, truncation and timeout. Report raw `n/N` acceptance and fallback results plus any semantic false accept. These enumerated cases are not an estimate of real-world model reliability.
8. **Error and threat analysis:** for each outcome family, identify the most plausible false-advance and false-deferral mechanism, whether current tests could detect it, and the real-world evidence needed to resolve it.
9. **Reproducibility check:** from the locked environment, install dependencies while retrieval is available if they are not cached; then block outbound network and have a clean process reproduce the evaluation output and app from the committed snapshots. Record the command, software/data versions, relevant hashes and output. Do not imply an uncached Python environment can install dependencies offline.

If an experiment cannot be run honestly with the available data, record it as an unvalidated hypothesis and specify the smallest defensible prospective study. Do not manufacture a metric.

The university/data-science judge must explicitly return `SCIENCE: CLEAR` or `SCIENCE: BLOCK`, with evidence for construct validity, source/reference validity, leakage control, uncertainty, sensitivity/ablation design, error analysis, reproducibility and limitations. A green test suite alone cannot clear this gate.

Use three independent judges. Each must lead with `CLEAR` or `BLOCK`, provide file/line or screen evidence, list blockers and cheap high-value improvements, and score the six official criteria from 1–5 in this exact form:

`PV x/5 · UF x/5 · TE x/5 · DAI x/5 · ACT x/5 · CP x/5`

The criteria are **Problem Value, User Fit & Usability, Technical Execution, Data & AI Integrity, Actionability, and Continuation Potential**.

| Judge | Primary challenge |
|---|---|
| Housing-practice | Would an acquisition analyst trust and act on this packet without mistaking it for an approval or acquisition recommendation? |
| University/data science and responsible technology | Are the constructs, provenance, cohort, labels, uncertainty, sensitivity, limitations and reproducibility scientifically defensible, and can data, UI or model behavior bypass determinism, abstention or offline fallback? |
| Startup/investor | Does the first minute establish a consequential problem, differentiated solution, credible operator/pilot and continuation path? |

Require file/line or screen evidence. Resolve disagreements by checking code, tests and primary sources—not by averaging opinions.

**M1 exit:** `docs/scientific_validation.md` exists; its reproducible command/script runs; it contains an H1–H6 verdict table using only `supported within scope`, `not supported` or `inconclusive`; all nine experiment outputs are present or explicitly recorded as unvalidated with a prospective study; the university judge returns `SCIENCE: CLEAR`; all three judges clear the integrated tree; no unresolved P0/P1 defect; full verification remains green.

### M2 — Demo and evidence package

Use `docs/demo_script.md` as the spoken source of truth and `docs/fallback/` as the recovery package.

1. Confirm the official team roster and presenter spelling before recording. Update title card, narration and submission metadata together if it differs.
2. Run two real, spoken, timed rehearsals. Log date/time, runtime and concrete corrections in `docs/demo_script.md`. A scripted UI walk-through is not a spoken rehearsal.
3. Keep runtime between 3:00 and 5:00; target 3:45–3:55. Open with the hackathon name and team.
4. Prefer the deterministic offline memo. Show live/cached Claude only if Benezet and Centre both produce checker-accepted selections; otherwise demonstrate the fail-safe fallback honestly.
5. Record at 1280×800. Keep the decision-support banner and snapshot dates visible. Show the Centre abstention, named checks, comparison, integrity result and concrete pilot.
6. Review the final audio for housing-practice safety: say the parcels are **advertised**, never imply the sale will occur, never imply clear title, site approval or acquisition suitability, show both Centre area values, and state that title, utilities, legal access, appraisal and market demand remain unestablished.
7. Have a second person play the exported video from beginning to end—not merely review the script or screenshots—and check picture, audio, roster, counts, disclosures, forbidden claims, runtime and logged-out accessibility.

The scientific story—not production infrastructure—must anchor the demo:

- the failure mode is false precision from conflicting and incomplete public records;
- the method is provenance + deterministic policy + selective abstention + named human resolution;
- Centre is the counterexample demonstrating why abstention changes the decision path;
- the 96/77/14 cohort and parcel-level findings are reported with denominators;
- the memo adversarial result demonstrates decision-layer separation, not general AI intelligence;
- limitations explicitly distinguish internal conformance from external/prospective validation.

After M1, update `docs/demo_script.md` to use only observed validation results and rerun both timed rehearsals. The narration must call this **retrospective internal validation** and must not imply preregistration, independent ground truth, source-to-result reproducibility or external validation.

Do not lead with framework choices, deployment, test count or the Claude API. Those are supporting controls, not the scientific result.

**M2 exit:** two logged rehearsals; final 3–5 minute exported file actually played and reviewed by a second person; fallback frames retained; video hosted at a logged-out-accessible URL.

### M3 — Publication and repository release

Treat this as a short eligibility check after the science and demo are sound. Do not add production infrastructure, observability, hosting or CI unless an organizer requirement makes it blocking.

Immediately before publication:

```bash
uv run pytest -q
git diff --check
git status --short --branch
git status --short --untracked-files=all
git ls-files --others --ignored --exclude-standard
rg --hidden --no-ignore -I -l 'sk-ant-|sk-proj-|ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY' . -g '!.git/**' -g '!.venv/**' -g '!**/__pycache__/**' -g '!.pytest_cache/**' -g '!.ruff_cache/**' -g '!docs/fallback/*.png' -g '!*.mp4'
```

These commands list filenames or Git status, not secret values. The `sk-ant-SECRET bad` test literal is fake; investigate every other match without printing real secret values into logs. Inspect untracked and ignored credential-like filenames, and confirm no `.env`, cache, recording scratch file or credential is tracked. After committing, rerun the tracked-tree scan against the new `HEAD`.

Set and verify the repository-local identity before committing:

```bash
git config --local user.name "Nibedita Biswal"
git config --local user.email "nbiswal@andrew.cmu.edu"
git config --local --get user.name
git config --local --get user.email
```

Commit only a green, reviewed tree using `Nibedita Biswal <nbiswal@andrew.cmu.edu>`. Do not amend, rebase away history, force-push or delete evidence. Push only with current user authorization. Make the repository public only with authority to change visibility, then verify the README, screenshots and clone URL in a logged-out/private browser.

**M3 exit:** local HEAD equals `origin/main`; public repository loads logged out; default branch is `main`; README media renders; no genuine secret matches.

### M4 — Submission form

Use the official form URL, authentication owner and field inventory verified at M0. Prepare the exact form payload before entering it:

- team members and startup track;
- Challenge 1 title and concise description;
- public repository URL and logged-out-accessible video URL;
- data-source list and citations;
- AI disclosure: Claude Code, OpenAI Codex and optional runtime Claude API;
- limitations and required attestation.

Have a second person compare the entered form to the prepared payload before submission. Claude may prepare and verify the payload, but it must not make the eligibility attestation or submit the form without explicit confirmation and authorization from the team owner. Roster membership and eligibility are human-confirmed facts. Capture the confirmation page or receipt and timestamp. Do not treat a drafted form as submitted.

**M4 exit:** receipt/confirmation exists and both links were rechecked after submission.

### M5 — Final freeze and handback

After submission, do not introduce feature work. Record:

- submission timestamp and confirmation evidence location;
- public repository URL, video URL and final SHA;
- final test/memo/integrity results;
- three judge verdicts;
- known limitations and pilot next step.

**M5 exit:** every item in the release evidence table below has evidence or an explicit owner/blocker.

## Release evidence table

Claude should maintain this table in its final report; do not mark a row complete from assumption.

| Evidence | Required result | Current handoff state |
|---|---|---|
| Full test suite | Exit 0; expected test count explained | 1,546 passed |
| Memo sweep | 0 violations / 96 records | Passed |
| Integrity suite | 10/10 | Passed |
| Outcome distribution | 63 / 19 / 7 / 3 / 3 / 1 | Passed |
| Offline app | All four views and downloads work | Passed; recheck |
| 1280×800 fallback media | All scenes legible | Nine PNGs verified |
| Three independent judges | Three explicit clears | Passed before handoff; rerun after changes |
| Scientific validity gate | Science clear with methods evidence | **Must be explicitly rerun** |
| Scientific validation artifact | Hypotheses, methods, results, threats, reproducible command | **Not yet complete** |
| Sensitivity and unsafe-ablation results | Denominators and parcel-level divergences shown | **Not yet complete** |
| Clean-process reproducibility | Command, locked environment/data version, relevant hashes and output | **Not yet complete** |
| Secret scan | No genuine credentials | Only fake test literal found |
| Official form URL/access | URL, deadline, owner and fields verified | **Not yet evidenced** |
| Repository visibility | Public and accessible logged out | **Blocked: private when last checked** |
| Official roster | Confirmed against registration | **Not yet evidenced** |
| Spoken rehearsals | Two logged, each 3–5 minutes | **Not done** |
| Final video playback | Export played end to end by second person | **Not done** |
| Final video access | URL accessible logged out | **Not done** |
| Submission form | Confirmation/receipt captured | **Not done** |
| Submitted-link recheck | Repo/video rechecked with timestamp | **Not done** |

## Quality rules for remaining changes

- Prefer deleting ambiguity over adding features. The core demo is already competitive.
- A visual or copy change must improve the 3–5 minute story without weakening precision.
- Do not add a live dependency, map service or model requirement.
- Do not change a rule value or label merely because a judge dislikes an outcome. Verify against a primary source and document any necessary change.
- Do not conceal limitations. A crisp abstention with a named resolver is a product strength.
- Do not present the hypothetical pilot as an agency relationship.
- Treat `docs/implementation_plan_v5.md` sections describing free-text LLM drafting as historical. Its final amendment and the current code supersede them.
- Keep manual actions manual: Claude may prepare, inspect and verify, but cannot truthfully claim a human spoke a rehearsal, confirmed a roster or submitted a form unless that occurred and evidence exists.

## Final report template

```text
LOTLINE FINAL RELEASE REPORT

Result: READY / BLOCKED
Final local SHA:
Remote SHA:
Repository URL + logged-out visibility evidence:
Video URL + runtime + logged-out visibility evidence:
Submission confirmation:

Verification
- pytest: <count>, exit <code>
- memo sweep: <violations>/96
- outcomes: <distribution>
- integrity: <result>
- offline/browser/download checks: <evidence>
- secret scan: <result>

Scientific validation
- artifact path and evaluation command:
- cohort and denominators:
- H1–H6 verdicts (`supported within scope` / `not supported` / `inconclusive`):
- sensitivity and post-hoc ablation results:
- clean-process reproducibility result:
- principal threats and unresolved external-validity questions:

Independent review
- Housing: CLEAR/BLOCK — <evidence>
- University/data science: SCIENCE CLEAR/BLOCK — <evidence>
- Startup/investor: CLEAR/BLOCK — <evidence>

Remaining blockers
- <blocker> — owner: <person/system> — next action: <exact action> — due: <time>
```

The release is complete only when every mandatory row has evidence. “Code complete” is not the same as “submitted.”
