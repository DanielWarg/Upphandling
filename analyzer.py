"""AI-driven procurement analysis using local Ollama models."""

from __future__ import annotations

import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET

import httpx
from dotenv import load_dotenv
from google import genai

from db import get_procurement, get_analysis, save_analysis, get_all_procurements, update_ai_relevance

logger = logging.getLogger(__name__)

load_dotenv()

# ---------------------------------------------------------------------------
# Hogia context
# ---------------------------------------------------------------------------
HOGIA_CONTEXT = """
Hogia Public Transport Systems (Hogia PTS) levererar IT-lösningar för kollektivtrafik i Norden.

PRODUKTER (detalj):
- PubTrans: Centralt driftsstöd och trafikledningssystem. Hanterar realtidsövervakning av fordonsflotta, avvikelsehantering, trafikantinformation vid störning, och koppling mot AVL (Automatic Vehicle Location). Marknadsledande i Norden.
- Realtidsinformation: Passagerarinformation i realtid — hållplatsskyltar (DPI), appar, webb, skärmar ombord. Stödjer SIRI och GTFS-RT.
- Reseplanerare: Multimodal reseplanering med stöd för NeTEx och GTFS. Integration med nationella reseplaneraren (Samtrafikens ResRobot).
- Beordringssystem: Beordring och bemanning av förare, tjänsteplanering, turlistor. Optimering av personalresurser.
- Anropsstyrd trafik: Komplett lösning för serviceresor, färdtjänst, sjukresor, skolskjuts. Bokningssystem, optimering, samordningscentral, fordonskommunikation.

STANDARDER OCH PROTOKOLL:
- NeTEx (Nordic NeTEx Profile) — hållplats- och tidtabelldata (Hogia stödjer fullt)
- SIRI — realtidsinformation (kärnan i PubTrans)
- GTFS / GTFS-RT — öppna resedata (export/import)
- ITxPT — fordons-IT-arkitektur (ombordssystem, FMS)
- BoB (Biljett och Betalning) — integration mot biljettsystem
- BODS / EU-regulatorik — öppna data-krav

REFERENSKUNDER (med leveransdetalj):
- Västtrafik: PubTrans, realtid, reseplanerare — en av Sveriges största RKM
- Skånetrafiken: PubTrans, realtid, anropsstyrd trafik — komplett leverans
- Svealandstrafiken/VL (Västmanland): PubTrans, realtid
- Länstrafiken Kronoberg: PubTrans, beordring
- Region Uppsala: Anropsstyrd trafik, serviceresor
- Hallandstrafiken: PubTrans, realtid

STYRKOR I UPPHANDLINGSKONTEXT:
- 30+ års erfarenhet av svensk kollektivtrafik-IT
- Komplett produktportfölj — kan leverera helhetsåtagande
- Beprövade integrationer mot befintliga biljettsystem, fordons-IT
- Stark på standarder (NeTEx, SIRI, GTFS) — ofta krav i upphandlingar
- Nordisk marknadsledare inom PubTrans/trafikledning
- Lokal support och förvaltning — svensk organisation
- Hög kundnöjdhet och långa kundrelationer

SVAGHETER/GAP ATT VARA MEDVETEN OM:
- Biljettsystem: Hogia har integration men inget eget biljettsystem (samarbetar med partners)
- Ren hårdvara (fordon, skyltar): Hogia levererar mjukvara, inte hårdvara
- Internationellt: Främst nordiskt fokus, begränsade internationella referenser
"""

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Du är en senior upphandlingsrådgivare och expert på svensk offentlig upphandling, specialiserad på kollektivtrafik-IT. Du arbetar för Hogia Public Transport Systems.

