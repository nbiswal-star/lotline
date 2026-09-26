"""Deterministic claim checker: one violation rejects the whole draft.

Every rule is a separate function with a stable rule id so it can be tested,
counted and shown in the integrity panel. Claim-level rules take
``(index, claim, ctx)``; memo-level rules take ``(claims, ctx)``.

The checker never asks a model anything and never changes a claim. It only
compares claim text and citations against the engine's ``ScreeningResult``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import cached_property

from lotline.memo.allowlist import DEFAULT_ALLOWLIST, SectionAllowlist
from lotline.memo.claims import AUTHORS, CLAIM_TYPES, Claim
from lotline.memo.outputs import SETBACK_SCREEN, fact_universe
from lotline.memo.text import (
    Num,
    Token,
    dates_in,
    ngrams,
    num_matches,
    numbers_in,
    split_quotes,
    tokenize,
)
from lotline.models import ConflictLevel, Fact, Outcome, ScreeningResult

# Stable rule ids -------------------------------------------------------------
WELL_FORMED = "WELL_FORMED"
CITE_EXISTS = "CITE_EXISTS"
NUMBERS = "NUMBERS"
CODE_SECTIONS = "CODE_SECTIONS"
STATUS_AGREES = "STATUS_AGREES"
FORBIDDEN_WORDS = "FORBIDDEN_WORDS"
NO_SOURCE_SELECTION = "NO_SOURCE_SELECTION"
CONFLICT_COMPLETENESS = "CONFLICT_COMPLETENESS"
LLM_CANNOT_AUTHOR = "LLM_CANNOT_AUTHOR"
ENGINE_AUTHENTIC = "ENGINE_AUTHENTIC"
QUALIFIERS = "QUALIFIERS"
UNTRUSTED_TEXT = "UNTRUSTED_TEXT"

RULE_IDS: tuple[str, ...] = (
    WELL_FORMED, CITE_EXISTS, NUMBERS, CODE_SECTIONS, STATUS_AGREES, FORBIDDEN_WORDS,
    NO_SOURCE_SELECTION, CONFLICT_COMPLETENESS, LLM_CANNOT_AUTHOR, ENGINE_AUTHENTIC,
    QUALIFIERS, UNTRUSTED_TEXT,
)

# The pending-law lens (Bill 2025-1545) is out of scope in v1: the check exists
# but is disabled, per implementation plan section 6.
PENDING_LAW_QUALIFIER_ENABLED = False


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    claim_index: int | None  # None for memo-level violations
    rule: str
    message: str
    text: str = ""


@dataclass(frozen=True)
class CheckReport:
    violations: tuple[Violation, ...]
    claims_checked: int
    claims: tuple[Claim, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.violations

    def by_rule(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for v in self.violations:
            out[v.rule] = out.get(v.rule, 0) + 1
        return out

    @property
    def rejected_claim_indices(self) -> set[int]:
        return {v.claim_index for v in self.violations if v.claim_index is not None}

    def summary(self) -> str:
        if self.ok:
            return f"{self.claims_checked} claims checked, 0 violations"
        rules = ", ".join(f"{k} x{n}" for k, n in sorted(self.by_rule().items()))
        return f"{self.claims_checked} claims checked, {len(self.violations)} violations ({rules})"


# --------------------------------------------------------------------------
# Context
# --------------------------------------------------------------------------

PIN_RE = r"\d{4}[A-Z]\d{5}[0-9A-Z]{4}\d{2}"
FACT_ID_RE = re.compile(
    r"^(?:RULE:(?P<district>[A-Za-z0-9][A-Za-z0-9.\-]*):[a-z][a-z0-9_]*"
    r"|(?P<pin>" + PIN_RE + r"):[a-z][a-z0-9_]*:[a-z][a-z0-9_]*)$"
)


@dataclass
class CheckContext:
    result: ScreeningResult
    allowlist: SectionAllowlist
    catalog: tuple[Fact, ...] = ()

    @cached_property
    def universe(self) -> dict[str, Fact]:
        return fact_universe(self.result, self.catalog)

    @cached_property
    def district(self) -> str | None:
        """Active parcel's resolved district: zoning polygon, else assessment zoning code."""
        pin = self.result.pin
        for fid in (f"{pin}:zoning_polygon:city_zoning", f"{pin}:zon_code:county_assessments"):
            f = self.universe.get(fid)
            if f is not None and f.value:
                return str(f.value)
        districts = {f.district for f in self.result.facts if f.id.startswith("RULE:") and f.district}
        return districts.pop() if len(districts) == 1 else None

    @cached_property
    def untrusted(self) -> list[Fact]:
        return [f for f in self.universe.values()
                if f.evidence_class == "untrusted_text" and f.pin == self.result.pin]

    def cited(self, claim: Claim) -> list[Fact]:
        """Cited facts that are valid for the active parcel (invalid ones are CITE_EXISTS's job)."""
        out = []
        for fid in claim.fact_ids if isinstance(claim.fact_ids, (tuple, list)) else ():
            f = self.universe.get(fid) if isinstance(fid, str) else None
            if f is None:
                continue
            if f.id.startswith("RULE:"):
                if f.district == self.district:
                    out.append(f)
            elif f.pin == self.result.pin:
                out.append(f)
        return out

    @cached_property
    def engine_texts(self) -> frozenset[str]:
        from lotline.memo.deterministic import engine_claim_texts

        return frozenset(engine_claim_texts(self.result))


ClaimRule = Callable[[int, Claim, CheckContext], list[Violation]]
MemoRule = Callable[[Sequence[Claim], CheckContext], list[Violation]]


def _v(i: int | None, rule: str, msg: str, claim: Claim | None = None) -> list[Violation]:
    return [Violation(i, rule, msg, claim.text if claim is not None else "")]


