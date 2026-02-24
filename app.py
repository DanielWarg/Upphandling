"""Streamlit dashboard — Upphandlingsbevakning, dark SaaS kanban."""

import html as html_lib
import streamlit as st
import pandas as pd
from datetime import datetime

from db import init_db, get_all_procurements, search_procurements, get_procurement, get_stats
from scorer import (
    HIGH_WEIGHT_KEYWORDS,
    MEDIUM_WEIGHT_KEYWORDS,
    BASE_WEIGHT_KEYWORDS,
    KNOWN_BUYERS,
)

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
.stMarkdown, .stMarkdown p, .stText, label, span, div,
.stSelectbox label, .stTextInput label, .stSlider label,
.stNumberInput label { color: var(--text-0) !important; }

/* --- Sidebar --- */
section[data-testid="stSidebar"] {
    background: var(--bg-1) !important;
    border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] * { color: var(--text-0) !important; }
section[data-testid="stSidebar"] .stRadio > div { gap: 2px !important; }
section[data-testid="stSidebar"] .stRadio label {
    padding: 10px 16px !important; border-radius: var(--r-sm) !important;
    transition: background 0.15s !important; cursor: pointer !important;
}
section[data-testid="stSidebar"] .stRadio label:hover { background: var(--bg-3) !important; }

