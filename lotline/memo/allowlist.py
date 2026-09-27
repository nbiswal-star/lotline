"""Versioned allowlist of code references a memo may cite.

A reference outside this list fails the CODE_SECTIONS rule, even if it looks
plausible: the memo may only point at sections the team reviewed.

Entries:
- ``exact``: a section that is allowed as written (a parenthetical
  subdivision such as ``911.04.A.69(b)`` of an allowed section is allowed).
- ``prefixes``: a section family ``903.03`` allows ``903.03``, ``903.03.B``,
  ``903.03.B.2`` ... but not ``903.04``.
- ``chapters``: bare chapter references (``Chapter 925``, ``Ch. 904``).
- ``acts``: state acts cited by name.
- ``documents``: other cited instruments by excerpt id (e.g. the Treasurer's
  Sale regulations), matched exactly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SectionAllowlist:
    version: str
    as_of: str
    exact: frozenset[str]
    prefixes: frozenset[str]
    chapters: frozenset[str]
    acts: frozenset[str]
    documents: frozenset[str] = frozenset()

    def allows(self, ref: str) -> bool:
        """``ref`` is a normalized reference from ``lotline.memo.text.code_refs``."""
        ref = ref.strip()
        if ref in self.documents:
            return True
        if ref.startswith("Act "):
            return ref in self.acts
        if ref.startswith("Chapter "):
            return ref.removeprefix("Chapter ") in self.chapters or self._section(ref.removeprefix("Chapter "))
        return self._section(ref)

    def _section(self, sec: str) -> bool:
        base = re.sub(r"\([0-9A-Za-z]+\)$", "", sec)
        if base in self.chapters and base == sec:
            return True
        if base in self.exact:
            return True
        return any(base == p or base.startswith(p + ".") for p in self.prefixes)


DEFAULT_ALLOWLIST = SectionAllowlist(
    version="lotline-code-refs v3",
    as_of="2026-09-27",
    exact=frozenset({
        "906.04", "906.05", "906.08", "911.02", "911.04.A.69", "911.04.A.69A",
        "915.02", "921.04.A", "922.04", "925.06",
    }),
    # 911.01 (General) holds the use-table key, including 911.01.F (a use with no letter is prohibited).
    prefixes=frozenset({"903.03", "904.02", "905.01", "905.02", "905.04", "911.01"}),
    chapters=frozenset({"903", "904", "905", "906", "908", "911", "915", "916", "921", "922", "925"}),
    acts=frozenset({"Act 171 of 1984", "Act 171 of 1984 §304"}),
    documents=frozenset({"TSR-2026-10-02 ¶1-3"}),
)
