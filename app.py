"""LotLine Streamlit app. Renders engine output only; see lotline/ui for view models.

Run:  uv run streamlit run app.py
"""

from __future__ import annotations

import html
from datetime import date

import pandas as pd
import streamlit as st

from lotline.loaders import context_for, load_snapshot
from lotline.models import Outcome
from lotline.ui import memo_adapter as memo
from lotline.ui import text
from lotline.ui import viewmodels as vmod

VIEWS = ("Sale pipeline", "Parcel packet", "Compare", "Integrity")

st.set_page_config(page_title="LotLine", page_icon=":material/home_work:", layout="wide")

CSS = """
<style>
:root {
  --ll-good-bg:#E7F4EA; --ll-good-fg:#1D6A33; --ll-good-bd:#B5DEC1;
  --ll-caution-bg:#FFF4DF; --ll-caution-fg:#865100; --ll-caution-bd:#F0CF94;
  --ll-neutral-bg:#EEF1F4; --ll-neutral-fg:#3D4652; --ll-neutral-bd:#D3D9E0;
  --ll-critical-bg:#FDECEC; --ll-critical-fg:#A21F1F; --ll-critical-bd:#F2BDBD;
  --ll-muted:#5B6573;
}
.block-container { padding-top: 1.6rem; max-width: 1280px; }
.ll-badge { display:inline-block; padding:0.28rem 0.75rem; border-radius:999px; font-weight:600;
  font-size:0.95rem; border:1px solid; line-height:1.3; }
.ll-badge.sm { font-size:0.78rem; padding:0.12rem 0.55rem; font-weight:600; }
.ll-good { background:var(--ll-good-bg); color:var(--ll-good-fg); border-color:var(--ll-good-bd); }
.ll-caution { background:var(--ll-caution-bg); color:var(--ll-caution-fg); border-color:var(--ll-caution-bd); }
.ll-neutral { background:var(--ll-neutral-bg); color:var(--ll-neutral-fg); border-color:var(--ll-neutral-bd); }
.ll-critical { background:var(--ll-critical-bg); color:var(--ll-critical-fg); border-color:var(--ll-critical-bd); }
.ll-big { font-size:1.9rem; font-weight:700; line-height:1.2; margin:0.1rem 0 0.3rem 0; }
.ll-label { font-size:0.78rem; text-transform:uppercase; letter-spacing:0.05em; color:var(--ll-muted); font-weight:600; }
.ll-muted { color:var(--ll-muted); font-size:0.88rem; }
.ll-unknown { color:var(--ll-muted); font-size:0.85rem; border-top:1px dashed #D3D9E0; padding-top:0.4rem; margin-top:0.4rem; }
.ll-chip { display:inline-block; font-family:ui-monospace,Menlo,monospace; font-size:0.7rem; background:#F1F3F6;
  color:#3D4652; border:1px solid #DDE2E8; border-radius:4px; padding:0 0.3rem; margin:0 0.2rem 0.15rem 0; }
.ll-funnel { display:flex; gap:0.6rem; align-items:stretch; flex-wrap:wrap; }
.ll-step { flex:1 1 150px; border:1px solid #D3D9E0; border-radius:10px; padding:0.7rem 0.9rem; background:#FAFBFC; }
.ll-step .n { font-size:2rem; font-weight:700; line-height:1.1; }
.ll-step .d { font-size:0.85rem; color:#3D4652; }
.ll-step.keep { border-color:#9DC3EA; background:#F2F7FD; }
.ll-step.out { background:#F6F6F7; }
.ll-arrow { align-self:center; color:#9AA3AE; font-size:1.4rem; }
.ll-row { margin:0.15rem 0 0.35rem 0; font-size:0.93rem; }
.ll-row b { color:#1B2430; }
.ll-flag { color:var(--ll-caution-fg); font-size:0.88rem; margin:0.1rem 0 0.3rem 0; }
</style>
"""


# --------------------------------------------------------------------------
# Cached data (offline: frozen CSV snapshot only)
# --------------------------------------------------------------------------


@st.cache_resource(show_spinner="Loading frozen snapshot...")
def get_snapshot():
    return load_snapshot()


@st.cache_resource(show_spinner="Screening all records...")
def get_results(today: date):
    return vmod.screen_all(get_snapshot(), today=today)


