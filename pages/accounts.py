"""Accounts page — customer accounts with drag & drop dashboard."""

import html as html_lib

import streamlit as st

from db import (
    get_all_accounts, get_account, create_account, update_account,
    get_procurements_for_account, get_contacts, add_contact, delete_contact,
    get_contracts, add_contract, get_user_dashboard, add_to_dashboard,
    remove_from_dashboard, add_watch, get_watches, remove_watch,
    get_pipeline_item, STAGE_LABELS,
)


def esc(s: str) -> str:
    return html_lib.escape(str(s)) if s else ""


def render_accounts():
    """Render accounts page with customer management."""
    current_user = st.session_state["current_user"]
    username = current_user["username"]

    st.markdown(
        '<div class="topbar"><h1>Konton</h1>'
        '<p>Hantera kundkonton och kontakter</p></div>',
        unsafe_allow_html=True,
    )

    # Tab layout: My Dashboard vs All Accounts
    tab_dash, tab_all, tab_new = st.tabs(["Min dashboard", "Alla konton", "Nytt konto"])

    with tab_dash:
        _render_dashboard(username)

    with tab_all:
        _render_all_accounts(username)

    with tab_new:
        _render_new_account()


def _render_dashboard(username: str):
    """User's personal account dashboard."""
    dashboard = get_user_dashboard(username)

    if not dashboard:
        st.markdown(
            '<div class="empty"><h3>Ingen dashboard ännu</h3>'
            '<p>Gå till "Alla konton" och lägg till konton på din dashboard.</p></div>',
            unsafe_allow_html=True,
        )
        return

    # Dynamic grid based on count
    count = len(dashboard)
    if count == 1:
        cols = [st.container()]
    elif count == 2:
        cols = st.columns(2)
    else:
        cols = st.columns(min(count, 3))

    for idx, item in enumerate(dashboard):
        col = cols[idx % len(cols)]
        account_id = item["account_id"]
        account = get_account(account_id)
        if not account:
            continue

        with col:
            procs = get_procurements_for_account(account_id)
            active_procs = [p for p in procs if (p.get("score") or 0) > 0]
            contacts = get_contacts(account_id)
            contracts_list = get_contracts(account_id)

            st.markdown(
                f'<div style="background:var(--bg-2);border:1px solid var(--border);border-radius:var(--r);'
                f'padding:16px;margin-bottom:12px;border-top:3px solid var(--orange)">'
                f'<div style="font-size:16px;font-weight:700;color:var(--text-0)">{esc(account["name"])}</div>'
                f'<div style="font-size:11px;color:var(--text-2);margin-top:4px">{esc(account.get("region") or "")}</div>'
                f'<div style="display:flex;gap:16px;margin-top:12px">'
                f'<div><span style="font-size:20px;font-weight:800;color:var(--text-0)">{len(active_procs)}</span>'
                f'<span style="font-size:11px;color:var(--text-2);margin-left:4px">upphandlingar</span></div>'
                f'<div><span style="font-size:20px;font-weight:800;color:var(--text-0)">{len(contacts)}</span>'
                f'<span style="font-size:11px;color:var(--text-2);margin-left:4px">kontakter</span></div>'
                f'<div><span style="font-size:20px;font-weight:800;color:var(--text-0)">{len(contracts_list)}</span>'
                f'<span style="font-size:11px;color:var(--text-2);margin-left:4px">avtal</span></div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            with st.expander(f"Detaljer — {account['name']}", expanded=count == 1):
                _render_account_detail(account, username)

            if st.button("Ta bort från dashboard", key=f"rm_dash_{account_id}"):
                remove_from_dashboard(username, account_id)
                st.rerun()


def _render_all_accounts(username: str):
    """List all accounts with option to add to dashboard."""
    accounts = get_all_accounts()

    if not accounts:
        st.markdown(
            '<div class="empty"><h3>Inga konton</h3>'
            '<p>Skapa ett nytt konto eller kör scraper för att seeda konton automatiskt.</p></div>',
            unsafe_allow_html=True,
        )
        return

    dashboard_ids = {d["account_id"] for d in get_user_dashboard(username)}

    for acc in accounts:
        on_dash = acc["id"] in dashboard_ids
        procs = get_procurements_for_account(acc["id"])

        c1, c2, c3 = st.columns([4, 1, 1])
        with c1:
            st.markdown(
                f'<div style="padding:8px 0">'
                f'<span style="font-size:14px;font-weight:600;color:var(--text-0)">{esc(acc["name"])}</span>'
                f'<span style="font-size:11px;color:var(--text-2);margin-left:8px">'
                f'{esc(acc.get("region") or "")} | {len(procs)} upphandlingar</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with c2:
            if not on_dash:
                if st.button("Till dashboard", key=f"add_dash_{acc['id']}"):
                    add_to_dashboard(username, acc["id"])
                    st.rerun()
            else:
                st.markdown(
                    '<span style="font-size:11px;color:var(--orange)">Pa dashboard</span>',
                    unsafe_allow_html=True,
                )
        with c3:
            if st.button("Visa", key=f"show_acc_{acc['id']}"):
                st.session_state["selected_account"] = acc["id"]

    # Show selected account detail
    sel = st.session_state.get("selected_account")
    if sel:
        account = get_account(sel)
        if account:
            st.markdown("---")
            _render_account_detail(account, username)


def _render_account_detail(account: dict, username: str):
    """Render full account detail with tabs."""
    account_id = account["id"]

    tab_info, tab_procs, tab_contacts, tab_contracts, tab_watch = st.tabs(
        ["Info", "Upphandlingar", "Kontakter", "Avtal", "Bevakning"]
    )

    with tab_info:
        st.markdown(f"**Namn:** {account['name']}")
        st.markdown(f"**Region:** {account.get('region') or 'Ej angiven'}")
        st.markdown(f"**Buyer-alias:** {account.get('buyer_aliases') or 'Inga'}")
        st.markdown(f"**Anteckningar:** {account.get('notes') or 'Inga'}")

        with st.form(f"edit_account_{account_id}"):
            new_notes = st.text_area("Redigera anteckningar", value=account.get("notes") or "")
            new_aliases = st.text_input("Buyer-alias (kommaseparerade)", value=account.get("buyer_aliases") or "")
            if st.form_submit_button("Spara"):
                update_account(account_id, notes=new_notes, buyer_aliases=new_aliases)
                st.success("Sparat!")
                st.rerun()

    with tab_procs:
        procs = get_procurements_for_account(account_id)
        if procs:
            for p in procs[:20]:
                score = p.get("score", 0) or 0
                pipeline = get_pipeline_item(p["id"])
                stage_label = STAGE_LABELS.get(pipeline.get("stage", ""), "") if pipeline else ""

                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;padding:8px 0;'
                    f'border-bottom:1px solid var(--border-subtle)">'
                    f'<span style="font-size:11px;font-weight:700;color:var(--orange);min-width:30px">{score}</span>'
                    f'<div style="flex:1;font-size:13px;color:var(--text-0)">{esc((p.get("title") or "")[:70])}</div>'
                    f'<span style="font-size:11px;color:var(--text-2)">{(p.get("deadline") or "")[:10]}</span>'
                    f'{"<span style=font-size:11px;color:var(--text-1)>" + stage_label + "</span>" if stage_label else ""}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("Inga upphandlingar länkade till detta konto.")

    with tab_contacts:
        contacts = get_contacts(account_id)
        if contacts:
            for c in contacts:
                st.markdown(
                    f'<div style="padding:8px 0;border-bottom:1px solid var(--border-subtle)">'
                    f'<div style="font-size:13px;font-weight:600;color:var(--text-0)">{esc(c["name"])}</div>'
                    f'<div style="font-size:11px;color:var(--text-2)">'
                    f'{esc(c.get("title") or "")} | {esc(c.get("email") or "")} | {esc(c.get("phone") or "")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Ta bort", key=f"del_contact_{c['id']}"):
                    delete_contact(c["id"])
                    st.rerun()

        with st.form(f"new_contact_{account_id}"):
            st.markdown("**Ny kontakt**")
            nc1, nc2 = st.columns(2)
            with nc1:
                c_name = st.text_input("Namn")
                c_title = st.text_input("Titel")
            with nc2:
                c_email = st.text_input("E-post")
                c_phone = st.text_input("Telefon")
            c_notes = st.text_input("Anteckning")
            if st.form_submit_button("Lägg till kontakt"):
                if c_name.strip():
                    add_contact(account_id, c_name.strip(), c_title, c_email, c_phone, c_notes)
                    st.rerun()

    with tab_contracts:
        contracts_list = get_contracts(account_id)
        if contracts_list:
            for ct in contracts_list:
                from datetime import datetime
                end_date = ct.get("contract_end") or ""
                color = "#71717a"
                if end_date:
                    try:
                        days_left = (datetime.fromisoformat(end_date) - datetime.now()).days
                        if days_left < 90:
                            color = "#ef4444"
                        elif days_left < 180:
                            color = "#eab308"
                        else:
                            color = "#22c55e"
                    except ValueError:
                        pass

                st.markdown(
                    f'<div style="padding:10px 14px;margin-bottom:6px;background:var(--bg-2);'
                    f'border:1px solid var(--border);border-radius:var(--r-sm);border-left:3px solid {color}">'
                    f'<div style="font-size:13px;font-weight:600;color:var(--text-0)">{esc(ct["title"])}</div>'
                    f'<div style="font-size:11px;color:var(--text-2);margin-top:4px">'
                    f'Start: {ct.get("contract_start") or "?"} | Slut: {end_date or "?"} | Option: {ct.get("option_end") or "?"}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        with st.form(f"new_contract_{account_id}"):
            st.markdown("**Nytt avtal**")
            ct_title = st.text_input("Avtalstitel")
            ct1, ct2, ct3 = st.columns(3)
            with ct1:
                ct_start = st.date_input("Startdatum", value=None)
            with ct2:
                ct_end = st.date_input("Slutdatum", value=None)
            with ct3:
                ct_option = st.date_input("Optionsdatum", value=None)
            ct_notes = st.text_input("Anteckningar")
            if st.form_submit_button("Lägg till avtal"):
                if ct_title.strip():
                    add_contract(
                        account_id, ct_title.strip(),
                        contract_start=str(ct_start) if ct_start else "",
                        contract_end=str(ct_end) if ct_end else "",
                        option_end=str(ct_option) if ct_option else "",
                        notes=ct_notes, created_by=username,
                    )
                    st.rerun()

    with tab_watch:
        watches = get_watches(username)
        account_watches = [w for w in watches if w.get("account_id") == account_id]

        if account_watches:
            st.markdown("Aktiva bevakningar for detta konto:")
            for w in account_watches:
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"Bevakning aktiv sedan {w['created_at'][:10]}")
                with c2:
                    if st.button("Avbryt", key=f"rm_watch_{w['id']}"):
                        remove_watch(w["id"])
                        st.rerun()
        else:
            if st.button("Bevaka detta konto", key=f"watch_acc_{account_id}"):
                add_watch(username, "account", account_id=account_id)
                st.success("Bevakning aktiverad!")
                st.rerun()


def _render_new_account():
    """Form to create a new account."""
    with st.form("new_account"):
        name = st.text_input("Kontonamn")
        c1, c2 = st.columns(2)
        with c1:
            region = st.text_input("Region")
        with c2:
            aliases = st.text_input("Buyer-alias (kommaseparerade)")
        notes = st.text_area("Anteckningar")

        if st.form_submit_button("Skapa konto"):
            if name.strip():
                create_account(name.strip(), aliases, region, notes)
                st.success(f"Konto '{name}' skapat!")
                st.rerun()
            else:
                st.error("Namn krävs.")
