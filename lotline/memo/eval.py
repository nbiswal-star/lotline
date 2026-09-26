"""Run the ten contract regression/adversarial cases and report raw counts.

``run_cases()`` returns one ``CaseResult`` per case in build contract section
6. The integrity panel shows ``summary(results)`` (e.g. "10/10 cases
passed"): raw counts on fixed cases, never a population accuracy claim.
Parcels come from the snapshot by location name; synthetic cases are labeled.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from lotline.engine import screen
from lotline.loaders import context_for, load_snapshot, lookup_pin
from lotline.memo import synthetic as syn
from lotline.memo.checker import check
from lotline.memo.claims import Claim
from lotline.memo.deterministic import deterministic_memo, unknown_pin_memo
from lotline.memo.pipeline import produce_memo
from lotline.memo.text import ngrams
from lotline.models import ConflictLevel, Outcome, ScreeningResult, Snapshot, derived_fact_id, fact_id


@dataclass
class CaseResult:
    number: int
    title: str
    synthetic: bool
    passed: bool = True
    checks: list[tuple[str, bool]] = field(default_factory=list)

    def expect(self, label: str, ok: bool) -> None:
        self.checks.append((label, bool(ok)))
        self.passed = self.passed and bool(ok)

    @property
    def detail(self) -> str:
        return "; ".join(f"{'ok' if ok else 'FAIL'}: {label}" for label, ok in self.checks)


def _memo_ok(r: ScreeningResult) -> tuple[str, bool]:
    memo = deterministic_memo(r)
    rep = check(memo.claims, r)
    return memo.text, rep.ok


def _rejected(r: ScreeningResult, claims: list[Claim]) -> bool:
    memo = produce_memo(r, claims)
    return memo.source == "deterministic" and memo.rejected_draft is not None


def _claim(text: str, ids: tuple[str, ...], ctype: str = "fact") -> list[Claim]:
    return [Claim(text, ids, ctype, "llm")]  # type: ignore[arg-type]


def case_1(s: Snapshot) -> CaseResult:
    c = CaseResult(1, "Centre Ave 10S5: vacant vs active condemned case", False)
    r = screen(syn.hero_context(s, "centre_10s5"))
    c.expect("critical current-condition conflict",
             any(x.kind == "current_condition" and x.level is ConflictLevel.CRITICAL for x in r.conflicts))
    c.expect("not scorable", r.ease is not None and r.ease.display == "Not scorable")
    text, ok = _memo_ok(r)
    c.expect("deterministic memo passes checker", ok)
    c.expect("memo says current site condition is unverified", "current site condition is unverified" in text.lower())
    c.expect("memo has no score", not re.search(r"\d\s*(?:-\s*\d\s*)?of 6|use \d|environment \d", text))
    pin = r.pin
    for bad, ids, ct in (
        ("The lot is vacant.", (fact_id(pin, "usedesc"),), "fact"),
        ("The building was demolished.", (fact_id(pin, "condemned_case_active"),), "fact"),
        ("Development Ease: 3 of 6.", (derived_fact_id(pin, "ease_result"),), "score"),
    ):
        c.expect(f"rejects {bad!r}", _rejected(r, _claim(bad, ids, ct)))
    return c


def case_2(s: Snapshot) -> CaseResult:
    c = CaseResult(2, "Centre Ave 10S5: area sources straddle the district minimum", False)
    r = screen(syn.hero_context(s, "centre_10s5"))
    c.expect("material lot-area conflict",
             any(x.kind == "lot_area" and x.level is ConflictLevel.MATERIAL for x in r.conflicts))
    c.expect("dimensional withheld", r.dimensional is not None and r.dimensional.status == "withheld")
    text, ok = _memo_ok(r)
    c.expect("deterministic memo passes checker", ok)
    c.expect("memo: sources disagree on lot area; conformity requires deed/survey review",
             "sources disagree on lot area; conformity requires deed/survey review" in text.lower())
    area = (fact_id(r.pin, "assess_lotarea_sf"),)
    for bad in ("The lot is substandard.", "The lot is conforming.", "The lot conforms to the minimum."):
        c.expect(f"rejects {bad!r}", _rejected(r, _claim(bad, area)))
    return c


def case_3(s: Snapshot) -> CaseResult:
    c = CaseResult(3, "Garfield Ave: in WPRDC, not in the 9/16 advertisement", False)
    r = screen(syn.hero_context(s, "garfield"))
    c.expect("routed out of sale universe", r.outcome is Outcome.OUT_OF_UNIVERSE)
    text, ok = _memo_ok(r)
    c.expect("deterministic memo passes checker", ok)
    c.expect("memo: not in the City advertisement dated 2026-09-16", "not in the City advertisement dated 2026-09-16" in text)
    sd = (fact_id(r.pin, "sale_date", "wprdc_treasury_sales"),)
    c.expect("rejects 'for sale on Oct 2'", _rejected(r, _claim("The lot is for sale on Oct 2.", sd)))
    return c


def case_4(s: Snapshot) -> CaseResult:
    c = CaseResult(4, "Kemper St: large area gap that crosses no known threshold", False)
    r = screen(syn.hero_context(s, "kemper"))
    lot = [x for x in r.conflicts if x.kind == "lot_area"]
    c.expect("area gap is disclose-level", bool(lot) and all(x.level is ConflictLevel.DISCLOSE for x in lot))
    c.expect("whole parcel not 'Not scorable'", r.ease is not None and r.ease.display != "Not scorable")
    dim = r.dimensional
    c.expect("any dimensional withholding is not attributed to the gap",
             dim is None or dim.status != "withheld" or "disagree" not in (dim.reason or ""))
    text, ok = _memo_ok(r)
    c.expect("deterministic memo passes checker", ok)
    c.expect("memo: area records disagree (disclosed)", "area records disagree (disclosed)" in text.lower())
    ease = (derived_fact_id(r.pin, "ease_result"),)
    c.expect("rejects 'not scorable'", _rejected(r, _claim("Kemper St is not scorable.", ease, "status")))
    c.expect("rejects attributing withholding to the gap",
             _rejected(r, _claim("Dimensional fit is withheld because of the area gap.", ease, "status")))
    return c


def case_5(s: Snapshot) -> CaseResult:
    c = CaseResult(5, "Mossfield St: disclosed gap, both sources above the minimum", False)
    r = screen(syn.hero_context(s, "mossfield"))
    lot = [x for x in r.conflicts if x.kind == "lot_area"]
    c.expect("disclose only", bool(lot) and all(x.level is ConflictLevel.DISCLOSE for x in lot))
    text, ok = _memo_ok(r)
    c.expect("deterministic memo passes checker", ok)
    c.expect("memo: both sources exceed the minimum", "both sources exceed the" in text.lower())
    ease = (derived_fact_id(r.pin, "ease_result"),)
    c.expect("rejects 'conflict prevents scoring'",
             _rejected(r, _claim("The area conflict prevents scoring.", ease, "status")))
    return c


def case_6(s: Snapshot) -> CaseResult:
    c = CaseResult(6, "SYNTHETIC injection in violation text", True)
    inj = syn.injection_case(s)
    c.expect("engine result unchanged", syn.decision_view(inj.baseline) == syn.decision_view(inj.injected))
    for n, draft in enumerate(inj.drafts, 1):
        c.expect(f"injection draft {n} rejected", _rejected(inj.injected, list(draft)))
    memo = produce_memo(inj.injected, None)
    c.expect("accepted memo passes checker", memo.report is not None and memo.report.ok)
    c.expect("no injected instruction in accepted memo",
             not (ngrams(syn.INJECTION_TEXT, 4) & ngrams(memo.text, 4)) and "buildable" not in memo.text.lower())
    return c


def case_7(s: Snapshot) -> CaseResult:
    c = CaseResult(7, "Unknown PIN typed in search", False)
    query = "9999Z99999"
    pin = lookup_pin(s, query)
    c.expect("PIN not found", pin is None)
    c.expect("no context/packet", pin is None or context_for(s, pin) is None)
    as_of = s.manifest["wprdc_treasury_sales"].snapshot_as_of
    memo = unknown_pin_memo(query, as_of)
    c.expect("no fabricated facts", all(not cl.fact_ids for cl in memo.claims))
    c.expect("states 'PIN not found in snapshot dated X'", f"PIN not found in snapshot dated {as_of}" in memo.text)
    return c


def case_8(s: Snapshot) -> CaseResult:
    c = CaseResult(8, "SYNTHETIC stale source snapshot", True)
    r = screen(syn.stale_context(s))
    text, ok = _memo_ok(r)
    c.expect("warning raised", any("sale status may have changed by payment or court order" in w for w in r.warnings))
    c.expect("deterministic memo passes checker", ok)
    c.expect("memo carries the warning", "sale status may have changed by payment or court order" in text)
    c.expect("memo never says 'will be sold'", "will be sold" not in text.lower())
    for n, draft in enumerate(syn.stale_drafts(r), 1):
        c.expect(f"'will be sold' draft {n} rejected", _rejected(r, draft))
    return c


def case_9(s: Snapshot) -> CaseResult:
    c = CaseResult(9, "Michigan St 15S66: possible corner", False)
    r = screen(syn.hero_context(s, "michigan_15s66"))
    c.expect("dimensional shown as a range",
             r.dimensional is not None and r.dimensional.status == "range")
    c.expect("setback screen gives the if-corner scenario", "if corner" in r.setback_screen)
    text, ok = _memo_ok(r)
    c.expect("deterministic memo passes checker", ok)
    w = (derived_fact_id(r.pin, "envelope_interior_width_ft"),)
    interior = next((sc for sc in r.scenarios if sc.label == "interior"), None)
    single = f"The illustrative envelope is about {round(interior.width_ft) if interior else 0} ft wide."
    c.expect("rejects a single envelope number", _rejected(r, _claim(single, w)))
    return c


def case_10(s: Snapshot) -> CaseResult:
    c = CaseResult(10, "SYNTHETIC memo tries to resolve the area conflict", True)
    r = screen(syn.hero_context(s, "centre_10s5"))
    memo = produce_memo(r, syn.conflict_resolution_draft(r))
    c.expect("fixed draft rejected; deterministic memo substituted",
             memo.source == "deterministic" and memo.rejected_draft is not None)
    c.expect("substituted memo passes checker", memo.report is not None and memo.report.ok)
    gis = (fact_id(r.pin, "county_gis_area_sf"), fact_id(r.pin, "assess_lotarea_sf"))
    for text in syn.SOURCE_SELECTION_PARAPHRASES:
        c.expect(f"rejects paraphrase {text!r}", _rejected(r, _claim(text, gis)))
    return c


CASES: tuple[Callable[[Snapshot], CaseResult], ...] = (
    case_1, case_2, case_3, case_4, case_5, case_6, case_7, case_8, case_9, case_10,
)


def run_cases(snapshot: Snapshot | None = None) -> list[CaseResult]:
    s = snapshot or load_snapshot()
    out = []
    for n, fn in enumerate(CASES, 1):
        try:
            out.append(fn(s))
        except Exception as exc:  # noqa: BLE001 - a crash is a failed case, not a crashed panel
            res = CaseResult(n, fn.__name__, False)
            res.expect(f"raised {type(exc).__name__}: {exc}", False)
            out.append(res)
    return out


def summary(results: list[CaseResult]) -> str:
    return f"{sum(r.passed for r in results)}/{len(results)} cases passed"
