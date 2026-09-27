"""Experiment 1: independent cohort reconstruction (H1).

This does NOT use ``lotline.reconcile`` as the oracle. It re-reads the two raw
CSVs with pandas (allowed columns only; the Treasury answer-key columns
``sale_flag`` etc. are never selected) and joins them with an evaluation-only
rule that is structurally different from production:

* Production builds a 16-character PIN from the account string (regex + padding
  rules) and matches it exactly.
* This module joins on the **map-block-lot stem** (the 10 characters after the
  ``1`` + 2-digit ward prefix) plus the 2-digit card, and accepts a Treasury PIN
  only if its 4-character supplement is *compatible* with the account's
  (possibly abbreviated) supplement: equal after deleting zero characters
  (``""`` ~ ``0000``, ``A`` ~ ``000A``, ``B3`` ~ ``B003``). It then requires the
  match to be unique. This rule was derived by inspecting the advertisement
  rows (the only abbreviated shapes present are blank, one letter, and
  letter+digit) and is reported with the observed shape counts below.

Prices are compared in integer cents (Decimal), not floats.
"""

from __future__ import annotations

import re
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from evaluation.common import (
    DATA_DIR,
    FIXTURES_DIR,
    Checks,
    Section,
    md_table,
    scope_note,
    snapshot,
)

TREASURY_FILE = DATA_DIR / "treasury_sale_2026-10-02_enriched.csv"
ADVERT_FILE = DATA_DIR / "advert_2026-09-16_reconciliation.csv"
PARCEL_FILE = DATA_DIR / "parcel_facts.csv"
# Allowed columns only (same allowlist spirit as the loader; no answer-key columns).
TREASURY_COLS = ["pin", "address", "ward", "total_tax_due", "usedesc", "nbhd"]
ADVERT_COLS = ["sale_no", "account", "pin", "ad_address", "upset"]

# Known, disclosed exception (see task brief and docs): account ward prefix 19
# while the Treasury record says ward 20.
KNOWN_WARD_EXCEPTIONS = {"0035N00157000000": ("19", "20")}