DIN EXPERTIS OMFATTAR:
- Lagen om offentlig upphandling (LOU) och LUF (försörjningssektorn — gäller kollektivtrafik)
- Upphandlingsförfaranden: öppet, selektivt, förhandlat med/utan föregående annonsering, konkurrenspräglad dialog, innovationspartnerskap
- Utvärderingsmodeller: bästa pris-kvalitetsförhållande, lägsta pris, fast pris med kvalitetstävlan
- Kvalificeringskrav vs tilldelningskriterier (ska-krav vs bör-krav)
- Ramavtal (enskild leverantör, rangordning, förnyad konkurrensutsättning)
- Överprövning och avtalsspärr (10 dagars regel)
- SKI-ramavtal och Kammarkollegiets ramavtal (Programvaror & Tjänster, IT-drift)
- ESPD (European Single Procurement Document)
- Dynamiska inköpssystem (DIS)
- Branschspecifikt: RKM-upphandlingar, Samtrafikens standarder, kollektivtrafiklagen

Svara ALLTID på svenska. Var konkret och handlingsorienterad — inga generella platityder.

Du ska returnera ett JSON-objekt med exakt dessa fyra nycklar:
- "kravsammanfattning": Sammanfattning av krav och scope (markdown)
- "matchningsanalys": Hur väl Hogias produkter matchar kraven (markdown)
- "prisstrategi": Rekommenderad prisstrategi och affärsmodell (markdown)
- "anbudshjalp": Konkreta tips för att skriva ett starkt anbud (markdown)

Returnera BARA JSON-objektet, ingen annan text runtomkring."""

USER_PROMPT_TEMPLATE = """Analysera denna upphandling åt Hogia Public Transport Systems:

## Upphandlingsdata
- Titel: {title}
- Köpare: {buyer}
- Geografi: {geography}
- CPV-koder: {cpv_codes}
- Publicerad: {published_date}
- Deadline: {deadline}
- Uppskattat värde: {estimated_value} {currency}
- Källa: {source}

## Beskrivning från upphandlingen
{description}

{full_text_section}

## Om Hogia
{hogia_context}

## Analysera enligt följande struktur:

### 1. Kravsammanfattning
- Vad upphandlas exakt? (system, tjänst, integration, drift?)
- Scope och volym (antal fordon, hållplatser, resenärer, kommuner?)
- Avtalsperiod och tidsplan (implementering, optionsår)
- Ska-krav (obligatoriska) vs bör-krav (mervärderade)
- Tekniska krav (standarder, integrationer, prestanda)
- Organisatoriska krav (bemanning, support, SLA)
- OBS: Om detta INTE handlar om IT/system utan om ren trafikering (köra bussar), säg det tydligt.

### 2. Matchningsanalys
- Gå igenom VARJE Hogia-produkt (PubTrans, Realtid, Reseplanerare, Beordring, Anropsstyrd trafik) och bedöm relevans
- Identifiera vilka krav Hogia täcker direkt, vilka som kräver anpassning, och vilka gap som finns
- Bedöm om Hogia behöver underleverantörer/partners för delar
- Ge en tydlig matchningsgrad: **Hög** (>70% täckning), **Medel** (40-70%), **Låg** (<40%), eller **Ej relevant** (fel domän)
- Lista konkreta styrkor och svagheter mot just denna upphandlings krav

### 3. Prisstrategi
- Rekommendera prismodell baserat på upphandlingens karaktär:
  - Licensmodell (per fordon, per hållplats, per användare, flat fee)
  - SaaS vs on-premise
  - Implementeringskostnad + löpande förvaltning
  - Eventuella optioner och tilläggsmoduler
- Bedöm prisnivå relativt marknaden om möjligt
- Identifiera vad som driver kostnaden (integrationer, datamigration, utbildning)
- Tips kring prissättning givet utvärderingsmodellen (om känd)

### 4. Anbudshjälp
- Vilka av Hogias referenskunder bör lyftas och varför?
- Konkreta differentierande argument mot konkurrenter (Hastus, Trapeze, IVU, Remix, etc.)
- Vilka risker bör adresseras proaktivt i anbudet?
- Tips för kvalitetsdelen: hur beskriva implementation, projektorganisation, stöd vid driftsättning
- Formella saker att tänka på (ESPD, referenskrav, ekonomisk kapacitet, yrkesmässig kapacitet)

