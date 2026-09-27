"""Fetch public Zoning Board of Adjustment decisions and zoning-code sections (build-time only).

The app never runs this; it reads the saved text offline. Run:

    uv run --with curl_cffi python scripts/fetch_zba.py

pittsburghpa.gov and ecode360.com reject plain HTTP clients (bot protection), so the script uses
``curl_cffi`` with a browser TLS profile when it is installed and falls back to urllib otherwise.
A decision that cannot be fetched is recorded in index.csv with blank text fields and the run
continues.

Outputs
  data/zba/<slug>.txt          verbatim pypdf text of each decision (phone/email lines removed)
  data/zba/index.csv           slug, case_number, address, source_url, fetched_at, pages, sha256,
                               district, decision_date, status
  data/zba/code_sections.json  verbatim zoning-code sections used for relief-path quotes
"""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "zba"
BASE = "https://www.pittsburghpa.gov/files/assets/city/v/1/dcp/documents/zoning-board-of-adjustment/"

# Chosen from the 2026 ZBA meeting pages (Business-Development/City-Planning/City-Planning-Meetings/
# ZBA-Agendas/ZBA-<Month>-<day>-2026): residential new construction on lots in R1D, R1A, R2, RM and
# H districts involving use variances or dimensional (setback) variances.
DECISIONS: tuple[tuple[str, str], ...] = (
    ("kendall-street-58-of-2026", "kendall-street-58-of-2026.pdf"),
    ("rockland-avenue-96-of-2026", "rockland-avenue-96-of-2026.pdf"),
    ("spring-garden-avenue-158-of-2025", "1065-spring-garden-zba-decision-158-of-2026.pdf"),
    ("buena-vista-street-19-of-2026", "buena-vista-street-19-of-2026_1.pdf"),
    ("e-jefferson-street-3-of-2026", "e-jefferson-street-3-of-2026-zba-decision.pdf"),
    ("camp-street-16-of-2026", "3315-camp-street-16-of-2026-zba-decision.pdf"),
    ("hillcrest-street-10-of-2026", "5409-hillcrest-street-10-of-2026.pdf"),
    ("east-liberty-boulevard-87-of-2026", "east-liberty-boulevard-87-of-2026.pdf"),
)

# (key, ecode360 chapter page, start marker, end marker): each section is stored verbatim.
CODE_SECTIONS: tuple[tuple[str, str, str, str], ...] = (
    ("921.04", "https://ecode360.com/45479031", "921.04 Nonconforming Lots. A lot", "§ 921.05"),
    ("922.09.E", "https://ecode360.com/45479304", "E. General Conditions for Approval. No variance", "In granting any variance"),
    ("911.04.A.69", "https://ecode360.com/45476784",
     "69. Single-Unit Detached and Attached Residential. (a) In H Districts.", "If the lot in which"),
)

CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b")


def _get(url: str) -> bytes:
    try:
        from curl_cffi import requests as creq  # type: ignore[import-not-found]
        r = creq.get(url, impersonate="chrome", timeout=60)
        if r.status_code != 200:
            raise OSError(f"HTTP {r.status_code}")
        return r.content
    except ImportError:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - fixed public URLs
            return resp.read()


def _pdf_text(data: bytes) -> tuple[str, int]:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    kept = [line for line in text.splitlines() if not CONTACT.search(line)]
    return "\n".join(kept), len(reader.pages)


def _header(text: str, label: str) -> str:
    m = re.search(rf"^{label}:\s*(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _iso(date_text: str) -> str:
    try:
        return datetime.strptime(date_text.strip(), "%B %d, %Y").date().isoformat()
    except ValueError:
        return ""


def fetch_decisions() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for slug, name in DECISIONS:
        url = BASE + name
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        row = {"slug": slug, "case_number": "", "address": "", "source_url": url, "fetched_at": now,
               "pages": "", "sha256": "", "district": "", "decision_date": "", "status": ""}
        try:
            text, pages = _pdf_text(_get(url))
        except Exception as exc:  # noqa: BLE001 - record and continue
            row["status"] = f"fetch failed: {type(exc).__name__}: {exc}"[:200]
            print(f"FAILED {slug}: {row['status']}", file=sys.stderr)
            rows.append(row)
            continue
        (OUT / f"{slug}.txt").write_text(text, encoding="utf-8")
        case = _header(text, "Zone Case")
        row.update(case_number=f"{case}" if case else "", address=_header(text, "Address"),
                   pages=str(pages), sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                   district=_header(text, r"Zoning Districts?"),
                   decision_date=_iso(_header(text, "Date of Decision")), status="ok")
        print(f"ok {slug}: {pages} pages, case {row['case_number']}, {row['district']}")
        rows.append(row)
    with (OUT / "index.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fetch_code() -> None:
    pages: dict[str, str] = {}
    sections = {}
    for key, url, start, end in CODE_SECTIONS:
        try:
            if url not in pages:
                raw = _get(url).decode("utf-8", "replace")
                pages[url] = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)))
            page = pages[url]
            i = page.rindex(start)
            j = page.index(end, i)
            sections[key] = {"source_url": url, "text": page[i:j].strip()}
            print(f"ok code {key}: {j - i} chars")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED code {key}: {exc}", file=sys.stderr)
    doc = {"_comment": "Verbatim Pittsburgh Zoning Code sections (ecode360), fetched "
                       + datetime.now(timezone.utc).date().isoformat()
                       + " by scripts/fetch_zba.py; used only as the source for relief-path quotes.",
           "sections": sections}
    (OUT / "code_sections.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n",
                                            encoding="utf-8")


if __name__ == "__main__":
    fetch_decisions()
    fetch_code()
