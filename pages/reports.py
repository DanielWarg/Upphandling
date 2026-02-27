"""Reports page — weekly pipeline reports (säljchef only)."""

import html as html_lib

import streamlit as st
import pandas as pd

from reports import generate_report, format_report_text
from db import STAGE_LABELS


def esc(s: str) -> str:
    return html_lib.escape(str(s)) if s else ""


def _fmt_value(val) -> str:
    if not val:
        return "0"
    try:
        v = float(val)
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M"
        if v >= 1_000:
            return f"{v/1_000:.0f}k"
        return f"{v:.0f}"
    except (ValueError, TypeError):
        return "0"


def render_reports():
    """Render reports page (säljchef only)."""
    current_user = st.session_state["current_user"]
    if current_user["role"] != "saljchef":
        st.warning("Denna sida är bara tillgänglig för säljchefer.")
        return

    st.markdown(
        '<div class="topbar"><h1>Rapporter</h1>'
        '<p>Veckorapporter och pipeline-visualiseringar</p></div>',
        unsafe_allow_html=True,
    )

    # Week selector
    week_input = st.text_input(
        "Vecka (lämna tomt för aktuell)",
        placeholder="t.ex. 2026-W09",
    )

    try:
        report = generate_report(week=week_input if week_input else None)
    except Exception as e:
        st.error(f"Kunde inte generera rapport: {e}")
        return

    # Summary metrics
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Aktiva deals", report["pipeline_total"])
    mc2.metric("Pipeline (viktat)", f"{_fmt_value(report['pipeline_weighted_value'])} SEK")
    mc3.metric("Nya relevanta", report["new_relevant_count"])
    mc4.metric("Win rate", report["win_rate"])

    # Stage distribution bar chart
    st.markdown("### Fördelning per steg")
    if report["stage_summary"]:
        df_stages = pd.DataFrame({
            "Steg": list(report["stage_summary"].keys()),
            "Antal": list(report["stage_summary"].values()),
        }).set_index("Steg")
        st.bar_chart(df_stages, color="#f97316")

    # KAM leaderboard
    st.markdown("### KAM-fördelning")
    if report["by_user"]:
        rows = []
        for user, stages in report["by_user"].items():
            total = sum(d.get("count", 0) for d in stages.values())
            weighted = sum(d.get("weighted_value", 0) for d in stages.values())
            rows.append({"KAM": user, "Deals": total, "Viktat värde (SEK)": f"{weighted:,.0f}"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Upcoming deadlines
    st.markdown("### Kommande deadlines")
    if report["upcoming_deadlines"]:
        for item in report["upcoming_deadlines"]:
            dl = (item.get("deadline") or "")[:10]
            st.markdown(
                f'<div style="display:flex;gap:12px;padding:6px 0;border-bottom:1px solid var(--border-subtle)">'
                f'<span style="font-size:12px;font-weight:700;color:#ef4444;min-width:80px">{dl}</span>'
                f'<span style="font-size:13px;color:var(--text-0)">{esc((item.get("title") or "")[:60])}</span>'
                f'<span style="font-size:11px;color:var(--text-2)">{esc(item.get("buyer") or "")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("Inga kommande deadlines denna period.")

    # New relevant procurements
    st.markdown("### Nya relevanta upphandlingar")
    if report["new_relevant"]:
        for p in report["new_relevant"]:
            st.markdown(
                f'<div style="display:flex;gap:8px;padding:6px 0;border-bottom:1px solid var(--border-subtle)">'
                f'<span style="font-size:11px;font-weight:700;color:var(--orange);min-width:30px">{p.get("score", 0)}</span>'
                f'<span style="font-size:13px;color:var(--text-0)">{esc((p.get("title") or "")[:60])}</span>'
                f'<span style="font-size:11px;color:var(--text-2)">{esc(p.get("buyer") or "")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("Inga nya relevanta upphandlingar denna period.")

    # Export as text
    st.markdown("---")
    text_report = format_report_text(report)
    st.download_button(
        "Ladda ner rapport (text)",
        text_report,
        file_name=f"rapport_{report['week']}.txt",
        mime="text/plain",
    )
