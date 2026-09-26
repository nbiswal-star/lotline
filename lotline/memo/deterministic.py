"""Deterministic cited memo: plain language built only from engine output and facts.

Every sentence is a ``Claim`` with the fact ids it rests on. Nothing here
decides anything: outcome, scores, conflicts, barriers and checks are copied
from the ``ScreeningResult`` (engine display strings verbatim). The memo must
pass ``lotline.memo.checker.check`` with zero violations for every parcel;
tests enforce this for all screened parcels.
"""

from __future__ import annotations

from lotline.memo.claims import Claim, Memo
from lotline.memo.outputs import (
    SETBACK_SCREEN,
    barrier_id,
    conflict_id,
    fact_universe,
    next_check_id,
    reason_id,
    warning_id,
)
from lotline.models import (
    ComponentScore,
    Conflict,
    ConflictLevel,
    Fact,
    Outcome,
    ScreeningResult,
    derived_fact_id,
    fact_id,
    rule_fact_id,
)

# --- Required caveats (exact wording; also used by the pipeline) ------------
DECISION_SUPPORT = "Decision support only; not legal, financial, title, survey or zoning advice."
ENVIRONMENT_CAVEAT = (
    "Environmental screening uses the checked screening layers only; where nothing is flagged the "
    "wording is 'no overlap in the checked screening layers', not a geotechnical or flood determination."
)
SETBACK_CAVEAT = (
    "The base-setback screen is illustrative and approximate: it uses the bounding rectangle of the "
    "County GIS polygon, not a survey, and contextual setbacks (Ch. 925) are not evaluated."
)
MARKET_CAVEAT = "Market demand and appraisal not evaluated; this packet is not an acquisition recommendation."
INFRASTRUCTURE_CAVEAT = "Utility capacity, laterals and legal access not established."
COMMUNITY_CAVEAT = (
    "Community plan alignment not evaluated; a Registered Community Organization listing is a contact "
    "for community review, not an endorsement."
)
SIDE_YARD_CAVEAT = (
    "Potential side yard or stewardship: not evaluated (no verified PLB ownership or adjacent "
    "owner-occupancy evidence in the v1 data)."
)
SALE_ROUTE_CAVEAT = (
    "Treasurer Sale route: competitive bidding, a redemption period applies, title is not cleared by "
    "the sale, and no PLB priority is verified."
)
OUT_OF_UNIVERSE_CAVEAT = "No screening score is computed for a record outside the sale universe."
STRUCTURE_CAVEAT = (
    "Condemnation and demolition records, where present, are shown for routing only; no vacant-land "
    "score is computed for a structure."
)
UNTRUSTED_CAVEAT = (
    "A source text record ({field}) is treated as untrusted data: it is not quoted, not followed as an "
    "instruction, and does not affect any screening result."
)

LEVEL_EFFECT = {
    ConflictLevel.CRITICAL: "Critical records conflict ({kind}): the whole parcel is held out of scoring.",
    ConflictLevel.MATERIAL: "Material records conflict ({kind}): only the affected component is held back ({affects}).",
    ConflictLevel.DISCLOSE: "Disclosed records difference ({kind}): no score change.",
}
KIND_LABEL = {
    "lot_area": "lot area",
    "current_condition": "current condition",
    "sale_universe": "sale universe",
    "zoning_split": "zoning split",
    "stale_source": "stale source",
}


