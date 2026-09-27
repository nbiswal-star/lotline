"""RIV riparian buffer screen (§905.04.E.4.a): pure classification plus the cached geometry."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from lotline.engine import riparian
from lotline.engine.riparian import (
    INSIDE,
    OUTSIDE,
    POSSIBLY_WITHIN,
    RiverPolygon,
    classify,
    distance_to_rivers,
    mbr_half_diagonal_ft,
    riparian_screen,
)
from lotline.loaders import load_parcel_points, load_river_geometry

WALCOTT = "0042D00039000000"  # RIV-RM, Esplen
LAT0, LON0 = 40.46, -80.05
FT_PER_DEG_LAT = math.radians(1) * 6_378_137.0 / 0.3048


def _lat_offset(feet: float) -> float:
    return feet / FT_PER_DEG_LAT


def _river_south_of(feet: float, *, hole: bool = False) -> RiverPolygon:
    """A wide east-west 'river' whose north shoreline lies ``feet`` south of (LAT0, LON0)."""
    north = LAT0 - _lat_offset(feet)
    south = north - 0.01
    outer = ((LON0 - 0.05, south), (LON0 + 0.05, south), (LON0 + 0.05, north), (LON0 - 0.05, north))
    rings = (outer,)
    if hole:  # an island around (LAT0 - 1000 ft)
        c = LAT0 - _lat_offset(feet) - 0.004
        rings += (((LON0 - 0.001, c - 0.001), (LON0 + 0.001, c - 0.001),
                   (LON0 + 0.001, c + 0.001), (LON0 - 0.001, c + 0.001)),)
    return RiverPolygon("Test River", rings)


# --------------------------------------------------------------------------
# Classification boundaries (125 ft buffer, band = half diagonal + margin)
# --------------------------------------------------------------------------


def test_constants_match_code_text() -> None:
    assert riparian.RIPARIAN_BUFFER_FT == 125.0
    assert riparian.RIPARIAN_CITATION == "905.04.E.4.a"
    assert riparian.HYDROGRAPHY_MARGIN_FT == 25.0


def test_outside_needs_the_whole_band_beyond_125() -> None:
    assert classify(125 + 50 + 25 + 0.01, 50)[0] == OUTSIDE
    # low == 125 exactly is "within 125 feet": not outside.
    assert classify(125 + 50 + 25, 50)[0] == POSSIBLY_WITHIN


def test_inside_needs_the_whole_band_within_125() -> None:
    assert classify(125 - 50 - 25, 50)[0] == INSIDE  # high == 125 counts as within
    assert classify(125 - 50 - 25 + 0.01, 50)[0] == POSSIBLY_WITHIN


def test_band_is_clamped_at_zero_and_symmetric() -> None:
    status, low, high = classify(10, 60)
    assert (status, low, high) == (INSIDE, 0.0, 95.0)
    status, low, high = classify(400, 60, margin_ft=0)
    assert (low, high) == (340, 460)


def test_point_straddling_the_line_is_possibly_within() -> None:
    assert classify(125, 60)[0] == POSSIBLY_WITHIN
    assert classify(0, 200)[0] == POSSIBLY_WITHIN  # a huge lot can reach past the buffer


def test_half_diagonal() -> None:
    assert mbr_half_diagonal_ft(30, 40) == 25
    assert mbr_half_diagonal_ft(None, 40) is None
    assert mbr_half_diagonal_ft(-1, 40) is None


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------


@pytest.mark.parametrize("feet", [50.0, 125.0, 647.0, 3000.0])
def test_distance_to_a_straight_shore(feet: float) -> None:
    d = distance_to_rivers(LAT0, LON0, [_river_south_of(feet)])
    assert d is not None and not d.on_water
    assert d.distance_ft == pytest.approx(feet, abs=0.5)


def test_point_on_water_is_zero_and_inside() -> None:
    river = _river_south_of(-300)  # shoreline 300 ft north: the point is on the water
    d = distance_to_rivers(LAT0, LON0, [river])
    assert d is not None and d.on_water and d.distance_ft == 0.0
    assert riparian_screen(LAT0, LON0, 20, 100, [river]).status == INSIDE


def test_island_hole_is_land() -> None:
    river = _river_south_of(0, hole=True)
    c = LAT0 - 0.004
    d = distance_to_rivers(c, LON0, [river])
    assert d is not None and not d.on_water and d.distance_ft > 0


def test_nearest_of_several_rivers() -> None:
    far, near = _river_south_of(900), RiverPolygon("Near", _river_south_of(200).rings)
    d = distance_to_rivers(LAT0, LON0, [far, near])
    assert d.river == "Near" and d.distance_ft == pytest.approx(200, abs=0.5)


def test_screen_classes_on_synthetic_shores() -> None:
    # 26 x 118 lot: half diagonal about 60.4 ft; band about +/- 85.4 ft.
    assert riparian_screen(LAT0, LON0, 26, 118, [_river_south_of(400)]).status == OUTSIDE
    assert riparian_screen(LAT0, LON0, 26, 118, [_river_south_of(150)]).status == POSSIBLY_WITHIN
    assert riparian_screen(LAT0, LON0, 26, 118, [_river_south_of(30)]).status == INSIDE


def test_missing_inputs_are_unknown_not_outside() -> None:
    river = [_river_south_of(400)]
    assert riparian_screen(None, LON0, 26, 118, river) is None
    assert riparian_screen(LAT0, LON0, None, 118, river) is None
    assert riparian_screen(LAT0, LON0, 26, 118, []) is None


# --------------------------------------------------------------------------
# Cached County hydrography and the RIV-RM sale parcel
# --------------------------------------------------------------------------


def test_cached_hydrography_loads_three_rivers() -> None:
    names = {r.name for r in load_river_geometry()}
    assert names == {"Allegheny River", "Monongahela River", "Ohio River"}


def test_missing_geometry_file_is_empty(tmp_path: Path) -> None:
    assert load_river_geometry(tmp_path) == ()
    (tmp_path / "geo").mkdir()
    (tmp_path / "geo" / "rivers_allegheny_county.geojson").write_text("{not json")
    assert load_river_geometry(tmp_path) == ()


def test_walcott_is_outside_the_riparian_buffer() -> None:
    lat, lon = load_parcel_points()[WALCOTT]
    result = riparian_screen(lat, lon, 26, 118, load_river_geometry())
    assert result is not None
    assert result.status == OUTSIDE
    assert result.river == "Ohio River"
    assert 600 < result.distance_ft < 700
    assert result.low_ft > riparian.RIPARIAN_BUFFER_FT
    assert "905.04.E.4.a" in result.note and "Approximate" in result.note
