"""Personal start page — mission control dashboard with interactive widgets."""

import calendar as cal_module
import html as html_lib
from datetime import datetime

import streamlit as st

from db import (
    get_all_procurements,
    get_analysis,
    get_label,
    get_calendar_events,
    get_all_contracts,
    get_pipeline_items,
    get_unread_count,
    get_conversations,
    get_notifications,
    get_unread_notification_count,
    create_notification,
    send_message,
)
from pages.procurements import show_procurement_dialog


# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------
MONTH_SV = {
    1: "Januari", 2: "Februari", 3: "Mars", 4: "April",
    5: "Maj", 6: "Juni", 7: "Juli", 8: "Augusti",
    9: "September", 10: "Oktober", 11: "November", 12: "December",
}
WEEKDAYS_SV = ["Ma", "Ti", "On", "To", "Fr", "Lo", "So"]
USERS = ["anna_lindberg", "erik_svensson", "maria_johansson", "peter_nilsson"]

NOTIF_TYPE_LABELS = {
    "new_procurement": "Ny upphandling",
    "deadline_warning": "Deadline",
    "watch_match": "Bevakning",
    "stage_change": "Steg",
    "message": "Meddelande",
}
NOTIF_TYPE_COLORS = {
    "new_procurement": "#22c55e",
    "deadline_warning": "#ef4444",
    "watch_match": "#f97316",
    "stage_change": "#3b82f6",
    "message": "#eab308",
}
EVENT_COLORS = {
    "meeting": "#3b82f6",
    "deadline": "#ef4444",
    "follow_up": "#eab308",
    "other": "#ef4444",
}


def esc(s: str) -> str:
    return html_lib.escape(str(s)) if s else ""


def score_css(score: int) -> str:
    if score >= 60:
        return "background:var(--orange-dim);color:var(--orange-light);border:1px solid rgba(249,115,22,0.3)"
    if score >= 30:
        return "background:var(--yellow-dim);color:var(--yellow);border:1px solid rgba(234,179,8,0.2)"
    return "background:var(--bg-3);color:var(--text-3);border:1px solid var(--border)"


def card_level(score: int) -> str:
    if score >= 60: return "high"
    if score >= 30: return "med"
    return "low"


# ---------------------------------------------------------------------------
# Pure HTML widget builders (calendar, notifications, messages)
# ---------------------------------------------------------------------------
def _widget(head_label: str, badge: str, body_html: str) -> str:
    badge_html = f'<span class="wh-badge">{esc(badge)}</span>' if badge else ""
    return (
        f'<div class="widget">'
        f'<div class="widget-head"><span>{esc(head_label)}</span>{badge_html}</div>'
        f'<div class="widget-body">{body_html}</div>'
        f'</div>'
    )


def _build_calendar_html(username: str, is_chef: bool) -> str:
    now = datetime.now()
    year, month, today_day = now.year, now.month, now.day
    today_str = now.strftime("%Y-%m-%d")

    events = []
    for ev in get_calendar_events(username=None if is_chef else username):
        color = EVENT_COLORS.get(ev.get("event_type", "other"), "#71717a")
        events.append({"title": ev["title"], "start": ev["event_date"], "color": color})

    for item in get_pipeline_items(assigned_to=None if is_chef else username):
        if item.get("deadline") and item.get("stage") not in ("vunnen", "forlorad"):
            events.append({"title": f"DL: {(item.get('title') or '')[:30]}", "start": item["deadline"][:10], "color": "#ef4444"})

    for ct in get_all_contracts():
        if ct.get("contract_end"):
            events.append({"title": f"Avtal: {(ct.get('title') or '')[:25]}", "start": ct["contract_end"][:10], "color": "#f97316"})

    # Event days this month
    month_prefix = f"{year}-{month:02d}"
    event_days: dict[int, str] = {}
    for ev in events:
        ds = ev.get("start", "")
        if ds.startswith(month_prefix):
            try:
                day = int(ds[8:10])
                if day not in event_days:
                    event_days[day] = ev.get("color", "#71717a")
            except (ValueError, IndexError):
                pass

    # Month grid
    weeks = cal_module.monthcalendar(year, month)
    thead = "".join(f"<th>{d}</th>" for d in WEEKDAYS_SV)
    trows = ""
    for week in weeks:
        cells = ""
        for day in week:
            if day == 0:
                cells += "<td></td>"
            else:
                cls = "mcal-day"
                if day == today_day:
                    cls += " mcal-today"
                if day in event_days:
                    cls += " mcal-has-event"
                dot = f'<span class="mcal-dot" style="background:{event_days[day]}"></span>' if day in event_days else ""
                cells += f'<td><div class="{cls}">{day}{dot}</div></td>'
        trows += f"<tr>{cells}</tr>"

    cal_html = (
        f'<div class="mcal-title">{MONTH_SV[month]} {year}</div>'
        f'<table class="mcal"><tr>{thead}</tr>{trows}</table>'
    )

    upcoming = sorted(
        [e for e in events if (e.get("start") or "") >= today_str],
        key=lambda e: e.get("start", ""),
    )
    if upcoming:
        cal_html += '<div style="border-top:1px solid var(--border-subtle);margin-top:6px;padding-top:3px">'
        for ev in upcoming[:5]:
            c = ev.get("color", "#71717a")
            cal_html += (
                f'<div class="mcal-event-row">'
                f'<div class="mcal-event-dot" style="background:{c}"></div>'
                f'<div class="mcal-event-date">{ev["start"][:10]}</div>'
                f'<div class="mcal-event-title">{esc(ev.get("title", ""))}</div>'
                f'</div>'
            )
        cal_html += '</div>'

    return _widget("Kalender", f"{len(upcoming)} kommande", cal_html)


