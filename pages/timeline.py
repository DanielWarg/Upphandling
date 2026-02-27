"""Contract timeline page — visual timeline with color-coded urgency."""

import html as html_lib
from datetime import datetime

import streamlit as st

from db import get_all_contracts, get_all_accounts, get_contracts


def esc(s: str) -> str:
    return html_lib.escape(str(s)) if s else ""


def _urgency_color(end_date: str | None) -> str:
    if not end_date:
        return "#71717a"
    try:
        days_left = (datetime.fromisoformat(end_date) - datetime.now()).days
        if days_left < 0:
            return "#ef4444"
        elif days_left < 90:
            return "#ef4444"
        elif days_left < 180:
            return "#eab308"
        else:
            return "#22c55e"
    except ValueError:
        return "#71717a"


def _days_until(date_str: str | None) -> str:
    if not date_str:
        return "?"
    try:
        days = (datetime.fromisoformat(date_str) - datetime.now()).days
        if days < 0:
            return f"{abs(days)}d sedan"
        return f"{days}d kvar"
    except ValueError:
        return "?"


def render_timeline():
    """Render contract timeline page."""
    st.markdown(
        '<div class="topbar"><h1>Avtalstidslinje</h1>'
        '<p>Visuell översikt av avtal och avtalsutgångar</p></div>',
        unsafe_allow_html=True,
    )

    all_contracts = get_all_contracts()

    if not all_contracts:
        st.markdown(
            '<div class="empty"><h3>Inga avtal registrerade</h3>'
            '<p>Lägg till avtal på kontosidorna.</p></div>',
            unsafe_allow_html=True,
        )
        return

    # Summary metrics
    now = datetime.now()
    expiring_90 = [c for c in all_contracts if c.get("contract_end") and _urgency_color(c["contract_end"]) == "#ef4444"]
    expiring_180 = [c for c in all_contracts if c.get("contract_end") and _urgency_color(c["contract_end"]) == "#eab308"]

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Totalt avtal", len(all_contracts))
    mc2.metric("Utgår <3 mån", len(expiring_90))
    mc3.metric("Utgår <6 mån", len(expiring_180))
    mc4.metric("Aktiva", len(all_contracts) - len(expiring_90))

    # Filter
    accounts = get_all_accounts()
    account_names = ["Alla"] + [a["name"] for a in accounts]
    selected_account = st.selectbox("Filtrera konto", account_names)

    filtered = all_contracts
    if selected_account != "Alla":
        filtered = [c for c in all_contracts if c.get("account_name") == selected_account]

    # Sort by end date
    filtered.sort(key=lambda c: c.get("contract_end") or "9999")

    # Visual timeline
    st.markdown("### Tidslinje")

    for contract in filtered:
        color = _urgency_color(contract.get("contract_end"))
        title = esc(contract.get("title", ""))
        account_name = esc(contract.get("account_name", ""))
        start = contract.get("contract_start") or "?"
        end = contract.get("contract_end") or "?"
        option = contract.get("option_end") or ""
        days_label = _days_until(contract.get("contract_end"))
        notes = esc(contract.get("notes") or "")

        # Calculate bar width (proportion of total timeline)
        bar_style = ""
        if contract.get("contract_start") and contract.get("contract_end"):
            try:
                start_d = datetime.fromisoformat(contract["contract_start"])
                end_d = datetime.fromisoformat(contract["contract_end"])
                total_days = (end_d - start_d).days or 1
                elapsed = (now - start_d).days
                pct = max(0, min(100, elapsed / total_days * 100))
                bar_style = f'width:{pct}%'
            except ValueError:
                bar_style = "width:50%"
        else:
            bar_style = "width:50%"

        st.markdown(
            f'<div style="padding:14px 16px;margin-bottom:8px;background:var(--bg-2);'
            f'border:1px solid var(--border);border-radius:var(--r-sm);border-left:4px solid {color}">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<div>'
            f'<div style="font-size:14px;font-weight:600;color:var(--text-0)">{title}</div>'
            f'<div style="font-size:11px;color:var(--text-2);margin-top:2px">{account_name}</div>'
            f'</div>'
            f'<div style="text-align:right">'
            f'<div style="font-size:13px;font-weight:700;color:{color}">{days_label}</div>'
            f'<div style="font-size:11px;color:var(--text-2)">{start} — {end}</div>'
            f'</div>'
            f'</div>'
            f'<div style="margin-top:10px;background:var(--bg-3);border-radius:3px;height:6px;overflow:hidden">'
            f'<div style="{bar_style};height:100%;background:{color};border-radius:3px"></div>'
            f'</div>'
            f'{f"<div style=font-size:11px;color:var(--text-2);margin-top:6px>Option: {option}</div>" if option else ""}'
            f'{f"<div style=font-size:11px;color:var(--text-1);margin-top:4px>{notes}</div>" if notes else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Predictions section
    st.markdown("---")
    st.markdown("### Förväntade upphandlingar")
    try:
        from predictions import predict_reprocurements
        predictions = predict_reprocurements()
        if predictions:
            for pred in predictions:
                st.markdown(
                    f'<div style="padding:10px 14px;margin-bottom:4px;background:var(--bg-2);'
                    f'border:1px solid var(--border);border-radius:var(--r-sm)">'
                    f'<div style="font-size:13px;font-weight:600;color:var(--text-0)">{esc(pred.get("title", ""))}</div>'
                    f'<div style="font-size:11px;color:var(--text-2);margin-top:2px">'
                    f'{esc(pred.get("account", ""))} | Snitt-intervall: {pred.get("avg_years", "?")} år | '
                    f'Nästa beräknad: {pred.get("predicted_date", "?")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("Inte tillräckligt med historisk data för prediktioner ännu.")
    except ImportError:
        st.info("Prediktionsmodulen är inte tillgänglig.")