Svara med ett JSON-objekt."""


# ---------------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------------
REQUIRED_ANALYSIS_KEYS = {"kravsammanfattning", "matchningsanalys", "prisstrategi", "anbudshjalp"}


def _parse_analysis_json(raw_text: str) -> dict | None:
    """Try to extract and validate a JSON analysis from LLM raw response.

    Returns the parsed dict if valid, or None if parsing/validation fails.
    Handles both valid JSON and malformed JSON with raw newlines in strings.
    """
    # Strip markdown code fences if present
    stripped = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
    stripped = re.sub(r"\s*```\s*$", "", stripped)

    # Try standard JSON parsing first
    json_match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            if _validate_analysis_dict(data):
                return data
        except json.JSONDecodeError:
            pass

    # Fallback: extract sections by key boundaries (handles raw newlines in strings)
    return _extract_sections_by_keys(raw_text)


def _validate_analysis_dict(data: dict) -> bool:
    """Check that dict has all required analysis keys with non-empty string values."""
    if not isinstance(data, dict):
        return False
    if not REQUIRED_ANALYSIS_KEYS.issubset(data.keys()):
        return False
    return all(isinstance(data[k], str) and data[k].strip() for k in REQUIRED_ANALYSIS_KEYS)


def _extract_sections_by_keys(raw_text: str) -> dict | None:
    """Extract analysis sections from malformed JSON by finding key boundaries.

    Handles cases where LLMs produce JSON with unescaped newlines in string values.
    """
    keys = ["kravsammanfattning", "matchningsanalys", "prisstrategi", "anbudshjalp"]
    positions = []
    for key in keys:
        match = re.search(rf'"{key}"\s*:\s*"', raw_text, re.IGNORECASE)
        if not match:
            return None
        positions.append((key, match.end()))

    result = {}
    for i, (key, start) in enumerate(positions):
        if i < len(positions) - 1:
            # Content runs until just before the next key's quote
            next_start = positions[i + 1][1]
            region = raw_text[start:next_start]
            # Find the last `",` or `"` before the next key definition
            trim_match = re.search(r'"\s*,?\s*"[^"]*"\s*:\s*"$', region, re.DOTALL)
            if trim_match:
                content = region[:trim_match.start()]
            else:
                content = region.rstrip()
                # Strip trailing ", or " and key preamble
                content = re.sub(r'"\s*,?\s*$', '', content)
        else:
            # Last key: content runs until closing `"}` or end
            region = raw_text[start:]
            # Find the last `"` before `}`
            close_match = re.search(r'"\s*}\s*(?:```\s*)?$', region, re.DOTALL)
            if close_match:
                content = region[:close_match.start()]
            else:
                content = region.rstrip().rstrip('"}` \n\r\t')

        result[key] = content.strip()

    if not all(result.get(k, "").strip() for k in REQUIRED_ANALYSIS_KEYS):
        return None

    return result


def get_client() -> genai.Client:
    """Create a Gemini client from GEMINI_API_KEY env var."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY saknas. Sätt den i .env-filen.")
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# TED full notice text
# ---------------------------------------------------------------------------
def _extract_text_from_xml(xml_bytes: bytes) -> str:
    """Extract readable text from TED eForms XML."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return ""

    # Remove namespace prefixes for easier searching
    text_parts = []
    for elem in root.iter():
        if elem.text and elem.text.strip():
            text_parts.append(elem.text.strip())
        if elem.tail and elem.tail.strip():
            text_parts.append(elem.tail.strip())

    return "\n".join(text_parts)


def fetch_full_notice_text(pub_number: str) -> str | None:
    """Fetch the full notice XML from TED and extract text."""
    if not pub_number:
        return None

    url = f"https://ted.europa.eu/en/notice/{pub_number}/xml"
    try:
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        if resp.status_code != 200:
            return None
        return _extract_text_from_xml(resp.content)
    except httpx.HTTPError:
        return None


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------
def analyze_procurement(procurement_id: int, force: bool = False, model: str = "ministral-3-14b") -> dict | None:
    """Run AI analysis on a procurement using local Ollama. Returns analysis dict or None on error.

    Uses cached result if available unless force=True.
    """
    # Check cache
    if not force:
        cached = get_analysis(procurement_id)
        if cached:
            return cached

    # Get procurement data
    proc = get_procurement(procurement_id)
    if not proc:
        return None

    # Fetch full text for TED notices
    full_text = None
    if proc.get("source") == "ted" and proc.get("source_id"):
        full_text = fetch_full_notice_text(proc["source_id"])

    full_text_section = ""
    if full_text:
        # Limit to ~8k chars for Ollama's smaller context window
        trimmed = full_text[:8000]
        full_text_section = f"## Fullständig notistext\n{trimmed}"

    # Build prompt
    user_prompt = USER_PROMPT_TEMPLATE.format(
        title=proc.get("title") or "Ej angiven",
        buyer=proc.get("buyer") or "Ej angiven",
        geography=proc.get("geography") or "Ej angiven",
        cpv_codes=proc.get("cpv_codes") or "Ej angivet",
        published_date=proc.get("published_date") or "Ej angivet",
        deadline=proc.get("deadline") or "Ej angiven",
        estimated_value=proc.get("estimated_value") or "Ej angivet",
        currency=proc.get("currency") or "",
        source=proc.get("source") or "Okänd",
        description=proc.get("description") or "Ingen beskrivning tillgänglig.",
        full_text_section=full_text_section,
        hogia_context=HOGIA_CONTEXT,
    )

    # Try function calling first (structured output), fall back to text + parse
    result = _call_ollama_tools(SYSTEM_PROMPT, user_prompt, model=model)

    if result is None or not _validate_analysis_dict(result):
        logger.info("Function calling failed for procurement %d, falling back to text mode", procurement_id)
        raw_text = _call_ollama(SYSTEM_PROMPT, user_prompt, model=model)
        if raw_text:
            result = _parse_analysis_json(raw_text)

    if result is None:
        logger.error("All analysis methods failed for procurement %d", procurement_id)
        result = {
            "kravsammanfattning": "",
            "matchningsanalys": "Analysen misslyckades.",
            "prisstrategi": "Analysen misslyckades.",
            "anbudshjalp": "Analysen misslyckades.",
        }

    analysis = {
        "procurement_id": procurement_id,
        "full_notice_text": full_text,
        "kravsammanfattning": result.get("kravsammanfattning", ""),
        "matchningsanalys": result.get("matchningsanalys", ""),
        "prisstrategi": result.get("prisstrategi", ""),
        "anbudshjalp": result.get("anbudshjalp", ""),
        "model": model,
        "input_tokens": None,
        "output_tokens": None,
    }

    # Save to cache
    save_analysis(procurement_id, analysis)

    # Return the saved version (includes created_at etc.)
    return get_analysis(procurement_id)


def analyze_all_relevant(min_score: int = 1, force: bool = False, model: str = "ministral-3-14b") -> int:
    """Run Ollama deep analysis on all relevant procurements.

    Processes procurements with score >= min_score and ai_relevance == "relevant".
    Skips those that already have a cached analysis unless force=True.
    Returns number of procurements analyzed.
    """
    procs = get_all_procurements()
    analyzed = 0

    for p in procs:
        score = p.get("score") or 0
        if score < min_score:
            continue
        if p.get("ai_relevance") != "relevant":
            continue
        if not force and get_analysis(p["id"]) is not None:
            continue

        logger.info("Deep analysis for procurement %d: %s", p["id"], p.get("title", "")[:80])
        print(f"  Analyserar: {p.get('title', '')[:70]}...")

        try:
            result = analyze_procurement(p["id"], force=force, model=model)
            if result is not None:
                analyzed += 1
        except Exception as e:
            logger.error("Deep analysis failed for procurement %d: %s", p["id"], e)
            print(f"  Fel: {e}")

    logger.info("Deep analysis: %d procurements analyzed", analyzed)
    print(f"Ollama-djupanalys: {analyzed} upphandlingar analyserade")
    return analyzed


def get_cached_analysis(procurement_id: int) -> dict | None:
    """Return cached analysis or None."""
    return get_analysis(procurement_id)


# ---------------------------------------------------------------------------
# AI Prefilter — cheap relevance check using Gemini
# ---------------------------------------------------------------------------
PREFILTER_SYSTEM_PROMPT = """Du är expert på svensk kollektivtrafik-IT. Bedöm om denna upphandling
är relevant för Hogia PTS (leverantör av realtidssystem, trafikledning,
reseplanerare, beordring, anropsstyrd trafik för kollektivtrafik).

