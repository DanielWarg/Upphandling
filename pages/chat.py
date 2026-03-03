"""AI-chatt — ställ frågor om upphandlingar med lokal LLM."""

import streamlit as st
from datetime import date, datetime

from db import search_procurements, get_analysis, get_pipeline_item


# ---------------------------------------------------------------------------
# Context retrieval — find relevant procurements for the question
# ---------------------------------------------------------------------------
def _find_relevant_procurements(question: str, max_results: int = 5) -> list[dict]:
    """Search procurements relevant to the user's question.

    Strategy:
    1. Extract keywords and search for buyer/keyword-specific hits
    2. Prioritize buyer matches when a specific organization is mentioned
    3. Fill remaining slots with top AI-relevant leads as baseline
    """
    import re as _re
    skip = {
        "vad", "hur", "vilka", "finns", "det", "som", "för", "med", "och",
        "kan", "har", "den", "att", "ett", "ska", "till", "från", "om",
        "alla", "visa", "berätta", "upphandling", "upphandlingar",
        "mest", "bäst", "aktuell", "aktuella", "hast", "viktigaste",
        "vilken", "just", "förslag", "dokument", "förbereda", "lämna",
        "anbud", "bör", "behöver", "tycker", "tror", "kolla",
        "jämför", "jämföra", "jämförelse", "mellan", "två", "båda",
    }
    # Strip Swedish possessive (:s, 's) then punctuation before filtering
    raw = question.lower().split()
    stripped = [_re.sub(r"[:'][s]$", "", w) for w in raw]
    cleaned = [_re.sub(r"[^a-zåäö0-9]", "", w) for w in stripped]
    words = [w for w in cleaned if len(w) > 1 and w not in skip]

    # 1. Keyword-specific search — these get priority
    keyword_hits: list[dict] = []
    seen_ids: set[int] = set()

    for word in words[:6]:
        hits = search_procurements(query=word, min_score=0)
        for h in hits:
            if h["id"] not in seen_ids:
                seen_ids.add(h["id"])
                keyword_hits.append(h)

    # 2. If keyword hits found, prioritize them (sorted by score)
    keyword_hits.sort(key=lambda p: p.get("score", 0), reverse=True)

    # 3. Fill remaining slots with top AI-relevant leads as baseline
    baseline: list[dict] = []
    top_leads = search_procurements(min_score=1, ai_relevance="relevant")
    for h in top_leads:
        if h["id"] not in seen_ids:
            seen_ids.add(h["id"])
            baseline.append(h)

    # Combine: keyword hits first, then baseline
    if keyword_hits:
        # Give keyword hits more slots when they exist
        kw_limit = min(len(keyword_hits), max_results)
        results = keyword_hits[:kw_limit]
        remaining = max_results - len(results)
        if remaining > 0:
            results.extend(baseline[:remaining])
    else:
        results = baseline[:max_results]

    results.sort(key=lambda p: p.get("score", 0), reverse=True)
    return results[:max_results]


def _days_until(deadline_str: str | None) -> str:
    """Calculate days until deadline from a date string."""
    if not deadline_str:
        return "ingen deadline"
    try:
        dl = datetime.strptime(deadline_str[:10], "%Y-%m-%d").date()
        delta = (dl - date.today()).days
        if delta < 0:
            return f"utgangen ({-delta} dagar sedan)"
        if delta == 0:
            return "IDAG"
        return f"{delta} dagar kvar"
    except (ValueError, TypeError):
        return "okant format"


def _build_context(procurements: list[dict]) -> str:
    """Build a text context block from procurements for the LLM."""
    if not procurements:
        return "Inga upphandlingar hittades."

    parts = []
    for p in procurements:
        deadline_raw = (p.get("deadline") or "")[:10]
        deadline_info = _days_until(deadline_raw) if deadline_raw else "ingen deadline angiven"

        part = (
            f"### {p.get('title', 'Utan titel')}\n"
            f"- ID: {p['id']}\n"
            f"- Kopare: {p.get('buyer') or 'Okand'}\n"
            f"- Kalla: {p.get('source', '')}\n"
            f"- HAST-score: {p.get('score', 0)}/100\n"
            f"- Geografi: {p.get('geography') or '-'}\n"
            f"- CPV: {p.get('cpv_codes') or '-'}\n"
            f"- Deadline: {deadline_raw or 'ej angiven'} ({deadline_info})\n"
            f"- Uppskattat varde: {p.get('estimated_value') or 'ej angivet'}"
            f"{' ' + (p.get('currency') or '') if p.get('estimated_value') else ''}\n"
            f"- AI-bedomning: {p.get('ai_relevance') or 'ej bedomd'}\n"
        )
        desc = p.get("description") or ""
        if desc:
            part += f"- Beskrivning: {desc[:500]}\n"

        # Add analysis if available
        analysis = get_analysis(p["id"])
        if analysis:
            if analysis.get("kravsammanfattning"):
                part += f"- Kravsammanfattning: {analysis['kravsammanfattning'][:300]}\n"
            if analysis.get("matchningsanalys"):
                part += f"- Matchningsanalys: {analysis['matchningsanalys'][:300]}\n"

        # Add pipeline info if available
        pipe = get_pipeline_item(p["id"])
        if pipe:
            part += f"- Pipeline-steg: {pipe.get('stage', '-')}\n"
            if pipe.get("assigned_to"):
                part += f"- Tilldelad: {pipe['assigned_to']}\n"

        parts.append(part)

    return "\n---\n".join(parts)


