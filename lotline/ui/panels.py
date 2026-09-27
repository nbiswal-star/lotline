"""Streamlit renderers for the AI reader panels, cost worksheet, task tickets, freshness
check and parcel map. They render view models only; nothing here decides anything."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from lotline import costs, refresh
from lotline.models import ScreeningResult, Snapshot
from lotline.ui import ai_panels as ai
from lotline.ui import geo, tickets

AI_CSS = """
<style>
.ll-ai-head { display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap; margin-bottom:0.2rem; }
.ll-ai-head h4 { margin:0; padding:0; }
.ll-ai-mark { font-size:0.72rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase;
  color:#5B3FA8; background:#F1ECFB; border:1px solid #D9CCF3; border-radius:999px; padding:0.1rem 0.55rem; }
.ll-ev { border:1px solid #E3E7EC; border-radius:10px; padding:0.6rem 0.8rem; margin:0.45rem 0; background:#FCFCFD; }
.ll-ev .meta { font-size:0.8rem; color:#5B6573; margin-bottom:0.25rem; }
.ll-ev .meta code { font-size:0.78rem; }
.ll-quote { border-left:3px solid #8C6BD8; padding:0.2rem 0 0.2rem 0.7rem; margin:0.3rem 0; font-size:0.95rem; color:#1B2430; }
.ll-quote mark { background:#FFF1B8; padding:0 0.1rem; border-radius:2px; }
.ll-tag { display:inline-block; font-size:0.74rem; font-weight:600; border-radius:4px; padding:0.05rem 0.4rem;
  margin:0 0.25rem 0.15rem 0; border:1px solid #D3D9E0; background:#EEF1F4; color:#3D4652; }
.ll-tag.ind { background:#EAF2FD; color:#1F4E8C; border-color:#BCD3F2; }
.ll-tag.cur { background:#F6F6F7; }
.ll-tag.old { background:#FFF4DF; color:#865100; border-color:#F0CF94; }
.ll-ok { display:inline-block; font-size:0.76rem; font-weight:600; color:#1D6A33; background:#E7F4EA;
  border:1px solid #B5DEC1; border-radius:999px; padding:0.05rem 0.5rem; }
.ll-legend { font-size:0.85rem; line-height:1.9; }
.ll-dot { display:inline-block; width:0.8rem; height:0.8rem; border-radius:50%; margin-right:0.4rem; vertical-align:-0.1rem; border:2px solid; }
.ll-ans { font-size:0.95rem; margin:0.2rem 0 0.35rem 0; }
</style>
"""


def esc(s: object) -> str:
    return html.escape(str(s))


def tag(label: str, cls: str = "") -> str:
    return f'<span class="ll-tag {cls}">{esc(label)}</span>'


def chip(label: str) -> str:
    return f'<span class="ll-chip">{esc(label)}</span>'


def ok(label: str) -> str:
    return f'<span class="ll-ok">✓ {esc(label)}</span>'


def ai_head(title: str, mark: str = "Claude reads · code verifies") -> None:
    st.markdown(f"<div class='ll-ai-head'><h4>{esc(title)}</h4><span class='ll-ai-mark'>{esc(mark)}</span></div>",
                unsafe_allow_html=True)


# --------------------------------------------------------------------------
# AI record reader
# --------------------------------------------------------------------------


def evidence_state(pin: str, snapshot: Snapshot) -> ai.EvidenceVM | None:
    """Clicked result if any, else a cached re-verified digest (looked up once per session)."""
    ss = st.session_state
    clicked = ss.get(f"evidence_{pin}")
    if clicked is not None:
        return clicked
    key = f"evidence_cached_{pin}"
    if key not in ss:
        ss[key] = ai.cached_evidence(pin, snapshot)
    return ss[key]


def render_evidence(snapshot: Snapshot, pin: str, *, prominent: bool) -> None:
    if not ai.evidence_available():
        return
    with st.container(border=True):
        ai_head("AI record reader" if not prominent else "AI record reader: what the enforcement record says")
        st.caption(ai.HUMAN_RESOLVER)
        vm = evidence_state(pin, snapshot)
        label = "Read the enforcement record with Claude" if vm is None or not vm.verified else \
            "Re-read the enforcement record with Claude"
        if st.button(label, key=f"btn_evidence_{pin}", type="primary" if prominent else "secondary"):
            with st.spinner("Claude is reading the enforcement record; code checks every quote against the source text..."):
                st.session_state[f"evidence_{pin}"] = vm = ai.read_evidence(pin, snapshot)
        if vm is None:
            st.caption("Claude quotes the violation and condemned-property records for this parcel; code "
                       "keeps only quotes that appear verbatim in the source text.")
            return
        render_evidence_vm(vm)
        render_ai_baseline_comparison(vm, ai.keyword_hits(pin, snapshot), expanded=prominent)


def _highlight(quote: str) -> str:
    return f"<mark>{esc(quote)}</mark>"


def render_evidence_vm(vm: ai.EvidenceVM) -> None:
    if vm.status == "no_records":
        st.markdown("No enforcement record text is on file for this parcel in the snapshot.")
        return
    if vm.status == "unavailable":
        st.markdown(f"<div class='ll-muted'>{esc(ai.UNAVAILABLE_READER)}"
                    + (f" ({esc(vm.reason)})" if vm.reason else "") + "</div>", unsafe_allow_html=True)
        return
    if vm.status == "rejected":
        st.warning(f"Claude's reading failed verification{f' ({vm.reason})' if vm.reason else ''}; nothing "
                   "from it is shown. Raw record text is in Provenance.", icon=":material/block:")
        st.caption(vm.counter)
        return
    head = [ok("every quote verified against source text"), f"<span class='ll-muted'>{esc(vm.counter)}</span>"]
    if vm.timing:
        head.append(f"<span class='ll-muted'>· {esc(vm.timing)}</span>")
    elif vm.cached:
        head.append("<span class='ll-muted'>· cached, re-verified now</span>")
    st.markdown(" ".join(head), unsafe_allow_html=True)
    for it in vm.items:
        tags = []
        if it.indicates:
            tags.append(tag(f"indicates: {it.indicates}", "ind"))
        if it.currency:
            tags.append(tag(it.currency, "old" if "older dated" in it.currency else "cur"))
        meta = (f"<code>{esc(it.record_id)}</code> · {esc(it.date)} · {esc(it.source)}"
                + (f" · field <code>{esc(it.field)}</code>" if it.field else ""))
        corro = (f"<div class='ll-muted'>Permit corroboration: {esc(it.corroboration)}</div>"
                 if it.corroboration else "")
        rel = f"<div class='ll-muted'>{esc(it.relevance)}</div>" if it.relevance else ""
        st.markdown(
            f"<div class='ll-ev'><div class='meta'>{meta}</div>"
            f"<div class='ll-quote'>The record says: “{_highlight(it.quote)}”</div>"
            f"{''.join(tags)} {ok('quote verified against source text')}{corro}{rel}</div>",
            unsafe_allow_html=True)
    if vm.resolver_note:
        st.info(f"**For the resolver:** {vm.resolver_note}", icon=":material/person_search:")
    extra = [f"Model: {vm.model}" if vm.model else "", f"Read: {vm.created_at}" if vm.created_at else ""]
    extra = [e for e in extra if e]
    if extra:
        st.caption(" · ".join(extra))


def render_ai_baseline_comparison(vm: ai.EvidenceVM, keyword_ids: list[str], *, expanded: bool) -> None:
    """Show the honest no-AI counterfactual without loading evaluation answer labels."""
    if not vm.verified:
        return
    ai_ids = sorted({it.record_id for it in vm.items})
    with st.expander("AI vs no-AI evidence triage", expanded=expanded):
        st.caption("Same frozen records, two retrieval methods. This compares review workload, not parcel outcomes: "
                   "the deterministic engine produces the same decision either way.")
        rows = [
            {"Method": "Keyword/lexicon scan (no AI)",
             "Records surfaced": len(keyword_ids),
             "What the analyst receives": "matching record IDs; open and interpret each record manually"},
            {"Method": "Claude + code verifier",
             "Records surfaced": len(ai_ids),
             "What the analyst receives": f"{len(vm.items)} exact source quote(s), dates and cross-checks"},
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        if keyword_ids:
            st.markdown("**No-AI keyword hits:** " + " ".join(chip(x) for x in keyword_ids),
                        unsafe_allow_html=True)
        if ai_ids:
            st.markdown("**Claude records surviving verification:** " + " ".join(chip(x) for x in ai_ids),
                        unsafe_allow_html=True)
        st.caption("Retrospective record-level precision/recall against labels frozen before the live run is "
                   "reported separately in docs/validation/results.md; those labels never enter the app.")


# --------------------------------------------------------------------------
# Ask LotLine
# --------------------------------------------------------------------------


def _ask(pin: str, result: ScreeningResult, question: str) -> None:
    question = (question or "").strip()
    if question:
        st.session_state[f"ask_{pin}"] = ai.ask_question(question, result)


def _on_chip(pin: str, result: ScreeningResult, question: str) -> None:
    _ask(pin, result, question)


def render_ask(result: ScreeningResult, pin: str) -> None:
    if not ai.ask_available():
        return
    with st.container(border=True):
        ai_head("Ask LotLine", "answers from verified facts · cited")
        st.caption("Ask about this parcel. Every answer sentence cites engine fact IDs or zoning-code sections, "
                   "and code verifies each one before it is shown. It does not give investment advice.")
        qs = ai.suggested_questions()
        if qs:
            cols = st.columns(min(len(qs), 3))
            for i, q in enumerate(qs):
                cols[i % len(cols)].button(q, key=f"askchip_{pin}_{i}", on_click=_on_chip,
                                           args=(pin, result, q), use_container_width=True)
        with st.form(key=f"askform_{pin}", clear_on_submit=True, border=False):
            c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
            q = c1.text_input("Your question", key=f"askq_{pin}", placeholder="e.g. Why is this lot deferred?")
            asked = c2.form_submit_button("Ask", use_container_width=True)
        if asked and q:
            with st.spinner("Composing an answer from verified facts; code checks every sentence..."):
                _ask(pin, result, q)
        ans = st.session_state.get(f"ask_{pin}")
        if ans is not None:
            render_answer(ans, result)


def render_answer(a: ai.AnswerVM, result: ScreeningResult) -> None:
    with st.chat_message("user"):
        st.markdown(esc(a.question))
    with st.chat_message("assistant", avatar=":material/fact_check:"):
        head = []
        if a.frame:
            head.append(tag(a.frame, "ind"))
        if a.status == "answered":
            head.append(ok("every sentence verified"))
            st.markdown(" ".join(head), unsafe_allow_html=True)
            for s in a.sentences:
                chips = "".join(chip(f) for f in s.fact_ids) + "".join(chip(f"§ {c}" if not str(c).startswith("§") else c)
                                                                         for c in s.code_refs)
                st.markdown(f"<div class='ll-ans'>{esc(s.text)}<br>{chips}</div>", unsafe_allow_html=True)
        elif a.status == "rejected":
            rules = ", ".join(a.violations) or (a.reason or "verification failed")
            st.markdown(" ".join(head), unsafe_allow_html=True)
            st.warning(f"Claude's answer failed verification (rules: {rules}); showing the engine packet instead.",
                       icon=":material/block:")
            nc = result.next_checks[0] if result.next_checks else None
            st.markdown(f"**Engine:** {esc(result.outcome.value)} · Development Ease "
                        f"{esc(result.ease.display if result.ease else 'n/a')}"
                        + (f" · principal barrier: {esc(result.barriers[0])}" if result.barriers else "")
                        + (f" · next check: {esc(nc.check)} ({esc(nc.owner)})" if nc else ""))
        elif a.status == "declined":
            st.markdown(" ".join(head), unsafe_allow_html=True)
            st.markdown(f"LotLine declines this question: {esc(a.reason or 'outside decision support')}")
            for s in a.sentences:
                st.markdown(f"<div class='ll-ans'>{esc(s.text)}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<span class='ll-muted'>Ask LotLine unavailable (no API key / offline)"
                        + (f": {esc(a.reason)}" if a.reason else "")
                        + ". Every answer is already in the packet above, from the engine.</span>",
                        unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Variance precedents + relief paths (inside the Zoning tile)
# --------------------------------------------------------------------------


def render_precedents(result: ScreeningResult) -> None:
    got = ai.precedents(result)
    paths = ai.relief_paths(result)
    if got is None and paths is None:
        return
    cards, counts = got if got is not None else ([], None)
    title = "Relief paths & variance precedents"
    if counts:
        title += f" · {counts}"
    with st.expander(title, expanded=bool(cards or paths)):
        if paths:
            st.markdown("**Possible relief paths**")
            st.caption(ai.RELIEF_BANNER)
            for p in paths:
                st.markdown(f"<div class='ll-row'>{esc(p.trigger)} → <b>{esc(p.path)}</b>"
                            + (f" {chip(p.code_ref)}" if p.code_ref else "") + "</div>", unsafe_allow_html=True)
                if p.code_quote:
                    st.markdown(f"<div class='ll-quote'>“{esc(p.code_quote)}” {ok('code quote verified')}</div>",
                                unsafe_allow_html=True)
                bits = "".join(chip(c) for c in p.precedents)
                if bits or p.counts:
                    st.markdown(f"<div class='ll-muted'>Precedents: {bits}"
                                + (f" · {esc(p.counts)}" if p.counts else "") + "</div>", unsafe_allow_html=True)
        if got is not None:
            st.markdown("**Variance precedents** · same district family, same relief type")
            if not cards:
                st.caption("No verified Zoning Board decision matched this parcel's district family and relief type.")
            for c in cards:
                reliefs = " ".join(tag(f"{r.kind}: {r.outcome}", "ind" if "grant" in r.outcome.lower() else "old")
                                   for r in c.reliefs)
                quote = c.rationale_quote or next((r.quote for r in c.reliefs if r.quote), "")
                link = f" · <a href='{esc(c.source_url)}' target='_blank'>decision</a>" if c.source_url else ""
                st.markdown(
                    f"<div class='ll-ev'><div class='meta'><b>{esc(c.case_number)}</b> · {esc(c.address)} · "
                    f"{esc(c.district)} · decided {esc(c.decision_date)}{link}</div>{reliefs}"
                    + (f"<div class='ll-quote'>“{esc(quote)}”</div>" if quote else "")
                    + f"{ok('quotes verified')} <span class='ll-muted'>{esc(ai.PRECEDENT_NOTE)}"
                    + (f" Matched: {esc(c.match_note)}" if c.match_note else "") + "</span></div>",
                    unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Cost worksheet
# --------------------------------------------------------------------------


def render_costs(snapshot: Snapshot, result: ScreeningResult) -> None:
    ws = costs.worksheet(snapshot, result)
    with st.expander("Pre-development cost worksheet (pro forma inputs)", expanded=False):
        if ws.blocked:
            st.error(costs.BLOCKED_BANNER, icon=":material/report:")
        st.caption(ws.disclaimer + " Cited defaults show their source; blank rows are yours to fill.")
        values: list[float | None] = []
        for row in ws.rows:
            c1, c2 = st.columns([3, 2], vertical_alignment="center")
            with c1:
                cite = esc(row.basis)
                if row.fact_ids:
                    cite += " · " + " ".join(chip(f) for f in row.fact_ids)
                src = (f" · <a href='{esc(row.source_url)}' target='_blank'>source</a>"
                       if row.source_url and row.cited else "")
                st.markdown(f"<div class='ll-row'><b>{esc(row.label)}</b><br><span class='ll-muted'>"
                            f"{cite}{src}</span></div>", unsafe_allow_html=True)
                if row.note:
                    st.caption(row.note)
            with c2:
                v = st.number_input(row.label, min_value=0.0, value=row.default_usd, step=100.0, format="%.2f",
                                    key=f"cost_{result.pin}_{row.key}", label_visibility="collapsed",
                                    placeholder=costs.ENTER_ESTIMATE)
                values.append(v)
        st.markdown(f"**Total of filled rows:** {esc(costs.total_line(values, len(ws.rows)))}")
        for n in ws.notes:
            st.caption(n)
        for ref in ws.references:
            st.caption(f"Reference, not added: {ref.label}: ${ref.default_usd:,.0f} ({ref.source}, {ref.source_date}). "
                       f"{ref.note or ''}")


# --------------------------------------------------------------------------
# Task tickets
# --------------------------------------------------------------------------


def render_tickets(snapshot: Snapshot, p, sale_date: str, snapshot_label: str) -> None:
    if not p.next_checks:
        return
    with st.expander("Create task ticket for a next check"):
        st.caption(tickets.TICKET_LABEL + ". A fixed template filled from the engine's check, owner and "
                   "trigger, plus any verified record quotes. No AI-written text.")
        checks = [c["Check"] for c in p.next_checks]
        choice = st.selectbox("Next check", range(len(checks)), format_func=lambda i: checks[i],
                              key=f"ticket_{p.pin}")
        ev = st.session_state.get(f"evidence_{p.pin}") or st.session_state.get(f"evidence_cached_{p.pin}")
        items = ev.items if ev is not None and ev.verified else []
        md = tickets.ticket_markdown(check=p.next_checks[choice], parcel_title=p.title, pin=p.pin,
                                     pin_short=p.pin_short, address=p.address, outcome=p.outcome_label,
                                     sale_date=sale_date, snapshot_label=snapshot_label, evidence=items)
        st.code(md, language="markdown")
        st.download_button("Download ticket (Markdown)", data=md, key=f"ticket_dl_{p.pin}",
                           file_name=f"lotline-{p.pin_short.lower()}-task-{choice + 1}.md", mime="text/markdown")


# --------------------------------------------------------------------------
# Snapshot freshness
# --------------------------------------------------------------------------


def render_freshness(snapshot: Snapshot) -> None:
    with st.container(border=True):
        st.markdown("#### Snapshot freshness")
        st.caption(refresh.PIPELINE_NOTE)
        if st.button("Check live sources for changes", key="btn_refresh"):
            with st.spinner("Asking WPRDC for the live Treasury Sales records (10 s limit)..."):
                st.session_state.refresh_report = refresh.check_live(snapshot)
        rep: refresh.RefreshReport | None = st.session_state.get("refresh_report")
        if rep is None:
            st.caption("Nothing is fetched until you click. Snapshot data under data/ is never modified.")
            return
        if rep.status != "ok":
            st.warning(rep.headline, icon=":material/cloud_off:")
            st.caption(f"Checked {rep.checked_at}" + (f" ({rep.reason})" if rep.reason else ""))
            return
        tone = "good" if not rep.changes else "caution"
        st.markdown(f'<span class="ll-badge ll-{tone}">{esc(rep.headline)}</span>', unsafe_allow_html=True)
        st.caption(f"Checked {rep.checked_at}: {rep.live_count} live records vs {rep.snapshot_count} in the snapshot. "
                   "LotLine is still screening the snapshot.")
        if rep.changes:
            labels = {pin: snapshot.treasury[pin].address.split(",")[0].title()
                      for pin in snapshot.treasury}
            st.dataframe(pd.DataFrame(refresh.change_rows(rep, labels)), hide_index=True,
                         use_container_width=True)


# --------------------------------------------------------------------------
# Parcel map
# --------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def _coords() -> dict[str, tuple[float, float]]:
    return geo.load_coordinates()


def render_map(snapshot: Snapshot, results) -> None:
    try:
        import pydeck as pdk
    except Exception:  # noqa: BLE001
        return
    pts = geo.map_points(snapshot, results, _coords())
    if not pts:
        return
    rows = []
    for pt in pts:
        label, fill, line = geo.FAMILY_STYLE[pt.family]
        rows.append({"lat": pt.lat, "lon": pt.lon, "fill": fill, "line": line, "address": pt.address,
                     "outcome": pt.outcome, "ease": pt.ease,
                     "radius": 5 if pt.family in ("structure", "out") else 7})
    df = pd.DataFrame(rows)
    layer = pdk.Layer(
        "ScatterplotLayer", data=df, get_position="[lon, lat]", get_fill_color="fill",
        get_line_color="line", stroked=True, filled=True, line_width_min_pixels=1.5,
        get_radius="radius", radius_units="pixels", pickable=True,
    )
    view = pdk.ViewState(latitude=float(df.lat.mean()), longitude=float(df.lon.mean()), zoom=10.6)
    deck = pdk.Deck(layers=[layer], initial_view_state=view, map_style=None,
                    tooltip={"text": "{address}\n{outcome}\nDevelopment Ease: {ease}"})
    left, right = st.columns([3, 1])
    with left:
        st.pydeck_chart(deck, height=350)
    with right:
        counts = geo.family_counts(pts)
        items = []
        for fam, (label, fill, line) in geo.FAMILY_STYLE.items():
            bg = f"rgba({fill[0]},{fill[1]},{fill[2]},{fill[3] / 255:.2f})"
            items.append(f"<span class='ll-dot' style='background:{bg};border-color:rgb({line[0]},{line[1]},{line[2]})'>"
                         f"</span>{esc(label)} · {counts[fam]}")
        st.markdown("<div class='ll-label'>All " + str(len(pts)) + " open-data records</div>"
                    "<div class='ll-legend'>" + "<br>".join(items) + "</div>", unsafe_allow_html=True)
        st.caption("Hover a point for address, outcome and Development Ease. Locations from the WPRDC "
                   "Treasury Sales feed. The basemap needs internet; points and colors work offline.")
