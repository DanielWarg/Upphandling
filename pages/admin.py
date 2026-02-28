"""Admin page — manual scraping, analysis, data cleanup and system status."""

import streamlit as st
from db import (
    get_connection, get_all_procurements, get_stats, get_pipeline_summary,
    get_all_accounts, deduplicate_procurements, init_db,
)


def render_admin():
    current_user = st.session_state.get("current_user")
    if not current_user or current_user.get("role") != "admin":
        st.error("Atkomst nekad — admin-behorighet kravs.")
        return

    st.markdown(
        '<div class="topbar"><h1>Admin</h1>'
        '<p>Datahamtning, analys och systemstatus</p></div>',
        unsafe_allow_html=True,
    )

    tab_fetch, tab_analysis, tab_cleanup, tab_users, tab_status = st.tabs([
        "Datahamtning", "Scoring & Analys", "Datarensning", "Anvandare & Bevakningar", "Systemstatus",
    ])

    with tab_fetch:
        _render_fetch_section()

    with tab_analysis:
        _render_analysis_section()

    with tab_cleanup:
        _render_cleanup_section()

    with tab_users:
        _render_users_section()

    with tab_status:
        _render_status_section()


# ---------------------------------------------------------------------------
# Section 1 — Data fetching
# ---------------------------------------------------------------------------

