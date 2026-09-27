"""Bounded multimodal parcel-imagery observer.

Claude may classify a small, fixed vocabulary of visible image properties. It
cannot write prose, identify a parcel boundary, or change any engine result.
Code compares those categories with already-verified record labels and keeps
discordance explicit. Cached results are accepted only while the image bytes
still match their recorded hash.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .client import AIOutputError, AIUnavailable, call_structured

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "data" / "parcel_imagery" / "index.json"
CACHE = ROOT / "data" / "ai_cache" / "visual"

STRUCTURE = frozenset({"clearly_visible", "not_visible", "unclear"})
SURFACE = frozenset({"mostly_vegetated", "mixed", "mostly_impervious", "unclear"})
ACCESS = frozenset({"street_edge_visible", "not_visible", "unclear"})
QUALITY = frozenset({"adequate", "limited", "unusable"})
LIMITS = frozenset({
    "imagery_date_unknown", "parcel_boundary_not_visible", "tree_cover", "shadows",
    "resolution", "off_nadir", "none_observed",
})

SYSTEM = """You are a conservative aerial-imagery observer for housing due diligence.
Return only the requested categorical JSON. Describe only what is visibly observable in this image.
The yellow outline is a public County parcel polygon, not a survey or legal boundary; the image date
may be unknown. For structure_footprint, use clearly_visible when a coherent building roof or
footprint is visibly and materially inside the yellow outline; use not_visible when no coherent
building footprint is visible inside it; use unclear when trees, shadows, resolution, or boundary
alignment prevent that distinction. Never infer ownership, legal
access, habitability, vacancy, demolition completion, zoning compliance, safety, environmental
condition, development feasibility, or whether a parcel is suitable for housing. Do not count a
neighboring roof outside the outline. A visible footprint is not proof of current occupancy or use."""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "structure_footprint": {"type": "string", "enum": sorted(STRUCTURE)},
        "surface_cover": {"type": "string", "enum": sorted(SURFACE)},
        "street_context": {"type": "string", "enum": sorted(ACCESS)},
        "image_quality": {"type": "string", "enum": sorted(QUALITY)},
        "limitations": {"type": "array", "items": {"type": "string", "enum": sorted(LIMITS)}},
    },
    "required": ["structure_footprint", "surface_cover", "street_context", "image_quality", "limitations"],
}
USER_INSTRUCTION = (
    "Classify only the fixed visual fields inside the yellow target polygon. "
    "The outline is a County GIS parcel polygon, not a survey; the imagery "
    "acquisition date is not provided."
)
CONTRACT_SHA256 = hashlib.sha256(json.dumps(
    {"system": SYSTEM, "user": USER_INSTRUCTION, "schema": SCHEMA},
    sort_keys=True, separators=(",", ":")
).encode()).hexdigest()


@dataclass(frozen=True)
class ImageAsset:
    pin: str
    path: Path
    source: str
    attribution: str
    retrieved_utc: str
    imagery_date: str | None
    center_basis: str
    sha256: str


@dataclass(frozen=True)
class VisualRead:
    structure_footprint: str
    surface_cover: str
    street_context: str
    image_quality: str
    limitations: tuple[str, ...]
    model: str
    cached: bool
    image_sha256: str
    created_utc: str | None = None
    request_id: str | None = None


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def asset_for(pin: str, index_path: Path = INDEX) -> ImageAsset | None:
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))[pin]
        path = index_path.parent / str(raw["file"])
        expected = str(raw["sha256"])
        if not path.is_file() or _hash(path) != expected:
            return None
        return ImageAsset(pin, path, str(raw["source"]), str(raw["attribution"]),
                          str(raw["retrieved_utc"]), raw.get("imagery_date"),
                          str(raw["center_basis"]), expected)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _validated(raw: Any, *, model: str, cached: bool, image_sha256: str,
               created_utc: str | None = None, request_id: str | None = None) -> VisualRead:
    if not isinstance(raw, dict) or set(raw) != {
        "structure_footprint", "surface_cover", "street_context", "image_quality", "limitations"
    }:
        raise AIOutputError("visual response fields did not match the contract")
    limits = raw["limitations"]
    if (raw["structure_footprint"] not in STRUCTURE or raw["surface_cover"] not in SURFACE or
            raw["street_context"] not in ACCESS or raw["image_quality"] not in QUALITY or
            not isinstance(limits, list) or len(limits) > 6 or
            any(x not in LIMITS for x in limits) or len(limits) != len(set(limits))):
        raise AIOutputError("visual response values did not match the fixed vocabulary")
    return VisualRead(str(raw["structure_footprint"]), str(raw["surface_cover"]),
                      str(raw["street_context"]), str(raw["image_quality"]), tuple(limits),
                      model, cached, image_sha256, created_utc, request_id)


def _cache_path(pin: str, cache_dir: Path = CACHE) -> Path:
    return cache_dir / f"{hashlib.sha256(pin.encode()).hexdigest()[:16]}.json"


def load_cached(asset: ImageAsset, cache_dir: Path = CACHE) -> VisualRead | None:
    try:
        raw = json.loads(_cache_path(asset.pin, cache_dir).read_text(encoding="utf-8"))
        if (raw["image_sha256"] != asset.sha256 or
                raw.get("contract_sha256") != CONTRACT_SHA256):
            return None
        return _validated(raw["result"], model=str(raw["model"]), cached=True,
                          image_sha256=asset.sha256, created_utc=raw.get("created_utc"),
                          request_id=raw.get("request_id"))
    except (OSError, ValueError, KeyError, TypeError, AIOutputError):
        return None


def observe(asset: ImageAsset, *, client: Any = None, save_cache: bool = True,
            cache_dir: Path = CACHE) -> VisualRead:
    mime = "image/jpeg" if asset.path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": mime,
                                      "data": base64.b64encode(asset.path.read_bytes()).decode("ascii")}},
        {"type": "text", "text": USER_INSTRUCTION},
    ]
    response = call_structured(SYSTEM, content, SCHEMA, client=client, effort="medium", max_tokens=1000)
    created = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    read = _validated(response.data, model=response.model, cached=False, image_sha256=asset.sha256,
                      created_utc=created, request_id=response.request_id)
    if save_cache:
        cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {"image_sha256": asset.sha256, "contract_sha256": CONTRACT_SHA256,
                   "model": response.model, "created_utc": created,
                   "request_id": response.request_id, "result": response.data}
        _cache_path(asset.pin, cache_dir).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                                                     encoding="utf-8")
    return read


def cross_modal_status(read: VisualRead, evidence_items: Any, *, structured_vacant: bool = False,
                       structured_structure: bool = False) -> str:
    """Deterministic comparison; never an engine decision or current-condition determination."""
    labels = {
        str(getattr(item, "indicates_code", "") or getattr(item, "indicates", ""))
        for item in (evidence_items or ())
    }
    present = "structure_present" in labels
    removed = "structure_removed_or_demolished" in labels
    if read.image_quality == "unusable" or read.structure_footprint == "unclear":
        return "Image does not resolve the record evidence"
    if read.structure_footprint == "clearly_visible" and removed:
        return "Visual–record discordance: a structure-like footprint is visible alongside a removal-labelled record"
    if read.structure_footprint == "clearly_visible" and present:
        return "Image is visually consistent with a structure-present record; neither establishes current condition"
    if read.structure_footprint == "not_visible" and present:
        return "Visual–record discordance: no clear footprint is visible alongside a structure-present record"
    if read.structure_footprint == "not_visible" and removed:
        return "Image is visually consistent with removal-labelled evidence; absence in imagery is not proof"
    if read.structure_footprint == "clearly_visible" and structured_structure:
        return "Image is visually consistent with the assessment's structure classification; neither establishes current condition"
    if read.structure_footprint == "not_visible" and structured_structure:
        return "Visual–record discordance: no clear footprint is visible despite the assessment's structure classification"
    if read.structure_footprint == "not_visible" and structured_vacant:
        return "Image is visually consistent with the assessment's vacant-land classification; neither proves current condition"
    if read.structure_footprint == "clearly_visible" and structured_vacant:
        return "Visual–record discordance: a structure-like footprint is visible despite the vacant-land classification"
    return "Image and records address different or insufficiently specific conditions"


__all__ = ["ImageAsset", "VisualRead", "asset_for", "cross_modal_status", "load_cached", "observe"]
