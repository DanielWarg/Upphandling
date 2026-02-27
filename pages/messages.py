"""Internal messaging page with chat UI."""

import html as html_lib

import streamlit as st

from db import (
    send_message, get_messages, get_conversations,
    mark_messages_read, get_unread_count,
)


def esc(s: str) -> str:
    return html_lib.escape(str(s)) if s else ""


# Available users for messaging
USERS = ["anna_lindberg", "erik_svensson", "maria_johansson", "peter_nilsson"]


def render_messages():
    """Render messaging page with two-panel layout."""
    current_user = st.session_state["current_user"]
    username = current_user["username"]

    st.markdown(
        '<div class="topbar"><h1>Meddelanden</h1>'
        '<p>Intern kommunikation med teamet</p></div>',
        unsafe_allow_html=True,
    )

    col_list, col_chat = st.columns([1, 2])

    with col_list:
        st.markdown("### Konversationer")

        # New conversation
        other_users = [u for u in USERS if u != username]
        new_conv = st.selectbox("Ny konversation med", ["Välj..."] + other_users, key="new_conv")

        conversations = get_conversations(username)

        if conversations:
            for conv in conversations:
                other = conv.get("other_user", "")
                last_msg = (conv.get("last_message") or "")[:40]
                last_time = (conv.get("last_message_at") or "")[:16].replace("T", " ")

                selected = st.session_state.get("chat_with") == other
                bg = "var(--bg-3)" if selected else "var(--bg-2)"

                st.markdown(
                    f'<div style="padding:10px 14px;margin-bottom:4px;background:{bg};'
                    f'border:1px solid var(--border);border-radius:var(--r-sm);cursor:pointer">'
                    f'<div style="font-size:13px;font-weight:600;color:var(--text-0)">{esc(other)}</div>'
                    f'<div style="font-size:11px;color:var(--text-2);margin-top:2px">'
                    f'{esc(last_msg)} — {last_time}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Öppna", key=f"open_conv_{other}", use_container_width=True):
                    st.session_state["chat_with"] = other
                    st.rerun()

        # Broadcast option
        st.markdown("---")
        if st.button("Skicka till alla", key="broadcast_btn"):
            st.session_state["chat_with"] = "__all__"
            st.rerun()

    with col_chat:
        chat_with = st.session_state.get("chat_with")

        # Handle new conversation selection
        if new_conv and new_conv != "Välj...":
            chat_with = new_conv
            st.session_state["chat_with"] = new_conv

        if not chat_with:
            st.markdown(
                '<div class="empty"><h3>Välj en konversation</h3>'
                '<p>Välj en konversation till vänster eller starta en ny.</p></div>',
                unsafe_allow_html=True,
            )
            return

        is_broadcast = chat_with == "__all__"
        header = "Alla" if is_broadcast else chat_with
        st.markdown(f"### Chatt med {esc(header)}")

        # Mark messages as read
        if not is_broadcast:
            mark_messages_read(username, from_user=chat_with)

        # Get messages
        if is_broadcast:
            messages_list = get_messages(username, limit=50)
            messages_list = [m for m in messages_list if m.get("to_user") is None]
        else:
            messages_list = get_messages(username, other_user=chat_with, limit=50)

        # Display messages (oldest first)
        messages_list.reverse()
        for msg in messages_list:
            is_mine = msg["from_user"] == username
            align = "flex-end" if is_mine else "flex-start"
            bg = "var(--orange-dim)" if is_mine else "var(--bg-2)"
            border_color = "rgba(249,115,22,0.2)" if is_mine else "var(--border)"

            st.markdown(
                f'<div style="display:flex;justify-content:{align};margin-bottom:8px">'
                f'<div style="max-width:70%;padding:10px 14px;background:{bg};'
                f'border:1px solid {border_color};border-radius:var(--r-sm)">'
                f'<div style="font-size:11px;font-weight:600;color:var(--text-2);margin-bottom:4px">'
                f'{esc(msg["from_user"])} — {(msg.get("created_at") or "")[:16].replace("T", " ")}</div>'
                f'<div style="font-size:13px;color:var(--text-0)">{esc(msg["content"])}</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Input
        new_msg = st.chat_input("Skriv ett meddelande...")
        if new_msg:
            to_user = None if is_broadcast else chat_with
            send_message(username, new_msg, to_user=to_user)
            st.rerun()


@st.fragment(run_every=30)
def _auto_refresh_messages():
    """Auto-refresh message count indicator."""
    pass  # Fragment triggers rerun which updates the sidebar badge
