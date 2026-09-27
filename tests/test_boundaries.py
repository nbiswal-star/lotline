"""Data-separation boundaries: the app never reads answer keys or prepared results."""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from lotline import loaders
from lotline.loaders import load_snapshot
from lotline.models import Snapshot
from tests.conftest import BENEZET, REPO_ROOT, edit_csv

APP_SOURCES = sorted((REPO_ROOT / "lotline").rglob("*.py")) + [
    p for p in [REPO_ROOT / "app.py"] if p.exists()
]

FORBIDDEN_FILES = ("expected_labels", "golden_set_prescreen", "expected_reconciliation", "fixtures")
# Prepared answer columns (enriched Treasury CSV and advertisement CSV) plus
# the undocumented Treasury sale flag.
FORBIDDEN_COLUMNS = (
    "in_city_advert_2026_09_16", "advert_sale_no", "advert_match_method",
    "pin_match", "price_check", "sale_flag", "treasury_sale_flag",
)
# Interpreted golden-set answers that must never be app inputs.
INTERPRETED_COLUMNS = (
    "single_unit_path", "two_unit_path", "controlling_min_lot", "expected_screen_outcome",
    "why", "demo_role", "score_notes",
)
PIN_LITERAL = re.compile(r"(?<![0-9A-Za-z])\d{4}[A-Z]\d{5}[0-9A-Z]{4}\d{2}(?![0-9A-Za-z])")


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _code_tokens(path: Path) -> list[str]:
    """String constants (excluding docstrings) and identifiers in a module."""
    tree = ast.parse(path.read_text())
    docs = _docstring_nodes(tree)
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            out.append(node.value)
        elif isinstance(node, ast.Name):
            out.append(node.id)
        elif isinstance(node, ast.Attribute):
            out.append(node.attr)
        elif isinstance(node, ast.keyword) and node.arg:
            out.append(node.arg)
    return out


def test_app_sources_found() -> None:
    names = {p.name for p in APP_SOURCES}
    assert {"loaders.py", "reconcile.py", "facts.py", "models.py"} <= names


@pytest.mark.parametrize("path", APP_SOURCES, ids=lambda p: p.name)
def test_app_source_never_names_answer_key_files(path: Path) -> None:
    text = path.read_text()
    hits = [f for f in FORBIDDEN_FILES if f in text]
    assert not hits, f"{path.name} references {hits}"


@pytest.mark.parametrize("path", APP_SOURCES, ids=lambda p: p.name)
def test_app_code_never_names_forbidden_columns(path: Path) -> None:
    # Docstrings may describe the prohibition (models.py does); code may not use the names.
    pattern = re.compile(r"\b(" + "|".join(FORBIDDEN_COLUMNS + INTERPRETED_COLUMNS) + r")\b")
    hits = [tok for tok in _code_tokens(path) if pattern.search(tok)]
    assert not hits, f"{path.name} uses {hits}"


@pytest.mark.parametrize("path", APP_SOURCES, ids=lambda p: p.name)
def test_no_pin_literal_in_app_source(path: Path) -> None:
    hits = PIN_LITERAL.findall(path.read_text())
    assert not hits, f"{path.name} hardcodes PIN(s) {hits}; select parcels from data or config"


def test_allowlists_exclude_forbidden_columns() -> None:
    allowed = set(loaders.TREASURY_COLUMNS) | set(loaders.ADVERT_COLUMNS) | set(
        loaders.PARCEL_COLUMNS) | set(loaders.RULE_COLUMNS) | set(loaders.MANIFEST_COLUMNS)
    assert allowed.isdisjoint(FORBIDDEN_COLUMNS + INTERPRETED_COLUMNS)
    assert loaders.ADVERT_COLUMNS == ("sale_no", "account", "pin", "ad_address", "upset")


def test_every_csv_read_uses_an_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    real = pd.read_csv

    def spy(path: object, *args: object, **kwargs: object) -> pd.DataFrame:
        calls.append({"path": str(path), **kwargs})
        return real(path, *args, **kwargs)

    monkeypatch.setattr(loaders.pd, "read_csv", spy)
    load_snapshot()
    data_reads = [c for c in calls if c.get("nrows") != 0]
    assert len(data_reads) == 7  # 5 snapshot CSVs + optional record text + allowlisted parcel points
    for c in data_reads:
        usecols = c.get("usecols")
        assert usecols, f"{c['path']} read without usecols"
        assert set(usecols).isdisjoint(FORBIDDEN_COLUMNS), c["path"]  # type: ignore[arg-type]
        assert c.get("dtype") is str
        assert Path(str(c["path"])).parent == loaders.DATA_DIR


