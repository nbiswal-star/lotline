"""Layer 1: load the frozen CSV snapshot into immutable typed records.

Every CSV is read with ``dtype=str`` and an explicit ``usecols`` allowlist, so
columns that hold prepared answers (or undocumented flags) can never be
selected. All normalization happens here; nothing downstream sees raw strings.

The loader reads only files under ``data/``. It never reads test data or
preparation artifacts under ``docs/``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path

import pandas as pd

from lotline.models import (
    FIELD_SOURCE,
    AdvertRecord,
    DistrictRule,
    ParcelContext,
    ParcelFacts,
    RecordText,
    Reconciliation,
    SourceEntry,
    Snapshot,
    TreasuryRecord,
    sfha_status,
)
from lotline.reconcile import PIN_PATTERN, account_pin_mismatches, pin_from_parts, reconcile

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

TREASURY_FILE = "treasury_sale_2026-10-02_enriched.csv"
ADVERT_FILE = "advert_2026-09-16_reconciliation.csv"
PARCEL_FACTS_FILE = "parcel_facts.csv"
DISTRICT_RULES_FILE = "district_rules.csv"
MANIFEST_FILE = "source_manifest.csv"
# Optional: enforcement-record text for the AI evidence reader. Absent -> no record text.
RECORD_TEXT_FILE = "record_text.csv"

# --------------------------------------------------------------------------
# Column allowlists. Only these columns are ever read from each file.
# --------------------------------------------------------------------------

TREASURY_COLUMNS: tuple[str, ...] = (
    "pin", "address", "nbhd", "ward", "sale_date", "total_tax_due", "demo_cost_due",
    "classdesc", "usedesc", "lotarea", "fm_land", "fm_bldg", "zon_code", "asof",
    "delq_prior_years", "pli_event_rows",
)
ADVERT_COLUMNS: tuple[str, ...] = ("sale_no", "account", "pin", "ad_address", "upset")
PARCEL_COLUMNS: tuple[str, ...] = (
    "pin", "location", "neighborhood", "zone", "zoning_polygon", "assess_lotarea_sf",
    "county_gis_area_sf", "mbr_short_side_ft", "mbr_long_side_ft", "upset_price",
    "assessed_land_value", "pli_unique_casefiles", "pli_open_or_in_court", "pli_latest_event",
    "condemned_case_active", "condemned_case_created", "condemned_case_address", "rco_overlay",
    "historic_district", "slope25_layer", "undermined_layer", "landslide_prone_layer",
    "fema_zone", "streets_within_30ft", "possible_corner",
)
RULE_COLUMNS: tuple[str, ...] = (
    "district", "single_unit_permission", "two_unit_permission", "min_lot_sf",
    "front_setback_ft", "rear_setback_ft", "exterior_side_ft", "interior_side_ft",
    "dimensions_applicable", "dimensions_encoded", "site_standard_blocks_dimensional",
    "use_citation", "dimensional_citation", "site_standard",
)
# Optional provenance/display columns: read when present, None when the file predates them.
RULE_OPTIONAL_COLUMNS: tuple[str, ...] = ("rules_as_of", "amended_by", "site_standard_summary")
MANIFEST_COLUMNS: tuple[str, ...] = (
    "source_id", "snapshot_as_of", "query_completed", "local_artifact", "scope",
)
RECORD_TEXT_COLUMNS: tuple[str, ...] = ("source_id", "pin", "record_id", "record_date", "field", "text")
RECORD_TEXT_SOURCES = frozenset({"pli_violations", "condemned_properties", "pli_permits"})
# Artifacts a manifest entry may name without the file being present.
OPTIONAL_ARTIFACTS = frozenset({RECORD_TEXT_FILE})

# --------------------------------------------------------------------------
# Expected universe counts for this frozen snapshot (Treasury pull 2026-09-24,
# City advertisement dated 2026-09-16). They are recomputed from the loaded
# data at startup and compared here; a mismatch means the snapshot changed and
# the demo narrative (96 vs 77 vs 19) must be re-verified before shipping.
# --------------------------------------------------------------------------

EXPECTED_COUNTS: dict[str, int] = {
    "treasury": 96,
    "advertised": 77,
    "matched": 77,
    "unmatched_treasury": 19,
    "unmatched_advert": 0,
    "price_check_pass": 77,
    "account_pin_mismatches": 0,
    "advertised_structures": 63,
    "advertised_vacant": 14,
    "parcel_facts": 15,
}

PERMISSIONS = frozenset({"P", "A", "S", "C", "PROHIBITED"})

_TRUE = frozenset({"Y", "YES", "TRUE", "T", "1"})
_FALSE = frozenset({"N", "NO", "FALSE", "F", "0"})
_NONE_TEXT = frozenset({"", "NONE", "NONE FOUND"})

class SnapshotError(RuntimeError):
    """The frozen snapshot is missing, malformed, or no longer matches expectations."""


# --------------------------------------------------------------------------
# Scalar normalization (pure)
# --------------------------------------------------------------------------


def parse_bool(text: str, *, where: str = "value") -> bool:
    """YES/yes/Y/true/1 -> True; NO/no/N/false/0 -> False; anything else is an error."""
    t = text.strip().upper()
    if t in _TRUE:
        return True
    if t in _FALSE:
        return False
    raise SnapshotError(f"{where}: cannot interpret {text!r} as yes/no")


def optional_text(text: str) -> str | None:
    """Blank, "none" and "none found" (any case) -> None; otherwise stripped text."""
    t = text.strip()
    return None if t.upper() in _NONE_TEXT else t


def required_text(text: str, *, where: str) -> str:
    t = text.strip()
    if not t:
        raise SnapshotError(f"{where}: required value is blank")
    return t


def optional_float(text: str, *, where: str = "value") -> float | None:
    """Blank -> None (unknown), never 0."""
    t = text.strip()
    if not t:
        return None
    try:
        return float(t.replace(",", ""))
    except ValueError as exc:
        raise SnapshotError(f"{where}: {text!r} is not a number") from exc


def optional_nonnegative(text: str, *, where: str) -> float | None:
    """Blank -> None; negative -> SnapshotError. Used for setbacks and minimums (0 is valid)."""
    value = optional_float(text, where=where)
    if value is not None and value < 0:
        raise SnapshotError(f"{where}: {text!r} is negative")
    return value


def optional_measure(text: str, *, where: str, unit: str) -> tuple[float | None, str | None]:
    """A lot area or lot dimension, where 0 is physically impossible.

    Blank -> (None, None); 0 -> (None, warning: "0 <unit> recorded; treated as
    unknown"); negative -> SnapshotError; otherwise (value, None).
    """
    value = optional_nonnegative(text, where=where)
    if value == 0:
        return None, f"{where}: 0 {unit} recorded; treated as unknown"
    return value, None


def required_float(text: str, *, where: str) -> float:
    value = optional_float(text, where=where)
    if value is None:
        raise SnapshotError(f"{where}: required number is blank")
    return value


def required_int(text: str, *, where: str) -> int:
    value = required_float(text, where=where)
    if value != int(value):
        raise SnapshotError(f"{where}: {text!r} is not a whole number")
    return int(value)


def split_overlay(text: str) -> tuple[str | None, str | None]:
    """Split the prepared ``rco_overlay`` cell into ``(rco, other_overlay)``.

    A parenthesized value such as "(45 ft max height overlay)" is an overlay
    note, not a Registered Community Organization.
    """
    t = optional_text(text)
    if t is None:
        return None, None
    if t.startswith("(") and t.endswith(")"):
        return None, t[1:-1].strip() or None
    return t, None


def is_sfha(fema_zone: str) -> bool | None:
    """SFHA status (True / False / None = unknown); see ``lotline.models.sfha_status``."""
    return sfha_status(fema_zone)


def split_streets(text: str) -> tuple[str, ...]:
    return tuple(s.strip() for s in text.split(";") if s.strip())


def normalize_pin(text: str) -> str | None:
    """Canonical 16-character PIN from user input, or None if it cannot be parsed.

    Accepts the full PIN with or without spaces/dashes, the dashed short form
    ``map-block-lot[-supplement[-card]]``, and the undashed short form
    ``<map><block><lot>`` (e.g. "131N31"), which expands with supplement
    ``0000`` and card ``00``. This is pure formatting; use ``lookup_pin`` to
    confirm the PIN exists in the snapshot.
    """
    raw = text.strip().upper()
    if not raw:
        return None
    if "-" in raw:
        parts = [p.strip() for p in raw.split("-")]
        if 3 <= len(parts) <= 5 and all(parts[:3]):
            return pin_from_parts(*parts)
        return None
    compact = re.sub(r"\s+", "", raw)
    if PIN_PATTERN.match(compact):
        return compact
    m = re.fullmatch(r"(\d{1,4})([A-Z])(\d{1,5})", compact)
    if m:
        return pin_from_parts(*m.groups())
    return None


def lookup_pin(snapshot: Snapshot, text: str) -> str | None:
    """The snapshot PIN the user typed, or None. Never returns a PIN outside the snapshot."""
    pin = normalize_pin(text)
    return pin if pin is not None and pin in snapshot.treasury else None


# --------------------------------------------------------------------------
# CSV reading
# --------------------------------------------------------------------------


def _read_csv(path: Path, columns: tuple[str, ...], optional: tuple[str, ...] = ()) -> pd.DataFrame:
    """Read only ``columns`` (plus any ``optional`` columns present) as strings.

    Blanks become "" (never NaN); an absent optional column is filled with "".
    """
    if not path.is_file():
        raise SnapshotError(
            f"Snapshot file missing: {path}. LotLine runs only on the frozen CSVs in data/; "
            "restore the file from the repository."
        )
    header = pd.read_csv(path, nrows=0, dtype=str).columns
    missing = [c for c in columns if c not in header]
    if missing:
        raise SnapshotError(f"{path.name}: missing required column(s) {missing}")
    present = [c for c in optional if c in header]
    df = pd.read_csv(path, usecols=list(columns) + present, dtype=str, keep_default_na=False)
    for c in optional:
        if c not in present:
            df[c] = ""
    return df.map(str.strip)[list(columns) + list(optional)]


def _rows(df: pd.DataFrame) -> list[dict[str, str]]:
    return df.to_dict(orient="records")  # type: ignore[return-value]


def _check_pins(pins: list[str], file_name: str) -> None:
    bad = [p for p in pins if not PIN_PATTERN.match(p)]
    if bad:
        raise SnapshotError(f"{file_name}: PINs must be 16-character County PINs; bad: {bad[:5]}")
    dupes = sorted({p for p in pins if pins.count(p) > 1})
    if dupes:
        raise SnapshotError(f"{file_name}: duplicate PINs {dupes[:5]}")


def _check_date(text: str, *, where: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise SnapshotError(f"{where}: {text!r} is not an ISO date (YYYY-MM-DD)") from exc


# --------------------------------------------------------------------------
# Row builders
# --------------------------------------------------------------------------


def _treasury_record(r: Mapping[str, str], notes: list[str] | None = None) -> TreasuryRecord:
    w = f"{TREASURY_FILE} pin {r['pin']}"
    lotarea, note = optional_measure(r["lotarea"], where=f"{w} lotarea", unit="sf")
    if note and notes is not None:
        notes.append(note)
    return TreasuryRecord(
        pin=r["pin"],
        address=required_text(r["address"], where=f"{w} address"),
        neighborhood=required_text(r["nbhd"], where=f"{w} nbhd"),
        ward=required_text(r["ward"], where=f"{w} ward"),
        sale_date=_check_date(r["sale_date"], where=f"{w} sale_date").isoformat(),
        total_tax_due=required_float(r["total_tax_due"], where=f"{w} total_tax_due"),
        demo_cost_due=required_float(r["demo_cost_due"], where=f"{w} demo_cost_due"),
        classdesc=required_text(r["classdesc"], where=f"{w} classdesc"),
        usedesc=required_text(r["usedesc"], where=f"{w} usedesc"),
        lotarea=lotarea,
        fm_land=optional_float(r["fm_land"], where=f"{w} fm_land"),
        fm_bldg=optional_float(r["fm_bldg"], where=f"{w} fm_bldg"),
        zon_code=optional_text(r["zon_code"]),
        asof=_check_date(r["asof"], where=f"{w} asof").isoformat(),
        delq_prior_years=optional_float(r["delq_prior_years"], where=f"{w} delq_prior_years"),
        pli_event_rows=optional_float(r["pli_event_rows"], where=f"{w} pli_event_rows"),
    )


def _advert_record(r: Mapping[str, str]) -> AdvertRecord:
    w = f"{ADVERT_FILE} pin {r['pin']}"
    return AdvertRecord(
        sale_no=required_int(r["sale_no"], where=f"{w} sale_no"),
        account=required_text(r["account"], where=f"{w} account"),
        pin=r["pin"],
        ad_address=required_text(r["ad_address"], where=f"{w} ad_address"),
        upset=required_float(r["upset"], where=f"{w} upset"),
    )


def _parcel_facts(r: Mapping[str, str]) -> ParcelFacts:
    w = f"{PARCEL_FACTS_FILE} pin {r['pin']}"
    rco, other_overlay = split_overlay(r["rco_overlay"])
    fema_zone = required_text(r["fema_zone"], where=f"{w} fema_zone")
    notes: list[str] = []
    measures: dict[str, float | None] = {}
    for name, unit in (("assess_lotarea_sf", "sf"), ("county_gis_area_sf", "sf"),
                       ("mbr_short_side_ft", "ft"), ("mbr_long_side_ft", "ft")):
        measures[name], note = optional_measure(r[name], where=f"{w} {name}", unit=unit)
        if note:
            notes.append(note)
    return ParcelFacts(
        pin=r["pin"],
        location=required_text(r["location"], where=f"{w} location"),
        neighborhood=required_text(r["neighborhood"], where=f"{w} neighborhood"),
        zone=required_text(r["zone"], where=f"{w} zone"),
        zoning_polygon=required_text(r["zoning_polygon"], where=f"{w} zoning_polygon"),
        assess_lotarea_sf=measures["assess_lotarea_sf"],
        county_gis_area_sf=measures["county_gis_area_sf"],
        mbr_short_side_ft=measures["mbr_short_side_ft"],
        mbr_long_side_ft=measures["mbr_long_side_ft"],
        upset_price=optional_float(r["upset_price"], where=f"{w} upset_price"),
        assessed_land_value=optional_float(r["assessed_land_value"], where=f"{w} assessed_land_value"),
        pli_unique_casefiles=required_int(r["pli_unique_casefiles"], where=f"{w} pli_unique_casefiles"),
        pli_open_or_in_court=required_int(r["pli_open_or_in_court"], where=f"{w} pli_open_or_in_court"),
        pli_latest_event=optional_text(r["pli_latest_event"]),
        condemned_case_active=parse_bool(r["condemned_case_active"], where=f"{w} condemned_case_active"),
        condemned_case_created=optional_text(r["condemned_case_created"]),
        condemned_case_address=optional_text(r["condemned_case_address"]),
        rco=rco,
        other_overlay=other_overlay,
        historic_district=optional_text(r["historic_district"]),
        slope25=parse_bool(r["slope25_layer"], where=f"{w} slope25_layer"),
        undermined=parse_bool(r["undermined_layer"], where=f"{w} undermined_layer"),
        landslide_prone=parse_bool(r["landslide_prone_layer"], where=f"{w} landslide_prone_layer"),
        fema_zone=fema_zone,
        fema_sfha=is_sfha(fema_zone),
        streets_within_30ft=split_streets(r["streets_within_30ft"]),
        possible_corner=parse_bool(r["possible_corner"], where=f"{w} possible_corner"),
        load_warnings=tuple(notes),
    )


def _permission(text: str, *, where: str) -> str:
    p = text.strip().upper()
    if p not in PERMISSIONS:
        raise SnapshotError(f"{where}: permission {text!r} not in {sorted(PERMISSIONS)}")
    return p


def _district_rule(r: Mapping[str, str]) -> DistrictRule:
    w = f"{DISTRICT_RULES_FILE} district {r['district']}"
    return DistrictRule(
        district=required_text(r["district"], where=f"{DISTRICT_RULES_FILE} district"),
        single_unit_permission=_permission(r["single_unit_permission"], where=f"{w} single_unit_permission"),
        two_unit_permission=_permission(r["two_unit_permission"], where=f"{w} two_unit_permission"),
        min_lot_sf=optional_nonnegative(r["min_lot_sf"], where=f"{w} min_lot_sf"),
        front_setback_ft=optional_nonnegative(r["front_setback_ft"], where=f"{w} front_setback_ft"),
        rear_setback_ft=optional_nonnegative(r["rear_setback_ft"], where=f"{w} rear_setback_ft"),
        exterior_side_ft=optional_nonnegative(r["exterior_side_ft"], where=f"{w} exterior_side_ft"),
        interior_side_ft=optional_nonnegative(r["interior_side_ft"], where=f"{w} interior_side_ft"),
        dimensions_applicable=parse_bool(r["dimensions_applicable"], where=f"{w} dimensions_applicable"),
        dimensions_encoded=parse_bool(r["dimensions_encoded"], where=f"{w} dimensions_encoded"),
        site_standard_blocks_dimensional=parse_bool(
            r["site_standard_blocks_dimensional"], where=f"{w} site_standard_blocks_dimensional"
        ),
        use_citation=required_text(r["use_citation"], where=f"{w} use_citation"),
        dimensional_citation=optional_text(r["dimensional_citation"]),
        site_standard=optional_text(r["site_standard"]),
        rules_as_of=(
            _check_date(r["rules_as_of"], where=f"{w} rules_as_of").isoformat()
            if r.get("rules_as_of", "")
            else None
        ),
        amended_by=optional_text(r.get("amended_by", "")),
        site_standard_summary=optional_text(r.get("site_standard_summary", "")),
    )


def _source_entry(r: Mapping[str, str]) -> SourceEntry:
    w = f"{MANIFEST_FILE} source {r['source_id']}"
    return SourceEntry(
        source_id=required_text(r["source_id"], where=f"{MANIFEST_FILE} source_id"),
        snapshot_as_of=_check_date(r["snapshot_as_of"], where=f"{w} snapshot_as_of").isoformat(),
        query_completed=parse_bool(r["query_completed"], where=f"{w} query_completed"),
        local_artifact=required_text(r["local_artifact"], where=f"{w} local_artifact"),
        scope=r["scope"],
    )


def _load_keyed[T](
    path: Path,
    columns: tuple[str, ...],
    key: str,
    build: Callable[[Mapping[str, str]], T],
    optional: tuple[str, ...] = (),
) -> dict[str, T]:
    df = _read_csv(path, columns, optional)
    keys = df[key].tolist()
    if key == "pin":
        _check_pins(keys, path.name)
    else:
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        if dupes:
            raise SnapshotError(f"{path.name}: duplicate {key} values {dupes}")
    return {row[key]: build(row) for row in _rows(df)}


def _load_record_text(path: Path) -> dict[str, tuple[RecordText, ...]]:
    """Enforcement-record text by PIN; an absent file means no record text (never an error)."""
    if not path.is_file():
        return {}
    df = _read_csv(path, RECORD_TEXT_COLUMNS)
    out: dict[str, list[RecordText]] = {}
    for r in _rows(df):
        w = f"{RECORD_TEXT_FILE} record {r['record_id']}"
        if not PIN_PATTERN.match(r["pin"]):
            raise SnapshotError(f"{w}: bad PIN {r['pin']!r}")
        if r["source_id"] not in RECORD_TEXT_SOURCES:
            raise SnapshotError(f"{w}: unknown source_id {r['source_id']!r}")
        out.setdefault(r["pin"], []).append(RecordText(
            source_id=r["source_id"],
            pin=r["pin"],
            record_id=required_text(r["record_id"], where=f"{w} record_id"),
            record_date=(_check_date(r["record_date"], where=f"{w} record_date").isoformat()
                         if r["record_date"] else None),
            field=required_text(r["field"], where=f"{w} field"),
            text=required_text(r["text"], where=f"{w} text"),
        ))
    return {pin: tuple(rows) for pin, rows in out.items()}


# --------------------------------------------------------------------------
# Startup assertions
# --------------------------------------------------------------------------


def _observed_counts(
    treasury: Mapping[str, TreasuryRecord],
    advert: Mapping[str, AdvertRecord],
    parcels: Mapping[str, ParcelFacts],
    rec: Reconciliation,
) -> dict[str, int]:
    matched = rec.matched_pins
    return {
        "treasury": len(treasury),
        "advertised": len(advert),
        "matched": len(matched),
        "unmatched_treasury": len(rec.unmatched_treasury_pins),
        "unmatched_advert": len(rec.unmatched_advert_pins),
        "price_check_pass": len(rec.price_check_pass),
        "account_pin_mismatches": len(account_pin_mismatches(advert)),
        "advertised_structures": sum(treasury[p].is_structure for p in matched),
        "advertised_vacant": sum(not treasury[p].is_structure for p in matched),
        "parcel_facts": len(parcels),
    }


def _check_counts(observed: Mapping[str, int], expected: Mapping[str, int]) -> None:
    diffs = {k: (observed[k], v) for k, v in expected.items() if observed[k] != v}
    if diffs:
        detail = "; ".join(f"{k}: found {o}, expected {e}" for k, (o, e) in diffs.items())
        raise SnapshotError(f"Snapshot universe counts changed ({detail})")


def _check_manifest(manifest: Mapping[str, SourceEntry], data_dir: Path, today: date | None) -> None:
    missing = sorted(set(FIELD_SOURCE.values()) - set(manifest))
    if missing:
        raise SnapshotError(f"{MANIFEST_FILE}: no entry for source(s) {missing} used by facts")
    for entry in manifest.values():
        artifact = entry.local_artifact
        if artifact.endswith(".csv") and artifact not in OPTIONAL_ARTIFACTS \
                and not (data_dir / artifact).is_file():
            raise SnapshotError(
                f"{MANIFEST_FILE}: source {entry.source_id} points to missing file {artifact}"
            )
    if today is not None:
        future = [e.source_id for e in manifest.values()
                  if e.local_artifact.endswith(".csv") and date.fromisoformat(e.snapshot_as_of) > today]
        if future:
            raise SnapshotError(f"{MANIFEST_FILE}: data snapshots dated after {today}: {future}")


def _check_joins(
    treasury: Mapping[str, TreasuryRecord], parcels: Mapping[str, ParcelFacts]
) -> None:
    orphans = sorted(set(parcels) - set(treasury))
    if orphans:
        raise SnapshotError(f"{PARCEL_FACTS_FILE}: PINs not in the Treasury snapshot: {orphans}")
    sale_dates = {t.sale_date for t in treasury.values()}
    if len(sale_dates) != 1:
        raise SnapshotError(f"{TREASURY_FILE}: expected one sale date, found {sorted(sale_dates)}")


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def load_snapshot(data_dir: Path = DATA_DIR, today: date | None = None) -> Snapshot:
    """Load, normalize and validate the frozen snapshot. Raises ``SnapshotError``.

    ``today``, when given, additionally rejects data-snapshot dates in the
    future (a clock or data-entry error). It is optional so the app keeps
    starting after the sale date.
    """
    data_dir = Path(data_dir)
    treasury_notes: list[str] = []
    treasury = _load_keyed(data_dir / TREASURY_FILE, TREASURY_COLUMNS, "pin",
                           lambda r: _treasury_record(r, treasury_notes))
    advert = _load_keyed(data_dir / ADVERT_FILE, ADVERT_COLUMNS, "pin", _advert_record)
    parcels = _load_keyed(data_dir / PARCEL_FACTS_FILE, PARCEL_COLUMNS, "pin", _parcel_facts)
    rules = _load_keyed(
        data_dir / DISTRICT_RULES_FILE, RULE_COLUMNS, "district", _district_rule, RULE_OPTIONAL_COLUMNS
    )
    manifest = _load_keyed(data_dir / MANIFEST_FILE, MANIFEST_COLUMNS, "source_id", _source_entry)

    _check_manifest(manifest, data_dir, today)
    _check_joins(treasury, parcels)
    reconciliation = reconcile(treasury, advert)
    _check_counts(_observed_counts(treasury, advert, parcels, reconciliation), EXPECTED_COUNTS)

    return Snapshot(
        treasury=treasury,
        advert=advert,
        parcels=parcels,
        rules=rules,
        manifest=manifest,
        reconciliation=reconciliation,
        load_warnings=tuple(treasury_notes) + tuple(w for p in parcels.values() for w in p.load_warnings),
        record_text=_load_record_text(data_dir / RECORD_TEXT_FILE),
        parcel_points=load_parcel_points(data_dir),
        river_geometry=load_river_geometry(data_dir),
    )



def resolved_district(treasury: TreasuryRecord, facts: ParcelFacts | None) -> str | None:
    """District used for rule lookup: the zoning polygon when parcel facts exist,
    otherwise the Treasury/assessment zoning code (point-based, structures only)."""
    return facts.zoning_polygon if facts is not None else treasury.zon_code


def context_for(snapshot: Snapshot, pin: str) -> ParcelContext | None:
    """All engine inputs for ``pin``; None if the PIN is not in the Treasury snapshot.

    A district with no row in ``district_rules.csv`` yields ``rule=None``
    ("rules not encoded"), never an error.
    """
    treasury = snapshot.treasury.get(pin)
    if treasury is None:
        return None
    facts = snapshot.parcels.get(pin)
    district = resolved_district(treasury, facts)
    point = snapshot.parcel_points.get(pin)
    return ParcelContext(
        pin=pin,
        treasury=treasury,
        advert=snapshot.advert.get(pin) if pin in snapshot.reconciliation.matched_pins else None,
        facts=facts,
        rule=snapshot.rules.get(district) if district else None,
        manifest=snapshot.manifest,
        point_lat=point[0] if point else None,
        point_lon=point[1] if point else None,
        river_geometry=snapshot.river_geometry,
    )


# --------------------------------------------------------------------------
# Optional geometry: river shorelines and parcel points for the RIV riparian
# screen (lotline/engine/riparian.py). Both are optional: a missing or
# malformed file yields no geometry, and the screen then reports "unknown".
# --------------------------------------------------------------------------

RIVER_GEOMETRY_FILE = "geo/rivers_allegheny_county.geojson"
PARCEL_POINT_COLUMNS: tuple[str, ...] = ("pin", "lat", "lon")


def load_river_geometry(data_dir: Path = DATA_DIR) -> tuple:
    """River polygons from the cached County "Major Rivers" GeoJSON; () if absent or unreadable."""
    import json

    from lotline.engine.riparian import RiverPolygon

    path = Path(data_dir) / RIVER_GEOMETRY_FILE
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        rivers = []
        for feature in doc.get("features", []):
            geom = feature.get("geometry") or {}
            name = str((feature.get("properties") or {}).get("NAME", "")).strip() or "river"
            polys = geom.get("coordinates", [])
            if geom.get("type") == "Polygon":
                polys = [polys]
            elif geom.get("type") != "MultiPolygon":
                continue
            for poly in polys:
                rings = tuple(tuple((float(c[0]), float(c[1])) for c in ring) for ring in poly)
                if rings and len(rings[0]) >= 3:
                    rivers.append(RiverPolygon(name=name, rings=rings))
        return tuple(rivers)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        return ()


def load_parcel_points(data_dir: Path = DATA_DIR) -> dict[str, tuple[float, float]]:
    """Treasury point (lat, lon) per PIN; {} if the columns are absent. Reads only pin/lat/lon."""
    path = Path(data_dir) / TREASURY_FILE
    try:
        df = _read_csv(path, PARCEL_POINT_COLUMNS)
    except SnapshotError:
        return {}
    points: dict[str, tuple[float, float]] = {}
    for r in _rows(df):
        try:
            lat = optional_float(r["lat"], where=f"{TREASURY_FILE} lat")
            lon = optional_float(r["lon"], where=f"{TREASURY_FILE} lon")
        except SnapshotError:
            continue  # a malformed point is unknown, never guessed
        if lat is not None and lon is not None:
            points[r["pin"]] = (lat, lon)
    return points
