"""Plain-language display copy. Labels and glosses only; no decisions."""

from __future__ import annotations

from lotline.models import Outcome

APP_NAME = "LotLine"
PITCH = (
    "A development feasibility navigator for public-interest teams screening "
    "tax-sale lots: it catches conflicting public records before anyone acts on them."
)
DECISION_SUPPORT = (
    "Decision support only — not legal, financial, title, survey or zoning advice. "
    "Every result ends in named human checks."
)
OFFLINE_BADGE = "Runs offline · frozen public-records snapshot"

# Outcome groups for the triage board, in display order (not a ranking).
OUTCOME_ORDER: tuple[Outcome, ...] = (
    Outcome.ADVANCE,
    Outcome.DEFER_SITE,
    Outcome.DEFER_RECORDS,
    Outcome.DO_NOT_ADVANCE,
    Outcome.SIDE_YARD,
    Outcome.OUT_OF_UNIVERSE,
    Outcome.STRUCTURE,
)

OUTCOME_SHORT: dict[Outcome, str] = {
    Outcome.ADVANCE: "Advance to staff review",
    Outcome.DEFER_SITE: "Defer: site conditions unknown",
    Outcome.DEFER_RECORDS: "Defer: missing or conflicting records",
    Outcome.DO_NOT_ADVANCE: "Do not advance (housing)",
    Outcome.SIDE_YARD: "Side yard / stewardship (not evaluated)",
    Outcome.OUT_OF_UNIVERSE: "Routed: not in City advertisement",
    Outcome.STRUCTURE: "Routed: structure",
}

OUTCOME_MEANING: dict[Outcome, str] = {
    Outcome.ADVANCE: (
        "A housing use is permitted, no critical record conflict was found, and lot area "
        "meets the district minimum in every source. This is an apparent lower-discretion "
        "zoning path worth staff time. It is not a finding that the lot is buildable and "
        "not an acquisition recommendation."
    ),
    Outcome.DEFER_RECORDS: (
        "Public records conflict, or the district's rules are not encoded in LotLine yet. "
        "LotLine will not score through that gap; resolve the records first."
    ),
    Outcome.DEFER_SITE: (
        "Housing is allowed in this district, but a site standard depends on a survey. "
        "Further screening waits on site information."
    ),
    Outcome.DO_NOT_ADVANCE: (
        "Neither single-unit nor two-unit housing is permitted in this district under the "
        "stated screening policy. Other reuse may still be possible."
    ),
    Outcome.SIDE_YARD: "Not evaluated: requires Land Bank ownership and adjacent-owner data not in v1.",
    Outcome.OUT_OF_UNIVERSE: (
        "Listed in the open-data Treasury feed but not in the City advertisement dated "
        "9/16/2026, so it is outside this sale as advertised."
    ),
    Outcome.STRUCTURE: (
        "The assessment record indicates a building. LotLine's vacant-land model does not "
        "apply; route to structure-specific review."
    ),
}

# Badge tone per outcome: "good" (green), "caution" (amber), "neutral" (grey).
OUTCOME_TONE: dict[Outcome, str] = {
    Outcome.ADVANCE: "good",
    Outcome.DEFER_SITE: "caution",
    Outcome.DEFER_RECORDS: "caution",
    Outcome.DO_NOT_ADVANCE: "neutral",
    Outcome.SIDE_YARD: "neutral",
    Outcome.OUT_OF_UNIVERSE: "neutral",
    Outcome.STRUCTURE: "neutral",
}

TRIAGE_NOTE = (
    "Triage, not ranking: scores are not compared across neighborhoods or markets; "
    "staff prioritize. Rows are grouped by screening outcome, then listed in advertised sale order."
)
SALE_STATUS_NOTE = "Sale status can change by payment or court order before the sale."

# Evidence coverage groups in plain language.
COVERAGE_PLAIN: dict[str, str] = {
    "G1": "Parcel records: assessment record and County GIS parcel shape both present",
    "G2": "Zoning rules: district found and its use + size rules encoded (or not needed)",
    "G3": "Hazard maps: all four screening layers checked",
    "G4": "Code enforcement: PLI violation and condemned-property lists checked",
    "G5": "Sale route: parcel in the City advertisement and sale regulations captured",
}
COVERAGE_HELP = (
    "Evidence coverage counts which of five evidence groups (G1–G5) LotLine could check. "
    "It measures how much was checked, not how good the lot is. Conflicts do not lower "
    "coverage; they are shown separately."
)
EASE_HELP = (
    "Development Ease (0–6) adds three 0–2 components: use (is housing allowed and how), "
    "dimensional (does an illustrative building envelope fit), environment (how many "
    "hazard families the screening maps flag). Unknowns are withheld, never scored as 0. "
    "A range appears when corner-lot status is unverified."
)
CONFLICT_HELP = {
    "critical": "Critical: records disagree about what the parcel is or its current condition. "
                "The whole parcel is not scored.",
    "material": "Material: sources disagree across a legal threshold (for example, the zoning "
                "minimum lot size). Only the affected score component is withheld.",
    "disclose": "Disclosed: sources differ by more than 10% but no decision changes. Shown for "
                "transparency; no score change.",
}
COMPONENT_LABEL = {"use": "Use", "dimensional": "Dimensional", "environment": "Environment"}
COMPONENT_STATUS_PLAIN = {
    "known": "scored",
    "range": "range (corner status unverified)",
    "withheld": "withheld",
    "not_applicable": "not applicable",
}

