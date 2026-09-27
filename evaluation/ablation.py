"""Experiment 6: unsafe comparator / ablation (post-hoc illustrative stress test).

WHAT THIS IS
    Four deliberately naive, evaluation-only screening policies. Each removes
    exactly ONE LotLine safeguard and otherwise reuses the pure engine
    (``lotline.engine.screen``) on an in-memory copy of the parcel context, or
    applies a declared output rule to LotLine's own components. The comparison
    shows, parcel by parcel, what that safeguard changes on the 14 advertised
    vacant lots of the frozen 2026-09-16 cohort, plus declared SYNTHETIC
    perturbations where the real cohort lacks the relevant missing state.

WHAT THIS IS NOT
    Not a benchmark, not an estimate of error rates, and not a model of any
    real product or competitor. The policies were written by the LotLine team
    after the application was built; the design is post-hoc and the cohort is
    tiny (n = 14). Divergence from LotLine is not evidence that LotLine is
    "right": there is no independent ground truth here, only the declared
    policy. Nothing in this module is imported by ``app.py`` or ``lotline/``;
    nothing is written to ``data/``.

FROZEN POLICY DEFINITIONS (written before any result was computed; do not edit
the rules below to change results; any change must be recorded as a new
policy id with its reason)

N1 "first area source"
    Area source: the assessment lot area (``assess_lotarea_sf``) if it is a
    positive number, otherwise the County GIS polygon area; the chosen value
    is used for BOTH area slots, so the second source is ignored and no lot-area
    conflict (material or disclosed) can be detected. All other inputs, rules
    and routing are LotLine's (bounding-rectangle geometry is kept).
    Disposition: advance iff the ablated screen's outcome is "Advance to staff
    review". Score: the ablated screen's Development Ease total.

N2 "unknown = 0"
    Components: LotLine's own use/dimensional/environment components for the
    same context; a component with status "withheld" or "not_applicable"
    contributes 0 points instead of being withheld; a "range" contributes its
    LOW end (so any divergence is attributable to unknown -> 0, not to
    optimism). Score: a single total 0-6, emitted for every parcel without a
    critical conflict (critical-conflict whole-parcel abstention is retained).
    Disposition: advance iff no critical conflict AND naive use points > 0 AND
    naive total >= N2_MIN_TOTAL (3, the lowest total of the "Conditional" band
    in lotline.engine.policy.BANDS). N2 has no separate area-conformance,
    site-standard or unencoded-dimension deferral: those states act only
    through the 0 they contribute.

N3 "ignore condition records"
    ``condemned_case_active`` is set False before screening, so the assessment
    VACANT use description is trusted and no current-condition conflict can
    be detected. Everything else is LotLine's. Disposition/score as N1.

N4 "single score, no range"
    ``possible_corner`` is set False before screening: an unresolved corner is
    assumed interior (the optimistic single number; the corner scenario, its
    range and its corner/frontage barrier disappear). Everything else is
    LotLine's. Disposition/score as N1.

SYNTHETIC perturbations (N2 only; the real 14 contain no withheld environment
input and no missing area source). Each is applied, one at a time, in memory
to every one of the 14 contexts and labeled SYNTHETIC:
    S1 fema_zone = "D" (flood hazard undetermined)
    S2 county_gis_area_sf = None (one area source missing)
    S3 manifest slope25 query_completed = False (screening layer incomplete)
    S4 district front_setback_ft = None (setback not encoded)
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from lotline.engine import screen
from lotline.loaders import context_for
from lotline.models import ConflictLevel, Outcome, ParcelContext, ScreeningResult, Snapshot

from evaluation.common import Checks, Section, advertised_vacant_pins, fingerprint, md_table, parcel_label
from evaluation.common import snapshot as shared_snapshot

SECTION_ID = "ablation"
SECTION_TITLE = "Experiment 6: unsafe comparator / ablation (post-hoc, illustrative)"

N2_MIN_TOTAL = 3  # lowest total of the "Conditional" band (policy.BANDS); frozen

POLICIES: dict[str, str] = {
    "N1": "first area source: assessment lot area only; County GIS ignored; no area-conflict detection",
    "N2": "unknown = 0: withheld/n.a. components score 0; advance if no critical conflict, use > 0, total >= 3",
    "N3": "ignore condition records: condemned-case association dropped; assessment VACANT trusted",
    "N4": "single score, no range: unresolved corner assumed interior",
}

SYNTHETIC_LABEL = "SYNTHETIC in-memory perturbation (not source data)"
PERTURBATIONS: dict[str, str] = {
    "S1": "fema_zone = 'D' (flood hazard undetermined)",
    "S2": "county_gis_area_sf = None (one area source missing)",
    "S3": "slope25 screening-layer query_completed = False",
    "S4": "district front_setback_ft = None (not encoded)",
}


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class View:
    """What a policy asserts about one parcel."""

    advance: bool
    outcome: str
    score: str  # "5", "3-4", "abstain (...)"
    numeric: bool  # a total was emitted
    components: dict[str, str]
    conflicts: tuple[str, ...]
    barrier_1: str | None


def _comp(c: Any) -> str:
    if c is None:
        return "n/a"
    if c.status in ("known", "range"):
        return f"{c.low}" if c.low == c.high else f"{c.low}-{c.high}"
    return c.status


def _conflicts(r: ScreeningResult) -> tuple[str, ...]:
    return tuple(f"{c.level.value}:{c.kind}" for c in r.conflicts)


def lotline_view(r: ScreeningResult) -> View:
    e = r.ease
    numeric = e is not None and e.total_low is not None
    if numeric:
        score = f"{e.total_low}" if e.total_low == e.total_high else f"{e.total_low}-{e.total_high}"
    else:
        score = f"abstain ({e.display.split(';')[0] if e else 'n/a'})"
    return View(
        advance=r.outcome is Outcome.ADVANCE,
        outcome=r.outcome.name,
        score=score,
        numeric=numeric,
        components={"use": _comp(r.use), "dimensional": _comp(r.dimensional), "environment": _comp(r.environment)},
        conflicts=_conflicts(r),
        barrier_1=r.barriers[0] if r.barriers else None,
    )


# --------------------------------------------------------------------------
# The four naive policies (evaluation-only)
# --------------------------------------------------------------------------


def _with_facts(ctx: ParcelContext, **changes: Any) -> ParcelContext:
    assert ctx.facts is not None
    return replace(ctx, facts=replace(ctx.facts, **changes))


def n1_context(ctx: ParcelContext) -> ParcelContext:
    f = ctx.facts
    if f is None:
        return ctx
    first = f.assess_lotarea_sf if (f.assess_lotarea_sf or 0) > 0 else f.county_gis_area_sf
    return _with_facts(ctx, assess_lotarea_sf=first, county_gis_area_sf=first)


def n3_context(ctx: ParcelContext) -> ParcelContext:
    return ctx if ctx.facts is None else _with_facts(ctx, condemned_case_active=False)


def n4_context(ctx: ParcelContext) -> ParcelContext:
    return ctx if ctx.facts is None else _with_facts(ctx, possible_corner=False)


def ablated_view(ctx: ParcelContext, transform) -> View:
    return lotline_view(screen(transform(ctx)))


def n2_view(r: ScreeningResult) -> View:
    """Output rule applied to LotLine's own components (see module docstring)."""
    def pts(c: Any) -> int:
        return c.low if c is not None and c.status in ("known", "range") else 0

    critical = any(c.level is ConflictLevel.CRITICAL for c in r.conflicts)
    routed = r.outcome in (Outcome.OUT_OF_UNIVERSE, Outcome.STRUCTURE)
    comps = {"use": pts(r.use), "dimensional": pts(r.dimensional), "environment": pts(r.environment)}
    total = sum(comps.values())
    advance = (not critical) and (not routed) and comps["use"] > 0 and total >= N2_MIN_TOTAL
    numeric = not critical and not routed
    return View(
        advance=advance,
        outcome="ADVANCE" if advance else "NOT_ADVANCE",
        score=str(total) if numeric else "abstain (critical conflict retained)",
        numeric=numeric,
        components={k: str(v) for k, v in comps.items()},
        conflicts=_conflicts(r),
        barrier_1=r.barriers[0] if r.barriers else None,
    )


