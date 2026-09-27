# Submission form payload (draft; the team owner verifies and submits)

The form link is in the official participant packet and in Slack. It closes **Sun Sep 27, 2026, 23:59 ET**, with no extensions. The fields below follow the packet's "How to Submit" table. Bracketed items must be confirmed by a human; Claude or Codex must not fill them in or attest to them.

| Field | Entry |
|---|---|
| Team name | [CONFIRM] LotLine |
| Members (name, email, affiliation) | [CONFIRM every member who actually participated; the rules require every listed member to participate.] Presenter on the video: Nibedita Biswal. Repository commits: Nibedita Biswal (nbiswal@andrew.cmu.edu) |
| Track / challenge | Startup track · Challenge 1: Development Feasibility & Pro Forma Navigator |
| Project title | LotLine: a development feasibility navigator that catches conflicting public records before anyone acts on a tax-sale lot |
| Demo video | [PASTE public/unlisted URL; check it plays logged out] |
| Public repository | https://github.com/nbiswal-star/lotline ([CONFIRM the repo is public and loads logged out]) |
| Attestation | [TEAM OWNER ONLY] Everyone is 18+ and no code predates kickoff (Sat Sep 26, 09:00 ET). Commit history starts 12:06 ET Sep 26 after two disclosed data-only prep commits (Sep 24) |

## Project description (paste)

**What it does.** LotLine screens the vacant lots in a real, dated Pittsburgh City Treasurer Sale (October 2, 2026).

- **Reconciliation.** It reconciles the open-data sale list (96 records) with the City's official advertisement (77) by parcel ID, and cross-checks every opening bid (77/77).
- **Routing.** It routes 63 structures out of the vacant-land model and screens the 14 advertised vacant lots.
- **The packet.** Enter a parcel ID, or pick from a triage board, and LotLine produces a cited screening packet containing:
  - a transparent Development Ease score (0–6, always shown with its use, dimensional and environmental components, and as a range when corner status is unknown);
  - a separate evidence-coverage measure;
  - zoning, environmental, infrastructure and acquisition-route flags;
  - plain-language barriers;
  - next checks, each routed to the named human who resolves it (surveyor, title examiner, Zoning Administrator, PLI, geotechnical engineer).
- **Refusing to score.** When public records disagree in a way that changes the decision, LotLine refuses to score. For example, one "vacant" lot is 1,672 sf in the assessment and 4,305 sf in County GIS, on either side of its 2,400 sf zoning minimum, and still has an active condemned case attached.
- **The AI boundary.** A deterministic engine makes every decision. Claude reads unstructured enforcement histories and proposes exact event-bearing passages; code checks the source ID, field, recorded date, quote and supported semantic label, and neutrally notes later-dated records without treating them as superseding. Claude also maps questions to fixed frames, engine-authored claim IDs and verbatim code excerpts—never model-written prose. None of these outputs can change a score, conflict, outcome or next check. The app's deterministic screening and cited memo remain available offline.
- **The multimodal cross-check.** For all 96 sale-feed parcels, a real aerial is overlaid with the target County parcel polygon and hash-bound to a cached Claude read. Claude returns only fixed categories for visible footprint, cover, street context and image quality. Code compares them with verified dated records and the assessment class. The current full-cohort run yielded 36 assessment-structure/no-visible-footprint human-review flags and 45 abstentions. Across two consecutive runs, exact categories agreed on 93/96 parcels and the same 29 structure-routed records were flagged. The imagery date is unavailable and visual absence is not proof; visual output never changes the engine.

**Who it's for.** Public-interest acquisition analysts at a land bank, the URA, a CDC or a City agency. They screen tax-sale lists before committing title and survey money.

**Problem scale.** A reproducible exact-ID join of current public snapshots finds 536 Pittsburgh parcels in both the County's 22,354-parcel vacant-assessment set and the City's 2,895 unique active-condemned IDs. This is a records-overlap count, not a present-site or unsafe-building determination.