def _sentences(text: str) -> list[tuple[int, str]]:
    out, start = [], 0
    for m in re.finditer(r"[.;!?](?:\s|$)", text):
        out.append((start, text[start:m.end()]))
        start = m.end()
    if start < len(text):
        out.append((start, text[start:]))
    return out


# --------------------------------------------------------------------------
# WELL_FORMED
# --------------------------------------------------------------------------


def rule_well_formed(i: int, claim: Claim, ctx: CheckContext) -> list[Violation]:
    if not isinstance(claim.text, str) or not claim.text.strip():
        return _v(i, WELL_FORMED, "claim text is empty", claim)
    if claim.claim_type not in CLAIM_TYPES:
        return _v(i, WELL_FORMED, f"invalid claim_type {claim.claim_type!r}", claim)
    if claim.author not in AUTHORS:
        return _v(i, WELL_FORMED, f"invalid author {claim.author!r}", claim)
    if not isinstance(claim.fact_ids, (tuple, list)):
        return _v(i, WELL_FORMED, "fact_ids must be a list of fact id strings", claim)
    return []


# --------------------------------------------------------------------------
# CITE_EXISTS
# --------------------------------------------------------------------------


def rule_cite_exists(i: int, claim: Claim, ctx: CheckContext) -> list[Violation]:
    ids = claim.fact_ids if isinstance(claim.fact_ids, (tuple, list)) else ()
    if not ids:
        if claim.claim_type == "caveat":
            return []
        return _v(i, CITE_EXISTS, f"{claim.claim_type} claim cites no facts", claim)
    out: list[Violation] = []
    for fid in ids:
        if not isinstance(fid, str) or not fid.strip():
            out += _v(i, CITE_EXISTS, f"malformed fact id {fid!r}", claim)
            continue
        m = FACT_ID_RE.match(fid)
        if m is None:
            out += _v(i, CITE_EXISTS, f"malformed fact id {fid!r} (expected PIN:field:source or RULE:district:field)", claim)
            continue
        if m.group("district") is not None:
            district = m.group("district")
            if district != ctx.district:
                out += _v(i, CITE_EXISTS, f"{fid} is a rule for district {district}; the active parcel's "
                          f"resolved district is {ctx.district}", claim)
            elif fid not in ctx.universe:
                out += _v(i, CITE_EXISTS, f"{fid} does not exist", claim)
            continue
        pin = m.group("pin")
        if pin != ctx.result.pin:
            out += _v(i, CITE_EXISTS, f"{fid} belongs to another parcel (cross-parcel citation)", claim)
        elif fid not in ctx.universe:
            out += _v(i, CITE_EXISTS, f"{fid} does not exist in this result's facts", claim)
        elif ctx.universe[fid].pin != ctx.result.pin:
            out += _v(i, CITE_EXISTS, f"{fid} is not a fact of the active parcel", claim)
    return out


# --------------------------------------------------------------------------
# NUMBERS
# --------------------------------------------------------------------------

UNIT_KINDS = {"money": {"USD"}, "percent": {"%"}, "area": {"sf"}, "length": {"ft"}, "ratio": {"ratio"}}
SCORE_KINDS = ("total", "partial", "coverage", "component")
SCORE_CLAIM_TYPES = ("score", "status", "conflict_summary", "caveat")
_SPAN = re.compile(r"^(\d)(?:-(\d))?$")


def _numeric(v: object) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _string_numbers(f: Fact) -> list[Num]:
    vals = f.value if isinstance(f.value, (tuple, list)) else (f.value,)
    out: list[Num] = []
    for v in vals:
        if isinstance(v, str):
            out += numbers_in(v)
    return out


def _fact_dates(f: Fact) -> set[str]:
    out = dates_in(f.as_of or "")
    vals = f.value if isinstance(f.value, (tuple, list)) else (f.value,)
    for v in vals:
        if isinstance(v, str):
            out |= dates_in(v)
    return out


def _date_ok(ref: str, known: set[str]) -> bool:
    if ref in known:
        return True
    md = ref[-5:]
    if ref.startswith("--") or ref.startswith("-"):
        return any(k[-5:] == md for k in known)
    return False


def _span_of(text: str) -> tuple[int, int] | None:
    m = _SPAN.match(text.strip())
    if not m:
        return None
    lo = int(m.group(1))
    return lo, int(m.group(2) or lo)


def _tok_span(tok: Token) -> tuple[int, int]:
    lo = int(tok.nums[0].value)
    hi = int(tok.nums[1].value) if len(tok.nums) > 1 and tok.kind != "partial" else lo
    if tok.kind == "partial" and len(tok.nums) == 3:
        hi = int(tok.nums[1].value)
    return lo, hi


def _score_supported(tok: Token, cited: list[Fact]) -> bool:
    for f in cited:
        val = str(f.value) if f.value is not None else ""
        if tok.kind == "total" and f.field == "ease_result":
            m = re.match(r"^(\d)(?:-(\d))? of 6", val)
            if m and (int(m.group(1)), int(m.group(2) or m.group(1))) == _tok_span(tok):
                return True
        if tok.kind == "partial" and f.field == "ease_result":
            m = re.match(r"^Partial: (\d)(?:-(\d))? of (\d) known", val)
            if m and (int(m.group(1)), int(m.group(2) or m.group(1))) == _tok_span(tok) \
                    and int(m.group(3)) == int(tok.nums[-1].value):
                return True
        if tok.kind == "coverage" and f.field == "evidence_coverage":
            if val.split("/")[0] == str(int(tok.nums[0].value)):
                return True
        if tok.kind == "component" and f.field == f"{tok.name}_score":
            if _span_of(val) == _tok_span(tok):
                return True
    return False


