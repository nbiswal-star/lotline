"""Run every evaluation experiment and write docs/validation/results.{md,json}.

    uv run python -m evaluation.run

Modules are imported lazily in a fixed registry order. A missing module or one
that raises is recorded as "NOT RUN: <reason>"; nothing is fabricated. The
output is deterministic apart from the generated-at timestamp in the header.
Exit code is 0 only when every section ran and every internal assertion held.
"""

from __future__ import annotations

import importlib

import platform
import sys
import traceback
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

from evaluation.common import REPO_ROOT, VALIDATION_DIR, Section, dumps

COMMAND = "uv run python -m evaluation.run"

# (module name, experiment number in docs/HANDOFF_CLAUDE.md M1, title used if NOT RUN)
REGISTRY: tuple[tuple[str, int, str], ...] = (
    ("cohort", 1, "Cohort reconstruction (independent join)"),
    ("matrix", 2, "Outcome and abstention matrix (14 advertised vacant parcels)"),
    ("conformance", 3, "Team-authored specification conformance (not accuracy)"),
    ("sensitivity", 4, "Boundary sensitivity"),
    ("missingness", 5, "Missingness and uncertainty injection"),
    ("ablation", 6, "Unsafe comparator / ablation"),
    ("adversarial", 7, "Adversarial language fidelity"),
    ("ai_reader", 8, "AI reader versus no-AI keyword baseline"),
    ("repro", 9, "Reproducibility record"),
    ("ai_scale", 10, "AI reader at citywide scale vs structured public reference (cached outputs)"),
)


def git_head() -> str:
    """Short HEAD SHA read from .git files (no git subprocess)."""
    git = REPO_ROOT / ".git"
    try:
        head = (git / "HEAD").read_text().strip()
        if head.startswith("ref: "):
            ref = head[5:]
            ref_file = git / ref
            if ref_file.exists():
                return ref_file.read_text().strip()[:7]
            packed = git / "packed-refs"
            if packed.exists():
                for line in packed.read_text().splitlines():
                    if line.endswith(" " + ref):
                        return line.split()[0][:7]
            return "unknown"
        return head[:7]
    except OSError:
        return "unknown (no .git directory)"


def versions() -> dict[str, str]:
    out = {"python": platform.python_version()}
    for pkg in ("pandas", "streamlit", "anthropic", "pytest"):
        try:
            out[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            out[pkg] = "not installed"
    return out


def run_one(name: str, number: int, title: str) -> Section:
    try:
        mod = importlib.import_module(f"evaluation.{name}")
    except ModuleNotFoundError as exc:
        if exc.name == f"evaluation.{name}":
            reason = f"module evaluation/{name}.py not present"
        else:
            reason = f"import failed: {exc!r}"
        return Section(id=name, title=title, markdown="", status=f"NOT RUN: {reason}")
    except Exception as exc:  # noqa: BLE001 - recorded, never hidden
        return Section(id=name, title=title, markdown="",
                       status=f"NOT RUN: import raised {type(exc).__name__}: {exc}")
    try:
        section = mod.run()
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc(limit=3).strip().splitlines()[-1]
        return Section(id=name, title=title, markdown="",
                       status=f"NOT RUN: run() raised {type(exc).__name__}: {exc} ({tb})")
    if not isinstance(section, Section):
        return Section(id=name, title=title, markdown="",
                       status=f"NOT RUN: run() returned {type(section).__name__}, not Section")
    if section.status == "ok" and not all(a.get("passed") for a in section.assertions):
        section.status = "failed: internal assertion(s) did not hold"
    return section


def render(sections: list[tuple[int, Section]], meta: dict) -> str:
    lines = [
        "# LotLine scientific validation: generated results",
        "",
        "<!-- GENERATED FILE: do not edit by hand. Regenerate with the command below. -->",
        "",
        f"- Command: `{meta['command']}`",
        f"- Repository HEAD: `{meta['git_head']}`",
        f"- Generated (UTC): {meta['generated_utc']}",
        "- Software: " + ", ".join(f"{k} {v}" for k, v in meta["versions"].items()),
        "- Scope: one frozen snapshot of one dated Pittsburgh Treasurer Sale "
        "(Treasury pull 2026-09-24; City advertisement dated 2026-09-16). Nothing here "
        "measures predictive accuracy, real-world outcomes or generalization.",
        "",
        "## Summary",
        "",
        "| # | Section | Status | Assertions held |",
        "|---|---|---|---|",
    ]
    for number, s in sections:
        n = len(s.assertions)
        ok = sum(bool(a.get("passed")) for a in s.assertions)
        held = f"{ok}/{n}" if n else "—"
        lines.append(f"| {number} | {s.title} | {s.status} | {held} |")
    for number, s in sections:
        lines += ["", f"## {number}. {s.title}", ""]
        if s.status.startswith("NOT RUN"):
            lines.append(f"**{s.status}.** No result is reported for this experiment.")
            continue
        if s.status != "ok":
            lines.append(f"**Status: {s.status}.**")
            lines.append("")
        lines.append(s.markdown.rstrip())
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    meta = {
        "command": COMMAND,
        "git_head": git_head(),
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "versions": versions(),
    }
    sections = [(number, run_one(name, number, title)) for name, number, title in REGISTRY]

    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    (VALIDATION_DIR / "results.md").write_text(render(sections, meta), encoding="utf-8")
    payload = {
        "meta": meta,
        "sections": [
            {
                "number": number,
                "id": s.id,
                "title": s.title,
                "status": s.status,
                "assertions": s.assertions,
                "verdict_inputs": s.verdict_inputs,
                "data": s.data,
            }
            for number, s in sections
        ],
    }
    (VALIDATION_DIR / "results.json").write_text(dumps(payload) + "\n", encoding="utf-8")

    all_ok = True
    print(f"{COMMAND}  (HEAD {meta['git_head']})")
    for number, s in sections:
        n = len(s.assertions)
        ok = sum(bool(a.get("passed")) for a in s.assertions)
        good = s.all_passed
        all_ok &= good
        print(f"  {number}. {s.id:<12} {s.status:<50} assertions {ok}/{n}")
        for a in s.assertions:
            if not a.get("passed"):
                print(f"       FAIL: {a['name']}: {a.get('detail', '')}")
    rel = Path("docs/validation")
    print(f"wrote {rel / 'results.md'} and {rel / 'results.json'}")
    print("ALL SECTIONS RAN AND ALL ASSERTIONS HELD" if all_ok else "INCOMPLETE OR FAILED: see above")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
