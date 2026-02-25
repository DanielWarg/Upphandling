"""AI-driven procurement analysis using Gemini 2.0 Flash."""

from __future__ import annotations

import json
import logging
import os
import re
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
    """Try to extract and validate a JSON analysis from Gemini's raw response.

    Returns the parsed dict if valid, or None if parsing/validation fails.
    """
    # Try markdown code block first
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try raw JSON
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        json_str = json_match.group(0) if json_match else None

    if not json_str:
        return None

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None

    # Validate required keys exist and are non-empty strings
    if not isinstance(data, dict):
        return None
    if not REQUIRED_ANALYSIS_KEYS.issubset(data.keys()):
        return None
    if not all(isinstance(data[k], str) and data[k].strip() for k in REQUIRED_ANALYSIS_KEYS):
        return None

    return data


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
def analyze_procurement(procurement_id: int, force: bool = False) -> dict | None:
    """Run AI analysis on a procurement. Returns analysis dict or None on error.

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
        # Limit to ~50k chars to stay well within context window
        trimmed = full_text[:50000]
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

    # Call Gemini with retry on JSON parse failure
    client = get_client()
    prompt_text = SYSTEM_PROMPT + "\n\n" + user_prompt

    result = None
    input_tokens = None
    output_tokens = None
    max_attempts = 2

    for attempt in range(max_attempts):
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {"role": "user", "parts": [{"text": prompt_text}]},
            ],
        )

        raw_text = response.text or ""

        # Token usage (from latest attempt)
        if response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count
            output_tokens = response.usage_metadata.candidates_token_count

        # Extract JSON from response (handle markdown code blocks)
        parsed = _parse_analysis_json(raw_text)
        if parsed is not None:
            result = parsed
            break

        # First attempt failed — retry with stricter prompt
        if attempt == 0:
            logger.warning("Gemini JSON parse failed (attempt 1), retrying with strict prompt")
            prompt_text = (
                "Ditt förra svar kunde inte parsas som JSON. "
                "Returnera ENBART ett giltigt JSON-objekt med exakt dessa fyra nycklar: "
                '"kravsammanfattning", "matchningsanalys", "prisstrategi", "anbudshjalp". '
                "Ingen annan text, inga code blocks, bara ren JSON.\n\n"
                + prompt_text
            )

    if result is None:
        logger.error("Gemini JSON parse failed after %d attempts. Raw: %s", max_attempts, raw_text[:500])
        result = {
            "kravsammanfattning": raw_text,
            "matchningsanalys": "Kunde inte parsa AI-svar som JSON.",
            "prisstrategi": "Kunde inte parsa AI-svar som JSON.",
            "anbudshjalp": "Kunde inte parsa AI-svar som JSON.",
        }

    analysis = {
        "procurement_id": procurement_id,
        "full_notice_text": full_text,
        "kravsammanfattning": result.get("kravsammanfattning", ""),
        "matchningsanalys": result.get("matchningsanalys", ""),
        "prisstrategi": result.get("prisstrategi", ""),
        "anbudshjalp": result.get("anbudshjalp", ""),
        "model": "gemini-2.0-flash",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }

    # Save to cache
    save_analysis(procurement_id, analysis)

    # Return the saved version (includes created_at etc.)
    return get_analysis(procurement_id)


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

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {"role": "user", "parts": [{"text": PREFILTER_SYSTEM_PROMPT + "\n\n" + user_msg}]},
            ],
        )
        raw_text = response.text or ""
    except Exception as e:
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

    logger.info("AI prefilter: checked %d, filtered %d as irrelevant", checked, filtered)
    print(f"AI-prefilter: {checked} bedömda, {filtered} filtrerade som irrelevanta")
    return filtered
