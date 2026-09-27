"""Evaluation package (evaluation/) invariants: cohort, matrix, conformance,
sensitivity, missingness and reproducibility experiments.

These run the experiments in-process (under a second in total) and assert the
key scientific invariants. The evaluation package is never imported by app code.
"""

from __future__ import annotations

import pytest

from evaluation import cohort, conformance, matrix, missingness, repro, sensitivity
from evaluation.common import Section, md_table


@pytest.fixture(scope="module")
def sections() -> dict[str, Section]:
    return {m.__name__.split(".")[-1]: m.run() for m in (cohort, matrix, conformance, sensitivity,
                                                          missingness, repro)}


@pytest.mark.parametrize("name", ["cohort", "matrix", "conformance", "sensitivity", "missingness", "repro"])
def test_section_assertions_all_hold(sections, name):
    s = sections[name]
    failed = [a for a in s.assertions if not a["passed"]]
    assert s.status == "ok" and not failed, failed
    assert "What this does and does not show" in s.markdown


def test_cohort_counts_and_runtime_agreement(sections):
    d = sections["cohort"].data
    assert d["counts"] == {"treasury": 96, "advertised": 77, "matched": 77, "not_advertised": 19,
                           "price_pass": 77, "advertised_structures": 63, "advertised_vacant": 14}
    assert d["runtime_agreement"]["matched"] == 77
    assert d["runtime_agreement"]["price_pass"] == 77
    assert d["ward_exceptions"] == ["0035N00157000000"]  # known, disclosed
    assert sections["cohort"].verdict_inputs["unexpected_exceptions"] == 0


def test_independent_join_does_not_use_production_reconcile():
    import inspect

    src = inspect.getsource(cohort)
    assert "from lotline.reconcile" not in src and "account_to_pin" not in src


def test_matrix_no_advance_with_withheld_and_no_critical_leak(sections):
    v = sections["matrix"].verdict_inputs
    assert v["advance_with_withheld"] == 0
    assert v["critical_leaks"] == 0
    assert v["parcels_with_named_first_resolver"] == "14/14"
    assert sum(sections["matrix"].data["outcome_counts_14"].values()) == 14


def test_conformance_is_labeled_not_accuracy(sections):
    s = sections["conformance"]
    assert "not accuracy" in s.title
    assert "accuracy" not in s.verdict_inputs["cells_agree"]
    assert s.verdict_inputs["cells_agree"] == "240/240"


def test_sensitivity_changes_confined(sections):
    n_ok, n = sections["sensitivity"].data["pairs"]
    assert n >= 20 and n_ok == n


def test_missingness_never_advances_and_controls_unchanged(sections):
    v = sections["missingness"].verdict_inputs
    total = v["advance_under_injection"].split("/")[1]
    assert v["advance_under_injection"] == f"0/{total}"
    assert v["unknown_as_zero"] == f"0/{total}"
    ok, n = v["negative_controls_unchanged"].split("/")
    assert ok == n


def test_repro_deterministic(sections):
    assert sections["repro"].verdict_inputs["deterministic_in_process"] is True
    assert sections["repro"].verdict_inputs["upstream_extraction_reproducible"] is False


def test_md_table_is_deterministic():
    rows = [("b", 2), ("a", 1), ("c|x", None)]
    assert md_table(["k", "v"], rows) == md_table(["k", "v"], list(reversed(rows)))
    assert "c\\|x" in md_table(["k", "v"], rows)


def test_runner_records_missing_module_as_not_run():
    from evaluation.run import run_one

    s = run_one("does_not_exist", 99, "placeholder")
    assert s.status.startswith("NOT RUN") and not s.all_passed


def test_app_code_never_imports_evaluation():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    for path in [root / "app.py", *(root / "lotline").rglob("*.py")]:
        text = path.read_text(encoding="utf-8")
        assert "import evaluation" not in text and "from evaluation" not in text, path