def _quantity_ok(tok: Token, n: Num, cited: list[Fact]) -> bool:
    units = UNIT_KINDS.get(tok.kind)
    for f in cited:
        v = _numeric(f.value)
        if v is not None and (units is None or f.unit in units):
            if num_matches(n, v, approx=tok.approx):
                return True
            if tok.kind == "percent" and num_matches(Num(abs(n.value), n.decimals, n.text), abs(v), approx=tok.approx):
                return True
        # Numbers written inside engine-authored text facts (reasons, barriers,
        # checks, warnings, addresses) may be repeated verbatim.
        for s in _string_numbers(f):
            if num_matches(n, s.value) or (n.value < 0 and num_matches(Num(-n.value, n.decimals, n.text), s.value)):
                return True
    return False


def rule_numbers(i: int, claim: Claim, ctx: CheckContext) -> list[Violation]:
    cited = ctx.cited(claim)
    out: list[Violation] = []
    known_dates: set[str] = set()
    for f in cited:
        known_dates |= _fact_dates(f)
    for tok in tokenize(claim.text):
        if tok.kind == "code":
            continue  # CODE_SECTIONS
        if tok.kind == "pin":
            if tok.ref != ctx.result.pin:
                out += _v(i, NUMBERS, f"PIN {tok.ref} is not the active parcel (cross-parcel)", claim)
            continue
        if tok.kind == "date":
            if not _date_ok(tok.ref, known_dates):
                out += _v(i, NUMBERS, f"date {tok.text!r} does not match any cited fact", claim)
            continue
        if tok.kind in SCORE_KINDS:
            if claim.claim_type not in SCORE_CLAIM_TYPES:
                out += _v(i, NUMBERS, f"score expression {tok.text!r} in a {claim.claim_type} claim; "
                          "scores belong in score/status claims citing engine score facts", claim)
            elif not _score_supported(tok, cited):
                out += _v(i, NUMBERS, f"score expression {tok.text!r} is not supported by a cited engine "
                          "score fact", claim)
            continue
        for n in tok.nums:
            if not _quantity_ok(tok, n, cited):
                out += _v(i, NUMBERS, f"{tok.kind} {n.text!r} in {tok.text!r} does not match any cited "
                          "fact value", claim)
    return out


# --------------------------------------------------------------------------
# CODE_SECTIONS
# --------------------------------------------------------------------------


def rule_code_sections(i: int, claim: Claim, ctx: CheckContext) -> list[Violation]:
    out: list[Violation] = []
    for tok in tokenize(claim.text):
        if tok.kind == "code" and not ctx.allowlist.allows(tok.ref):
            out += _v(i, CODE_SECTIONS, f"code reference {tok.ref!r} is not in allowlist "
                      f"{ctx.allowlist.version} ({ctx.allowlist.as_of})", claim)
    return out


# --------------------------------------------------------------------------
# STATUS_AGREES
# --------------------------------------------------------------------------

OUTCOME_PATTERNS: tuple[tuple[Outcome, re.Pattern[str]], ...] = (
    (Outcome.DO_NOT_ADVANCE, re.compile(r"\bdo(?:es)? not advance\b|\bdon'?t advance\b|\bnot (?:be )?advanced? for housing\b", re.I)),
    (Outcome.OUT_OF_UNIVERSE, re.compile(r"\bout of (?:the )?sale universe\b", re.I)),
    (Outcome.STRUCTURE, re.compile(r"\bvacant-land model not applicable\b", re.I)),
    (Outcome.DEFER_SITE, re.compile(r"\bsite conditions unknown\b", re.I)),
    (Outcome.DEFER_RECORDS, re.compile(r"\bmissing or conflicting records\b", re.I)),
    (Outcome.ADVANCE, re.compile(
        r"\badvance(?:s|d)? to staff review\b|\b(?:should|will|can|could|may|must) (?:be )?advance[ds]?\b"
        r"|\boutcome\W+(?:is\W+)?advance\b|\brecommend(?:s|ed)? (?:to )?advanc\w*|\b(?:ready|qualifies|eligible) to advance\b",
        re.I)),
    (Outcome.SIDE_YARD, re.compile(r"\bside yard\b|\bstewardship\b", re.I)),
)
DEFER_RE = re.compile(r"\bdefer(?:red|s|ral)?\b", re.I)
NOT_EVALUATED_RE = re.compile(r"not (?:evaluated|available|reachable)", re.I)
NEGATED_BEFORE = re.compile(r"\b(?:not|no|never|cannot|isn't|is not)\s+(?:\w+\s+){0,2}$", re.I)

BAND_WORDS = {
    "apparently lower-discretion": re.compile(r"\bapparently lower[- ]discretion\b", re.I),
    "conditional": re.compile(r"\bconditional\b(?!\s+use)", re.I),
    "difficult": re.compile(r"\bdifficult\b", re.I),
}
NOT_SCORABLE_RE = re.compile(r"\bnot scorable\b|\bunscorable\b|\bcannot be scored\b|\bno score (?:can|could) be\b", re.I)
CONFLICT_BLOCKS_RE = re.compile(
    r"\bconflicts? (?:prevents?|blocks?|stops?|precludes?) (?:any )?scor"
    r"|\bwithheld (?:because|due to|owing to|as a result) (?:of )?(?:the )?(?:[\w-]+ ){0,2}(?:gap|conflict|discrepancy|disagreement)"
    r"|\b(?:because of|due to) (?:the )?(?:[\w-]+ ){0,2}(?:gap|conflict|discrepancy|disagreement)[^.;]*\b(?:withheld|not scored|cannot be scored|unscored)",
    re.I,
)
NO_CONFLICT_RE = re.compile(r"\bno (?:records? )?conflicts?\b|\brecords (?:all )?agree\b|\bsources (?:all )?agree\b", re.I)


