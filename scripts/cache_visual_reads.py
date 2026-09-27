"""Run the bounded Claude visual observer for all 96 sale-feed parcels.

This is an explicit, optional online preparation step. The app itself remains
offline-first and re-verifies each cached result against the exact image hash.

Run: ``uv run python scripts/cache_visual_reads.py``.
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lotline.ai import visual  # noqa: E402
from lotline.loaders import load_snapshot  # noqa: E402


def main() -> None:
    snapshot = load_snapshot()
    pins = list(snapshot.treasury)
    if len(pins) != 96:
        raise RuntimeError(f"expected the 96-parcel sale-feed cohort, got {len(pins)}")

    def read_one(number: int, pin: str) -> tuple[int, visual.VisualRead]:
        asset = visual.asset_for(pin)
        if asset is None:
            raise RuntimeError(f"missing or hash-invalid parcel image at cohort position {number}")
        return number, visual.observe(asset)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(read_one, number, pin) for number, pin in enumerate(pins, start=1)]
        for future in as_completed(futures):
            number, read = future.result()
            print(
                f"{number:02d}/96 {read.structure_footprint} · {read.surface_cover} · "
                f"{read.image_quality}"
            )


if __name__ == "__main__":
    main()
