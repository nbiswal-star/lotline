"""Atomic memo claims and the memo container."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from lotline.memo.checker import CheckReport

ClaimType = Literal["fact", "status", "score", "next_check", "caveat", "conflict_summary"]
Author = Literal["engine", "llm"]

CLAIM_TYPES: tuple[str, ...] = ("fact", "status", "score", "next_check", "caveat", "conflict_summary")
LLM_CLAIM_TYPES: tuple[str, ...] = ("fact", "status", "score", "next_check", "caveat")
AUTHORS: tuple[str, ...] = ("engine", "llm")


@dataclass(frozen=True)
class Claim:
    """One atomic, cited statement. ``fact_ids`` point into the active result's facts."""

    text: str
    fact_ids: tuple[str, ...]
    claim_type: ClaimType
    author: Author = "engine"


@dataclass
class Memo:
    pin: str
    claims: list[Claim]
    source: Literal["deterministic", "llm"]
    rejected_draft: CheckReport | None = None
    report: CheckReport | None = None  # checker report for the claims shown
    fallback_reason: str | None = None  # why the deterministic memo was used

    @property
    def text(self) -> str:
        return "\n".join(c.text for c in self.claims)
