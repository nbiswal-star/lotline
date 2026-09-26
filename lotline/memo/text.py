"""Claim-text tokenizer used by the checker.

Tokens are recognized in a fixed order and each match is masked before the
next pass, so one character span is only ever validated once and by the
right rule: PINs, code references, dates, score expressions, then ordinary
quantities (money, percent, area, length, ratio) and finally bare numbers.
There is deliberately no single global numeric comparison.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --------------------------------------------------------------------------
# Token record
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Num:
    value: float
    decimals: int
    text: str


@dataclass(frozen=True)
class Token:
    kind: str  # pin|code|date|total|partial|coverage|component|money|percent|area|length|ratio|bare
    text: str
    start: int
    end: int
    nums: tuple[Num, ...] = ()
    ref: str = ""  # normalized code reference / PIN / ISO date ("YYYY-MM-DD" or "--MM-DD")
    name: str = ""  # component name for kind == "component"
    approx: bool = False  # preceded by about / approximately / roughly / ~


NUMBER = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_NUM_RE = re.compile(NUMBER)


def parse_num(text: str) -> Num:
    clean = text.replace(",", "").replace("−", "-").lstrip("+")
    decimals = len(clean.split(".")[1]) if "." in clean else 0
    return Num(float(clean), decimals, text)


# --------------------------------------------------------------------------
# Patterns (order matters)
# --------------------------------------------------------------------------

PIN_RE = re.compile(r"(?<![0-9A-Za-z])\d{4}[A-Z]\d{5}[0-9A-Z]{4}\d{2}(?![0-9A-Za-z])")
ACT_RE = re.compile(r"\bAct\s+(\d+)\s+of\s+(\d{4})\b(?:\s*(?:§+|Section)\s*(\d+(?:\.\d+)?))?", re.I)
_SEC_BODY = r"\d{1,4}(?:\.\d{1,3}[A-Za-z]?)*(?:\.[A-Z](?:\.\d+[A-Za-z]?)*)?(?:\([0-9a-z]+\))?"
PREFIXED_CODE_RE = re.compile(
    r"(?P<prefix>§+\s*|\bSections?\s+|\bChapters?\s+|\bCh\.\s*|\bCode\s+)(?P<sec>" + _SEC_BODY + r")(?![0-9])",
    re.I,
)
BARE_CODE_RE = re.compile(
    r"(?<![\d.$,])(?P<sec>9\d{2}\.\d{2}(?:\.[A-Z](?:\.\d+[A-Za-z]?)*)?(?:\([0-9a-z]+\))?)(?![\d])"
)
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
ISO_DATE_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
US_DATE_RE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4})(?![\d/])")
NAMED_DATE_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?"
    r"(?:,?\s+(\d{4}))?(?!\d)",
    re.I,
)
_RANGE = r"(\d)(?:\s*(?:to|-|–|—)\s*(\d))?"
PARTIAL_RE = re.compile(r"(?<![\d.,])" + _RANGE + r"\s+(?:of|out of)\s+(\d)\s+known\b", re.I)
TOTAL_RE = re.compile(r"(?<![\d.,/$])" + _RANGE + r"\s*(?:of|out of|/)\s*6(?![\d,.]?\d)", re.I)
COVERAGE_RE = re.compile(r"(?<![\d.,/$])(\d)\s*(?:of|out of|/)\s*5(?![\d,.]?\d)", re.I)
COMPONENT_RE = re.compile(
    r"\b(?P<name>use|dimensional|environment(?:al)?)(?:\s+(?:score|component|fit|entitlement|hazards?))?"
    r"(?:\s*(?:is|of|=|:|scored?|scores))?\s*" + _RANGE + r"(?:\s*(?:/|of|out of)\s*2)?(?![\d,]*\d)(?!\s*(?:ft|feet|sf|sq|%))",
    re.I,
)
SHORT_DATE_RE = re.compile(r"(?<![\d/])(1[0-2]|0?[1-9])/([0-2]?\d|3[01])(?![\d/])")
MONEY_RE = re.compile(r"\$\s?(" + NUMBER + r")")
PERCENT_RE = re.compile(r"([+\-−]?)(" + NUMBER + r")\s?(?:%|percent\b)", re.I)
DIMS_RE = re.compile(r"(" + NUMBER + r")\s?[x×]\s?(" + NUMBER + r")\s?(?:ft|feet)\b", re.I)
AREA_RE = re.compile(r"(" + NUMBER + r")\s?(?:sq\.?\s?ft\.?|square\s+feet|square\s+foot|sf\b|ft²|ft2\b)", re.I)
LENGTH_RE = re.compile(r"(" + NUMBER + r")\s?(?:-\s?)?(?:ft\b|feet\b|foot\b|')", re.I)
RATIO_RE = re.compile(r"(" + NUMBER + r")\s?(?:x\b|×|times\b)", re.I)
BARE_RE = re.compile(r"(?<![A-Za-z0-9.])([+\-−]?)(" + NUMBER + r")(?![A-Za-z0-9]|\.\d)")
APPROX_RE = re.compile(r"(?:about|approximately|approx\.?|roughly|around|nearly|~)\s*\$?\s*$", re.I)


def _mask(text: str, start: int, end: int) -> str:
    return text[:start] + " " * (end - start) + text[end:]


def _approx(text: str, start: int) -> bool:
    return bool(APPROX_RE.search(text[max(0, start - 16):start]))


def normalize_section(prefix: str, sec: str) -> str:
    prefix = prefix.strip().lower()
    if prefix.startswith(("chapter", "ch.")) and "." not in sec:
        return f"Chapter {sec}"
    if prefix.startswith("§") and "." not in sec:
        return f"Chapter {sec}"
    return sec


def tokenize(text: str) -> list[Token]:
    """All numeric-bearing tokens of ``text``, each span validated by exactly one kind."""
    out: list[Token] = []
    work = text

    def take(regex: re.Pattern[str], build) -> None:
        nonlocal work
        for m in list(regex.finditer(work)):
            tok = build(m)
            if tok is not None:
                out.append(tok)
                work = _mask(work, m.start(), m.end())

    take(PIN_RE, lambda m: Token("pin", m.group(0), m.start(), m.end(), ref=m.group(0)))
    take(ACT_RE, lambda m: Token("code", m.group(0), m.start(), m.end(),
                                 ref=f"Act {int(m.group(1))} of {m.group(2)}" + (f" §{m.group(3)}" if m.group(3) else "")))
    take(PREFIXED_CODE_RE, lambda m: Token("code", m.group(0), m.start(), m.end(),
                                           ref=normalize_section(m.group("prefix"), m.group("sec"))))
    take(BARE_CODE_RE, lambda m: Token("code", m.group(0), m.start(), m.end(), ref=m.group("sec")))

    def iso(m: re.Match[str]) -> Token:
        return Token("date", m.group(0), m.start(), m.end(), ref=f"{m.group(1)}-{m.group(2)}-{m.group(3)}")

    def us(m: re.Match[str]) -> Token:
        return Token("date", m.group(0), m.start(), m.end(),
                     ref=f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}")

    def named(m: re.Match[str]) -> Token:
        month = MONTHS[m.group(1).lower()[:3]]
        year = m.group(3) or ""
        return Token("date", m.group(0), m.start(), m.end(),
                     ref=f"{year or '-'}-{month:02d}-{int(m.group(2)):02d}")

    take(ISO_DATE_RE, iso)
    take(US_DATE_RE, us)
    take(NAMED_DATE_RE, named)

    def rng(m: re.Match[str], kind: str, name: str = "") -> Token:
        lo = parse_num(m.group(1 if kind != "component" else 2))
        hi_txt = m.group(2 if kind != "component" else 3)
        nums = (lo, parse_num(hi_txt)) if hi_txt else (lo,)
        return Token(kind, m.group(0), m.start(), m.end(), nums=nums, name=name)

    def partial(m: re.Match[str]) -> Token:
        t = rng(m, "partial")
        return Token("partial", t.text, t.start, t.end, nums=t.nums + (parse_num(m.group(3)),))

    take(PARTIAL_RE, partial)
    take(TOTAL_RE, lambda m: rng(m, "total"))
    take(COVERAGE_RE, lambda m: Token("coverage", m.group(0), m.start(), m.end(), nums=(parse_num(m.group(1)),)))
    take(COMPONENT_RE, lambda m: rng(m, "component", m.group("name").lower().removesuffix("al")
                                     if m.group("name").lower().startswith("environment") else m.group("name").lower()))

    def short_date(m: re.Match[str]) -> Token | None:
        month, day = int(m.group(1)), int(m.group(2))
        if not 1 <= day <= 31:
            return None
        return Token("date", m.group(0), m.start(), m.end(), ref=f"--{month:02d}-{day:02d}")

    take(SHORT_DATE_RE, short_date)

    def qty(kind: str, group: int = 1):
        def build(m: re.Match[str]) -> Token:
            return Token(kind, m.group(0), m.start(), m.end(), nums=(parse_num(m.group(group)),),
                         approx=_approx(text, m.start()))
        return build

    take(MONEY_RE, qty("money"))
    take(PERCENT_RE, lambda m: Token("percent", m.group(0), m.start(), m.end(),
                                     nums=(parse_num(m.group(1).replace("−", "-") + m.group(2)),),
                                     approx=_approx(text, m.start())))
    take(DIMS_RE, lambda m: Token("length", m.group(0), m.start(), m.end(),
                                  nums=(parse_num(m.group(1)), parse_num(m.group(2))),
                                  approx=_approx(text, m.start())))
    take(AREA_RE, qty("area"))
    take(LENGTH_RE, qty("length"))
    take(RATIO_RE, qty("ratio"))
    take(BARE_RE, lambda m: Token("bare", m.group(0), m.start(), m.end(),
                                  nums=(parse_num(m.group(1).replace("−", "-") + m.group(2)),),
                                  approx=_approx(text, m.start())))
    return sorted(out, key=lambda t: t.start)


# --------------------------------------------------------------------------
# Helpers for values carried by facts
# --------------------------------------------------------------------------


def numbers_in(text: str) -> list[Num]:
    """Every number written in a fact's string value (for engine-authored text facts)."""
    work = ISO_DATE_RE.sub(" ", text)
    return [parse_num(m.group(0)) for m in _NUM_RE.finditer(work)]


