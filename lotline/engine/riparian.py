"""RIV riparian buffer screen (Pittsburgh Code §905.04.E.4.a). Pure functions.

§905.04.E.4.a(1): "No development is permitted within one hundred twenty-five
(125) feet of the Project Pool Elevation of the river, except as provided
herein." §905.04.B.4 fixes the Project Pool Elevation at 710 ft on all three
rivers. That is a contour, not a mapped line, so this module measures to a
public shoreline polygon (Allegheny County "Major Rivers", source
``river_hydrography``) as a stand-in and widens the answer by an uncertainty
band. The result is an approximate screening fact, never a determination.

Method (offline, no GIS library):
- Distance: the parcel's Treasury point (lat/lon) to the nearest river-polygon
  edge, in a local equirectangular plane centred on the point (WGS84 equatorial
  radius, cos(latitude) scaling on longitude). Across the few thousand feet
  that matter here the error is far below one foot, which is negligible next to
  the band below.
- Band: ± the full MBR diagonal (the source does not establish where the point
  sits within the lot, so the farthest MBR corner is conservatively allowed) ± a
  hydrography margin (the mapped shoreline vs. the 710 ft contour; see
  ``HYDROGRAPHY_MARGIN_FT``).
- Classes: the whole band beyond 125 ft -> outside; the whole band at or
  within 125 ft ("within" includes 125) -> inside; otherwise possibly within.

Callers pass geometry that a loader read; this module reads no files, no AI
output and no record text.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# Pittsburgh Code §905.04.E.4.a(1) (current text, ecode360 through 2026-09-16).
RIPARIAN_BUFFER_FT = 125.0
RIPARIAN_CITATION = "905.04.E.4.a"
# Mapped shoreline vs. the 710 ft Project Pool Elevation contour. The county
# polygons were digitized from aerial imagery near normal pool (710 ft is the
# Emsworth pool that the three rivers share in the city), so the gap is
# digitizing error plus pool fluctuation on the bank slope. Two independent
# county layers ("Major Rivers" and the 2004 "Hydrology Areas") differ by
# about 17 ft at the RIV-RM sale parcel; 25 ft covers that with room.
HYDROGRAPHY_MARGIN_FT = 25.0

OUTSIDE = "outside buffer"
INSIDE = "inside buffer"
POSSIBLY_WITHIN = "possibly within buffer (inside uncertainty)"

_EARTH_RADIUS_M = 6_378_137.0
_M_PER_FT = 0.3048

Ring = Sequence[tuple[float, float]]  # (lon, lat) vertices, closed or open


@dataclass(frozen=True)
class RiverPolygon:
    """One river polygon: an outer ring followed by any holes, as (lon, lat)."""

    name: str
    rings: tuple[tuple[tuple[float, float], ...], ...]


@dataclass(frozen=True)
class RiverDistance:
    distance_ft: float  # 0.0 when the point lies on the water
    river: str
    on_water: bool


@dataclass(frozen=True)
class RiparianResult:
    status: str  # OUTSIDE | INSIDE | POSSIBLY_WITHIN
    distance_ft: float
    low_ft: float
    high_ft: float
    river: str
    parcel_diagonal_ft: float
    margin_ft: float
    buffer_ft: float
    note: str


def _local_xy_ft(lon: float, lat: float, lon0: float, lat0: float) -> tuple[float, float]:
    k = _EARTH_RADIUS_M / _M_PER_FT
    return (math.radians(lon - lon0) * k * math.cos(math.radians(lat0)),
            math.radians(lat - lat0) * k)


def _segment_distance(ax: float, ay: float, bx: float, by: float) -> float:
    """Distance from the origin to segment AB."""
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length2))
    return math.hypot(ax + t * dx, ay + t * dy)


def _contains_origin(ring: Sequence[tuple[float, float]]) -> bool:
    inside = False
    n = len(ring)
    for i in range(n):
        (x1, y1), (x2, y2) = ring[i], ring[i - 1]
        if (y1 > 0) != (y2 > 0) and 0 < (x2 - x1) * (0 - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def distance_to_rivers(lat: float, lon: float, rivers: Iterable[RiverPolygon]) -> RiverDistance | None:
    """Minimum distance (ft) from a point to the nearest river-polygon edge.

    Returns None when no river geometry is given. A point on the water
    (inside an outer ring and not in a hole) gets distance 0.
    """
    best: RiverDistance | None = None
    for river in rivers:
        on_water = False
        for i, ring in enumerate(river.rings):
            pts = [_local_xy_ft(x, y, lon, lat) for x, y in ring]
            if len(pts) < 2:
                continue
            if len(pts) >= 3 and _contains_origin(pts):
                on_water = i == 0  # inside the outer ring; inside a hole means land
            for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
                d = _segment_distance(ax, ay, bx, by)
                if best is None or d < best.distance_ft:
                    best = RiverDistance(d, river.name, False)
        if on_water:
            return RiverDistance(0.0, river.name, True)
    return best


def mbr_diagonal_ft(short_side_ft: float | None, long_side_ft: float | None) -> float | None:
    if short_side_ft is None or long_side_ft is None or short_side_ft < 0 or long_side_ft < 0:
        return None
    return math.hypot(short_side_ft, long_side_ft)


def classify(
    distance_ft: float,
    positional_uncertainty_ft: float,
    *,
    margin_ft: float = HYDROGRAPHY_MARGIN_FT,
    buffer_ft: float = RIPARIAN_BUFFER_FT,
) -> tuple[str, float, float]:
    """(status, low_ft, high_ft) for a point distance and its uncertainty band."""
    spread = positional_uncertainty_ft + margin_ft
    low, high = max(0.0, distance_ft - spread), distance_ft + spread
    if low > buffer_ft:
        return OUTSIDE, low, high
    if high <= buffer_ft:
        return INSIDE, low, high
    return POSSIBLY_WITHIN, low, high


def riparian_screen(
    lat: float | None,
    lon: float | None,
    mbr_short_side_ft: float | None,
    mbr_long_side_ft: float | None,
    rivers: Iterable[RiverPolygon],
    *,
    margin_ft: float = HYDROGRAPHY_MARGIN_FT,
    buffer_ft: float = RIPARIAN_BUFFER_FT,
) -> RiparianResult | None:
    """Approximate §905.04.E.4.a screen. None when any input is missing (unknown, never 'outside')."""
    if lat is None or lon is None:
        return None
    diagonal = mbr_diagonal_ft(mbr_short_side_ft, mbr_long_side_ft)
    if diagonal is None:
        return None
    nearest = distance_to_rivers(lat, lon, rivers)
    if nearest is None:
        return None
    status, low, high = classify(nearest.distance_ft, diagonal, margin_ft=margin_ft, buffer_ft=buffer_ft)
    note = (
        f"Approximate: Treasury point to the nearest {nearest.river} shoreline edge "
        f"(Allegheny County Major Rivers polygon, local planar approximation) = "
        f"{nearest.distance_ft:,.0f} ft; band ±{diagonal:,.0f} ft (full lot MBR diagonal; "
        "source-point location within the lot is not established) "
        f"±{margin_ft:,.0f} ft (mapped shoreline vs. the 710 ft Project Pool Elevation) = "
        f"{low:,.0f}–{high:,.0f} ft against the {buffer_ft:,.0f} ft riparian buffer "
        f"(§{RIPARIAN_CITATION}). Not a survey; the Zoning Administrator determines the buffer line."
    )
    return RiparianResult(
        status=status, distance_ft=nearest.distance_ft, low_ft=low, high_ft=high,
        river=nearest.river, parcel_diagonal_ft=diagonal, margin_ft=margin_ft, buffer_ft=buffer_ft,
        note=note,
    )


__all__ = [
    "HYDROGRAPHY_MARGIN_FT", "INSIDE", "OUTSIDE", "POSSIBLY_WITHIN", "RIPARIAN_BUFFER_FT",
    "RIPARIAN_CITATION", "RiparianResult", "RiverDistance", "RiverPolygon", "classify",
    "distance_to_rivers", "mbr_diagonal_ft", "riparian_screen",
]