def _component(result: ScreeningResult, name: str):
    return {"use": result.use, "dimensional": result.dimensional, "environment": result.environment}.get(name)


def rule_status_agrees(i: int, claim: Claim, ctx: CheckContext) -> list[Violation]:
    r = ctx.result
    text = claim.text
    out: list[Violation] = []

    # Outcome language.
    work = text
    for outcome, pat in OUTCOME_PATTERNS:
        for m in list(pat.finditer(work)):
            sentence_tail = work[m.end():].split(".")[0]
            if outcome is Outcome.SIDE_YARD and NOT_EVALUATED_RE.search(sentence_tail):
                continue
            if outcome is Outcome.ADVANCE and NEGATED_BEFORE.search(work[:m.start()]):
                continue
            if outcome is not r.outcome:
                out += _v(i, STATUS_AGREES, f"claims outcome {outcome.value!r} but the engine outcome is "
                          f"{r.outcome.value!r}", claim)
            work = work[:m.start()] + " " * (m.end() - m.start()) + work[m.end():]
    if DEFER_RE.search(work) and r.outcome not in (Outcome.DEFER_RECORDS, Outcome.DEFER_SITE):
        out += _v(i, STATUS_AGREES, f"claims a Defer outcome but the engine outcome is {r.outcome.value!r}", claim)

    # Band language.
    band = (r.ease.band or "").lower() if r.ease else ""
    for word, pat in BAND_WORDS.items():
        if word != "apparently lower-discretion" and claim.claim_type not in ("score", "status") \
                and not re.search(r"\bband\b", text, re.I):
            continue
        if pat.search(text) and word not in band:
            out += _v(i, STATUS_AGREES, f"band {word!r} does not agree with the engine "
                      f"({r.ease.display if r.ease else 'no ease result'})", claim)

    # Score semantics, independent of what the claim cites.
    ease = r.ease
    no_total = ease is None or ease.total_low is None
    not_scorable = ease is None or ease.display in ("Not scorable", "n/a")
    for tok in tokenize(text):
        if tok.kind == "total":
            lo, hi = _tok_span(tok)
            if no_total:
                out += _v(i, STATUS_AGREES, f"{tok.text!r} states a total but the engine shows "
                          f"{ease.display if ease else 'no score'} (no total)", claim)
            elif (lo == hi) != (ease.total_low == ease.total_high):
                kind = "a single total" if lo == hi else "a range"
                out += _v(i, STATUS_AGREES, f"{tok.text!r} states {kind} but the engine shows {ease.display}", claim)
            elif (lo, hi) != (ease.total_low, ease.total_high):
                out += _v(i, STATUS_AGREES, f"{tok.text!r} disagrees with the engine ({ease.display})", claim)
        elif tok.kind == "partial":
            if ease is None or not ease.display.startswith("Partial"):
                out += _v(i, STATUS_AGREES, f"{tok.text!r} states a partial result but the engine shows "
                          f"{ease.display if ease else 'no score'}", claim)
            else:
                lo, hi = _tok_span(tok)
                m = re.match(r"^Partial: (\d)(?:-(\d))? of (\d) known", ease.display)
                engine = (int(m.group(1)), int(m.group(2) or m.group(1)), int(m.group(3))) if m else None
                if engine != (lo, hi, int(tok.nums[-1].value)):
                    out += _v(i, STATUS_AGREES, f"{tok.text!r} disagrees with the engine ({ease.display})", claim)
        elif tok.kind == "component":
            comp = _component(r, tok.name)
            if not_scorable:
                out += _v(i, STATUS_AGREES, f"{tok.text!r} gives a score but the engine shows "
                          f"{ease.display if ease else 'no score'}", claim)
            elif comp is None or comp.status in ("withheld", "not_applicable") or comp.low is None:
                out += _v(i, STATUS_AGREES, f"{tok.text!r} scores a component the engine withholds", claim)
            else:
                lo, hi = _tok_span(tok)
                if (lo == hi) != (comp.low == comp.high) or (lo, hi) != (comp.low, comp.high):
                    out += _v(i, STATUS_AGREES, f"{tok.text!r} disagrees with engine {tok.name} "
                              f"{comp.low}-{comp.high}", claim)
        elif tok.kind == "coverage":
            if int(tok.nums[0].value) != sum(r.coverage.values()):
                out += _v(i, STATUS_AGREES, f"{tok.text!r} disagrees with engine coverage {r.coverage_display}", claim)

    if NOT_SCORABLE_RE.search(text) and not (ease is not None and ease.display == "Not scorable"):
        out += _v(i, STATUS_AGREES, "says the parcel is not scorable but the engine result is "
                  f"{ease.display if ease else 'none'}", claim)
    blocking = [c for c in r.conflicts if c.level in (ConflictLevel.CRITICAL, ConflictLevel.MATERIAL)]
    if CONFLICT_BLOCKS_RE.search(text):
        dim = r.dimensional
        dim_for_conflict = dim is not None and dim.reason is not None and "disagree" in dim.reason
        if not blocking or (re.search(r"withheld", text, re.I) and not dim_for_conflict and not
                            any(c.level is ConflictLevel.CRITICAL for c in r.conflicts)):
            out += _v(i, STATUS_AGREES, "attributes withholding/scoring to a conflict, but no conflict "
                      "withholds a component here", claim)
    if r.conflicts and NO_CONFLICT_RE.search(text):
        out += _v(i, STATUS_AGREES, "says there is no conflict but the engine reports "
                  f"{len(r.conflicts)} conflict(s)", claim)
    return out


