"""Screening-policy constants: the only place thresholds and vocabularies live.

Everything here is a stated LotLine screening assumption or a value frozen by
docs/build_contract.md. Engine modules import from here; nothing else
hardcodes these numbers.
"""

from __future__ import annotations

from datetime import date

from lotline.reconcile import PRICE_TOLERANCE_USD  # single source; re-exported here

# --- Use entitlement -------------------------------------------------------
# Permission vocabulary is data: add a code here (e.g. a new conditional-use
# path) and every district using it scores without an engine change.
# P = permitted by right; A = Administrator Exception; S = Special Exception;
# C = conditional use (not in v1 rules, supported for future rows).
PERMISSION_SCORES: dict[str, int] = {
    "P": 2,
    "A": 1,
    "S": 1,
    "C": 1,
    "PROHIBITED": 0,
}
PERMISSION_LABELS: dict[str, str] = {
    "P": "permitted by right",
    "A": "Administrator Exception",
    "S": "Special Exception",
    "C": "conditional use",
    "PROHIBITED": "prohibited (use variance or rezoning)",
}

# --- Dimensional fit ---------------------------------------------------------
# LotLine screening assumption, not a code requirement: illustrative envelope
# bands on the base setbacks only. The same thresholds apply to width and to
# depth, and the scenario scores the smaller of the two bands:
#   score = min(band(width), band(depth)), band(x) = 2 if x >= 20 ft,
#   1 if x >= 10 ft, else 0.
# A 30 ft wide lot with 1 ft of envelope depth therefore scores 0, not 2.
WIDTH_FULL_FT = 20.0
WIDTH_PARTIAL_FT = 10.0
DEPTH_FULL_FT = WIDTH_FULL_FT
DEPTH_PARTIAL_FT = WIDTH_PARTIAL_FT
DIMENSIONAL_ASSUMPTION = (
    "LotLine screening assumption: illustrative base-setback envelope on the "
    "minimum-bounding-rectangle sides (short side treated as frontage); the score is the "
    f"lower of the width and depth bands (>= {WIDTH_FULL_FT:g} ft scores 2, "
    f">= {WIDTH_PARTIAL_FT:g} ft scores 1, otherwise 0); "
    "contextual setbacks (Ch. 925) not evaluated"
)

# --- Conflicts ---------------------------------------------------------------
DISCLOSE_GAP_PCT = 10.0  # symmetric or directional gap above this is disclosed
# A disclose-level gap this large (directional or symmetric) adds a deed and
# record-area reconciliation check and a barrier, without changing any score.
LARGE_GAP_PCT = 25.0

# Upset price / assessed land value at or above this adds an acquisition-burden
# barrier (indicator only, not market value).
ACQUISITION_BURDEN_RATIO = 3.0

CURRENT_CONDITION_WORDING = (
    "Assessment classifies the parcel as vacant, while an active condemned/dead-end "
    "case remains associated with the parcel/address. Current site condition is unverified."
)

# --- Ease bands (only when all components known) -----------------------------
BANDS: tuple[tuple[int, int, str], ...] = (
    (5, 6, "Apparently lower-discretion"),
    (3, 4, "Conditional"),
    (0, 2, "Difficult"),
)
MAX_TOTAL = 6

# Discretion caps on the band (data-driven): (ParcelFacts boolean field, the
# highest band allowed when it is True, reason appended to the display). A
# slope25 overlap means possible Steep Slope Overlay Planning Commission
# review (§906.08), so the band cannot read "Apparently lower-discretion".
BAND_CAPS: tuple[tuple[str, str, str], ...] = (
    ("slope25", "Conditional", "possible Steep Slope Overlay review, §906.08"),
)

# --- Sale status / staleness -------------------------------------------------
ADVERTISEMENT_DATE = date(2026, 9, 16)  # build contract section 8
SALE_STATUS_SOURCES: tuple[str, ...] = ("wprdc_treasury_sales", "city_advertisement")
STALE_WARNING = "sale status may have changed by payment or court order"