class _Builder:
    def __init__(self, result: ScreeningResult) -> None:
        self.r = result
        self.pin = result.pin
        self.u = fact_universe(result)
        self.claims: list[Claim] = []

    # -- helpers ------------------------------------------------------------
    def val(self, fid: str) -> object:
        """A fact's value; untrusted source text is never reproduced by the engine memo."""
        f = self.u.get(fid)
        return None if f is None or f.evidence_class == "untrusted_text" else f.value

    def ids(self, *fids: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(f for f in fids if f in self.u))

    def add(self, text: str, fids: tuple[str, ...], ctype: str) -> None:
        if ctype != "caveat" and not fids:
            return  # never emit an uncited non-caveat claim
        self.claims.append(Claim(text=text, fact_ids=fids, claim_type=ctype, author="engine"))  # type: ignore[arg-type]

    def d(self, name: str) -> str:
        return derived_fact_id(self.pin, name)

    def fid(self, name: str, source: str | None = None) -> str:
        try:
            return fact_id(self.pin, name, source)
        except KeyError:
            return ""

    # -- sections -----------------------------------------------------------
    def identity(self) -> None:
        addr = self.fid("address", "wprdc_treasury_sales")
        nb = self.fid("neighborhood", "wprdc_treasury_sales")
        a, n = self.val(addr), self.val(nb)
        if a:
            text = f"Parcel {self.pin}: {a}" + (f" ({n})" if n else "") + "."
            self.add(text, self.ids(addr, nb), "fact")

    def status(self) -> None:
        o = self.r.outcome
        text = f"Screening outcome: {o.value}."
        if o is Outcome.ADVANCE:
            text += (" This is an apparent lower-discretion zoning path for staff review, not an "
                     "acquisition recommendation.")
        self.add(text, self.ids(self.d("screen_outcome")), "status")

    def score(self) -> None:
        from lotline.engine.scoring import components_summary

        r, e = self.r, self.r.ease
        if e is None:
            return
        comps = (r.use, r.dimensional, r.environment)
        score_ids = self.ids(self.d("ease_result"), self.d("use_score"), self.d("dimensional_score"),
                             self.d("environment_score"))
        if e.display == "Not scorable":
            conflict_ids = self.ids(*(conflict_id(self.pin, c.kind) for c in r.conflicts))
            self.add("Development Ease: Not scorable. A critical records conflict holds the whole parcel "
                     "out of scoring; no total or component score is shown.",
                     self.ids(self.d("ease_result"), *conflict_ids), "score")
        elif r.outcome is Outcome.DO_NOT_ADVANCE:
            self.add(f"Development Ease: {e.display}.", self.ids(self.d("ease_result")), "score")
        elif e.total_low is not None:
            self.add(f"Development Ease: {e.display} ({components_summary(*comps)}).", score_ids, "score")
        else:
            self.add(f"Development Ease: {e.display}; no total or band is shown "
                     f"({components_summary(*comps)}).", score_ids, "score")

    def component(self, c: ComponentScore | None, label: str) -> None:
        if c is None or not c.reason:
            return
        rid = reason_id(self.pin, c.name)
        plain = [fid for fid in c.fact_ids if fid in self.u and self.u[fid].evidence_class != "approximate"]
        self.add(f"{label}: {c.reason}.", self.ids(rid, *plain), "fact")

    def setback(self) -> None:
        r = self.r
        if r.setback_screen in ("", "not computed"):
            return
        env = [self.d(f"envelope_{s.label}_{dim}_ft") for s in r.scenarios for dim in ("width", "depth")]
        self.add(f"Base-setback screen: {r.setback_screen} (illustrative, approximate geometry; "
                 "contextual setbacks (Ch. 925) not evaluated).",
                 self.ids(self.d(SETBACK_SCREEN), *env), "fact")

    def coverage(self) -> None:
        from lotline.engine.coverage import COVERAGE_LABELS

        r = self.r
        if not r.coverage:
            return
        parts = "; ".join(f"{g} {COVERAGE_LABELS.get(g, g)}: {'yes' if ok else 'no'}"
                          for g, ok in r.coverage.items())
        self.add(f"Evidence coverage: {r.coverage_display} groups ({parts}).",
                 self.ids(self.d("evidence_coverage")), "score")

    def conflicts(self) -> None:
        for c in self.r.conflicts:
            self.claims.append(conflict_summary_claim(self.r, c))
            text = LEVEL_EFFECT[c.level].format(kind=KIND_LABEL.get(c.kind, c.kind),
                                                affects=", ".join(c.affects) or "none")
            self.add(text, self.ids(conflict_id(self.pin, c.kind)), "status")

    def key_facts(self) -> None:
        pin, r = self.pin, self.r
        zp = self.fid("zoning_polygon")
        if self.val(zp):
            self.add(f"Zoning district (polygon): {self.val(zp)}.", self.ids(zp), "fact")
        a_id, g_id = self.fid("assess_lotarea_sf"), self.fid("county_gis_area_sf")
        a, g = self.val(a_id), self.val(g_id)
        if isinstance(a, (int, float)):
            self.add(f"The assessment record reports a lot area of {a:,.0f} sq ft.", self.ids(a_id), "fact")
        if isinstance(g, (int, float)):
            self.add(f"The County GIS polygon area is {g:,.0f} sq ft.", self.ids(g_id), "fact")
        district = self.val(zp)
        if district:
            m_id = rule_fact_id(str(district), "min_lot_sf")
            m = self.val(m_id)
            if isinstance(m, (int, float)) and m > 0:
                self.add(f"The {district} district minimum lot area is {m:,.0f} sq ft (district rule).",
                         self.ids(m_id), "fact")
        hz = [self.fid(n) for n in ("landslide_prone", "slope25", "undermined", "fema_zone", "fema_sfha")]
        hz_ids = self.ids(self.d("hazard_families"), *hz)
        if len(hz_ids) > 1:
            if r.hazard_families:
                self.add(f"Checked hazard families flagged: {', '.join(r.hazard_families)} (screening layers "
                         "only; not a geotechnical or flood determination).", hz_ids, "fact")
            else:
                self.add("No overlap in the checked screening layers (landslide-prone, slope25, undermined, "
                         "FEMA SFHA); screening layers only, not a geotechnical or flood determination.",
                         hz_ids, "fact")
        st = self.fid("streets_within_30ft")
        streets = self.val(st)
        if streets:
            self.add("Street centerlines in approximate proximity to the parcel (proximity only, not legal "
                     f"frontage or access): {'; '.join(streets)}.", self.ids(st), "fact")
        pc = self.fid("possible_corner")
        if self.val(pc) is True:
            self.add("Possible corner lot (geometry heuristic; corner status not established).",
                     self.ids(pc), "fact")

        sale_no, upset = self.fid("sale_no"), self.fid("upset")
        if self.val(sale_no) is not None and isinstance(self.val(upset), (int, float)):
            as_of = self.u[upset].as_of
            self.add(f"The City advertisement dated {as_of} lists sale no. {self.val(sale_no)} with an upset "
                     f"price of ${self.val(upset):,.2f}.", self.ids(sale_no, upset), "fact")
        land, ratio = self.fid("assessed_land_value"), self.d("upset_to_assessed_land")
        if isinstance(self.val(land), (int, float)) and isinstance(self.val(ratio), (int, float)):
            self.add(f"Assessed land value is ${self.val(land):,.2f}; the upset price is {self.val(ratio)} "
                     "times the assessed land value (acquisition-burden indicator only).",
                     self.ids(land, ratio), "fact")
        sd = self.fid("sale_date", "wprdc_treasury_sales")
        if self.val(sd):
            self.add(f"Treasurer sale date recorded in the Treasury snapshot: {self.val(sd)}.", self.ids(sd), "fact")
        dq = self.fid("delq_prior_years", "wprdc_treasury_sales")
        if isinstance(self.val(dq), (int, float)):
            self.add(f"Delinquent prior years recorded: {self.val(dq):g}.", self.ids(dq), "fact")
        u_id, o_id, le_id = self.fid("pli_unique_casefiles"), self.fid("pli_open_or_in_court"), self.fid("pli_latest_event")
        if isinstance(self.val(u_id), int) and isinstance(self.val(o_id), int):
            text = (f"PLI violations: {self.val(u_id)} unique casefiles, {self.val(o_id)} open or in court")
            ids = [u_id, o_id]
            le = self.val(le_id)
            if isinstance(le, str) and le:
                text += f"; latest event {le}"
                ids.append(le_id)
            self.add(text + ".", self.ids(*ids), "fact")
        rco = self.fid("rco")
        if self.val(rco):
            self.add(f"Registered Community Organization: {self.val(rco)} (community-review contact, not "
                     "endorsement).", self.ids(rco), "fact")
        hd = self.fid("historic_district")
        if self.val(hd):
            self.add(f"Historic district: {self.val(hd)} (historic-review screening flag).", self.ids(hd), "fact")

    def barriers(self) -> None:
        for i, b in enumerate(self.r.barriers):
            self.add(f"Barrier: {b}.", self.ids(barrier_id(self.pin, i)), "fact")

    def next_checks(self) -> None:
        for i, nc in enumerate(self.r.next_checks):
            self.add(f"Next check: {nc.check} (owner: {nc.owner}).", self.ids(next_check_id(self.pin, i)),
                     "next_check")

    def untrusted(self) -> None:
        for f in self.u.values():
            if f.evidence_class == "untrusted_text" and f.pin == self.pin:
                self.add(UNTRUSTED_CAVEAT.format(field=f.field.replace("_", " ")), (f.id,), "caveat")

    def warnings(self) -> None:
        self.claims.extend(warning_claims(self.r))

    def usedesc(self) -> None:
        u, c = self.fid("usedesc"), self.fid("classdesc")
        if self.val(u):
            self.add(f"Assessment use description: {self.val(u)}; class: {self.val(c)}.", self.ids(u, c), "fact")