def _render_fetch_section():
    st.subheader("Hamta upphandlingar")

    sources = st.multiselect(
        "Valj kallor",
        options=["ted", "kommers", "eavrop"],
        default=["ted", "kommers", "eavrop"],
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Hamta upphandlingar", use_container_width=True):
            _run_scrape(sources)

    with col2:
        if st.button("Kor hela pipelinen", use_container_width=True):
            _run_full_pipeline(sources)


def _run_scrape(sources: list[str]):
    from run_scrapers import scrape_sources, run_dedup
    with st.status("Hamtar upphandlingar...", expanded=True) as status:
        def on_progress(msg: str):
            st.write(msg)

        counts = scrape_sources(sources or None, on_progress=on_progress)
        dedup_removed = run_dedup(on_progress=on_progress)

        total = sum(counts.values())
        status.update(label=f"Klart — {total} hamtade, {dedup_removed} dubbletter borttagna", state="complete")


def _run_full_pipeline(sources: list[str]):
    from run_scrapers import (
        scrape_sources, run_dedup, score_all, run_ai_prefilter,
        run_deep_analysis, create_pipeline_entries, link_accounts,
        check_watch_lists,
    )
    from db import archive_expired_procurements, cross_source_deduplicate, create_deadline_calendar_events

    with st.status("Kor hela pipelinen...", expanded=True) as status:
        def on_progress(msg: str):
            st.write(msg)

        on_progress("Steg 1/10: Hamtar upphandlingar...")
        scrape_sources(sources or None, on_progress=on_progress)

        on_progress("Steg 2/10: Deduplicerar (inom kalla)...")
        run_dedup(on_progress=on_progress)

        on_progress("Steg 3/10: Cross-source dedup...")
        cross_removed = cross_source_deduplicate()
        on_progress(f"Cross-source dubbletter borttagna: {cross_removed}")

        on_progress("Steg 4/10: Arkiverar utgangna...")
        archived = archive_expired_procurements()
        on_progress(f"Arkiverade: {archived}")

        on_progress("Steg 5/10: Scorar...")
        score_all(on_progress=on_progress)

        on_progress("Steg 6/10: AI-prefilter...")
        try:
            run_ai_prefilter(on_progress=on_progress)
        except Exception as e:
            on_progress(f"AI-prefilter kunde inte koras: {e}")

        on_progress("Steg 7/10: Djupanalys...")
        try:
            run_deep_analysis(on_progress=on_progress)
        except Exception as e:
            on_progress(f"Djupanalys kunde inte koras: {e}")

        on_progress("Steg 8/10: Pipeline-poster & kontolänkning...")
        create_pipeline_entries(on_progress=on_progress)
        link_accounts(on_progress=on_progress)

        on_progress("Steg 9/10: Bevakningslistor...")
        check_watch_lists(on_progress=on_progress)

        on_progress("Steg 10/10: Kalenderhandelser...")
        cal_count = create_deadline_calendar_events()
        on_progress(f"Kalenderhandelser skapade: {cal_count}")

        status.update(label="Hela pipelinen klar", state="complete")


# ---------------------------------------------------------------------------
# Section 2 — Scoring & Analysis
# ---------------------------------------------------------------------------

def _render_analysis_section():
    st.subheader("Scoring & AI-analys")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Scora alla", use_container_width=True):
            from run_scrapers import score_all
            with st.status("Scorar...", expanded=True) as status:
                def on_progress(msg: str):
                    st.write(msg)
                count = score_all(on_progress=on_progress)
                status.update(label=f"Scorade {count} upphandlingar", state="complete")

    with col2:
        if st.button("Kor AI-prefilter", use_container_width=True):
            from run_scrapers import run_ai_prefilter
            with st.status("Kor AI-prefilter...", expanded=True) as status:
                def on_progress(msg: str):
                    st.write(msg)
                try:
                    run_ai_prefilter(on_progress=on_progress)
                    status.update(label="AI-prefilter klar", state="complete")
                except Exception as e:
                    status.update(label=f"Fel: {e}", state="error")

    if st.button("Kor djupanalys", use_container_width=True):
        from run_scrapers import run_deep_analysis
        with st.status("Kor djupanalys...", expanded=True) as status:
            def on_progress(msg: str):
                st.write(msg)
            try:
                run_deep_analysis(on_progress=on_progress)
                status.update(label="Djupanalys klar", state="complete")
            except Exception as e:
                status.update(label=f"Fel: {e}", state="error")


# ---------------------------------------------------------------------------
# Section 3 — Data cleanup
# ---------------------------------------------------------------------------

def _render_cleanup_section():
    st.subheader("Datarensning")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Arkivera utgangna**")
        st.caption("Markerar upphandlingar med passerad deadline som 'expired'")
        if st.button("Arkivera utgangna", use_container_width=True):
            from db import archive_expired_procurements
            count = archive_expired_procurements()
            st.success(f"Arkiverade {count} utgangna upphandlingar")

    with col2:
        st.markdown("**Rensa gamla**")
        st.caption("Tar bort upphandlingar som varit expired i >180 dagar")
        if st.button("Rensa gamla expired", use_container_width=True):
            from db import purge_old_expired
            count = purge_old_expired()
            st.success(f"Borttagna: {count} gamla expired-poster")

    with col3:
        st.markdown("**Cross-source dedup**")
        st.caption("Slar ihop dubbletter mellan kallor (fuzzy title+buyer)")
        if st.button("Kor cross-source dedup", use_container_width=True):
            from db import cross_source_deduplicate
            count = cross_source_deduplicate()
            st.success(f"Borttagna cross-source dubbletter: {count}")


# ---------------------------------------------------------------------------
# Section 4 — Users & Watches
# ---------------------------------------------------------------------------

def _render_users_section():
    st.subheader("Anvandare & Bevakningar")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Synka anvandare**")
        st.caption("Synka users-tabellen fran config/users.yaml")
        if st.button("Synka anvandare", use_container_width=True):
            from db import sync_users_from_yaml
            count = sync_users_from_yaml()
            st.success(f"Synkade {count} anvandare")

    with col2:
        st.markdown("**Skapa default-bevakningar**")
        st.caption("Skapar nyckelords- och kontobevakningar for alla anvandare")
        if st.button("Skapa default-bevakningar", use_container_width=True):
            from db import sync_users_from_yaml, seed_default_watches, seed_accounts
            # Ensure accounts exist first
            seed_accounts()
            sync_users_from_yaml()
            conn = get_connection()
            users = conn.execute("SELECT username FROM users").fetchall()
            conn.close()
            total = 0
            for u in users:
                total += seed_default_watches(u["username"])
            st.success(f"Skapade {total} bevakningar for {len(users)} anvandare")

    with col3:
        st.markdown("**Skapa kalenderhandelser**")
        st.caption("Auto-skapar deadline-events for upphandlingar inom 30 dagar")
        if st.button("Skapa kalenderhandelser", use_container_width=True):
            from db import create_deadline_calendar_events
            count = create_deadline_calendar_events()
            st.success(f"Skapade {count} kalenderhandelser")

    # Show current users table
    st.markdown("---")
    st.markdown("**Registrerade anvandare**")
    conn = get_connection()
    users = conn.execute("SELECT username, display_name, role, email FROM users ORDER BY role, username").fetchall()
    conn.close()
    if users:
        for u in users:
            role_label = {"kam": "KAM", "saljchef": "Saljchef"}.get(u["role"], u["role"])
            st.text(f"  {u['display_name']} ({u['username']}) — {role_label} — {u['email'] or '-'}")
    else:
        st.caption("Inga anvandare synkade annu. Klicka 'Synka anvandare' ovan.")

    # Show watch stats
    conn = get_connection()
    watch_stats = conn.execute("""
        SELECT user_username, watch_type, COUNT(*) as c
        FROM watch_list WHERE active = 1
        GROUP BY user_username, watch_type
        ORDER BY user_username
    """).fetchall()
    conn.close()
    if watch_stats:
        st.markdown("**Bevakningar per anvandare**")
        for w in watch_stats:
            st.text(f"  {w['user_username']}: {w['c']} {w['watch_type']}-bevakningar")


# ---------------------------------------------------------------------------
# Section 5 — System status
# ---------------------------------------------------------------------------

def _render_status_section():
    st.subheader("Systemstatus")

    conn = get_connection()

    # Per-source counts
    source_rows = conn.execute(
        "SELECT source, COUNT(*) as c FROM procurements GROUP BY source ORDER BY c DESC"
    ).fetchall()

    # Analysis counts
    total = conn.execute("SELECT COUNT(*) as c FROM procurements").fetchone()["c"]
    analyzed = conn.execute(
        "SELECT COUNT(*) as c FROM procurements WHERE ai_relevance IS NOT NULL"
    ).fetchone()["c"]

    # Active vs expired
    active = conn.execute(
        "SELECT COUNT(*) as c FROM procurements WHERE (deadline IS NULL OR deadline >= date('now')) AND status != 'expired'"
    ).fetchone()["c"]
    expired = conn.execute(
        "SELECT COUNT(*) as c FROM procurements WHERE status = 'expired' OR (deadline IS NOT NULL AND deadline < date('now'))"
    ).fetchone()["c"]

    # Missing deadlines
    no_deadline = conn.execute(
        "SELECT COUNT(*) as c FROM procurements WHERE deadline IS NULL"
    ).fetchone()["c"]

    # Pipeline
    pipeline_count = conn.execute("SELECT COUNT(*) as c FROM pipeline").fetchone()["c"]

    # Accounts with linked procurements
    accounts_total = conn.execute("SELECT COUNT(*) as c FROM accounts").fetchone()["c"]
    accounts_linked = conn.execute(
        "SELECT COUNT(DISTINCT account_id) as c FROM procurements WHERE account_id IS NOT NULL"
    ).fetchone()["c"]

    # Users, contacts, watches
    users_count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    contacts_count = conn.execute("SELECT COUNT(*) as c FROM contacts").fetchone()["c"]
    watches_count = conn.execute("SELECT COUNT(*) as c FROM watch_list WHERE active = 1").fetchone()["c"]
    calendar_count = conn.execute("SELECT COUNT(*) as c FROM calendar_events").fetchone()["c"]

    # Duplicate groups (within source)
    dupe_groups = conn.execute("""
        SELECT COUNT(*) as c FROM (
            SELECT source, title, buyer
            FROM procurements
            GROUP BY source, title, buyer
            HAVING COUNT(*) > 1
        )
    """).fetchone()["c"]

    # Field completeness
    fields = ["title", "buyer", "geography", "deadline", "description", "cpv_codes", "estimated_value"]
    completeness = {}
    for field in fields:
        if field == "estimated_value":
            filled = conn.execute(f"SELECT COUNT(*) as c FROM procurements WHERE {field} IS NOT NULL AND {field} > 0").fetchone()["c"]
        else:
            filled = conn.execute(f"SELECT COUNT(*) as c FROM procurements WHERE {field} IS NOT NULL AND {field} != ''").fetchone()["c"]
        completeness[field] = round(filled / total * 100, 1) if total > 0 else 0

    conn.close()

    # Display metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Totalt upphandlingar", total)
    c2.metric("Analyserade", f"{analyzed}/{total}")
    c3.metric("Aktiva", active)
    c4.metric("Utan deadline", no_deadline)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Pipeline-poster", pipeline_count)
    c6.metric("Konton", f"{accounts_linked}/{accounts_total} lankade")
    c7.metric("Duplikatgrupper", dupe_groups)
    c8.metric("Expired", expired)

    c9, c10, c11, c12 = st.columns(4)
    c9.metric("Anvandare", users_count)
    c10.metric("Kontakter", contacts_count)
    c11.metric("Bevakningar", watches_count)
    c12.metric("Kalenderhandelser", calendar_count)

    # Per-source breakdown
    st.markdown("---")
    st.markdown("**Upphandlingar per kalla**")
    for row in source_rows:
        st.text(f"  {row['source']}: {row['c']}")

    # Field completeness
    st.markdown("**Datakvalitet — faltifyllnad**")
    for field, pct in completeness.items():
        bar_filled = int(pct / 5)
        bar = "#" * bar_filled + "-" * (20 - bar_filled)
        st.text(f"  {field:20s} [{bar}] {pct}%")
