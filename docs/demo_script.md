# LotLine demo video script (target 3:45–3:55; hard limits 3:00–5:00)

Record the real app at 1280×800 with `uv run streamlit run app.py`. Keep the deterministic path offline; show a live or cached Claude assembly only after it has passed the checker on both demo parcels. Every scene must have a fallback screenshot or clip in `docs/fallback/`. If a cached assembly is used, leave its on-screen label in frame.

Scene numbers (§) are referenced in the rehearsal log.

| # | Time | Screen | Voice-over (read at a calm pace) |
|---|---|---|---|
| 0 | 0:00–0:10 | Title card: "LotLine · AI Horizons 2026 AI for Housing Hackathon · Challenge 1: Development Feasibility Navigator · Nibedita Biswal" | "This is LotLine, built by Nibedita Biswal for the AI Horizons 2026 AI for Housing Hackathon, Challenge 1." |
| 1 | 0:10–0:30 | Pipeline view, top | "Pittsburgh advertises tax-delinquent properties for an October 2 Treasurer Sale. The open-data feed lists 96 parcels, but the City advertises 77. An acquisition analyst at a land bank or CDC has days, not weeks, to decide which lots deserve title and survey money." |
| 2 | 0:30–0:50 | Funnel → triage board | "LotLine reconciles the two lists by parcel ID and checks every opening bid: 77 of 77 match. It routes 63 structures out of the vacant-land model and screens the 14 vacant lots. Seven advance to staff review. Three it refuses to score, because the public records conflict. Three need a survey first. One isn't zoned for housing. This is triage, not a ranking; staff decide." |
| 3 | 0:50–1:40 | Benezet packet (131-N-31): score card, four tiles, next checks | "Here's a record-consistent screening example: no decision-changing conflict was found in the checked records. Benezet Street scores 5 to 6 of 6. Use is permitted by right, and there's no overlap in the hazard layers we checked. It's a range, not one number, because we can't confirm whether it's a corner lot, and a corner lot's setbacks would shrink the envelope to about 14 feet. Every score shows its components and its sources. The packet starts with a current-sale check before anyone incurs costs, then names who verifies the corner, title and Treasurer Sale terms. Liens and water claims survive this sale, and there's a 90-day redemption period. This is not a recommendation to buy." |
| 4 | 1:40–2:35 | Centre Ave packet (10-S-5): red and amber banners, provenance drawer | "Now the reason LotLine exists. Centre Avenue is 1,672 square feet in the assessment and 4,305 in County GIS, and the zoning minimum of 2,400 falls between them. The assessment also calls it vacant, while an active condemned case is still attached to it. A tool that ranks whatever field it loads first would score this lot. LotLine won't choose between the records. It shows both, holds the parcel out of scoring, and routes it to deed reconciliation, a PLI site check, and a possible lot-of-record path under §921.04.A." |
| 5 | 2:35–2:55 | Compare Benezet vs Michigan 15-S-66 | "Two lots that look alike, both advancing. The difference is that Michigan overlaps the slope and undermining layers, so its environment score drops and a geotechnical and mine-subsidence review goes to the top of its list." |
| 6 | 2:55–3:35 | Integrity view, then the memo panel on Benezet | "The engine decides; Claude assembles; the checker enforces. Claude can only select and order approved claim IDs—it cannot submit prose, scores, citations, checks or owners. On this offline run, the cited deterministic memo is shown. A planted sentence that picks the GIS source is rejected, and injected source text changes nothing. Ten of ten red-team and regression cases pass. The engine, checker and fallback all run offline." |
| 7 | 3:35–3:55 | README / limitations and pilot slide | "What's real: every parcel value, from public sources, dated. What's approximate: envelope geometry. What's synthetic: only the red-team inputs. Next, a pilot with a Land Bank or CDC acquisitions team, refreshing the snapshot before each Treasurer Sale, then Sheriff Sale lists and structures. Every packet ends in a named next check, not just a score." |

## Rules for the recording

- Never say "buildable", "clear", "safe", "will be sold", or "best lot". Say "apparent lower-discretion zoning path", "no overlap in the checked screening layers", and "advertised for the October 2 sale".
- Don't show Saline St or Kemper St (Parks district; they carry an open-space designation check). They are in the app and README, not the video.
- If the live Claude call fails on camera, keep rolling: the fallback is part of the product. Say "and when the model is unavailable, the deterministic memo is shown."
- Show the Decision-support banner at least once in frame, and keep the snapshot dates visible in the header.
- Total runtime must stay between 3:00 and 5:00. Rehearse twice and log the times below.

## Rehearsal log

| Take | Date/time | Runtime | Notes |
|---|---|---|---|
