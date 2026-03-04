"""Bidrag page — Kanban, Sök, and Företag (company register) tabs."""

import html as html_lib
import json

import streamlit as st

from db import (
    get_pipeline_items,
    search_procurements,
    ensure_pipeline_entry,
    get_all_companies,
    get_company,
    create_company,
    update_company,
    delete_company,
    get_company_matches,
    update_match_status,
    get_bidrag_sources,
    BIDRAG_PIPELINE_STAGES,
    BIDRAG_STAGE_LABELS,
    STAGE_LABELS,
)
from pages.procurements import show_procurement_dialog, badge_cls, card_cls, fmt_value, esc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
BIDRAG_STAGE_COLORS = {
    "hittad": "#71717a",
    "matchad": "#eab308",
    "ansokan_pagar": "#f97316",
    "inskickad": "#3b82f6",
    "beviljad": "#22c55e",
    "avslagen": "#ef4444",
    "beviljad_avslagen": "#22c55e",
}


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------
def render_bidrag():
    """Render bidrag page with Kanban, Sök, and Företag tabs."""
    st.markdown(
        '<div class="topbar"><h1>Bidrag</h1>'
        '<p>Bidragsbevakning, matchning och kundföretag</p></div>',
        unsafe_allow_html=True,
    )

    tab_kanban, tab_search, tab_companies = st.tabs(["Kanban", "Sök", "Företag"])

    with tab_kanban:
        _render_bidrag_kanban()

    with tab_search:
        _render_bidrag_search()

    with tab_companies:
        _render_companies()


