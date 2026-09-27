# LotLine demo video script (target 3:45–3:55; hard limits 3:00–5:00)

Record the real app at 1280×800 with `uv run streamlit run app.py`. Keep the deterministic path offline; show a live or cached Claude assembly only after it has passed the checker on both demo parcels. Every scene must have a fallback screenshot or clip in `docs/fallback/`. If a cached assembly is used, leave its on-screen label in frame.

Scene numbers (§) are referenced in the rehearsal log.

| # | Time | Screen | Voice-over (read at a calm pace) |
|---|---|---|---|
| 0 | 0:00–0:10 | Title card: "LotLine · AI Horizons 2026 AI for Housing Hackathon · Challenge 1: Development Feasibility Navigator · Nibedita Biswal" | "This is LotLine, built by Nibedita Biswal for the AI Horizons 2026 AI for Housing Hackathon, Challenge 1." |
| 1 | 0:10–0:28 | Pipeline view, top | "Pittsburgh's open-data feed lists 96 parcels for this sale cycle, while the City advertisement lists 77. An acquisition analyst has days to decide which of those records deserve title and survey money—and the record systems often disagree." |
| 2 | 0:28–1:08 | Centre packet: AI record reader first; expand AI vs no-AI | "This is why the AI is here. Centre Avenue has years of enforcement notes, permits and condemnation records. Claude reads that changing free text and proposes the passages that matter. Code accepts only matching record IDs, dates, fields and exact source quotes, and an exact evidence tuple must recur in two model runs. The January PLI note states that a demolition permit was issued, the property is demolished, and the case was withdrawn. Permits data records the cited permit as Issued but carries no final-inspection date. A keyword scan finds all seven records; the verified reader narrows them to five and gives the analyst dated quotes. AI finds evidence. It does not decide the parcel." |
| 3 | 1:08–1:42 | Centre conflict banners and score | "The rules still refuse to score. Assessment area is 1,672 square feet and County GIS is 4,305; the 2,400-square-foot zoning minimum lies between them. The condemned list still records an Active status. LotLine shows both sources, withholds the result, routes area reconciliation to County Real Estate and a licensed surveyor, and routes current-condition verification to PLI plus a site visit. Without AI, the decision is equally cautious—but the analyst must open and interpret every keyword hit to find the evidence." |
| 4 | 1:42–2:07 | Pipeline → triage board/map | "Across the sale, 77 of 77 advertised records reconcile by parcel ID and price. Sixty-three structures leave this vacant-land workflow. Of 14 vacant lots, seven advance to staff review, three are withheld for record conflicts, three need site or survey evidence, and one has no housing use under this screening policy. This is triage, not ranking." |
| 5 | 2:07–2:42 | Benezet packet → Ask LotLine | "On Benezet Street, ask whether a two-family house is permitted. Claude interprets the question, but it cannot write the answer. It selects a fixed answer frame, engine-authored claim IDs and an exact code excerpt; the server renders and verifies every sentence, then routes permission questions to the Zoning Administrator. Ask whether this is a good investment, and it declines. In a scripted live smoke run, all twelve demo questions on Benezet and Centre were answered or safely declined; all five adversarial or out-of-scope requests were rejected or declined." |
| 6 | 2:42–3:18 | Integrity view and validation table | "The scientific result is bounded. On a team-labeled development audit of 21 records across three conflict parcels, the verified reader surfaced all 12 labeled relevant records and no irrelevant ones. The no-AI keyword scan found the same 12 plus nine irrelevant records. That is retrospective internal conformance, not general accuracy or proof of time saved. Missing-value tests produced zero advances in 105 injections, and model behavior changed zero engine decisions." |
| 7 | 3:18–3:52 | Pilot slide / README limitations | "The next study is a blinded, parcel-level comparison against a strong recency and text-retrieval baseline, labeled by two practitioners. The proposed one-sale pilot measures analyst hours, critical conflicts found before paid diligence, and accepted packets with complete owners and next checks. LotLine's thesis is simple: let AI read messy records, let deterministic policy abstain, and let accountable people resolve what the data cannot." |

## Rules for the recording

- Never say "buildable", "clear", "safe", "will be sold", or "best lot". Say "apparent lower-discretion zoning path", "no overlap in the checked screening layers", and "advertised for the October 2 sale".
- Don't show Saline St or Kemper St (Parks district; they carry an open-space designation check). They are in the app and README, not the video.
- If the live Claude call fails on camera, keep rolling: the fallback is part of the product. Say "and when the model is unavailable, the deterministic memo is shown."
- Show the Decision-support banner at least once in frame, and keep the snapshot dates visible in the header.
- Total runtime must stay between 3:00 and 5:00. Rehearse twice and log the times below.

## Rehearsal log

| Take | Date/time | Runtime | Notes |
|---|---|---|---|

## Verified fallback assets

The 1280×800 app captures were opened and checked on 2026-09-26: `00-title.png`, `01-pipeline.png`, `02-benezet.png`, `02b-benezet-checks.png`, `03-centre.png`, `04-compare.png`, `05-integrity.png`, `06-memo.png`, and `07-pilot.png`. See `docs/fallback/README.md` for the frame-by-frame manifest. These assets do not replace the two timed spoken rehearsals required above.
