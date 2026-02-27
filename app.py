"""Streamlit dashboard — Upphandlingsbevakning, dark SaaS with multi-user pipeline."""

import streamlit as st

from dotenv import load_dotenv

from db import init_db, get_unread_notification_count, get_unread_count
from auth import check_auth, get_current_user, render_sidebar_user

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

/* --- Navigation section headers --- */
section[data-testid="stSidebar"] [data-testid="stSidebarNavSectionHeader"] {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.8px; color: var(--text-2) !important;
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
/* --- Password toggle icon fix --- */
.stTextInput input[type="password"], .stTextInput input[type="text"] {
    padding-right: 40px !important;
}
button[kind="passwordToggle"], .stTextInput button {
    color: var(--text-2) !important;
    background: transparent !important;
    border: none !important;
    right: 4px !important;
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

/* --- Dashboard widgets --- */
.mcr-header { font-size:18px; font-weight:800; color:var(--text-0); letter-spacing:-0.3px; margin-bottom:10px; }
.mcr-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; height:calc(100vh - 180px); }
.widget { background:var(--bg-1); border:1px solid var(--border); border-radius:var(--r); overflow:hidden; position:relative; display:flex; flex-direction:column; min-height:0; }
.widget::after { content:''; position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg, var(--orange), transparent 60%); z-index:1; pointer-events:none; }
.widget-head { padding:8px 12px; border-bottom:1px solid var(--border-subtle); font-weight:700; font-size:10px; text-transform:uppercase; letter-spacing:0.8px; color:var(--text-2); display:flex; justify-content:space-between; align-items:center; flex-shrink:0; }
.wh-badge { font-size:10px; font-weight:700; color:var(--orange-light); background:var(--orange-dim); padding:2px 8px; border-radius:10px; border:1px solid rgba(249,115,22,0.2); text-transform:none; letter-spacing:0; }
.widget-body { padding:4px 8px; flex:1; min-height:0; overflow-y:auto; scrollbar-width:thin; scrollbar-color:var(--bg-3) transparent; }
.widget-body::-webkit-scrollbar { width:5px; }
.widget-body::-webkit-scrollbar-track { background:transparent; }
.widget-body::-webkit-scrollbar-thumb { background:var(--bg-3); border-radius:3px; }
.widget-empty { padding:28px 16px; text-align:center; color:var(--text-2); font-size:12px; }