@st.cache_resource
def get_config():
    return vmod.load_demo_config(get_snapshot())


@st.cache_resource(show_spinner="Running claim-checker cases...")
def get_cases():
    return memo.run_cases(snapshot=get_snapshot())


@st.cache_resource(show_spinner="Running red-team inputs through the checker...")
def get_red_team():
    return memo.red_team(get_snapshot())


def badge(label: str, tone: str, small: bool = False) -> str:
    return f'<span class="ll-badge ll-{tone}{" sm" if small else ""}">{html.escape(label)}</span>'


def esc(s: object) -> str:
    return html.escape(str(s))


# --------------------------------------------------------------------------
# Navigation state and callbacks
# --------------------------------------------------------------------------


def init_state(cfg: vmod.DemoConfig) -> None:
    ss = st.session_state
    ss.setdefault("view", VIEWS[0])
    ss.setdefault("packet_pin", cfg.default_packet)
    ss.setdefault("packet_miss", None)
    ss.setdefault("lot_select", cfg.default_packet)
    ss.setdefault("pin_text", "")
    if cfg.compare_default:
        ss.setdefault("cmp_pin_a", cfg.compare_default[0])
        ss.setdefault("cmp_pin_b", cfg.compare_default[1])


def open_packet(pin: str) -> None:
    ss = st.session_state
    ss.packet_pin, ss.packet_miss, ss.view = pin, None, "Parcel packet"
    options = {p for p, _ in vmod.lot_options(get_snapshot(), RESULTS)}
    ss.lot_select = pin if pin in options else None


def on_triage_select() -> None:
    rows = st.session_state.triage_table["selection"]["rows"]
    if rows:
        pins = vmod.vacant_pins(get_snapshot(), RESULTS)
        open_packet(pins[rows[0]])
        st.session_state.pin_text = ""


def on_pin_text() -> None:
    q = st.session_state.pin_text.strip()
    if not q:
        return
    res = vmod.resolve_query(get_snapshot(), q)
    if isinstance(res, vmod.NotFound):
        st.session_state.packet_pin = None
        st.session_state.packet_miss = res.message
        st.session_state.lot_select = None
    else:
        open_packet(res)


def on_lot_select() -> None:
    pin = st.session_state.lot_select
    if pin:
        open_packet(pin)
        st.session_state.pin_text = ""


def on_hero(pin: str) -> None:
    open_packet(pin)
    st.session_state.pin_text = ""


def on_compare_select(side: str) -> None:
    st.session_state[f"cmp_pin_{side}"] = st.session_state[f"cmp_select_{side}"]


# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------


def render_header(snapshot, results) -> None:
    left, right = st.columns([3, 2], vertical_alignment="center")
    with left:
        st.markdown(f"# {text.APP_NAME}")
        st.markdown(f"<div style='font-size:1.08rem;margin-top:-0.6rem'>{esc(text.PITCH)}</div>",
                    unsafe_allow_html=True)
    with right:
        dates = " · ".join(f"{label} {d}" for label, d in vmod.snapshot_dates(snapshot))
        st.markdown(badge(text.OFFLINE_BADGE, "neutral", small=True)
                    + f"<div class='ll-muted' style='margin-top:0.35rem'>Snapshot: {esc(dates)}</div>",
                    unsafe_allow_html=True)
    st.info(text.DECISION_SUPPORT, icon=":material/gavel:")
    for w in vmod.all_warnings(results):
        st.warning(f"**Source may be stale.** {w}", icon=":material/schedule:")


# --------------------------------------------------------------------------
# View 1: sale pipeline
# --------------------------------------------------------------------------