# --- Evidence coverage source groups (source_manifest.csv ids) ---------------
G1_SOURCES = ("county_assessments", "county_parcels")
G2_SOURCES = ("city_zoning", "zoning_code")
G3_SOURCES = ("landslide_prone", "slope25", "undermined", "fema_nfhl")
G4_SOURCES = ("pli_violations", "condemned_properties")
G5_SOURCES = ("city_advertisement", "treasurer_sale_regulations")

# --- District procedure checks and barriers ----------------------------------
# Code-required reviews that apply by district (verified against ecode360,
# legislation through 2026-09-16). Each entry: (check text, owner, trigger,
# minimum lot area in sf that triggers it or None). A check with a lot-area
# trigger is listed when any recorded lot area meets it, or when area is
# unknown (possibly applicable).
DISTRICT_REVIEW_CHECKS: dict[str, tuple[tuple[str, str, str, float | None], ...]] = {
    "P": (
        (
            "open-space / greenway designation",
            "City Planning (open space & parks planning)",
            "rule: P district; single-unit detached is permitted by right under §911.02 and site "
            "plan review applies (§905.01.D), but the lot may be designated or used as open space",
            None,
        ),
        (
            "site plan review (§905.01.D)",
            "Zoning Administrator / Planning",
            "rule: P district; new construction on lots >= 2,400 sf (§905.01.D.1(a))",
            2400.0,
        ),
    ),
    "LNC": (
        (
            "site plan review (§904.02.D)",
            "Zoning Administrator / Planning",
            "rule: LNC district; lots >= 2,400 sf (§904.02.D)",
            2400.0,
        ),
        (
            "residential compatibility (Ch. 916)",
            "Zoning Administrator",
            "rule: LNC district residential compatibility standards (Ch. 916)",
            None,
        ),
    ),
    "H": (
        (
            "Administrator Exception for single-unit (§911.04.A.69)",
            "Zoning Administrator",
            "rule: H district; single-unit is an Administrator Exception subject to "
            "§911.04.A.69(a) topography, soils, access and utility conditions",
            None,
        ),
    ),
}

# Decision-impact category of each district review check (see
# DECISION_IMPACT_ORDER); checks not listed are "district_procedure".
DISTRICT_REVIEW_CATEGORY: dict[str, str] = {
    "open-space / greenway designation": "parks_open_space",
    "Administrator Exception for single-unit (§911.04.A.69)": "site_standard",
}

# Plain-language district risk barriers (policy risk, not a code prohibition).
DISTRICT_RISK_BARRIERS: dict[str, str] = {
    "P": (
        "Parks and Open Space (P) district: confirm whether the lot is designated or used as "
        "park, greenway or open space before pursuing housing"
    ),
}

# Plain-language barriers for survey-dependent site standards (never raw CSV text).
SITE_STANDARD_BARRIERS: dict[str, str] = {
    "H": (
        "Hillside (H) district: single-unit housing needs an Administrator Exception that "
        "depends on a survey showing a contiguous area under 30% slope for the house, soils, "
        "access and utilities (§911.04.A.69); clearing is capped (§911.04.A.69(b))"
    ),
}
SITE_STANDARD_SHORT: dict[str, str] = {
    "H": "survey-dependent site standard, §911.04.A.69",
}
SITE_STANDARD_GENERIC_BARRIER = (
    "{district} district: a site standard requires a survey before dimensional fit can be screened"
)
SITE_STANDARD_GENERIC_SHORT = "survey-dependent site standard"

# Districts whose dimensions LotLine does not model: a tool gap, not a records problem.
UNENCODED_DIMENSIONS_BARRIER = (
    "LotLine does not yet model {district} dimensions{cite}; this is a tool limitation, "
    "not a records problem"
)

# §921.04.A lot of record (vacant nonconforming lot in separate ownership).
LOT_OF_RECORD_CHECK = (
    "lot-of-record eligibility (§921.04.A): vacant lot in separate ownership may qualify for "
    "an Administrator Exception for single-unit use"
)
LOT_OF_RECORD_OWNER = "Zoning Administrator + County deed records"
BELOW_MINIMUM_BARRIER = (
    "records agree the lot is below the {minimum} sf district minimum; §921.04.A lot-of-record "
    "path requires Zoning Administrator review"
)

