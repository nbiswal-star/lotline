"""Read-only view model for committed scientific evaluation artifacts.

These values describe a frozen development experiment. They never enter the
screening engine and cannot change a parcel outcome.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RESULTS_PATH = Path(__file__).resolve().parents[2] / "data" / "validation_scale" / "results.json"
PROBLEM_SCALE_PATH = Path(__file__).resolve().parents[2] / "data" / "problem_scale" / "results.json"
MULTIMODAL_PATH = Path(__file__).resolve().parents[2] / "data" / "multimodal" / "results.json"
MULTIMODAL_REPEAT_PATH = Path(__file__).resolve().parents[2] / "data" / "multimodal" / "repeatability.json"


@dataclass(frozen=True)
class AIDelta:
    sample_n: int
    reference_positive_n: int
    reference_proxy_n: int
    ai_tp: int
    ai_fp: int
    ai_fn: int
    ai_precision: str
    ai_recall: str
    ai_f1: str
    baseline_name: str
    baseline_tp: int
    baseline_fp: int
    baseline_fn: int
    baseline_precision: str
    baseline_recall: str
    baseline_f1: str
    contextual_tp: int
    contextual_fp: int
    contextual_fn: int
    contextual_precision: str
    contextual_recall: str
    contextual_f1: str
    total_cost_usd: float


@dataclass(frozen=True)
class ProblemScale:
    vacant_unique: int
    condemned_unique: int
    overlap_unique: int
    overlap_pct_vacant: float
    overlap_pct_condemned: float
    assessment_as_of: str


@dataclass(frozen=True)
class MultimodalAudit:
    cohort_n: int
    valid_reads: int
    review_flags: int
    routed_structure_review_flags: int
    abstentions: int
    exact_repeat_agreement: int


def load_problem_scale(path: Path = PROBLEM_SCALE_PATH) -> ProblemScale | None:
    """Load the reproducible records-overlap count; fail closed on bad artifacts."""
    try:
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        dates = raw["assessment_as_of"]
        result = ProblemScale(
            vacant_unique=int(raw["vacant_unique"]),
            condemned_unique=int(raw["condemned_unique"]),
            overlap_unique=int(raw["overlap_unique"]),
            overlap_pct_vacant=float(raw["overlap_pct_vacant"]),
            overlap_pct_condemned=float(raw["overlap_pct_condemned"]),
            assessment_as_of=str(dates[0]) if isinstance(dates, list) and dates else "unknown",
        )
        if not (0 < result.overlap_unique <= result.vacant_unique and
                result.overlap_unique <= result.condemned_unique):
            return None
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return None


def load_multimodal_audit(path: Path = MULTIMODAL_PATH) -> MultimodalAudit | None:
    """Load bounded visual-audit counts; never recompute a decision in the UI."""
    try:
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        categories = raw["categories"]
        repeat = json.loads(MULTIMODAL_REPEAT_PATH.read_text(encoding="utf-8"))
        result = MultimodalAudit(
            cohort_n=int(raw["cohort_n"]),
            valid_reads=int(raw["valid_reads"]),
            review_flags=int(raw["structure_discordant_n"]),
            routed_structure_review_flags=int(raw["routed_structure_discordant_n"]),
            abstentions=int(categories["unclear"]),
            exact_repeat_agreement=int(repeat["exact_category_agreement_n"]),
        )
        if not (result.cohort_n == result.valid_reads == 96 and
                0 <= result.routed_structure_review_flags <= result.review_flags <= 96 and
                0 <= result.abstentions <= 96):
            return None
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return None


def load_ai_delta(path: Path = RESULTS_PATH) -> AIDelta | None:
    """Return validated headline fields, or ``None`` if the artifact is absent/malformed."""
    try:
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        metrics = raw["metrics"]
        ai, baseline, contextual = metrics["AI"], metrics[raw["best"]], metrics["B5"]
        positive = int(ai["tp"]) + int(ai["fn"])
        proxy = int(ai["tn"]) + int(ai["fp"])
        sample = positive + proxy
        if sample <= 0 or positive <= 0 or proxy <= 0:
            return None
        return AIDelta(
            sample_n=sample,
            reference_positive_n=positive,
            reference_proxy_n=proxy,
            ai_tp=int(ai["tp"]), ai_fp=int(ai["fp"]), ai_fn=int(ai["fn"]),
            ai_precision=str(ai["precision"]), ai_recall=str(ai["recall"]), ai_f1=str(ai["f1"]),
            baseline_name=str(raw["best"]),
            baseline_tp=int(baseline["tp"]), baseline_fp=int(baseline["fp"]),
            baseline_fn=int(baseline["fn"]), baseline_precision=str(baseline["precision"]),
            baseline_recall=str(baseline["recall"]), baseline_f1=str(baseline["f1"]),
            contextual_tp=int(contextual["tp"]), contextual_fp=int(contextual["fp"]),
            contextual_fn=int(contextual["fn"]),
            contextual_precision=str(contextual["precision"]),
            contextual_recall=str(contextual["recall"]),
            contextual_f1=str(contextual["f1"]),
            total_cost_usd=float(raw["all_cost"]),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def comparison_rows(delta: AIDelta) -> list[dict[str, object]]:
    """Compact, screen-ready comparison without interpreting the proxy as site truth."""
    return [
        {
            "Method": "Frozen AI reader (k=1)",
            "TP / discordant / missed": f"{delta.ai_tp} / {delta.ai_fp} / {delta.ai_fn}",
            "Precision vs proxy": delta.ai_precision,
            "Recall vs proxy": delta.ai_recall,
            "F1": delta.ai_f1,
        },
        {
            "Method": f"Highest-F1 pre-call simple rule ({delta.baseline_name})",
            "TP / discordant / missed": (
                f"{delta.baseline_tp} / {delta.baseline_fp} / {delta.baseline_fn}"
            ),
            "Precision vs proxy": delta.baseline_precision,
            "Recall vs proxy": delta.baseline_recall,
            "F1": delta.baseline_f1,
        },
        {
            "Method": "Post-hoc contextual deterministic rule (B5)",
            "TP / discordant / missed": (
                f"{delta.contextual_tp} / {delta.contextual_fp} / {delta.contextual_fn}"
            ),
            "Precision vs proxy": delta.contextual_precision,
            "Recall vs proxy": delta.contextual_recall,
            "F1": delta.contextual_f1,
        },
    ]
