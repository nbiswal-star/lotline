"""Internal task tickets for next checks: a fixed template filled from engine output.

No AI-written text. The check, owner and trigger come from the engine's
``NextCheck``; evidence quotes (if any) are the record reader's verified,
verbatim quotes with their record IDs. Tickets are downloaded or copied by the
user; LotLine sends nothing anywhere.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta

TICKET_LABEL = "Internal task ticket (not sent anywhere)"


def due_before(sale_date: str) -> str:
    """The business day before the sale, as an ISO date; the raw value if unparseable."""
    try:
        d = date.fromisoformat(sale_date) - timedelta(days=1)
    except ValueError:
        return f"before the sale ({sale_date})"
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def ticket_markdown(*, check: Mapping[str, str], parcel_title: str, pin: str, pin_short: str,
                    address: str, outcome: str, sale_date: str, snapshot_label: str,
                    evidence: Iterable[object] = (), evidence_checks: Iterable[object] = ()) -> str:
    """Deterministic ticket text. ``evidence`` items need record_id, date, source and quote;
    ``evidence_checks`` are ``lotline.ai.evidence_checks.EvidenceCheck`` (check, owner, reason)."""
    lines = [
        f"# Task: {check['Check']}",
        "",
        f"- **Owner (who resolves it):** {check['Who resolves it']}",
        f"- **Why it is listed:** {check['Reason listed']}",
        f"- **Parcel:** {parcel_title} · PIN {pin_short} ({pin})",
        f"- **Address on record:** {address}",
        f"- **Screening outcome:** {outcome}",
        f"- **Due before:** {due_before(sale_date)} (Treasurer Sale {sale_date})",
        f"- **Snapshot:** {snapshot_label}",
        "",
        "## Verified record quotes",
    ]
    ev = list(evidence)
    if ev:
        for e in ev:
            rid = getattr(e, "record_id", "")
            when = getattr(e, "date", "")
            src = getattr(e, "source", "")
            quote = getattr(e, "quote", "")
            lines.append(f"- {rid} ({src}, {when}): the record says “{quote}”")
    else:
        lines.append("- None attached (read the enforcement record in the packet to attach verified quotes).")
    extra = [c for c in evidence_checks if getattr(c, "check", "") != check["Check"]]
    if extra:
        lines += ["", "## Checks prompted by the record evidence (AI-read, quote-verified)"]
        for c in extra:
            lines.append(f"- {getattr(c, 'check', '')} → {getattr(c, 'owner', '')} "
                         f"(prompted by: {getattr(c, 'reason', '')})")
    lines += [
        "",
        "## Resolution",
        "- [ ] Verified by: ____________________   Date: __________",
        "- Finding (cite the document): ________________________________",
        "",
        f"_{TICKET_LABEL}. Generated from LotLine screening output; decision support only — not legal, "
        "financial, title, survey or zoning advice._",
    ]
    return "\n".join(lines) + "\n"
