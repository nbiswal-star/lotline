"""Sentence-level verification for any text an AI feature might show about a parcel.

Every sentence must carry citations (engine fact ids and/or code-excerpt ids) and must pass:

* the memo claim checker's rules, run on the sentence as a claim (CITE_EXISTS, NUMBERS,
  CODE_SECTIONS, STATUS_AGREES, FORBIDDEN_WORDS, NO_SOURCE_SELECTION, QUALIFIERS,
  UNTRUSTED_TEXT, ENGINE_AUTHENTIC for engine-labelled text) plus the memo-level
  CONFLICT_COMPLETENESS rule; and
* three rules that close the gap the adversarial experiment found in the memo checker, where
  fluent prose such as "Two-unit housing is permitted in R1D-L." passed:
  - PERMISSION_AGREES: a sentence that says single-unit, two-unit or housing use is permitted,
    allowed, by right or prohibited must match the district rule facts (A = Administrator
    Exception, S = Special Exception, C = conditional use).
  - UNSUPPORTED_TOPIC: utilities, title/ownership, access and market/price/value are outside
    the screening evidence. A sentence on one of them must say it is not established / not
    evaluated, or cite the engine fact or next check that covers it, and may never assert
    a condition ("sewer is connected", "the owner agreed").
  - OUTCOME_OVERREACH: no promise of approval, permits, feasibility or "no problems".

Verbatim code quotes are verified separately (exact substring of a curated excerpt); the rules
here run on everything outside the quote. Nothing here calls a model or changes a sentence.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from lotline.memo import checker as ck
from lotline.memo.allowlist import DEFAULT_ALLOWLIST, SectionAllowlist
from lotline.memo.claims import Claim
from lotline.models import Fact, ScreeningResult

REPO_ROOT = Path(__file__).resolve().parents[2]
EXCERPTS_PATH = REPO_ROOT / "data" / "code_excerpts.json"

# Rule ids added by this module.
CITATION_REQUIRED = "CITATION_REQUIRED"
CODE_REF_EXISTS = "CODE_REF_EXISTS"
QUOTE_VERBATIM = "QUOTE_VERBATIM"
PERMISSION_AGREES = "PERMISSION_AGREES"
UNSUPPORTED_TOPIC = "UNSUPPORTED_TOPIC"
OUTCOME_OVERREACH = "OUTCOME_OVERREACH"
NEW_RULE_IDS: tuple[str, ...] = (PERMISSION_AGREES, UNSUPPORTED_TOPIC, OUTCOME_OVERREACH)

# Memo checker rules applied to every sentence (LLM_CANNOT_AUTHOR is implied: sentences are never
# conflict summaries unless they are the engine's own).
CHECKER_RULES: tuple[str, ...] = (
    ck.CITE_EXISTS, ck.NUMBERS, ck.CODE_SECTIONS, ck.STATUS_AGREES, ck.FORBIDDEN_WORDS,
    ck.NO_SOURCE_SELECTION, ck.LLM_CANNOT_AUTHOR, ck.ENGINE_AUTHENTIC, ck.QUALIFIERS, ck.UNTRUSTED_TEXT,
)


# --------------------------------------------------------------------------
# Code excerpts
# --------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _excerpts_cached(path: str) -> tuple[dict, ...]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return tuple(data["excerpts"])


def load_excerpts(path: Path | None = None) -> dict[str, dict]:
    """Curated code excerpts keyed by id (``data/code_excerpts.json``)."""
    return {e["id"]: e for e in _excerpts_cached(str(path or EXCERPTS_PATH))}


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def quote_in_excerpt(quote: str, excerpt: dict) -> bool:
    """``quote`` is an exact (whitespace-insensitive) substring of one verbatim piece of the excerpt."""
    q = _squash(quote)
    if not q or "[...]" in q:
        return False
    return any(q in _squash(piece) for piece in excerpt["text"].split(" [...] "))


# --------------------------------------------------------------------------
# Items and context
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Item:
    """One sentence to verify. ``check_text`` is the text outside any verbatim quote."""

    text: str
    fact_ids: tuple[str, ...]
    code_refs: tuple[str, ...] = ()
    claim_type: str = "fact"
    author: str = "llm"
    quote: str | None = None  # verbatim code quote carried by this sentence (checked separately)
    check_text: str | None = None

    @property
    def outside(self) -> str:
        return self.check_text if self.check_text is not None else self.text


@dataclass
class _Ctx(ck.CheckContext):
    excerpts: dict[str, dict] = field(default_factory=dict)
    code_refs: dict[int, tuple[str, ...]] = field(default_factory=dict)
    current: int = -1

    def cited(self, claim: Claim) -> list[Fact]:
        out = super().cited(claim)
        for ref in self.code_refs.get(self.current, ()):
            e = self.excerpts.get(ref)
            if e is not None:
                # A cited excerpt supports numbers and dates written in its label, title or text.
                out.append(Fact(id=f"EXCERPT:{ref}", pin=self.result.pin, field="code_excerpt",
                                value=f"{e.get('label', '')} {e.get('title', '')} {e['text']}", unit=None,
                                source="code_excerpts", as_of=str(e.get("as_of", "")), evidence_class="rule"))
        return out


# --------------------------------------------------------------------------
# PERMISSION_AGREES
# --------------------------------------------------------------------------

TWO_UNIT_RE = re.compile(r"\btwo[- ](?:unit|family)\b|\bduplex(?:es)?\b|\btwo dwelling units\b|\b2[- ]unit\b", re.I)
SINGLE_UNIT_RE = re.compile(r"\bsingle[- ](?:unit|family)\b|\bone[- ](?:unit|family)\b|\bdetached (?:house|home|dwelling)s?\b",
                            re.I)
HOUSING_RE = re.compile(r"\bhousing\b|\bresidential (?:use|development|construction)s?\b|\bhouses?\b|\bhomes?\b|\bdwellings?\b"
                        r"|\bresidences?\b", re.I)
NEG_PERMIT_RE = re.compile(r"\b(?:not|never|isn't|aren't|cannot|can't)\s+(?:be\s+)?(?:\w+\s+)?(?:permitted|allowed)\b"
                           r"|\bneither\b[^.;]*\b(?:permitted|allowed)\b|\bprohibited\b|\bforbidden\b|\bbarred\b|\bnot a permitted\b|\bdisallowed\b", re.I)
POS_PERMIT_RE = re.compile(r"\bpermitted\b|\ballowed\b|\bby[- ]right\b|\bpermissible\b|\blegal to build\b", re.I)
LETTER_WORDS = {
    "A": re.compile(r"\badministrator exception\b", re.I),
    "S": re.compile(r"\bspecial exception\b", re.I),
    "C": re.compile(r"\bconditional use\b", re.I),
}
BY_RIGHT_RE = re.compile(r"\bby[- ]right\b|\bwithout (?:any )?(?:review|approval|hearing)\b|\bas of right\b", re.I)
CLAUSE_SPLIT_RE = re.compile(r";|\.\s|,\s(?=(?:but|while|whereas|and)\b)|\bbut\b|\bwhile\b|\bwhereas\b", re.I)


def _district_rules(ctx: _Ctx) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for f in ctx.universe.values():
        if f.id.startswith("RULE:") and f.district and f.field in ("single_unit_permission", "two_unit_permission"):
            out.setdefault(f.district, {})[f.field] = str(f.value).strip().upper()
    return out


def _named_districts(text: str, known: Iterable[str]) -> list[str]:
    hits = []
    for d in sorted(known, key=len, reverse=True):
        if re.search(r"(?<![A-Za-z0-9-])" + re.escape(d) + r"(?![A-Za-z0-9-])", text):
            hits.append(d)
    return hits


def _all_known_districts() -> frozenset[str]:
    try:
        import csv

        with open(REPO_ROOT / "data" / "district_rules.csv", encoding="utf-8") as fh:
            return frozenset(row["district"] for row in csv.DictReader(fh))
    except OSError:
        return frozenset()


def _permission_problem(code: str, asserted: str, clause: str) -> str | None:
    """None if ``asserted`` ('permitted' | 'prohibited') is a correct reading of ``code``."""
    code = code.upper()
    if asserted == "prohibited":
        return None if code == "PROHIBITED" else f"rule is {code!r}, not prohibited"
    if code == "PROHIBITED":
        return "rule is prohibited"
    if code == "P":
        return None
    if BY_RIGHT_RE.search(clause):
        return f"rule is {code!r} (not by right)"
    word = LETTER_WORDS.get(code)
    if word is not None and not word.search(clause):
        label = {"A": "Administrator Exception", "S": "Special Exception", "C": "conditional use"}[code]
        return f"rule is {code!r}; a permission statement must name the {label}"
    return None


def rule_permission_agrees(i: int, item: Item, ctx: _Ctx) -> list[str]:
    text = item.outside
    if not (TWO_UNIT_RE.search(text) or SINGLE_UNIT_RE.search(text) or HOUSING_RE.search(text)):
        return []
    rules = _district_rules(ctx)
    known = set(rules) | _all_known_districts()
    cited_districts = {fid.split(":")[1] for fid in item.fact_ids if fid.startswith("RULE:")}
    out: list[str] = []
    for clause in CLAUSE_SPLIT_RE.split(text):
        if not clause or not clause.strip():
            continue
        neg = NEG_PERMIT_RE.search(clause)
        pos = POS_PERMIT_RE.search(clause)
        if not (neg or pos):
            continue
        asserted = "prohibited" if neg else "permitted"
        subjects = []
        if TWO_UNIT_RE.search(clause):
            subjects.append("two_unit_permission")
        if SINGLE_UNIT_RE.search(clause):
            subjects.append("single_unit_permission")
        generic = not subjects and bool(HOUSING_RE.search(clause))
        if not subjects and not generic:
            continue
        districts = _named_districts(clause, known) or sorted(cited_districts) or ([ctx.district] if ctx.district else [])
        for d in districts:
            if d != ctx.district:
                out.append(f"{PERMISSION_AGREES}: sentence {i + 1}: permission statement about district {d}, "
                           f"but the active parcel's district is {ctx.district}")
                continue
            rule = rules.get(d)
            if not rule:
                out.append(f"{PERMISSION_AGREES}: sentence {i + 1}: no encoded use rule for {d}; permission "
                           "cannot be stated")
                continue
            if generic:
                codes = [rule.get("single_unit_permission", ""), rule.get("two_unit_permission", "")]
                if asserted == "prohibited":
                    problems = [] if all(c == "PROHIBITED" for c in codes) else ["a housing use is not prohibited"]
                else:
                    ok = [c for c in codes if _permission_problem(c, "permitted", clause) is None]
                    problems = [] if ok else ["no housing use matches that permission"]
            else:
                problems = [p for s in subjects if (p := _permission_problem(rule.get(s, ""), asserted, clause))]
            for p in problems:
                out.append(f"{PERMISSION_AGREES}: sentence {i + 1}: says {asserted} in {d} but {p}")
    return out


# --------------------------------------------------------------------------
# UNSUPPORTED_TOPIC
# --------------------------------------------------------------------------

TOPICS: dict[str, tuple[re.Pattern[str], tuple[str, ...], tuple[str, ...]]] = {
    # topic: (pattern, cited fact fields that cover it, words an engine next check/barrier must contain)
    "utilities": (re.compile(r"\butilit(?:y|ies)\b|\bsewers?\b|\bsewage\b|\bpublic water\b|\bwater (?:and sewer|service|lines?|mains?|"
                             r"laterals?|connection|tap)\b|\blaterals?\b|\bcapacity\b|\bgas (?:line|service)\b|\belectric(?:al|ity)? "
                             r"(?:service|hookup)\b|\bhook[- ]?ups?\b", re.I), (), ("utilit",)),
    "title": (re.compile(r"\btitle\b|\bliens?\b|\bmortgages?\b|\bjudgments?\b|\bowner(?:s|ship)?\b(?!\s*:)|\bencumbranc\w+\b"
                         r"|\btransfer(?:s|red)? (?:the )?(?:lot|parcel|property|title|deed)\b|\bagreed to (?:sell|transfer|convey)\b",
                         re.I), (), ("title", "Treasurer Sale terms", "deed")),
    "access": (re.compile(r"\blegal access\b|\baccess(?:ible)? (?:from|to|via|by)\b|\bhas access\b|\bright[- ]of[- ]way\b"
                          r"|\bfrontage\b|\bdriveways?\b|\bcurb cuts?\b", re.I),
               ("streets_within_30ft", "possible_corner"), ("access", "frontage")),
    "market": (re.compile(r"\bmarket\b|\bprices?\b|\b(?:market|property|resale|fair|home|house|land|lot|true|real|future) "
                          r"values?\b|\bvalu(?:ed|ation)\b|\bapprais\w+\b|\bresale\b|\bprofit\w*\b|\breturns?\b|\brents?\b"
                          r"|\brental income\b|\bcomparables?\b|\bcomps\b|\bworth\b|\bcheap\b|\bbargain\b|\bundervalued\b", re.I),
               ("upset", "upset_price", "assessed_land_value", "fm_land", "fm_bldg", "upset_to_assessed_land",
                "total_tax_due", "demo_cost_due"), ("market", "not market value", "appraisal")),
}
NOT_ESTABLISHED_RE = re.compile(
    r"\bnot (?:\w+ ){0,2}(?:established|evaluated|verified|known|determined|assessed|checked|cleared|divested|"
    r"reviewed|confirmed|screened|included|covered)\b|\bunverified\b|\bunknown\b|\bproximity only\b|\bindicator only\b"
    r"|\bnot (?:legal frontage|market value|an acquisition recommendation)\b|\bdoes not (?:evaluate|establish|check|"
    r"assess|verify|estimate|cover|know)\b|\bno (?:\w+ )?(?:data|evidence|record)s? (?:on|about|for)\b|\boutside (?:the |this )?"
    r"(?:screen|packet|snapshot|evidence)\b|\bnot (?:[\w-]+,? )+(?:or [\w-]+ )?advice\b",
    re.I,
)
CONDITION_ASSERT_RE = re.compile(
    r"\b(?:is|are|was|were|has been|have been)\s+(?:already\s+|fully\s+|currently\s+)?(?:connected|available|in place|"
    r"installed|adequate|sufficient|clear|clean|unencumbered|free of|resolved|paid|settled|guaranteed|secured)\b"
    r"|\bha(?:s|ve)\s+(?:capacity|access|clear title|agreed)\b|\bagreed to\b|\bwill (?:sell|appreciate|rent|transfer|convey)\b"
    r"|\bis worth\b|\bworth (?:about |roughly |around )?\$|\bmarket value (?:is|of)\b|\bwill (?:be )?(?:worth|valued)\b",
    re.I,
)


def _covering_fact(item: Item, ctx: _Ctx, fields: tuple[str, ...], words: tuple[str, ...]) -> bool:
    for fid in item.fact_ids:
        f = ctx.universe.get(fid)
        if f is None or f.pin != ctx.result.pin:
            continue
        if f.field in fields:
            return True
        if (f.field.startswith(("next_check_", "barrier_", "warning_"))) and any(
                w.lower() in str(f.value).lower() for w in words):
            return True
    return False


def rule_unsupported_topic(i: int, item: Item, ctx: _Ctx) -> list[str]:
    text = item.outside
    out: list[str] = []
    for topic, (pat, fields, words) in TOPICS.items():
        m = pat.search(text)
        if not m:
            continue
        negated = bool(NOT_ESTABLISHED_RE.search(text))
        asserted = CONDITION_ASSERT_RE.search(text)
        if asserted and not negated:
            out.append(f"{UNSUPPORTED_TOPIC}: sentence {i + 1}: asserts a {topic} condition ({asserted.group(0)!r}) "
                       "that the screening evidence does not establish")
            continue
        if not negated and not _covering_fact(item, ctx, fields, words):
            out.append(f"{UNSUPPORTED_TOPIC}: sentence {i + 1}: mentions {topic} ({m.group(0)!r}) without saying it is "
                       "not established/not evaluated or citing the engine next check that covers it")
    return out


# --------------------------------------------------------------------------
# OUTCOME_OVERREACH
# --------------------------------------------------------------------------

OVERREACH_RE = re.compile(
    r"\bwill (?:\w+ )?(?:be )?(?:approved|granted|issued|permitted|allowed|accepted)\b"
    r"|\b(?:approval|approvals|permits?|variances?|rezoning|exceptions?|review)\s+(?:is|are|will be|would be|should be)\s+"
    r"(?:\w+ )?(?:likely|assured|certain|guaranteed|expected|easy|straightforward|routine|granted|issued|automatic|a formality)\b"
    r"|\b(?:should|would|will|can)\s+(?:easily\s+|likely\s+|certainly\s+|definitely\s+)?(?:get|obtain|receive|win|secure)\s+"
    r"(?:an?\s+|the\s+|your\s+)?(?:approval|permits?|variance|exception|rezoning|certificate)\b"
    r"|\b(?:must|shall|has to|have to|is required to|is obligated to)\s+approve\b"
    r"|\bfeasib(?:le|ility)\b|\bviable\b|\bdevelopable\b|\bcan (?:definitely|certainly|easily|safely) (?:build|develop)\b"
    r"|\bno (?:real )?(?:problems?|issues?|obstacles?|barriers?|risks?|concerns?)\b|\bnothing (?:stands|standing) in the way\b"
    r"|\bready (?:for|to) (?:development|develop|build|construction)\b|\bgood to go\b|\bgreen light\b"
    r"|\bsafe (?:bet|buy|purchase|investment)\b|\blow[- ]risk\b|\brisk[- ]free\b|\bsure thing\b"
    r"|\b(?:you|they|staff|buyers?|bidders?)\s+(?:should|must|can safely)\s+(?:bid|buy|purchase|acquire)\b",
    re.I,
)
OVERREACH_GUARD = re.compile(r"\b(?:not|never|no one|nobody|cannot|can't|does not|do not|doesn't|without)\b[^.;]{0,30}$", re.I)


def rule_outcome_overreach(i: int, item: Item, ctx: _Ctx) -> list[str]:
    text = item.outside
    out = []
    for m in OVERREACH_RE.finditer(text):
        before = text[max(0, m.start() - 40):m.start()]
        word = m.group(0).lower()
        if OVERREACH_GUARD.search(before) and not word.startswith("no "):
            continue  # "LotLine does not say approval is likely", "not a feasibility study"
        out.append(f"{OUTCOME_OVERREACH}: sentence {i + 1}: promises an outcome the engine does not decide "
                   f"({m.group(0)!r})")
        break
    return out


NEW_RULES = (
    (PERMISSION_AGREES, rule_permission_agrees),
    (UNSUPPORTED_TOPIC, rule_unsupported_topic),
    (OUTCOME_OVERREACH, rule_outcome_overreach),
)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def verify(items: Sequence[Item], result: ScreeningResult, *, excerpts: dict[str, dict] | None = None,
           allowlist: SectionAllowlist = DEFAULT_ALLOWLIST, catalog: Iterable[Fact] = (),
           memo_level: bool = True) -> list[str]:
    """All violations for ``items`` (empty list = every sentence verified)."""
    excerpts = load_excerpts() if excerpts is None else excerpts
    ctx = _Ctx(result=result, allowlist=allowlist, catalog=tuple(catalog), excerpts=excerpts,
               code_refs={i: tuple(it.code_refs) for i, it in enumerate(items)})
    rules = dict(ck.CLAIM_RULES)
    out: list[str] = []
    claims: list[Claim] = []
    for i, it in enumerate(items):
        ctx.current = i
        if not isinstance(it.text, str) or not it.text.strip():
            out.append(f"{ck.WELL_FORMED}: sentence {i + 1}: empty sentence")
            continue
        if not it.fact_ids and not it.code_refs and not (it.author == "engine" and it.claim_type == "caveat"):
            out.append(f"{CITATION_REQUIRED}: sentence {i + 1}: cites no fact id or code excerpt")
        for ref in it.code_refs:
            if ref not in excerpts:
                out.append(f"{CODE_REF_EXISTS}: sentence {i + 1}: code excerpt {ref!r} does not exist")
            elif not allowlist.allows(ref):
                out.append(f"{CODE_REF_EXISTS}: sentence {i + 1}: code excerpt {ref!r} is not in allowlist {allowlist.version}")
        if it.quote is not None:
            if not any(r in excerpts and quote_in_excerpt(it.quote, excerpts[r]) for r in it.code_refs):
                out.append(f"{QUOTE_VERBATIM}: sentence {i + 1}: quote is not an exact substring of a cited excerpt")
        claim = Claim(it.outside, tuple(it.fact_ids), it.claim_type, it.author)  # type: ignore[arg-type]
        shape = ck.rule_well_formed(i, claim, ctx)
        if shape:
            out += [f"{v.rule}: sentence {i + 1}: {v.message}" for v in shape]
            continue
        for rule_id in CHECKER_RULES:
            if rule_id == ck.CITE_EXISTS and not it.fact_ids and it.code_refs:
                continue  # cites a code excerpt only; CODE_REF_EXISTS covers it
            if rule_id == ck.ENGINE_AUTHENTIC and it.author != "engine":
                continue
            out += [f"{v.rule}: sentence {i + 1}: {v.message}" for v in rules[rule_id](i, claim, ctx)]
        for _, fn in NEW_RULES:
            out += fn(i, it, ctx)
        claims.append(claim)
    if memo_level:
        out += [f"{v.rule}: {v.message}" for v in ck.rule_conflict_completeness(claims, ctx)]
    return out


def verify_claim(claim: Claim, result: ScreeningResult, **kw) -> list[str]:
    """Verify one memo ``Claim`` as a free-text sentence (evaluation helper)."""
    return verify([Item(claim.text, tuple(claim.fact_ids), (), claim.claim_type, claim.author)], result, **kw)