def render_pipeline(snapshot, results) -> None:
    f = vmod.funnel(snapshot, results)
    advert_date = vmod.display_date(vmod.source_date(snapshot, "city_advertisement"))
    st.subheader(f"From {f.treasury} open-data records to {f.vacant} vacant lots worth screening")
    st.markdown(
        f"""
<div class="ll-funnel">
  <div class="ll-step"><div class="n">{f.treasury}</div><div class="d">records in the WPRDC Treasury Sales open-data feed</div></div>
  <div class="ll-arrow">→</div>
  <div class="ll-step keep"><div class="n">{f.advertised}</div><div class="d">in the City advertisement ({advert_date})<br>PIN match {f.pins_matched}/{f.advertised} · price check {f.prices_agree}/{f.advertised}</div></div>
  <div class="ll-arrow">→</div>
  <div class="ll-step out"><div class="n">{f.structures}</div><div class="d">structures routed out: vacant-land model not applicable</div></div>
  <div class="ll-arrow">+</div>
  <div class="ll-step keep"><div class="n">{f.vacant}</div><div class="d"><b>advertised vacant lots</b> screened below</div></div>
</div>
<div class="ll-muted" style="margin-top:0.5rem">{f.not_advertised} open-data records are <b>not</b> in the City advertisement and are routed out of the sale universe.
{f.advert_not_in_treasury} advertised records are missing from open data. {esc(text.SALE_STATUS_NOTE)}</div>
""",
        unsafe_allow_html=True,
    )

    st.divider()
    st.subheader(f"Triage board: {f.vacant} advertised vacant lots")
    counts = " ".join(
        badge(f"{text.OUTCOME_SHORT[o]}: {n}", text.OUTCOME_TONE[o], small=True)
        for o, n in vmod.outcome_counts(results)
    )
    st.markdown(counts, unsafe_allow_html=True)
    st.caption(text.TRIAGE_NOTE + " Select a row to open its parcel packet.")

    rows = vmod.triage_rows(snapshot, results)
    df = pd.DataFrame(rows).drop(columns=["pin"])
    styled = df.style.map(_tone_style, subset=["Outcome"])
    st.dataframe(
        styled,
        hide_index=True,
        use_container_width=True,
        on_select=on_triage_select,
        selection_mode="single-row",
        key="triage_table",
        column_config={
            "Sale #": st.column_config.NumberColumn(width=55, help="Sale number in the City advertisement"),
            "Parcel": st.column_config.TextColumn(width=145),
            "Outcome": st.column_config.TextColumn(width=145),
            "Development Ease": st.column_config.TextColumn(width=120, help=text.EASE_HELP),
            "Evidence": st.column_config.TextColumn(help=text.COVERAGE_HELP, width=70),
            "Principal barrier": st.column_config.TextColumn(width=215),
            "First parcel-specific check": st.column_config.TextColumn(width=180),
            "Who resolves it": st.column_config.TextColumn(width=190),
        },
        height=(len(df) + 1) * 35 + 3,
    )
    st.download_button(
        "Download triage handoff (CSV)",
        data=vmod.triage_csv(snapshot, results),
        file_name="lotline-triage.csv",
        mime="text/csv",
        help="Engine-rendered rows in the same outcome grouping. Triage, not ranking.",
    )

    c1, c2 = st.columns(2)
    with c1, st.expander(f"{f.not_advertised} records not in the City advertisement"):
        routed = next(r for r in results.values() if r.outcome is Outcome.OUT_OF_UNIVERSE)
        st.caption(vmod.outcome_meaning(snapshot, routed) + " No owner data is loaded or shown.")
        st.dataframe(pd.DataFrame(vmod.routed_rows(snapshot, results, Outcome.OUT_OF_UNIVERSE)),
                     hide_index=True, use_container_width=True)
    with c2, st.expander(f"{f.structures} advertised structures routed out"):
        st.caption(text.OUTCOME_MEANING[Outcome.STRUCTURE] + " No owner data is loaded or shown.")
        st.dataframe(pd.DataFrame(vmod.routed_rows(snapshot, results, Outcome.STRUCTURE)),
                     hide_index=True, use_container_width=True)


_TONE_HEX = {
    "good": ("#E7F4EA", "#1D6A33"),
    "caution": ("#FFF4DF", "#865100"),
    "neutral": ("#EEF1F4", "#3D4652"),
}


def _tone_style(value: object) -> str:
    for o, label in text.OUTCOME_SHORT.items():
        if value == label:
            bg, fg = _TONE_HEX[text.OUTCOME_TONE[o]]
            return f"background-color: {bg}; color: {fg}; font-weight: 600"
    return ""


# --------------------------------------------------------------------------
# View 2: parcel packet
# --------------------------------------------------------------------------


