"""Experiment 3: team-authored specification conformance (NOT accuracy).

Compares engine output field by field with ``tests/fixtures/expected_labels.csv``
(15 hand-labeled parcels). The labels were written by the same team that wrote
the engine, and labels and engine were revised together over several recorded
rounds (docs/label_changes.md). Agreement therefore measures conformance to the
team's own specification, not real-world correctness.
"""

from __future__ import annotations

import csv
import re

from evaluation.common import (
    FIXTURES_DIR,
    REPO_ROOT,
    Checks,
    Section,
    md_table,
    parcel_label,
    scope_note,
    screen_all,
    snapshot,
)

LABELS = FIXTURES_DIR / "expected_labels.csv"
LIST_SEP = " | "


def _split(text: str, sep: str = ";") -> list[str]:
    return [] if text in ("", "none") else [t.strip() for t in text.split(sep)]


def _engine_fields(pin: str, r, snap) -> dict[str, object]:
    from lotline.engine import conflict_level
    from lotline.engine.scoring import component_display

    adv = snap.advert.get(pin) if pin in snap.reconciliation.matched_pins else None
    price_ok = pin in snap.reconciliation.price_check_pass
    return {
        "in_city_advert": "Y" if adv else "N",
        "advert_sale_no": str(adv.sale_no) if adv else "",
        "advert_match_method": ("PIN+price" if price_ok else "PIN") if adv else "",
        "area_gap_pct": r.area_gap_pct,
        "upset_to_assessed_land": r.upset_to_assessed_land,
        "base_setback_screen": r.setback_screen,
        "hazard_families": r.hazard_families,
        "use_score": component_display(r.use),
        "dimensional_score": component_display(r.dimensional),
        "environment_score": component_display(r.environment),
        "ease_result": r.ease.display if r.ease else "n/a",
        "evidence_coverage": r.coverage_display,
        "screen_outcome": r.outcome.value.removeprefix("(routing) "),
        "conflict_level": conflict_level(r),
        "barriers": list(r.barriers),
        "unresolved_checks": [c.check for c in r.next_checks],
    }


# How each label column is compared (stated in the report).
RULES = {
    "area_gap_pct": "integer percent (label is written to whole percent)",
    "upset_to_assessed_land": "exact at 1 decimal",
    "hazard_families": "exact ordered list",
    "barriers": "exact ordered list",
    "unresolved_checks": "exact ordered list",
}


def _compare(field: str, label: str, got: object) -> bool:
    if field == "area_gap_pct":
        return got is not None and round(float(got)) == round(float(label))
    if field == "upset_to_assessed_land":
        return got is not None and abs(float(got) - float(label)) < 1e-9
    if field == "hazard_families":
        return got == _split(label)
    if field in ("barriers", "unresolved_checks"):
        return got == _split(label, LIST_SEP)
    return str(got) == label


def _label_rounds() -> list[str]:
    text = (REPO_ROOT / "docs" / "label_changes.md").read_text(encoding="utf-8")
    heads = re.findall(r"^# (.+)$|^## (Round .+)$", text, flags=re.M)
    return [a or b for a, b in heads]


PRESCREEN = REPO_ROOT / "docs" / "prep" / "golden_set_prescreen.csv"
# Why an outcome moved between the pre-build prescreen and the current engine
# (from docs/label_changes.md, "Label changes by parcel", rule verification pass).
PRESCREEN_EXPLANATIONS = {
    "P": "P-district dimensions (§905.01.C) encoded during rule re-verification; lot conforms, "
         "so dimensional became known and the parcel advanced",
    "LNC": "LNC dimensions (§904.02.C) encoded during rule re-verification; dimensional became "
           "known and the parcel advanced",
}


def _family(text: str) -> str:
    t = text.removeprefix("(routing) ")
    for sep in (" (", ":"):
        if sep in t and not t.startswith("Defer:"):
            t = t.split(sep)[0]
    if t.startswith("Defer:"):
        t = t.split(" (")[0]
    return t.strip()


def prescreen_comparison(results, snap) -> tuple[list[tuple], int, int]:
    rows = list(csv.DictReader(PRESCREEN.open(newline="", encoding="utf-8")))
    out = []
    agree = 0
    for row in rows:
        pin = row["pin"]
        pre = _family(row["screen_outcome_prelim"])
        now = _family(results[pin].outcome.value)
        ok = pre == now
        agree += ok
        if not ok:
            district = snap.parcels[pin].zoning_polygon if pin in snap.parcels else ""
            out.append((parcel_label(pin), pre, now, PRESCREEN_EXPLANATIONS.get(district, "see docs/label_changes.md")))
    return out, agree, len(rows)


