"""Experiment 5: missingness and uncertainty injection (H3, H6).

In-memory only. Unknown values are injected into real Advance parcels and the
engine is re-run. For each case the report gives the outcome, withheld
components, whether any component became a *known 0* that was not a known 0
before (unknown scored as zero), whether Advance occurred (it must not), and the
first parcel-specific next check naming the missing input.

Negative controls: the unperturbed parcel (re-screened), and perturbations of
fields that the declared policy does not use for any decision output.
"""

from __future__ import annotations

from dataclasses import replace

from evaluation.common import (
    Checks,
    Section,
    component_text,
    fingerprint,
    frac,
    md_table,
    named_context,
    parcel_label,
    scope_note,
    screen_all,
)

LAYERS = ("landslide_prone", "slope25", "undermined", "fema_nfhl")


def _facts(ctx, **kw):
    return replace(ctx, facts=replace(ctx.facts, **kw))


def _rule(ctx, **kw):
    return replace(ctx, rule=replace(ctx.rule, **kw))


def _layer_failed(ctx, sid):
    m = dict(ctx.manifest)
    m[sid] = replace(m[sid], query_completed=False)
    return replace(ctx, manifest=m)


# (case id, description, expected withheld component(s), injector)
INJECTIONS = (
    ("fema_D", "FEMA zone 'D' (undetermined)", {"environment"},
     lambda c: _facts(c, fema_zone="D", fema_sfha=None)),
    ("fema_unrecognized", "FEMA zone unrecognized text ('unknown')", {"environment"},
     lambda c: _facts(c, fema_zone="unknown", fema_sfha=None)),
    ("fema_blank", "FEMA zone blank", {"environment"},
     lambda c: _facts(c, fema_zone="", fema_sfha=None)),
    ("rule_missing", "district rule row missing (rule=None)", {"use", "dimensional"},
     lambda c: replace(c, rule=None)),
    ("assess_area_none", "assessment lot area unknown", {"dimensional"},
     lambda c: _facts(c, assess_lotarea_sf=None)),
    ("gis_area_none", "County GIS area unknown", {"dimensional"},
     lambda c: _facts(c, county_gis_area_sf=None)),
    ("both_areas_none", "both lot areas unknown", {"dimensional"},
     lambda c: _facts(c, assess_lotarea_sf=None, county_gis_area_sf=None)),
    ("geometry_none", "bounding-rectangle sides unknown", {"dimensional"},
     lambda c: _facts(c, mbr_short_side_ft=None, mbr_long_side_ft=None)),
    ("corner_blank_exterior", "possible corner with blank exterior-side setback", {"dimensional"},
     lambda c: _rule(_facts(c, possible_corner=True), exterior_side_ft=None)),
    ("min_lot_blank", "district minimum lot size blank", {"dimensional"},
     lambda c: _rule(c, min_lot_sf=None)),
    ("permission_unrecognized", "permission code outside vocabulary ('X')", {"use"},
     lambda c: _rule(c, single_unit_permission="X")),
    *(
        (f"layer_{sid}", f"layer query incomplete: {sid}", {"environment"},
         (lambda s: (lambda c: _layer_failed(c, s)))(sid))
        for sid in LAYERS
    ),
)

# Keyword the parcel-specific check naming the injected input must contain.
NAMED_INPUT = {
    "fema_D": "floodplain", "fema_unrecognized": "floodplain", "fema_blank": "floodplain",
    "rule_missing": "district rules", "assess_area_none": "record-area", "gis_area_none": "record-area",
    "both_areas_none": "record-area", "geometry_none": "parcel geometry",
    "corner_blank_exterior": "exterior side", "min_lot_blank": "minimum lot size",
    "permission_unrecognized": "zoning/use table",
    **{f"layer_{sid}": "re-run screening layer query" for sid in LAYERS},
}

# Fields no decision output reads (per engine code); changing them must not change the fingerprint.
IRRELEVANT = (
    ("pli_latest_event", lambda c: _facts(c, pli_latest_event="1999-01-01")),
    ("pli_unique_casefiles", lambda c: _facts(c, pli_unique_casefiles=c.facts.pli_unique_casefiles + 7)),
    ("neighborhood", lambda c: _facts(c, neighborhood="Elsewhere")),
    ("streets_within_30ft", lambda c: _facts(c, streets_within_30ft=("Nowhere Way",))),
    ("condemned_case_address (case inactive)", lambda c: _facts(c, condemned_case_address="1 Test St")),
)