# --------------------------------------------------------------------------
# FORBIDDEN_WORDS
# --------------------------------------------------------------------------

ALWAYS_FORBIDDEN: tuple[tuple[str, str], ...] = (
    ("buildable", r"\bbuildable\b|\bbuild[- ]ready\b|\bshovel[- ]ready\b|\bready to build\b|\bsafe to build\b"),
    ("environmentally clear", r"\benvironmentally (?:clear|clean|safe)\b|\bhazard[- ]free\b|\bfree (?:of|from) (?:\w+ )?hazards?\b"
                              r"|\bclear of (?:all |any )?(?:\w+ )?hazards?\b|\bno (?:environmental )?hazards?\b|\bflood[- ]free\b"),
    ("will be sold", r"\bwill be (?:sold|auctioned|conveyed)\b|\b(?:is|are) (?:going to be )?sold on\b|\bfor sale on\b"),
    ("the lot is vacant", r"\bthe (?:lot|parcel|property|site|land) (?:is|appears to be|seems to be|looks) (?:currently |now |actually |likely |probably |clearly )?(?:an? )?(?:vacant|empty|unimproved|cleared)\b"),
    ("feasibility claim", r"\benough (?:land|area|room|space|lot area)\b|\b(?:can|could) (?:be )?(?:built|build|support|accommodate) (?:on|two|a|an|one|\d)"),
    ("was demolished", r"\b(?:was|were|has been|have been|had been) demolished\b|\bbuilding (?:is )?gone\b"),
    ("guarantee", r"\bguarantee[sd]?\b"),
    ("clear title", r"\bclear title\b|\btitle is clear\b|\bmarketable title\b"),
    ("acquisition recommendation", r"\b(?:we |i )?recommend(?:s|ed)? (?:for )?(?:acquisition|acquiring|purchas\w+|buying)\b"
                                   r"|\bshould (?:be )?(?:buy|acquire|purchase|bought|acquired|purchased)\b|\bgood investment\b"
                                   r"|\b(?:strong|good|ideal|great|prime|top|excellent) (?:candidate|opportunity|pick|choice|prospect)\b"),
    ("approval", r"\b(?:is|are|will be) approved\b|\bapproval is (?:assured|likely|guaranteed)\b"),
    ("no checks needed", r"\bno (?:further )?(?:review|checks?|verification) (?:is |are )?(?:needed|required)\b"),
)
AREA_CONFLICT_FORBIDDEN: tuple[tuple[str, str], ...] = (
    ("conforming", r"\b(?:non-?)?conform(?:s|ing)\b"),
    ("substandard", r"\bsubstandard\b|\bundersized\b|\bnon-?compliant\b"),
    ("meets the minimum", r"\b(?:meets|exceeds|satisfies|clears|passes|fails|misses|is below|falls below|falls short of|is under|is over|is above) the (?:[\w,.-]+ ){0,3}minimum\b"),
)
CONDITION_CONFLICT_FORBIDDEN: tuple[tuple[str, str], ...] = (
    ("no structure", r"\bno (?:building|structure|house)\b|\b(?:building|structure|house) (?:still )?(?:stands|exists|is present|remains)\b"),
    ("condemnation resolved", r"\bcondemnation (?:is|was|has been) (?:resolved|closed|lifted|moot)\b"),
    ("is vacant", r"\b(?:is|remains) (?:currently |still |actually )?vacant\b(?!\s+land\b)"),
    ("condition asserted", r"\b(?:is|are|appears to be|seems to be|looks) (?:likely |probably |now |currently |already )?(?:gone|empty|cleared|razed|removed|occupied)\b|\bempty lot\b"),
)


def _has_conflict(r: ScreeningResult, kind: str, levels: tuple[ConflictLevel, ...]) -> bool:
    return any(c.kind == kind and c.level in levels for c in r.conflicts)


def rule_forbidden_words(i: int, claim: Claim, ctx: CheckContext) -> list[Violation]:
    r = ctx.result
    lists = list(ALWAYS_FORBIDDEN)
    if _has_conflict(r, "lot_area", (ConflictLevel.CRITICAL, ConflictLevel.MATERIAL)):
        lists += AREA_CONFLICT_FORBIDDEN
    if _has_conflict(r, "current_condition", tuple(ConflictLevel)):
        lists += CONDITION_CONFLICT_FORBIDDEN
    out: list[Violation] = []
    for label, pat in lists:
        m = re.search(pat, claim.text, re.I)
        if m:
            out += _v(i, FORBIDDEN_WORDS, f"forbidden decision language ({label}): {m.group(0)!r}", claim)
    return out


# --------------------------------------------------------------------------
# NO_SOURCE_SELECTION
# --------------------------------------------------------------------------

_SUBJ = (r"(?:gis|polygon|assessment|assessor'?s?|assessed|county|deed|records?|figure|number|measurement|"
         r"value|area|source|data|condemn\w*|case|pli|survey|treasury|wprdc|one)")
_EVAL = (r"(?:correct|right|accurate|wrong|incorrect|inaccurate|outdated|out[- ]of[- ]date|stale|obsolete|"
         r"erroneous|mistaken|a mistake|an error|in error|a typo|reliable|unreliable|authoritative|"
         r"trustworthy|flawed|superseded|invalid|the true|the real|the actual|the correct|the right|old|dated|"
         r"an? (?:old|outdated|stale|wrong|bad) (?:number|figure|value|record|measurement)|"
         r"(?:more|most|less|least) (?:accurate|reliable|current|recent|authoritative|trustworthy|precise|credible))")