def render_packet_picker(snapshot, results, cfg) -> None:
    options = vmod.lot_options(snapshot, results)
    labels = dict(options)
    vacant_count = vmod.funnel(snapshot, results).vacant
    c1, c2 = st.columns([2, 3])
    with c1:
        st.text_input(
            "Enter a parcel ID (PIN)",
            key="pin_text",
            on_change=on_pin_text,
            placeholder="e.g. 131-N-31 or the full 16-character PIN",
            help="Accepts the full 16-character County PIN (spaces or dashes allowed) or the short map-block-lot form.",
        )
    with c2:
        st.selectbox(
            f"…or choose one of the {vacant_count} advertised vacant lots",
            options=[p for p, _ in options],
            format_func=lambda p: labels.get(p, p),
            key="lot_select",
            on_change=on_lot_select,
            index=None,
            placeholder="Choose a lot",
        )
    if cfg.hero_buttons:
        cols = st.columns(len(cfg.hero_buttons) + 2)
        for col, key in zip(cols, cfg.hero_buttons):
            pin = cfg.parcels[key]
            col.button(vmod.parcel_label(snapshot, pin).split(",")[0] + f" ({vmod.short_pin(pin)})",
                       key=f"hero_{key}", on_click=on_hero, args=(pin,), use_container_width=True)


def render_packet(snapshot, results, cfg) -> None:
    render_packet_picker(snapshot, results, cfg)
    ss = st.session_state
    if ss.packet_miss:
        st.error(ss.packet_miss, icon=":material/search_off:")
        return
    pin = ss.packet_pin
    if not pin:
        st.caption("Enter a PIN or choose a lot to open its screening packet.")
        return
    p = vmod.packet(snapshot, results, pin, cfg.captions)
    st.divider()

    head, meta = st.columns([3, 2], vertical_alignment="bottom")
    with head:
        st.markdown(f"## {esc(p.title)}")
        st.markdown(f"<div class='ll-muted'>{esc(p.neighborhood)} · PIN {esc(p.pin_short)} "
                    f"(<code>{esc(p.pin)}</code>) · {esc(p.address)}</div>", unsafe_allow_html=True)
    with meta:
        st.markdown(f"<div class='ll-label'>Screening outcome</div>{badge(p.outcome_label, p.tone)}",
                    unsafe_allow_html=True)
    st.markdown(esc(p.outcome_meaning))
    if p.caption:
        st.caption(p.caption)
    st.download_button(
        "Download screening packet (Markdown)",
        data=vmod.packet_markdown(snapshot, results[pin], p),
        file_name=f"lotline-{p.pin_short.lower()}-packet.md",
        mime="text/markdown",
        help="Outcome, unresolved checks, deterministic memo, citations, snapshot dates and limits.",
    )

    for w in p.warnings:
        st.warning(w, icon=":material/schedule:")
    for c in p.conflicts:
        if c.level == "critical":
            st.error(f"**Critical conflict: this parcel is not scored.** {c.summary}", icon=":material/report:")
        elif c.level == "material":
            st.warning(f"**Material conflict: {', '.join(c.affects) or 'affected'} component withheld.** "
                       f"{c.summary}", icon=":material/warning:")
        else:
            st.info(f"**Disclosed difference (no score change).** {c.summary}", icon=":material/info:")

    if p.routing:
        render_routing_packet(p)
        return

    render_scores(p)
    st.markdown("### Flags by area")
    tiles = {t.key: t for t in p.tiles}
    r1 = st.columns(2)
    r2 = st.columns(2)
    for col, key in zip([*r1, *r2], ("zoning", "environmental", "infrastructure", "policy")):
        with col:
            render_tile(snapshot, tiles[key], p if key == "policy" else None)

    render_barriers_and_checks(p)
    render_memo(snapshot, results, pin)
    render_provenance(p)


