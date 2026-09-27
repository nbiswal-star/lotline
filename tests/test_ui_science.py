from pathlib import Path

from lotline.ui.science import (
    comparison_rows,
    load_ai_delta,
    load_multimodal_audit,
    load_problem_scale,
)


def test_committed_ai_delta_artifact_is_readable() -> None:
    delta = load_ai_delta()
    assert delta is not None
    assert (delta.sample_n, delta.reference_positive_n, delta.reference_proxy_n) == (150, 75, 75)
    assert (delta.ai_tp, delta.ai_fp, delta.ai_fn) == (30, 0, 45)
    assert (delta.baseline_name, delta.baseline_tp, delta.baseline_fp) == ("B4", 46, 15)
    assert (delta.contextual_tp, delta.contextual_fp, delta.contextual_fn) == (35, 2, 40)
    assert len(comparison_rows(delta)) == 3


def test_ai_delta_loader_fails_closed(tmp_path: Path) -> None:
    assert load_ai_delta(tmp_path / "missing.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    assert load_ai_delta(bad) is None


def test_committed_problem_scale_artifact_is_readable() -> None:
    scale = load_problem_scale()
    assert scale is not None
    assert (scale.vacant_unique, scale.condemned_unique, scale.overlap_unique) == (22354, 2895, 536)
    assert (scale.overlap_pct_vacant, scale.overlap_pct_condemned) == (2.4, 18.5)


def test_problem_scale_loader_fails_closed(tmp_path: Path) -> None:
    assert load_problem_scale(tmp_path / "missing.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text('{"vacant_unique": 1}', encoding="utf-8")
    assert load_problem_scale(bad) is None


def test_committed_multimodal_audit_is_readable() -> None:
    audit = load_multimodal_audit()
    assert audit is not None
    assert (audit.cohort_n, audit.valid_reads) == (96, 96)
    assert (audit.review_flags, audit.routed_structure_review_flags, audit.abstentions) == (36, 29, 45)
    assert audit.exact_repeat_agreement == 93


def test_multimodal_audit_loader_fails_closed(tmp_path: Path) -> None:
    assert load_multimodal_audit(tmp_path / "missing.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text('{"cohort_n": 96}', encoding="utf-8")
    assert load_multimodal_audit(bad) is None
