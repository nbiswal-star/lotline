"""Evidence coverage G1-G5 (build contract section 3), derived from joined data + manifest.

Conflicts never reduce coverage; they are reported separately.
"""

from __future__ import annotations

from collections.abc import Mapping

from lotline.models import ParcelContext, SourceEntry

from . import policy
from .use import permission_score


def sources_queried(manifest: Mapping[str, SourceEntry], source_ids: tuple[str, ...]) -> bool:
    """Every listed source is in the manifest with query_completed=True."""
    return all(sid in manifest and manifest[sid].query_completed for sid in source_ids)


def evidence_coverage(ctx: ParcelContext) -> dict[str, bool]:
    m, facts, rule = ctx.manifest, ctx.facts, ctx.rule
    g1 = (
        facts is not None
        and facts.assess_lotarea_sf is not None
        and facts.county_gis_area_sf is not None
        and sources_queried(m, policy.G1_SOURCES)
    )
    use_encoded = rule is not None and all(
        permission_score(code) is not None
        for code in (rule.single_unit_permission, rule.two_unit_permission)
    )
    g2 = (
        use_encoded
        and (rule.dimensions_encoded or not rule.dimensions_applicable)
        and sources_queried(m, policy.G2_SOURCES)
    )
    g3 = facts is not None and sources_queried(m, policy.G3_SOURCES)
    g4 = facts is not None and sources_queried(m, policy.G4_SOURCES)
    g5 = ctx.advert is not None and sources_queried(m, policy.G5_SOURCES)
    return {"G1": bool(g1), "G2": bool(g2), "G3": g3, "G4": g4, "G5": g5}


COVERAGE_LABELS: dict[str, str] = {
    "G1": "assessment record and County GIS polygon present",
    "G2": "district resolved and use + dimensional rules encoded (or dimensions not applicable)",
    "G3": "all four screening layers queried",
    "G4": "PLI violations and condemned datasets queried",
    "G5": "parcel in City advertisement and sale regulations captured",
}