def render_scores(p: vmod.PacketVM) -> None:
    left, right = st.columns([3, 2])
    with left, st.container(border=True):
        st.markdown("<div class='ll-label'>Development Ease (0–6)</div>", unsafe_allow_html=True,
                    help=text.EASE_HELP)
        st.markdown(f"<div class='ll-big'>{esc(p.ease_display)}</div>", unsafe_allow_html=True)
        if p.ease_band:
            st.markdown(badge(f"Band: {p.ease_band}", "neutral", small=True), unsafe_allow_html=True)
        critical = any(c.level == "critical" for c in p.conflicts)
        if critical:
            st.caption("Component values are not shown because a critical conflict prevents whole-parcel scoring.")
        else:
            cols = st.columns(len(p.components) or 1)
            for col, c in zip(cols, p.components):
                with col:
                    val = c.value if c.value in ("withheld", "n/a") else f"{c.value} / 2"
                    tone = "caution" if c.withheld else "neutral"
                    st.markdown(f"**{esc(c.label)}** &nbsp;{badge(val, tone, small=True)}<br>"
                                f"<span class='ll-muted'>{esc(c.short_reason)}</span>", unsafe_allow_html=True)
                    with st.expander("How this was computed"):
                        st.caption(c.reason)
    with right, st.container(border=True):
        st.markdown("<div class='ll-label'>Evidence coverage</div>", unsafe_allow_html=True,
                    help=text.COVERAGE_HELP)
        st.markdown(f"<div class='ll-big'>{esc(p.coverage_display)}</div>", unsafe_allow_html=True)
        for g, label, ok in p.coverage:
            icon = ":green[:material/check_circle:]" if ok else ":orange[:material/cancel:]"
            st.markdown(f"{icon} **{g}** {label}")
        st.caption("Coverage measures what was checked, not how good the lot is.")


def render_tile(snapshot, t: vmod.TileVM, p: vmod.PacketVM | None) -> None:
    with st.container(border=True):
        st.markdown(f"#### {t.title}")
        for flag in t.flags:
            st.markdown(f"<div class='ll-flag'>⚑ {esc(flag)}</div>", unsafe_allow_html=True)
        if p is not None and p.treasurer_sale:
            sale_date = vmod.sale_date(snapshot)
            sale_long = vmod.display_date_long(sale_date)
            st.markdown(badge(f"City Treasurer Sale · {sale_long}", "neutral", small=True), unsafe_allow_html=True)
            st.markdown("\n".join(f"- {term}" for term in text.TREASURER_SALE_TERMS))
            st.caption("Source: Second Class City Treasurer's Sale and Collection Act "
                       f"(Act 171 of 1984) and the City Treasurer Sale regulations for {sale_date}.")
            for label, value in p.acquisition:
                st.markdown(f"<div class='ll-row'><b>{esc(label)}:</b> {esc(value)}</div>", unsafe_allow_html=True)
        for label, value in t.rows:
            st.markdown(f"<div class='ll-row'><b>{esc(label)}:</b> {esc(value)}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='ll-unknown'><b>Not established:</b> {esc(t.unknown)}</div>",
                    unsafe_allow_html=True)


def render_barriers_and_checks(p: vmod.PacketVM) -> None:
    st.markdown("### Principal barriers")
    if p.barriers:
        st.markdown("\n".join(f"{i}. {b[0].upper()}{b[1:]}" for i, b in enumerate(p.barriers, 1)))
    else:
        st.markdown("None listed by the engine.")
    st.markdown("### Next checks: who resolves what")
    st.caption("LotLine stops here. Each open question goes to a named human role before any money "
               "or commitment moves. Tick items as they are verified (this session only).")
    pre_spend = [c for c in p.next_checks if c["Standard"] == "pre-spend"]
    specific = [c for c in p.next_checks if c["Standard"] == "no"]
    standard = [c for c in p.next_checks if c["Standard"] == "yes"]

    def checklist(rows: list[dict[str, str]], key: str) -> None:
        df = pd.DataFrame(rows).drop(columns=["Standard"])
        df.insert(0, "Verified", False)
        st.data_editor(
            df, hide_index=True, use_container_width=True, key=key,
            disabled=["Check", "Who resolves it", "Reason listed"],
            column_config={"Verified": st.column_config.CheckboxColumn(width="small")},
        )

    if pre_spend:
        st.markdown("**Before incurring costs**")
        checklist(pre_spend, f"checks_prespend_{p.pin}")
    if specific:
        st.markdown(f"**Specific to this parcel ({len(specific)})**")
        checklist(specific, f"checks_specific_{p.pin}")
    if standard:
        with st.expander(f"Standard checks for every advertised vacant lot ({len(standard)})",
                         expanded=not specific and not pre_spend):
            checklist(standard, f"checks_standard_{p.pin}")


def render_routing_packet(p: vmod.PacketVM) -> None:
    with st.container(border=True):
        st.markdown(f"**Development Ease:** {esc(p.ease_display)} (routed record; not screened)")
        for b in p.barriers:
            st.markdown(f"- {b[0].upper()}{b[1:]}")
    st.markdown("### Next step")
    st.dataframe(pd.DataFrame(p.next_checks).drop(columns=["Standard"]), hide_index=True,
                 use_container_width=True)
    render_provenance(p)


