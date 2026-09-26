"""Property-style abstention tests: unknown inputs are never scored and never advance.

Each case feeds one or more unknown inputs (missing or invalid area, blank
setbacks, missing geometry, undetermined FEMA zone, failed screening-layer
queries) into an otherwise clean synthetic parcel that would Advance, over the
full cross product of combinations.
"""

from __future__ import annotations

import itertools

import pytest
from engine_builders import ctx, facts, manifest, rule

from lotline.engine import screen
from lotline.engine.hazards import score_environment
from lotline.models import Outcome, SourceEntry, sfha_status

LAYERS = ("landslide_prone", "slope25", "undermined", "fema_nfhl")

AREA_CASES = {
    "areas ok": {},
    "assess None": dict(assess_lotarea_sf=None),
    "gis None": dict(county_gis_area_sf=None),
    "both None": dict(assess_lotarea_sf=None, county_gis_area_sf=None),
    "gis 0": dict(county_gis_area_sf=0.0),  # built outside the loader: engine must still refuse
    "assess negative": dict(assess_lotarea_sf=-10.0),
}
GEOMETRY_CASES = {"geometry ok": {}, "short side None": dict(mbr_short_side_ft=None)}
SETBACK_CASES = {
    "setbacks ok": ({}, {}),
    "rear None": ({"rear_setback_ft": None}, {}),
    "exterior None, corner": ({"exterior_side_ft": None}, {"possible_corner": True}),
    "min lot None": ({"min_lot_sf": None}, {}),
}
FEMA_CASES = {"X": "X", "D": "D", "unrecognized": "ZONE Q"}
LAYER_CASES = {"all queried": (), **{f"{s} failed": (s,) for s in LAYERS}}


def _manifest(failed: tuple[str, ...]):
    m = manifest()
    for s in failed:
        m[s] = SourceEntry(s, "2026-09-24", False, "synthetic.csv", "synthetic")
    return m


CASES = list(itertools.product(AREA_CASES, GEOMETRY_CASES, SETBACK_CASES, FEMA_CASES, LAYER_CASES))


def _build(area, geom, setback, fema, layers):
    rule_kw, facts_kw = SETBACK_CASES[setback]
    zone = FEMA_CASES[fema]
    fk = {**AREA_CASES[area], **GEOMETRY_CASES[geom], **facts_kw,
          "fema_zone": zone, "fema_sfha": sfha_status(zone)}
    return ctx(facts_kw=fk, rule_obj=rule(**rule_kw), manifest_obj=_manifest(LAYER_CASES[layers]))


def test_clean_baseline_advances():
    r = screen(_build("areas ok", "geometry ok", "setbacks ok", "X", "all queried"))
    assert r.outcome is Outcome.ADVANCE and r.ease.display == "6 of 6: Apparently lower-discretion"


@pytest.mark.parametrize("case", CASES, ids=[" / ".join(c) for c in CASES])
def test_unknown_inputs_never_scored_and_never_advance(case):
    area, geom, setback, fema, layers = case
    r = screen(_build(*case))
    unknown_dim = area != "areas ok" or geom != "geometry ok" or setback != "setbacks ok"
    unknown_env = fema != "X" or layers != "all queried"

    if unknown_dim:
        assert r.dimensional.status == "withheld" and r.dimensional.low is None, case
    if unknown_env:
        assert r.environment.status == "withheld" and r.environment.low is None, case
    # Nothing unknown is ever reported as a known score of 0.
    for comp in (r.use, r.dimensional, r.environment):
        if comp.status == "withheld":
            assert comp.low is None and comp.high is None and comp.short_reason
    if unknown_dim or unknown_env:
        assert r.outcome is not Outcome.ADVANCE, case
        assert r.outcome is Outcome.DEFER_RECORDS
        assert r.ease.total_low is None and r.ease.display.startswith("Partial: ")
        # The Defer names what is missing: at least one barrier and one specific next check.
        assert r.barriers, case
        base = {"contextual setbacks (Ch. 925)", "survey", "title", "legal access", "utilities",
                "market demand/appraisal", "corner/frontage status"}
        specific = [c for c in r.next_checks
                    if c.check not in base and not c.check.startswith("Treasurer Sale terms")]
        assert specific, (case, [c.check for c in r.next_checks])
        for comp in (r.dimensional, r.environment):
            if comp.status == "withheld":
                assert f"{comp.name} withheld ({comp.short_reason})" in r.ease.display
    else:
        assert r.outcome is Outcome.ADVANCE


@pytest.mark.parametrize("layer", LAYERS)
def test_failed_layer_query_names_the_layer(layer):
    r = screen(ctx(manifest_obj=_manifest((layer,))))
    assert r.outcome is Outcome.DEFER_RECORDS
    assert any("environmental screening incomplete" in b for b in r.barriers)
    assert any(c.check.startswith("re-run screening layer query") for c in r.next_checks)


def test_failed_query_never_flags_or_clears_a_family():
    f = facts(slope25=True, undermined=True)
    e = score_environment("P", f, ("slope25",))
    assert e.status == "withheld" and e.low is None
    r = screen(ctx(facts_kw=dict(slope25=True), manifest_obj=_manifest(("slope25",))))
    assert r.hazard_families == [] and r.environment.status == "withheld"
    assert "Conditional (possible Steep Slope" not in r.ease.display  # no cap from an unqueried layer


@pytest.mark.parametrize("zone", ["D", "ZONE Q", "D + X"])
def test_undetermined_fema_zone_is_unknown_even_if_flag_says_false(zone):
    """A record built outside the loader with fema_sfha=False still cannot score zone D as clear."""
    r = screen(ctx(facts_kw=dict(fema_zone=zone, fema_sfha=False)))
    assert r.environment.status == "withheld" and r.outcome is Outcome.DEFER_RECORDS
    assert "floodplain determination" in [c.check for c in r.next_checks]


def test_blank_exterior_side_on_possible_corner_is_named():
    r = screen(ctx(facts_kw=dict(possible_corner=True), rule_obj=rule(exterior_side_ft=None)))
    assert r.outcome is Outcome.DEFER_RECORDS
    assert any("exterior side setback is not encoded (needed because the lot may be a corner)" in b
               for b in r.barriers)
    assert any(c.check.startswith("confirm district setbacks: exterior side") for c in r.next_checks)


def test_missing_area_source_is_named():
    r = screen(ctx(facts_kw=dict(county_gis_area_sf=None)))
    assert "lot area is missing from the County GIS record; conformity in all sources not established" \
        in r.barriers
    deed = next(c for c in r.next_checks if c.check == "deed and record-area reconciliation")
    assert "County GIS" in deed.trigger