**Results on the October 2 sale.** Of 14 advertised vacant lots:
- 7 advance to staff review, each with named checks;
- 3 are refused because their records conflict;
- 3 Hillside lots need a survey first;
- 1 is not zoned for housing.

A retrospective internal validation is in `docs/scientific_validation.md`. In a balanced 150-parcel development sample checked against a structured City-record proxy, the frozen one-pass AI reader made 0/75 demolition assertions discordant with the active-condemned/no-demolition-permit stratum, versus 15/75 for the highest-F1 pre-call simple rule (B4). A post-hoc contextual deterministic rule (B5) reduced that to 2/75 and had higher F1 than AI (.625 versus .571). The result supports a conservative precision tradeoff—not LLM necessity or overall superiority. This is a development-set estimate of one derived rule, not a benchmark, present-site determination, predictive claim or measured time saving.

**What we'd build next.** A hypothetical per-sale-cycle license for a Land Bank or URA acquisitions team, with subsidized CDC access. The untested pricing hypothesis is $2,500 per agency sale cycle and $500 for a CDC. A pilot would measure analyst hours to shortlist and title/survey dollars not yet committed on lots with unresolved conflicts. Then come Sheriff Sale lists, a structures model, and a prospectively frozen comparison with practitioner screening. No agency affiliation, willingness to pay or savings is claimed.

## Data sources (paste)

These are the public sources, with snapshot dates:

- WPRDC City Treasury Sales (pulled 2026-09-24)
- City of Pittsburgh "Available for Auction as of 9/16/2026" advertisement
- Treasurer Sale regulations for the 10/2/2026 sale
- Second Class City Treasurer's Sale and Collection Act (Act 171 of 1984)
- Allegheny County assessments (ASOFDATE 2026-09-01)
- Allegheny County parcels via PASDA ("Parcels 20260921")
- Allegheny County OPENDATA parcel outlines and Esri World Imagery (retrieved 2026-09-27; imagery acquisition date unavailable)
- City delinquency, PLI violations and condemned properties (WPRDC, 2026-09-24)
- City GIS zoning, 25%+ slope, undermined, landslide-prone, historic and RCO layers (2026-09-24)
- FEMA National Flood Hazard Layer
- Pittsburgh Zoning Code (ecode360, current through 2026-09-16): Ch. 903, 904, 905, 906, 911, 915, 921 and 925
- Ord. No. 10-2025 (minimum lot sizes)
- ZBA decisions: Kendall St, Rockland Ave
- Pittsburgh Land Bank Task Force report (Jan 2026)

Full identifiers are in the README.

## AI tool disclosure (paste)

- **Claude Code (Anthropic).** Coding assistant during the build window, including multi-agent build and review.
- **OpenAI Codex.** Plan review and restructuring of the prepared CSVs before kickoff (data preparation only), plus implementation and handoff work during the build window.
- **Claude API (claude-opus-5), at runtime and optional.** It performs bounded extraction from enforcement/ZBA documents, question-to-verified-atom selection, and memo claim ordering. Exact quotes and identifiers are rechecked; unsupported semantics are withheld; the engine is isolated from model output. Verified caches support the demo offline.
- All scoring, routing, conflict detection and next checks are deterministic Python, not AI output.

## Limitations (paste if a field allows)

- Decision support only; not legal, title, survey, financial, appraisal or zoning advice.
- One dated sale. Vacant lots only; structures are routed out.
- Contextual setbacks, utilities, legal access, title, market demand and appraisal are not evaluated; each is a named next check.
- Screening map layers are not determinations.
- RIV-RM base dimensions and an approximate 125-foot riparian screen are modeled; a surveyor and Zoning Administrator must confirm the §905.04.E river-edge line.
- The 15-parcel label set is team-authored. It measures conformance to our own specification, not accuracy.
- Upstream data extraction was ad hoc before the event and is not reproducible from the repository.
