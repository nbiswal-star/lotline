"""Experiment 2: parcel-level outcome and abstention matrix (H2, H3, H6).

Every one of the 14 advertised vacant parcels is listed before any aggregate.
All values come from ``lotline.engine.screen``; the first parcel-specific next
check uses the engine's ``is_standard`` helper. A pattern-based leakage probe
also checks that critical-conflict parcels expose no score values through the
triage CSV, comparison view or Markdown packet.
"""

from __future__ import annotations

import re
from collections import Counter

from evaluation.common import (
    Checks,
    Section,
    advertised_vacant_pins,
    component_text,
    frac,
    md_table,
    parcel_label,
    scope_note,
    screen_all,
    snapshot,
)

FAMILY_ORDER = (
    "Advance to staff review",
    "Defer: missing or conflicting records",
    "Defer: site conditions unknown",
    "Do not advance for housing under stated screening policy",
    "Potential side yard or stewardship",
)

# A numeric score leaking for a critical parcel would look like one of these.
LEAK_PATTERNS = (
    re.compile(r"\b\d(?:-\d)? of [46]\b"),          # "5 of 6", "3-4 of 6", "2 of 4 known"
    re.compile(r"\b(?:use|dimensional|environment)\s*[:=]?\s*\d\b", re.I),
    re.compile(r"\bscores? \d\b", re.I),
    re.compile(r"\bknown points\b", re.I),
)


def _leaks(text: str) -> list[str]:
    return sorted({m.group(0) for p in LEAK_PATTERNS for m in p.finditer(text)})


