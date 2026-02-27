"""Pipeline kanban page with drag & drop using streamlit-sortables."""

import streamlit as st
from streamlit_sortables import sort_items

from db import (
    get_pipeline_items, get_pipeline_summary, update_pipeline_stage,
    update_pipeline_assignment, update_pipeline_details,
    ensure_pipeline_entry, get_procurement, get_procurement_notes,
    add_procurement_note, PIPELINE_STAGES, STAGE_LABELS, STAGE_PROBABILITIES,
)


STAGE_COLORS = {
    "bevakad": "#71717a",
    "kvalificerad": "#eab308",
    "anbud_pagaende": "#f97316",
    "inskickad": "#3b82f6",
    "vunnen": "#22c55e",
    "forlorad": "#ef4444",
}


def _fmt_value(val) -> str:
    if not val:
        return ""
    try:
        v = float(val)
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M"
        if v >= 1_000:
            return f"{v/1_000:.0f}k"
        return f"{v:.0f}"
    except (ValueError, TypeError):
        return ""


def _fmt_weighted(val, prob) -> str:
    if not val:
        return ""
    try:
        weighted = float(val) * (prob or 0) / 100
        return _fmt_value(weighted)
    except (ValueError, TypeError):
        return ""


def render_pipeline():
    """Render the pipeline kanban page."""
    current_user = st.session_state["current_user"]
    username = current_user["username"]
    is_chef = current_user["role"] == "saljchef"

    st.markdown(
        '<div class="topbar"><h1>Säljpipeline</h1>'
        '<p>Dra upphandlingar mellan steg för att uppdatera status</p></div>',
        unsafe_allow_html=True,
    )

    # Summary metrics
    summary = get_pipeline_summary()
    total_weighted = sum(s.get("weighted_value", 0) for s in summary.values())
    total_count = sum(s.get("count", 0) for s in summary.values())
    active_stages = [s for s in PIPELINE_STAGES if s not in ("vunnen", "forlorad")]
    active_weighted = sum(summary.get(s, {}).get("weighted_value", 0) for s in active_stages)

    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Totalt i pipeline", total_count)
    mc2.metric("Aktiv pipeline (viktat)", f"{_fmt_value(active_weighted)} SEK")
    mc3.metric("Vunna", summary.get("vunnen", {}).get("count", 0))
    mc4.metric("Förlorade", summary.get("forlorad", {}).get("count", 0))

    # Get all pipeline items
    all_items = get_pipeline_items()

    # Filter for KAM: only their assigned + unassigned
    if not is_chef:
        all_items = [i for i in all_items if i.get("assigned_to") in (username, None)]

    # Group by stage
    items_by_stage: dict[str, list[dict]] = {s: [] for s in PIPELINE_STAGES}
    for item in all_items:
        stage = item.get("stage", "bevakad")
        if stage in items_by_stage:
            items_by_stage[stage].append(item)

    # Build sortable items for streamlit-sortables
    # Each item represented as string key "proc_ID"
    stage_items: list[dict] = []
    item_lookup: dict[str, dict] = {}

    for stage in PIPELINE_STAGES:
        items_in_stage = items_by_stage[stage]
        keys = []
        for item in items_in_stage:
            key = f"{item['id']}|{item.get('title', 'Utan titel')[:50]}"
            keys.append(key)
            item_lookup[key] = item
        stage_items.append({"header": STAGE_LABELS[stage], "items": keys})

    # Render sortable kanban
    sorted_items = sort_items(stage_items, multi_containers=True, direction="horizontal")

    # Detect changes and save
    if sorted_items:
        for idx, stage in enumerate(PIPELINE_STAGES):
            if idx < len(sorted_items):
                for key in sorted_items[idx]["items"]:
                    if key in item_lookup:
                        item = item_lookup[key]
                        old_stage = item.get("stage", "bevakad")
                        if old_stage != stage:
                            update_pipeline_stage(item["id"], stage, updated_by=username)
                            st.toast(f"Flyttade till {STAGE_LABELS[stage]}")
                            st.rerun()

    st.markdown("---")

    # Pipeline detail cards below kanban
    st.markdown("### Detaljer")

    # Stage filter
    selected_stage = st.selectbox(
        "Filtrera steg",
        ["Alla"] + [STAGE_LABELS[s] for s in PIPELINE_STAGES],
        key="pipeline_stage_filter",
    )

    stage_filter = None
    if selected_stage != "Alla":
        stage_filter = next(s for s, l in STAGE_LABELS.items() if l == selected_stage)

    filtered_items = all_items
    if stage_filter:
        filtered_items = [i for i in all_items if i.get("stage") == stage_filter]

    if not filtered_items:
        st.markdown(
            '<div class="empty"><h3>Inga upphandlingar i pipeline</h3>'
            '<p>Upphandlingar läggs automatiskt till vid scraping, eller manuellt via detaljvyn.</p></div>',
            unsafe_allow_html=True,
        )
        return

    for item in filtered_items:
        stage = item.get("stage", "bevakad")
        color = STAGE_COLORS.get(stage, "#71717a")
        title = item.get("title", "Utan titel")
        buyer = item.get("buyer", "")
        assigned = item.get("assigned_to") or "Ej tilldelad"
        deadline = (item.get("deadline") or "")[:10]
        est_val = item.get("pipeline_value") or item.get("estimated_value")
        prob = item.get("probability", 0)
        weighted = _fmt_weighted(est_val, prob)

        with st.expander(f"{title[:80]} — {STAGE_LABELS[stage]}", expanded=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"**Köpare:** {buyer}")
                st.markdown(f"**Deadline:** {deadline or 'Ej angiven'}")
                st.markdown(f"**Tilldelad:** {assigned}")
            with c2:
                st.markdown(f"**Värde:** {_fmt_value(est_val) or 'Ej angivet'} SEK")
                st.markdown(f"**Sannolikhet:** {prob}%")
                st.markdown(f"**Viktat värde:** {weighted or '-'} SEK")
            with c3:
                st.markdown(
                    f'<div style="display:inline-block;padding:4px 10px;border-radius:6px;'
                    f'background:{color}20;color:{color};font-weight:700;font-size:12px">'
                    f'{STAGE_LABELS[stage]}</div>',
                    unsafe_allow_html=True,
                )

            # Edit controls
            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                new_stage = st.selectbox(
                    "Ändra steg",
                    PIPELINE_STAGES,
                    index=PIPELINE_STAGES.index(stage),
                    format_func=lambda s: STAGE_LABELS[s],
                    key=f"stage_{item['id']}",
                )
                if new_stage != stage:
                    update_pipeline_stage(item["id"], new_stage, updated_by=username)
                    st.rerun()

            with ec2:
                if is_chef:
                    new_assigned = st.text_input(
                        "Tilldela KAM",
                        value=item.get("assigned_to") or "",
                        key=f"assign_{item['id']}",
                    )
                    if new_assigned != (item.get("assigned_to") or ""):
                        update_pipeline_assignment(
                            item["id"],
                            new_assigned if new_assigned else None,
                            updated_by=username,
                        )
                        st.rerun()

            with ec3:
                new_val = st.number_input(
                    "Uppskattat värde (SEK)",
                    value=float(est_val) if est_val else 0.0,
                    min_value=0.0,
                    step=100000.0,
                    key=f"val_{item['id']}",
                )

            # Notes section
            notes = get_procurement_notes(item["id"])
            if notes:
                st.markdown("**Anteckningar:**")
                for note in notes[:5]:
                    st.markdown(
                        f'<div style="font-size:12px;color:var(--text-1);padding:4px 0">'
                        f'<strong>{note["user_username"]}</strong> ({note["created_at"][:10]}): '
                        f'{note["content"]}</div>',
                        unsafe_allow_html=True,
                    )

            new_note = st.text_input(
                "Lägg till anteckning",
                key=f"note_{item['id']}",
                placeholder="Skriv en anteckning...",
            )
            if st.button("Spara anteckning", key=f"save_note_{item['id']}"):
                if new_note.strip():
                    add_procurement_note(item["id"], username, new_note.strip())
                    st.rerun()