def render_provenance(p: vmod.PacketVM) -> None:
    with st.expander(f"Provenance: every fact behind this packet ({len(p.provenance)} facts)"):
        if p.area is not None:
            a = p.area
            st.markdown("**Lot area: both sources, both gap measures**")
            c1, c2, c3 = st.columns(3)
            c1.metric("Assessment lot area", a.assessment_sf)
            c2.metric("County GIS polygon area", a.county_gis_sf)
            c3.metric("District minimum", a.minimum_sf or "not encoded")
            st.markdown(f"- Directional gap **{a.gap_pct}** = {a.gap_formula}\n"
                        f"- Symmetric gap **{a.symmetric_pct}** = {a.symmetric_formula}")
            st.caption("LotLine never picks a winning source; a deed or survey resolves it.")
        st.caption("Evidence classes: " + " · ".join(
            f"**{k}**" for k in ("raw", "derived", "approximate", "rule")) +
            ". Conflict-group facts are listed first.")
        st.dataframe(pd.DataFrame(p.provenance), hide_index=True, use_container_width=True,
                     column_config={"Note": st.column_config.TextColumn(width="large")})


def render_claims(vm) -> None:
    sections = (
        ("Decision and score", {"status", "score", "conflict_summary"}),
        ("Evidence", {"fact"}),
        ("Next checks", {"next_check"}),
        ("Caveats", {"caveat"}),
    )
    shown: set[int] = set()
    for title, types in sections:
        claims = [(i, c) for i, c in enumerate(vm.claims) if c.claim_type in types]
        if not claims:
            continue
        st.markdown(f"**{title}**")
        for i, c in claims:
            shown.add(i)
            who = "" if c.author == "llm" else " <span class='ll-muted'>(engine)</span>"
            citations = f" · {len(c.fact_ids)} citation{'s' if len(c.fact_ids) != 1 else ''}"
            st.markdown(f"<div class='ll-row'>{esc(c.text)}{who}"
                        f"<span class='ll-muted'>{citations}</span></div>", unsafe_allow_html=True)
    for i, c in enumerate(vm.claims):
        if i not in shown:
            st.markdown(f"<div class='ll-row'>{esc(c.text)}</div>", unsafe_allow_html=True)
    citation_rows = [
        {"Claim": c.text, "Fact IDs": " · ".join(c.fact_ids) if c.fact_ids else "none"}
        for c in vm.claims
    ]
    with st.expander(f"Full citation IDs ({sum(len(c.fact_ids) for c in vm.claims)} references)"):
        st.dataframe(pd.DataFrame(citation_rows), hide_index=True, use_container_width=True,
                     column_config={"Claim": st.column_config.TextColumn(width="large"),
                                    "Fact IDs": st.column_config.TextColumn(width="large")})


CLAUDE_TONE = {"accepted": "good", "cached_accepted": "good", "rejected": "critical", "cached_rejected": "critical",
               "unavailable": "neutral", "refused": "caution", "failed": "caution", "error": "caution"}


