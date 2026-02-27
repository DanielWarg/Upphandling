"""Integrations management page — säljchef only."""

import html as html_lib

import streamlit as st


def esc(s: str) -> str:
    return html_lib.escape(str(s)) if s else ""


def render_integrations():
    """Render integrations page (säljchef only)."""
    current_user = st.session_state["current_user"]
    if current_user["role"] != "saljchef":
        st.warning("Denna sida är bara tillgänglig för säljchefer.")
        return

    st.markdown(
        '<div class="topbar"><h1>Integrationer</h1>'
        '<p>Anslut externa tjänster för att synka data</p></div>',
        unsafe_allow_html=True,
    )

    from integrations import ALL_INTEGRATIONS

    for IntCls in ALL_INTEGRATIONS:
        integration = IntCls()
        status = integration.sync_status()
        connected = status.get("connected", False)
        status_color = "#22c55e" if connected else "#71717a"
        status_label = "Ansluten" if connected else "Ej ansluten"

        st.markdown(
            f'<div style="padding:16px 20px;margin-bottom:12px;background:var(--bg-2);'
            f'border:1px solid var(--border);border-radius:var(--r);'
            f'border-left:3px solid {status_color}">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<div>'
            f'<div style="font-size:16px;font-weight:700;color:var(--text-0)">{esc(integration.name)}</div>'
            f'<div style="font-size:12px;color:var(--text-2);margin-top:4px">{esc(integration.description)}</div>'
            f'</div>'
            f'<div style="text-align:right">'
            f'<div style="font-size:12px;font-weight:700;color:{status_color}">{status_label}</div>'
            f'</div>'
            f'</div>'
            f'<div style="font-size:11px;color:var(--text-1);margin-top:8px">{esc(status.get("message", ""))}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown(
        '<div style="font-size:12px;color:var(--text-2)">'
        'Konfigurera integrationer genom att sätta API-nycklar i <code>.env</code>: '
        'NOTION_API_KEY, HUBSPOT_API_KEY</div>',
        unsafe_allow_html=True,
    )
