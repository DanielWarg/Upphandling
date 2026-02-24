"""Streamlit dashboard for Upphandlingsbevakning."""

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

# --- Page config ---
st.set_page_config(
    page_title="Upphandlingsbevakning",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

init_db()

# --- Sidebar navigation ---
page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Sok & Filter", "Detaljvy", "Installningar"],
)


def score_color(score: int) -> str:
    if score >= 60:
        return "background-color: #ffcccc"  # Red = high
    elif score >= 30:
        return "background-color: #fff3cd"  # Yellow = medium
    return ""


def style_score_column(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """Apply color styling to the score column."""
    def highlight(val):
        if isinstance(val, (int, float)):
            if val >= 60:
                return "background-color: #ffcccc"
            elif val >= 30:
                return "background-color: #fff3cd"
        return ""
    return df.style.map(highlight, subset=["score"] if "score" in df.columns else [])


# ============================================================
# DASHBOARD
# ============================================================
if page == "Dashboard":
    st.title("Upphandlingsbevakning - Dashboard")

    stats = get_stats()

    # KPI row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Totalt antal", stats["total"])
    col2.metric("Nya idag", stats["new_today"])
    col3.metric("Snitt-score", stats["avg_score"])
    col4.metric("Hog fit (60+)", stats["high_fit"])

    # Source breakdown
    if stats["by_source"]:
        st.subheader("Per kalla")
        source_df = pd.DataFrame(
            list(stats["by_source"].items()), columns=["Kalla", "Antal"]
        )
        st.bar_chart(source_df.set_index("Kalla"))

    # Top scored procurements
    st.subheader("Topp-rankade upphandlingar")
    all_procs = get_all_procurements()
    if all_procs:
        df = pd.DataFrame(all_procs)
        top = df.nlargest(10, "score")[
            ["title", "buyer", "score", "source", "deadline", "geography"]
        ]
        st.dataframe(style_score_column(top), use_container_width=True, hide_index=True)
    else:
        st.info("Ingen data annu. Kor `python run_scrapers.py` for att hamta upphandlingar.")

    # Upcoming deadlines
    st.subheader("Snart deadline")
    if all_procs:
        df = pd.DataFrame(all_procs)
        with_deadline = df[df["deadline"].notna() & (df["deadline"] != "")].copy()
        if not with_deadline.empty:
            with_deadline["deadline_dt"] = pd.to_datetime(
                with_deadline["deadline"], errors="coerce"
            )
            upcoming = with_deadline.dropna(subset=["deadline_dt"])
            upcoming = upcoming[upcoming["deadline_dt"] >= datetime.now()]
            upcoming = upcoming.nsmallest(10, "deadline_dt")[
                ["title", "buyer", "deadline", "score", "source"]
            ]
            st.dataframe(style_score_column(upcoming), use_container_width=True, hide_index=True)
        else:
            st.info("Inga upphandlingar med deadline.")

    # Score distribution
    st.subheader("Score-fordelning")
    if all_procs:
        df = pd.DataFrame(all_procs)
        bins = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        df["score_bin"] = pd.cut(df["score"], bins=bins, right=True)
        dist = df["score_bin"].value_counts().sort_index()
        st.bar_chart(dist)


# ============================================================
# SOK & FILTER
# ============================================================
elif page == "Sok & Filter":
    st.title("Sok & Filter")

    col1, col2 = st.columns(2)
    with col1:
        query = st.text_input("Fritext-sok", placeholder="t.ex. realtidssystem")
        source_filter = st.selectbox("Kalla", ["Alla", "ted", "mercell", "kommers", "eavrop"])
    with col2:
        geography_filter = st.text_input("Region/geografi", placeholder="t.ex. Stockholm")
        score_range = st.slider("Score-intervall", 0, 100, (0, 100))

    source_val = "" if source_filter == "Alla" else source_filter
    results = search_procurements(
        query=query,
        source=source_val,
        min_score=score_range[0],
        max_score=score_range[1],
        geography=geography_filter,
    )

    st.write(f"**{len(results)} resultat**")

    if results:
        df = pd.DataFrame(results)[
            ["id", "title", "buyer", "score", "source", "geography", "deadline", "url"]
        ]
        st.dataframe(style_score_column(df), use_container_width=True, hide_index=True)
    else:
        st.info("Inga resultat matchar din sokning.")


# ============================================================
# DETALJVY
# ============================================================
elif page == "Detaljvy":
    st.title("Detaljvy")

    proc_id = st.number_input("Ange upphandlings-ID", min_value=1, step=1, value=1)
    proc = get_procurement(int(proc_id))

    if proc:
        st.subheader(proc["title"])

        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Kalla:** {proc['source']}")
            st.write(f"**Kopare:** {proc['buyer'] or 'Okand'}")
            st.write(f"**Geografi:** {proc['geography'] or 'Ej angiven'}")
            st.write(f"**CPV-koder:** {proc['cpv_codes'] or 'Ej angivet'}")
            st.write(f"**Forfarandetyp:** {proc['procedure_type'] or 'Ej angiven'}")
        with col2:
            st.write(f"**Publicerad:** {proc['published_date'] or 'Okant'}")
            st.write(f"**Deadline:** {proc['deadline'] or 'Ej angiven'}")
            st.write(f"**Uppskattat varde:** {proc['estimated_value'] or 'Ej angivet'} {proc['currency'] or ''}")
            st.write(f"**Status:** {proc['status'] or 'Okand'}")
            if proc["url"]:
                st.write(f"**Lank:** [{proc['url']}]({proc['url']})")

        # Score breakdown
        st.divider()
        score_val = proc["score"] or 0
        if score_val >= 60:
            st.error(f"Lead Score: {score_val}/100 (HOG)")
        elif score_val >= 30:
            st.warning(f"Lead Score: {score_val}/100 (MEDEL)")
        else:
            st.info(f"Lead Score: {score_val}/100 (LAG)")

        st.write(f"**Motivering:** {proc['score_rationale'] or 'Ej scorad annu'}")

        # Description
        if proc["description"]:
            st.divider()
            st.subheader("Beskrivning")
            st.write(proc["description"])
    else:
        st.warning("Ingen upphandling med det ID:t. Prova ett annat.")


# ============================================================
# INSTALLNINGAR
# ============================================================
elif page == "Installningar":
    st.title("Installningar - Scoring-vikter")
    st.write("Nuvarande konfiguration for lead scoring.")

    st.subheader("Hog vikt (20p)")
    for kw, w in HIGH_WEIGHT_KEYWORDS.items():
        st.write(f"- `{kw}` = {w}p")

    st.subheader("Medel vikt (10p)")
    for kw, w in MEDIUM_WEIGHT_KEYWORDS.items():
        st.write(f"- `{kw}` = {w}p")

    st.subheader("Bas vikt (5p)")
    for kw, w in BASE_WEIGHT_KEYWORDS.items():
        st.write(f"- `{kw}` = {w}p")

    st.subheader("Kanda kopare (bonus +10p)")
    st.write(", ".join(KNOWN_BUYERS[:20]) + "...")

    st.divider()
    st.info(
        "For att andra vikterna, redigera `scorer.py` och kor sedan "
        "`python run_scrapers.py --score-only` for att uppdatera alla scores."
    )
