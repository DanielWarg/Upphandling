"""Notification center page."""

import html as html_lib

import streamlit as st

from db import (
    get_notifications, get_unread_notification_count,
    mark_notification_read, mark_all_notifications_read,
)


def esc(s: str) -> str:
    return html_lib.escape(str(s)) if s else ""


TYPE_LABELS = {
    "new_procurement": "Ny upphandling",
    "deadline_warning": "Deadline-varning",
    "watch_match": "Bevaknings-träff",
    "stage_change": "Steg ändrat",
    "message": "Meddelande",
}

TYPE_COLORS = {
    "new_procurement": "#22c55e",
    "deadline_warning": "#ef4444",
    "watch_match": "#f97316",
    "stage_change": "#3b82f6",
    "message": "#eab308",
}


def render_notifications():
    """Render notifications page."""
    current_user = st.session_state["current_user"]
    username = current_user["username"]

    st.markdown(
        '<div class="topbar"><h1>Notiser</h1>'
        '<p>Bevakningar, deadlines och uppdateringar</p></div>',
        unsafe_allow_html=True,
    )

    unread = get_unread_notification_count(username)

    c1, c2 = st.columns([3, 1])
    with c1:
        st.metric("Olästa notiser", unread)
    with c2:
        if unread > 0:
            if st.button("Markera alla som lästa"):
                mark_all_notifications_read(username)
                st.rerun()

    # Filter
    show_unread = st.checkbox("Visa bara olästa", value=True)

    notifications = get_notifications(username, unread_only=show_unread, limit=100)

    if not notifications:
        st.markdown(
            '<div class="empty"><h3>Inga notiser</h3>'
            '<p>Notiser skapas automatiskt vid bevakningsträffar, deadline-varningar och andra händelser.</p></div>',
            unsafe_allow_html=True,
        )
        return

    for notif in notifications:
        ntype = notif.get("notification_type", "")
        color = TYPE_COLORS.get(ntype, "#71717a")
        type_label = TYPE_LABELS.get(ntype, ntype)
        is_read = notif.get("read_at") is not None
        bg = "var(--bg-2)" if not is_read else "var(--bg-1)"
        border = f"border-left:3px solid {color}" if not is_read else ""

        title = esc(notif.get("title", ""))
        body = esc(notif.get("body", ""))
        timestamp = (notif.get("created_at") or "")[:16].replace("T", " ")

        c1, c2 = st.columns([6, 1])
        with c1:
            st.markdown(
                f'<div style="padding:12px 16px;margin-bottom:6px;background:{bg};'
                f'border:1px solid var(--border);border-radius:var(--r-sm);{border}">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
                f'<span style="font-size:10px;font-weight:700;text-transform:uppercase;color:{color};'
                f'padding:2px 6px;border-radius:3px;background:{color}15;border:1px solid {color}30">{type_label}</span>'
                f'<span style="font-size:11px;color:var(--text-2)">{timestamp}</span>'
                f'</div>'
                f'<div style="font-size:13px;font-weight:600;color:var(--text-0)">{title}</div>'
                f'{f"<div style=font-size:12px;color:var(--text-1);margin-top:4px>{body}</div>" if body else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )
        with c2:
            if not is_read:
                if st.button("Läst", key=f"read_{notif['id']}"):
                    mark_notification_read(notif["id"])
                    st.rerun()
