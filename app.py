"""Streamlit dashboard for Upphandlingsbevakning — dark SaaS kanban theme."""

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

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Upphandlingsbevakning",
    page_icon="U",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

# ---------------------------------------------------------------------------
# Global dark theme CSS
# ---------------------------------------------------------------------------
THEME_CSS = """
<style>
/* ---- Import Inter font ---- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ---- Root variables ---- */
:root {
    --bg-primary: #0e0e0e;
    --bg-secondary: #1a1a1a;
    --bg-card: #1e1e1e;
    --bg-card-hover: #252525;
    --border: #2a2a2a;
    --border-light: #333;
    --text-primary: #f0f0f0;
    --text-secondary: #999;
    --text-muted: #666;
    --orange-500: #f97316;
    --orange-400: #fb923c;
    --orange-600: #ea580c;
    --orange-glow: rgba(249, 115, 22, 0.15);
    --green-500: #22c55e;
    --yellow-500: #eab308;
    --red-500: #ef4444;
    --radius: 10px;
    --radius-sm: 6px;
}

/* ---- Global overrides ---- */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', sans-serif !important;
}
header[data-testid="stHeader"] { background: transparent !important; }
section[data-testid="stSidebar"] {
    background-color: var(--bg-secondary) !important;
    border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] * { color: var(--text-primary) !important; }

/* Fix all text */
.stMarkdown, .stMarkdown p, .stText, label, .stSelectbox label,
.stTextInput label, .stSlider label, .stNumberInput label,
span, div { color: var(--text-primary) !important; }

/* Sidebar radio buttons */
div[data-testid="stSidebar"] .stRadio > div {
    gap: 2px !important;
}
div[data-testid="stSidebar"] .stRadio label {
    padding: 10px 16px !important;
    border-radius: var(--radius-sm) !important;
    transition: background 0.15s !important;
    cursor: pointer !important;
}
div[data-testid="stSidebar"] .stRadio label:hover {
    background: var(--bg-card) !important;
}

/* Inputs */
.stTextInput input, .stNumberInput input, .stSelectbox select,
div[data-baseweb="select"] > div {
    background-color: var(--bg-card) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color: var(--orange-500) !important;
    box-shadow: 0 0 0 1px var(--orange-500) !important;
}

/* Slider */
div[data-testid="stSlider"] > div > div > div {
    background-color: var(--orange-500) !important;
}

/* Metrics */
div[data-testid="stMetric"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    padding: 20px 24px !important;
}
div[data-testid="stMetric"] label { color: var(--text-secondary) !important; font-size: 13px !important; }
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: var(--orange-400) !important;
    font-weight: 700 !important;
    font-size: 32px !important;
}

/* Tables / dataframes */
.stDataFrame, [data-testid="stDataFrame"] { border-radius: var(--radius) !important; overflow: hidden !important; }

/* Divider */
hr { border-color: var(--border) !important; }

/* ---- Kanban layout ---- */
.kanban-board {
    display: flex;
    gap: 16px;
    overflow-x: auto;
    padding-bottom: 16px;
}
.kanban-column {
    flex: 1;
    min-width: 300px;
    max-width: 420px;
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    display: flex;
    flex-direction: column;
    max-height: 75vh;
}
.kanban-column-header {
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
}
.kanban-column-title {
    font-weight: 600;
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-secondary);
}
.kanban-count {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
}
.kanban-cards {
    padding: 12px;
    overflow-y: auto;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.kanban-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 16px;
    transition: all 0.15s ease;
    cursor: default;
}
.kanban-card:hover {
    background: var(--bg-card-hover);
    border-color: var(--border-light);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
.kanban-card-title {
    font-weight: 600;
    font-size: 14px;
    color: var(--text-primary);
    margin-bottom: 8px;
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.kanban-card-buyer {
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 10px;
}
.kanban-card-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
}
.kanban-tag {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}
.tag-source {
    background: rgba(249, 115, 22, 0.12);
    color: var(--orange-400);
    border: 1px solid rgba(249, 115, 22, 0.25);
}
.tag-deadline {
    background: rgba(255,255,255,0.05);
    color: var(--text-secondary);
    border: 1px solid var(--border);
}
.score-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 38px;
    height: 24px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 700;
}
.score-high {
    background: rgba(249, 115, 22, 0.18);
    color: var(--orange-400);
    border: 1px solid rgba(249, 115, 22, 0.35);
}
.score-med {
    background: rgba(234, 179, 8, 0.12);
    color: var(--yellow-500);
    border: 1px solid rgba(234, 179, 8, 0.25);
}
.score-low {
    background: rgba(255,255,255,0.05);
    color: var(--text-muted);
    border: 1px solid var(--border);
}

/* ---- Detail card ---- */
.detail-panel {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 32px;
}
.detail-title {
    font-size: 22px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 4px;
}
.detail-row {
    display: flex;
    padding: 10px 0;
    border-bottom: 1px solid var(--border);
}
.detail-label {
    width: 180px;
    flex-shrink: 0;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
}
.detail-value {
    font-size: 14px;
    color: var(--text-primary);
}
.detail-value a {
    color: var(--orange-400) !important;
    text-decoration: none;
}
.detail-value a:hover { text-decoration: underline; }

/* Score bar */
.score-bar-track {
    width: 100%;
    height: 8px;
    background: var(--bg-card);
    border-radius: 4px;
    overflow: hidden;
    margin-top: 8px;
}
.score-bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.4s ease;
}

/* ---- Settings keyword tag ---- */
.kw-tag {
    display: inline-block;
    padding: 4px 10px;
    margin: 3px 4px 3px 0;
    border-radius: 4px;
    font-size: 12px;
    font-family: 'SF Mono', 'Fira Code', monospace;
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-primary);
}

/* Sidebar branding */
.sidebar-brand {
    padding: 20px 16px 24px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 16px;
}
.sidebar-brand-title {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.3px;
}
.sidebar-brand-sub {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 2px;
}

/* Top bar */
.top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 28px;
}
.top-bar-title {
    font-size: 26px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.5px;
}
.top-bar-sub {
    font-size: 13px;
    color: var(--text-muted);
    margin-top: 2px;
}

/* Empty state */
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
}
.empty-state-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 8px;
}
.empty-state-text {
    font-size: 14px;
    color: var(--text-muted);
}

/* Hide default streamlit branding */
#MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }
</style>
"""