/* --- KEEP sidebar collapse button visible --- */
button[kind="header"], [data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    color: var(--text-1) !important;
    background: var(--bg-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
}

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
.kb { display: flex; gap: 16px; overflow-x: auto; padding-bottom: 12px; }
.kb-col {
    flex: 1; min-width: 320px; background: var(--bg-1);
    border: 1px solid var(--border); border-radius: var(--r);
    display: flex; flex-direction: column; max-height: 78vh;
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
.kb-cards { padding: 10px; overflow-y: auto; flex: 1; display: flex; flex-direction: column; gap: 8px; }

/* --- Cards --- */
.card {
    background: var(--bg-2); border: 1px solid var(--border); border-radius: var(--r-sm);
    padding: 14px 16px; transition: all 0.2s cubic-bezier(.4,0,.2,1); position: relative; overflow: hidden;
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

/* --- Keyword tags --- */
.kw { display: inline-block; padding: 4px 10px; margin: 3px 4px 3px 0; border-radius: 5px; font-size: 12px; font-family: 'SF Mono','Fira Code',monospace; background: var(--bg-2); border: 1px solid var(--border); color: var(--text-0); }

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

/* Hide Streamlit chrome except sidebar toggle */
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
    ["Kanban", "Sök & Filter", "Detaljvy", "Inställningar"],
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


def make_card(p: dict) -> str:
    s = p.get("score", 0) or 0
    title = esc(p.get("title") or "Utan titel")[:90]
    buyer = esc(p.get("buyer") or "")
    geo = esc(p.get("geography") or "")
    source = esc((p.get("source") or "").upper())
    deadline = (p.get("deadline") or "")[:10]
    desc = esc((p.get("description") or "")[:120])
    value = fmt_value(p.get("estimated_value"), p.get("currency"))

    tags = f'<span class="tag tag-src">{source}</span>'
    if geo:
        tags += f' <span class="tag tag-geo">{geo}</span>'
    if deadline:
        tags += f' <span class="tag tag-dl">{deadline}</span>'
    if value:
        tags += f' <span class="tag tag-val">{value}</span>'

    buyer_line = f'<div class="card-buyer">{buyer}</div>' if buyer else ""
    desc_line = f'<div class="card-desc">{desc}</div>' if desc else ""

    return (
        f'<div class="card {card_cls(s)}">'
        f'  <div class="card-title">{title}</div>'
        f'  {buyer_line}'
        f'  {desc_line}'
        f'  <div class="card-foot">'
        f'    <div>{tags}</div>'
        f'    <span class="badge {badge_cls(s)}">{s}</span>'
        f'  </div>'
        f'</div>'
    )


# ============================================================
# KANBAN
# ============================================================
if page == "Kanban":
    st.markdown(
        '<div class="topbar"><h1>Pipeline</h1>'
        '<p>Upphandlingar sorterade efter lead score</p></div>',
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
        high = [p for p in all_procs if (p.get("score") or 0) >= 60]
        med = [p for p in all_procs if 30 <= (p.get("score") or 0) < 60]
        low = [p for p in all_procs if (p.get("score") or 0) < 30]

        cols = [
            ("Hög prioritet", high, "var(--orange)"),
            ("Medel", med, "var(--yellow)"),
            ("Låg", low, "var(--text-3)"),
        ]

        html = '<div class="kb">'
        for title, items, accent in cols:
            cards = "".join(make_card(p) for p in items[:40])
            empty = '<div style="padding:24px;text-align:center;color:var(--text-3);font-size:12px">Inga upphandlingar</div>'
            html += (
                f'<div class="kb-col">'
                f'  <div class="kb-col-head">'
                f'    <span class="kb-col-title" style="color:{accent}">{title}</span>'
                f'    <span class="kb-count">{len(items)}</span>'
                f'  </div>'
                f'  <div class="kb-cards">{cards or empty}</div>'
                f'</div>'
            )
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)


# ============================================================
# SÖK & FILTER
# ============================================================
elif page == "Sök & Filter":
    st.markdown(
        '<div class="topbar"><h1>Sök & Filter</h1>'
        '<p>Filtrera upphandlingar efter nyckelord, källa och score</p></div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        query = st.text_input("Fritext", placeholder="t.ex. realtidssystem")
    with c2:
        source_filter = st.selectbox("Källa", ["Alla", "ted", "mercell", "kommers", "eavrop"])
    with c3:
        geography_filter = st.text_input("Region", placeholder="t.ex. Stockholm")
    with c4:
        score_range = st.slider("Score", 0, 100, (0, 100))

    source_val = "" if source_filter == "Alla" else source_filter
    results = search_procurements(
        query=query, source=source_val,
        min_score=score_range[0], max_score=score_range[1],
        geography=geography_filter,
    )

    st.markdown(f"**{len(results)}** resultat")

    if results:
        df = pd.DataFrame(results)[["id", "title", "buyer", "score", "source", "geography", "deadline"]]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.markdown(
            '<div class="empty"><h3>Inga resultat</h3><p>Prova att ändra filtren.</p></div>',
            unsafe_allow_html=True,
        )


# ============================================================
# DETALJVY
# ============================================================
elif page == "Detaljvy":
    st.markdown(
        '<div class="topbar"><h1>Detaljvy</h1>'
        '<p>Fullständig information om en upphandling</p></div>',
        unsafe_allow_html=True,
    )

    proc_id = st.number_input("Upphandlings-ID", min_value=1, step=1, value=1)
    proc = get_procurement(int(proc_id))

    if proc:
        s = proc.get("score") or 0
        bc = bar_color(s)
        url_html = (
            f'<a href="{esc(proc["url"])}" target="_blank">{esc(proc["url"])}</a>'
            if proc.get("url")
            else '<span style="color:var(--text-3)">Ej tillgänglig</span>'
        )
        value_str = fmt_value(proc.get("estimated_value"), proc.get("currency")) or "Ej angivet"

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

        if proc.get("description"):
            st.markdown(
                f'<div class="dp" style="margin-top:12px">'
                f'<div style="font-weight:700;font-size:12px;color:var(--text-2);margin-bottom:10px;text-transform:uppercase;letter-spacing:0.5px">Beskrivning</div>'
                f'<div style="font-size:14px;line-height:1.7;color:var(--text-1)">{esc(proc["description"])}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="empty"><h3>Ingen upphandling hittad</h3><p>Prova ett annat ID.</p></div>',
            unsafe_allow_html=True,
        )


# ============================================================
# INSTÄLLNINGAR
# ============================================================
elif page == "Inställningar":
    st.markdown(
        '<div class="topbar"><h1>Inställningar</h1>'
        '<p>Scoring-vikter och konfiguration</p></div>',
        unsafe_allow_html=True,
    )

    def render_kw_section(title: str, keywords: dict, accent: str):
        tags = "".join(
            f'<span class="kw">{esc(kw)} <span style="color:{accent};margin-left:4px">+{w}</span></span>'
            for kw, w in keywords.items()
        )
        st.markdown(
            f'<div class="dp" style="margin-bottom:12px">'
            f'<div style="font-weight:700;font-size:12px;color:var(--text-2);margin-bottom:10px;text-transform:uppercase;letter-spacing:0.5px">{title}</div>'
            f'<div>{tags}</div></div>',
            unsafe_allow_html=True,
        )

    render_kw_section("Hög vikt (20p)", HIGH_WEIGHT_KEYWORDS, "var(--orange-light)")
    render_kw_section("Medel vikt (10p)", MEDIUM_WEIGHT_KEYWORDS, "var(--yellow)")
    render_kw_section("Bas vikt (5p)", BASE_WEIGHT_KEYWORDS, "var(--text-1)")

    buyers_html = "".join(f'<span class="kw">{esc(b)}</span>' for b in KNOWN_BUYERS)
    st.markdown(
        f'<div class="dp">'
        f'<div style="font-weight:700;font-size:12px;color:var(--text-2);margin-bottom:10px;text-transform:uppercase;letter-spacing:0.5px">Kända köpare (bonus +10p)</div>'
        f'<div>{buyers_html}</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown(
        '<div style="font-size:12px;color:var(--text-3);padding:8px 0">'
        'Redigera <code>scorer.py</code> och kör <code>python run_scrapers.py --score-only</code> för att uppdatera scores.'
        '</div>',
        unsafe_allow_html=True,
    )
