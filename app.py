"""Streamlit dashboard — Upphandlingsbevakning, dark SaaS kanban."""

import html as html_lib
import streamlit as st
import pandas as pd

from dotenv import load_dotenv

from db import (
    init_db, get_all_procurements, search_procurements, get_procurement,
    get_stats, get_analysis, save_label, get_label, get_all_labels, get_label_stats,
)

load_dotenv()

st.set_page_config(
    page_title="Upphandlingsbevakning",
    page_icon="U",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

# ---------------------------------------------------------------------------
# CSS — dark theme, polished cards, sidebar collapse fix
# ---------------------------------------------------------------------------
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --bg-0: #09090b;
    --bg-1: #111113;
    --bg-2: #18181b;
    --bg-3: #1f1f23;
    --bg-hover: #27272a;
    --border: #27272a;
    --border-subtle: #1f1f23;
    --text-0: #fafafa;
    --text-1: #a1a1aa;
    --text-2: #71717a;
    --text-3: #52525b;
    --orange: #f97316;
    --orange-light: #fb923c;
    --orange-dim: rgba(249, 115, 22, 0.12);
    --orange-glow: rgba(249, 115, 22, 0.06);
    --yellow: #eab308;
    --yellow-dim: rgba(234, 179, 8, 0.10);
    --r: 12px;
    --r-sm: 8px;
}

/* --- Global --- */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
.main .block-container { background: var(--bg-0) !important; font-family: 'Inter', sans-serif !important; }
header[data-testid="stHeader"] { background: transparent !important; }
.stMarkdown, .stMarkdown p, .stText,
.main .block-container label, .main .block-container span, .main .block-container div,
.stSelectbox label, .stTextInput label, .stSlider label,
.stNumberInput label { color: var(--text-0) !important; }

/* --- Sidebar: force always visible --- */
section[data-testid="stSidebar"] {
    background: var(--bg-1) !important;
    border-right: 1px solid var(--border) !important;
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    transform: none !important;
    min-width: 260px !important;
    width: 260px !important;
    position: relative !important;
}
section[data-testid="stSidebar"] > div { overflow-y: auto; }
section[data-testid="stSidebar"] * { color: var(--text-0) !important; }
section[data-testid="stSidebar"] .stRadio > div { gap: 2px !important; }
section[data-testid="stSidebar"] .stRadio label {
    padding: 10px 16px !important; border-radius: var(--r-sm) !important;
    transition: background 0.15s !important; cursor: pointer !important;
}
section[data-testid="stSidebar"] .stRadio label:hover { background: var(--bg-3) !important; }

/* --- Inputs --- */
.stTextInput input, .stNumberInput input, .stSelectbox select,
div[data-baseweb="select"] > div {
    background: var(--bg-2) !important; color: var(--text-0) !important;
    border: 1px solid var(--border) !important; border-radius: var(--r-sm) !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: var(--orange) !important; box-shadow: 0 0 0 1px var(--orange) !important;
}

/* --- Metrics --- */
div[data-testid="stMetric"] {
    background: var(--bg-2) !important; border: 1px solid var(--border) !important;
    border-radius: var(--r) !important; padding: 20px 24px !important;
    position: relative; overflow: hidden;
}
div[data-testid="stMetric"]::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--orange), transparent);
}
div[data-testid="stMetric"] label { color: var(--text-2) !important; font-size: 12px !important; text-transform: uppercase; letter-spacing: 0.5px; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: var(--text-0) !important; font-weight: 800 !important; font-size: 28px !important;
}

/* --- Kanban --- */
.kb { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; padding-bottom: 12px; }
.kb-col {
    background: var(--bg-1);
    border: 1px solid var(--border); border-radius: var(--r);
    display: flex; flex-direction: column;
    height: calc(100vh - 260px); min-height: 400px;
}
.kb-col-head {
    padding: 14px 18px; border-bottom: 1px solid var(--border-subtle);
    display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
}
.kb-col-title { font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.8px; }
.kb-count {
    background: var(--bg-3); border-radius: 20px; padding: 2px 10px;
    font-size: 11px; font-weight: 700; color: var(--text-2);
}
.kb-cards {
    padding: 10px; overflow-y: auto; flex: 1; display: flex; flex-direction: column; gap: 8px;
    scrollbar-width: thin; scrollbar-color: var(--bg-3) transparent;
}
.kb-cards::-webkit-scrollbar { width: 6px; }
.kb-cards::-webkit-scrollbar-track { background: transparent; }
.kb-cards::-webkit-scrollbar-thumb { background: var(--bg-3); border-radius: 3px; }
.kb-cards::-webkit-scrollbar-thumb:hover { background: var(--border); }

/* --- Cards --- */
.card {
    background: var(--bg-2); border: 1px solid var(--border); border-radius: var(--r-sm);
    padding: 12px 14px; transition: all 0.2s cubic-bezier(.4,0,.2,1); position: relative; overflow: hidden;
    flex-shrink: 0;
}
.card::before {
    content: ''; position: absolute; top: 0; left: 0; bottom: 0; width: 3px;
    border-radius: 3px 0 0 3px; transition: opacity 0.2s;
}
.card-high::before { background: var(--orange); }
.card-med::before { background: var(--yellow); }
.card-low::before { background: var(--border); opacity: 0.5; }
.card:hover {
    background: var(--bg-hover); border-color: #3f3f46;
    transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}
