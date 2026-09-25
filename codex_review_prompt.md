# Review request: hackathon build plan "LotLine" (AI for Housing Hackathon, Pittsburgh)

You are a senior reviewer with three hats: (1) a civic tech engineer who knows Pittsburgh open data (WPRDC, City GIS) and has shipped 39 hour hackathon builds, (2) a housing practitioner who understands Pittsburgh zoning, the Land Bank and CDC for-sale development, (3) a responsible AI researcher. Your job is to find what is wrong, risky, or missing in the plan below and make it more likely to win, not to praise it.

If you have web access, verify every claim in the Fact Ledger (Section 6) and every dataset in Section 5, and cite URLs. If you cannot verify something, say "unverified" rather than guessing. Do not write application code; this is a plan review (hackathon rules forbid pre-existing code).

---

## 1. Hackathon facts (from the organizer site and participant packet)

- Event: AI Horizons 2026 "AI for Housing" Hackathon, Pittsburgh, virtual. Theme: responsible, human-centered civic AI for housing affordability.
- Timeline: kickoff Fri Sep 25, 2026. Build window Sat Sep 26 9:00am to Sun Sep 27 11:59pm ET (about 39 hours). Winners announced Oct 2.
- Tracks: College students and Startups. Teams of 1 to 5, formed on Slack. $30,000 shared by 1st/2nd/3rd in each track.
- Partners: CMU, Pitt, Penn State Invent, GraySwan (AI safety), Housing Innovation Alliance, Allegheny County Economic Development, City of Pittsburgh, PA DCED and others. Packet mentions City Planning, URA, PHFA as plausible pilot adopters.
- Rules: all code written during the event (ideas and data exploration beforehand are encouraged); libraries, open source and APIs allowed; public repo with intact commit history; keys stripped; one project per team; all AI tools disclosed.
- Submission: Google Form with description, track, 3 to 5 minute demo video ("a screen recording of the actual tool beats slides every time"; honesty about what is functional vs mocked is valued over polish), repo link, data sources, AI disclosure.
- Judging criteria: Problem Value (documented housing bottleneck); User Fit & Usability (intuitive for practitioners); Technical Execution (reliable core functionality); Data & AI Integrity (accurate sourcing, privacy, clear limitations); Actionability (supports real decisions); Continuation Potential (path to pilot adoption). Site summary: "practical, source-grounded, clear about who they help."

### Challenge 1 brief (the one we chose): Development Feasibility & Pro Forma Navigator
- Problem: older housing stock and a constrained development environment create friction for new production, especially affordable and starter homes; unclear how zoning, infrastructure and environmental factors interact.
- Users: municipal planner, small/mid developer, housing nonprofit/CDC, policy analyst.
- Required: parcel ID input (single or multi-parcel compare); a "Development Ease Score"; plain-language explanation of the biggest barriers; flags across zoning, environmental, infrastructure and policy.
- Suggested data: Allegheny County Real Estate Portal; City of Pittsburgh Zoning Code and Zoning Map; PA DEP eMapPA; Pittsburgh Dept. of City Planning GIS.
- Success: user enters a parcel ID or compares parcels and gets a source-grounded score, plain-language barrier explanation and clear flags, with Pittsburgh/Allegheny examples and documented assumptions and uncertainty. Site blurb adds "grounded in public records and approved affordability assumptions."

### Other challenges (rejected, for context)
- Challenge 2, Housing Production, Rents & Household Flow Observatory: interactive observatory of proposed/permitted/completed/lost homes, rents, household flows; every viz communicates data quality; residents contribute without exposing personal data.
- Challenge 3, Housing Typology, Equity & Climate Matchmaker: match places with housing types and tradeoffs (demand, feasibility, affordability, displacement, infrastructure, opportunity, carbon); compare 2+ scenarios, adjustable normative weights, separate data-driven vs value judgments.

---

## 2. Team and constraints

- Lead: senior applied scientist (agentic AI, LLM guardrails and evaluation), Pittsburgh resident. Likely Startup track.
- Teammates: to be recruited on Slack at kickoff; assume 3 to 4 people total with uneven skills.
- **Hard constraint: no outreach.** We cannot count on calls or quotes from the Land Bank, CDCs, URA or City staff before or during the event. Any "practitioner validation" must come from public online sources (published Land Bank policies, board materials, disposition criteria, CDC plans, news interviews) or from the event's own Slack office hours with subject matter experts (Sat and Sun 10am to 6pm ET), which may or may not happen.