def dates_in(text: str) -> set[str]:
    """ISO forms of dates written in ``text`` (also "--MM-DD" month-day keys)."""
    out: set[str] = set()
    for tok in tokenize(text):
        if tok.kind == "date":
            out.add(tok.ref)
    return out


def num_matches(shown: Num, value: float, *, approx: bool = False) -> bool:
    """``shown`` is ``value`` written at its displayed precision (4,305 vs 4305.0; 157% vs 157.48)."""
    tol = 0.5 * 10 ** (-shown.decimals) + 1e-9
    if abs(shown.value - value) <= tol:
        return True
    if approx and value:
        return abs(shown.value - value) / abs(value) <= 0.05
    return False


QUOTE_RE = re.compile(r"\"([^\"]*)\"|“([^”]*)”|'([^']{12,})'")


def split_quotes(text: str) -> tuple[str, list[str]]:
    """(text with quoted spans blanked, list of quoted spans)."""
    quotes: list[str] = []
    outside = text
    for m in QUOTE_RE.finditer(text):
        quotes.append(next(g for g in m.groups() if g is not None))
        outside = _mask(outside, m.start(), m.end())
    return outside, quotes


WORD_RE = re.compile(r"[a-z0-9]+")


def words(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def ngrams(text: str, n: int = 4) -> set[tuple[str, ...]]:
    w = words(text)
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}
