from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageStat

from lotline.ai import visual
from lotline.ai.evidence_checks import evidence_checks
from lotline.loaders import load_snapshot
from lotline.ui.ai_panels import EvidenceItemVM, headline


def _item(*, quote: str, indicates: str) -> SimpleNamespace:
    return SimpleNamespace(source_id="pli_violations", record_id="CF-1", record_date="2026-01-02",
                           quote=quote, indicates=indicates)


def test_withheld_hearsay_cannot_be_repromoted_into_headline_or_check() -> None:
    quote = "Owner claims property is demolished per neighbor, which inspector found false."
    vm = EvidenceItemVM("CF-1", "pli_violations", "2026-01-02", "findings", quote,
                        "label not verified — quote only", "", None, None, "unverified_label")
    assert headline([vm]) is None
    digest = SimpleNamespace(status="verified", items=(_item(quote=quote, indicates="unverified_label"),))
    assert evidence_checks(digest) == []


def test_verified_structure_semantics_can_prompt_bounded_check_and_headline() -> None:
    quote = "Property is demolished."
    vm = EvidenceItemVM("CF-1", "pli_violations", "2026-01-02", "findings", quote,
                        "structure removed or demolished", "", None, None,
                        "structure_removed_or_demolished")
    assert quote in (headline([vm]) or "")
    digest = SimpleNamespace(status="verified", items=(
        _item(quote=quote, indicates="structure_removed_or_demolished"),))
    checks = evidence_checks(digest)
    assert len(checks) == 1 and "demolished 2026" in checks[0].check


def test_asset_hash_and_cache_fail_closed(tmp_path: Path) -> None:
    image = tmp_path / "image.jpg"
    image.write_bytes(b"real-image-bytes")
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"P": {
        "file": image.name, "source": "source", "attribution": "credit",
        "retrieved_utc": "2026-09-27T00:00:00Z", "imagery_date": None,
        "center_basis": "County outline", "sha256": digest,
    }}))
    asset = visual.asset_for("P", index)
    assert asset is not None
    cache = tmp_path / "cache"
    cache.mkdir()
    cache_path = cache / f"{hashlib.sha256(b'P').hexdigest()[:16]}.json"
    result = {"structure_footprint": "unclear", "surface_cover": "mixed",
              "street_context": "street_edge_visible", "image_quality": "limited",
              "limitations": ["imagery_date_unknown", "parcel_boundary_not_visible"]}
    cache_path.write_text(json.dumps({"image_sha256": digest,
                                      "contract_sha256": visual.CONTRACT_SHA256,
                                      "model": "fake", "result": result}))
    assert visual.load_cached(asset, cache) is not None
    cache_path.write_text(json.dumps({"image_sha256": digest,
                                      "contract_sha256": "stale-contract",
                                      "model": "fake", "result": result}))
    assert visual.load_cached(asset, cache) is None
    image.write_bytes(b"tampered")
    assert visual.asset_for("P", index) is None


def test_cross_modal_comparison_is_deterministic_and_non_decisional() -> None:
    read = visual.VisualRead("clearly_visible", "mixed", "street_edge_visible", "adequate",
                             ("imagery_date_unknown",), "fake", True, "hash")
    removed = [SimpleNamespace(indicates="structure_removed_or_demolished")]
    present = [SimpleNamespace(indicates="structure_present")]
    assert visual.cross_modal_status(read, removed).startswith("Visual–record discordance")
    assert "consistent" in visual.cross_modal_status(read, present)


def test_cross_modal_comparison_uses_verified_code_from_ui_view_model() -> None:
    read = visual.VisualRead("clearly_visible", "mixed", "street_edge_visible", "adequate",
                             ("imagery_date_unknown",), "fake", True, "hash")
    item = EvidenceItemVM("CF-1", "pli_violations", "2026-01-02", "findings",
                          "Property is demolished.", "structure removed or demolished", "", None,
                          None, "structure_removed_or_demolished")
    status = visual.cross_modal_status(read, [item], structured_vacant=True)
    assert status.startswith("Visual–record discordance")
    assert "removal-labelled record" in status


def test_contract_hash_covers_the_complete_model_instruction() -> None:
    expected = hashlib.sha256(json.dumps(
        {"system": visual.SYSTEM, "user": visual.USER_INSTRUCTION, "schema": visual.SCHEMA},
        sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    assert visual.CONTRACT_SHA256 == expected
    changed = hashlib.sha256(json.dumps(
        {"system": visual.SYSTEM, "user": visual.USER_INSTRUCTION + " changed", "schema": visual.SCHEMA},
        sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    assert changed != visual.CONTRACT_SHA256


def test_every_sale_feed_parcel_has_hash_verified_imagery_and_ai_read() -> None:
    snapshot = load_snapshot()
    pins = list(snapshot.treasury)
    assert len(pins) == 96
    for pin in pins:
        asset = visual.asset_for(pin)
        assert asset is not None
        assert visual.load_cached(asset) is not None


def test_every_committed_image_is_nonblank_and_contains_the_target_overlay() -> None:
    snapshot = load_snapshot()
    for pin in snapshot.treasury:
        asset = visual.asset_for(pin)
        assert asset is not None
        with Image.open(asset.path).convert("RGB") as image:
            assert image.size == (800, 800)
            assert min(ImageStat.Stat(image).stddev) > 10
            # Sample every fourth pixel. JPEG compression softens the exact
            # overlay color, so use a conservative yellow neighborhood.
            yellow = sum(
                1 for y in range(0, 800, 4) for x in range(0, 800, 4)
                if (lambda rgb: rgb[0] > 180 and rgb[1] > 140 and rgb[2] < 150)(image.getpixel((x, y)))
            )
            assert yellow > 20


def test_structured_vacant_comparison_never_claims_proof() -> None:
    read = visual.VisualRead("not_visible", "mostly_vegetated", "street_edge_visible", "adequate",
                             ("imagery_date_unknown",), "fake", True, "hash")
    status = visual.cross_modal_status(read, (), structured_vacant=True)
    assert "consistent" in status
    assert "neither proves" in status


def test_structured_structure_discordance_is_review_signal() -> None:
    read = visual.VisualRead("not_visible", "mostly_vegetated", "street_edge_visible", "adequate",
                             ("imagery_date_unknown",), "fake", True, "hash")
    status = visual.cross_modal_status(read, (), structured_structure=True)
    assert status.startswith("Visual–record discordance")
    assert "assessment's structure classification" in status
