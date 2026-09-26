"""Checked environmental hazard families and the environment component (0-2)."""

from __future__ import annotations

from lotline.models import ComponentScore, ParcelFacts, fact_id

TERRAIN = "terrain"
UNDERMINING = "undermining"
FEMA_SFHA = "FEMA SFHA"
FAMILY_ORDER = (TERRAIN, UNDERMINING, FEMA_SFHA)

SCREENING_CAVEAT = "Screening layers only; not a geotechnical or flood determination"


def hazard_families(facts: ParcelFacts | None) -> list[str]:
    """Families flagged in the checked screening layers, in canonical order.

    Terrain = landslide-prone OR slope25 (slope25 counted once even though it is
    also cross-listed in the zoning tile).
    """
    if facts is None:
        return []
    flagged = {
        TERRAIN: facts.landslide_prone or facts.slope25,
        UNDERMINING: facts.undermined,
        FEMA_SFHA: facts.fema_sfha,
    }
    return [f for f in FAMILY_ORDER if flagged[f]]


def hazard_fact_ids(pin: str) -> tuple[str, ...]:
    return tuple(
        fact_id(pin, name) for name in ("landslide_prone", "slope25", "undermined", "fema_zone", "fema_sfha")
    )


def score_environment(pin: str, facts: ParcelFacts | None, layers_queried: bool) -> ComponentScore:
    """2 = no family flagged; 1 = one; 0 = two or more. Unknown is withheld, never 0."""
    if facts is None or not layers_queried:
        return ComponentScore(
            "environment", None, None, "withheld",
            "screening layers not queried for this parcel; hazard families unknown",
        )
    fams = hazard_families(facts)
    score = 2 if not fams else 1 if len(fams) == 1 else 0
    if fams:
        reason = f"flagged in the checked screening layers: {', '.join(fams)}. {SCREENING_CAVEAT}"
    else:
        reason = f"no overlap in the checked screening layers. {SCREENING_CAVEAT}"
    return ComponentScore("environment", score, score, "known", reason, hazard_fact_ids(pin))