---

## 3. Local context we researched (Sept 2026)

- About 5,000 tax delinquent vacant lots and 270 condemned buildings in the city's inventory; blight task force estimates $32M/year for 5 years; Land Bank funded only through 2027; sold 108 properties since 2023, owns 66 (WESA, 2026-01-15).
- Nov 2025: City, school district and County let the Pittsburgh Land Bank take priority at tax sales at about $3,000 per property (processing cost); title clearance cut from about 2 years to about 9 months; on track to sell about 80 properties per year; of 5,000 to 20,000 delinquent properties, about 1,000 need Land Bank intervention (WESA, 2025-11-20).
- Allegheny County lost 44,000 apartments under $1,000/month (2019 to 2024) and gained 13,000 over $2,000; SW PA needs 66,000+ homes; starter home supply shrinking; renovation per sq ft often exceeds new construction; Whole Home Repairs met 3% of demand (PA Capital-Star, 2026-09-16).
- Permitting under Mayor Corey O'Connor: typical BDA permit 27 days (Jul 2025) to 11 days (Jul 2026); EZ permits; virtual inspections. Remaining bottleneck: zoning relief, conditional uses needing Council hearings, codes misaligned with development patterns (PublicSource, 2026-09-23).
- Minimum lot size ordinance passed May 6, 2025: minimum lot area per unit eliminated in all residential districts; new minimums VL 6,000, L 3,000, M 2,400, H 1,200, VH 0 sq ft (Pro-Housing Pittsburgh).
- Pending zoning bill: Planning Commission on Jun 3, 2026 recommended voluntary inclusionary zoning (height/density bonus, 20 year affordability; mandatory kept in Lawrenceville, Oakland, Polish Hill, Bloomfield), by-right ADUs, elimination of parking minimums; returned to Council, needs another hearing (WESA, 2026-06-03).

---

## 4. The plan (current version after two rounds of review)

### Pitch
The Pittsburgh Land Bank can now outbid everyone at tax sales but can only clear title on about 80 properties a year out of roughly 1,000 that need it. LotLine takes the parcel list from an upcoming Sheriff or Treasurer's sale and tells staff which lots are worth a $3k bid and nine months of title work, and for what: starter home, home plus ADU, two unit, side yard, greening or hold. Each answer includes the approval path with the code section it rests on, deal killer flags and the for-sale appraisal gap. Every sentence traces to a dataset row or code section, and the approval logic is backtested against real Zoning Board of Adjustment (ZBA) cases.

### Users
Primary: Land Bank acquisition staff (bid triage). Secondary: CDCs buying from the Land Bank and small infill builders. Byproduct for planners: which code provisions block the most vacant lots.