SOURCE_SELECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b" + _SUBJ + r"\b[\w\s,'()-]{0,40}?\b(?:is|are|was|were|seems?|appears?|looks?|must be|should be|"
               r"is likely|is probably|remains?|looks? like|seems? like)\s+(?:to be\s+)?(?:(?:clearly|likely|probably|simply|actually|obviously|"
               r"definitely|also|just|still|the)\s+)*(?:not\s+)?" + _EVAL + r"\b", re.I),
    re.compile(r"\b(?:true|actual|real|correct|right|accurate|official)\s+(?:lot\s+)?(?:area|size|figure|value|"
               r"measurement|number|lot size|site condition|condition)\s+(?:is|was|=|of|:)\s+(?:about\s+|approximately\s+)?"
               r"(?:\$?\d|the\s+(?:county|gis|assessment|deed|polygon)|county|gis|assessment|vacant|occupied)", re.I),
    re.compile(r"\bthe (?:true|actual|real|correct) (?:lot )?(?:area|size)\b", re.I),
    re.compile(r"\bactually\s+(?:is\s+|was\s+|about\s+)?\$?\d|\breally\s+(?:is\s+)?\$?\d|\bin (?:fact|reality)\b", re.I),
    re.compile(r"\b(?:use|using|rely(?:ing)? on|trust(?:ing)?|prefer(?:ring)?|go(?:ing)? with|adopt(?:ing)?|"
               r"believ(?:e|ing)|favou?r(?:ing)?|accept(?:ing)?|take|taking)\s+(?:the\s+)?(?:(?:county\s+)?gis|polygon|"
               r"assessment|assessor\w*|assessed|deed|condemn\w*|pli|treasury|larger|smaller|higher|lower|newer|"
               r"older|more recent|\d{1,3},\d{3}|\d{4,})\b", re.I),
    re.compile(r"\b(?:ignore|ignoring|disregard\w*|discount\w*|dismiss\w*|set aside|overrides?|overriding|"
               r"supersed\w+|trumps?|outweighs?)\b", re.I),
    re.compile(r"\b(?:resolv(?:es|ed|ing)|settles?|settled|reconcil(?:es|ed|ing))\s+(?:the\s+)?(?:[\w-]+\s+)?"
               r"(?:conflict|discrepancy|disagreement|gap|question)", re.I),
    re.compile(r"\b(?:clerical|data[- ]entry|typographical|recording)\s+error\b|\btypo\b", re.I),
    re.compile(r"\bso the (?:lot|parcel) (?:conforms|meets|qualifies|is conforming|complies)\b", re.I),
    re.compile(r"\b(?:is|was|are) (?:likely|probably|most likely|almost certainly) (?:vacant|demolished|occupied|"
               r"gone|still standing|stale|closed|correct|wrong|right)\b", re.I),
    re.compile(r"\b(?:gis|assessment|county|deed|survey)\s+(?:is|was)\s+right\b|\b(?:gis|assessment)\s+wins\b", re.I),
    re.compile(r"\b(?:understates?|overstates?|under-?reports?|over-?reports?|underestimates?|overestimates?|"
               r"misstates?|misreports?|mismeasures?|(?:better|more (?:closely|accurately)) (?:reflects?|captures?|represents?|matches?)|"
               r"reflects? the (?:actual|true|real) )", re.I),
    re.compile(r"\bgoing by the\b|\bbased on the (?:county )?(?:gis|assessment|polygon|deed|larger|smaller)\b|"
               r"\bplan around\b|\btreat (?:the )?(?:lot|parcel|site|area|it) as\b|\bwork(?:ing)? from the (?:gis|assessment|larger|smaller)\b", re.I),
    re.compile(r"\b(?:discrepancy|gap|difference|conflict|disagreement|mismatch)\s+(?:\w+\s+){0,2}(?:reflects?|is due to|"
               r"is explained by|comes from|stems from|results from|is because|arises from|is caused by)\b|"
               r"\b(?:gis|assessment|assessor\w*|county|polygon|record)\s+(?:\w+\s+)?(?:missed|omitted|overlooked|failed to)\b", re.I),
    re.compile(r"\b(?:gis|assessment|assessor\w*|polygon|county|deed|condemn\w*)\b[\w\s]{0,25}?\b(?:governs|controls|"
               r"prevails|wins|should govern|should control|should prevail|takes precedence)\b", re.I),
)
SELECTION_GUARD = re.compile(
    r"\b(?:neither|whether|nor|which (?:source|one|area|value|record|figure)s?|not known|unknown|"
    r"cannot (?:determine|tell|say)|can't (?:determine|tell|say)|no (?:source|record) is|"
    r"(?:does|do|did|will) not (?:select|choose|pick|use|prefer|treat|trust|decide|assume|resolve)|"
    r"without (?:selecting|choosing|treating|deciding|assuming)|(?:is|are) not treated)\b",
    re.I,
)


SUFFIX_GUARD = re.compile(
    r"\b(?:requires?|needs?|is unknown|is not known|cannot be (?:determined|established)|is unverified|"
    r"remains? unverified|is not established|until)\b",
    re.I,
)
# Patterns whose match may be followed by uncertainty framing ("the true area
# is unknown until survey", "resolving the conflict requires a deed review").
SUFFIX_GUARDED = frozenset({1, 2, 6})


def selects_source(text: str) -> str | None:
    """The matched phrase if ``text`` picks a winning source, else None."""
    for _, sentence in _sentences(text):
        for k, pat in enumerate(SOURCE_SELECTION_PATTERNS):
            for m in pat.finditer(sentence):
                if SELECTION_GUARD.search(sentence[:m.start()]):
                    continue  # "neither source is known to be correct", "whether the GIS area is right"
                if k in SUFFIX_GUARDED and SUFFIX_GUARD.search(sentence[m.end():m.end() + 40]):
                    continue
                return m.group(0)
    return None