def render_memo(snapshot, results, pin: str) -> None:
    with st.container(border=True):
        st.markdown("### Screening memo")
        det = memo.deterministic_fn()
        if det is None:
            st.caption("Memo: coming soon. The cited memo and claim checker load here when available; "
                       "the packet above is complete without it.")
            return
        ctx = context_for(snapshot, pin)
        prod = memo.produce_fn()
        checked = (lambda result: prod(result, None)) if prod is not None else det  # deterministic + checker report
        vm, err = memo.build_memo(checked, ctx=ctx, result=results[pin], snapshot=snapshot)
        if vm is None:
            vm, err = memo.build_memo(det, ctx=ctx, result=results[pin], snapshot=snapshot)
        key = f"claude_{pin}"
        # No network until this button is clicked.
        if st.button("Assemble with Claude (claim-checked)", key=f"btn_{key}"):
            with st.spinner("Claude is selecting approved claims; the checker verifies the assembled memo..."):
                st.session_state[key] = memo.claude_draft(results[pin])
        draft = st.session_state.get(key)
        if draft is not None:
            st.markdown(badge(draft.headline, CLAUDE_TONE.get(draft.status, "neutral"), small=True),
                        unsafe_allow_html=True)
            if draft.status in ("accepted", "cached_accepted") and draft.claims_checked is not None:
                st.caption(f"Claim checker: {draft.claims_checked} claims checked, 0 violations. "
                           "Engine-authored caveats, warnings and conflict summaries are inserted verbatim.")
            if draft.violations:
                st.caption(f"Claim checker rejected the draft ({draft.claims_checked} claims checked, "
                           f"{len(draft.violations)} violation(s)):")
                st.dataframe(pd.DataFrame([{"Rule": v.rule, "Message": v.message, "Claim": v.claim}
                                           for v in draft.violations]),
                             hide_index=True, use_container_width=True)
            for n in draft.notes:
                st.caption(n)
            if draft.memo is not None:
                vm, err = draft.memo, None
        if vm is None:
            st.caption(f"Memo unavailable ({err}). The packet above is complete without it.")
            return
        label = "Claude-assembled memo (claim-checked)" if vm.source == "llm" else "Deterministic cited memo"
        st.markdown(f"<span class='ll-label'>Showing:</span> " + badge(label, "neutral", small=True)
                    + (f" {badge(vm.checker_summary, 'good', small=True)}" if vm.checker_summary else ""),
                    unsafe_allow_html=True)
        if vm.fallback_reason and draft is None and vm.fallback_reason != "no model draft":
            st.caption(f"Fallback: {vm.fallback_reason}")
        result = results[pin]
        st.info(f"**Deterministic summary:** {result.outcome.value} · Development Ease "
                f"{result.ease.display if result.ease else 'n/a'} · Evidence {result.coverage_display}")
        render_claims(vm)
        for n in vm.notes:
            st.caption(n)


# --------------------------------------------------------------------------
# View 3: compare
# --------------------------------------------------------------------------


def render_compare(snapshot, results, cfg) -> None:
    st.subheader("Compare two parcels")
    st.caption("Side by side, same columns, no combined ranking. Scores are not compared across "
               "neighborhoods or markets.")
    options = vmod.lot_options(snapshot, results)
    labels = dict(options)
    pins = [p for p, _ in options]
    defaults = cfg.compare_default or (pins[0], pins[min(1, len(pins) - 1)])
    selected_a = st.session_state.get("cmp_pin_a", defaults[0])
    selected_b = st.session_state.get("cmp_pin_b", defaults[1])
    if selected_a not in pins:
        selected_a = defaults[0]
    if selected_b not in pins:
        selected_b = defaults[1]
    c1, c2 = st.columns(2)
    a = c1.selectbox("Parcel A", pins, index=pins.index(selected_a), format_func=lambda p: labels[p],
                     key="cmp_select_a", on_change=on_compare_select, args=("a",))
    b = c2.selectbox("Parcel B", pins, index=pins.index(selected_b), format_func=lambda p: labels[p],
                     key="cmp_select_b", on_change=on_compare_select, args=("b",))
    if not a or not b:
        return
    cols = vmod.compare_columns(snapshot, results, [a, b])
    for col, (label, rows), pin in zip(st.columns(2), cols.items(), (a, b)):
        with col, st.container(border=True):
            r = results[pin]
            st.markdown(f"#### {esc(label)}")
            st.markdown(badge(rows["Outcome"], text.OUTCOME_TONE[r.outcome]), unsafe_allow_html=True)
            for row in vmod.COMPARE_ROWS[1:]:
                st.markdown(f"<div class='ll-row'><span class='ll-label'>{esc(row)}</span><br>"
                            f"{esc(rows[row])}</div>", unsafe_allow_html=True)
            st.button("Open packet", key=f"open_{pin}_{'a' if pin == a else 'b'}",
                      on_click=on_hero, args=(pin,))
    st.info(f"**What explains the difference:** {vmod.difference_line(snapshot, results, a, b)}",
            icon=":material/compare_arrows:")


# --------------------------------------------------------------------------
# View 4: integrity
# --------------------------------------------------------------------------


