"""AI-chatt — ställ frågor om upphandlingar med lokal LLM."""

import streamlit as st

from db import search_procurements, get_analysis, get_pipeline_item


# ---------------------------------------------------------------------------
# Context retrieval — find relevant procurements for the question
# ---------------------------------------------------------------------------
def _find_relevant_procurements(question: str, max_results: int = 5) -> list[dict]:
    """Search procurements relevant to the user's question."""
    # Extract meaningful words (skip short/common ones)
    skip = {
        "vad", "hur", "vilka", "finns", "det", "som", "för", "med", "och",
        "kan", "har", "den", "att", "ett", "ska", "till", "från", "om",
        "alla", "visa", "berätta", "upphandling", "upphandlingar",
    }
    words = [w for w in question.lower().split() if len(w) > 2 and w not in skip]

    results: list[dict] = []
    seen_ids: set[int] = set()

    # Search each keyword
    for word in words[:6]:
        hits = search_procurements(query=word, min_score=1)
        for h in hits:
            if h["id"] not in seen_ids:
                seen_ids.add(h["id"])
                results.append(h)

    # If no keyword hits, fall back to all scored procurements
    if not results:
        results = search_procurements(min_score=1)

    # Sort by score descending and limit
    results.sort(key=lambda p: p.get("score", 0), reverse=True)
    return results[:max_results]


def _build_context(procurements: list[dict]) -> str:
    """Build a text context block from procurements for the LLM."""
    if not procurements:
        return "Inga upphandlingar hittades."

    parts = []
    for p in procurements:
        part = (
            f"### {p.get('title', 'Utan titel')}\n"
            f"- ID: {p['id']}\n"
            f"- Köpare: {p.get('buyer') or 'Okänd'}\n"
            f"- Källa: {p.get('source', '')}\n"
            f"- Score: {p.get('score', 0)}\n"
            f"- Geografi: {p.get('geography') or '-'}\n"
            f"- CPV: {p.get('cpv_codes') or '-'}\n"
            f"- Deadline: {(p.get('deadline') or '-')[:10]}\n"
            f"- AI-bedömning: {p.get('ai_relevance') or 'ej bedömd'}\n"
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


CHAT_SYSTEM_PROMPT = """Du är en AI-assistent för HAST Utvecklings säljteam. Du hjälper till att svara på frågor om upphandlingar som finns i systemet.

HAST Utveckling erbjuder: ledarskapsutbildning, chefsutveckling, executive coaching, teamutveckling, organisationsutveckling, kommunikationsutbildning, förändringsledning, seminarier och workshops.

Regler:
- Svara ALLTID på svenska
- Basera svaren på den upphandlingsdata du får — hitta inte på information
- Var konkret och handlingsorienterad
- Om du inte hittar relevant information, säg det tydligt
- Referera till specifika upphandlingar med titel och ID när det är relevant
- Håll svaren lagom korta men informativa"""


def _chat_with_llm(messages: list[dict], context: str) -> str | None:
    """Send chat messages to local LLM with procurement context."""
    import os
    import httpx

    base_url = os.getenv("LLM_BASE_URL", "http://localhost:8081/v1")

    # Build message list with context injected
    llm_messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]

    # Add context as first user message if this is the first exchange
    for i, msg in enumerate(messages):
        if i == len(messages) - 1 and msg["role"] == "user":
            # Last user message — inject context
            augmented = (
                f"## Relevanta upphandlingar från databasen\n\n{context}\n\n"
                f"---\n\n## Användarens fråga\n{msg['content']}"
            )
            llm_messages.append({"role": "user", "content": augmented})
        else:
            llm_messages.append(msg)

    try:
        resp = httpx.post(
            f"{base_url}/chat/completions",
            json={
                "model": "Ministral-3-14B-Instruct-2512-Q4_K_M.gguf",
                "messages": llm_messages,
                "temperature": 0.3,
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except httpx.ConnectError:
        return "Kunde inte ansluta till AI-servern. Kontrollera att llama-server körs på port 8081."
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
        st.session_state["chat_messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Find relevant procurements and build context
        with st.chat_message("assistant"):
            with st.spinner("Söker relevanta upphandlingar..."):
                relevant = _find_relevant_procurements(prompt)
                context = _build_context(relevant)

            with st.spinner("Tänker..."):
                response = _chat_with_llm(
                    st.session_state["chat_messages"],
                    context,
                )

            if response:
                st.markdown(response)
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
