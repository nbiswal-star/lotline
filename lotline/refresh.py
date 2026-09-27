"""Read-only snapshot freshness check against the live WPRDC Treasury Sales feed.

This module never writes under ``data/`` and never feeds the engine. It fetches
the live open-data records only when the user clicks, compares them to the
frozen snapshot, and reports differences (PINs added or removed, changed sale
date, total tax due or demolition cost due). A real refresh pipeline re-runs
the whole reconciliation before each sale; this panel only says whether one is
needed.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from lotline.models import Snapshot

API_URL = "https://data.wprdc.org/api/3/action/datastore_search"
RESOURCE_ID = "6b2aa631-26e0-4d02-abe0-7fb87707210c"
LIMIT = 2000
TIMEOUT_S = 10.0
# Only these live fields are requested; nothing else is read.
LIVE_FIELDS = ("pin", "treasury_sale_date", "total_tax_due", "demo_cost_due")

PIPELINE_NOTE = ("Read-only check. LotLine keeps screening the dated snapshot; a refresh pipeline "
                 "re-runs reconciliation (and every screen) before each sale, and changed universe "
                 "counts stop the import for review.")
OFFLINE_MESSAGE = "Can't reach WPRDC; snapshot unchanged."

FetchFn = Callable[[str, bytes, float], bytes]  # (url, JSON body, timeout seconds) -> response bytes


class RefreshError(RuntimeError):
    """The live feed could not be reached or returned something unusable."""


@dataclass(frozen=True)
class Change:
    pin: str
    kind: str  # "added" | "removed" | "sale_date" | "total_tax_due" | "demo_cost_due"
    snapshot_value: str
    live_value: str


@dataclass(frozen=True)
class RefreshReport:
    status: str  # "ok" | "offline"
    snapshot_as_of: str
    checked_at: str
    snapshot_count: int
    live_count: int | None
    changes: tuple[Change, ...] = field(default_factory=tuple)
    reason: str | None = None

    @property
    def headline(self) -> str:
        if self.status != "ok":
            return OFFLINE_MESSAGE
        n = len(self.changes)
        return f"Snapshot {self.snapshot_as_of} vs live now: {n} change{'s' if n != 1 else ''}"


def _urllib_fetch(url: str, body: bytes, timeout: float) -> bytes:
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "LotLine-freshness-check"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https URL
        return resp.read()


def request_body() -> bytes:
    return json.dumps({"resource_id": RESOURCE_ID, "limit": LIMIT,
                       "fields": ",".join(LIVE_FIELDS)}).encode()


def fetch_live(fetch: FetchFn | None = None, timeout: float = TIMEOUT_S) -> list[dict[str, Any]]:
    fetch = fetch or _urllib_fetch
    try:
        raw = fetch(API_URL, request_body(), timeout)
        payload = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 - any network/parse failure means "offline"
        raise RefreshError(type(exc).__name__) from exc
    if not isinstance(payload, dict) or not payload.get("success"):
        raise RefreshError("WPRDC returned an unsuccessful response")
    records = (payload.get("result") or {}).get("records")
    if not isinstance(records, list):
        raise RefreshError("WPRDC response had no records")
    return records


def _norm_pin(value: object) -> str:
    return "".join(str(value or "").split()).replace("-", "").upper()


def _money(v: float | None) -> str:
    return "none" if v is None else f"${v:,.2f}"


def _float(v: object) -> float | None:
    try:
        return None if v in (None, "") else float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def compare(snapshot: Snapshot, records: list[Mapping[str, Any]]) -> list[Change]:
    """Differences between the frozen Treasury snapshot and live records."""
    live: dict[str, Mapping[str, Any]] = {}
    for r in records:
        pin = _norm_pin(r.get("pin"))
        if pin:
            live[pin] = r
    changes: list[Change] = []
    snap = snapshot.treasury
    for pin in sorted(set(live) - set(snap)):
        r = live[pin]
        changes.append(Change(pin, "added", "not in snapshot",
                              f"in live feed (sale {str(r.get('treasury_sale_date') or 'unknown')[:10]})"))
    for pin in sorted(set(snap) - set(live)):
        changes.append(Change(pin, "removed", "in snapshot", "not in live feed"))
    for pin in sorted(set(snap) & set(live)):
        t, r = snap[pin], live[pin]
        live_date = str(r.get("treasury_sale_date") or "")[:10]
        if live_date and live_date != t.sale_date:
            changes.append(Change(pin, "sale_date", t.sale_date, live_date))
        for name, snap_value in (("total_tax_due", t.total_tax_due), ("demo_cost_due", t.demo_cost_due)):
            live_value = _float(r.get(name))
            if live_value is not None and round(live_value, 2) != round(snap_value, 2):
                changes.append(Change(pin, name, _money(snap_value), _money(live_value)))
    return changes


def check_live(snapshot: Snapshot, fetch: FetchFn | None = None, *,
               now: datetime | None = None, timeout: float = TIMEOUT_S) -> RefreshReport:
    """Fetch and compare; any failure returns an "offline" report and changes nothing."""
    entry = snapshot.manifest.get("wprdc_treasury_sales")
    as_of = entry.snapshot_as_of if entry else "unknown"
    checked = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M UTC")
    try:
        records = fetch_live(fetch, timeout)
    except RefreshError as exc:
        return RefreshReport("offline", as_of, checked, len(snapshot.treasury), None, (), str(exc))
    return RefreshReport("ok", as_of, checked, len(snapshot.treasury), len(records),
                         tuple(compare(snapshot, records)))


def change_rows(report: RefreshReport, labels: Mapping[str, str] | None = None) -> list[dict[str, str]]:
    kinds = {"added": "PIN added", "removed": "PIN removed", "sale_date": "Sale date changed",
             "total_tax_due": "Total tax due changed", "demo_cost_due": "Demolition cost due changed"}
    return [{"PIN": c.pin, "Parcel": (labels or {}).get(c.pin, ""), "Change": kinds.get(c.kind, c.kind),
             "Snapshot": c.snapshot_value, "Live now": c.live_value} for c in report.changes]