# ---------------------------------------------------------------------------
# Kanban tab
# ---------------------------------------------------------------------------
def _render_bidrag_kanban():
    """Bidrag pipeline kanban with 5+1 columns."""
    all_items = get_pipeline_items()
    # Filter to bidrag only
    bidrag_items = [i for i in all_items if i.get("record_type") == "bidrag"]

    # Metrics
    total = len(bidrag_items)
    matchade = len([i for i in bidrag_items if i.get("stage") == "matchad"])
    ansokningar = len([i for i in bidrag_items if i.get("stage") in ("ansokan_pagar", "inskickad")])
    beviljade = len([i for i in bidrag_items if i.get("stage") == "beviljad"])

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Totalt bidrag", total)
    mc2.metric("Matchade", matchade)
    mc3.metric("Ansökningar", ansokningar)
    mc4.metric("Beviljade", beviljade)

    if not bidrag_items:
        st.markdown(
            '<div class="empty"><h3>Inga bidrag i pipeline</h3>'
            '<p>Bidrag läggs till automatiskt vid scraping, eller manuellt via "Sök".</p></div>',
            unsafe_allow_html=True,
        )
        return

    # Group by stage — show 5 columns (beviljad+avslagen merged)
    display_stages = ["hittad", "matchad", "ansokan_pagar", "inskickad", "beviljad_avslagen"]
    stage_titles = {
        "hittad": "Hittad",
        "matchad": "Matchad",
        "ansokan_pagar": "Ansökan pågår",
        "inskickad": "Inskickad",
        "beviljad_avslagen": "Beviljad / Avslagen",
    }

    items_by_stage: dict[str, list[dict]] = {s: [] for s in display_stages}
    for item in bidrag_items:
        stage = item.get("stage", "hittad")
        if stage in ("beviljad", "avslagen"):
            items_by_stage["beviljad_avslagen"].append(item)
        elif stage in items_by_stage:
            items_by_stage[stage].append(item)
        else:
            items_by_stage["hittad"].append(item)

    cols = st.columns(5)
    for col, stage_key in zip(cols, display_stages):
        items = items_by_stage[stage_key]
        title = stage_titles[stage_key]
        color = BIDRAG_STAGE_COLORS.get(stage_key, "#71717a")

        with col:
            st.markdown(
                f'<div style="background:var(--bg-1);border:1px solid var(--border);border-radius:var(--r);'
                f'padding:14px 18px;display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">'
                f'<span style="font-weight:700;font-size:12px;text-transform:uppercase;letter-spacing:0.8px;'
                f'color:{color}">{title}</span>'
                f'<span class="kb-count">{len(items)}</span></div>',
                unsafe_allow_html=True,
            )

            if not items:
                st.markdown(
                    '<div style="padding:24px;text-align:center;color:var(--text-3);font-size:12px">Inga bidrag</div>',
                    unsafe_allow_html=True,
                )

            for item in items[:30]:
                _s = item.get("score", 0) or 0
                _title = esc((item.get("title") or "Utan titel")[:80])
                _buyer = esc(item.get("buyer") or "")
                _source = esc((item.get("source") or "").upper())
                _deadline = (item.get("deadline") or "")[:10]
                _stage = item.get("stage", "")
                _stage_label = BIDRAG_STAGE_LABELS.get(_stage, _stage)

                tags = f'<span class="tag tag-bidrag">BIDRAG</span> '
                tags += f'<span class="tag tag-src">{_source}</span>'
                if _deadline:
                    tags += f' <span class="tag tag-dl">DL {_deadline}</span>'

                st.markdown(
                    f'<div class="card {card_cls(_s)}" style="margin-bottom:2px">'
                    f'  <div class="card-title">{_title}</div>'
                    f'  {"<div class=card-buyer>" + _buyer + "</div>" if _buyer else ""}'
                    f'  <div class="card-foot">'
                    f'    <div>{tags}</div>'
                    f'    <div><span class="badge {badge_cls(_s)}">{_s}</span></div>'
                    f'  </div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Visa", key=f"bk_{item['id']}", use_container_width=True):
                    show_procurement_dialog(item["id"])

            if len(items) > 30:
                overflow = len(items) - 30
                st.markdown(
                    f'<div style="padding:8px;text-align:center;color:var(--text-3);'
                    f'font-size:11px;font-style:italic">...och {overflow} till</div>',
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Sök tab
# ---------------------------------------------------------------------------
def _render_bidrag_search():
    """Search and filter bidrag."""
    current_user = st.session_state["current_user"]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        query = st.text_input("Fritext", placeholder="t.ex. innovation", key="bidrag_search_q")
    with c2:
        source_options = ["Alla"] + get_bidrag_sources()
        source_filter = st.selectbox("Källa", source_options, key="bidrag_search_src")
    with c3:
        score_range = st.slider("Score", 0, 100, (0, 100), key="bidrag_search_score")
    with c4:
        ai_filter = st.selectbox("AI Relevans", ["Alla", "Relevant", "Inte relevant", "Ej bedömd"], key="bidrag_search_ai")

    source_val = "" if source_filter == "Alla" else source_filter
    ai_val_map = {"Alla": "", "Relevant": "relevant", "Inte relevant": "irrelevant", "Ej bedömd": "unassessed"}
    ai_val = ai_val_map[ai_filter]

    results = search_procurements(
        query=query,
        source=source_val,
        min_score=score_range[0],
        max_score=score_range[1],
        ai_relevance=ai_val,
        record_type="bidrag",
    )

    st.markdown(f"**{len(results)}** bidrag")

    if results:
        import pandas as pd
        df = pd.DataFrame(results)[["id", "title", "buyer", "score", "source", "deadline"]]
        df = df.rename(columns={"deadline": "Deadline", "buyer": "Bidragsgivare"})
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("---")
        sel_id = st.number_input("ID att visa/lägga till i pipeline", min_value=1, step=1, key="bidrag_search_id")
        sc1, sc2 = st.columns(2)
        with sc1:
            if st.button("Visa detaljer", key="bidrag_show"):
                show_procurement_dialog(int(sel_id))
        with sc2:
            if st.button("Lägg till i pipeline", key="bidrag_add_pipe"):
                ensure_pipeline_entry(int(sel_id), stage="hittad", assigned_to=current_user["username"])
                st.success("Tillagd i bidragspipeline!")
    else:
        st.markdown(
            '<div class="empty"><h3>Inga bidrag hittades</h3><p>Prova att ändra filtren.</p></div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Företag tab
# ---------------------------------------------------------------------------
def _render_companies():
    """Company register with AI profiling and bidrag matching."""
    current_user = st.session_state["current_user"]

    st.markdown(
        '<div style="font-weight:700;font-size:16px;color:var(--text-0);margin-bottom:12px">'
        'Kundföretag</div>',
        unsafe_allow_html=True,
    )

    # Add company form
    with st.expander("Lägg till företag", expanded=False):
        fc1, fc2 = st.columns(2)
        with fc1:
            new_name = st.text_input("Företagsnamn", key="new_company_name")
        with fc2:
            new_url = st.text_input("Webbadress", key="new_company_url", placeholder="https://...")
        if st.button("Lägg till", key="add_company"):
            if new_name.strip():
                try:
                    create_company(new_name.strip(), new_url.strip(), current_user["username"])
                    st.success(f"Företag '{new_name.strip()}' tillagt!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Kunde inte lägga till: {e}")

    # List companies
    companies = get_all_companies()
    if not companies:
        st.markdown(
            '<div class="empty"><h3>Inga företag registrerade</h3>'
            '<p>Lägg till kundföretag ovan för att börja matcha mot bidrag.</p></div>',
            unsafe_allow_html=True,
        )
        return

    for company in companies:
        cid = company["id"]
        name = company["name"]
        url = company.get("website_url") or ""
        industry = company.get("industry") or ""
        has_profile = bool(company.get("ai_profile"))

        profile_status = "Profil klar" if has_profile else "Ej analyserad"
        profile_color = "#4ade80" if has_profile else "#71717a"

        with st.expander(f"{name} — {industry or 'Okänd bransch'}", expanded=False):
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">'
                f'<span style="font-size:12px;color:var(--text-1)">Webb: {esc(url) or "Ej angiven"}</span>'
                f'<span style="font-size:11px;font-weight:700;color:{profile_color};padding:2px 8px;'
                f'border:1px solid {profile_color}30;border-radius:4px">{profile_status}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # AI Profile
            if has_profile:
                try:
                    profile = json.loads(company["ai_profile"])
                except (json.JSONDecodeError, TypeError):
                    profile = {}

                if profile:
                    st.markdown(
                        f'<div style="background:var(--bg-2);border:1px solid var(--border);'
                        f'border-radius:var(--r-sm);padding:12px;margin-bottom:8px">'
                        f'<div style="font-size:12px;font-weight:700;color:var(--text-0);margin-bottom:6px">AI-profil</div>'
                        f'<div style="font-size:12px;color:var(--text-1)"><b>Bransch:</b> {esc(profile.get("bransch", ""))}</div>'
                        f'<div style="font-size:12px;color:var(--text-1)"><b>Tjanster:</b> {esc(", ".join(profile.get("tjanster", [])))}</div>'
                        f'<div style="font-size:12px;color:var(--text-1)"><b>Kompetenser:</b> {esc(", ".join(profile.get("kompetensomraden", [])))}</div>'
                        f'<div style="font-size:12px;color:var(--text-1)"><b>Nyckelord:</b> {esc(", ".join(profile.get("nyckelord_for_bidrag", [])))}</div>'
                        f'<div style="font-size:12px;color:var(--text-1)"><b>Storlek:</b> {esc(profile.get("storlek_indikation", ""))}</div>'
                        f'<div style="font-size:12px;color:var(--text-1);margin-top:4px"><i>{esc(profile.get("sammanfattning", ""))}</i></div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            # Action buttons
            bc1, bc2, bc3 = st.columns(3)
            with bc1:
                if st.button("Analysera webbplats", key=f"profile_{cid}"):
                    from company_profiler import profile_company
                    with st.spinner("Analyserar..."):
                        result = profile_company(cid)
                        if result:
                            st.success("Profil skapad!")
                            st.rerun()
                        else:
                            st.error("Kunde inte analysera webbplatsen.")
            with bc2:
                if st.button("Sök matchningar", key=f"match_{cid}"):
                    if not has_profile:
                        st.warning("Analysera webbplatsen först.")
                    else:
                        from company_profiler import match_company_to_bidrag
                        with st.spinner("Matchar..."):
                            matches = match_company_to_bidrag(cid)
                            if matches:
                                st.success(f"{len(matches)} matchningar hittades!")
                                st.rerun()
                            else:
                                st.info("Inga matchningar hittades.")
            with bc3:
                if st.button("Ta bort", key=f"del_company_{cid}"):
                    delete_company(cid)
                    st.rerun()

            # Show matches
            matches = get_company_matches(cid)
            if matches:
                st.markdown(
                    '<div style="font-size:12px;font-weight:700;color:var(--text-0);margin:8px 0 4px">'
                    'Matchade bidrag</div>',
                    unsafe_allow_html=True,
                )
                for m in matches:
                    score = m.get("match_score", 0) or 0
                    status = m.get("status", "suggested")
                    status_colors = {"suggested": "#eab308", "accepted": "#4ade80", "dismissed": "#71717a"}
                    status_labels = {"suggested": "Föreslagen", "accepted": "Accepterad", "dismissed": "Avfärdad"}
                    sc = status_colors.get(status, "#71717a")
                    sl = status_labels.get(status, status)

                    st.markdown(
                        f'<div style="background:var(--bg-2);border:1px solid var(--border);'
                        f'border-radius:var(--r-sm);padding:8px 12px;margin-bottom:4px">'
                        f'<div style="display:flex;align-items:center;justify-content:space-between">'
                        f'<div style="font-size:12px;font-weight:600;color:var(--text-0)">{esc(m.get("title", ""))[:70]}</div>'
                        f'<div style="display:flex;align-items:center;gap:6px">'
                        f'<span class="badge {badge_cls(int(score))}">{score:.0f}</span>'
                        f'<span style="font-size:10px;font-weight:700;color:{sc};padding:2px 6px;'
                        f'border:1px solid {sc}30;border-radius:4px">{sl}</span>'
                        f'</div></div>'
                        f'<div style="font-size:11px;color:var(--text-2);margin-top:4px">{esc(m.get("match_reasoning", ""))}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    mc1, mc2, mc3 = st.columns(3)
                    with mc1:
                        if status != "accepted":
                            if st.button("Acceptera", key=f"accept_{m['id']}"):
                                update_match_status(m["id"], "accepted")
                                st.rerun()
                    with mc2:
                        if status != "dismissed":
                            if st.button("Avfärda", key=f"dismiss_{m['id']}"):
                                update_match_status(m["id"], "dismissed")
                                st.rerun()
                    with mc3:
                        if st.button("Visa bidrag", key=f"view_match_{m['id']}"):
                            show_procurement_dialog(m["procurement_id"])