# --------------------------------------------------------------------------
# Synthetic perturbations (N2)
# --------------------------------------------------------------------------


def perturb(ctx: ParcelContext, key: str) -> ParcelContext:
    """SYNTHETIC: one declared unknown state injected in memory."""
    if key == "S1":
        return _with_facts(ctx, fema_zone="D", fema_sfha=None)
    if key == "S2":
        return _with_facts(ctx, county_gis_area_sf=None)
    if key == "S3":
        manifest = dict(ctx.manifest)
        manifest["slope25"] = replace(manifest["slope25"], query_completed=False)
        return replace(ctx, manifest=manifest)
    if key == "S4":
        return ctx if ctx.rule is None else replace(ctx, rule=replace(ctx.rule, front_setback_ft=None))
    raise KeyError(key)


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------


def cohort(snapshot: Snapshot) -> list[ParcelContext]:
    """The advertised vacant lots (runtime reconciliation match, assessment use description VACANT)."""
    out = []
    for pin in sorted(snapshot.treasury):
        ctx = context_for(snapshot, pin)
        if ctx is not None and ctx.advert is not None and not ctx.treasury.is_structure:
            out.append(ctx)
    return out


def label(ctx: ParcelContext) -> str:
    return parcel_label(ctx.pin)


def divergences(base: View, naive: View) -> list[str]:
    out = []
    if naive.advance and not base.advance:
        out.append("naive ADVANCES where LotLine does not")
    if base.advance and not naive.advance:
        out.append("naive does not advance where LotLine advances")
    if naive.numeric and not base.numeric:
        out.append("naive emits a score where LotLine abstains")
    if base.numeric and naive.numeric and "-" in base.score and "-" not in naive.score:
        out.append("range collapsed to a single number")
    lost = [c for c in base.conflicts if c not in naive.conflicts]
    if lost:
        out.append("conflict not detected: " + ", ".join(lost))
    for k in base.components:
        if base.components[k] != naive.components.get(k):
            out.append(f"{k} {base.components[k]} -> {naive.components.get(k)}")
    if base.barrier_1 != naive.barrier_1:
        out.append("principal barrier changed")
    return out