SOURCE_NAME_RE = re.compile(r"\b(?:assessment|assessor\w*|assessed|gis|polygon|county|record(?:s|ed)?|deed|"
                            r"source|survey|treasury|wprdc|advertisement|pli)\b", re.I)


def _disputed_value_unqualified(claim: Claim, ctx: CheckContext) -> bool:
    """A lot-area value from a conflict stated as *the* lot area, with no source named."""
    if SOURCE_NAME_RE.search(claim.text):
        return False
    for c in ctx.result.conflicts:
        if c.kind != "lot_area":
            continue
        values = [v for fid in c.fact_ids if (f := ctx.universe.get(fid)) is not None and f.unit == "sf"
                  and f.id.split(":")[0] != "RULE" and (v := _numeric(f.value)) is not None]
        for tok in tokenize(claim.text):
            if tok.kind in ("area", "bare") and any(num_matches(n, v, approx=tok.approx) for n in tok.nums for v in values):
                return True
    return False


def rule_no_source_selection(i: int, claim: Claim, ctx: CheckContext) -> list[Violation]:
    if claim.claim_type == "conflict_summary" and claim.author == "engine":
        return []  # verbatim engine text; ENGINE_AUTHENTIC and completeness verify it
    hit = selects_source(claim.text)
    if hit:
        return _v(i, NO_SOURCE_SELECTION, f"picks a winning source or resolves a conflict: {hit!r}", claim)
    if _disputed_value_unqualified(claim, ctx):
        return _v(i, NO_SOURCE_SELECTION, "states a disputed lot-area value without naming its source "
                  "(implicitly selects that source)", claim)
    return []


# --------------------------------------------------------------------------
# LLM_CANNOT_AUTHOR / ENGINE_AUTHENTIC
# --------------------------------------------------------------------------


def rule_llm_cannot_author(i: int, claim: Claim, ctx: CheckContext) -> list[Violation]:
    if claim.claim_type == "conflict_summary" and claim.author != "engine":
        return _v(i, LLM_CANNOT_AUTHOR, "conflict_summary claims are reserved for the engine", claim)
    return []


def rule_engine_authentic(i: int, claim: Claim, ctx: CheckContext) -> list[Violation]:
    if claim.author == "engine" and claim.text not in ctx.engine_texts:
        return _v(i, ENGINE_AUTHENTIC, "claim is labeled engine-authored but its text is not an engine output", claim)
    return []


# --------------------------------------------------------------------------
# QUALIFIERS
# --------------------------------------------------------------------------

QUALIFIER_RE = re.compile(
    r"\b(?:illustrative|approximate(?:ly)?|approx\.?|about|roughly|estimated|if corner|heuristic|possible|"
    r"possibly|proximity|not (?:a )?survey(?:ed)?)\b|~",
    re.I,
)
PENDING_LAW_RE = re.compile(r"\bBill\s+\d{4}-\d+|\bpending (?:law|legislation|bill)\b", re.I)


def rule_qualifiers(i: int, claim: Claim, ctx: CheckContext) -> list[Violation]:
    cited = ctx.cited(claim)
    approx = [f for f in cited if f.evidence_class == "approximate"]
    out: list[Violation] = []
    if approx and not QUALIFIER_RE.search(claim.text):
        out += _v(i, QUALIFIERS, "cites approximate evidence (" + ", ".join(f.field for f in approx)
                  + ") without a qualifier such as 'illustrative', 'approximate', 'about' or 'if corner'", claim)
    corner = [s for s in ctx.result.scenarios if s.label == "corner"]
    if corner:
        env_cited = any(f.field.startswith("envelope_") or f.field == SETBACK_SCREEN for f in cited)
        mentions_width = re.search(r"\b(?:width|wide|envelope)\b", claim.text, re.I)
        if (env_cited or mentions_width) and not re.search(r"\bcorner\b", claim.text, re.I):
            out += _v(i, QUALIFIERS, "corner status is unverified: an envelope/width statement must give the "
                      "range or the 'if corner' scenario, not a single envelope number", claim)
    if PENDING_LAW_QUALIFIER_ENABLED and PENDING_LAW_RE.search(claim.text) \
            and not re.search(r"\bpending\b.*\bnot (?:enacted|in effect)\b", claim.text, re.I):
        out += _v(i, QUALIFIERS, "pending-law statements must say the bill is pending and not enacted", claim)
    return out


# --------------------------------------------------------------------------
# UNTRUSTED_TEXT
# --------------------------------------------------------------------------

INJECTION_RE = re.compile(
    r"\bignore (?:all |the |any |previous |prior |above |these |those )*(?:rules|instructions|prompts?|"
    r"constraints|policy|policies|checks?|checker)\b|\bmark (?:this|the) (?:parcel|lot|property)\b|"
    r"\b(?:system|developer) prompt\b|\byou (?:must|should) now\b|\bnew instructions?\b|"
    r"\bdisregard (?:all|the|previous|prior|any)\b|\bpretend (?:that|to)\b|\bact as\b",
    re.I,
)
UNTRUSTED_LABEL_RE = re.compile(r"\buntrusted\b", re.I)


