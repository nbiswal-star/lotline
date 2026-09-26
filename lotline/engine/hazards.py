"""Checked environmental hazard families and the environment component (0-2).

A family counts as flagged only from a layer whose query completed. The
environment component is withheld (never scored) when any screening layer
query did not complete or the FEMA zone is undetermined or unrecognized.
"""

from __future__ import annotations

from collections.abc import Iterable

from lotline.models import ComponentScore, ParcelFacts, fact_id, sfha_status

from . import policy

TERRAIN = "terrain"
UNDERMINING = "undermining"
FEMA_SFHA = "FEMA SFHA"
FAMILY_ORDER = (TERRAIN, UNDERMINING, FEMA_SFHA)

SCREENING_CAVEAT = "Screening layers only; not a geotechnical or flood determination"


def effective_sfha(facts: ParcelFacts) -> bool | None:
    """FEMA SFHA flag re-validated against the zone vocabulary.

    True when either the normalized flag or the zone text shows an SFHA zone;
    None (unknown) when either is unknown (zone D or an unrecognized code);
    otherwise False. Guards against a record built outside the loader.
    """
    from_zone = sfha_status(facts.fema_zone)
    if facts.fema_sfha is True or from_zone is True:
        return True
    if facts.fema_sfha is None or from_zone is None:
        return None
    return False


def hazard_families(facts: ParcelFacts | None, unqueried: Iterable[str] = ()) -> list[str]:
    """Families flagged in the checked screening layers, in canonical order.

    Terrain = landslide-prone OR slope25 (slope25 counted once even though it is
    also cross-listed in the zoning tile). Layers in ``unqueried`` (source ids
    whose query did not complete) never flag a family.
    """
    if facts is None:
        return []
    skip = set(unqueried)
    flagged = {
        TERRAIN: (facts.landslide_prone and "landslide_prone" not in skip)
        or (facts.slope25 and "slope25" not in skip),
        UNDERMINING: facts.undermined and "undermined" not in skip,
        FEMA_SFHA: effective_sfha(facts) is True and "fema_nfhl" not in skip,
    }
    return [f for f in FAMILY_ORDER if flagged[f]]


def hazard_fact_ids(pin: str) -> tuple[str, ...]:
    return tuple(
        fact_id(pin, name) for name in ("landslide_prone", "slope25", "undermined", "fema_zone", "fema_sfha")
    )


def layer_names(source_ids: Iterable[str]) -> str:
    return ", ".join(policy.LAYER_NAMES.get(s, s) for s in source_ids)


def score_environment(
    pin: str, facts: ParcelFacts | None, unqueried: Iterable[str] = ()
) -> ComponentScore:
    """2 = no family flagged; 1 = one; 0 = two or more. Unknown is withheld, never scored."""
    missing = tuple(unqueried)
    if facts is None:
        return ComponentScore(
            "environment", None, None, "withheld",
            "prepared parcel records missing; hazard families unknown",
            short_reason="parcel records missing",
        )
    if missing:
        names = layer_names(missing)
        return ComponentScore(
            "environment", None, None, "withheld",
            f"screening layer query did not complete ({names}); hazard families unknown",
            hazard_fact_ids(pin),
            short_reason=f"screening layer query incomplete: {names}",
        )
    if effective_sfha(facts) is None:
        return ComponentScore(
            "environment", None, None, "withheld",
            f"FEMA flood zone {facts.fema_zone!r} is undetermined or not a recognized NFHL zone; "
            "flood family unknown",
            hazard_fact_ids(pin),
            short_reason="FEMA flood zone undetermined",
        )
    fams = hazard_families(facts)
    score = 2 if not fams else 1 if len(fams) == 1 else 0
    if fams:
        reason = f"flagged in the checked screening layers: {', '.join(fams)}. {SCREENING_CAVEAT}"
    else:
        reason = f"no overlap in the checked screening layers. {SCREENING_CAVEAT}"
    short = f"flagged: {', '.join(fams)} (screening layers)" if fams else "no overlap in the checked screening layers"
    return ComponentScore("environment", score, score, "known", reason, hazard_fact_ids(pin), short_reason=short)
