# LotLine AI plan (vetted Sun Sep 27, 01:40 ET by three independent judge reviews; code freeze 15:00 ET)

## Positioning

**Claude reads the record. Rules decide. Code verifies source identity and every displayed quote.**

An analyst screening a tax-sale list spends most of their time reading unstructured public records: enforcement case notes, condemnation files, zoning board decisions and the code itself. LotLine uses Claude to do that reading. A deterministic engine still owns every score and outcome so that results are auditable. Every AI statement must quote or cite a source that code checks, and anything that fails verification is not shown. Without a key, the readers are unavailable and everything else works.

## Status of each capability

| # | Capability | What Claude does | How code verifies | Status |
|---|---|---|---|---|
| A1 | **Enforcement-record reader** | Searches loaded PLI, condemnation and permit text and proposes passages relevant to current condition and enforcement | Model-proposed tuples recur across two runs; IDs, fields, recorded dates and exact quotes are checked; unsupported semantics are withheld; deterministic structured companions are labeled by design | **Complete; development audit only** |
| A2 | **Ask LotLine** (grounded Q&A) | Maps plain-language questions to fixed frames, engine claims and stored code excerpts | No model prose reaches users; permission claims must agree with rules; unsupported topics are declined | **Complete; 12+5 live smoke** |
| A3 | **Variance precedent reader** | Reads selected ZBA decisions and extracts relief, outcome, date and rationale | Exact quotes and metadata are checked; relief-kind patterns are checked; code matches cards to lots | **Secondary; 6/8 usable, not predictive** |
| A4 | **Internal next-check ticket** | None; deterministic template attaches verified evidence to the engine's named owner | No outgoing message; identifiers come from engine/evidence output | **Complete, deterministic** |
| A5 | **Aerial-imagery observer** | — | Cut because the observation could not be adequately verified | **Cut** |
| A6 | **Portfolio copilot** | — | Cut because deterministic triage is clearer for 14 lots | **Cut** |
| P1 | Live snapshot drift check | None (deterministic) | A read-only comparison of the snapshot with live WPRDC | **Complete** |
| P2 | Pre-development cost worksheet | None | Defaults are cited or left blank for the user; nothing is invented | **Complete** |
| P3 | Outcome map | None | Offline-safe rendering | **Complete** |

## Evidence the AI adds value (to be measured, not asserted)

- The number of records read per lot, and time-to-evidence (seconds, compared with manual lookup across the PLI and condemned datasets).
- For each conflict lot, whether the reader surfaced the decision-relevant record (for Centre 10-S-5, the 2025 demolition finding).
- Verification pass and reject counts for every reader (reported as raw n/N).
- Adversarial results: injected text in records, fabricated quotes, permission inversions and unsupported topics all rejected (n/N).

## Non-negotiables

The engine is never changed by AI output. There is no AI prose without verification. Cached AI outputs are re-verified on load, and none are fabricated when no key is available. Every AI panel says what it is and what it is not. The forbidden words stay forbidden.

## Vetting outcome (housing-practice, responsible-AI and investor reviews)

| Item | Decision | Reason |
|---|---|---|
| A1 Enforcement-record reader | **Keep. This is the headline.** | All three reviewers. |
| | Harden verification | Quotes of at least 8 tokens aligned to clause boundaries; a guard against clipped negations; code assigns recorded dates and neutrally notes later-dated records; the "indicates" label is checked against a keyword lexicon (absence or disagreement withholds the label); model-proposed tuples must recur across two runs; instruction-like quotes are rejected. |
| | Cross-check demolition claims | Checked in code against the WPRDC PLI permits data. |
| | Wording | Always "the record says", never "the site is". |
| | Measure against a baseline | Recall against pre-run team labels, compared with a no-AI keyword baseline. |
| A2 Ask LotLine | **Change: no model prose.** | Claude understands the question and selects verified atoms (engine claim IDs, verbatim code quotes) into fixed answer frames. Permission answers always route to the Zoning Administrator. Out-of-scope questions get a categorized decline. The prose checker stays as defense in depth, because prose checkers leak. |
| A3 Variance precedents | **Keep, narrowed.** | Case number, date, relief kind and a verbatim outcome sentence. Honest granted/decided counts, with their denominator. |
| New: required-relief paths | **Add.** | The brief asks for "required variances". Code derives the trigger from the engine, a deterministic table gives the path, Claude selects the supporting code quote (verified), and precedents attach. |
| A4 Request drafter | **Change to an internal task ticket.** | Templated and deterministic, with the verified evidence attached. Not outgoing mail. |
| A5 Aerial observer, A6 Portfolio copilot | **Cut.** | A5 can't be verified and is misleading. A6 is a filter, and a table beats a chatbot for 14 lots. |
| P2 Cost worksheet | **Make it sale-specific.** | Surviving liens and water claims, redemption risk, quiet title, survey, demolition lien. No filler rows. |
| Video | **Lead with the AI reading Centre's records.** | Show the verified quote, then the rules refusing to score, then the next check; show a deliberate rejection; keep live Q&A scripted. |

**Tagline:** *Claude searches loaded enforcement histories and surfaces quote-grounded conflict evidence before analysts decide whether to begin paid diligence.*
