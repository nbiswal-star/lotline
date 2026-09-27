# LotLine demo video script (target 4:10–4:20; hard limits 3:00–5:00)

Record the real app at 1280×800 with `uv run streamlit run app.py`. The main take uses live Claude actions after the pre-flight smoke test; every result remains checker-gated and falls back automatically to a cached, re-verified result. Record a separate offline-proof clip with `LOTLINE_OFFLINE=1`. Every scene must have a fallback screenshot or clip in `docs/fallback/`, and any fallback state must remain visibly labeled.

Scene numbers (§) are referenced in the rehearsal log.

| # | Time | Screen | Voice-over (read at a calm pace) |
|---|---|---|---|
| 0 | 0:00–0:10 | Title card: "LotLine · AI Horizons 2026 AI for Housing Hackathon · Challenge 1: Development Feasibility Navigator · Team: Nibedita Biswal & Premics" | "This is LotLine, built by Nibedita Biswal for the AI Horizons 2026 AI for Housing Hackathon, Challenge 1." |
| 1 | 0:10–0:35 | Title card stays on screen (intro for judges) | "Before the demo: LotLine is a screening assistant for public-interest housing teams. It reconciles the City's tax-sale list with open data, screens each vacant lot against cited zoning and hazard rules, and uses Claude to read enforcement records and aerial images, with code verifying every AI claim. When records conflict, it withholds a score and names who resolves it." |
| 2 | 0:35–0:53 | Pipeline view, top | "Pittsburgh's open-data feed lists 96 parcels for this sale cycle, while the City advertisement lists 77. An acquisition analyst has days to decide which of those records deserve title and survey money—and the record systems often disagree." |
| 3 | 0:53–1:33 | Centre packet: AI record reader, then multimodal cross-check | "This is why the AI is here. Claude proposes event-bearing passages from years of enforcement text; code verifies every ID, date, field, quote and semantic label. Below that is real aerial context with the County parcel outlined—not a placeholder. This works for all 96 records, not just this demo. Claude is restricted to four visual categories. Here it says structure visibility is unclear, so the image does not resolve the demolition note against the Active condemned record. AI connects modalities and exposes uncertainty. It does not decide the parcel." |
| 4 | 1:33–2:07 | Centre conflict banners and score | "The rules still refuse to score. Assessment area is 1,672 square feet and County GIS is 4,305; the 2,400-square-foot zoning minimum lies between them. The condemned list still records an Active status. LotLine shows both sources, withholds the result, routes area reconciliation to County Real Estate and a licensed surveyor, and routes current-condition verification to PLI plus a site visit. Without AI, the decision is equally cautious—but the analyst must open and interpret every keyword hit to find the evidence." |
| 5 | 2:07–2:32 | Pipeline → triage board (leave the optional map collapsed) | "Across the sale, 77 of 77 advertised records reconcile by parcel ID and price. Sixty-three structures leave this vacant-land workflow. Of 14 vacant lots, seven advance to staff review, three are withheld for record conflicts, three need site or survey evidence, and one has no housing use under this screening policy. This is triage, not ranking." |
| 6 | 2:32–3:07 | Benezet packet → Ask LotLine | "On Benezet Street, ask whether a two-family house is permitted. Claude interprets the question, but it cannot write the answer. It selects a fixed answer frame, engine-authored claim IDs and an exact code excerpt; the server renders and verifies every sentence, then routes permission questions to the Zoning Administrator. Ask whether this is a good investment, and it declines. In a scripted live smoke run, all twelve demo questions on Benezet and Centre were answered or safely declined; all five adversarial or out-of-scope requests were rejected or declined." |
| 7 | 3:07–3:43 | Integrity view: problem scale, text AI delta, then multimodal delta | "This is not isolated: an exact record join finds 536 Pittsburgh parcels both assessed vacant and actively condemned—records overlap, not site truth. Across all 96 sale records, the current imagery run produced 36 review flags and 45 abstentions; the same 29 structure-routed records were flagged twice. No outcome changed. In a separate 150-parcel sample, AI made zero proxy-discordant assertions versus fifteen for the best pre-call rule, but a post-hoc rule had higher F1. That shows bounded precision and a new review signal—not accuracy or improved decisions." |
| 8 | 3:43–4:17 | Pilot slide / README limitations | "The proposed buyer is a Land Bank or URA acquisitions team on a per-sale-cycle license, with subsidized CDC access. Our untested price hypothesis is twenty-five hundred dollars per agency sale cycle and five hundred for a CDC. A pilot measures analyst hours to shortlist and title or survey dollars not yet committed on unresolved lots. LotLine's thesis is simple: let AI read messy records, let deterministic policy abstain, and let accountable people resolve what the data cannot." |

## Rules for the recording

- Never say "buildable", "clear", "safe", "will be sold", or "best lot". Say "apparent lower-discretion zoning path", "no overlap in the checked screening layers", and "advertised for the October 2 sale".
- Don't show Saline St or Kemper St (Parks district; they carry an open-space designation check). They are in the app and README, not the video.
- If the live Claude call fails on camera, keep rolling: the fallback is part of the product. Say "and when the model is unavailable, the deterministic memo is shown."
- Leave the optional parcel map collapsed. The recorded workflow uses the triage table so basemap/WebGL rendering cannot distract from the decision path.
- Show the Decision-support banner at least once in frame, and keep the snapshot dates visible in the header.
- Total runtime must stay between 3:00 and 5:00. Rehearse twice and log the times below.

## Rehearsal log

| Take | Date/time | Runtime | Notes |
|---|---|---|---|

## Verified fallback assets

The 1280×800 app captures were opened and checked on 2026-09-26: `00-title.png`, `01-pipeline.png`, `02-benezet.png`, `02b-benezet-checks.png`, `03-centre.png`, `04-compare.png`, `05-integrity.png`, `06-memo.png`, and `07-pilot.png`. See `docs/fallback/README.md` for the frame-by-frame manifest. These assets do not replace the two timed spoken rehearsals required above.
