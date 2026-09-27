"""Experiment 4: boundary sensitivity around every consequential threshold (H4).

All perturbations are applied to in-memory copies (``dataclasses.replace`` on
ParcelContext / ParcelFacts / DistrictRule / AdvertRecord and a copied manifest
dict). Nothing under ``data/`` is written. Each case perturbs one input of a
real parcel just below, at and above a policy boundary and runs ``screen()``.

For each adjacent pair of variants the report lists which decision outputs
changed (``evaluation.common.fingerprint``) and asserts

    must ⊆ changed ⊆ must ∪ may

where ``must`` is the minimal change the declared policy implies at that
boundary (empty when the pair does not cross it) and ``may`` lists numeric
echoes of the perturbed value (e.g. the area-gap percentage itself). Protected
outputs (outcome, ease, components) may change only where declared.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date

from evaluation.common import (
    Checks,
    Section,
    changed_keys,
    fingerprint,
    md_table,
    named_context,
    scope_note,
)


def with_facts(ctx, **kw):
    return replace(ctx, facts=replace(ctx.facts, **kw))


def with_rule(ctx, **kw):
    return replace(ctx, rule=replace(ctx.rule, **kw))


def with_advert(ctx, **kw):
    return replace(ctx, advert=replace(ctx.advert, **kw))


def with_source(ctx, source_id: str, **kw):
    m = dict(ctx.manifest)
    m[source_id] = replace(m[source_id], **kw)
    return replace(ctx, manifest=m)


@dataclass
class Pair:
    frm: int
    to: int
    must: frozenset[str]
    may: frozenset[str] = frozenset()
    note: str = ""


@dataclass
class Case:
    id: str
    threshold: str
    base: str
    perturbed: str
    variants: list[tuple[str, object, dict]]  # (label, ctx, screen kwargs)
    pairs: list[Pair]
    finding: str = ""
    extra: list[tuple[str, bool, str]] = field(default_factory=list)  # extra named checks


def _fs(*k: str) -> frozenset[str]:
    return frozenset(k)


CHECKS_CHANGE = _fs("next_checks", "next_check_triggers")
DIM_CROSS = _fs("dimensional", "ease")


def build_cases() -> list[Case]:
    from lotline.engine import policy

    ben = named_context("benezet")
    assess = ben.facts.assess_lotarea_sf  # 5,500 sf
    cases: list[Case] = []

    # A. Disclose-level area gap (policy.DISCLOSE_GAP_PCT = 10): directional gap above 10% disclosed.
    g = [round(assess * (1 + p / 100), 2) for p in (9.99, 10.0, 10.01)]  # 6,049.45 / 6,050 / 6,050.55
    cases.append(Case(
        "A_disclose_gap", f"DISCLOSE_GAP_PCT = {policy.DISCLOSE_GAP_PCT:g}% (gap > threshold is disclosed)",
        "Benezet (R1D-L; assessment 5,500 sf)", "County GIS area",
        [(f"GIS {v:,.2f} sf", with_facts(ben, county_gis_area_sf=v), {}) for v in g],
        [Pair(0, 1, _fs(), _fs("area_gap_pct"), "at the threshold: not disclosed (strictly above)"),
         Pair(1, 2, _fs("conflicts"), _fs("area_gap_pct"), "crossing: disclose conflict only; no score change")],
        finding=("Boundaries are evaluated in binary floating point. A gap of exactly 10% (GIS 6,050 sf) is "
                 "not disclosed, but computing the same input as 5,500 × 1.10 (= 6,050.000000000001) is. "
                 "Committed areas are whole square feet, so no real parcel sits within floating-point "
                 "error of a boundary; this matters only for derived or unit-converted inputs."),
    ))

    # B. Large-gap deed check (policy.LARGE_GAP_PCT = 25): gap >= 25% adds deed check + barrier.
    g = [round(assess * (1 - p / 100), 2) for p in (24.99, 25.0, 25.01)]
    cases.append(Case(
        "B_large_gap", f"LARGE_GAP_PCT = {policy.LARGE_GAP_PCT:g}% (gap >= threshold adds deed check + barrier)",
        "Benezet (R1D-L; assessment 5,500 sf; min 3,000)", "County GIS area",
        [(f"GIS {v:,.2f} sf", with_facts(ben, county_gis_area_sf=v), {}) for v in g],
        [Pair(0, 1, _fs("barriers") | CHECKS_CHANGE, _fs("area_gap_pct"),
              "crossing (at = triggers): deed/record-area check + gap barrier; no score change"),
         Pair(1, 2, _fs(), _fs("area_gap_pct", "barriers"), "above: only the numbers echoed in the barrier text")],
    ))

    # C. Minimum lot area crossed by ONE source (material conflict) — R1D-L min 3,000 sf.
    base_c = with_facts(ben, assess_lotarea_sf=3010.0, county_gis_area_sf=3010.0)
    cases.append(Case(
        "C_min_one_source", "district min_lot_sf (R1D-L 3,000 sf; material when min lies between sources)",
        "Benezet with assessment area set to 3,010 sf", "County GIS area",
        [(f"GIS {v:,.0f} sf", with_facts(base_c, county_gis_area_sf=v), {}) for v in (2999.0, 3000.0, 3001.0)],
        [Pair(0, 1, _fs("conflicts", "outcome", "setback_screen", "barriers") | DIM_CROSS | CHECKS_CHANGE,
              _fs("area_gap_pct"),
              "below→at: material conflict disappears; dimensional known again; Defer→Advance"),
         Pair(1, 2, _fs(), _fs("area_gap_pct"), "at→above: no crossing")],
    ))

    # D. Minimum lot area crossed by BOTH sources (records agree below minimum).
    cases.append(Case(
        "D_min_both_sources", "district min_lot_sf (R1D-L 3,000 sf; both sources)",
        "Benezet", "both lot areas (equal)",
        [(f"both {v:,.0f} sf", with_facts(ben, assess_lotarea_sf=v, county_gis_area_sf=v), {})
         for v in (2999.0, 3000.0, 3001.0)],
        [Pair(0, 1, _fs("outcome", "barriers") | DIM_CROSS | CHECKS_CHANGE, _fs(),
              "below→at: known 0 (below minimum in all sources) → scored; Defer→Advance"),
         Pair(1, 2, _fs(), _fs(), "no crossing")],
    ))

    # E. Width bands (policy.WIDTH_PARTIAL_FT = 10, WIDTH_FULL_FT = 20); corner resolved to interior.
    ben_int = with_facts(ben, possible_corner=False)
    widths = (9.9, 10.0, 19.9, 20.0)
    side = ben.rule.interior_side_ft
    cases.append(Case(
        "E_width_bands", f"WIDTH_PARTIAL_FT = {policy.WIDTH_PARTIAL_FT:g}, WIDTH_FULL_FT = {policy.WIDTH_FULL_FT:g}",
        "Benezet, corner status set to interior; depth 51 ft", "MBR short side (envelope width)",
        [(f"width {w:g} ft", with_facts(ben_int, mbr_short_side_ft=w + 2 * side), {}) for w in widths],
        [Pair(0, 1, _fs("barriers") | DIM_CROSS, _fs(), "9.9→10: band 0→1 (rounded size text identical)"),
         Pair(1, 2, _fs("setback_screen"), _fs(), "10→19.9: same band 1 (illustrative size text only)"),
         Pair(2, 3, _fs("barriers") | DIM_CROSS, _fs(), "19.9→20: band 1→2 (rounded size text identical)")],
    ))

    # F. Depth bands (same thresholds on depth).
    depths = (9.9, 10.0, 19.9, 20.0)
    fr = ben.rule.front_setback_ft + ben.rule.rear_setback_ft
    cases.append(Case(
        "F_depth_bands", f"DEPTH_PARTIAL_FT = {policy.DEPTH_PARTIAL_FT:g}, DEPTH_FULL_FT = {policy.DEPTH_FULL_FT:g}",
        "Benezet, corner status set to interior; width 39 ft", "MBR long side (envelope depth)",
        [(f"depth {d:g} ft", with_facts(ben_int, mbr_long_side_ft=d + fr), {}) for d in depths],
        [Pair(0, 1, _fs("barriers") | DIM_CROSS, _fs(), "9.9→10: band 0→1 (rounded size text identical)"),
         Pair(1, 2, _fs("setback_screen"), _fs(), "10→19.9: same band 1"),
         Pair(2, 3, _fs("barriers") | DIM_CROSS, _fs(), "19.9→20: band 1→2")],
    ))

    # G. Acquisition-burden ratio (policy.ACQUISITION_BURDEN_RATIO = 3.0).
    land = ben.facts.assessed_land_value
    ratios = (2.94, 2.95, 2.99, 3.0, 3.01)
    cases.append(Case(
        "G_burden_ratio", f"ACQUISITION_BURDEN_RATIO = {policy.ACQUISITION_BURDEN_RATIO:g} (>= adds barrier)",
        "Benezet (assessed land $1,600)", "upset price (raw ratio shown)",
        [(f"raw ratio {r:.2f}", with_facts(ben, upset_price=round(land * r, 2)), {}) for r in ratios],
        [Pair(0, 1, _fs("barriers", "upset_to_assessed_land"), _fs(),
              "2.94→2.95: barrier appears — the ratio is rounded to 1 decimal (2.95→3.0) before comparison"),
         Pair(1, 2, _fs(), _fs(), "2.95→2.99: both round to 3.0"),
         Pair(2, 3, _fs(), _fs(), "2.99→3.00: no change (already 3.0 after rounding)"),
         Pair(3, 4, _fs(), _fs(), "3.00→3.01: no change")],
        finding=("The burden barrier's effective threshold is a raw ratio of 2.95, not 3.0: "
                 "`upset_to_assessed_land` rounds to one decimal before the >= 3.0 comparison. The "
                 "displayed ratio (3.0×) is consistent with the barrier, so this is a documentation-"
                 "level boundary discrepancy, not a decision error; it affects an indicator-only barrier "
                 "and no score or outcome."),
    ))

    # H. Price tolerance (reconcile.PRICE_TOLERANCE_USD = 0.01): mismatch -> critical sale-universe conflict.
    due = ben.treasury.total_tax_due
    cases.append(Case(
        "H_price_tolerance", f"PRICE_TOLERANCE_USD = {policy.PRICE_TOLERANCE_USD:g}",
        "Benezet (Treasury total tax due $1,433.76)", "advertised upset price",
        [(f"upset = due + ${d:.2f}", with_advert(ben, upset=round(due + d, 2)), {}) for d in (0.0, 0.01, 0.02)],
        [Pair(0, 1, _fs(), _fs(), "within one cent: agrees"),
         Pair(1, 2, _fs("conflicts", "outcome", "ease", "barriers") | CHECKS_CHANGE, _fs(),
              "2 cents: critical sale-universe conflict; whole parcel Not scorable")],
    ))

    # I. Band cap (policy.BAND_CAPS: slope25 caps band at Conditional).
    sal = named_context("saline")
    cases.append(Case(
        "I_slope_cap_saline", "BAND_CAPS: slope25 → band at most Conditional (§906.08)",
        "Saline (P; slope25 + landslide-prone, so terrain family either way)", "slope25 layer flag",
        [("slope25 = False", with_facts(sal, slope25=False), {}), ("slope25 = True (as recorded)", sal, {})],
        [Pair(0, 1, _fs("ease", "next_check_triggers"), _fs(),
              "cap lowers band Apparently lower-discretion → Conditional; hazard family and score unchanged")],
    ))
    cases.append(Case(
        "I_slope_vs_landslide_benezet", "BAND_CAPS isolation: same terrain family, cap vs no cap",
        "Benezet (no hazard recorded)", "which terrain layer is flagged",
        [("landslide_prone = True", with_facts(ben, landslide_prone=True), {}),
         ("slope25 = True", with_facts(ben, slope25=True), {})],
        [Pair(0, 1, _fs("ease", "next_check_triggers"), _fs(),
              "identical terrain family and environment score; only the cap and the check citation differ")],
    ))

    # J. Staleness: sale-status source snapshot before the advertisement date.
    ad = policy.ADVERTISEMENT_DATE
    days = ("2026-09-15", ad.isoformat(), "2026-09-17")
    cases.append(Case(
        "J_stale_manifest", f"ADVERTISEMENT_DATE = {ad.isoformat()} (source as-of < date → stale warning)",
        "Benezet", "city_advertisement snapshot_as_of",
        [(f"as of {d}", with_source(ben, "city_advertisement", snapshot_as_of=d), {}) for d in days],
        [Pair(0, 1, _fs("warnings"), _fs(), "before→at: stale warning removed"),
         Pair(1, 2, _fs(), _fs(), "at→after: no change")],
    ))
    sale = date.fromisoformat(ben.treasury.sale_date)
    todays = (date(2026, 10, 1), sale, date(2026, 10, 3))
    cases.append(Case(
        "J_sale_date_passed", f"recorded sale date {sale.isoformat()} (screening after it → warning)",
        "Benezet", "screening date (`today`)",
        [(f"today {t.isoformat()}", ben, {"today": t}) for t in todays],
        [Pair(0, 1, _fs(), _fs(), "before→on sale date: no warning"),
         Pair(1, 2, _fs("warnings"), _fs(), "after sale date: sale-status warning")],
    ))

    # K. Site plan review lot-area trigger (policy.DISTRICT_REVIEW_CHECKS LNC 2,400 sf).
    wy = named_context("wylie")
    cases.append(Case(
        "K_site_plan_trigger", "DISTRICT_REVIEW_CHECKS LNC site plan review at lots >= 2,400 sf (§904.02.D)",
        "Wylie (LNC; no minimum lot size)", "both lot areas (equal)",
        [(f"both {v:,.0f} sf", with_facts(wy, assess_lotarea_sf=v, county_gis_area_sf=v), {})
         for v in (2399.0, 2400.0, 2401.0)],
        [Pair(0, 1, CHECKS_CHANGE, _fs(), "crossing adds the site plan review check only"),
         Pair(1, 2, _fs(), _fs(), "no crossing")],
    ))
    return cases


def run() -> Section:
    from lotline.engine import screen

    ck = Checks()
    md = [
        "**Cohort:** synthetic in-memory variants of real parcels (Benezet, Saline, Wylie), one input "
        "perturbed per case; the committed snapshot is untouched. **Denominator:** adjacent variant "
        "pairs per case. `changed` lists fingerprint outputs that differ (outcome, conflicts, use, "
        "dimensional, environment, ease, hazard families, coverage, setback screen, area gap, burden "
        "ratio, barriers, next checks, next-check triggers, warnings); the provenance fact list is "
        "excluded because it echoes every input by design.",
    ]
    summary_rows = []
    data_cases = {}
    findings = []
    n_pairs = n_ok = 0
    for case in build_cases():
        fps = [fingerprint(screen(ctx, **kw)) for _, ctx, kw in case.variants]
        var_rows = []
        for (label, _, _), fp in zip(case.variants, fps, strict=True):
            var_rows.append((label, fp["outcome"], fp["ease"], fp["dimensional"],
                             [f"{lv}:{k}" for lv, k, _ in fp["conflicts"]] or "none",
                             len(fp["barriers"]), len(fp["next_checks"]), len(fp["warnings"])))
        pair_rows = []
        case_data = {"threshold": case.threshold, "base": case.base, "perturbed": case.perturbed,
                     "variants": [v[0] for v in case.variants], "pairs": []}
        for p in case.pairs:
            changed = set(changed_keys(fps[p.frm], fps[p.to]))
            ok = p.must <= changed <= (p.must | p.may)
            n_pairs += 1
            n_ok += ok
            ck.check(f"{case.id}: {case.variants[p.frm][0]} → {case.variants[p.to][0]}", ok,
                     f"changed={sorted(changed) or '∅'}; must={sorted(p.must) or '∅'}; may={sorted(p.may) or '∅'}")
            pair_rows.append((f"{case.variants[p.frm][0]} → {case.variants[p.to][0]}",
                              sorted(changed) or "nothing", sorted(p.must) or "nothing",
                              "as declared" if ok else "**UNEXPECTED**", p.note))
            case_data["pairs"].append({"from": case.variants[p.frm][0], "to": case.variants[p.to][0],
                                       "changed": sorted(changed), "must": sorted(p.must),
                                       "may": sorted(p.may), "ok": ok})
        data_cases[case.id] = case_data
        summary_rows.append((case.id, case.threshold, f"{sum(r[3] == 'as declared' for r in pair_rows)}/{len(pair_rows)}"))
        md.append(f"### {case.id}: {case.threshold}\n\nBase: {case.base}. Perturbed input: {case.perturbed}.")
        md.append(md_table(["Variant", "Outcome", "Ease", "Dimensional", "Conflicts", "Barriers (n)",
                            "Next checks (n)", "Warnings (n)"], var_rows, sort=False))
        md.append(md_table(["Pair", "Outputs changed", "Minimal declared change", "Verdict", "Policy note"],
                           pair_rows, sort=False))
        if case.finding:
            findings.append((case.id, case.finding))
            md.append(f"**Finding:** {case.finding}")

    # Semantic spot checks beyond set membership.
    from lotline.engine import screen as _screen
    cases = {c.id: c for c in build_cases()}
    c = cases["C_min_one_source"]
    below = _screen(c.variants[0][1])
    ck.check("C: below-minimum variant withholds dimensional only (use and environment stay known)",
             below.dimensional.status == "withheld" and below.use.status == "known"
             and below.environment.status == "known", "")
    ck.check("C: below-minimum variant raises a MATERIAL lot_area conflict affecting dimensional",
             any(x.kind == "lot_area" and x.level.value == "material" and "dimensional" in x.affects
                 for x in below.conflicts), "")
    a = cases["A_disclose_gap"]
    above = _screen(a.variants[2][1])
    at = _screen(a.variants[1][1])
    ck.check("A: disclose conflict carries no withheld component (affects = ())",
             all(x.affects == () for x in above.conflicts) and above.ease.display == at.ease.display, "")
    h = cases["H_price_tolerance"]
    crit = _screen(h.variants[2][1])
    ck.check("H: price mismatch variant is Defer: records and Not scorable",
             crit.outcome.value.startswith("Defer: missing") and crit.ease.display == "Not scorable", "")
    e = cases["E_width_bands"]
    narrow = _screen(e.variants[0][1])
    ck.check("E: width 9.9 ft still Advances with dimensional known 0 (policy: a known low score is not a stop)",
             narrow.outcome.value == "Advance to staff review" and narrow.dimensional.low == 0, narrow.ease.display)
    findings.append(("E_width_bands",
                     "An envelope narrower than 10 ft scores dimensional 0 yet the parcel still Advances "
                     f"({narrow.ease.display}). This follows the declared policy (only unknowns and critical "
                     "conflicts block Advance; a known low score lowers the band), but a reviewer should know "
                     "Advance does not imply a usable envelope."))

    md.insert(1, "**Summary (pairs behaving exactly as declared / pairs):**\n\n"
              + md_table(["Case", "Threshold", "Pairs as declared"], summary_rows, sort=False))
    md.append("**Findings from this experiment:**\n\n" + "\n".join(f"- `{cid}`: {t}" for cid, t in findings))
    md.append(ck.markdown())
    md.append(scope_note(
        "It shows that, for the enumerated thresholds, each boundary changes only the outputs the declared "
        "policy says it should (and that the expected change does occur), using real parcels as bases. It "
        "does not show that the thresholds themselves are the right policy (10%/25% gap levels, 10/20 ft "
        "bands and the 3.0 ratio are stated LotLine screening assumptions, not code requirements), and it "
        "covers only one-at-a-time perturbations; interactions between several thresholds are exercised "
        "only where a case needs a reference variant (e.g. case C sets the assessment area to 3,010 sf)."
    ))
    data = {"cases": data_cases, "pairs": [n_ok, n_pairs], "findings": [list(f) for f in findings]}
    verdict = {"pairs_as_declared": f"{n_ok}/{n_pairs}", "cases": len(data_cases),
               "findings": [f[0] for f in findings]}
    return Section("sensitivity", "Boundary sensitivity", "\n\n".join(md), data, verdict, ck.items)