.card-title {
    font-weight: 600; font-size: 13px; color: var(--text-0); line-height: 1.45;
    margin-bottom: 6px; display: -webkit-box; -webkit-line-clamp: 2;
    -webkit-box-orient: vertical; overflow: hidden;
}
.card-buyer { font-size: 11px; color: var(--text-1); margin-bottom: 8px; }
.card-desc {
    font-size: 11px; color: var(--text-2); line-height: 1.4; margin-bottom: 10px;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.card-foot { display: flex; align-items: center; justify-content: space-between; gap: 6px; flex-wrap: wrap; }
.tag {
    display: inline-block; padding: 2px 7px; border-radius: 4px;
    font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px;
}
.tag-src { background: var(--orange-dim); color: var(--orange-light); border: 1px solid rgba(249,115,22,0.2); }
.tag-geo { background: var(--bg-3); color: var(--text-1); border: 1px solid var(--border); }
.tag-dl { background: var(--bg-3); color: var(--text-2); border: 1px solid var(--border); }
.tag-val { background: rgba(34,197,94,0.08); color: #4ade80; border: 1px solid rgba(34,197,94,0.15); }
.badge {
    display: inline-flex; align-items: center; justify-content: center;
    min-width: 32px; height: 22px; border-radius: 4px; font-size: 11px; font-weight: 800;
}
.badge-h { background: var(--orange-dim); color: var(--orange-light); border: 1px solid rgba(249,115,22,0.3); }
.badge-m { background: var(--yellow-dim); color: var(--yellow); border: 1px solid rgba(234,179,8,0.2); }
.badge-l { background: var(--bg-3); color: var(--text-3); border: 1px solid var(--border); }

/* --- Detail panel --- */
.dp { background: var(--bg-1); border: 1px solid var(--border); border-radius: var(--r); padding: 28px 32px; position: relative; overflow: hidden; }
.dp::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, var(--orange), transparent 60%); }
.dp-title { font-size: 20px; font-weight: 700; color: var(--text-0); margin-bottom: 4px; line-height: 1.35; }
.dp-row { display: flex; padding: 10px 0; border-bottom: 1px solid var(--border-subtle); }
.dp-lbl { width: 160px; flex-shrink: 0; font-size: 12px; font-weight: 600; color: var(--text-2); text-transform: uppercase; letter-spacing: 0.3px; }
.dp-val { font-size: 14px; color: var(--text-0); }
.dp-val a { color: var(--orange-light) !important; text-decoration: none; }
.dp-val a:hover { text-decoration: underline; }
.score-track { width: 100%; height: 6px; background: var(--bg-3); border-radius: 3px; overflow: hidden; margin-top: 8px; }
.score-fill { height: 100%; border-radius: 3px; transition: width 0.5s cubic-bezier(.4,0,.2,1); }

/* --- Topbar --- */
.topbar { margin-bottom: 24px; }
.topbar h1 { font-size: 24px; font-weight: 800; color: var(--text-0); letter-spacing: -0.5px; margin: 0 0 2px; }
.topbar p { font-size: 13px; color: var(--text-2); margin: 0; }

/* --- Empty --- */
.empty { text-align: center; padding: 48px 20px; }
.empty h3 { font-size: 16px; font-weight: 600; color: var(--text-1); margin: 0 0 4px; }
.empty p { font-size: 13px; color: var(--text-2); margin: 0; }

hr { border-color: var(--border) !important; }
.stDataFrame { border-radius: var(--r) !important; overflow: hidden !important; }

/* Hide Streamlit chrome */
#MainMenu, footer { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
</style>
"""

st.markdown(THEME_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div style="padding:20px 16px 20px;border-bottom:1px solid var(--border);margin-bottom:12px">'
        '<div style="font-size:17px;font-weight:800;color:var(--text-0);letter-spacing:-0.3px">Upphandling</div>'
        '<div style="font-size:11px;color:var(--text-2);margin-top:2px;text-transform:uppercase;letter-spacing:0.5px">Procurement Intelligence</div>'
        '</div>',
        unsafe_allow_html=True,
    )

page = st.sidebar.radio(
    "Navigation",
    ["Kanban", "Sök & Filter", "Feedback"],
    label_visibility="collapsed",
)


# ---------------------------------------------------------------------------
# Helpers
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


@st.dialog("Upphandling", width="large")
def show_procurement_dialog(proc_id: int):
    """Native Streamlit dialog with details, feedback and AI analysis."""
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
        <div class="dp-row"><div class="dp-lbl">Status</div><div class="dp-val">{esc(proc.get("status") or "Okänd")}</div></div>
        <div class="dp-row" style="border-bottom:none"><div class="dp-lbl">Länk</div><div class="dp-val">{url_html}</div></div>
    </div>
    """, unsafe_allow_html=True)

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


# ============================================================
# KANBAN
# ============================================================
if page == "Kanban":
    st.markdown(
        '<div class="topbar"><h1>Pipeline</h1>'
        '<p>Upphandlingar sorterade efter publiceringsdatum (nyast först)</p></div>',
        unsafe_allow_html=True,
    )

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
    else:
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


# ============================================================
# SÖK & FILTER
# ============================================================
elif page == "Sök & Filter":
    st.markdown(
        '<div class="topbar"><h1>Sök & Filter</h1>'
        '<p>Filtrera upphandlingar efter nyckelord, källa och score</p></div>',
        unsafe_allow_html=True,
    )

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
    else:
        st.markdown(
            '<div class="empty"><h3>Inga resultat</h3><p>Prova att ändra filtren.</p></div>',
            unsafe_allow_html=True,
        )


# ============================================================
# FEEDBACK
# ============================================================
elif page == "Feedback":
    st.markdown(
        '<div class="topbar"><h1>Feedback</h1>'
        '<p>Markerade upphandlingar och feedbackhistorik</p></div>',
        unsafe_allow_html=True,
    )

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
            '<p>Använd Relevant/Inte relevant-knapparna på Kanban-sidan för att markera upphandlingar.</p></div>',
            unsafe_allow_html=True,
        )


