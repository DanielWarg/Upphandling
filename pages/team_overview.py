"""Team overview page — säljchef only."""

import html as html_lib

import streamlit as st

from db import (
    get_pipeline_items, get_pipeline_summary, get_pipeline_summary_by_user,
    STAGE_LABELS, PIPELINE_STAGES,
)


STAGE_COLORS = {
    "bevakad": "#71717a",
    "kvalificerad": "#eab308",
    "anbud_pagaende": "#f97316",
    "inskickad": "#3b82f6",
    "vunnen": "#22c55e",
    "forlorad": "#ef4444",
}


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


def render_team_overview():
    """Render team overview page (säljchef only)."""
    current_user = st.session_state["current_user"]
    if current_user["role"] != "saljchef":
        st.warning("Denna sida är bara tillgänglig för säljchefer.")
        return

    st.markdown(
        '<div class="topbar"><h1>Teamöversikt</h1>'
        '<p>Pipeline-fördelning och KAM-prestationer</p></div>',
        unsafe_allow_html=True,
    )

    summary = get_pipeline_summary()
    by_user = get_pipeline_summary_by_user()
    all_items = get_pipeline_items()

    # Pipeline waterfall
    st.markdown("### Pipeline per steg")
    active_stages = ["bevakad", "kvalificerad", "anbud_pagaende", "inskickad"]

    chart_data = {}
    for stage in active_stages:
        data = summary.get(stage, {"count": 0, "weighted_value": 0, "total_value": 0})
        chart_data[STAGE_LABELS[stage]] = data["weighted_value"]

    if any(v > 0 for v in chart_data.values()):
        import pandas as pd
        df = pd.DataFrame({
            "Steg": list(chart_data.keys()),
            "Viktat värde (SEK)": list(chart_data.values()),
        }).set_index("Steg")
        st.bar_chart(df, color="#f97316")

    # Conversion funnel
    st.markdown("### Konverteringstratt")
    prev_count = None
    for stage in PIPELINE_STAGES:
        data = summary.get(stage, {"count": 0})
        count = data["count"]
        color = STAGE_COLORS.get(stage, "#71717a")
        conversion = ""
        if prev_count and prev_count > 0 and stage not in ("vunnen", "forlorad"):
            pct = count / prev_count * 100
            conversion = f' ({pct:.0f}% från föregående)'

        bar_width = min(count * 10, 100) if count else 0
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:12px;padding:8px 0">'
            f'<div style="min-width:120px;font-size:12px;color:var(--text-1)">{STAGE_LABELS[stage]}</div>'
            f'<div style="flex:1;background:var(--bg-2);border-radius:4px;height:24px;position:relative">'
            f'<div style="background:{color};height:100%;border-radius:4px;width:{bar_width}%;'
            f'min-width:{20 if count else 0}px;display:flex;align-items:center;padding:0 8px">'
            f'<span style="font-size:11px;font-weight:700;color:#fff">{count}</span>'
            f'</div></div>'
            f'<div style="font-size:11px;color:var(--text-2);min-width:150px">{conversion}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if stage not in ("vunnen", "forlorad"):
            prev_count = count

    # KAM leaderboard
    st.markdown("### KAM-leaderboard")
    if by_user:
        leaderboard = []
        for user, stages in by_user.items():
            total_count = sum(d.get("count", 0) for d in stages.values())
            total_weighted = sum(d.get("weighted_value", 0) for d in stages.values())
            won = stages.get("vunnen", {}).get("count", 0)
            lost = stages.get("forlorad", {}).get("count", 0)
            win_rate = f"{won / (won + lost) * 100:.0f}%" if (won + lost) > 0 else "—"
            leaderboard.append((user, total_count, total_weighted, won, win_rate))

        leaderboard.sort(key=lambda x: x[2], reverse=True)

        # Table header
        st.markdown(
            '<div style="display:flex;padding:8px 14px;font-size:11px;font-weight:700;color:var(--text-2);'
            'text-transform:uppercase;letter-spacing:0.5px">'
            '<div style="flex:2">KAM</div>'
            '<div style="flex:1;text-align:center">Deals</div>'
            '<div style="flex:1;text-align:center">Pipeline (viktat)</div>'
            '<div style="flex:1;text-align:center">Vunna</div>'
            '<div style="flex:1;text-align:center">Win rate</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        for user, count, weighted, won, win_rate in leaderboard:
            st.markdown(
                f'<div style="display:flex;align-items:center;padding:10px 14px;margin-bottom:4px;'
                f'background:var(--bg-2);border:1px solid var(--border);border-radius:var(--r-sm)">'
                f'<div style="flex:2;font-size:14px;font-weight:600;color:var(--text-0)">{esc(user)}</div>'
                f'<div style="flex:1;text-align:center;font-size:13px;color:var(--text-1)">{count}</div>'
                f'<div style="flex:1;text-align:center;font-size:13px;font-weight:600;color:var(--orange)">'
                f'{_fmt_value(weighted)} SEK</div>'
                f'<div style="flex:1;text-align:center;font-size:13px;color:#22c55e">{won}</div>'
                f'<div style="flex:1;text-align:center;font-size:13px;color:var(--text-1)">{win_rate}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div style="padding:16px;text-align:center;color:var(--text-3);font-size:12px">'
            'Inga pipeline-data ännu</div>',
            unsafe_allow_html=True,
        )

    # All pipeline items list
    st.markdown("### Alla deals")
    if all_items:
        import pandas as pd
        df = pd.DataFrame([{
            "Titel": (i.get("title") or "")[:60],
            "Köpare": i.get("buyer") or "",
            "Steg": STAGE_LABELS.get(i.get("stage", ""), ""),
            "Tilldelad": i.get("assigned_to") or "Ej tilldelad",
            "Värde": i.get("pipeline_value") or i.get("estimated_value") or 0,
            "Sannolikhet": f"{i.get('probability', 0)}%",
            "Deadline": (i.get("deadline") or "")[:10],
        } for i in all_items])
        st.dataframe(df, use_container_width=True, hide_index=True)