def _build_notifications_html(username: str) -> str:
    notif_count = get_unread_notification_count(username)
    notifications = get_notifications(username, unread_only=True, limit=12)

    if not notifications:
        return _widget("Notiser", "", '<div class="widget-empty">Inga olästa notiser</div>')

    cards = []
    for notif in notifications:
        ntype = notif.get("notification_type", "")
        color = NOTIF_TYPE_COLORS.get(ntype, "#71717a")
        type_label = NOTIF_TYPE_LABELS.get(ntype, ntype)
        title = esc((notif.get("title") or "")[:55])
        body = esc((notif.get("body") or "")[:60])
        ts = (notif.get("created_at") or "")[:16].replace("T", " ")

        cards.append(
            f'<div class="ncard">'
            f'<div style="position:absolute;top:0;left:0;bottom:0;width:3px;background:{color};border-radius:3px 0 0 3px"></div>'
            f'<div class="ncard-top">'
            f'<span class="ncard-type" style="color:{color};background:{color}15;border:1px solid {color}30">{type_label}</span>'
            f'<span style="font-size:10px;color:var(--text-2)">{ts}</span>'
            f'</div>'
            f'<div class="ncard-title">{title}</div>'
            f'{f"<div style=font-size:11px;color:var(--text-2);margin-top:1px>{body}</div>" if body else ""}'
            f'</div>'
        )

    return _widget("Notiser", f"{notif_count} olästa", "".join(cards))