def render_integrity(snapshot, results, cfg) -> None:
    st.subheader("Integrity: how LotLine keeps itself honest")
    st.markdown("**The engine decides; Claude assembles; the checker enforces.** Scores, outcomes, "
                "conflicts, prose atoms and next checks come from deterministic rules. Claude may "
                "select and order approved claim IDs, but it cannot submit prose or alter citations. "
                "The checker verifies the assembled memo and any failure shows the deterministic fallback.")

    with st.container(border=True):
        st.markdown("#### Claim checker and red-team cases")
        outcome, err = get_cases()
        summary = memo.summarize_cases(outcome) if outcome is not None else None
        if summary is not None:
            passed, total, rows = summary
            tone = "good" if passed == total else "critical"
            st.markdown(badge(f"{passed}/{total} cases passed · no network needed", tone), unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.caption("Live case results load here when the claim checker is available "
                       f"({err or 'unrecognized result'}). Expected behavior, from the build contract:")
            st.dataframe(pd.DataFrame(text.CONTRACT_CASES, columns=["Case", "Expected behavior"]),
                         hide_index=True, use_container_width=True)

    with st.container(border=True):
        st.markdown("#### Red-team: synthetic drafts run live through the checker")
        st.caption("SYNTHETIC red-team inputs (not source data). Each runs through the same guarded memo "
                   "pipeline; one violation rejects the whole draft.")
        rt, rt_err = get_red_team()
        if rt_err:
            st.caption(f"Red-team runner unavailable ({rt_err}).")
        for case in rt:
            st.markdown(badge(("PASS · " if case.passed else "FAIL · ") + case.title,
                              "good" if case.passed else "critical", small=True), unsafe_allow_html=True)
            for line in case.lines:
                st.markdown(f"<div class='ll-row'>{esc(line)}</div>", unsafe_allow_html=True)
            if case.violations:
                st.dataframe(pd.DataFrame([{"Rule": v.rule, "Message": v.message} for v in case.violations]),
                             hide_index=True, use_container_width=True)

    left, right = st.columns(2)
    with left, st.container(border=True):
        st.markdown("#### What is real, derived, approximate, synthetic")
        for key, desc in text.EVIDENCE_CLASS_PLAIN.items():
            st.markdown(f"- {desc}")
        counts = vmod.evidence_class_counts(results, cfg.parcels.values())
        if counts:
            st.caption("Facts behind the demo packets by class: "
                       + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    with right, st.container(border=True):
        st.markdown("#### Known limits (v1)")
        applicable = {d: rule for d, rule in snapshot.rules.items() if rule.dimensions_applicable}
        encoded = sorted(d for d, rule in applicable.items() if rule.dimensions_encoded)
        unencoded = sorted(d for d, rule in applicable.items() if not rule.dimensions_encoded)
        rule_limit = (f"- Zoning dimensions encoded for **{len(encoded)} of {len(applicable)}** applicable "
                      f"districts; not encoded: **{', '.join(unencoded) if unencoded else 'none'}**.\n")
        st.markdown(
            "- Screens **vacant** advertised lots only; structures are routed out.\n"
            + rule_limit +
            "- Base setbacks only; contextual setbacks (Ch. 925) not evaluated.\n"
            "- Screening map layers flag where to look; not geotechnical or flood determinations.\n"
            "- Utilities, legal access, title, market demand and appraisal not established.\n"
            "- Frozen snapshot: sale status can change by payment or court order."
        )

    st.markdown("#### Data sources and snapshot dates")
    st.dataframe(pd.DataFrame(vmod.source_rows(snapshot)), hide_index=True, use_container_width=True)
    with st.expander("Glossary"):
        for term, gloss in text.GLOSSARY:
            st.markdown(f"**{term}.** {gloss}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

st.markdown(CSS, unsafe_allow_html=True)
SNAPSHOT = get_snapshot()
RESULTS = get_results(date.today())
CONFIG = get_config()
init_state(CONFIG)

render_header(SNAPSHOT, RESULTS)
st.radio("View", VIEWS, key="view", horizontal=True, label_visibility="collapsed")

VIEW = st.session_state.view
if VIEW == "Sale pipeline":
    render_pipeline(SNAPSHOT, RESULTS)
elif VIEW == "Parcel packet":
    render_packet(SNAPSHOT, RESULTS, CONFIG)
elif VIEW == "Compare":
    render_compare(SNAPSHOT, RESULTS, CONFIG)
else:
    render_integrity(SNAPSHOT, RESULTS, CONFIG)