/* Procurement mini-cards */
.pcard { background:var(--bg-2); border:1px solid var(--border); border-radius:var(--r-sm); padding:7px 10px; margin-bottom:4px; position:relative; overflow:hidden; transition:all .15s ease; }
.pcard:hover { background:var(--bg-hover); border-color:#3f3f46; box-shadow:0 4px 12px rgba(0,0,0,0.3); }
.pcard::before { content:''; position:absolute; top:0; left:0; bottom:0; width:3px; border-radius:3px 0 0 3px; }
.pcard-high::before { background:var(--orange); }
.pcard-med::before { background:var(--yellow); }
.pcard-low::before { background:var(--border); opacity:0.5; }
.pcard-top { display:flex; align-items:center; gap:8px; margin-bottom:4px; }
.pcard-score { min-width:30px; height:20px; border-radius:4px; font-size:10px; font-weight:800; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.pcard-title { font-weight:600; font-size:12px; color:var(--text-0); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1; min-width:0; }
.pcard-meta { display:flex; align-items:center; gap:6px; }
.pcard-tag { display:inline-block; padding:1px 5px; border-radius:3px; font-size:9px; font-weight:700; text-transform:uppercase; }

/* Mini calendar */
.mcal { width:100%; border-collapse:collapse; table-layout:fixed; }
.mcal-title { font-size:13px; font-weight:700; color:var(--text-0); text-align:center; padding:4px 0 8px; letter-spacing:0.3px; }
.mcal th { font-size:10px; font-weight:600; color:var(--text-2); padding:3px 0; text-align:center; }
.mcal td { text-align:center; padding:1px; vertical-align:top; }
.mcal-day { width:26px; height:26px; border-radius:6px; display:inline-flex; align-items:center; justify-content:center; font-size:11px; font-weight:500; color:var(--text-1); position:relative; }
.mcal-today { background:var(--orange-dim); color:var(--orange-light); font-weight:700; box-shadow:0 0 0 1px rgba(249,115,22,0.3); }
.mcal-has-event { font-weight:600; color:var(--text-0); }
.mcal-dot { position:absolute; bottom:1px; left:50%; transform:translateX(-50%); width:4px; height:4px; border-radius:50%; }
.mcal-event-row { display:flex; align-items:center; gap:8px; padding:3px 8px; font-size:11px; color:var(--text-0); }
.mcal-event-dot { width:6px; height:6px; border-radius:50%; flex-shrink:0; }
.mcal-event-date { font-size:10px; color:var(--text-2); min-width:68px; font-weight:600; }
.mcal-event-title { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

/* Notification cards */
.ncard { background:var(--bg-2); border:1px solid var(--border); border-radius:var(--r-sm); padding:7px 10px; margin-bottom:4px; position:relative; overflow:hidden; transition:background .15s ease; }
.ncard:hover { background:var(--bg-hover); }
.ncard::before { content:''; position:absolute; top:0; left:0; bottom:0; width:3px; border-radius:3px 0 0 3px; }
.ncard-top { display:flex; align-items:center; gap:6px; margin-bottom:3px; }
.ncard-type { font-size:9px; font-weight:700; text-transform:uppercase; padding:1px 6px; border-radius:3px; letter-spacing:0.3px; }
.ncard-title { font-size:12px; font-weight:600; color:var(--text-0); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

/* Chat cards */
.chatcard { background:var(--bg-2); border:1px solid var(--border); border-radius:var(--r-sm); padding:7px 10px; margin-bottom:4px; display:flex; align-items:center; gap:8px; transition:background .15s ease; }
.chatcard:hover { background:var(--bg-hover); }
.chat-avatar { width:30px; height:30px; border-radius:50%; background:var(--orange-dim); border:1px solid rgba(249,115,22,0.2); display:flex; align-items:center; justify-content:center; font-size:11px; font-weight:700; color:var(--orange-light); flex-shrink:0; }
.chat-content { flex:1; min-width:0; }
.chat-name { font-size:12px; font-weight:600; color:var(--text-0); }
.chat-preview { font-size:11px; color:var(--text-2); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-top:1px; }
.chat-time { font-size:10px; color:var(--text-2); flex-shrink:0; }

hr { border-color: var(--border) !important; }
.stDataFrame { border-radius: var(--r) !important; overflow: hidden !important; }

/* Hide Streamlit chrome */
#MainMenu, footer { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
</style>
"""

st.markdown(THEME_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Auth gate — nothing renders without login
# ---------------------------------------------------------------------------
if not check_auth():
    st.stop()

current_user = get_current_user()
if not current_user:
    st.error("Kunde inte hämta användarinformation.")
    st.stop()

st.session_state["current_user"] = current_user

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

render_sidebar_user()

# Notification indicators
try:
    notif_count = get_unread_notification_count(current_user["username"])
    msg_count = get_unread_count(current_user["username"])
    if notif_count > 0 or msg_count > 0:
        badge_text = []
        if notif_count > 0:
            badge_text.append(f"{notif_count} notiser")
        if msg_count > 0:
            badge_text.append(f"{msg_count} meddelanden")
        st.sidebar.markdown(
            f'<div style="padding:8px 16px;margin-bottom:8px;background:var(--orange-dim);'
            f'border:1px solid rgba(249,115,22,0.2);border-radius:var(--r-sm);font-size:11px;color:var(--orange-light)">'
            f'{", ".join(badge_text)} olästa</div>',
            unsafe_allow_html=True,
        )
except Exception:
    pass

# ---------------------------------------------------------------------------
# Navigation — 2 pages
# ---------------------------------------------------------------------------
from pages.my_page import render_my_page
from pages.procurements import render_procurements

nav_pages = [
    st.Page(render_my_page, title="Min sida", default=True, url_path=""),
    st.Page(render_procurements, title="Upphandlingar", url_path="upphandlingar"),
]

pg = st.navigation(nav_pages)
pg.run()
