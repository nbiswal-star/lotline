"""Experiment 9: reproducibility record.

Hashes every committed input (data/, tests/fixtures/, uv.lock), records software
versions and the repository HEAD, and re-runs the full engine twice in-process
(from two independent snapshot loads) to show byte-identical serialized output.
"""

from __future__ import annotations

import hashlib
import platform

from evaluation.common import (
    DATA_DIR,
    FIXTURES_DIR,
    REPO_ROOT,
    Checks,
    Section,
    dumps,
    md_table,
    scope_note,
)


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _serialize_run() -> tuple[str, str]:
    """Fresh snapshot load + screen of all 96 records; returns (results JSON, triage CSV)."""
    from lotline.engine import screen
    from lotline.loaders import context_for, load_snapshot
    from lotline.ui.viewmodels import triage_csv

    snap = load_snapshot()
    results = {pin: screen(context_for(snap, pin)) for pin in sorted(snap.treasury)}
    return dumps(results), triage_csv(snap, results)


def run() -> Section:
    from evaluation.run import git_head, versions

    ck = Checks()
    files = sorted([p for p in DATA_DIR.rglob("*") if p.is_file()]
                   + [p for p in FIXTURES_DIR.rglob("*") if p.is_file()]
                   + [REPO_ROOT / "uv.lock", REPO_ROOT / "pyproject.toml"])
    file_rows = [(str(p.relative_to(REPO_ROOT)), p.stat().st_size, sha256(p)) for p in files if p.exists()]
    ck.check("uv.lock present", (REPO_ROOT / "uv.lock").exists(), "")

    j1, c1 = _serialize_run()
    j2, c2 = _serialize_run()
    h1 = hashlib.sha256(j1.encode()).hexdigest()
    h2 = hashlib.sha256(j2.encode()).hexdigest()
    hc1 = hashlib.sha256(c1.encode()).hexdigest()
    hc2 = hashlib.sha256(c2.encode()).hexdigest()
    ck.check("two in-process runs produce byte-identical serialized results (96 records)", j1 == j2,
             f"sha256 {h1[:16]}… vs {h2[:16]}…")
    ck.check("two in-process runs produce byte-identical triage CSV", c1 == c2, f"sha256 {hc1[:16]}…")

    vers = versions()
    env_rows = [("python", vers["python"]), ("implementation", platform.python_implementation()),
                *((k, v) for k, v in vers.items() if k != "python"), ("git HEAD (short)", git_head())]
    md = [
        "**Cohort:** all committed inputs and all 96 screened records.",
        md_table(["File", "Bytes", "sha256"], file_rows),
        md_table(["Component", "Version"], env_rows, sort=False),
        f"**Determinism:** two fresh snapshot loads + full screens in one process produced identical "
        f"serialized results (sha256 `{h1}`) and identical triage CSV (sha256 `{hc1}`).",
        "**Reproduction command** (after `uv sync` with network access, or with a warm uv cache): "
        "`uv run python -m evaluation.run`. The results hash above should match on any machine with the "
        "same `uv.lock`; a mismatch means the inputs or dependency versions differ.",
        "**Not reproducible from this repository:** the upstream extraction of the committed snapshots "
        "(WPRDC Treasurer Sales, City advertisement, County assessments/parcels, City GIS layers, PLI and "
        "condemned datasets). Those pre-event queries and transformations were ad hoc and were not "
        "retained, so source-to-snapshot reproduction is **not established**; only snapshot-to-result "
        "reproduction is. A prospective refresh pipeline (scripted, dated queries with retained raw "
        "responses and hashes) is future work.",
        "**Checked separately, not here:** offline app start with outbound network blocked and no API key "
        "(M0/M1 runbook in `docs/HANDOFF_CLAUDE.md`). This experiment runs in-process and does not block "
        "the network; installing dependencies from an uncached environment requires network access.",
        ck.markdown(),
        scope_note(
            "It pins exactly which inputs and software produced these results and shows the engine is "
            "deterministic in-process. It does not show that a different machine reproduces the hash (that "
            "needs an independent re-run), that the snapshots faithfully reflect the live public sources, "
            "or that the app starts offline."
        ),
    ]
    data = {"files": {f: h for f, _, h in file_rows}, "versions": vers,
            "results_sha256": h1, "triage_csv_sha256": hc1, "deterministic": j1 == j2 and c1 == c2}
    verdict = {"deterministic_in_process": j1 == j2 and c1 == c2, "results_sha256": h1,
               "upstream_extraction_reproducible": False}
    return Section("repro", "Reproducibility record", "\n\n".join(md), data, verdict, ck.items)