RELEVANT: IT-system för kollektivtrafik, serviceresor, passagerarinformation, färdtjänst, sjukresor, skolskjuts
IRRELEVANT: Drift av bussar/tåg, kulturella institutioner, generell IT utan transport, hårdvaruinköp, kontorsmaterial

Returnera ENBART JSON: {"relevant": true/false, "reasoning": "kort motivering på svenska"}"""


def _parse_prefilter_json(raw_text: str) -> dict | None:
    """Parse AI prefilter JSON response. Returns dict with 'relevant' and 'reasoning', or None."""
    # Try markdown code block first
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        json_str = json_match.group(0) if json_match else None

    if not json_str:
        return None

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None
    if "relevant" not in data:
        return None
    if not isinstance(data["relevant"], bool):
        return None

    return {
        "relevant": data["relevant"],
        "reasoning": str(data.get("reasoning", "")),
    }


# ---------------------------------------------------------------------------
# Local LLM — OpenAI-compatible API (Ollama or llama-server)
# ---------------------------------------------------------------------------
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")

ANALYSIS_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_analysis",
        "description": "Lämna in upphandlingsanalys med fyra sektioner",
        "parameters": {
            "type": "object",
            "properties": {
                "kravsammanfattning": {
                    "type": "string",
                    "description": "Sammanfattning av krav och scope (markdown)",
                },
                "matchningsanalys": {
                    "type": "string",
                    "description": "Hur väl Hogias produkter matchar kraven (markdown)",
                },
                "prisstrategi": {
                    "type": "string",
                    "description": "Rekommenderad prisstrategi och affärsmodell (markdown)",
                },
                "anbudshjalp": {
                    "type": "string",
                    "description": "Konkreta tips för att skriva ett starkt anbud (markdown)",
                },
            },
            "required": ["kravsammanfattning", "matchningsanalys", "prisstrategi", "anbudshjalp"],
        },
    },
}


def _call_ollama(system_prompt: str, user_msg: str, model: str = "ministral-3-14b", json_mode: bool = False) -> str | None:
    """Call local LLM via OpenAI-compatible API. Returns response text or None."""
    try:
        payload = {
            "model": model,
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


def _call_ollama_tools(system_prompt: str, user_msg: str, model: str = "ministral-3-14b") -> dict | None:
    """Call local LLM with function calling to get structured JSON output.

    Returns parsed dict with the 4 analysis keys, or None on error.
    """
    try:
        resp = httpx.post(
            f"{LLM_BASE_URL}/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.15,
                "tools": [ANALYSIS_TOOL],
                "tool_choice": {"type": "function", "function": {"name": "submit_analysis"}},
            },
            timeout=600,
        )
        resp.raise_for_status()
        data = resp.json()
        # Extract tool call arguments
        tool_calls = data["choices"][0]["message"].get("tool_calls", [])
        if tool_calls:
            args_str = tool_calls[0]["function"]["arguments"]
            return json.loads(args_str)
        # Fallback: some servers put it in content
        content = data["choices"][0]["message"].get("content", "")
        if content:
            return _parse_analysis_json(content)
        return None
    except Exception as e:
        logger.error("LLM tools error: %s", e)
        return None


def ollama_prefilter_procurement(proc_id: int, model: str = "ministral-3-14b") -> dict | None:
    """Run AI relevance check on a single procurement using local Ollama. Returns {'relevant': bool, 'reasoning': str} or None."""
    proc = get_procurement(proc_id)
    if not proc:
        return None

    title = proc.get("title") or ""
    buyer = proc.get("buyer") or ""
    cpv = proc.get("cpv_codes") or ""
    desc = (proc.get("description") or "")[:300]

    user_msg = f"Titel: {title}\nKöpare: {buyer}\nCPV: {cpv}\nBeskrivning: {desc}"

    raw_text = _call_ollama(PREFILTER_SYSTEM_PROMPT, user_msg, model=model)
    if raw_text is None:
        return None

    parsed = _parse_prefilter_json(raw_text)
    if parsed is None:
        logger.warning("Ollama prefilter JSON parse failed for proc %d: %s", proc_id, raw_text[:200])
        return None

    relevance = "relevant" if parsed["relevant"] else "irrelevant"
    update_ai_relevance(proc_id, relevance, parsed["reasoning"])

    return parsed


def ollama_prefilter_all(model: str = "ministral-3-14b", force: bool = False, min_score: int = 1) -> int:
    """Run AI prefilter on procurements using local Ollama.

    Only processes procurements with score >= min_score (default 1, i.e. those
    that passed the sector gate). No sleep between calls (local model).
    Skips already-assessed procurements unless force=True.
    Returns number of procurements filtered as irrelevant.
    """
    procs = get_all_procurements()
    filtered = 0
    checked = 0
    skipped_low = 0

    for p in procs:
        # Skip procurements that didn't pass sector gate
        score = p.get("score") or 0
        if score < min_score:
            skipped_low += 1
            continue

        # Skip already assessed unless force
        if not force and p.get("ai_relevance") is not None:
            continue

        result = ollama_prefilter_procurement(p["id"], model=model)
        if result is not None:
            checked += 1
            if not result["relevant"]:
                filtered += 1

    logger.info("Ollama prefilter: checked %d, filtered %d as irrelevant, skipped %d (low score)", checked, filtered, skipped_low)
    print(f"Ollama-prefilter: {checked} bedömda, {filtered} filtrerade som irrelevanta, {skipped_low} hoppade över (score < {min_score})")
    return filtered


def ai_prefilter_procurement(proc_id: int) -> dict | None:
    """Run AI relevance check on a single procurement. Returns {'relevant': bool, 'reasoning': str} or None."""
    proc = get_procurement(proc_id)
    if not proc:
        return None

    title = proc.get("title") or ""
    buyer = proc.get("buyer") or ""
    cpv = proc.get("cpv_codes") or ""
    desc = (proc.get("description") or "")[:300]

    user_msg = f"Titel: {title}\nKöpare: {buyer}\nCPV: {cpv}\nBeskrivning: {desc}"

    try:
        client = get_client()
    except ValueError:
        logger.warning("GEMINI_API_KEY saknas — hoppar över AI-prefilter")
        return None

    max_retries = 3
    raw_text = ""
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    {"role": "user", "parts": [{"text": PREFILTER_SYSTEM_PROMPT + "\n\n" + user_msg}]},
                ],
            )
            raw_text = response.text or ""
            break
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait = 10 * (attempt + 1)
                logger.info("Rate limited on proc %d, waiting %ds (attempt %d/%d)", proc_id, wait, attempt + 1, max_retries)
                print(f"  Rate limit — väntar {wait}s...")
                time.sleep(wait)
            else:
                logger.error("AI prefilter API error for proc %d: %s", proc_id, e)
                return None

    parsed = _parse_prefilter_json(raw_text)
    if parsed is None:
        logger.warning("AI prefilter JSON parse failed for proc %d: %s", proc_id, raw_text[:200])
        return None

    relevance = "relevant" if parsed["relevant"] else "irrelevant"
    update_ai_relevance(proc_id, relevance, parsed["reasoning"])

    return parsed


def ai_prefilter_all(threshold: int = 0, force: bool = False) -> int:
    """Run AI prefilter on all procurements with score >= threshold.

    Skips already-assessed procurements unless force=True.
    Returns number of procurements filtered as irrelevant.
    """
    try:
        get_client()
    except ValueError:
        logger.warning("GEMINI_API_KEY saknas — hoppar över AI-prefilter")
        return 0

    procs = get_all_procurements()
    filtered = 0
    checked = 0

    for p in procs:
        score = p.get("score") or 0
        if score < threshold:
            continue

        # Skip already assessed unless force
        if not force and p.get("ai_relevance") is not None:
            continue

        result = ai_prefilter_procurement(p["id"])
        if result is not None:
            checked += 1
            if not result["relevant"]:
                filtered += 1
            # Respect rate limits — pause between API calls
            time.sleep(4)

    logger.info("AI prefilter: checked %d, filtered %d as irrelevant", checked, filtered)
    print(f"AI-prefilter: {checked} bedömda, {filtered} filtrerade som irrelevanta")
    return filtered