def compare(snapshot: Snapshot | None = None) -> dict[str, Any]:
    s = snapshot or shared_snapshot()
    ctxs = cohort(s)
    baseline_fp = {c.pin: fingerprint(screen(c)) for c in ctxs}
    rows: list[dict[str, Any]] = []
    transforms = {"N1": n1_context, "N3": n3_context, "N4": n4_context}
    for ctx in ctxs:
        r = screen(ctx)
        base = lotline_view(r)
        views = {k: ablated_view(ctx, t) for k, t in transforms.items()}
        views["N2"] = n2_view(r)
        rows.append({
            "parcel": label(ctx),
            "lotline": base.__dict__,
            **{k: {"view": v.__dict__, "divergences": divergences(base, v)} for k, v in sorted(views.items())},
        })

    synthetic: list[dict[str, Any]] = []
    for key in PERTURBATIONS:
        for ctx in ctxs:
            pctx = perturb(ctx, key)
            r = screen(pctx)
            base, naive = lotline_view(r), n2_view(r)
            synthetic.append({"perturbation": key, "parcel": label(ctx), "lotline_outcome": base.outcome,
                              "lotline_score": base.score, "n2_score": naive.score, "n2_advance": naive.advance,
                              "divergences": divergences(base, naive), "label": SYNTHETIC_LABEL})

    n = len(rows)
    counts: dict[str, dict[str, int]] = {}
    for k in ("N1", "N2", "N3", "N4"):
        ds = [row[k]["divergences"] for row in rows]
        counts[k] = {
            "n": n,
            "any_divergence": sum(bool(d) for d in ds),
            "naive_advances_lotline_not": sum("naive ADVANCES where LotLine does not" in d for d in ds),
            "naive_scores_lotline_abstains": sum("naive emits a score where LotLine abstains" in d for d in ds),
            "range_collapsed": sum("range collapsed to a single number" in d for d in ds),
            "conflict_not_detected": sum(any(x.startswith("conflict not detected") for x in d) for d in ds),
        }
    syn_counts = {
        key: {
            "n": sum(1 for x in synthetic if x["perturbation"] == key),
            "n2_advances_lotline_not": sum(1 for x in synthetic if x["perturbation"] == key
                                           and "naive ADVANCES where LotLine does not" in x["divergences"]),
            "lotline_advance": sum(1 for x in synthetic if x["perturbation"] == key
                                   and x["lotline_outcome"] == "ADVANCE"),
        }
        for key in PERTURBATIONS
    }
    engine_unchanged = all(fingerprint(screen(c)) == baseline_fp[c.pin] for c in cohort(s))
    return {"policies": POLICIES, "perturbations": PERTURBATIONS, "n2_min_total": N2_MIN_TOTAL,
            "cohort_pins_match_shared_helper": [c.pin for c in ctxs] == advertised_vacant_pins(),
            "engine_unchanged_after_ablation": engine_unchanged,
            "cohort_n": n, "rows": rows, "counts": counts, "synthetic": synthetic,
            "synthetic_counts": syn_counts}


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