# Treasurer Sale mechanics (sale regulations for the recorded sale date; Act 171 of
# 1984 §304 redemption). Written "sec. 304" so the memo claim checker does not
# read it as a Pittsburgh Code section.
SALE_TERMS_CHECK = (
    "Treasurer Sale terms: 90-day redemption; mortgages, judgments, water claims and other "
    "secured claims are not divested ({sale_date} regulations; Act 171 of 1984 sec. 304)"
)
SALE_TERMS_OWNER = "title examiner or attorney"
CURRENT_SALE_STATUS_CHECK = "verify current advertised sale status before incurring costs"
CURRENT_SALE_STATUS_OWNER = "City Treasurer / Real Estate Division"
CURRENT_SALE_STATUS_TRIGGER = (
    "standard pre-spend gate: advertised status may change by payment or court order"
)

# Friendly names for the four screening layers (source_manifest ids).
LAYER_NAMES: dict[str, str] = {
    "landslide_prone": "landslide-prone",
    "slope25": "slope 25%+",
    "undermined": "undermined",
    "fema_nfhl": "FEMA NFHL",
}

# Code references attached to hazard next-check triggers (check text stays canonical).
TERRAIN_SLOPE_TRIGGER = (
    "slope25 overlap: possible Steep Slope Overlay Planning Commission review (§906.08); "
    "grading, cut and fill standards (§915.02)"
)
TERRAIN_LANDSLIDE_TRIGGER = "landslide-prone overlap: LS-O geotechnical investigation (§906.04)"
UNDERMINING_TRIGGER = (
    "undermined overlap: UM-O site investigation for structures larger than a typical "
    "single-unit dwelling (§906.05)"
)

# --- Decision-impact ordering (Round 3) ---------------------------------------
# Barriers and parcel-specific next checks are listed most consequential first,
# so the "principal barrier" (first barrier) and the first parcel-specific next
# check are the items most likely to change the decision. Each barrier and
# check is tagged with one category by lotline.engine.checks; lists are
# stable-sorted by the category's position here (ties keep insertion order).
# Standard checks (trigger "base") and the Treasurer Sale terms check are not
# parcel-specific and always follow every parcel-specific check.
DECISION_IMPACT_ORDER: tuple[str, ...] = (
    "critical_conflict",   # whole parcel held out of scoring
    "material_conflict",   # records cross a controlling threshold (component withheld)
    "below_minimum",       # records agree the lot is below the district minimum (§921.04.A)
    "use_prohibition",     # no housing use permitted
    "rules_not_encoded",   # LotLine tool gap (district dimensions / use vocabulary)
    "missing_input",       # a named input is missing or invalid; a component is withheld
    "site_standard",       # survey-dependent site standard (H, §911.04.A.69)
    "hazard",              # terrain, undermining, FEMA screening overlaps
    "dimensional_envelope",  # narrow or shallow illustrative envelope
    "parks_open_space",    # Parks / open-space designation (P district)
    "area_gap",            # large disclose-level area gap (no score change)
    "acquisition_burden",  # upset price >= ACQUISITION_BURDEN_RATIO x assessed land value
    "corner_frontage",     # corner / frontage status unverified
    "district_procedure",  # code-required procedural reviews (site plan review, Ch. 916)
    "community_historic",  # RCO contact, historic review applicability
    "standard",            # base checks and Treasurer Sale terms (never parcel-specific)
)


def impact_rank(category: str) -> int:
    """Position of ``category`` in DECISION_IMPACT_ORDER (unknown categories sort last)."""
    try:
        return DECISION_IMPACT_ORDER.index(category)
    except ValueError:
        return len(DECISION_IMPACT_ORDER)


# Trigger text of the Treasurer Sale terms check (a standard check, like "base").
SALE_TERMS_TRIGGER = "advertised for the Treasurer Sale (treasurer_sale_regulations)"
STANDARD_TRIGGERS: frozenset[str] = frozenset({
    "base", SALE_TERMS_TRIGGER, CURRENT_SALE_STATUS_TRIGGER,
})