def cents(text: str) -> int:
    return int((Decimal(text.strip()) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_account(account: str) -> dict[str, str]:
    """Split an advertisement account into ward, map-block-lot stem, supplement, card.

    Shapes observed: ``1WW`` + 10-char stem + 6 chars (supp+card) with no space,
    or ``1WW`` + stem + abbreviated supplement + whitespace + 2-digit card.
    """
    s = account.strip().upper()
    if not s.startswith("1") or len(s) < 13:
        raise ValueError(f"unparseable account {account!r}")
    ward, rest = s[1:3], s[3:]
    stem, tail = rest[:10], rest[10:]
    if " " in tail:
        parts = tail.split()
        supp, card = ("", parts[0]) if len(parts) == 1 else (parts[0], parts[-1])
    else:
        supp, card = tail[:4], tail[4:]
    return {"ward": ward, "stem": stem, "supp": supp, "card": card,
            "shape": "full" if " " not in tail else ("abbrev:" + (re.sub(r"\d", "9", re.sub(r"[A-Z]", "A", supp)) or "blank"))}


def supp_compatible(abbrev: str, full: str) -> bool:
    return abbrev.replace("0", "") == full.replace("0", "")


def _norm_street(text: str) -> str:
    """Street text for comparison; a leading house number 0 (advertisement convention for
    lots without a number) is dropped, so "0 Wylie Ave" compares equal to "WYLIE AVE"."""
    s = text.split(",")[0].upper()
    s = re.sub(r"^0\s+", "", s.strip())
    s = re.sub(r"\bUNIT\b.*$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def independent_join() -> dict:
    t = pd.read_csv(TREASURY_FILE, dtype=str, keep_default_na=False, usecols=TREASURY_COLS)
    a = pd.read_csv(ADVERT_FILE, dtype=str, keep_default_na=False, usecols=ADVERT_COLS)
    t_rows = {r["pin"]: r for r in t.to_dict("records")}
    by_stem: dict[tuple[str, str], list[str]] = {}
    for pin in t_rows:
        by_stem.setdefault((pin[:10], pin[14:16]), []).append(pin)

    matches: dict[str, dict] = {}  # treasury pin -> advert row info
    unmatched_advert: list[dict] = []
    shapes: Counter[str] = Counter()
    exceptions: list[tuple] = []
    for r in a.to_dict("records"):
        p = parse_account(r["account"])
        shapes[p["shape"]] += 1
        cands = [pin for pin in by_stem.get((p["stem"], p["card"]), [])
                 if supp_compatible(p["supp"], pin[10:14])]
        if len(cands) != 1:
            unmatched_advert.append({"account": r["account"], "candidates": cands})
            exceptions.append((r["sale_no"], r["account"], "join", f"{len(cands)} Treasury candidates"))
            continue
        pin = cands[0]
        tr = t_rows[pin]
        price_ok = cents(r["upset"]) == cents(tr["total_tax_due"])
        ward_ok = int(p["ward"]) == int(tr["ward"])
        pin_col_ok = r["pin"].strip() == pin
        addr_ok = _norm_street(r["ad_address"]) == _norm_street(tr["address"])
        no_number = not re.match(r"^\s*[1-9]", tr["address"])
        matches[pin] = {
            "sale_no": int(r["sale_no"]), "account": r["account"], "account_ward": str(int(p["ward"])),
            "treasury_ward": str(int(tr["ward"])), "upset_cents": cents(r["upset"]),
            "tax_due_cents": cents(tr["total_tax_due"]), "price_ok": price_ok, "ward_ok": ward_ok,
            "pin_column_agrees": pin_col_ok, "address_agrees": addr_ok,
            "ad_address": r["ad_address"], "treasury_address": tr["address"].split(",")[0],
            "vacant": "VACANT" in tr["usedesc"].upper(), "usedesc": tr["usedesc"],
            "no_house_number": no_number,
        }
        if no_number and "VACANT" not in tr["usedesc"].upper():
            exceptions.append((r["sale_no"], pin, "no house number but assessment use is a structure "
                               "(disclosed; routed as structure)",
                               f"{tr['address'].split(',')[0]!r}; usedesc {tr['usedesc']}"))
        if not price_ok:
            exceptions.append((r["sale_no"], pin, "price", f"{r['upset']} vs {tr['total_tax_due']}"))
        if not pin_col_ok:
            exceptions.append((r["sale_no"], pin, "advert pin column", r["pin"]))
        if not ward_ok:
            known = KNOWN_WARD_EXCEPTIONS.get(pin) == (str(int(p["ward"])), str(int(tr["ward"])))
            exceptions.append((r["sale_no"], pin, "ward prefix vs Treasury ward"
                               + (" (known, disclosed)" if known else " (UNEXPECTED)"),
                               f"account ward {int(p['ward'])} vs Treasury ward {int(tr['ward'])}"))
        if not addr_ok:
            exceptions.append((r["sale_no"], pin, "address text differs",
                               f"{r['ad_address']!r} vs {tr['address'].split(',')[0]!r}"))
    unmatched_treasury = sorted(set(t_rows) - set(matches))
    usedesc_all = Counter(r["usedesc"] for r in t_rows.values())
    return {
        "treasury_n": len(t_rows), "advert_n": len(a), "matches": matches,
        "unmatched_advert": unmatched_advert, "unmatched_treasury": unmatched_treasury,
        "shapes": dict(sorted(shapes.items())), "exceptions": exceptions,
        "t_rows": t_rows, "usedesc_all": usedesc_all, "advert_pins_col": sorted(a["pin"].str.strip()),
    }


def run() -> Section:
    j = independent_join()
    ck = Checks()
    m = j["matches"]
    matched = set(m)
    n_price = sum(v["price_ok"] for v in m.values())
    vacant = sorted(p for p, v in m.items() if v["vacant"])
    structures = sorted(p for p, v in m.items() if not v["vacant"])
    ward_exc = sorted(p for p, v in m.items() if not v["ward_ok"])
    addr_exc = sorted(p for p, v in m.items() if not v["address_agrees"])
    pin_col_ok = sum(v["pin_column_agrees"] for v in m.values())

    ck.check("Treasury records = 96", j["treasury_n"] == 96, str(j["treasury_n"]))
    ck.check("advertised records = 77", j["advert_n"] == 77, str(j["advert_n"]))
    ck.check("independent join matches 77/77 advertised records uniquely",
             len(matched) == 77 and not j["unmatched_advert"], f"{len(matched)} matched")
    ck.check("19 Treasury records not advertised", len(j["unmatched_treasury"]) == 19,
             str(len(j["unmatched_treasury"])))
    ck.check("price cross-check to the cent 77/77", n_price == 77, f"{n_price}/77")
    ck.check("advertised structures 63 / vacant 14", (len(structures), len(vacant)) == (63, 14),
             f"{len(structures)}/{len(vacant)}")
    ck.check("advert pin column agrees with independent join 77/77", pin_col_ok == 77, f"{pin_col_ok}/77")
    ck.check("street text agrees after house-number-0 normalization 77/77", not addr_exc,
             f"{77 - len(addr_exc)}/77")
    ck.check("only ward exception is the known, disclosed one",
             ward_exc == sorted(KNOWN_WARD_EXCEPTIONS), ", ".join(ward_exc) or "none")

    # Compare to lotline's runtime reconciliation (production code path).
    snap = snapshot()
    rec = snap.reconciliation
    agree_matched = len(matched & rec.matched_pins)
    agree_price = len({p for p, v in m.items() if v["price_ok"]} & rec.price_check_pass)
    runtime_vacant = sorted(p for p in rec.matched_pins if not snap.treasury[p].is_structure)
    struct_agree = sum(
        (snap.treasury[p].is_structure) == ("VACANT" not in j["t_rows"][p]["usedesc"].upper())
        for p in j["t_rows"]
    )
    ck.check("independent vs runtime: matched set agrees 77/77",
             agree_matched == 77 and matched == set(rec.matched_pins), f"{agree_matched}/77")
    ck.check("independent vs runtime: price-pass set agrees 77/77", agree_price == 77, f"{agree_price}/77")
    ck.check("independent vs runtime: unmatched Treasury set agrees 19/19",
             set(j["unmatched_treasury"]) == set(rec.unmatched_treasury_pins), "")
    ck.check("independent vs runtime: vacancy classification agrees 96/96", struct_agree == 96,
             f"{struct_agree}/96")
    ck.check("independent vs runtime: 14 vacant advertised set identical", vacant == runtime_vacant, "")

    # Secondary comparison: team-prepared pre-event reconciliation file (test fixture).
    fx = pd.read_csv(FIXTURES_DIR / "expected_reconciliation.csv", dtype=str, keep_default_na=False)
    fx_in = {r["pin"]: r for r in fx.to_dict("records")}
    fx_agree = sum((fx_in[p]["in_city_advert_2026_09_16"] == "Y") == (p in matched) for p in j["t_rows"]
                   if p in fx_in)
    fx_sale = sum(str(m[p]["sale_no"]) == fx_in[p]["advert_sale_no"] for p in matched if p in fx_in)
    ck.check("agreement with team-prepared reconciliation fixture (in advert Y/N) 96/96",
             fx_agree == 96 and len(fx_in) == 96, f"{fx_agree}/{len(fx_in)}")
    ck.check("agreement with fixture sale numbers 77/77", fx_sale == 77, f"{fx_sale}/77")

    # parcel_facts upset_price vs advertised upset (prepared-facts cross-check).
    pf = pd.read_csv(PARCEL_FILE, dtype=str, keep_default_na=False, usecols=["pin", "upset_price", "location"])
    pf_rows = []
    pf_ok = 0
    pf_adv = 0
    for r in pf.to_dict("records"):
        if r["pin"] in m:
            pf_adv += 1
            ok = cents(r["upset_price"]) == m[r["pin"]]["upset_cents"]
            pf_ok += ok
            if not ok:
                pf_rows.append((r["pin"], r["location"], r["upset_price"], m[r["pin"]]["upset_cents"] / 100))
    ck.check("parcel_facts upset_price equals advertised upset for every advertised prepared parcel",
             pf_ok == pf_adv == 14, f"{pf_ok}/{pf_adv}")

    counts = [
        ("Treasury source records (WPRDC snapshot 2026-09-24)", j["treasury_n"], "96 (all rows)"),
        ("Advertisement rows (City advertisement 2026-09-16)", j["advert_n"], "77 (all rows)"),
        ("Advertised rows joined uniquely to Treasury", len(matched), f"{len(matched)}/77"),
        ("Treasury rows not in advertisement (routed, retained)", len(j["unmatched_treasury"]), "19/96"),
        ("Upset price = Treasury total tax due, to the cent", n_price, f"{n_price}/77"),
        ("Advertised structures (usedesc lacks VACANT)", len(structures), f"{len(structures)}/77"),
        ("Advertised vacant (usedesc contains VACANT)", len(vacant), f"{len(vacant)}/77"),
    ]
    adv_use = Counter(v["usedesc"] for v in m.values())
    non_use = Counter(j["t_rows"][p]["usedesc"] for p in j["unmatched_treasury"])
    use_rows = [(u, adv_use.get(u, 0), non_use.get(u, 0), "vacant" if "VACANT" in u.upper() else "structure")
                for u in sorted(j["usedesc_all"])]
    exc_rows = [(int(s), p, kind, d) for s, p, kind, d in j["exceptions"]]
    shapes_rows = list(j["shapes"].items())

    md = []
    md.append(
        "**Cohort:** all 96 WPRDC Treasurer Sales records and all 77 City advertisement rows "
        "(`data/`). **Method:** evaluation-only pandas join on map-block-lot stem + card with a "
        "supplement-compatibility test (see `evaluation/cohort.py` docstring); `lotline.reconcile` "
        "is not used to produce these numbers and is compared only afterwards."
    )
    md.append(md_table(["Quantity", "Count", "n/N"], counts, sort=False))
    md.append("Account shapes observed in the advertisement (basis of the join rule):")
    md.append(md_table(["Account shape (A=letter, 9=digit)", "Rows (of 77)"], shapes_rows))
    md.append("Assessment use descriptions (denominator: 77 advertised, 19 not advertised):")
    md.append(md_table(["usedesc", "Advertised", "Not advertised", "Class"], use_rows))
    md.append(
        f"**Exception rows** (every row-level disagreement; {len(exc_rows)} rows). The ward exception "
        "for 0035N00157000000 is a known, disclosed source discrepancy: the account's ward prefix "
        "(19) differs from the Treasury ward (20); PIN, price and address all agree, so the record "
        "is matched. Street text is compared after dropping the advertisement's house number 0; "
        "an advertised record with no house number whose assessment use is a structure is listed "
        "because it is a plausible false-routing risk (a demolished building would make it a "
        "vacant lot the vacant-land model never sees)."
    )
    md.append(md_table(["Sale #", "PIN / account", "Exception", "Detail"], exc_rows) if exc_rows else "None.")
    md.append(
        "**Independent vs runtime reconciliation** (`snapshot.reconciliation`): "
        f"matched {agree_matched}/77, price-pass {agree_price}/77, not-advertised "
        f"{len(set(j['unmatched_treasury']) & rec.unmatched_treasury_pins)}/19, vacancy class "
        f"{struct_agree}/96. **Team-prepared reconciliation fixture** "
        f"(`tests/fixtures/expected_reconciliation.csv`, prepared by the same team before the build): "
        f"in-advertisement flag {fx_agree}/{len(fx_in)}, sale number {fx_sale}/77. "
        f"Prepared `parcel_facts.upset_price` equals advertised upset for {pf_ok}/{pf_adv} advertised "
        "prepared parcels."
    )
    md.append(ck.markdown())
    md.append(scope_note(
        "It shows that the 96 → 77 (+19 routed) → 63 structures + 14 vacant cohort is reproducible "
        "from the two committed CSVs by a second, structurally different join, with every row-level "
        "exception listed, and that production reconciliation agrees with it. Both joins read the "
        "same committed snapshots, so this does not validate the snapshots against the live City "
        "and WPRDC sources, and it cannot detect an error present in both files (e.g. a parcel "
        "missing from both). Vacancy is taken from the assessment use description, which the "
        "current-condition conflict shows can be out of date."
    ))

    data = {
        "counts": {"treasury": j["treasury_n"], "advertised": j["advert_n"], "matched": len(matched),
                   "not_advertised": len(j["unmatched_treasury"]), "price_pass": n_price,
                   "advertised_structures": len(structures), "advertised_vacant": len(vacant)},
        "advertised_vacant_pins": vacant,
        "not_advertised_pins": j["unmatched_treasury"],
        "account_shapes": j["shapes"],
        "exceptions": [list(e) for e in exc_rows],
        "ward_exceptions": ward_exc,
        "address_text_mismatches": addr_exc,
        "structures_without_house_number": sorted(
            p for p, v in m.items() if v["no_house_number"] and not v["vacant"]),
        "runtime_agreement": {"matched": agree_matched, "price_pass": agree_price,
                              "vacancy_class": struct_agree},
        "fixture_agreement": {"in_advert": fx_agree, "sale_no": fx_sale},
        "parcel_facts_upset_agreement": [pf_ok, pf_adv],
    }
    verdict = {
        "H1_counts": "96/77/19/63/14",
        "independent_matched": f"{len(matched)}/77",
        "price_pass": f"{n_price}/77",
        "runtime_agreement": f"{agree_matched}/77",
        "exceptions": len(exc_rows),
        "unexpected_exceptions": sum("UNEXPECTED" in e[2] for e in exc_rows),
    }
    return Section("cohort", "Cohort reconstruction (independent join)", "\n\n".join(md), data, verdict,
                   ck.items)