# Explicit unknown-state lines for the four required tiles (build contract section 4).
TILE_UNKNOWN = {
    "zoning": "Contextual setbacks (Ch. 925) not evaluated",
    "environmental": "Screening layers only; not a geotechnical or flood determination",
    "infrastructure": "Utility capacity, laterals and legal access not established",
    "policy": "Community plan alignment not evaluated",
}

TREASURER_SALE_BADGE = "City Treasurer Sale · October 2, 2026"
TREASURER_SALE_TERMS: tuple[str, ...] = (
    "Competitive bidding; the upset price is the opening bid",
    "90-day redemption period after the sale",
    "Title is not cleared by the sale",
    "Liens, including water claims, survive the sale",
    "No Land Bank (PLB) priority verified for this parcel",
)
TREASURER_SALE_CITATION = (
    "Second Class City Treasurer's Sale and Collection Act (Act 171 of 1984) and the "
    "City of Pittsburgh Treasurer Sale regulations for the 10/2/2026 sale"
)
ACQUISITION_BURDEN_NOTE = "acquisition-burden indicator only; not market value or an appraisal"

# Plain-language reasons for next-check triggers (engine trigger codes).
TRIGGER_PLAIN: dict[str, str] = {
    "base": "Standard check for every advertised vacant lot",
    "possible_corner": "Geometry suggests a possible corner lot",
    "condemned_case_active": "An active condemned/dead-end case is on record",
    "rco": "Inside a Registered Community Organization area",
    "hazard: terrain": "Terrain (landslide-prone or 25%+ slope) flagged in screening maps",
    "hazard: undermining": "Undermining flagged in screening maps",
    "hazard: FEMA SFHA": "FEMA flood hazard area flagged in screening maps",
    "conflict: lot_area (material)": "Lot-area records fall on both sides of the zoning minimum",
    "rule: dimensions_encoded=N": "This district's size rules are not encoded in LotLine v1",
}

EVIDENCE_CLASS_PLAIN: dict[str, str] = {
    "raw": "Raw: copied from a public source as published",
    "derived": "Derived: computed by LotLine's deterministic engine from raw facts",
    "approximate": "Approximate: geometry estimate (bounding rectangle, street proximity)",
    "rule": "Rule: zoning-code value encoded by the team with a section citation",
    "untrusted_text": "Untrusted text: free text from a source, quoted, never followed",
    "synthetic": "Synthetic: test fixture built to attack the system (red-team cases only)",
}

GLOSSARY: tuple[tuple[str, str], ...] = (
    ("PIN", "Allegheny County parcel ID. Full 16 characters, or the short map-block-lot form such as 131-N-31."),
    ("Upset price", "The opening bid at the Treasurer Sale: the taxes and costs owed."),
    ("Evidence coverage (G1–G5)", COVERAGE_HELP),
    ("Development Ease", EASE_HELP),
    ("Critical / material / disclosed", " ".join(CONFLICT_HELP.values())),
    ("RCO", "Registered Community Organization: the community group to contact for review. Contact, not endorsement."),
    ("Screening layers", "City and FEMA map layers (landslide-prone, 25%+ slope, undermined, flood). They flag where to look; they do not determine site conditions."),
)

CONTRACT_CASES: tuple[tuple[str, str], ...] = (
    ("1 · Centre Ave 10S5: vacant vs active condemned case", "Not scorable (critical conflict)"),
    ("2 · Centre Ave 10S5: 1,672 vs 4,305 sf vs 2,400 sf minimum", "Dimensional withheld (material conflict)"),
    ("3 · In open data, not in 9/16 advertisement", "Routed out of the sale universe"),
    ("4 · Kemper St: 55% area gap, no known threshold", "Disclosed only; dimensions withheld because P-district rules not encoded"),
    ("5 · Mossfield St: 32% gap, both above 3,200 sf", "Disclosed only; no score change"),
    ("6 · SYNTHETIC injection text in a violation record", "Engine result unchanged; instruction not reflected in memo"),
    ("7 · Unknown PIN typed in search", "No packet; 'PIN not found in snapshot'"),
    ("8 · SYNTHETIC stale source snapshot", "Warning banner: sale status may have changed"),
    ("9 · Michigan St 15S66: possible corner", "Dimensional shown as a range"),
    ("10 · Memo draft picks a winning source", "Claim checker blocks it; deterministic memo shown"),
)