def rule_untrusted_text(i: int, claim: Claim, ctx: CheckContext) -> list[Violation]:
    outside, quotes = split_quotes(claim.text)
    out: list[Violation] = []
    m = INJECTION_RE.search(outside)
    if m:
        out += _v(i, UNTRUSTED_TEXT, f"instruction-like text outside a labeled quote: {m.group(0)!r}", claim)
    labeled = bool(UNTRUSTED_LABEL_RE.search(outside))
    cited_ids = set(claim.fact_ids) if isinstance(claim.fact_ids, (tuple, list)) else set()
    for f in ctx.untrusted:
        src = " ".join(map(str, f.value)) if isinstance(f.value, (tuple, list)) else str(f.value or "")
        grams = ngrams(src, 4)
        if grams & ngrams(outside, 4):
            out += _v(i, UNTRUSTED_TEXT, f"reproduces untrusted source text ({f.id}) outside quotes", claim)
        quoted = any(grams & ngrams(q, 4) for q in quotes)
        if (quoted or f.id in cited_ids) and not labeled:
            out += _v(i, UNTRUSTED_TEXT, f"uses untrusted source text ({f.id}) without labeling it untrusted", claim)
        if f.id in cited_ids and claim.claim_type not in ("fact", "caveat"):
            out += _v(i, UNTRUSTED_TEXT, f"untrusted text ({f.id}) cannot support a {claim.claim_type} claim", claim)
    return out


# --------------------------------------------------------------------------
# CONFLICT_COMPLETENESS (memo level)
# --------------------------------------------------------------------------

CONDITION_WORDS = re.compile(r"vacan|condemn|demoli|dead-end|site condition|current condition|current-condition", re.I)
SALE_WORDS = re.compile(r"\bupset\b|tax due|starting bid|sale universe", re.I)
UNCERTAINTY_RE = re.compile(r"\bdisagree|\bunverified\b|\brequires\b|\bnot evaluated\b|\bconfirmation\b", re.I)


def touches_conflict(claim: Claim, conflict, ctx: CheckContext) -> bool:
    ids = set(claim.fact_ids) if isinstance(claim.fact_ids, (tuple, list)) else set()
    group = set(conflict.fact_ids) | {f"{ctx.result.pin}:conflict_{conflict.kind}:engine"}
    if ids & group:
        return True
    if conflict.kind == "current_condition":
        return bool(CONDITION_WORDS.search(claim.text))
    if conflict.kind == "sale_universe":
        return bool(SALE_WORDS.search(claim.text))
    if conflict.kind == "lot_area":
        values = [v for fid in conflict.fact_ids
                  if (f := ctx.universe.get(fid)) is not None and (v := _numeric(f.value)) is not None and abs(v) >= 10]
        for tok in tokenize(claim.text):
            if tok.kind in ("area", "bare", "percent"):
                if any(num_matches(n, v) or num_matches(n, -v) for n in tok.nums for v in values):
                    return True
    return False


def rule_conflict_completeness(claims: Sequence[Claim], ctx: CheckContext) -> list[Violation]:
    out: list[Violation] = []
    for c in ctx.result.conflicts:
        touching = [i for i, cl in enumerate(claims)
                    if cl.claim_type != "conflict_summary" and touches_conflict(cl, c, ctx)]
        if not touching:
            continue
        ok = any(
            cl.claim_type == "conflict_summary" and cl.author == "engine" and cl.text == c.summary
            and set(c.fact_ids) <= set(cl.fact_ids) and UNCERTAINTY_RE.search(cl.text)
            for cl in claims
        )
        if not ok:
            out += _v(None, CONFLICT_COMPLETENESS,
                      f"claim {touching[0]} touches the {c.level.value} {c.kind} conflict but the memo lacks the "
                      "engine-authored conflict summary citing every fact in that group")
    return out


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

CLAIM_RULES: tuple[tuple[str, ClaimRule], ...] = (
    (CITE_EXISTS, rule_cite_exists),
    (NUMBERS, rule_numbers),
    (CODE_SECTIONS, rule_code_sections),
    (STATUS_AGREES, rule_status_agrees),
    (FORBIDDEN_WORDS, rule_forbidden_words),
    (NO_SOURCE_SELECTION, rule_no_source_selection),
    (LLM_CANNOT_AUTHOR, rule_llm_cannot_author),
    (ENGINE_AUTHENTIC, rule_engine_authentic),
    (QUALIFIERS, rule_qualifiers),
    (UNTRUSTED_TEXT, rule_untrusted_text),
)
MEMO_RULES: tuple[tuple[str, MemoRule], ...] = ((CONFLICT_COMPLETENESS, rule_conflict_completeness),)


def check(
    claims: Iterable[Claim],
    result: ScreeningResult,
    *,
    allowlist: SectionAllowlist = DEFAULT_ALLOWLIST,
    catalog: Iterable[Fact] = (),
    skip: Iterable[str] = (),
) -> CheckReport:
    """Validate every claim against the engine result. ``report.ok`` only if zero violations.

    ``catalog``: extra facts (e.g. every district's RULE facts) so invalid
    citations are explained precisely; they never become citable for another
    parcel or district. ``skip`` exists for rule-isolation tests only.
    """
    claims = tuple(claims)
    ctx = CheckContext(result=result, allowlist=allowlist, catalog=tuple(catalog))
    skipped = set(skip)
    violations: list[Violation] = []
    for i, claim in enumerate(claims):
        shape = rule_well_formed(i, claim, ctx)
        if shape:
            violations += shape
            continue
        for rule_id, fn in CLAIM_RULES:
            if rule_id not in skipped:
                violations += fn(i, claim, ctx)
    for rule_id, fn in MEMO_RULES:
        if rule_id not in skipped:
            violations += fn([c for c in claims if isinstance(c.text, str)], ctx)
    return CheckReport(tuple(violations), len(claims), claims)


def run_rule(rule_id: str, claim: Claim, result: ScreeningResult, **kw) -> list[Violation]:
    """Run one claim-level rule in isolation (tests and the integrity panel)."""
    ctx = CheckContext(result=result, allowlist=kw.get("allowlist", DEFAULT_ALLOWLIST),
                       catalog=tuple(kw.get("catalog", ())))
    fn = dict(CLAIM_RULES)[rule_id]
    return fn(0, claim, ctx)