st.markdown(THEME_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div class="sidebar-brand">'
        '<div class="sidebar-brand-title">Upphandling</div>'
        '<div class="sidebar-brand-sub">Procurement Intelligence</div>'
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
def score_class(score: int) -> str:
    if score >= 60:
        return "score-high"
    if score >= 30:
        return "score-med"
    return "score-low"


def score_bar_color(score: int) -> str:
    if score >= 60:
        return "var(--orange-500)"
    if score >= 30:
        return "var(--yellow-500)"
    return "var(--border-light)"


def make_card_html(p: dict) -> str:
    s = p.get("score", 0) or 0
    title = (p.get("title") or "Utan titel")[:80]
    buyer = p.get("buyer") or "Okänd köpare"
    source = (p.get("source") or "").upper()
    deadline = p.get("deadline") or ""
    if deadline and len(deadline) > 10:
        deadline = deadline[:10]

    deadline_tag = (
        f'<span class="kanban-tag tag-deadline">{deadline}</span>' if deadline else ""
    )

    return (
        f'<div class="kanban-card">'
        f'  <div class="kanban-card-title">{title}</div>'
        f'  <div class="kanban-card-buyer">{buyer}</div>'
        f'  <div class="kanban-card-meta">'
        f'    <div>'
        f'      <span class="kanban-tag tag-source">{source}</span>'
        f'      {deadline_tag}'
        f'    </div>'
        f'    <span class="score-badge {score_class(s)}">{s}</span>'
        f'  </div>'
        f'</div>'
    )


# ============================================================
# KANBAN BOARD
# ============================================================
if page == "Kanban":
    st.markdown(
        '<div class="top-bar">'
        '  <div>'
        '    <div class="top-bar-title">Pipeline</div>'
        '    <div class="top-bar-sub">Upphandlingar sorterade efter lead score</div>'
        '  </div>'
        '</div>',
        unsafe_allow_html=True,
    )

    stats = get_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Totalt", stats["total"])
    c2.metric("Nya idag", stats["new_today"])
    c3.metric("Snitt score", stats["avg_score"])
    c4.metric("Hög fit", stats["high_fit"])

    all_procs = get_all_procurements()

    if not all_procs:
        st.markdown(
            '<div class="empty-state">'
            '  <div class="empty-state-title">Ingen data ännu</div>'
            '  <div class="empty-state-text">Kör <code>python run_scrapers.py</code> för att hämta upphandlingar.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        high = [p for p in all_procs if (p.get("score") or 0) >= 60]
        med = [p for p in all_procs if 30 <= (p.get("score") or 0) < 60]
        low = [p for p in all_procs if (p.get("score") or 0) < 30]

        columns_data = [
            ("Hög prioritet", high, "var(--orange-500)"),
            ("Medel", med, "var(--yellow-500)"),
            ("Låg", low, "var(--border-light)"),
        ]

        html = '<div class="kanban-board">'
        for col_title, items, accent in columns_data:
            cards_html = "".join(make_card_html(p) for p in items[:30])
            empty_msg = '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:13px">Inga upphandlingar</div>'
            cards_content = cards_html if cards_html else empty_msg
            html += (
                f'<div class="kanban-column">'
                f'  <div class="kanban-column-header">'
                f'    <span class="kanban-column-title" style="color:{accent}">{col_title}</span>'
                f'    <span class="kanban-count">{len(items)}</span>'
                f'  </div>'
                f'  <div class="kanban-cards">{cards_content}</div>'
                f'</div>'
            )
        html += '</div>'
        st.markdown(html, unsafe_allow_html=True)


# ============================================================
# SOK & FILTER
# ============================================================
elif page == "Sök & Filter":
    st.markdown(
        '<div class="top-bar">'
        '  <div>'
        '    <div class="top-bar-title">Sök & Filter</div>'
        '    <div class="top-bar-sub">Filtrera upphandlingar efter nyckelord, källa och score</div>'
        '  </div>'
        '</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        query = st.text_input("Fritext", placeholder="t.ex. realtidssystem")
    with col2:
        source_filter = st.selectbox("Källa", ["Alla", "ted", "mercell", "kommers", "eavrop"])
    with col3:
        geography_filter = st.text_input("Region", placeholder="t.ex. Stockholm")
    with col4:
        score_range = st.slider("Score", 0, 100, (0, 100))

    source_val = "" if source_filter == "Alla" else source_filter
    results = search_procurements(
        query=query,
        source=source_val,
        min_score=score_range[0],
        max_score=score_range[1],
        geography=geography_filter,
    )

    st.markdown(f"**{len(results)}** resultat")

    if results:
        df = pd.DataFrame(results)[
            ["id", "title", "buyer", "score", "source", "geography", "deadline"]
        ]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.markdown(
            '<div class="empty-state">'
            '  <div class="empty-state-title">Inga resultat</div>'
            '  <div class="empty-state-text">Prova att ändra filtren.</div>'
            '</div>',
            unsafe_allow_html=True,
        )


# ============================================================
# DETALJVY
# ============================================================
elif page == "Detaljvy":
    st.markdown(
        '<div class="top-bar">'
        '  <div>'
        '    <div class="top-bar-title">Detaljvy</div>'
        '    <div class="top-bar-sub">Fullständig information om en upphandling</div>'
        '  </div>'
        '</div>',
        unsafe_allow_html=True,
    )

    proc_id = st.number_input("Upphandlings-ID", min_value=1, step=1, value=1)
    proc = get_procurement(int(proc_id))

    if proc:
        s = proc.get("score") or 0
        bar_color = score_bar_color(s)

        url_html = ""
        if proc.get("url"):
            url_html = f'<a href="{proc["url"]}" target="_blank">{proc["url"]}</a>'
        else:
            url_html = '<span style="color:var(--text-muted)">Ej tillgänglig</span>'

        detail_html = f"""
        <div class="detail-panel">
            <div class="detail-title">{proc.get("title", "")}</div>
            <div style="margin-top:12px;margin-bottom:20px">
                <span class="kanban-tag tag-source">{(proc.get("source") or "").upper()}</span>
                <span class="score-badge {score_class(s)}" style="margin-left:8px">{s}/100</span>
            </div>
            <div class="score-bar-track">
                <div class="score-bar-fill" style="width:{s}%;background:{bar_color}"></div>
            </div>
            <div style="font-size:12px;color:var(--text-muted);margin-top:6px;margin-bottom:20px">
                {proc.get("score_rationale") or "Ej scorad"}
            </div>

            <div class="detail-row">
                <div class="detail-label">Köpare</div>
                <div class="detail-value">{proc.get("buyer") or "Okänd"}</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Geografi</div>
                <div class="detail-value">{proc.get("geography") or "Ej angiven"}</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">CPV-koder</div>
                <div class="detail-value">{proc.get("cpv_codes") or "Ej angivet"}</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Förfarandetyp</div>
                <div class="detail-value">{proc.get("procedure_type") or "Ej angiven"}</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Publicerad</div>
                <div class="detail-value">{proc.get("published_date") or "Okänt"}</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Deadline</div>
                <div class="detail-value">{proc.get("deadline") or "Ej angiven"}</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Uppskattat värde</div>
                <div class="detail-value">{proc.get("estimated_value") or "Ej angivet"} {proc.get("currency") or ""}</div>
            </div>
            <div class="detail-row">
                <div class="detail-label">Status</div>
                <div class="detail-value">{proc.get("status") or "Okänd"}</div>
            </div>
            <div class="detail-row" style="border-bottom:none">
                <div class="detail-label">Länk</div>
                <div class="detail-value">{url_html}</div>
            </div>
        </div>
        """
        st.markdown(detail_html, unsafe_allow_html=True)

        if proc.get("description"):
            st.markdown(
                f'<div class="detail-panel" style="margin-top:16px">'
                f'<div style="font-weight:600;font-size:14px;color:var(--text-secondary);margin-bottom:12px;text-transform:uppercase;letter-spacing:0.5px">Beskrivning</div>'
                f'<div style="font-size:14px;line-height:1.7;color:var(--text-primary)">{proc["description"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="empty-state">'
            '  <div class="empty-state-title">Ingen upphandling hittad</div>'
            '  <div class="empty-state-text">Prova ett annat ID.</div>'
            '</div>',
            unsafe_allow_html=True,
        )


# ============================================================
# INSTALLNINGAR
# ============================================================
elif page == "Inställningar":
    st.markdown(
        '<div class="top-bar">'
        '  <div>'
        '    <div class="top-bar-title">Inställningar</div>'
        '    <div class="top-bar-sub">Scoring-vikter och konfiguration</div>'
        '  </div>'
        '</div>',
        unsafe_allow_html=True,
    )

    def render_keyword_section(title: str, keywords: dict, accent: str):
        tags = "".join(
            f'<span class="kw-tag">{kw} <span style="color:{accent};margin-left:4px">+{w}</span></span>'
            for kw, w in keywords.items()
        )
        st.markdown(
            f'<div class="detail-panel" style="margin-bottom:16px">'
            f'<div style="font-weight:600;font-size:14px;color:var(--text-secondary);margin-bottom:12px;text-transform:uppercase;letter-spacing:0.5px">{title}</div>'
            f'<div>{tags}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    render_keyword_section("Hög vikt (20p)", HIGH_WEIGHT_KEYWORDS, "var(--orange-400)")
    render_keyword_section("Medel vikt (10p)", MEDIUM_WEIGHT_KEYWORDS, "var(--yellow-500)")
    render_keyword_section("Bas vikt (5p)", BASE_WEIGHT_KEYWORDS, "var(--text-secondary)")

    # Known buyers
    buyers_html = "".join(
        f'<span class="kw-tag">{b}</span>' for b in KNOWN_BUYERS
    )
    st.markdown(
        f'<div class="detail-panel">'
        f'<div style="font-weight:600;font-size:14px;color:var(--text-secondary);margin-bottom:12px;text-transform:uppercase;letter-spacing:0.5px">Kända köpare (bonus +10p)</div>'
        f'<div>{buyers_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown(
        '<div style="font-size:13px;color:var(--text-muted);padding:8px 0">'
        'Redigera <code>scorer.py</code> och kör <code>python run_scrapers.py --score-only</code> för att uppdatera scores.'
        '</div>',
        unsafe_allow_html=True,
    )
