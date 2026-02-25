"""Two-stage lead scoring for Hogia public transport IT procurements.

Stage 1: Is this an IT/system procurement (not just bus operation)?
Stage 2: How well does it match Hogia's specific products?

Key distinction: "trafikledning" in a bus-operation procurement means
"performing traffic management", not "buying a traffic management system".
We require system-indicating context for ambiguous terms.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Transport OPERATIONS patterns — if title matches these, it's likely about
# running buses/trains, not buying IT systems
# ---------------------------------------------------------------------------
OPERATIONS_TITLE_PATTERNS: list[str] = [
    r"kollektivtrafik på väg",
    r"kollektivtrafik med buss",
    r"busstrafik",
    r"linjetrafik",
    r"tågtrafik",
    r"stadstrafik",
    r"regionaltrafik",
    r"taxitjänst",
    r"vägtransport",
    r"passagerartransport",
    r"persontransport",
    r"skolskjuts",
    r"serviceresor",
    r"färdtjänst",
    r"sjukresor",
    r"anropsstyrd trafik",
]

# ---------------------------------------------------------------------------
# Stage 1: IT/system gate — UNAMBIGUOUS system/IT keywords
# These clearly indicate buying/procuring IT, not operating transport
# ---------------------------------------------------------------------------
IT_GATE_KEYWORDS: list[str] = [
    # System/IT — unambiguous
    "informationssystem", "it-system", "programvara", "mjukvara", "software",
    "systemlösning", "systemutveckling", "systemstöd", "systemförvaltning",
    "plattform", "molntjänst", "saas", "driftmiljö",
    # System-suffix compounds (unambiguous)
    "realtidssystem", "trafikledningssystem", "biljettsystem", "betalsystem",
    "bokningssystem", "beordringssystem", "biljettlösning", "e-biljett",
    "fordons-it", "fordonsdator", "ombordssystem",
    # Realtid/info — when these appear it's usually about system delivery
    "realtidsinformation", "passagerarinformation", "resenärsinformation",
    "reseinformation", "hållplatsinformation", "reseplanerare",
    # Standards — only relevant in IT context
    "netex", "gtfs", "itxpt", "pubtrans",
    # IT-specifik kontext
    "api", "integration", "dataplattform", "datalagring",
    "digitalisering", "e-tjänst",
]

# ---------------------------------------------------------------------------
# Stage 2: Hogia-specific relevance keywords
# ---------------------------------------------------------------------------
HIGH_WEIGHT_KEYWORDS: dict[str, int] = {
    # Hogias kärnprodukter — system-specifika termer
    "realtidsinformation": 25,
    "realtidssystem": 25,
    "trafikledningssystem": 25,
    "pubtrans": 30,
    "reseplanerare": 20,
    "reseplanering": 20,
    "beordringssystem": 25,
    "anropsstyrd trafik": 15,  # lower — can be operations too
    "samordningscentral": 20,
    "beställningscentral": 20,
    "bestallningscentral": 20,
}

MEDIUM_WEIGHT_KEYWORDS: dict[str, int] = {
    # Relaterade system/standarder
    "passagerarinformation": 15,
    "resenärsinformation": 15,
    "resenarsinformation": 15,
    "hållplatsinformation": 15,
    "trafikinformation": 12,
    "netex": 15,
    "siri": 12,
    "gtfs": 12,
    "itxpt": 15,
    "biljettsystem": 10,
    "betalsystem": 10,
    "fordons-it": 12,
    "ombordssystem": 12,
    "förarstöd": 10,
    "driftstöd": 10,
    "bokningssystem": 10,
}

BASE_WEIGHT_KEYWORDS: dict[str, int] = {
    # Transportkontext (ger poäng bara om IT-gate passerad)
    "kollektivtrafik": 3,
    "serviceresor": 5,
    "färdtjänst": 5,
    "fardtjanst": 5,
    "sjukresor": 5,
    "skolskjuts": 3,
}

# ---------------------------------------------------------------------------
# Blocked sectors — hard gate, blocks scoring entirely
# ---------------------------------------------------------------------------
BLOCKED_SECTORS: dict[str, list[str]] = {
    "Medicinsk": [
        "ekg", "journal", "antikoagulantia", "medicinsk programvara",
        "elevhälsa", "läkemedel", "laboratori", "röntgen", "patologi",
        "klinisk",
    ],
    "VA/vatten": [
        "ultrafilter", "reningsverk", "va-databas", "avlopp",
        "vattenledning", "vattenverk",
    ],
    "Socialtjänst": [
        "hemtjänst", "lov", "omsorg", "äldreboende", "lss",
    ],
    "Kultur/scen": [
        "konserthus", "stadsteater", "museum", "bibliotek",
    ],
    "Bygg/anläggning": [
        "totalentreprenad", "markentreprenad", "betongarbeten",
        "asfaltering", "rivning",
    ],
    "Generell IT": [
        "rekryteringssystem", "lönesystem", "crm", "erp",
        "ekonomisystem", "e-arkiv", "dokumenthantering",
    ],
    "Övrigt": [
        "nyckelskåp", "kassaskåp", "kontorsmaterial", "möbler",
        "livsmedel", "tryckeri", "städ",
    ],
}

# ---------------------------------------------------------------------------
# Transport signals — at least one must be present to pass the gate
# ---------------------------------------------------------------------------
TRANSPORT_SIGNALS: list[str] = [
    "kollektivtrafik", "linjetrafik", "realtid", "trafikledning",
    "hållplats", "biljettsystem", "serviceresor", "färdtjänst",
    "sjukresor", "skolskjuts", "anropsstyrd", "netex", "siri",
    "gtfs", "pubtrans", "itxpt", "passagerarinformation",
]

# CPV-codes that strongly indicate IT (48=software, 72=IT services)
IT_CPV_PREFIXES = ["48", "72"]

# ---------------------------------------------------------------------------
# Known transport buyers — RKM, traffic companies, transport authorities
# Match is case-insensitive substring
# ---------------------------------------------------------------------------
KNOWN_BUYERS = [
    # RKM / Trafikbolag
    "skånetrafiken", "skanetrafiken",
    "västtrafik", "vasttrafik",
    "trafiknämnden",  # Stockholm
    "storstockholms lokaltrafik",
    "uppsalatrafik",
    "östgötatrafiken", "ostgotatrafiken",
    "jönköpings länstrafik", "jlt",
    "länstrafiken kronoberg",
    "kalmar länstrafik", "klt",
    "hallandstrafiken",
    "blekingetrafiken",
    "gotlandsbuss",
    "dalatrafik",
    "x-trafik",
    "din tur",
    "länstrafiken västerbotten",
    "länstrafiken i norrbotten",
    "norrbottens länstrafik",
    "samtrafiken",
    "svealandstrafiken",
    # Bussoperatörer (köper ibland IT-system)
    "keolis", "nobina", "arriva", "vy buss", "bergkvarabuss",
    "tide buss", "nettbuss",
    # Regionala köpare med transportfokus
    "kollektivtrafikmyndighet",
    "kommunalförbundet kollektivtrafik",
]

ALL_KEYWORDS = {**HIGH_WEIGHT_KEYWORDS, **MEDIUM_WEIGHT_KEYWORDS, **BASE_WEIGHT_KEYWORDS}


def sector_gate(
    title: str = "",
    description: str = "",
    buyer: str = "",
    cpv_codes: str = "",
) -> tuple[bool, str]:
    """Hard sector gate — blocks irrelevant sectors before scoring.

    Three checks in order:
    1. Blocked sectors — hard block if text matches wrong sectors
    2. Transport-signal must-have — at least one transport signal required
    3. Operations check — bus operation without IT signal → block

    Returns (passed, reason).
    """
    text = f"{title} {description}".lower()
    buyer_lower = (buyer or "").lower()
    cpv_lower = (cpv_codes or "").lower()
    full_text = f"{text} {buyer_lower} {cpv_lower}"

    # --- Check 1: Blocked sectors ---
    for sector, keywords in BLOCKED_SECTORS.items():
        for kw in keywords:
            if kw in full_text:
                # Exception: "bibliotek" in transport context is OK
                if kw == "bibliotek" and any(ts in full_text for ts in TRANSPORT_SIGNALS):
                    continue
                return False, f"Blockerad sektor ({sector}): {kw}"

    # --- Check 2: Transport signal must-have ---
    has_transport_signal = any(ts in full_text for ts in TRANSPORT_SIGNALS)

    # Known buyer counts as transport signal
    if not has_transport_signal:
        has_transport_signal = any(kb in buyer_lower for kb in KNOWN_BUYERS)

    # CPV 60* (transport services) counts as transport signal
    if not has_transport_signal:
        has_transport_signal = cpv_lower.startswith("60")

    if not has_transport_signal:
        return False, "Ingen transportsignal i titel/beskrivning/köpare/CPV"

    # --- Check 3: Operations without IT signal ---
    title_lower = title.lower()
    if _is_operations_procurement(title_lower):
        if not _is_it_procurement(text, cpv_lower, buyer_lower):
            return False, "Trafikdrift utan IT-signal"

    return True, "Passerade sector gate"


def _is_operations_procurement(title: str) -> bool:
    """Check if the title indicates a transport OPERATIONS procurement."""
    for pattern in OPERATIONS_TITLE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True
    return False


TRANSPORT_CONTEXT_WORDS: list[str] = [
    "kollektivtrafik", "resenär", "passagerarinformation",
    "hållplats", "biljett", "färdtjänst", "serviceresor",
    "skolskjuts", "trafikledning", "realtidsinformation",
    "linjetrafik", "stadstrafik", "busstrafik",
    "anropsstyrd", "beställningscentral",
    "gtfs", "netex", "siri", "itxpt", "pubtrans",
    "realtidssystem", "trafikledningssystem", "beordringssystem",
    "reseplanerare",
]


def _has_transport_context(text: str, buyer: str = "") -> bool:
    """Check if the text relates to transport/mobility."""
    if any(tw in text for tw in TRANSPORT_CONTEXT_WORDS):
        return True
    # Known transport buyer = transport context
    buyer_lower = buyer.lower()
    if any(kb in buyer_lower for kb in KNOWN_BUYERS):
        return True
    return False


def _is_it_procurement(text: str, cpv_codes: str, buyer: str = "") -> bool:
    """Check if this is a transport-IT procurement.

    ALWAYS requires transport context. An IT procurement for healthcare,
    education etc. is irrelevant even if it's software.
    """
    has_transport = _has_transport_context(text, buyer)

    if not has_transport:
        return False

    # Check for IT gate keywords (system-specific terms)
    if any(kw in text for kw in IT_GATE_KEYWORDS):
        return True

    # IT CPV + transport context
    if any(prefix in (cpv_codes or "") for prefix in IT_CPV_PREFIXES):
        return True

    return False


def score_procurement(
    title: str = "",
    description: str = "",
    buyer: str = "",
    cpv_codes: str = "",
) -> tuple[int, str]:
    """Score a procurement and return (score, rationale).

    Pipeline:
    0. Sector gate — hard block for wrong sectors / missing transport signal
    1. Is the title clearly about transport operations? → heavy dampening
    2. Does it pass the IT gate? → full scoring
    3. Neither → minimal scoring
    """
    # --- Sector gate (hard block) ---
    gate_passed, gate_reason = sector_gate(title, description, buyer, cpv_codes)
    if not gate_passed:
        return 0, gate_reason

    text = f"{title} {description}".lower()
    cpv_lower = (cpv_codes or "").lower()
    full_text = f"{text} {cpv_lower}"
    buyer_lower = (buyer or "").lower()
    title_lower = title.lower()

    total = 0
    matched: list[str] = []

    is_operations = _is_operations_procurement(title_lower)
    is_it = _is_it_procurement(text, cpv_lower, buyer_lower)

    if is_operations and not is_it:
        # Transport operations without IT signals → zero
        matched.append("Trafikdrift (ej IT-system)")
        total = 0
    elif is_it:
        matched.append("IT/system-upphandling")
        for keyword, weight in ALL_KEYWORDS.items():
            if keyword in full_text:
                total += weight
                matched.append(f"{keyword} (+{weight})")
    else:
        # Not transport ops but also not clearly IT → zero
        total = 0

    if is_it:
        # Buyer bonus — only for IT procurements
        for known in KNOWN_BUYERS:
            if known in buyer_lower:
                total += 10
                matched.append(f"känd köpare: {buyer} (+10)")
                break

        # CPV bonus for IT-specific codes
        for prefix in IT_CPV_PREFIXES:
            if prefix in cpv_lower:
                total += 8
                matched.append(f"IT-CPV ({prefix}*) (+8)")
                break

    # Cap at 0-100
    total = max(0, min(total, 100))

    rationale = ", ".join(matched) if matched else "Inga matchande nyckelord"
    return total, rationale