def test_poisoned_answer_columns_do_not_change_snapshot(data_copy: Path, snapshot: Snapshot) -> None:
    """Add lying answer-key columns; the loaded snapshot must be identical."""
    def poison_treasury(df: pd.DataFrame) -> pd.DataFrame:
        return df.assign(in_city_advert_2026_09_16="N", advert_sale_no="999",
                         advert_match_method="bogus", sale_flag="N")

    def poison_advert(df: pd.DataFrame) -> pd.DataFrame:
        return df.assign(pin_match="False", price_check="False")

    edit_csv(data_copy / loaders.TREASURY_FILE, poison_treasury)
    edit_csv(data_copy / loaders.ADVERT_FILE, poison_advert)
    assert load_snapshot(data_copy) == snapshot


def test_sale_flag_is_optional(data_copy: Path, snapshot: Snapshot) -> None:
    edit_csv(data_copy / loaders.TREASURY_FILE, lambda df: df.drop(columns=["sale_flag"]))
    assert load_snapshot(data_copy) == snapshot


def test_parcel_facts_file_has_no_interpreted_answers() -> None:
    header = pd.read_csv(loaders.DATA_DIR / loaders.PARCEL_FACTS_FILE, nrows=0).columns
    assert set(header).isdisjoint(FORBIDDEN_COLUMNS + INTERPRETED_COLUMNS)


def _imports(path: Path) -> set[str]:
    mods: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    return mods


@pytest.mark.parametrize("path", APP_SOURCES, ids=lambda p: p.name)
def test_app_never_imports_tests(path: Path) -> None:
    assert _imports(path).isdisjoint({"tests", "conftest", "pytest"})


PURE_MODULES = ["reconcile.py", "facts.py", "models.py"] + sorted(
    f"engine/{p.name}" for p in (REPO_ROOT / "lotline" / "engine").glob("*.py")
)


@pytest.mark.parametrize("name", PURE_MODULES)
def test_pure_layers_do_no_io(name: str) -> None:
    """Reconcile, facts, models and every engine module import only pure stdlib + lotline."""
    path = REPO_ROOT / "lotline" / name
    mods: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            mods.add(node.module.split(".")[0])
    # math is pure arithmetic (riparian distance); it performs no I/O.
    assert mods <= {"__future__", "collections", "dataclasses", "datetime", "enum", "math", "re",
                    "lotline"}, mods
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open":
            raise AssertionError(f"{name} opens a file")
    # Relative imports inside lotline.engine stay inside the engine package.
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level:
            assert name.startswith("engine/"), name


def test_app_starts_without_tests_or_docs(tmp_path: Path) -> None:
    """Run the loader from a tree containing only lotline/ and data/.

    An audit hook records every file opened; none may be outside data/ (apart
    from Python/pandas internals) and none may be a fixture or prep artifact.
    """
    shutil.copytree(REPO_ROOT / "lotline", tmp_path / "lotline",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(loaders.DATA_DIR, tmp_path / "data")
    script = textwrap.dedent(f"""
        import sys
        opened = []
        sys.addaudithook(lambda ev, args: opened.append(str(args[0])) if ev == "open" else None)
        from lotline.loaders import load_snapshot, context_for, lookup_pin
        from lotline.facts import facts_for, rule_facts
        from lotline.engine import screen
        snap = load_snapshot()
        pin = lookup_pin(snap, "{BENEZET}")
        ctx = context_for(snap, pin)
        assert ctx is not None and ctx.rule is not None
        assert facts_for(ctx) and rule_facts(ctx.rule, ctx.manifest)
        results = [screen(context_for(snap, p)) for p in snap.treasury]
        assert len(results) == 96 and results and all(r.facts for r in results)
        benezet = screen(ctx)
        assert benezet.outcome.value == "Advance to staff review", benezet.outcome
        assert not any(m == "tests" or m.startswith("tests.") for m in sys.modules)
        bad = [p for p in opened if any(k in p for k in
               ("fixtures", "expected_", "golden_set", "docs/"))]
        assert not bad, bad
        data = sorted({{p for p in opened if p.endswith(".csv")}})
        assert all("{tmp_path}/data/" in p for p in data), data
        print("OK", len(data))
    """)
    res = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, capture_output=True,
                         text=True, env={"PYTHONPATH": str(tmp_path), "PATH": ""})
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "OK 6"  # includes optional record_text.csv
