"""Shared calendar page using streamlit-calendar."""

import streamlit as st
from datetime import datetime, timedelta

from db import (
    get_calendar_events, add_calendar_event, delete_calendar_event,
    get_all_procurements, get_all_contracts, get_pipeline_items,
)


EVENT_COLORS = {
    "meeting": "#3b82f6",
    "deadline": "#ef4444",
    "follow_up": "#eab308",
    "other": "#71717a",
    "contract_end": "#f97316",
    "procurement_deadline": "#ef4444",
}

USER_COLORS = {
    "anna_lindberg": "#3b82f6",
    "erik_svensson": "#22c55e",
    "maria_johansson": "#eab308",
    "peter_nilsson": "#f97316",
}


def render_calendar():
    """Render shared calendar page."""
    current_user = st.session_state["current_user"]
    username = current_user["username"]
    is_chef = current_user["role"] == "saljchef"

    st.markdown(
        '<div class="topbar"><h1>Kalender</h1>'
        '<p>Deadlines, möten och avtalsutgångar</p></div>',
        unsafe_allow_html=True,
    )

    # Build events list
    events = []

    # Manual calendar events
    cal_events = get_calendar_events(
        username=None if is_chef else username,
    )
    for ev in cal_events:
        color = EVENT_COLORS.get(ev.get("event_type", "other"), "#71717a")
        if is_chef:
            color = USER_COLORS.get(ev.get("user_username", ""), color)
        events.append({
            "title": ev["title"],
            "start": ev["event_date"],
            "color": color,
            "id": f"cal_{ev['id']}",
        })

    # Procurement deadlines from pipeline
    pipeline_items = get_pipeline_items(
        assigned_to=None if is_chef else username,
    )
    for item in pipeline_items:
        if item.get("deadline") and item.get("stage") not in ("vunnen", "forlorad"):
            events.append({
                "title": f"DL: {(item.get('title') or '')[:40]}",
                "start": item["deadline"][:10],
                "color": "#ef4444",
                "id": f"dl_{item['id']}",
            })

    # Contract end dates
    contracts = get_all_contracts()
    for ct in contracts:
        if ct.get("contract_end"):
            events.append({
                "title": f"Avtal: {(ct.get('title') or '')[:40]} ({ct.get('account_name', '')})",
                "start": ct["contract_end"][:10],
                "color": "#f97316",
                "id": f"ct_{ct['id']}",
            })

    # Try to use streamlit-calendar, fall back to simple list
    try:
        from streamlit_calendar import calendar

        calendar_options = {
            "headerToolbar": {
                "left": "prev,next today",
                "center": "title",
                "right": "dayGridMonth,timeGridWeek,listWeek",
            },
            "initialView": "dayGridMonth",
            "selectable": True,
            "editable": False,
        }

        cal_result = calendar(events=events, options=calendar_options, key="main_calendar")

        if cal_result and cal_result.get("dateClick"):
            st.session_state["new_event_date"] = cal_result["dateClick"]["date"]

    except Exception:
        # Fallback: simple list view
        st.markdown("### Kommande händelser")
        today = datetime.now().strftime("%Y-%m-%d")
        upcoming = [e for e in events if (e.get("start") or "") >= today]
        upcoming.sort(key=lambda e: e.get("start", ""))

        for ev in upcoming[:30]:
            color = ev.get("color", "#71717a")
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;padding:8px 14px;margin-bottom:4px;'
                f'background:var(--bg-2);border:1px solid var(--border);border-radius:var(--r-sm);'
                f'border-left:3px solid {color}">'
                f'<div style="min-width:80px;font-size:12px;font-weight:600;color:var(--text-2)">{ev.get("start", "")}</div>'
                f'<div style="font-size:13px;color:var(--text-0)">{ev.get("title", "")}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # Add new event form
    st.markdown("---")
    st.markdown("### Ny händelse")

    with st.form("new_calendar_event"):
        c1, c2 = st.columns(2)
        with c1:
            ev_title = st.text_input("Titel")
            ev_date = st.date_input(
                "Datum",
                value=datetime.now(),
            )
        with c2:
            ev_type = st.selectbox(
                "Typ",
                ["meeting", "deadline", "follow_up", "other"],
                format_func=lambda t: {"meeting": "Möte", "deadline": "Deadline",
                                       "follow_up": "Uppföljning", "other": "Övrigt"}[t],
            )
            ev_desc = st.text_input("Beskrivning")

        if st.form_submit_button("Lägg till"):
            if ev_title.strip():
                add_calendar_event(
                    username, ev_title.strip(), str(ev_date),
                    event_type=ev_type, description=ev_desc,
                )
                st.success("Händelse tillagd!")
                st.rerun()

    # List my events with delete option
    st.markdown("### Mina händelser")
    my_events = get_calendar_events(username=username)
    for ev in my_events:
        c1, c2 = st.columns([5, 1])
        with c1:
            type_labels = {"meeting": "Möte", "deadline": "Deadline",
                          "follow_up": "Uppföljning", "other": "Övrigt"}
            st.markdown(
                f'{ev["event_date"]} — **{ev["title"]}** ({type_labels.get(ev.get("event_type", ""), "")})'
            )
        with c2:
            if st.button("Ta bort", key=f"del_ev_{ev['id']}"):
                delete_calendar_event(ev["id"])
                st.rerun()