### Must work flawlessly
1. Input: paste a sale list (Sheriff or Treasurer), or pick from a precomputed map of vacant delinquent city lots. Sheriff Sales data is keyed by address, so address to parcel matching with a reported match rate; filter out mortgage foreclosures.
2. Triage table (headline): separate "Bid decision" and "End use" columns; "Don't bid" expected to be the largest bucket, each row with reasons.
3. Fact sheet per lot, each tile tagged verified source / derived approximate / assumption, with source and as-of date: lot area, approximate frontage, zoning district (split district flag), use class, owner type only (City, Land Bank, URA, private; never names), delinquency status, last valid sale, condemned/PLI violations nearby, landslide prone overlap, FEMA flood, adjacency to other vacant/public lots, adjacent owner occupied (homestead flag), City Steps adjacency.
4. Approval path for 3 typologies (detached SFD; SFD plus ADU; two unit): by right / special exception (ZBA) / dimensional variance / use variance / rezoning. Logic = Ch. 911 use table x Ch. 903 dimensional standards (post May 2025) x substandard / nonconforming lot of record rules. Hand-encoded for 6 to 10 residential districts in demo neighborhoods, each rule cited.
5. Transparent, editable decision tree for bid and end use (e.g., conforming + clean flags + comps support value = Bid, starter home; substandard next to owner occupied home = Bid, side yard, else Hold; steep + no frontage + no steward = Don't bid, route to Adopt-a-Lot or Grounded Strategies). Decomposed Ease Score (zoning path, site, title, access) is secondary, with one weight slider panel.
6. Appraisal gap pro forma (for-sale): TDC = hard cost/sf x size (range) + soft + slope site premium + about $3k acquisition, vs value from neighborhood valid sales comps and the 80% AMI affordable price (HUD FY26 income limits). Output low/base/high gap and candidate programs marked "verify eligibility": URA Housing Opportunity Fund for-sale and homebuyer assistance, City of Bridges Community Land Trust, PHFA Keystone down payment programs.
7. Cited memo: LLM emits {claim, fact_ids[]}; a claim checker blocks unsupported numbers, unknown code sections and any status word contradicting the engine.

### Where AI does real work
- Remedy agent: for each failed constraint, chooses from a fixed catalog (dimensional variance, consolidate with adjacent public/delinquent lot, switch typology, reform scenario); the engine re-scores each; LLM selects and explains. Fallback: deterministic loop over all remedies with LLM narration only.
- ZBA backtest: 15 to 25 matched cases (new residential construction on small lots, 2025 to 26), 10 hand labeled, rest LLM extracted. Headline metric: agreement on required relief type. Disclose sampling bias (only projects that applied) and that the ZBA approves most cases. Fallback: relief type approval rates as "path difficulty context, small sample."
- Eval and red team (about 60s of video): unsupported claim rate before/after checker (30 parcels x 3 memos), status contradiction rate, human agreement on a 10 parcel golden set; prompt injection in a violation text field blocked; request for owner identity or pressure tactics refused; stale/beta data triggers "verify" language.

### Policy lenses
- Look back: May 2025 lot size reform, "N vacant delinquent lots were substandard under old minimums and conform now" (old minimums from the Dec 2024 draft legislation).
- Scenario: pending bill "if passed as recommended Jun 3, 2026": by-right ADUs and no parking minimums; report "N lots gain an income unit (ADU) path"; bonus program excluded (targets larger projects).

### Scope guardrails
City of Pittsburgh only; vacant land only (condemned structures later). Deep verification in Hazelwood, Homewood, Hill District, Beltzhoover. Cut: natural language search, citywide ranking of 5 typologies, LLM extraction of zoning tables, generic bundling, transit scoring, compare beyond 2 parcels. Slip order if behind at Sat 8pm: remedy agent LLM planning, then weight sliders, then frontage length; never cut claim checker, golden set or backtest core. Freeze demo parcels Sun 12:00.

### Schedule (4 people: Data, Rules, Frontend, AI/Eval)
- Before Sat (data exploration only, no code): download datasets; read Ch. 903/911 and pick districts; collect ZBA decision URLs and agendas by hand; pick a real recent Hazelwood sale list; draft the 10 parcel golden set; recruit on Slack.
- Sat 9 to 13: joins on PIN; hand encode rules; UI shell (Streamlit + pydeck unless FE fluent in Next/deck.gl); fact schema.
- Sat 13 to 20: flags, comps; engine + 15 unit tests; parcel page; claim checker; ZBA extraction.
- Sat 20 to Sun 2: decision tree + triage table; pro forma; remedy loop; policy lens precompute; eval set.
- Sun 9 to 15: SME office hours if available; hand check parcels; real/approximate/mocked panel; backtest numbers.
- Sun 15 to 19: code freeze, README (sources, AI disclosure, limitations), record video. Sun 19 to 23:59: buffer, submit.

### Demo (4 min screen recording)
0:00 hackathon name + team; problem (1,000 need intervention, 80 sales/yr). 0:30 paste Hazelwood sale list: match rate, triage bid 7 / don't bid 18 with reasons. 1:15 one lot: facts with tags, approval path with sections, flags, gap band + programs. 2:00 failed two unit case: remedies re-scored. 2:30 May 2025 look back number + ADU scenario. 3:00 ZBA backtest, claim checker metrics, red team clip. 3:40 real/approximate/mocked, pilot next steps.

---

## 5. Datasets and known gotchas (please verify)

| Dataset | Notes |
|---|---|
| WPRDC Allegheny County Property Assessments | PARID (16 chars), LOTAREA, CLASS, USEDESC, OWNERDESC, HOMESTEADFLAG, sale fields; no zoning, no frontage; ~415 MB CSV; filter to city MUNICODE; date format differs CSV vs API |
| County parcel boundaries (WPRDC/PASDA) | PIN = PARID after normalizing; PA State Plane South (ft); frontage must be derived from geometry |
| City zoning layer (WPRDC / pghgishub) | beware a Pittsburg, CA layer in search results; centroid in polygon, flag split parcels |
| Zoning code on ecode360 (Title Nine) | Ch. 903 tables extractable; Ch. 911 use table; lot of record rules; Ch. 925 contextual setbacks not computable; confirm codified post May 2025 text |
| City of Pittsburgh Property Tax Delinquency (WPRDC) | weekly, by PIN, no names; primary delinquency source |
| County Tax Liens (WPRDC) | beta, false positives, possible staleness; secondary only |
| Sheriff Sales (WPRDC) | monthly, keyed by address, includes mortgage foreclosures |
| Treasurer's Sales (City) | listed in Pittsburgh Legal Journal; format unknown |
| Property sales, PLI violations, condemned properties | address to parcel join messy |
| Landslide Prone Areas, Landslides, FEMA NFHL | flags only |
| City Steps / street centerlines | frontage heuristic, 3h timebox |
| PASDA / DEP mine maps | "mapped workings nearby: verify" only if loaded by Sat noon |
| HUD FY26 income limits (Pittsburgh HMFA) | hardcode with citation |
| ZBA decisions and agenda PDFs (pittsburghpa.gov) | decision template is regular; no URL pattern; listing pages script rendered; collect URLs by hand |

---

## 6. Fact ledger (verify each; mark Confirmed / Wrong / Unverified with URL)

1. Land Bank priority bidding at ~$3k/property; title ~9 months; ~80 sales/yr; ~1,000 need intervention.
2. ~5,000 tax delinquent vacant lots in city inventory (exact phrasing and whether it mixes City owned with delinquent).
3. May 6, 2025 lot size ordinance numbers and elimination of lot area per unit; whether it is codified in current ecode360 Ch. 903.
4. Two unit dwellings are not permitted in R1D/R1A (so a duplex there needs a use variance or rezoning), and are permitted in R2 and above. Which of these are by right vs special exception vs conditional use.
5. What the substandard / nonconforming lot of record rules say for building a single family home on a 20 to 25 ft lot of record.
6. Whether ADUs are currently permitted anywhere by right, and exactly what the pending bill would change.
7. Pittsburgh Land Bank side yard program exists and its eligibility rules; City side yard program.
8. Adopt-a-Lot (City) and Grounded Strategies as greening routes.
9. URA Housing Opportunity Fund for-sale development and homebuyer assistance programs; City of Bridges CLT; PHFA Keystone programs: exist, and eligibility at 80% AMI.
10. WPRDC Sheriff Sales dataset: keyed by address, includes mortgage foreclosures, update frequency, whether it covers upcoming sales or only past.
11. Treasurer's Sale lists for the City of Pittsburgh: where published and in what format.
12. HOMESTEADFLAG exists in the assessment data.
13. ZBA approves most cases it hears (any published stats).
14. HUD FY26 income limit for 80% AMI in the Pittsburgh HMFA (household of 3 and 4).
15. Realistic hard cost per sq ft and total development cost for new infill starter homes in Pittsburgh CDC projects, and typical appraisals in Hazelwood / Homewood (any public source: news, URA board docs, CDC reports).

---

## 7. What we want from you

Answer in this structure, concise and high signal:

1. **Verdict:** keep, modify, or replace. Probability of top 3 in the Startup track as written and after your changes.
2. **Scores 1 to 10** on the six judging criteria, with one line of reasoning each.
3. **Fatal or serious flaws** (factual, legal/zoning, data, scope, ethics), ranked, each with a concrete fix.
4. **Fact ledger results** (table: item, status, correct fact, source URL).
5. **Dataset reality check:** anything that breaks the plan, plus the exact resource URL or API endpoint you would use for each core dataset.
6. **Replacing practitioner outreach:** since we cannot contact anyone, list the best public sources that stand in for a practitioner voice (Land Bank published acquisition/disposition policy, board minutes, strategic plan, task force report, CDC neighborhood plans, news interviews with quotes on bid criteria) and how to cite them in the video and README.
7. **Scope for 39 hours with 3 to 4 people:** what to cut or simplify further; the single demo path that must never fail; any schedule changes.
8. **AI integrity:** is the LLM role meaningful? Improvements to the claim checker, eval metrics and red team demo that a GraySwan judge would reward.
9. **Pre-event checklist** (data exploration only, no code): an ordered list of what to download, read, and hand-label before Saturday 9am.
10. **Anything we are not seeing:** a sharper framing, a missing user, a better demo moment, or a competing team's likely approach we should differentiate from.