DOES_AND_DOES_NOT = """\
**What this does show.** On the frozen 14-lot cohort, each safeguard is load-bearing for specific,
named parcels: removing it changes a disposition, emits a number where LotLine abstains, collapses a
range, or drops a detected records conflict. The parcel tables make every such change inspectable.

**What this does not show.** It is not a benchmark and gives no error rate: the naive policies are
team-authored, post-hoc strawmen that do not represent any real product, analyst or competitor. With no
independent outcome labels, a divergence shows only that the policies *differ*, not that LotLine is
correct or that the naive answer is wrong on the ground (for example, a condemned case could be stale
and the lot really vacant). n = 14 from one dated Pittsburgh sale supports no superiority, causal or
generalization claim. SYNTHETIC rows exercise states absent from the real cohort and say nothing about
how often those states occur."""


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    return md_table(headers, rows, sort=False)


def render(data: dict[str, Any]) -> str:
    n = data["cohort_n"]
    parts = [
        "Post-hoc illustrative stress test, **not a benchmark**. Cohort: the "
        f"{n} advertised vacant lots of the frozen 2026-09-16 snapshot (denominator n = {n}). "
        "Each naive policy removes exactly one LotLine safeguard; rules were frozen in "
        "`evaluation/ablation.py` before results were computed. Evaluation-only; never shipped.",
        "",
        "**Frozen naive policies**",
        "",
        *[f"- **{k}** {v}" for k, v in data["policies"].items()],
        "",
        "**Raw counts (real cohort)**",
        "",
        _md_table(
            ["Policy", "any divergence", "advances where LotLine does not", "scores where LotLine abstains",
             "range collapsed", "conflict not detected"],
            [[k, f"{c['any_divergence']}/{c['n']}", f"{c['naive_advances_lotline_not']}/{c['n']}",
              f"{c['naive_scores_lotline_abstains']}/{c['n']}", f"{c['range_collapsed']}/{c['n']}",
              f"{c['conflict_not_detected']}/{c['n']}"] for k, c in data["counts"].items()],
        ),
        "",
        "**Disposition flips on the real cohort** (naive advances where LotLine does not):",
        "",
        *([f"- {k} would advance {row['parcel']} at {row[k]['view']['score']} of 6 with "
           f"{', '.join(x for x in row[k]['divergences'] if x.startswith('conflict not detected')) or 'no conflict'}; "
           f"LotLine: {row['lotline']['outcome']} / {row['lotline']['score']}."
           for row in data["rows"] for k in ("N1", "N2", "N3", "N4")
           if "naive ADVANCES where LotLine does not" in row[k]["divergences"]] or ["- none"]),
        "",
        "**Parcel-level divergences (real cohort; parcels with no divergence under any policy omitted)**",
        "",
    ]
    table = []
    for row in data["rows"]:
        base = row["lotline"]
        for k in ("N1", "N2", "N3", "N4"):
            d = row[k]["divergences"]
            if d:
                v = row[k]["view"]
                table.append([row["parcel"], f"{base['outcome']} / {base['score']}", k,
                              f"{v['outcome']} / {v['score']}", "; ".join(d)])
    parts.append(_md_table(["Parcel", "LotLine outcome / score", "Policy", "Naive outcome / score",
                            "Divergence"], table))
    parts += [
        "",
        f"**SYNTHETIC perturbations for N2** ({SYNTHETIC_LABEL}; each applied to all {n} lots, one at a time)",
        "",
        _md_table(["Perturbation", "LotLine advances", "N2 advances where LotLine does not"],
                  [[f"{k} {data['perturbations'][k]}", f"{c['lotline_advance']}/{c['n']}",
                    f"{c['n2_advances_lotline_not']}/{c['n']}"] for k, c in data["synthetic_counts"].items()]),
        "",
        "SYNTHETIC N2 rows where N2 advances and LotLine does not:",
        "",
        _md_table(["Perturbation", "Parcel", "LotLine", "N2 score"],
                  [[x["perturbation"], x["parcel"], f"{x['lotline_outcome']} / {x['lotline_score']}", x["n2_score"]]
                   for x in data["synthetic"] if "naive ADVANCES where LotLine does not" in x["divergences"]]),
        "",
        "### What this does and does not show",
        "",
        DOES_AND_DOES_NOT,
    ]
    return "\n".join(parts)