def run() -> Section:
    snap = snapshot()
    results = screen_all()
    rows = list(csv.DictReader(LABELS.open(newline="", encoding="utf-8")))
    fields = [c.removeprefix("expected_") for c in rows[0] if c.startswith("expected_")]
    ck = Checks()
    ck.check("15 labeled parcels, unique", len(rows) == 15 and len({r["pin"] for r in rows}) == 15, str(len(rows)))

    per_field = {f: 0 for f in fields}
    disagreements = []
    for row in rows:
        pin = row["pin"]
        got = _engine_fields(pin, results[pin], snap)
        for f in fields:
            ok = _compare(f, row[f"expected_{f}"], got[f])
            per_field[f] += ok
            if not ok:
                disagreements.append((parcel_label(pin), f, row[f"expected_{f}"], str(got[f])))
    n = len(rows)
    total_cells = n * len(fields)
    agree_cells = sum(per_field.values())
    field_rows = [(f, per_field[f], f"{per_field[f]}/{n}", RULES.get(f, "exact string")) for f in fields]
    rounds = _label_rounds()
    pre_rows, pre_agree, pre_n = prescreen_comparison(results, snap)
    ck.check("pre-build prescreen covers the same 15 parcels", pre_n == 15, str(pre_n))
    ck.check("every prescreen outcome change is explained by a recorded rule change",
             all(r[3] != "see docs/label_changes.md" for r in pre_rows), f"{len(pre_rows)} changed")

    ck.check("every field compared for every parcel", total_cells == 15 * len(fields), f"{len(fields)} fields")
    # Not an assertion on agreement level: disagreements are findings, not failures.
    md = [
        "**Title: team-authored specification conformance (not accuracy).** **Cohort:** the 15 "
        "hand-labeled parcels in `tests/fixtures/expected_labels.csv` (14 advertised vacant parcels + "
        "1 non-advertised vacant control). **Reference:** labels written by the LotLine team; **not** "
        "independent ground truth.",
        md_table(["Field", "Exact agreements", "n/15", "Comparison rule"], field_rows, sort=False),
        f"Overall: {agree_cells}/{total_cells} field-parcel cells agree ({len(fields)} fields × {n} parcels). "
        "This is reported as a count, not averaged into an accuracy figure.",
        f"**Disagreements ({len(disagreements)}):**",
        md_table(["Parcel", "Field", "Label", "Engine"], disagreements) if disagreements else
        "None. Every disagreement found during development was resolved by a recorded label or engine "
        "change (below), so zero disagreements is expected by construction and is not evidence of "
        "correctness.",
        "**Limitation (co-revision):** labels and engine were revised together in "
        f"{len(rounds)} recorded passes in `docs/label_changes.md` ({'; '.join(rounds)}). In those "
        "passes both label values and engine rules changed after the two were compared, with a cited "
        "reason for each change. That makes this a regression and specification-consistency check. "
        "A defensible accuracy estimate needs labels produced blind to engine output by independent "
        "practitioners (see the prospective study below).",
        "**Less co-revised comparison: pre-build prescreen vs current engine (outcome family only).** "
        "`docs/prep/golden_set_prescreen.csv` holds the team's preliminary outcomes written before the "
        "build window (also team-authored, and never read by the app). Outcome family agreement: "
        f"**{pre_agree}/{pre_n}**. "
        + ("Every change moved a parcel from Defer to Advance after district dimensions were encoded "
           "(a less conservative direction), each with a recorded, cited reason:"
           if pre_rows and all(r[1].startswith("Defer") and r[2].startswith("Advance") for r in pre_rows)
           else "Changes, each with its recorded reason:"),
        md_table(["Parcel", "Pre-build prescreen", "Current engine", "Recorded reason"], pre_rows)
        if pre_rows else "No outcome changed.",
        "**Minimal prospective study (external validity, currently unvalidated):** two independent "
        "practitioners (e.g. a zoning examiner and an acquisition analyst) label the next advertised "
        "Treasurer Sale's vacant lots from primary records, blind to LotLine output. Pre-register the "
        "fields (outcome family, critical conflict yes/no, principal barrier category, first resolver). "
        "Report agreement with LotLine and inter-rater agreement (Cohen's κ) per field, with every "
        "disagreement adjudicated against primary records.",
        ck.markdown(),
        scope_note(
            "It shows that the engine reproduces the team's written specification for 15 parcels, field "
            "by field, including exact barrier and next-check order. It does not show accuracy, "
            "predictive validity or generalization: the reference labels are team-authored, were "
            "co-revised with the engine, and cover one dated sale."
        ),
    ]
    data = {
        "cohort": "15 team-labeled parcels",
        "fields": fields,
        "per_field_agree": per_field,
        "cells": [agree_cells, total_cells],
        "disagreements": [list(d) for d in disagreements],
        "label_revision_passes": rounds,
        "prescreen_outcome_agreement": [pre_agree, pre_n],
        "prescreen_changes": [list(r) for r in pre_rows],
    }
    verdict = {
        "cells_agree": f"{agree_cells}/{total_cells}",
        "fields_fully_agree": f"{sum(v == n for v in per_field.values())}/{len(fields)}",
        "disagreements": len(disagreements),
        "prescreen_outcome_agreement": f"{pre_agree}/{pre_n}",
        "reference": "team-authored, co-revised (conformance, not accuracy)",
    }
    return Section("conformance", "Team-authored specification conformance (not accuracy)",
                   "\n\n".join(md), data, verdict, ck.items)
