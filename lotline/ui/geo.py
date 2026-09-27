"""Point locations for the sale-pipeline map. Presentation only; no decisions.

Coordinates come from the frozen WPRDC Treasury Sales CSV (``lat``/``lon``),
read with an explicit column allowlist and ``dtype=str`` like every loader read.
Colors are keyed to engine outcomes; nothing here computes an outcome.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from lotline.loaders import DATA_DIR, TREASURY_FILE
from lotline.models import Outcome, ScreeningResult, Snapshot

GEO_COLUMNS: tuple[str, ...] = ("pin", "lat", "lon")

# Outcome family -> (legend label, RGBA fill, RGBA outline). Alpha 0 fill = hollow marker.
FAMILY_STYLE: dict[str, tuple[str, list[int], list[int]]] = {
    "advance": ("Advance to staff review", [46, 139, 87, 230], [29, 106, 51, 255]),
    "defer": ("Defer (site or records)", [230, 160, 30, 230], [134, 81, 0, 255]),
    "dna": ("Do not advance (housing)", [110, 118, 128, 230], [61, 70, 82, 255]),
    "structure": ("Structure (routed out)", [200, 205, 212, 200], [150, 158, 168, 255]),
    "out": ("Not in City advertisement", [0, 0, 0, 0], [120, 128, 140, 255]),
}

FAMILY_OF: dict[Outcome, str] = {
    Outcome.ADVANCE: "advance",
    Outcome.DEFER_SITE: "defer",
    Outcome.DEFER_RECORDS: "defer",
    Outcome.DO_NOT_ADVANCE: "dna",
    Outcome.SIDE_YARD: "dna",
    Outcome.STRUCTURE: "structure",
    Outcome.OUT_OF_UNIVERSE: "out",
}


@dataclass(frozen=True)
class MapPoint:
    pin: str
    lat: float
    lon: float
    family: str
    address: str
    outcome: str
    ease: str


def load_coordinates(data_dir: Path = DATA_DIR) -> dict[str, tuple[float, float]]:
    """PIN -> (lat, lon). A missing file or bad value just drops that point."""
    try:
        df = pd.read_csv(Path(data_dir) / TREASURY_FILE, usecols=list(GEO_COLUMNS), dtype=str,
                         keep_default_na=False)
    except (OSError, ValueError):
        return {}
    out: dict[str, tuple[float, float]] = {}
    for pin, lat, lon in df.itertuples(index=False):
        try:
            la, lo = float(lat), float(lon)
        except ValueError:
            continue
        if -90 <= la <= 90 and -180 <= lo <= 180:
            out[pin.strip()] = (la, lo)
    return out


def map_points(snapshot: Snapshot, results: Mapping[str, ScreeningResult],
               coords: Mapping[str, tuple[float, float]]) -> list[MapPoint]:
    pts: list[MapPoint] = []
    for pin, r in results.items():
        if pin not in coords:
            continue
        t = snapshot.treasury[pin]
        lat, lon = coords[pin]
        pts.append(MapPoint(
            pin=pin, lat=lat, lon=lon, family=FAMILY_OF[r.outcome],
            address=t.address.split(",")[0].title(),
            outcome=r.outcome.value.replace("(routing) ", "Routed: "),
            ease=r.ease.display if r.ease else "n/a",
        ))
    # Draw routed records first so screened lots sit on top.
    order = {"out": 0, "structure": 1, "dna": 2, "defer": 3, "advance": 4}
    return sorted(pts, key=lambda p: order[p.family])


def family_counts(points: list[MapPoint]) -> dict[str, int]:
    counts = {k: 0 for k in FAMILY_STYLE}
    for p in points:
        counts[p.family] += 1
    return counts
