"""Fetch and annotate real parcel-context imagery for every sale-feed parcel.

The County parcel polygon identifies the target; Esri World Imagery supplies
the pixels. The imagery acquisition date is not exposed by the export service,
so the generated metadata records it as unknown. These images are visual
evidence for a bounded multimodal cross-check, never engine inputs.

Run: ``uv run python scripts/fetch_parcel_imagery.py`` (network required).
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lotline.loaders import load_snapshot
from lotline.ui.viewmodels import load_demo_config

OUT = ROOT / "data" / "parcel_imagery"
COUNTY_QUERY = "https://gisdata.alleghenycounty.us/arcgis/rest/services/OPENDATA/Parcels/MapServer/0/query"
IMAGERY_EXPORT = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export"
ATTRIBUTION = "Source: Esri, Vantor, Earthstar Geographics, and the GIS User Community"


def _get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    target = url + "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            request = urllib.request.Request(target, headers={"User-Agent": "lotline-imagery-fetch"})
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except Exception:  # noqa: BLE001 - retry public GIS services
            if attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def _download(url: str, path: Path) -> None:
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "lotline-imagery-fetch"})
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read()
                if not body.startswith(b"\xff\xd8"):
                    raise RuntimeError("imagery service did not return a JPEG")
                path.write_bytes(body)
                return
        except Exception:  # noqa: BLE001 - retry public imagery service
            if attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))


def _ring(pin: str) -> list[tuple[float, float]]:
    payload = _get_json(COUNTY_QUERY, {
        "where": f"PIN='{pin}'", "outFields": "PIN,MAPBLOCKLOT", "returnGeometry": "true",
        "outSR": "4326", "f": "geojson",
    })
    features = payload.get("features", [])
    if len(features) != 1:
        raise RuntimeError(f"expected one County parcel polygon for {pin}, got {len(features)}")
    coords = features[0]["geometry"]["coordinates"]
    if features[0]["geometry"]["type"] == "MultiPolygon":
        coords = coords[0]
    return [(float(lon), float(lat)) for lon, lat in coords[0]]


def _bbox(ring: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    # Roughly 225×330 feet of context at Pittsburgh's latitude: enough to see
    # a street edge while keeping a typical narrow city parcel visually legible.
    half_y = max((max(ys) - min(ys)) * 1.25, 0.00045)
    half_x = max((max(xs) - min(xs)) * 1.25, 0.00040)
    return cx - half_x, cy - half_y, cx + half_x, cy + half_y


def _annotate(source: Path, target: Path, ring: list[tuple[float, float]],
              bbox: tuple[float, float, float, float]) -> None:
    image = Image.open(source).convert("RGBA")
    xmin, ymin, xmax, ymax = bbox
    points = [((lon - xmin) / (xmax - xmin) * image.width,
               (ymax - lat) / (ymax - ymin) * image.height) for lon, lat in ring]
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.polygon(points, fill=(255, 196, 0, 48), outline=(255, 230, 90, 255), width=7)
    cx = sum(x for x, _ in points) / len(points)
    cy = sum(y for _, y in points) / len(points)
    draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=(255, 255, 255, 255),
                 outline=(22, 62, 110, 255), width=4)
    draw.rounded_rectangle((14, 14, 365, 54), radius=8, fill=(12, 30, 55, 215))
    draw.text((28, 26), "TARGET: COUNTY PARCEL OUTLINE", fill=(255, 255, 255, 255))
    Image.alpha_composite(image, overlay).convert("RGB").save(
        target, format="JPEG", quality=88, optimize=True, progressive=True
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    snapshot = load_snapshot()
    config = load_demo_config(snapshot)
    demo_names = {pin: key for key, pin in config.parcels.items()}
    pins = list(snapshot.treasury)
    if len(pins) != 96:
        raise RuntimeError(f"expected the 96-parcel sale-feed cohort, got {len(pins)}")
    index: dict[str, Any] = {}
    try:
        prior_index = json.loads((OUT / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prior_index = {}
    retrieved = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def fetch_one(pin: str) -> tuple[str, dict[str, Any]]:
        key = demo_names.get(pin, f"parcel-{pin.lower()}")
        prior = prior_index.get(pin, {})
        stored_ring = prior.get("county_polygon_wgs84") if isinstance(prior, dict) else None
        ring = ([(float(lon), float(lat)) for lon, lat in stored_ring]
                if stored_ring else _ring(pin))
        bbox = _bbox(ring)
        export_params = {
            "bbox": ",".join(str(v) for v in bbox), "bboxSR": "4326", "imageSR": "3857",
            "size": "800,800", "format": "jpg", "transparent": "false", "f": "image",
        }
        raw = OUT / f".{key}-source.tmp.jpg"
        annotated = OUT / f"{key}-parcel-context.jpg"
        try:
            _download(IMAGERY_EXPORT + "?" + urllib.parse.urlencode(export_params), raw)
            _annotate(raw, annotated, ring, bbox)
        finally:
            raw.unlink(missing_ok=True)
        digest = hashlib.sha256(annotated.read_bytes()).hexdigest()
        item = {
            "file": annotated.name,
            "source": "Esri World Imagery + Allegheny County OPENDATA/Parcels outline",
            "attribution": ATTRIBUTION + "; parcel outline © Allegheny County DCS-GIS",
            "retrieved_utc": retrieved,
            "imagery_date": None,
            "bbox_wgs84": list(bbox),
            "county_polygon_wgs84": ring,
            "center_basis": "yellow outline is the County parcel polygon; white dot is its vertex-average center",
            "sha256": digest,
        }
        print(f"{key}: {annotated.name} {digest[:12]}", flush=True)
        return pin, item

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch_one, pin) for pin in pins]
        for future in as_completed(futures):
            pin, item = future.result()
            index[pin] = item
    (OUT / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
