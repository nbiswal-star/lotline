"""Write the frozen, app-readable summary of the full-cohort visual audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.multimodal import summarize  # noqa: E402


def main() -> None:
    target = ROOT / "data" / "multimodal" / "results.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summarize(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
