"""Stale-source warning hook (adversarial case 8). Pure functions over the manifest."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from lotline.models import SourceEntry

from . import policy


def _as_date(text: str) -> date | None:
    try:
        return date.fromisoformat(text.strip()[:10])
    except (ValueError, AttributeError):
        return None


def stale_source_warnings(
    manifest: Mapping[str, SourceEntry],
    *,
    advertisement_date: date = policy.ADVERTISEMENT_DATE,
    sale_status_sources: tuple[str, ...] = policy.SALE_STATUS_SOURCES,
) -> list[str]:
    """Warn when a sale-status source snapshot predates the controlling advertisement.

    Never says "will be sold".
    """
    stale = []
    for sid in sale_status_sources:
        entry = manifest.get(sid)
        if entry is None:
            continue
        as_of = _as_date(entry.snapshot_as_of)
        if as_of is None or as_of < advertisement_date:
            stale.append(f"{sid} as of {entry.snapshot_as_of or 'unknown'}")
    if not stale:
        return []
    return [
        f"Source snapshot predates the City advertisement dated {advertisement_date.isoformat()} "
        f"({'; '.join(stale)}): {policy.STALE_WARNING}."
    ]


def sale_date_passed_warning(sale_date: str, today: date | None) -> list[str]:
    """When screening after the recorded sale date, status is no longer the snapshot's."""
    if today is None:
        return []
    sd = _as_date(sale_date)
    if sd is None or today <= sd:
        return []
    return [f"The recorded sale date {sale_date} has passed: {policy.STALE_WARNING}."]
