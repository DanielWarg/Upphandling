"""Procurements page — Kanban + Sök & Filter + Feedback in tabs, with detail dialog."""

import html as html_lib

import streamlit as st
import pandas as pd

import json

from db import (
    get_all_procurements, search_procurements, get_procurement,
    get_stats, get_analysis, save_label, get_label, get_all_labels, get_label_stats,
    get_pipeline_item, ensure_pipeline_entry, add_procurement_note, get_procurement_notes,
    STAGE_LABELS,
)


# ---------------------------------------------------------------------------
# Helpers (same style as Fas1)
# ---------------------------------------------------------------------------
def esc(s: str) -> str:
    return html_lib.escape(str(s)) if s else ""


def badge_cls(score: int) -> str:
    if score >= 60: return "badge-h"
    if score >= 30: return "badge-m"
    return "badge-l"


def card_cls(score: int) -> str:
    if score >= 60: return "card-high"
    if score >= 30: return "card-med"
    return "card-low"


def bar_color(score: int) -> str:
    if score >= 60: return "var(--orange)"
    if score >= 30: return "var(--yellow)"
    return "#3f3f46"


def fmt_value(val, cur) -> str:
    if not val:
        return ""
    try:
        v = float(val)
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M {cur or 'SEK'}"
        if v >= 1_000:
            return f"{v/1_000:.0f}k {cur or 'SEK'}"
        return f"{v:.0f} {cur or 'SEK'}"
    except (ValueError, TypeError):
        return ""