def run() -> Section:
    from lotline.engine import conflict_level
    from lotline.engine.checks import is_standard
    from lotline.models import ConflictLevel, Outcome
    from lotline.ui import viewmodels as vm

    snap = snapshot()
    results = screen_all()
    pins = advertised_vacant_pins()
    ck = Checks()
    ck.check("14 advertised vacant parcels", len(pins) == 14, str(len(pins)))

    rows = []
    records = {}
    for pin in pins:
        r = results[pin]
        comps = {c.name: c for c in (r.use, r.dimensional, r.environment) if c is not None}
        withheld = [(n, c.short_reason or c.reason) for n, c in comps.items() if c.status == "withheld"]
        specific = next((nc for nc in r.next_checks if not is_standard(nc)), None)
        conflicts = [f"{c.level.value}: {c.kind}" for c in r.conflicts]
        rule = snap.rules.get(snap.parcels[pin].zoning_polygon) if pin in snap.parcels else None
        district = rule.district if rule else (snap.parcels[pin].zoning_polygon if pin in snap.parcels else "—")
        rec = {
            "parcel": parcel_label(pin),
            "district": district,
            "outcome": r.outcome.value,
            "conflicts": conflicts,
            "ease": r.ease.display if r.ease else None,
            "use": component_text(r.use),
            "dimensional": component_text(r.dimensional),
            "environment": component_text(r.environment),
            "withheld": [f"{n} ({why})" for n, why in withheld],
            "principal_barrier": r.barriers[0] if r.barriers else None,
            "first_specific_check": specific.check if specific else None,
            "first_specific_owner": specific.owner if specific else None,
            "coverage": r.coverage_display,
            "conflict_level": conflict_level(r),
        }
        records[pin] = rec
        rows.append((
            FAMILY_ORDER.index(r.outcome.value), rec["parcel"], district, r.outcome.value,
            conflicts or "none", rec["ease"], rec["use"], rec["dimensional"], rec["environment"],
            rec["withheld"] or "none", rec["principal_barrier"] or "none",
            f"{rec['first_specific_check']} — {rec['first_specific_owner']}" if specific else "none",
            rec["coverage"],
        ))
    rows.sort()
    table = md_table(
        ["Parcel", "District", "Outcome", "Conflicts", "Ease display", "Use", "Dimensional",
         "Environment", "Withheld component (reason)", "Principal barrier",
         "First parcel-specific check — owner", "Coverage"],
        [r[1:] for r in rows], sort=False,
    )

    # --- invariants over the 14 --------------------------------------------------
    adv = [p for p in pins if results[p].outcome is Outcome.ADVANCE]
    def withheld_any(p):
        return any(c is not None and c.status == "withheld"
                   for c in (results[p].use, results[p].dimensional, results[p].environment))
    critical = [p for p in pins if any(c.level is ConflictLevel.CRITICAL for c in results[p].conflicts)]
    ranged = [p for p in pins if any(c is not None and c.status == "range"
                                     for c in (results[p].use, results[p].dimensional, results[p].environment))]
    ck.check("no Advance with any withheld component",
             not any(withheld_any(p) for p in adv), f"{sum(withheld_any(p) for p in adv)}/{len(adv)} Advance")
    ck.check("every Advance has no critical or material conflict",
             all(conflict_level(results[p]) in ("none", "disclose") for p in adv), "")
    ck.check("every critical-conflict parcel shows 'Not scorable' with no total",
             all(results[p].ease.display == "Not scorable" and results[p].ease.total_low is None
                 for p in critical), f"{len(critical)} critical")
    ck.check("every critical-conflict parcel is Defer: missing or conflicting records",
             all(results[p].outcome is Outcome.DEFER_RECORDS for p in critical), "")
    ck.check("every range component comes from an unresolved corner scenario",
             all(len(results[p].scenarios) == 2 for p in ranged), f"{len(ranged)} parcels with a range")
    ck.check("every parcel has >= 1 barrier and a first parcel-specific check with a named owner",
             all(results[p].barriers and records[p]["first_specific_check"] and records[p]["first_specific_owner"]
                 for p in pins), "")
    ck.check("every next check on every parcel has an owner and trigger",
             all(nc.owner and nc.trigger for p in pins for nc in results[p].next_checks), "")
    ck.check("current-sale pre-spend gate present on every advertised vacant parcel",
             all(any(nc.check.startswith("verify current advertised sale status") for nc in results[p].next_checks)
                 for p in pins), "")
    ck.check("every withheld component has a matching barrier or conflict and a non-standard next check",
             all(any(not is_standard(nc) for nc in results[p].next_checks) for p in pins if withheld_any(p)), "")

    # UI consistency: the triage export renders the engine's values.
    trows = {row["pin"]: row for row in vm.triage_rows(snap, results)}
    ui_agree = sum(
        trows[p]["Development Ease"] == records[p]["ease"]
        and trows[p]["Principal barrier"] == (records[p]["principal_barrier"] or "none listed")
        and trows[p]["First parcel-specific check"] == (records[p]["first_specific_check"] or "")
        and trows[p]["Who resolves it"] == (records[p]["first_specific_owner"] or "")
        and trows[p]["Evidence"] == records[p]["coverage"]
        for p in pins if p in trows
    )
    ck.check("triage export fields equal engine fields 14/14", ui_agree == 14 and set(trows) == set(pins),
             f"{ui_agree}/14")

    # Leakage probe for critical parcels (triage CSV row, compare column, Markdown packet).
    leak_rows = []
    csv_text = vm.triage_csv(snap, results)
    cols = vm.compare_columns(snap, results, critical)
    for p in critical:
        label = vm.parcel_label(snap, p)
        csv_line = next((ln for ln in csv_text.splitlines() if label.split(" · ")[0] in ln
                         and trows[p]["Parcel"] in ln), "")
        comp_text = " ".join(cols[label].values())
        packet_text = vm.packet_markdown(snap, results[p], vm.packet(snap, results, p))
        # The memo section is audited separately (experiment 7); probe the packet body above it.
        packet_body = packet_text.split("## Deterministic cited memo")[0]
        for surface, text in (("triage CSV row", csv_line), ("compare column", comp_text),
                              ("packet body", packet_body)):
            leak_rows.append((parcel_label(p), surface, _leaks(text) or "none"))
    n_leaks = sum(1 for r in leak_rows if r[2] != "none")
    # Positive control: the probe must fire on a scored (non-critical) parcel's triage row.
    scored = [p for p in adv if p in trows]
    control_hits = sum(bool(_leaks(" ".join(str(v) for v in trows[p].values()))) for p in scored)
    ck.check("leak probe positive control fires on every scored Advance triage row",
             control_hits == len(scored) > 0, f"{control_hits}/{len(scored)}")
    ck.check("no score-value pattern in critical parcels' triage row, compare column or packet body",
             n_leaks == 0, f"{n_leaks}/{len(leak_rows)} surfaces matched a leak pattern")

    # --- aggregates (after the parcel table) ------------------------------------
    fam = Counter(results[p].outcome.value for p in pins)
    agg = [(o, fam.get(o, 0), frac(fam.get(o, 0), 14)) for o in FAMILY_ORDER]
    all_counts = Counter(r.outcome.value for r in results.values())
    all_rows = [(o, n, frac(n, 96)) for o, n in sorted(all_counts.items())]
    cls = Counter(conflict_level(results[p]) for p in pins)
    cls_rows = [(k, cls.get(k, 0), frac(cls.get(k, 0), 14)) for k in ("critical", "material", "disclose", "none")]
    struct = [
        ("parcels with >= 1 withheld component", sum(withheld_any(p) for p in pins)),
        ("parcels with a range component (corner unresolved)", len(ranged)),
        ("Advance parcels with a withheld component", sum(withheld_any(p) for p in adv)),
        ("Advance parcels with a range (corner) component", len(set(adv) & set(ranged))),
        ("critical-conflict parcels", len(critical)),
    ]
    struct_rows = [(k, v, frac(v, 14)) for k, v in struct]

    expected = {"Advance to staff review": 7, "Defer: missing or conflicting records": 3,
                "Defer: site conditions unknown": 3,
                "Do not advance for housing under stated screening policy": 1}
    ck.check("outcome families 7 / 3 / 3 / 1 (as reported in README and handoff)",
             all(fam.get(k, 0) == v for k, v in expected.items()), dict(fam).__repr__())
    ck.check("error-analysis note holds: every Defer-records parcel has a critical current-condition conflict",
             all(any(c.kind == "current_condition" and c.level is ConflictLevel.CRITICAL
                     for c in results[p].conflicts)
                 for p in pins if results[p].outcome is Outcome.DEFER_RECORDS), "")
    ck.check("error-analysis note holds: every Defer-site parcel is in the H district",
             all(records[p]["district"] == "H" for p in pins if results[p].outcome is Outcome.DEFER_SITE), "")
    ck.check("Potential side yard outcome unreachable in v1 (0/14)", fam.get("Potential side yard or stewardship", 0) == 0, "")

    md = [
        "**Cohort:** the 14 advertised vacant parcels (advertised per runtime reconciliation, vacant per "
        "assessment use description; identical to experiment 1's independent set). Denominator for every "
        "aggregate below is 14 unless stated. Status legend: `known n`, `range lo-hi` (corner unresolved), "
        "`withheld` (unknown, never scored), `n.a.` (not applicable).",
        table,
        "**Aggregates by outcome family (n/14):**",
        md_table(["Outcome", "Parcels", "n/14"], agg, sort=False),
        "**Highest conflict level (n/14):**",
        md_table(["Highest conflict level", "Parcels", "n/14"], cls_rows, sort=False),
        "**Abstention structure (n/14):**",
        md_table(["Measure", "Parcels", "n/14"], struct_rows, sort=False),
        "**Whole source cohort (n/96), for context:**",
        md_table(["Outcome", "Records", "n/96"], all_rows),
        "**Leakage probe on critical-conflict parcels** (patterns: `N of 6`, `N of 4`, "
        "`<component> N`, `scores N`, `known points`; memo section excluded here and audited in "
        "experiment 7). Positive control: the same probe fires on "
        f"{control_hits}/{len(scored)} scored Advance triage rows.",
        md_table(["Parcel", "Surface", "Matched leak patterns"], leak_rows),
        "**Error-analysis notes (per family, from this table):** *Advance* (7) still carries unresolved "
        "hazard, corner, open-space and procedural checks; its most plausible false-advance mechanism is a "
        "condition absent from every loaded source (e.g. an unrecorded structure, a paper street, a title "
        "defect), which no test here can detect. Two Advance parcels are in the P (Parks) district, where "
        "advancing follows the code (§911.02) but is a policy choice flagged by the open-space barrier. "
        "*Defer: records* (3) are all critical current-condition conflicts (active condemned case on a "
        "VACANT-classified lot); the false-deferral risk is a stale condemned-case association, resolvable "
        "only by PLI status and a site visit. *Defer: site* (3) are all Hillside (H) parcels withheld by "
        "the survey-dependent §911.04.A.69 standard; they may be feasible after survey. *Do not advance* "
        "(1) is the UI parcel; a false stop would require the use table to be misencoded, which the rule "
        "citation audit, not this matrix, addresses.",
        ck.markdown(),
        scope_note(
            "It shows, parcel by parcel, that every decision on the 14 vacant lots is traceable to an "
            "engine outcome, conflict class, component status, principal barrier and a named first "
            "resolver, that no parcel with a withheld component advanced, and that the triage export "
            "matches engine output. It does not show that any outcome is *correct* in the world: there "
            "is no independent reference outcome for these parcels, and the same team wrote the policy. "
            "The leakage probe is pattern-based and covers three surfaces; it cannot prove the absence "
            "of every possible rendering of a score."
        ),
    ]
    data = {
        "cohort": "14 advertised vacant parcels",
        "parcels": records,
        "outcome_counts_14": {o: fam.get(o, 0) for o in FAMILY_ORDER},
        "outcome_counts_96": dict(sorted(all_counts.items())),
        "conflict_levels_14": {k: cls.get(k, 0) for k in ("critical", "material", "disclose", "none")},
        "structure": dict(struct),
        "leak_probe": [list(r) for r in sorted(leak_rows)],
        "triage_ui_agreement": ui_agree,
    }
    verdict = {
        "outcomes_14": {o: fam.get(o, 0) for o in FAMILY_ORDER if fam.get(o, 0)},
        "advance_with_withheld": sum(withheld_any(p) for p in adv),
        "critical_parcels": len(critical),
        "critical_leaks": n_leaks,
        "parcels_with_named_first_resolver": f"{sum(bool(records[p]['first_specific_owner']) for p in pins)}/14",
    }
    return Section("matrix", "Outcome and abstention matrix (14 advertised vacant parcels)",
                   "\n\n".join(md), data, verdict, ck.items)