def _components(r):
    return {c.name: c for c in (r.use, r.dimensional, r.environment) if c is not None}


def _new_zero(base, r) -> list[str]:
    """Components that became known 0 (or a range starting at 0) though not 0 in the base."""
    b, n = _components(base), _components(r)
    out = []
    for name, c in n.items():
        if c.status in ("known", "range") and c.low == 0:
            bc = b.get(name)
            if bc is None or bc.status not in ("known", "range") or bc.low != 0:
                out.append(name)
    return out


def run() -> Section:
    from lotline.engine import screen
    from lotline.engine.checks import is_standard
    from lotline.models import Outcome

    results = screen_all()
    advance_pins = sorted(p for p, r in results.items() if r.outcome is Outcome.ADVANCE)
    ck = Checks()
    ck.check("7 real Advance parcels available as bases", len(advance_pins) == 7, str(len(advance_pins)))

    from evaluation.common import context
    bases = {p: context(p) for p in advance_pins}

    detail_rows = []
    agg = {cid: {"n": 0, "advance": 0, "zero": 0, "expected_withheld": 0, "named_check": 0, "barrier": 0,
                 "names_input": 0, "first_names_input": 0}
           for cid, *_ in INJECTIONS}
    records = []
    for pin, ctx in bases.items():
        base = results[pin]
        for cid, desc, expect, inject in INJECTIONS:
            r = screen(inject(ctx))
            comps = _components(r)
            withheld = sorted(n for n, c in comps.items() if c.status == "withheld")
            zero = _new_zero(base, r)
            specific = next((nc for nc in r.next_checks if not is_standard(nc)), None)
            a = agg[cid]
            a["n"] += 1
            a["advance"] += r.outcome is Outcome.ADVANCE
            a["zero"] += bool(zero)
            a["expected_withheld"] += expect <= set(withheld)
            a["named_check"] += specific is not None
            a["barrier"] += bool(r.barriers)
            kw = NAMED_INPUT[cid]
            specifics = [nc.check for nc in r.next_checks if not is_standard(nc)]
            a["names_input"] += any(kw in t for t in specifics)
            a["first_names_input"] += bool(specifics) and kw in specifics[0]
            records.append({"pin": pin, "case": cid, "outcome": r.outcome.value, "withheld": withheld,
                            "new_zero": zero, "first_check": specific.check if specific else None})
            if pin == named_context("benezet").pin:
                detail_rows.append((desc, r.outcome.value, withheld or "none", zero or "none",
                                    r.outcome is Outcome.ADVANCE,
                                    f"{specific.check} — {specific.owner}" if specific else "none",
                                    r.barriers[0] if r.barriers else "none"))

    total = sum(a["n"] for a in agg.values())
    adv = sum(a["advance"] for a in agg.values())
    zeros = sum(a["zero"] for a in agg.values())
    exp_ok = sum(a["expected_withheld"] for a in agg.values())
    named = sum(a["named_check"] for a in agg.values())
    ck.check("no Advance under any injection", adv == 0, f"{adv}/{total}")
    ck.check("no unknown converted to a new known 0", zeros == 0, f"{zeros}/{total}")
    ck.check("expected component withheld in every injection", exp_ok == total, f"{exp_ok}/{total}")
    names = sum(a["names_input"] for a in agg.values())
    first_names = sum(a["first_names_input"] for a in agg.values())
    ck.check("a parcel-specific check names the injected input in every case", names == total,
             f"{names}/{total}")
    ck.check("every injected case has a named parcel-specific next check and a barrier",
             named == total and all(a["barrier"] == a["n"] for a in agg.values()), f"{named}/{total}")

    agg_rows = [(cid, desc, frac(agg[cid]["advance"], agg[cid]["n"]), frac(agg[cid]["zero"], agg[cid]["n"]),
                 frac(agg[cid]["expected_withheld"], agg[cid]["n"]), frac(agg[cid]["names_input"], agg[cid]["n"]),
                 frac(agg[cid]["first_names_input"], agg[cid]["n"]))
                for cid, desc, *_ in INJECTIONS]

    # --- corner uncertainty is a bounded range, not a guess -----------------------
    ben = named_context("benezet")
    r_corner = screen(ben)
    r_int = screen(_facts(ben, possible_corner=False))
    ck.check("unresolved corner → dimensional range with both scenarios; resolved interior → known",
             r_corner.dimensional.status == "range" and len(r_corner.scenarios) == 2
             and r_int.dimensional.status == "known" and len(r_int.scenarios) == 1,
             f"{component_text(r_corner.dimensional)} vs {component_text(r_int.dimensional)}")
    ck.check("range bounds contain the interior score",
             r_corner.dimensional.low <= r_int.dimensional.low <= r_corner.dimensional.high, "")

    # --- negative controls ---------------------------------------------------------
    neg_rows = []
    neg_ok = neg_n = 0
    for pin, ctx in bases.items():
        base_fp = fingerprint(results[pin])
        again = fingerprint(screen(ctx))
        neg_n += 1
        neg_ok += again == base_fp
        if pin == ben.pin:
            neg_rows.append(("unperturbed re-screen", "unchanged" if again == base_fp else "CHANGED"))
        for name, inject in IRRELEVANT:
            fp = fingerprint(screen(inject(ctx)))
            neg_n += 1
            neg_ok += fp == base_fp
            if pin == ben.pin:
                neg_rows.append((f"irrelevant field: {name}", "unchanged" if fp == base_fp else "CHANGED"))
    ck.check("negative controls: all decision outputs unchanged", neg_ok == neg_n, f"{neg_ok}/{neg_n}")

    md = [
        "**Cohort:** the 7 real parcels whose committed-snapshot outcome is Advance; each receives each "
        f"of {len(INJECTIONS)} single-input injections in memory ({total} screens). Benezet (131-N-31) is "
        "shown in full; the aggregate table covers all 7 bases (denominator n = 7 per injection).",
        md_table(["Injection (Benezet)", "Outcome", "Withheld", "New known-0", "Advanced?",
                  "First parcel-specific check — owner", "Principal barrier"], detail_rows, sort=False),
        md_table(["Case", "Injection", "Advanced (n/7)", "New known-0 (n/7)", "Expected component withheld (n/7)",
                  "Check names the input (n/7)", "…as first parcel-specific check (n/7)"], agg_rows, sort=False),
        f"**Totals:** Advance {adv}/{total}; unknown scored as zero {zeros}/{total}; expected withholding "
        f"{exp_ok}/{total}; a check names the injected input {names}/{total} (first parcel-specific check "
        f"{first_names}/{total}).",
        "**Corner uncertainty (Benezet):** unresolved corner status gives dimensional "
        f"`{component_text(r_corner.dimensional)}` and ease `{r_corner.ease.display}`; resolving it to "
        f"interior gives `{component_text(r_int.dimensional)}` and `{r_int.ease.display}`. The range is "
        "bounded by the two computed scenarios, not imputed.",
        "**Negative controls** (Benezet shown; all 7 bases counted: "
        f"{neg_ok}/{neg_n} unchanged):",
        md_table(["Control", "Decision outputs"], neg_rows, sort=False),
        "**Observations (wording, not decisions):** with the district rule row missing, the named check "
        "reads \"add or review <district> district rules for use and dimensions (missing from LotLine)\" "
        "(fixed after this experiment first flagged an awkward label), and one check covers both withheld "
        "components; the tool-limitation barrier routes the question to the Zoning Administrator. "
        "Neither affects any outcome or score.",
        ck.markdown(),
        scope_note(
            "It shows that, for the enumerated single-input injections on the 7 Advance parcels, the engine "
            "withholds rather than zero-fills, never advances with an unknown, and names a parcel-specific "
            "check and owner, while unrelated inputs leave every decision output unchanged. It does not show "
            "behaviour under simultaneous multiple missing inputs beyond those enumerated, nor that the "
            "committed values themselves are complete or correct (a value that is wrong but present is not "
            "'missing' and is not caught here), nor that the named owner is the right real-world resolver."
        ),
    ]
    data = {"cohort": "7 Advance parcels × injections", "screens": total,
            "aggregate": agg, "records": sorted(records, key=lambda d: (d["case"], d["pin"])),
            "negative_controls": [neg_ok, neg_n]}
    verdict = {"advance_under_injection": f"{adv}/{total}", "unknown_as_zero": f"{zeros}/{total}",
               "expected_withholding": f"{exp_ok}/{total}", "named_check": f"{named}/{total}",
               "check_names_input": f"{names}/{total}", "first_check_names_input": f"{first_names}/{total}",
               "negative_controls_unchanged": f"{neg_ok}/{neg_n}",
               "corner_range": component_text(r_corner.dimensional)}
    return Section("missingness", "Missingness and uncertainty injection", "\n\n".join(md), data, verdict,
                   ck.items)
