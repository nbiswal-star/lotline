"""Shared fixtures. Test data under tests/fixtures/ is for tests only."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from lotline.loaders import DATA_DIR, load_snapshot
from lotline.models import Snapshot

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures"

BENEZET = "0131N00031000000"
CENTRE_10S5 = "0010S00005000000"
GARFIELD = "0023E00229000000"
WALCOTT = "0042D00039000000"


@pytest.fixture(scope="session")
def snapshot() -> Snapshot:
    return load_snapshot()


@pytest.fixture
def data_copy(tmp_path: Path) -> Path:
    """A writable copy of data/ for mutation tests."""
    dest = tmp_path / "data"
    shutil.copytree(DATA_DIR, dest)
    return dest


EditFn = Callable[[pd.DataFrame], pd.DataFrame]


def edit_csv(path: Path, fn: EditFn) -> None:
    """Rewrite a CSV (all strings, blanks preserved) through ``fn``."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    fn(df).to_csv(path, index=False)