def _build_messages_html(username: str) -> str:
    msg_count = get_unread_count(username)
    conversations = get_conversations(username)

    if not conversations:
        return _widget("Meddelanden", "", '<div class="widget-empty">Inga konversationer ännu</div>')

    cards = []
    for conv in conversations[:8]:
        other = conv.get("other_user", "")
        initials = "".join(w[0].upper() for w in other.split("_")[:2]) if other else "?"
        display_name = esc(other.replace("_", " ").title())
        last_msg = esc((conv.get("last_message") or "")[:50])
        last_time = (conv.get("last_message_at") or "")[:16].replace("T", " ")

        cards.append(
            f'<div class="chatcard">'
            f'<div class="chat-avatar">{initials}</div>'
            f'<div class="chat-content">'
            f'<div class="chat-name">{display_name}</div>'
            f'<div class="chat-preview">{last_msg}</div>'
            f'</div>'
            f'<div class="chat-time">{last_time}</div>'
            f'</div>'
        )

    badge = f"{msg_count} olästa" if msg_count else ""
    return _widget("Meddelanden", badge, "".join(cards))


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------
def render_my_page():
    current_user = st.session_state["current_user"]
    username = current_user["username"]
    is_chef = current_user["role"] == "saljchef"

    all_procs = get_all_procurements()
    visible = [
        p for p in all_procs
        if (p.get("score") or 0) > 0 and p.get("ai_relevance") != "irrelevant"
    ]
    # Top 3 by score
    visible.sort(key=lambda p: p.get("score") or 0, reverse=True)
    top3 = visible[:3]

    # Build pure-HTML widgets
    w_cal = _build_calendar_html(username, is_chef)
    w_notif = _build_notifications_html(username)
    w_msg = _build_messages_html(username)

    # ── Header ──
    st.markdown(
        f'<div class="mcr-header">Hej, {esc(current_user["name"])}</div>',
        unsafe_allow_html=True,
    )

    # ── Row 1: Upphandlingar (interactive) + Kalender (HTML) ──
    col_proc, col_cal = st.columns(2)

    with col_proc:
        badge = f'<span class="wh-badge">{len(visible)} relevanta</span>' if visible else ""
        st.markdown(
            f'<div class="widget"><div class="widget-head"><span>Upphandlingar</span>{badge}</div>'
            f'<div class="widget-body">',
            unsafe_allow_html=True,
        )
        if not top3:
            st.markdown(
                '<div class="widget-empty">Inga upphandlingar hittade</div></div></div>',
                unsafe_allow_html=True,
            )
        else:
            for p in top3:
                s = p.get("score", 0) or 0
                title = esc((p.get("title") or "Utan titel")[:65])
                source = esc((p.get("source") or "").upper())
                buyer = esc((p.get("buyer") or "")[:28])
                deadline = (p.get("deadline") or "")[:10]

                indicators = ""
                label = get_label(p["id"])
                if label:
                    lc = "#4ade80" if label["label"] == "relevant" else "#f87171"
                    lt = "R" if label["label"] == "relevant" else "IR"
                    indicators += f'<span style="font-size:9px;font-weight:700;color:{lc};margin-left:4px">{lt}</span>'
                if get_analysis(p["id"]):
                    indicators += '<span style="font-size:9px;font-weight:700;color:#60a5fa;margin-left:4px">AI</span>'

                tags = f'<span class="pcard-tag" style="background:var(--orange-dim);color:var(--orange-light);border:1px solid rgba(249,115,22,0.2)">{source}</span>'
                if buyer:
                    tags += f' <span style="font-size:10px;color:var(--text-2)">{buyer}</span>'
                if deadline:
                    tags += f' <span class="pcard-tag" style="background:var(--bg-3);color:var(--text-2);border:1px solid var(--border)">DL {deadline}</span>'

                st.markdown(
                    f'<div class="pcard pcard-{card_level(s)}">'
                    f'<div class="pcard-top">'
                    f'<div class="pcard-score" style="{score_css(s)}">{s}</div>'
                    f'<div class="pcard-title">{title}</div>'
                    f'{indicators}'
                    f'</div>'
                    f'<div class="pcard-meta">{tags}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Visa", key=f"dash_p_{p['id']}", use_container_width=True):
                    show_procurement_dialog(p["id"])

            st.markdown('</div></div>', unsafe_allow_html=True)

    with col_cal:
        st.markdown(w_cal, unsafe_allow_html=True)

    # ── Row 2: Notiser (HTML) + Meddelanden (HTML) ──
    col_notif, col_msg = st.columns(2)

    with col_notif:
        st.markdown(w_notif, unsafe_allow_html=True)

    with col_msg:
        st.markdown(w_msg, unsafe_allow_html=True)

    # ── Interactive bar: Notis + Chatt ──
    col_n, col_c = st.columns(2)

    with col_n:
        with st.popover("Skapa notis", use_container_width=True):
            notis_typ = st.selectbox(
                "Typ",
                ["deadline_warning", "watch_match", "stage_change", "message"],
                format_func=lambda t: {"deadline_warning": "Deadline-varning", "watch_match": "Bevakningsträff", "stage_change": "Steg ändrat", "message": "Meddelande"}[t],
                key="notis_typ",
            )
            notis_till = st.selectbox("Till", USERS, format_func=lambda u: u.replace("_", " ").title(), key="notis_till")
            notis_titel = st.text_input("Titel", key="notis_titel")
            notis_body = st.text_input("Beskrivning (valfritt)", key="notis_body")
            if st.button("Skicka notis", key="notis_send", use_container_width=True):
                if notis_titel.strip():
                    create_notification(notis_till, notis_typ, notis_titel.strip(), notis_body.strip())
                    st.success("Notis skickad!")
                    st.rerun()

    with col_c:
        with st.popover("Skicka meddelande", use_container_width=True):
            other_users = [u for u in USERS if u != username]
            chatt_till = st.selectbox("Till", other_users, format_func=lambda u: u.replace("_", " ").title(), key="chatt_till")
            chatt_msg = st.text_area("Meddelande", height=80, key="chatt_msg")
            if st.button("Skicka", key="chatt_send", use_container_width=True):
                if chatt_msg.strip():
                    send_message(username, chatt_msg.strip(), to_user=chatt_till)
                    st.success("Meddelande skickat!")
                    st.rerun()