# ---------------------------------------------------------------------------
# Detail dialog (same as Fas1)
# ---------------------------------------------------------------------------
@st.dialog("Upphandling", width="large")
def show_procurement_dialog(proc_id: int):
    """Native Streamlit dialog with details, feedback and AI analysis."""
    current_user = st.session_state["current_user"]
    proc = get_procurement(proc_id)
    if not proc:
        st.error("Upphandlingen hittades inte.")
        return

    s = proc.get("score") or 0
    bc = bar_color(s)
    value_str = fmt_value(proc.get("estimated_value"), proc.get("currency")) or "Ej angivet"
    url_html = (
        f'<a href="{esc(proc["url"])}" target="_blank">{esc(proc["url"])}</a>'
        if proc.get("url")
        else '<span style="color:var(--text-3)">Ej tillgänglig</span>'
    )

    st.markdown(f"""
    <div class="dp">
        <div class="dp-title">{esc(proc.get("title", ""))}</div>
        <div style="margin:12px 0 16px;display:flex;align-items:center;gap:8px">
            <span class="tag tag-src">{esc((proc.get("source") or "").upper())}</span>
            <span class="badge {badge_cls(s)}">{s}/100</span>
        </div>
        <div class="score-track"><div class="score-fill" style="width:{s}%;background:{bc}"></div></div>
        <div style="font-size:11px;color:var(--text-2);margin:6px 0 18px">{esc(proc.get("score_rationale") or "Ej scorad")}</div>
        <div class="dp-row"><div class="dp-lbl">Köpare</div><div class="dp-val">{esc(proc.get("buyer") or "Okänd")}</div></div>
        <div class="dp-row"><div class="dp-lbl">Geografi</div><div class="dp-val">{esc(proc.get("geography") or "Ej angiven")}</div></div>
        <div class="dp-row"><div class="dp-lbl">CPV-koder</div><div class="dp-val">{esc(proc.get("cpv_codes") or "Ej angivet")}</div></div>
        <div class="dp-row"><div class="dp-lbl">Förfarandetyp</div><div class="dp-val">{esc(proc.get("procedure_type") or "Ej angiven")}</div></div>
        <div class="dp-row"><div class="dp-lbl">Publicerad</div><div class="dp-val">{esc(proc.get("published_date") or "Okänt")}</div></div>
        <div class="dp-row"><div class="dp-lbl">Deadline</div><div class="dp-val">{esc(proc.get("deadline") or "Ej angiven")}</div></div>
        <div class="dp-row"><div class="dp-lbl">Uppskattat värde</div><div class="dp-val">{value_str}</div></div>
        <div class="dp-row" style="border-bottom:none"><div class="dp-lbl">Länk</div><div class="dp-val">{url_html}</div></div>
    </div>
    """, unsafe_allow_html=True)

    # --- Score Breakdown ---
    raw_breakdown = proc.get("score_breakdown")
    if raw_breakdown:
        try:
            bd = json.loads(raw_breakdown) if isinstance(raw_breakdown, str) else raw_breakdown
        except (json.JSONDecodeError, TypeError):
            bd = None
        if bd:
            with st.expander("Poanganalys", expanded=False):
                gate_color = "#4ade80" if bd.get("gate_passed") else "#f87171"
                gate_label = "Passerad" if bd.get("gate_passed") else "Blockerad"
                st.markdown(
                    f'<div style="font-size:12px;margin-bottom:8px">'
                    f'<span style="color:{gate_color};font-weight:700">Gate: {gate_label}</span>'
                    f'<span style="color:var(--text-2);margin-left:8px">{esc(bd.get("gate_reason", ""))}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                kw_matches = bd.get("keyword_matches", [])
                if kw_matches:
                    kw_html = "".join(
                        f'<span style="display:inline-block;padding:2px 8px;margin:2px 4px 2px 0;'
                        f'background:var(--orange-dim);border:1px solid rgba(249,115,22,0.2);'
                        f'border-radius:4px;font-size:11px;color:var(--orange-light)">'
                        f'{esc(m["keyword"])} <span style="font-weight:700">+{m["weight"]}</span></span>'
                        for m in kw_matches
                    )
                    st.markdown(
                        f'<div style="margin-bottom:8px">'
                        f'<div style="font-size:11px;font-weight:600;color:var(--text-2);margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px">Nyckelord</div>'
                        f'{kw_html}</div>',
                        unsafe_allow_html=True,
                    )

                cpv_matches = bd.get("cpv_matches", [])
                if cpv_matches:
                    cpv_html = "".join(
                        f'<span style="display:inline-block;padding:2px 8px;margin:2px 4px 2px 0;'
                        f'background:rgba(96,165,250,0.1);border:1px solid rgba(96,165,250,0.2);'
                        f'border-radius:4px;font-size:11px;color:#60a5fa">'
                        f'{esc(m["code"])} <span style="font-weight:700">+{m["bonus"]}</span></span>'
                        for m in cpv_matches
                    )
                    st.markdown(
                        f'<div style="margin-bottom:8px">'
                        f'<div style="font-size:11px;font-weight:600;color:var(--text-2);margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px">CPV-koder</div>'
                        f'{cpv_html}</div>',
                        unsafe_allow_html=True,
                    )

                buyer_bonus = bd.get("buyer_bonus", 0)
                if buyer_bonus:
                    st.markdown(
                        f'<div style="font-size:12px;color:var(--text-1);margin-bottom:4px">'
                        f'Offentlig kopare: <span style="font-weight:700;color:var(--orange-light)">+{buyer_bonus}</span></div>',
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    f'<div style="font-size:14px;font-weight:700;color:var(--text-0);margin-top:8px;padding-top:8px;border-top:1px solid var(--border-subtle)">'
                    f'Totalpoang: {bd.get("total", 0)}/100</div>',
                    unsafe_allow_html=True,
                )

    # --- Pipeline status ---
    pipeline_item = get_pipeline_item(proc_id)
    if pipeline_item:
        stage_label = STAGE_LABELS.get(pipeline_item.get("stage", ""), "")
        assigned = pipeline_item.get("assigned_to") or "Ej tilldelad"
        st.markdown(
            f'<div style="padding:10px 14px;margin:12px 0;background:var(--bg-2);border:1px solid var(--border);border-radius:var(--r-sm)">'
            f'<span style="font-weight:700;font-size:12px;color:var(--orange)">Pipeline: {stage_label}</span>'
            f'<span style="font-size:12px;color:var(--text-1);margin-left:12px">Tilldelad: {esc(assigned)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # --- AI Relevance ---
    ai_rel = proc.get("ai_relevance")
    ai_reason = proc.get("ai_relevance_reasoning") or ""
    if ai_rel:
        rel_color = "#4ade80" if ai_rel == "relevant" else "#f87171"
        rel_label = "Relevant" if ai_rel == "relevant" else "Inte relevant"
        st.markdown(
            f'<div style="padding:10px 14px;margin:12px 0;background:var(--bg-2);border:1px solid var(--border);border-radius:var(--r-sm);'
            f'border-left:3px solid {rel_color}">'
            f'<span style="font-weight:700;font-size:12px;color:{rel_color}">AI: {rel_label}</span>'
            f'<span style="font-size:12px;color:var(--text-1);margin-left:8px"> — {esc(ai_reason)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if proc.get("description"):
        with st.expander("Beskrivning", expanded=False):
            st.markdown(proc["description"])

    # --- Add to pipeline ---
    if not pipeline_item:
        if st.button("Lägg till i pipeline", key=f"add_pipe_{proc_id}"):
            ensure_pipeline_entry(proc_id, assigned_to=current_user["username"])
            st.rerun()

    # --- Notes ---
    st.markdown("---")
    st.markdown(
        '<div style="font-weight:700;font-size:14px;color:var(--text-0);margin-bottom:8px">Anteckningar</div>',
        unsafe_allow_html=True,
    )
    notes = get_procurement_notes(proc_id)
    for note in notes[:10]:
        st.markdown(
            f'<div style="font-size:12px;color:var(--text-1);padding:4px 0;border-bottom:1px solid var(--border-subtle)">'
            f'<strong>{esc(note["user_username"])}</strong> ({note["created_at"][:10]}): '
            f'{esc(note["content"])}</div>',
            unsafe_allow_html=True,
        )
    new_note = st.text_input("Ny anteckning", key=f"dlg_note_{proc_id}", placeholder="Skriv en anteckning...")
    if st.button("Spara", key=f"dlg_save_note_{proc_id}"):
        if new_note.strip():
            add_procurement_note(proc_id, current_user["username"], new_note.strip())
            st.rerun()

    # --- Feedback ---
    st.markdown("---")
    st.markdown(
        '<div style="font-weight:700;font-size:14px;color:var(--text-0);margin-bottom:8px">Feedback</div>',
        unsafe_allow_html=True,
    )

    fb_reason = st.text_input(
        "Anledning", key=f"dlg_reason_{proc_id}",
        label_visibility="collapsed", placeholder="Anledning (valfri)",
    )
    fc1, fc2 = st.columns(2)
    with fc1:
        btn_rel = st.button("Relevant", key=f"dlg_rel_{proc_id}", use_container_width=True)
    with fc2:
        btn_irr = st.button("Inte relevant", key=f"dlg_irr_{proc_id}", use_container_width=True)

    if btn_rel:
        save_label(proc_id, "relevant", fb_reason)
    if btn_irr:
        save_label(proc_id, "irrelevant", fb_reason)

    existing_label = get_label(proc_id)
    if existing_label:
        lbl = existing_label["label"]
        lbl_color = "#4ade80" if lbl == "relevant" else "#f87171"
        lbl_text = "Relevant" if lbl == "relevant" else "Inte relevant"
        reason_text = f' — {existing_label["reason"]}' if existing_label.get("reason") else ""
        st.markdown(
            f'<div style="font-size:12px;color:{lbl_color};margin-top:4px">'
            f'Senaste: {lbl_text}{reason_text} ({existing_label["created_at"][:10]})</div>',
            unsafe_allow_html=True,
        )

    # --- AI Analysis ---
    st.markdown("---")
    st.markdown(
        '<div style="font-weight:700;font-size:14px;color:var(--text-0);margin-bottom:8px">AI Analys</div>',
        unsafe_allow_html=True,
    )

    cached = get_analysis(proc_id)

    btn_ai = st.button(
        "Analysera med AI" if not cached else "Analysera igen",
        key=f"dlg_ai_{proc_id}",
    )
    if btn_ai:
        from analyzer import analyze_procurement
        with st.spinner("Analyserar med Ollama..."):
            try:
                result = analyze_procurement(proc_id, force=bool(cached))
                if result:
                    cached = result
                else:
                    st.error("Analysen misslyckades.")
            except Exception as e:
                st.error(f"Fel: {e}")

    if cached:
        with st.expander("Kravsammanfattning", expanded=True):
            st.markdown(cached.get("kravsammanfattning") or "Ingen data.")
        with st.expander("Matchningsanalys", expanded=True):
            st.markdown(cached.get("matchningsanalys") or "Ingen data.")
        with st.expander("Prisstrategi", expanded=False):
            st.markdown(cached.get("prisstrategi") or "Ingen data.")
        with st.expander("Anbudshjälp", expanded=False):
            st.markdown(cached.get("anbudshjalp") or "Ingen data.")

        meta_parts = []
        if cached.get("model"):
            meta_parts.append(f"Modell: {cached['model']}")
        if cached.get("input_tokens"):
            meta_parts.append(f"Input: {cached['input_tokens']} tokens")
        if cached.get("output_tokens"):
            meta_parts.append(f"Output: {cached['output_tokens']} tokens")
        if cached.get("created_at"):
            meta_parts.append(f"Analyserad: {cached['created_at'][:10]}")
        if meta_parts:
            st.caption(" | ".join(meta_parts))


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------
def render_procurements():
    """Render procurements page with Kanban + Sök & Filter + Feedback tabs."""
    st.markdown(
        '<div class="topbar"><h1>Upphandlingar</h1>'
        '<p>Kanban, sök och feedback</p></div>',
        unsafe_allow_html=True,
    )

    tab_kanban, tab_search, tab_feedback = st.tabs(["Kanban", "Sök & Filter", "Feedback"])

    with tab_kanban:
        _render_kanban()

    with tab_search:
        _render_search()

    with tab_feedback:
        _render_feedback()


# ---------------------------------------------------------------------------
# Kanban tab — Fas1 3-column layout
# ---------------------------------------------------------------------------
def _render_kanban():
    """Fas1 kanban: 3 columns by score (Hög / Medel / Låg) with cards."""
    stats = get_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Totalt", stats["total"])
    c2.metric("Nya idag", stats["new_today"])
    c3.metric("Snitt score", stats["avg_score"])
    c4.metric("Hög fit (60+)", stats["high_fit"])

    all_procs = get_all_procurements()

    if not all_procs:
        st.markdown(
            '<div class="empty"><h3>Ingen data ännu</h3>'
            '<p>Kör <code>python run_scrapers.py</code> för att hämta upphandlingar.</p></div>',
            unsafe_allow_html=True,
        )
        return

    # Filter: only scored (>0) and not AI-irrelevant, sort by newest
    visible = [p for p in all_procs if (p.get("score") or 0) > 0 and p.get("ai_relevance") != "irrelevant"]
    visible.sort(key=lambda p: p.get("published_date") or "", reverse=True)
    high = [p for p in visible if (p.get("score") or 0) >= 60]
    med = [p for p in visible if 30 <= (p.get("score") or 0) < 60]
    low = [p for p in visible if 1 <= (p.get("score") or 0) < 30]

    col_h, col_m, col_l = st.columns(3)

    def _render_column(col, title: str, accent: str, items: list, max_show: int = 50):
        with col:
            st.markdown(
                f'<div style="background:var(--bg-1);border:1px solid var(--border);border-radius:var(--r);padding:14px 18px;'
                f'display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">'
                f'<span style="font-weight:700;font-size:12px;text-transform:uppercase;letter-spacing:0.8px;color:{accent}">{title}</span>'
                f'<span class="kb-count">{len(items)}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if not items:
                st.markdown(
                    '<div style="padding:24px;text-align:center;color:var(--text-3);font-size:12px">Inga upphandlingar</div>',
                    unsafe_allow_html=True,
                )
            for p in items[:max_show]:
                _s = p.get("score", 0) or 0
                _title = esc((p.get("title") or "Utan titel")[:90])
                _buyer = esc(p.get("buyer") or "")
                _source = esc((p.get("source") or "").upper())
                _published = (p.get("published_date") or "")[:10]
                _deadline = (p.get("deadline") or "")[:10]
                _desc = esc((p.get("description") or "")[:120])
                _value = fmt_value(p.get("estimated_value"), p.get("currency"))
                _label = get_label(p["id"])

                tags = f'<span class="tag tag-src">{_source}</span>'
                if _published:
                    tags += f' <span class="tag tag-geo">{_published}</span>'
                if _deadline:
                    tags += f' <span class="tag tag-dl">DL {_deadline}</span>'
                if _value:
                    tags += f' <span class="tag tag-val">{_value}</span>'

                label_indicator = ""
                if _label:
                    _lc = "#4ade80" if _label["label"] == "relevant" else "#f87171"
                    _lt = "R" if _label["label"] == "relevant" else "IR"
                    label_indicator = (
                        f'<span style="display:inline-block;padding:2px 6px;border-radius:4px;font-size:9px;'
                        f'font-weight:700;color:{_lc};border:1px solid {_lc}30;margin-left:4px">{_lt}</span>'
                    )

                cached_ai = get_analysis(p["id"])
                ai_indicator = ""
                if cached_ai:
                    ai_indicator = (
                        '<span style="display:inline-block;padding:2px 6px;border-radius:4px;font-size:9px;'
                        'font-weight:700;color:#60a5fa;border:1px solid #60a5fa30;margin-left:4px">AI</span>'
                    )

                _ai_rel = p.get("ai_relevance")
                ai_rel_indicator = ""
                if _ai_rel == "irrelevant":
                    ai_rel_indicator = (
                        '<span style="display:inline-block;padding:2px 6px;border-radius:4px;font-size:9px;'
                        'font-weight:700;color:#f87171;border:1px solid #f8717130;margin-left:4px">IR-AI</span>'
                    )

                st.markdown(
                    f'<div class="card {card_cls(_s)}" style="margin-bottom:2px">'
                    f'  <div class="card-title">{_title}</div>'
                    f'  {"<div class=card-buyer>" + _buyer + "</div>" if _buyer else ""}'
                    f'  {"<div class=card-desc>" + _desc + "</div>" if _desc else ""}'
                    f'  <div class="card-foot">'
                    f'    <div>{tags}</div>'
                    f'    <div><span class="badge {badge_cls(_s)}">{_s}</span>{label_indicator}{ai_indicator}{ai_rel_indicator}</div>'
                    f'  </div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Visa", key=f"kb_{p['id']}", use_container_width=True):
                    show_procurement_dialog(p["id"])

            if len(items) > max_show:
                st.caption(f"+{len(items) - max_show} till")

    _render_column(col_h, "Hög prioritet", "#f97316", high)
    _render_column(col_m, "Medel", "#eab308", med)
    _render_column(col_l, "Låg", "#52525b", low, max_show=20)


# ---------------------------------------------------------------------------
# Sök & Filter tab
# ---------------------------------------------------------------------------
def _render_search():
    """Search and filter procurements."""
    current_user = st.session_state["current_user"]

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        query = st.text_input("Fritext", placeholder="t.ex. realtidssystem")
    with c2:
        source_filter = st.selectbox("Källa", ["Alla", "ted", "mercell", "kommers", "eavrop"])
    with c3:
        geography_filter = st.text_input("Region", placeholder="t.ex. Stockholm")
    with c4:
        score_range = st.slider("Score", 0, 100, (0, 100))
    with c5:
        ai_filter = st.selectbox("AI Relevans", ["Alla", "Relevant", "Inte relevant", "Ej bedömd"])

    source_val = "" if source_filter == "Alla" else source_filter
    ai_val_map = {"Alla": "", "Relevant": "relevant", "Inte relevant": "irrelevant", "Ej bedömd": "unassessed"}
    ai_val = ai_val_map[ai_filter]
    results = search_procurements(
        query=query, source=source_val,
        min_score=score_range[0], max_score=score_range[1],
        geography=geography_filter,
        ai_relevance=ai_val,
    )

    st.markdown(f"**{len(results)}** resultat")

    if results:
        df = pd.DataFrame(results)[["id", "title", "buyer", "score", "source", "published_date", "deadline", "geography"]]
        df = df.rename(columns={"published_date": "Publicerad", "deadline": "Deadline"})
        df = df.sort_values("Publicerad", ascending=False, na_position="last")
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Quick add to pipeline
        st.markdown("---")
        sel_id = st.number_input("Upphandlings-ID att visa/lägga till i pipeline", min_value=1, step=1, key="search_proc_id")
        sc1, sc2 = st.columns(2)
        with sc1:
            if st.button("Visa detaljer", key="search_show"):
                show_procurement_dialog(int(sel_id))
        with sc2:
            if st.button("Lägg till i pipeline", key="search_add_pipe"):
                ensure_pipeline_entry(int(sel_id), assigned_to=current_user["username"])
                st.success("Tillagd i pipeline!")
    else:
        st.markdown(
            '<div class="empty"><h3>Inga resultat</h3><p>Prova att ändra filtren.</p></div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Feedback tab
# ---------------------------------------------------------------------------
def _render_feedback():
    """Feedback history and pattern analysis."""
    label_stats = get_label_stats()
    fc1, fc2, fc3 = st.columns(3)
    fc1.metric("Totalt bedömda", label_stats["total"])
    fc2.metric("Relevanta", label_stats["relevant"])
    fc3.metric("Inte relevanta", label_stats["irrelevant"])

    all_labels = get_all_labels()
    if all_labels:
        st.markdown("### Senaste feedback")
        for lb in all_labels[:50]:
            lbl = lb["label"]
            color = "#4ade80" if lbl == "relevant" else "#f87171"
            icon = "+" if lbl == "relevant" else "-"
            reason = f' — {lb["reason"]}' if lb.get("reason") else ""
            score = lb.get("score", 0) or 0
            st.markdown(
                f'<div style="display:flex;align-items:flex-start;gap:12px;padding:10px 14px;margin-bottom:6px;'
                f'background:var(--bg-2);border:1px solid var(--border);border-radius:var(--r-sm)">'
                f'<span style="color:{color};font-weight:800;font-size:16px;min-width:16px">{icon}</span>'
                f'<div style="flex:1">'
                f'<div style="font-size:13px;font-weight:600;color:var(--text-0)">{esc(lb.get("title", ""))}</div>'
                f'<div style="font-size:11px;color:var(--text-2);margin-top:2px">'
                f'{esc(lb.get("buyer", ""))} | Score: {score} | {lb["created_at"][:10]}{reason}</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Show top irrelevant patterns
        irrelevant = [lb for lb in all_labels if lb["label"] == "irrelevant"]
        if irrelevant:
            st.markdown("### Mönster i felklassade")
            irr_buyers = {}
            irr_reasons = {}
            for lb in irrelevant:
                buyer = lb.get("buyer") or "Okänd"
                irr_buyers[buyer] = irr_buyers.get(buyer, 0) + 1
                if lb.get("reason"):
                    irr_reasons[lb["reason"]] = irr_reasons.get(lb["reason"], 0) + 1

            if irr_buyers:
                st.markdown("**Köpare markerade som irrelevanta:**")
                sorted_buyers = sorted(irr_buyers.items(), key=lambda x: x[1], reverse=True)
                for buyer, count in sorted_buyers[:10]:
                    st.markdown(
                        f'<div style="font-size:12px;color:var(--text-1);padding:2px 0">'
                        f'{esc(buyer)}: <span style="color:#f87171">{count}x</span></div>',
                        unsafe_allow_html=True,
                    )

            if irr_reasons:
                st.markdown("**Vanligaste anledningar:**")
                sorted_reasons = sorted(irr_reasons.items(), key=lambda x: x[1], reverse=True)
                for reason, count in sorted_reasons[:10]:
                    st.markdown(
                        f'<div style="font-size:12px;color:var(--text-1);padding:2px 0">'
                        f'{esc(reason)}: <span style="color:#f87171">{count}x</span></div>',
                        unsafe_allow_html=True,
                    )
    else:
        st.markdown(
            '<div class="empty"><h3>Ingen feedback ännu</h3>'
            '<p>Använd Relevant/Inte relevant-knapparna på upphandlingssidan för att markera upphandlingar.</p></div>',
            unsafe_allow_html=True,
        )