def run(snapshot: Snapshot | None = None) -> Section:
    data = compare(snapshot)
    c = data["counts"]
    verdict_inputs = {
        "cohort_n": data["cohort_n"],
        "post_hoc": True,
        "benchmark": False,
        "real_naive_advances_lotline_not": {k: v["naive_advances_lotline_not"] for k, v in c.items()},
        "real_naive_scores_lotline_abstains": {k: v["naive_scores_lotline_abstains"] for k, v in c.items()},
        "synthetic_n2_advances_lotline_not": {k: v["n2_advances_lotline_not"]
                                              for k, v in data["synthetic_counts"].items()},
        "synthetic_lotline_advances": {k: v["lotline_advance"] for k, v in data["synthetic_counts"].items()},
    }
    checks = Checks()
    checks.check("cohort is the 14 advertised vacant lots", data["cohort_n"] == 14
                 and data["cohort_pins_match_shared_helper"], f"n = {data['cohort_n']}")
    checks.check("engine output identical before and after all ablations (inputs never mutated)",
                 data["engine_unchanged_after_ablation"])
    base = [row["lotline"] for row in data["rows"]]
    checks.check("LotLine never advances a lot with a withheld component (real cohort)",
                 all(not b["advance"] or "withheld" not in b["components"].values() for b in base))
    syn_ll = sum(v["lotline_advance"] for v in data["synthetic_counts"].values())
    checks.check("LotLine advances 0 SYNTHETIC unknown-state lots", syn_ll == 0,
                 f"{syn_ll}/{sum(v['n'] for v in data['synthetic_counts'].values())}")
    by_pin = {row["parcel"]: row for row in data["rows"]}
    centre = next((r for p, r in by_pin.items() if "(10-S-5)" in p), None)
    checks.check("N1 drops the Centre Ave 10-S-5 material lot-area conflict",
                 centre is not None and any("material:lot_area" in d for d in centre["N1"]["divergences"]))
    checks.check("N3 drops the Centre Ave 10-S-5 critical current-condition conflict",
                 centre is not None and any("critical:current_condition" in d for d in centre["N3"]["divergences"]))
    return Section(id=SECTION_ID, title=SECTION_TITLE, markdown=render(data) + "\n\n" + checks.markdown(),
                   data=data, verdict_inputs=verdict_inputs, assertions=checks.items)
