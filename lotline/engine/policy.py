"""Screening-policy constants: the only place thresholds and vocabularies live.

Everything here is a stated LotLine screening assumption or a value frozen by
docs/build_contract.md. Engine modules import from here; nothing else
hardcodes these numbers.
"""

from __future__ import annotations

from datetime import date

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
# width bands on the base setbacks only.
WIDTH_FULL_FT = 20.0
WIDTH_PARTIAL_FT = 10.0
DIMENSIONAL_ASSUMPTION = (
    "LotLine screening assumption: illustrative base-setback envelope on the "
    "minimum-bounding-rectangle sides (short side treated as frontage); width "
    f">= {WIDTH_FULL_FT:g} ft scores 2, >= {WIDTH_PARTIAL_FT:g} ft scores 1, otherwise 0; "
    "contextual setbacks (Ch. 925) not evaluated"
)

# --- Conflicts ---------------------------------------------------------------
DISCLOSE_GAP_PCT = 10.0  # symmetric or directional gap above this is disclosed
PRICE_TOLERANCE_USD = 0.01

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
