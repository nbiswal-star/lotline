"""Hand-built records for engine unit tests (no loader dependency)."""

from __future__ import annotations

from dataclasses import replace

from lotline.models import (
    AdvertRecord,
    DistrictRule,
    ParcelContext,
    ParcelFacts,
    SourceEntry,
    TreasuryRecord,
)

PIN = "9999X00001000000"

SOURCES = (
    "wprdc_treasury_sales", "city_advertisement", "treasurer_sale_regulations",
    "county_assessments", "county_parcels", "city_zoning", "landslide_prone", "slope25",
    "undermined", "fema_nfhl", "pli_violations", "condemned_properties", "rco_overlays",
    "historic_overlays", "zoning_code",
)
AS_OF = {"city_advertisement": "2026-09-16", "county_assessments": "2026-09-01",
         "county_parcels": "2026-09-21", "treasurer_sale_regulations": "2026-10-02"}


def manifest(**overrides: SourceEntry) -> dict[str, SourceEntry]:
    m = {
        s: SourceEntry(s, AS_OF.get(s, "2026-09-24"), True, "synthetic.csv", "synthetic")
        for s in SOURCES
    }
    m.update(overrides)
    return m


def rule(**kw) -> DistrictRule:
    base = dict(
        district="R2-H", single_unit_permission="P", two_unit_permission="P", min_lot_sf=1200.0,
        front_setback_ft=15.0, rear_setback_ft=15.0, exterior_side_ft=15.0, interior_side_ft=5.0,
        dimensions_applicable=True, dimensions_encoded=True, site_standard_blocks_dimensional=False,
        use_citation="911.02", dimensional_citation="903.03.D", site_standard=None,
    )
    base.update(kw)
    return DistrictRule(**base)


def facts(**kw) -> ParcelFacts:
    base = dict(
        pin=PIN, location="Synthetic St", neighborhood="Nowhere", zone="R2-H",
        zoning_polygon="R2-H", assess_lotarea_sf=3000.0, county_gis_area_sf=3100.0,
        mbr_short_side_ft=33.0, mbr_long_side_ft=100.0, upset_price=1200.0,
        assessed_land_value=1000.0, pli_unique_casefiles=0, pli_open_or_in_court=0,
        pli_latest_event=None, condemned_case_active=False, condemned_case_created=None,
        condemned_case_address=None, rco=None, other_overlay=None, historic_district=None,
        slope25=False, undermined=False, landslide_prone=False, fema_zone="X", fema_sfha=False,
        streets_within_30ft=("Synthetic St",), possible_corner=False,
    )
    base.update(kw)
    return ParcelFacts(**base)


def treasury(**kw) -> TreasuryRecord:
    base = dict(
        pin=PIN, address="SYNTHETIC ST", neighborhood="Nowhere", ward="1",
        sale_date="2026-10-02", total_tax_due=1200.0, demo_cost_due=0.0,
        classdesc="RESIDENTIAL", usedesc="VACANT LAND", lotarea=3000.0, fm_land=1000.0,
        fm_bldg=0.0, zon_code="R2-H", asof="2026-09-01", delq_prior_years=5.0,
        pli_event_rows=0.0,
    )
    base.update(kw)
    return TreasuryRecord(**base)


def advert(**kw) -> AdvertRecord:
    base = dict(sale_no=1, account="1019999X00001000000", pin=PIN, ad_address="Synthetic St",
                upset=1200.0)
    base.update(kw)
    return AdvertRecord(**base)


def ctx(*, facts_kw=None, rule_obj="default", advert_obj="default", treasury_kw=None,
        manifest_obj=None) -> ParcelContext:
    return ParcelContext(
        pin=PIN,
        treasury=treasury(**(treasury_kw or {})),
        advert=advert() if advert_obj == "default" else advert_obj,
        facts=facts(**(facts_kw or {})),
        rule=rule() if rule_obj == "default" else rule_obj,
        manifest=manifest_obj or manifest(),
    )


__all__ = ["PIN", "advert", "ctx", "facts", "manifest", "replace", "rule", "treasury"]