def _build_system_prompt() -> str:
    """Build system prompt with current date."""
    today = date.today().isoformat()
    return f"""Du ar en AI-assistent for HAST Utvecklings saljteam. Dagens datum: {today}.

HAST Utveckling erbjuder: ledarskapsutbildning, chefsutveckling, executive coaching, teamutveckling, organisationsutveckling, kommunikationsutbildning, forandringsledning, seminarier och workshops.

REGLER:
- Svara ALLTID pa svenska
- Basera svaren ENBART pa upphandlingsdata du far — hitta INTE pa information
- HALLUCINATION-FORBUD: Hitta ALDRIG pa siffror, varden, belopp eller datum som inte star i datan. Om "Uppskattat varde: ej angivet" — skriv "varde ej angivet", hitta inte pa ett belopp.
- HAST-score ar en intern relevansscore 0-100, INTE en matchningsgrad i procent
- Var kortfattad och konkret — max 10-15 meningar
- Referera till upphandlingar med titel och ID
- Nar du jamfor deadlines, anvand "dagar kvar"-vardet som ges i datan
- Avsluta med en tydlig rekommendation pa 1-2 rader"""


def _chat_with_llm(question: str, context: str, history: list[dict]) -> str | None:
    """Send question to local LLM with procurement context."""
    import os
    import httpx

    base_url = os.getenv("LLM_BASE_URL", "http://localhost:8081/v1")

    # Build messages: system + last 4 history messages + current question with context
    llm_messages = [{"role": "system", "content": _build_system_prompt()}]

    # Include recent history for continuity (max 4 messages = 2 exchanges)
    for msg in history[-4:]:
        llm_messages.append({"role": msg["role"], "content": msg["content"]})

    # Current question with fresh context
    augmented = (
        f"## Upphandlingsdata fran databasen\n\n{context}\n\n"
        f"---\n\n## Fraga\n{question}"
    )
    llm_messages.append({"role": "user", "content": augmented})

    try:
        resp = httpx.post(
            f"{base_url}/chat/completions",
            json={
                "model": "Ministral-3-14B-Instruct-2512-Q4_K_M.gguf",
                "messages": llm_messages,
                "temperature": 0.2,
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except httpx.ConnectError:
        return "Kunde inte ansluta till AI-servern. Kontrollera att llama-server kor pa port 8081."
    except Exception as e:
        return f"AI-fel: {e}"


# ---------------------------------------------------------------------------
# Streamlit page
# ---------------------------------------------------------------------------
def render_chat():
    """Render the AI chat page."""
    st.markdown(
        '<div class="topbar"><h1>AI-assistent</h1>'
        '<p>Ställ frågor om upphandlingar i systemet</p></div>',
        unsafe_allow_html=True,
    )

    # Initialize chat history
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    # Display chat history
    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ställ en fråga om upphandlingar..."):
        # Show user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Find relevant procurements and build context
        with st.chat_message("assistant"):
            with st.spinner("Söker relevanta upphandlingar..."):
                relevant = _find_relevant_procurements(prompt)
                context = _build_context(relevant)

            with st.spinner("Tänker..."):
                response = _chat_with_llm(
                    prompt,
                    context,
                    st.session_state["chat_messages"],
                )

            if response:
                st.markdown(response)
                st.session_state["chat_messages"].append(
                    {"role": "user", "content": prompt}
                )
                st.session_state["chat_messages"].append(
                    {"role": "assistant", "content": response}
                )

                # Show which procurements were used as context
                if relevant:
                    with st.expander(f"Baserat på {len(relevant)} upphandlingar", expanded=False):
                        for p in relevant:
                            score = p.get("score", 0)
                            title = p.get("title", "")[:70]
                            buyer = p.get("buyer") or ""
                            st.markdown(
                                f'<div style="font-size:12px;padding:4px 0;color:var(--text-1)">'
                                f'<strong>[{score}p]</strong> {title}'
                                f'{f" — {buyer}" if buyer else ""}</div>',
                                unsafe_allow_html=True,
                            )

    # Sidebar: clear chat + example questions
    with st.sidebar:
        st.markdown("---")
        if st.button("Rensa chatt", use_container_width=True):
            st.session_state["chat_messages"] = []
            st.rerun()

        st.markdown(
            '<div style="font-size:11px;color:var(--text-2);margin-top:12px">'
            '<strong>Exempelfrågor:</strong><br>'
            'Vilka upphandlingar kräver UGL?<br>'
            'Sammanfatta kraven i Sundsvalls upphandling<br>'
            'Vilka leads har högst score?<br>'
            'Jämför AP7:s två upphandlingar<br>'
            'Vilka deadlines är närmast?</div>',
            unsafe_allow_html=True,
        )
