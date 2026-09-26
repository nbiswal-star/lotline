"""Layer 3: deterministic screening engine.

``screen(ctx)`` is the only entry point. It consumes ``lotline.models``
records and returns a ``ScreeningResult``; the UI and the LLM never compute or
revise any of these values. The engine reads only the ParcelContext it is given.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from lotline.facts import facts_for, rule_facts
from lotline.models import (
    Fact,
    Outcome,
    ParcelContext,
    ScreeningResult,
)

from . import policy
from .checks import CheckInputs, barriers, next_checks
from .conflicts import area_gap, conflict_group_id, detect_conflicts, has_critical, highest_level
from .coverage import evidence_coverage, sources_queried
from .derived import (
    AREA_GAP_NOTE,
    AREA_INPUTS,
    AREA_SYM_NOTE,
    ENVELOPE_NOTE,
    RATIO_NOTE,
    backfill_fact,
    derived_fact,
    upset_to_assessed_land,
)
from .dimensions import score_dimensional
from .hazards import hazard_families, score_environment
from .routing import RoutingInputs, route
from .scoring import component_display, ease_result
from .staleness import sale_date_passed_warning, stale_source_warnings
from .use import score_use

__all__ = ["screen", "conflict_level"]

ROUTING_ONLY = (Outcome.OUT_OF_UNIVERSE, Outcome.STRUCTURE)


def conflict_level(result: ScreeningResult) -> str:
    """"critical" | "material" | "disclose" | "none"."""
    return highest_level(result.conflicts)


def _advertisement_date(ctx: ParcelContext) -> str:
    entry = ctx.manifest.get("city_advertisement")
    return entry.snapshot_as_of if entry else policy.ADVERTISEMENT_DATE.isoformat()


def _upstream_facts(ctx: ParcelContext) -> list[Fact]:
    """Raw and rule facts from lotline.facts (Layer 2)."""
    out = list(facts_for(ctx))
    if ctx.rule is not None:
        out += rule_facts(ctx.rule, ctx.manifest)
    return out


def _band_caps(ctx: ParcelContext, unqueried: tuple[str, ...]) -> list[tuple[str, str]]:
    """policy.BAND_CAPS whose ParcelFacts flag is True (from a completed layer query)."""
    if ctx.facts is None:
        return []
    return [
        (cap, reason)
        for flag, cap, reason in policy.BAND_CAPS
        if getattr(ctx.facts, flag, False) is True and flag not in unqueried
    ]


def screen(ctx: ParcelContext, *, today: date | None = None) -> ScreeningResult:
    facts, rule = ctx.facts, ctx.rule
    conflicts = detect_conflicts(ctx)
    critical = has_critical(conflicts)
    unqueried = tuple(s for s in policy.G3_SOURCES if not sources_queried(ctx.manifest, (s,)))

    use = score_use(rule)
    dim = score_dimensional(ctx.pin, facts, rule, conflicts)
    env = score_environment(ctx.pin, facts, unqueried)
    families = hazard_families(facts, unqueried)

    r = route(
        RoutingInputs(
            advertised=ctx.advert is not None,
            is_structure=ctx.treasury.is_structure,
            critical_conflict=critical,
            has_parcel_facts=facts is not None,
            use=use,
            rule_encoded=rule is not None,
            dimensions_applicable=rule.dimensions_applicable if rule else True,
            dimensions_encoded=rule.dimensions_encoded if rule else False,
            site_standard_blocks=rule.site_standard_blocks_dimensional if rule else False,
            dimensional=dim.component,
            area_conforms=dim.area_conforms,
            environment=env,
        )
    )
    outcome = r.outcome
    routing_only = outcome in ROUTING_ONLY

    result = ScreeningResult(pin=ctx.pin, outcome=outcome, conflicts=conflicts)
    result.hazard_families = families
    if not routing_only:
        result.use, result.dimensional, result.environment = use, dim.component, env
        result.scenarios = dim.scenarios
        result.setback_screen = dim.setback_screen
    result.ease = ease_result(
        outcome, [result.use, result.dimensional, result.environment], critical=critical,
        caps=_band_caps(ctx, unqueried),
    )
    result.coverage = evidence_coverage(ctx)

    gap = area_gap(facts.assess_lotarea_sf, facts.county_gis_area_sf) if facts else None
    if gap is not None:
        result.area_gap_pct = round(gap.pct, 2)
        result.area_gap_symmetric_pct = round(gap.symmetric_pct, 2)
    result.upset_to_assessed_land = upset_to_assessed_land(ctx)

    inputs = CheckInputs(
        ctx=ctx,
        outcome=outcome,
        conflicts=conflicts,
        dimensional=dim,
        hazard_families=families,
        advertisement_date=_advertisement_date(ctx),
        environment=env,
        unqueried_layers=unqueried,
        upset_to_assessed_land=result.upset_to_assessed_land,
    )
    result.barriers = barriers(inputs)
    result.next_checks = next_checks(inputs)

    result.warnings = (
        list(facts.load_warnings if facts else ())
        + stale_source_warnings(ctx.manifest)
        + sale_date_passed_warning(ctx.treasury.sale_date, today)
    )

    result.facts, result.conflicts = _assemble_facts(ctx, result)
    return result


def _derived_facts(ctx: ParcelContext, result: ScreeningResult) -> list[Fact]:
    out: list[Fact] = []
    if result.area_gap_pct is not None:
        out.append(derived_fact(ctx, "area_gap_pct", result.area_gap_pct, unit="%",
                                note=AREA_GAP_NOTE, inputs=AREA_INPUTS))
        out.append(derived_fact(ctx, "area_gap_symmetric_pct", result.area_gap_symmetric_pct,
                                unit="%", note=AREA_SYM_NOTE, inputs=AREA_INPUTS))
    if result.upset_to_assessed_land is not None:
        out.append(derived_fact(ctx, "upset_to_assessed_land", result.upset_to_assessed_land,
                                unit="ratio", note=RATIO_NOTE,
                                inputs=("city_advertisement", "county_assessments")))
    geo_inputs = ("county_parcels", "zoning_code")
    for s in result.scenarios:
        out.append(derived_fact(ctx, f"envelope_{s.label}_width_ft", round(s.width_ft, 1), unit="ft",
                                note=ENVELOPE_NOTE, inputs=geo_inputs, evidence_class="approximate"))
        out.append(derived_fact(ctx, f"envelope_{s.label}_depth_ft", round(s.depth_ft, 1), unit="ft",
                                note=ENVELOPE_NOTE, inputs=geo_inputs, evidence_class="approximate"))
    all_sources = tuple(ctx.manifest)
    score_note = "deterministic LotLine screening score (build contract section 3)"
    for c in (result.use, result.dimensional, result.environment):
        if c is not None:
            out.append(derived_fact(ctx, f"{c.name}_score", component_display(c), unit="points",
                                    note=f"{score_note}; {c.reason or c.status}", inputs=all_sources))
    if result.ease is not None:
        out.append(derived_fact(ctx, "ease_result", result.ease.display, unit=None,
                                note=score_note, inputs=all_sources))
    out.append(derived_fact(ctx, "hazard_families", tuple(result.hazard_families), unit=None,
                            note="terrain = landslide-prone OR slope25; undermining; FEMA SFHA; "
                                 "screening layers only",
                            inputs=("landslide_prone", "slope25", "undermined", "fema_nfhl")))
    out.append(derived_fact(ctx, "evidence_coverage", result.coverage_display, unit="groups",
                            note="G1-G5 from joined data and source manifest", inputs=all_sources))
    out.append(derived_fact(ctx, "screen_outcome", result.outcome.value, unit=None,
                            note="routing precedence (implementation plan section 4)",
                            inputs=all_sources))
    return out


def _assemble_facts(ctx: ParcelContext, result: ScreeningResult):
    """Upstream facts + derived facts; tag conflict groups; complete cited provenance."""
    facts = _upstream_facts(ctx) + _derived_facts(ctx, result)
    by_id: dict[str, Fact] = {}
    for f in facts:
        by_id.setdefault(f.id, f)

    # Every fact in a conflict's group is carried by the conflict, and vice versa.
    conflicts = []
    for c in result.conflicts:
        group = conflict_group_id(c.kind)
        grouped = [f.id for f in by_id.values() if f.conflict_group == group and f.pin == ctx.pin]
        ids = tuple(dict.fromkeys((*c.fact_ids, *grouped)))
        conflicts.append(replace(c, fact_ids=ids))
        for fid in ids:
            if fid in by_id and by_id[fid].conflict_group is None:
                by_id[fid] = replace(by_id[fid], conflict_group=group)

    cited = [fid for c in conflicts for fid in c.fact_ids]
    for comp in (result.use, result.dimensional, result.environment):
        if comp is not None:
            cited.extend(comp.fact_ids)
    for fid in cited:
        if fid not in by_id:
            f = backfill_fact(ctx, fid)
            if f is not None:
                by_id[fid] = f
    return list(by_id.values()), conflicts
