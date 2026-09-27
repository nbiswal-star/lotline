"""Engine unit tests on hand-built records (no loader dependency)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from engine_builders import PIN, ctx, facts, manifest, rule

from lotline.engine import conflict_level, screen
from lotline.engine import policy
from lotline.engine.conflicts import area_gap, detect_conflicts, threshold_between
from lotline.engine.coverage import evidence_coverage
from lotline.engine.dimensions import compute_scenarios, envelope_score, format_setback_screen, score_dimensional
from lotline.engine.hazards import hazard_families, score_environment
from lotline.engine.scoring import component_display, ease_result
from lotline.engine.staleness import sale_date_passed_warning, stale_source_warnings
from lotline.engine.use import score_use
from lotline.models import ComponentScore, ConflictLevel, Outcome, SourceEntry, derived_fact_id


# --- conflicts ---------------------------------------------------------------


def test_area_gap_formulas():
    g = area_gap(1672, 4305)
    assert g.pct == pytest.approx((4305 - 1672) / 1672 * 100)
    assert g.symmetric_pct == pytest.approx(abs(1672 - 4305) / 4305 * 100)
    assert area_gap(None, 10) is None and area_gap(0, 10) is None


@pytest.mark.parametrize(
    "a,b,minimum,expected",
    [(1672, 4305, 2400, True), (3000, 3100, 3000, False), (2999, 3001, 3000, True),
     (5203, 7636, 3200, False), (1000, 2000, None, False)],
)
def test_threshold_between(a, b, minimum, expected):
    assert threshold_between(a, b, minimum) is expected


def test_material_conflict_withholds_dimensional_only():
    c = ctx(facts_kw=dict(assess_lotarea_sf=1000.0, county_gis_area_sf=1500.0))  # min 1200
    r = screen(c)
    lot = [k for k in r.conflicts if k.kind == "lot_area"][0]
    assert lot.level is ConflictLevel.MATERIAL and lot.affects == ("dimensional",)
    assert r.dimensional.status == "withheld" and "lot area" in r.dimensional.reason
    assert r.use.status == "known" and r.environment.status == "known"
    assert r.ease.display == (
        "Partial: 4 of 4 known points; dimensional withheld (lot-area records cross the 1,200 sf minimum)")
    assert r.ease.total_low is None
    assert r.outcome is Outcome.DEFER_RECORDS  # Advance requires conformity in all sources
    assert "withheld because area conflicts" in r.setback_screen


def test_material_even_when_gap_small():
    c = ctx(facts_kw=dict(assess_lotarea_sf=1190.0, county_gis_area_sf=1210.0))
    assert detect_conflicts(c)[0].level is ConflictLevel.MATERIAL


def test_disclose_only_above_ten_percent():
    assert detect_conflicts(ctx(facts_kw=dict(assess_lotarea_sf=3000.0, county_gis_area_sf=3300.0))) == []
    (c,) = detect_conflicts(ctx(facts_kw=dict(assess_lotarea_sf=3000.0, county_gis_area_sf=3400.0)))
    assert c.level is ConflictLevel.DISCLOSE and c.affects == ()
    assert "both sources exceed the 1,200 sf minimum" in c.summary.lower()


def test_current_condition_requires_vacant_assessment():
    c = ctx(facts_kw=dict(condemned_case_active=True))
    (k,) = detect_conflicts(c)
    assert k.level is ConflictLevel.CRITICAL and k.summary == policy.CURRENT_CONDITION_WORDING
    # Structure-classified: no vacant-vs-condemned conflict (routing handles it).
    s = ctx(facts_kw=dict(condemned_case_active=True), treasury_kw=dict(usedesc="SINGLE FAMILY"))
    assert detect_conflicts(s) == []


def test_sale_universe_price_mismatch_is_critical():
    from engine_builders import advert
    c = ctx(advert_obj=advert(upset=999.0))
    r = screen(c)
    assert conflict_level(r) == "critical" and r.outcome is Outcome.DEFER_RECORDS
    assert r.ease.display == "Not scorable"


@pytest.mark.parametrize("winner", ["is correct", "is wrong", "should be used", "is accurate"])
def test_conflict_summaries_never_pick_a_source(winner):
    c = ctx(facts_kw=dict(assess_lotarea_sf=1000.0, county_gis_area_sf=1500.0, condemned_case_active=True))
    for k in screen(c).conflicts:
        assert winner not in k.summary.lower()


# --- use -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "single,two,expected",
    [("P", "P", 2), ("P", "PROHIBITED", 2), ("A", "PROHIBITED", 1), ("S", "PROHIBITED", 1),
     ("C", "PROHIBITED", 1), ("PROHIBITED", "P", 2), ("PROHIBITED", "C", 1),
     ("PROHIBITED", "PROHIBITED", 0)],
)
def test_use_best_of_paths(single, two, expected):
    u = score_use(rule(single_unit_permission=single, two_unit_permission=two))
    assert (u.low, u.high, u.status) == (expected, expected, "known")


def test_unknown_permission_code_is_withheld_not_zero():
    u = score_use(rule(single_unit_permission="Z"))
    assert u.status == "withheld" and u.low is None


def test_no_per_unit_density_test():
    """Ord. 10-2025 repealed per-unit density: the two-unit path depends only on permission."""
    import lotline.engine.use as use_mod
    assert not hasattr(use_mod, "two_unit_density_ok")
    u = score_use(rule(single_unit_permission="PROHIBITED", two_unit_permission="P"))
    assert (u.low, u.high, u.status) == (2, 2, "known")


def test_riv_rm_use_copy_distinguishes_detached_from_unmodeled_attached() -> None:
    u = score_use(rule(district="RIV-RM", single_unit_permission="PROHIBITED", two_unit_permission="P"))
    assert "single-unit detached prohibited" in u.reason
    assert "attached housing not evaluated" in u.reason
    assert "two-unit permitted by right" in u.reason


# --- dimensional -----------------------------------------------------------------


def test_envelope_formulas_and_bands():
    s = compute_scenarios(49, 111, rule(front_setback_ft=30.0, rear_setback_ft=30.0, exterior_side_ft=30.0), True)
    assert [(x.label, x.width_ft, x.depth_ft, x.score) for x in s] == [
        ("interior", 39, 51, 2), ("corner", 14, 51, 1)]
    assert envelope_score(20, 20) == 2 and envelope_score(19.9, 50) == 1 and envelope_score(9.9, 50) == 0
    assert envelope_score(30, 0) == 0
    assert compute_scenarios(8, 20, rule(), False)[0].width_ft == 0  # clamped


def test_setback_screen_formats():
    s = compute_scenarios(20, 101, rule(), True)
    assert format_setback_screen(s, withheld_for_area=False) == (
        "Illustrative only: interior 10x71 ft; if corner about 0 ft wide")
    assert format_setback_screen([], withheld_for_area=False) == "not computed"


def test_blank_setback_is_unknown_never_zero():
    d = score_dimensional(PIN, facts(), rule(rear_setback_ft=None), [])
    assert d.component.status == "withheld" and "rear_setback_ft" in d.component.reason
    assert d.scenarios == [] and d.setback_screen == "not computed"
    # exterior side only matters for a possible corner
    ok = score_dimensional(PIN, facts(), rule(exterior_side_ft=None), [])
    assert ok.component.status == "known"
    corner = score_dimensional(PIN, facts(possible_corner=True), rule(exterior_side_ft=None), [])
    assert corner.component.status == "withheld"


def test_dimensional_withheld_reasons():
    assert "not encoded" in score_dimensional(PIN, facts(), rule(dimensions_encoded=False, min_lot_sf=None,
                                                              dimensional_citation="904"), []).component.reason
    site = score_dimensional(PIN, facts(), rule(site_standard_blocks_dimensional=True,
                                               site_standard="911.04.A.69 x"), [])
    assert site.component.status == "withheld" and site.component.short_reason == "survey-dependent site standard"
    assert "911.04.A.69 x" not in site.component.reason  # never raw CSV text
    na = score_dimensional(PIN, facts(), rule(dimensions_applicable=False), [])
    assert na.component.status == "not_applicable"


def test_area_below_minimum_in_all_sources_scores_zero_and_defers():
    r = screen(ctx(facts_kw=dict(assess_lotarea_sf=1000.0, county_gis_area_sf=1050.0)))
    assert (r.dimensional.low, r.dimensional.status) == (0, "known")
    assert r.outcome is Outcome.DEFER_RECORDS
    assert policy.BELOW_MINIMUM_BARRIER.format(minimum="1,200") in r.barriers
    assert policy.LOT_OF_RECORD_CHECK in [c.check for c in r.next_checks]
    lor = next(c for c in r.next_checks if c.check == policy.LOT_OF_RECORD_CHECK)
    assert lor.owner == "Zoning Administrator + County deed records"


def test_lot_of_record_check_when_below_minimum_in_one_source():
    r = screen(ctx(facts_kw=dict(assess_lotarea_sf=1000.0, county_gis_area_sf=1500.0)))
    assert policy.LOT_OF_RECORD_CHECK in [c.check for c in r.next_checks]
    assert policy.LOT_OF_RECORD_CHECK not in [c.check for c in screen(ctx()).next_checks]


def test_depth_limits_the_envelope_score():
    """Screening assumption: score = min(width band, depth band), same 20/10 ft thresholds."""
    r = screen(ctx(facts_kw=dict(mbr_long_side_ft=31.0)))  # depth 31 - 15 - 15 = 1 ft
    assert (r.dimensional.low, r.dimensional.high) == (0, 0)
    assert "illustrative envelope shallower than 10 ft" in r.barriers
    r = screen(ctx(facts_kw=dict(mbr_long_side_ft=45.0)))  # depth 15 ft -> band 1
    assert r.dimensional.low == 1 and "shallow illustrative envelope" in r.barriers
    assert "depth" in policy.DIMENSIONAL_ASSUMPTION


def test_zero_minimum_is_no_minimum_lot_size():
    c = ctx(rule_obj=rule(min_lot_sf=0.0), facts_kw=dict(assess_lotarea_sf=2000.0, county_gis_area_sf=3000.0))
    r = screen(c)
    text = " ".join([*r.barriers, *(k.summary for k in r.conflicts)])
    assert "0 sf minimum" not in text and "no minimum lot size" in text
    assert r.outcome is Outcome.ADVANCE


def test_possible_corner_range_does_not_collapse():
    r = screen(ctx(facts_kw=dict(possible_corner=True)))  # 33 ft: interior 23 (2), corner 13 (1)
    assert (r.dimensional.low, r.dimensional.high, r.dimensional.status) == (1, 2, "range")
    assert component_display(r.dimensional) == "1-2"
    assert r.ease.total_low != r.ease.total_high


# --- hazards / environment ---------------------------------------------------------


def test_hazard_families_and_scores():
    assert hazard_families(facts(slope25=True, landslide_prone=True)) == ["terrain"]
    assert hazard_families(facts(undermined=True, fema_sfha=True, landslide_prone=True)) == [
        "terrain", "undermining", "FEMA SFHA"]
    assert score_environment(PIN, facts()).low == 2
    assert score_environment(PIN, facts(undermined=True)).low == 1
    assert score_environment(PIN, facts(undermined=True, slope25=True)).low == 0


def test_unqueried_layers_are_withheld_not_zero():
    e = score_environment(PIN, facts(undermined=True, slope25=True), ("fema_nfhl",))
    assert e.status == "withheld" and e.low is None and "FEMA NFHL" in e.short_reason


# --- scoring -----------------------------------------------------------------------


def _k(name, lo, hi=None, status=None):
    hi = lo if hi is None else hi
    return ComponentScore(name, lo, hi, status or ("known" if lo == hi else "range"))


@pytest.mark.parametrize(
    "use,dim,env,expected",
    [(2, (2, 2), 2, "6 of 6: Apparently lower-discretion"),
     (2, (2, 2), 1, "5 of 6: Apparently lower-discretion"),
     (2, (1, 2), 2, "5-6 of 6: Apparently lower-discretion"),
     (2, (0, 1), 2, "4-5 of 6: band spans Conditional to Apparently lower-discretion"),
     (2, (1, 2), 0, "3-4 of 6: Conditional"),
     (1, (0, 1), 0, "1-2 of 6: Difficult"),
     (1, (1, 1), 0, "2 of 6: Difficult"),
     (1, (1, 2), 0, "2-3 of 6: band spans Difficult to Conditional")],
)
def test_ease_display(use, dim, env, expected):
    e = ease_result(Outcome.ADVANCE, [_k("use", use), _k("dimensional", *dim), _k("environment", env)],
                    critical=False)
    assert e.display == expected


def test_band_cap_is_data_driven():
    comps = [_k("use", 2), _k("dimensional", 2), _k("environment", 1)]
    cap = [("Conditional", "possible Steep Slope Overlay review, §906.08")]
    e = ease_result(Outcome.ADVANCE, comps, critical=False, caps=cap)
    assert e.display == "5 of 6: Conditional (possible Steep Slope Overlay review, §906.08)"
    assert (e.total_low, e.total_high, e.band) == (5, 5, "Conditional")
    # A cap that does not lower the band adds no reason.
    low = ease_result(Outcome.ADVANCE, [_k("use", 1), _k("dimensional", 1), _k("environment", 1)],
                      critical=False, caps=cap)
    assert low.display == "3 of 6: Conditional"
    span = ease_result(Outcome.ADVANCE, [_k("use", 2), _k("dimensional", 0, 1), _k("environment", 2)],
                       critical=False, caps=cap)
    assert span.display == "4-5 of 6: Conditional (possible Steep Slope Overlay review, §906.08)"
    assert policy.BAND_CAPS[0][0] == "slope25"


def test_slope25_caps_band_on_real_style_parcel():
    r = screen(ctx(facts_kw=dict(slope25=True)))  # 2 + 2 + 1 = 5
    assert r.ease.display == "5 of 6: Conditional (possible Steep Slope Overlay review, §906.08)"
    assert r.outcome is Outcome.ADVANCE


def test_partial_and_special_displays():
    withheld = ComponentScore("dimensional", None, None, "withheld", "x", short_reason="why")
    e = ease_result(Outcome.DEFER_RECORDS, [_k("use", 2), withheld, _k("environment", 1)], critical=False)
    assert e.display == "Partial: 3 of 4 known points; dimensional withheld (why)"
    assert e.total_low is None and e.band is None
    assert ease_result(Outcome.DEFER_RECORDS, [_k("use", 2), withheld, _k("environment", 1)],
                       critical=True).display == "Not scorable"
    assert ease_result(Outcome.OUT_OF_UNIVERSE, [None, None, None], critical=False).display == "n/a"


# --- coverage -----------------------------------------------------------------------


def test_coverage_derives_from_manifest_not_constants():
    assert evidence_coverage(ctx()) == {f"G{i}": True for i in range(1, 6)}
    m = manifest(fema_nfhl=SourceEntry("fema_nfhl", "2026-09-24", False, "x", "x"))
    assert evidence_coverage(ctx(manifest_obj=m))["G3"] is False
    m = manifest(condemned_properties=SourceEntry("condemned_properties", "2026-09-24", False, "x", "x"))
    assert evidence_coverage(ctx(manifest_obj=m))["G4"] is False
    m = manifest()
    del m["treasurer_sale_regulations"]
    assert evidence_coverage(ctx(manifest_obj=m))["G5"] is False
    assert evidence_coverage(ctx(advert_obj=None))["G5"] is False
    assert evidence_coverage(ctx(facts_kw=dict(county_gis_area_sf=None)))["G1"] is False
    assert evidence_coverage(ctx(rule_obj=None))["G2"] is False
    assert evidence_coverage(ctx(rule_obj=rule(dimensions_applicable=False, dimensions_encoded=False)))["G2"]


# --- staleness (adversarial case 8, synthetic fixture) --------------------------------


def test_stale_sale_status_source_warns():
    m = manifest(wprdc_treasury_sales=SourceEntry("wprdc_treasury_sales", "2026-09-10", True, "x", "SYNTHETIC"))
    (w,) = stale_source_warnings(m)
    assert "sale status may have changed by payment or court order" in w and "will be sold" not in w
    assert stale_source_warnings(manifest()) == []
    r = screen(ctx(manifest_obj=m))
    assert any("sale status may have changed" in x for x in r.warnings)
    assert r.outcome is Outcome.ADVANCE  # warning only; no decision change


def test_sale_date_passed_warning():
    assert sale_date_passed_warning("2026-10-02", date(2026, 10, 3))
    assert sale_date_passed_warning("2026-10-02", date(2026, 9, 26)) == []
    assert sale_date_passed_warning("2026-10-02", None) == []


# --- routing precedence ---------------------------------------------------------------


def test_routing_precedence():
    both = dict(condemned_case_active=True)
    assert screen(ctx(advert_obj=None, facts_kw=both)).outcome is Outcome.OUT_OF_UNIVERSE
    assert screen(ctx(treasury_kw=dict(usedesc="SINGLE FAMILY"), facts_kw=both)).outcome is Outcome.STRUCTURE
    ui = rule(district="UI", single_unit_permission="PROHIBITED", two_unit_permission="PROHIBITED",
              dimensions_applicable=False, dimensions_encoded=False)
    assert screen(ctx(rule_obj=ui, facts_kw=both)).outcome is Outcome.DEFER_RECORDS
    assert screen(ctx(rule_obj=ui)).outcome is Outcome.DO_NOT_ADVANCE
    assert screen(ctx(rule_obj=rule(dimensions_encoded=False))).outcome is Outcome.DEFER_RECORDS
    h = rule(site_standard_blocks_dimensional=True, site_standard="911.04.A.69")
    assert screen(ctx(rule_obj=h)).outcome is Outcome.DEFER_SITE
    assert screen(ctx()).outcome is Outcome.ADVANCE


def test_missing_rule_row_defers_without_crash():
    r = screen(ctx(rule_obj=None))
    assert r.outcome is Outcome.DEFER_RECORDS
    assert r.use.status == "withheld" and r.dimensional.status == "withheld"
    assert "not encoded" in "; ".join(r.barriers)


def test_derived_facts_and_cited_ids_exist():
    r = screen(ctx(facts_kw=dict(assess_lotarea_sf=1000.0, county_gis_area_sf=1500.0, possible_corner=True)))
    ids = {f.id for f in r.facts}
    assert derived_fact_id(PIN, "area_gap_pct") in ids
    assert derived_fact_id(PIN, "upset_to_assessed_land") in ids
    for f in r.facts:
        if f.source == "engine":
            assert f.evidence_class in ("derived", "approximate") and f.note
    for c in r.conflicts:
        assert set(c.fact_ids) <= ids
    for comp in (r.use, r.dimensional, r.environment):
        assert set(comp.fact_ids) <= ids


def test_replace_is_frozen_safe():
    # Engine never mutates inputs.
    c = ctx()
    before = replace(c.facts)
    screen(c)
    assert c.facts == before
