"""AI-driven company profiling and bidrag matching via Ministral."""

import json
import logging
import os
import re

import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone

import db

logger = logging.getLogger(__name__)

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8081/v1")

PROFILE_SYSTEM_PROMPT = """Du är en affärsanalytiker. Analysera denna företagswebbplats och returnera JSON med följande fält:
- bransch: företagets primära bransch (sträng)
- tjanster: lista med tjänster företaget erbjuder
- kompetensomraden: lista med kompetensområden
- nyckelord_for_bidrag: lista med nyckelord relevanta för att matcha mot bidrag/utlysningar (maximal 15)
- storlek_indikation: "litet", "medelstort" eller "stort" baserat på tillgänglig information
- sammanfattning: kort sammanfattning av företaget (max 2 meningar)

Returnera ENBART giltig JSON, inget annat."""

MATCH_SYSTEM_PROMPT = """Du är en bidragsrådgivare. Bedöm hur väl detta bidrag/utlysning matchar företagets profil.

Returnera JSON med:
- match_score: 0-100 (hur väl bidraget passar företaget)
- reasoning: kort motivering (max 3 meningar) på svenska

Bedöm baserat på:
- Överensstämmelse mellan företagets tjänster/kompetenser och bidragets krav
- Om företagets bransch är relevant
- Om företaget troligen uppfyller formella krav

Returnera ENBART giltig JSON, inget annat."""


def _call_llm(system_prompt: str, user_msg: str, json_mode: bool = True) -> str | None:
    """Call local LLM via OpenAI-compatible API. Returns response text or None."""
    try:
        payload: dict = {
            "model": "Ministral-3-14B-Instruct-2512-Q4_K_M.gguf",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.1,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        resp = httpx.post(
            f"{LLM_BASE_URL}/chat/completions",
            json=payload,
            timeout=600,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("LLM error: %s", e)
        return None


def fetch_website_text(url: str) -> str | None:
    """Fetch website and extract text content. Returns up to ~5000 chars."""
    if not url:
        return None
    # Ensure https
    if not url.startswith("http"):
        url = "https://" + url
    try:
        resp = httpx.get(
            url,
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HASTProfiling/1.0)"},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # Remove script/style
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        # Clean up whitespace
        text = re.sub(r"\s+", " ", text)
        return text[:5000]
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None


def profile_company(company_id: int, on_progress: callable = None) -> dict | None:
    """Analyze a company's website and create an AI profile.

    Returns the parsed profile dict, or None on failure.
    """
    company = db.get_company(company_id)
    if not company:
        return None

    if on_progress:
        on_progress(f"Hämtar webbplats: {company.get('website_url', '')}...")

    website_text = fetch_website_text(company.get("website_url", ""))
    if not website_text:
        if on_progress:
            on_progress("Kunde inte hämta webbplatsen.")
        return None

    if on_progress:
        on_progress("Analyserar med AI...")

    user_msg = f"Företag: {company['name']}\nWebbplats: {company.get('website_url', '')}\n\nInnehåll:\n{website_text}"
    result = _call_llm(PROFILE_SYSTEM_PROMPT, user_msg)
    if not result:
        return None

    try:
        profile = json.loads(result)
    except json.JSONDecodeError:
        logger.error("Failed to parse profile JSON: %s", result[:200])
        return None

    now = datetime.now(timezone.utc).isoformat()
    db.update_company(
        company_id,
        ai_profile=json.dumps(profile, ensure_ascii=False),
        ai_profile_updated_at=now,
        industry=profile.get("bransch", ""),
    )

    if on_progress:
        on_progress("Profil sparad!")

    return profile


def _keyword_score(keywords: list[str], text: str) -> float:
    """Simple keyword overlap score 0-100."""
    if not keywords or not text:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    return min(100.0, (hits / max(len(keywords), 1)) * 100)


def match_company_to_bidrag(company_id: int, on_progress: callable = None) -> list[dict]:
    """Match a company against all bidrag. Returns list of match dicts."""
    company = db.get_company(company_id)
    if not company:
        return []

    profile_json = company.get("ai_profile")
    if not profile_json:
        if on_progress:
            on_progress("Företaget har ingen AI-profil. Analysera webbplatsen först.")
        return []

    try:
        profile = json.loads(profile_json)
    except (json.JSONDecodeError, TypeError):
        return []

    keywords = profile.get("nyckelord_for_bidrag", [])
    if not keywords:
        if on_progress:
            on_progress("Inga nyckelord i profilen.")
        return []

    # Get all bidrag
    bidrag = db.search_procurements(record_type="bidrag")
    if not bidrag:
        if on_progress:
            on_progress("Inga bidrag i databasen.")
        return []

    if on_progress:
        on_progress(f"Matchar mot {len(bidrag)} bidrag (nyckelord)...")

    # Step 1: keyword scoring
    scored = []
    for b in bidrag:
        text = f"{b.get('title', '')} {b.get('description', '')}".strip()
        kw_score = _keyword_score(keywords, text)
        if kw_score > 0:
            scored.append((b, kw_score))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_candidates = scored[:5]

    if not top_candidates:
        if on_progress:
            on_progress("Inga matchningar hittades.")
        return []

    # Step 2: AI matching for top candidates
    matches = []
    profile_summary = (
        f"Bransch: {profile.get('bransch', '')}\n"
        f"Tjänster: {', '.join(profile.get('tjanster', []))}\n"
        f"Kompetenser: {', '.join(profile.get('kompetensomraden', []))}\n"
        f"Nyckelord: {', '.join(keywords)}"
    )

    for i, (b, kw_score) in enumerate(top_candidates):
        if on_progress:
            on_progress(f"AI-matchning {i+1}/{len(top_candidates)}: {b['title'][:50]}...")

        user_msg = (
            f"FÖRETAGSPROFIL:\n{profile_summary}\n\n"
            f"BIDRAG/UTLYSNING:\n"
            f"Titel: {b.get('title', '')}\n"
            f"Bidragsgivare: {b.get('buyer', '')}\n"
            f"Beskrivning: {b.get('description', 'Ingen beskrivning')}\n"
            f"Deadline: {b.get('deadline', 'Ej angiven')}"
        )

        result = _call_llm(MATCH_SYSTEM_PROMPT, user_msg)
        if result:
            try:
                match_data = json.loads(result)
                score = float(match_data.get("match_score", kw_score))
                reasoning = match_data.get("reasoning", "")
            except (json.JSONDecodeError, ValueError, TypeError):
                score = kw_score
                reasoning = f"Nyckelordsmatchning: {kw_score:.0f}%"
        else:
            score = kw_score
            reasoning = f"Nyckelordsmatchning: {kw_score:.0f}%"

        db.save_bidrag_match(b["id"], company_id, score, reasoning)
        matches.append({
            "procurement_id": b["id"],
            "title": b.get("title", ""),
            "match_score": score,
            "reasoning": reasoning,
        })

    if on_progress:
        on_progress(f"Klar! {len(matches)} matchningar sparade.")

    return matches


def match_all_companies(on_progress: callable = None) -> int:
    """Run matching for all companies with AI profiles. Returns total match count."""
    companies = db.get_all_companies()
    total = 0
    for company in companies:
        if not company.get("ai_profile"):
            continue
        if on_progress:
            on_progress(f"Matchar: {company['name']}...")
        matches = match_company_to_bidrag(company["id"])
        total += len(matches)
    if on_progress:
        on_progress(f"Klar! {total} matchningar totalt.")
    return total
