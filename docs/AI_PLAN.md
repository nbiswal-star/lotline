# LotLine AI plan (vetted Sun Sep 27, 01:40 ET by three independent judge reviews; code freeze 15:00 ET)

## Positioning

**Claude reads the record. Rules decide. Code verifies every AI claim.**

An analyst screening a tax-sale list spends most of their time reading unstructured public records: enforcement case notes, condemnation files, zoning board decisions and the code itself. LotLine uses Claude to do that reading. A deterministic engine still owns every score and outcome so that results are auditable. Every AI statement must quote or cite a source that code checks, and anything that fails verification is not shown. Without a key, the readers are unavailable and everything else works.

## Status of each capability

| # | Capability | What Claude does | How code verifies | Status |
|---|---|---|---|---|
| A1 | **Enforcement-record reader** | Reads every PLI violation and condemnation record for a lot (free text such as "Property is demolished. Demo permit DP-2024-13867") and extracts the items relevant to current site condition and open enforcement | Each item's quote must be an exact substring of the cited record, and its record ID and date must match. There is no free-form AI prose: summary lines are templates filled from verified items | Building |
| A2 | **Ask LotLine** (grounded Q&A) | Answers plain-language questions about a lot ("Could I build a two-family house here?", "Why is this deferred?") from engine output and stored code excerpts | Every sentence cites facts or code sections that exist. The memo checker runs on every sentence, plus new rules: permission claims must agree with the rule table, utilities/title/market claims must be cited, and no promises of approval. Out-of-scope questions are declined | Building |
| A3 | **Variance precedent reader** | Reads Zoning Board of Adjustment decision PDFs and extracts relief requested, outcome, date and rationale | Every quote is an exact substring of the decision text, and the date, district and case number appear in it. Code, not AI, matches cards to lots | Building |
| A4 | **Next-check request drafter** (stretch) | For a named next check (for example "PLI: confirm demolition for record CF-PLI-2024-060362"), drafts the email or letter the analyst would send to the named owner | Every record ID, date, address and code section in the draft must exist in the parcel's facts. Forbidden words and source selection are rejected. It is a draft only; a human sends it | Proposed |
| A5 | **Aerial-imagery observer** (stretch, higher risk) | Looks at a dated public County orthophoto of the lot and reports whether a building footprint appears | This can't be quote-verified. It would be shown only as "AI observation of a {year} aerial image, unverified", never used by the engine, and dated. Only if a public imagery source with clear terms is reachable | Proposed, needs vetting |
| A6 | **Portfolio copilot** (stretch) | Answers questions across all 14 lots ("Which lots need only a survey and title work?") | Code first filters engine results to candidate lots; Claude explains only those, with the same per-sentence verification as A2 | Proposed |
| P1 | Live snapshot drift check | None (deterministic) | A read-only comparison of the snapshot with live WPRDC | Building |
| P2 | Pre-development cost worksheet | None | Defaults are cited or left blank for the user; nothing is invented | Building |
| P3 | Outcome map | None | Offline-safe rendering | Building |

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
| | Harden verification | Quotes of at least 8 tokens aligned to clause boundaries; a guard against clipped negations; code assigns record dates and flags superseded records; the "indicates" label is checked against a keyword lexicon (disagreement drops the label); two extraction passes must agree; instruction-like quotes are rejected. |
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

**Tagline:** *LotLine's AI reads every public record on a tax-sale lot, quotes what matters, and stops analysts from spending title money on lots whose records disagree.*