def conflict_summary_claim(result: ScreeningResult, c: Conflict) -> Claim:
    """The engine-authored summary: verbatim text, citing every fact in the group."""
    ids = tuple(dict.fromkeys((*c.fact_ids, conflict_id(result.pin, c.kind))))
    return Claim(text=c.summary, fact_ids=ids, claim_type="conflict_summary", author="engine")


def warning_claims(result: ScreeningResult) -> list[Claim]:
    return [Claim(text=f"Warning: {w}", fact_ids=(warning_id(result.pin, i),), claim_type="caveat", author="engine")
            for i, w in enumerate(result.warnings)]


def decision_support_claim() -> Claim:
    return Claim(text=DECISION_SUPPORT, fact_ids=(), claim_type="caveat", author="engine")


def deterministic_memo(result: ScreeningResult) -> Memo:
    b = _Builder(result)
    b.identity()
    b.status()
    b.warnings()
    if result.outcome in (Outcome.OUT_OF_UNIVERSE, Outcome.STRUCTURE):
        if result.outcome is Outcome.STRUCTURE:
            b.usedesc()
        b.barriers()
        b.next_checks()
        b.untrusted()
        b.add(OUT_OF_UNIVERSE_CAVEAT if result.outcome is Outcome.OUT_OF_UNIVERSE else STRUCTURE_CAVEAT, (), "caveat")
        b.add(DECISION_SUPPORT, (), "caveat")
        return Memo(pin=result.pin, claims=b.claims, source="deterministic")

    b.score()
    b.conflicts()
    b.component(result.use, "Use entitlement")
    b.component(result.dimensional, "Dimensional fit")
    b.component(result.environment, "Environmental hazard families")
    b.setback()
    b.coverage()
    b.key_facts()
    b.barriers()
    b.next_checks()
    b.untrusted()
    for text in (DECISION_SUPPORT, ENVIRONMENT_CAVEAT, SETBACK_CAVEAT, MARKET_CAVEAT, INFRASTRUCTURE_CAVEAT,
                 COMMUNITY_CAVEAT, SALE_ROUTE_CAVEAT, SIDE_YARD_CAVEAT):
        b.add(text, (), "caveat")
    return Memo(pin=result.pin, claims=b.claims, source="deterministic")


def engine_claim_texts(result: ScreeningResult) -> set[str]:
    """Every text the engine may author for this result (used by ENGINE_AUTHENTIC)."""
    texts = {c.text for c in deterministic_memo(result).claims}
    texts |= {c.summary for c in result.conflicts}
    texts |= {c.text for c in warning_claims(result)}
    texts.add(DECISION_SUPPORT)
    return texts


def unknown_pin_memo(query: str, snapshot_as_of: str) -> Memo:
    """Case 7: no packet, no facts, one statement of absence."""
    safe = "".join(ch for ch in query if ch.isalnum() or ch in " -")[:40]
    return Memo(
        pin="",
        claims=[Claim(text=f"PIN not found in snapshot dated {snapshot_as_of}: {safe!r}. No packet or facts "
                      "are produced.", fact_ids=(), claim_type="caveat", author="engine")],
        source="deterministic",
    )
