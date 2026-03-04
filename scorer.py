"""Lead scoring for HAST Utveckling — ledarskap, utbildning & organisationsutveckling.

HAST erbjuder: ledarskapsutbildning, teamutveckling, kommunikationsutbildning,
personaleffektivitet, executive coaching, seminarier och AI-workshops.

Scoring:
1. Sector gate — blockera irrelevanta sektorer (bygg, medicin, IT-drift etc)
2. Utbildningsrelevans — matchar det HAST:s tjänsteområden?

Profiles:
- UPPHANDLING_PROFILE: offentlig upphandling (LOU)
- BIDRAG_PROFILE: bidrag/utlysningar (Vinnova, Tillväxtverket, ESF)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Stage 1: Utbildnings-/utvecklingsgate — unambiguous signals
# ---------------------------------------------------------------------------
EDUCATION_GATE_KEYWORDS: list[str] = [
    # Utbildning & utveckling
    "utbildning", "ledarskapsutbildning", "ledarskapsutveckling",
    "chefsutveckling", "chefsutbildning", "kompetensutveckling",
    "kompetensförsörjning", "organisationsutveckling",
    "teamutveckling", "grupputveckling", "medarbetarutveckling",
    "personalutveckling", "personlig utveckling",
    "kommunikationsutbildning", "kommunikationsträning",
    # Coaching
    "coaching", "executive coaching", "chefscoaching", "handledning",
    "mentorskap", "mentor", "coachning",
    # Seminarier & workshops
    "seminarium", "workshop", "inspirationsföreläsning",
    "föreläsning", "konferens", "kunskapsseminarium",
    # Ledarskap & organisation
    "ledarskap", "ledarskapsprogram", "chefsprogram",
    "arbetsmiljö", "organisationsförändring", "förändringsledning",
    "förändringsarbete", "arbetskultur", "medarbetarskap",
    # HR & kompetens
    "hr-tjänster", "personaleffektivitet", "stresshantering",
    "konflikthantering", "feedbackkultur", "gruppdynamik",
    "teambuilding", "team building",
    # Ramavtal utbildning
    "ramavtal utbildning", "konsulttjänster utbildning",
    "managementkonsult", "organisationskonsult",
]

# ---------------------------------------------------------------------------
# Stage 2: HAST-specifika relevance keywords med vikter
# ---------------------------------------------------------------------------
HIGH_WEIGHT_KEYWORDS: dict[str, int] = {
    # HAST kärnkompetens
    "ledarskapsutbildning": 25,
    "ledarskapsutveckling": 25,
    "chefsutveckling": 25,
    "chefsutbildning": 25,
    "ledarskapsprogram": 25,
    "chefsprogram": 20,
    "executive coaching": 30,
    "chefscoaching": 25,
    "teamutveckling": 25,
    "grupputveckling": 25,
    "organisationsutveckling": 20,
    "kommunikationsutbildning": 25,
    "kommunikationsträning": 20,
    "personaleffektivitet": 20,
    "förändringsledning": 20,
}

MEDIUM_WEIGHT_KEYWORDS: dict[str, int] = {
    "coaching": 15,
    "coachning": 15,
    "handledning": 12,
    "mentorskap": 12,
    "kompetensutveckling": 15,
    "kompetensförsörjning": 12,
    "medarbetarutveckling": 15,
    "personalutveckling": 12,
    "organisationsförändring": 12,
    "förändringsarbete": 12,
    "arbetsmiljö": 3,
    "stresshantering": 15,
    "konflikthantering": 5,
    "feedbackkultur": 12,
    "gruppdynamik": 15,
    "teambuilding": 12,
    "seminarium": 10,
    "workshop": 10,
    "föreläsning": 3,
    "inspirationsföreläsning": 12,
    "ledarskap": 10,
    "medarbetarskap": 10,
    "arbetskultur": 10,
}

BASE_WEIGHT_KEYWORDS: dict[str, int] = {
    "utbildning": 5,
    "hr-tjänster": 5,
    "managementkonsult": 8,
    "organisationskonsult": 8,
    "konsulttjänster": 3,
    "ramavtal": 3,
}

# ---------------------------------------------------------------------------
# Blocked sectors — hard gate
# ---------------------------------------------------------------------------
BLOCKED_SECTORS: dict[str, list[str]] = {
    "Medicinsk/vård": [
        "ekg", "journal", "antikoagulantia", "medicinsk programvara",
        "läkemedel", "laboratori", "röntgen", "patologi", "klinisk",
        "tandvård", "tandvårdssystem", "ambulans", "patient",
        "sjukvård", "vårdmöten", "egenmonitorering", "medicintekn",
        "bildhanteringssystem", "frikort", "veterinär",
    ],
    "VA/vatten": [
        "ultrafilter", "reningsverk", "avlopp", "vattenledning", "vattenverk",
    ],
    "Bygg/anläggning": [
        "totalentreprenad", "markentreprenad", "betongarbeten",
        "asfaltering", "rivning", "schakt", "byggnation",
        "tekniska konsulter", "ingenjörstjänster",
    ],
    "IT-drift/system": [
        "serverdrift", "nätverksdrift", "hårdvara", "licenser",
        "systemdrift", "it-infrastruktur", "cyberhot", "mdr-tjänst",
        "bokningssystem", "biljettsystem", "biljett-",
        "bibliotekssystem", "lagerförvaltning", "kassasystem",
    ],
    "Transport/drift": [
        "busstrafik", "linjetrafik", "tågtrafik", "färjetrafik",
        "taxitjänst", "godstransport", "bränsle", "skolskjuts",
        "yrkesförare", "körkortsutbildning", "snöskoter",
        "skogsbrandsbevakning", "avfallstransport", "åkeritjänster",
        "tredjepartslogistik", "3pl", "hemkörning",
        "realtidsinformation", "passagerarinformation",
        "kollektivtrafik", "färdtjänst",
    ],
    "Material/varor": [
        "kontorsmaterial", "möbler", "livsmedel", "tryckeri",
        "städ", "tvätt", "fordon", "maskiner", "dagligvaror",
    ],
    "Infrastruktur": [
        "fyra spår", "infrastrukturprojekt", "terminologitjänst",
        "patientkallelse", "larm", "passerkontroll",
    ],
    "Rekrytering/bemanning": [
        "bemanningstjänster", "personaluthyrning", "inhyrning av läkare",
        "inhyrning av sjukskötersk", "förmedling av vårdpersonal",
        "förmedling av läkare", "sjukskötersketjänster",
        "rekryteringstjänster", "second opinion vid rekrytering",
    ],
    "Juridik/finans": [
        "inkasso", "påminnelsetjänster", "juridisk rådgivning",
        "advokatbyråtjänster", "revisionstjänster",
    ],
    "Marknadsföring/reklam": [
        "reklam och marknadsföring", "kommunikationsbyrå",
        "profilprodukter", "presenter och priser",
        "korrekturläsning", "proofreading",
    ],
    "Undersökning/analys": [
        "undersökningstjänster", "marknadsundersökning",
        "telefonnummersättning", "statistisk",
    ],
    "Hälsovård/företagshälsa": [
        "företagshälsovård", "hälsovård", "rehabilitering", "ergonomi",
        "hälsokontroll", "friskvård",
    ],
    "Säkerhetsutbildning": [
        "hot och våld", "brandskyddsutbildning", "hjlr", "första hjälpen",
        "truckkort", "truckutbildning",
    ],
    "Förmedling/bokning": [
        "förmedling av talare", "bokningsförmedling", "artistförmedling",
    ],
}

# ---------------------------------------------------------------------------
# CPV-koder relevanta för HAST:s tjänsteområden
# ---------------------------------------------------------------------------
HAST_CPV_CODES: dict[str, int] = {
    # Kärnkoder — exakt match, hög bonus
    "80532000": 20,  # Chefsutbildning
    "79633000": 20,  # Personalutveckling
    "79632000": 18,  # Utbildning av personal
    "80511000": 18,  # Personalutbildning
    "79998000": 20,  # Coachning
    "80570000": 18,  # Utbildning i personlig utveckling
    # Relevanta koder — mellannivå
    "79414000": 12,  # Managementkonsulttjänster
    "79411100": 10,  # Rådgivning rörande utveckling
    "79411000": 10,  # Allmän managementrådgivning
    "79410000": 8,   # Företags- och organisationsrådgivning
    "80590000": 10,  # Handledning
    "80521000": 8,   # Utbildningsprogram
    "79600000": 5,   # Rekryteringstjänster (HR-angränsande)
    # Breda koder — låg bonus (gate-signal)
    "80500000": 5,   # Utbildningstjänster (bred)
    "80530000": 5,   # Yrkesutbildning (bred)
    "80000000": 3,   # Undervisning och utbildning (mycket bred)
}

# Gate-prefix: CPV-koder som indikerar utbildnings-/konsultrelevans
EDUCATION_CPV_PREFIXES = ["8053", "8051", "8057", "8059", "7963", "7941", "7999"]

# ---------------------------------------------------------------------------
# Known relevant buyers — offentliga organisationer som upphandlar utbildning
# ---------------------------------------------------------------------------
KNOWN_BUYERS = [
    "region", "kommun", "landsting", "länsstyrelse",
    "myndighet", "verk", "styrelse", "nämnd",
    "polisen", "försvarsmakten", "trafikverket",
    "arbetsförmedlingen", "skatteverket", "försäkringskassan",
    "sida", "folkhälsomyndigheten",
]

ALL_KEYWORDS = {**HIGH_WEIGHT_KEYWORDS, **MEDIUM_WEIGHT_KEYWORDS, **BASE_WEIGHT_KEYWORDS}


# ---------------------------------------------------------------------------
# ScoringProfile — encapsulates all constants for a record_type
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScoringProfile:
    """Configuration for scoring a specific record type."""
    gate_keywords: list[str]
    blocked_sectors: dict[str, list[str]]
    all_keywords: dict[str, int]
    cpv_codes: dict[str, int]
    cpv_prefixes: list[str]
    known_buyers: list[str]
    buyer_bonus: int = 8


UPPHANDLING_PROFILE = ScoringProfile(
    gate_keywords=EDUCATION_GATE_KEYWORDS,
    blocked_sectors=BLOCKED_SECTORS,
    all_keywords=ALL_KEYWORDS,
    cpv_codes=HAST_CPV_CODES,
    cpv_prefixes=EDUCATION_CPV_PREFIXES,
    known_buyers=KNOWN_BUYERS,
    buyer_bonus=8,
)

# ---------------------------------------------------------------------------
# Bidragsprofil — nyckelord för Vinnova/Tillväxtverket/ESF-utlysningar
# ---------------------------------------------------------------------------
BIDRAG_GATE_KEYWORDS: list[str] = [
    "bidrag", "anslag", "finansiering", "utlysning", "projektbidrag",
    "kompetensutveckling", "omställningsstöd", "ledarskap",
    "organisationsutveckling", "vinnova", "tillväxtverket",
    "utbildning", "ledarskapsutveckling", "chefsutveckling",
    "förändringsledning", "omställning", "coaching",
    "medarbetarutveckling", "kompetensförsörjning",
]

BIDRAG_HIGH_KEYWORDS: dict[str, int] = {
    "ledarskapsutveckling": 25,
    "kompetensutveckling": 20,
    "organisationsutveckling": 20,
    "förändringsledning": 20,
    "omställning": 15,
}

BIDRAG_MEDIUM_KEYWORDS: dict[str, int] = {
    "coaching": 15,
    "medarbetarutveckling": 15,
    "kompetensförsörjning": 12,
}

BIDRAG_BASE_KEYWORDS: dict[str, int] = {
    "utbildning": 5,
    "bidrag": 5,
    "projektbidrag": 8,
}

BIDRAG_ALL_KEYWORDS = {**BIDRAG_HIGH_KEYWORDS, **BIDRAG_MEDIUM_KEYWORDS, **BIDRAG_BASE_KEYWORDS}

BIDRAG_BLOCKED_SECTORS: dict[str, list[str]] = {
    "Teknik/FoU": [
        "teknisk forskning", "materialteknik", "halvledare", "kvantdator",
        "rymdteknik", "nanoteknik",
    ],
    "Infrastruktur": [
        "infrastrukturprojekt", "vägbygge", "järnväg", "bredbandsutbyggnad",
    ],
    "IT-system": [
        "systemutveckling", "mjukvaruutveckling", "ai-modell", "maskininlärning",
        "cybersäkerhet", "molntjänst",
    ],
}

BIDRAG_KNOWN_BUYERS: list[str] = [
    "vinnova", "tillväxtverket", "europeiska socialfonden", "esf",
    "arvsfonden", "forte", "formas",
]

BIDRAG_PROFILE = ScoringProfile(
    gate_keywords=BIDRAG_GATE_KEYWORDS,
    blocked_sectors=BIDRAG_BLOCKED_SECTORS,
    all_keywords=BIDRAG_ALL_KEYWORDS,
    cpv_codes={},
    cpv_prefixes=[],
    known_buyers=BIDRAG_KNOWN_BUYERS,
    buyer_bonus=10,
)

_PROFILES: dict[str, ScoringProfile] = {
    "upphandling": UPPHANDLING_PROFILE,
    "bidrag": BIDRAG_PROFILE,
}


def sector_gate(
    title: str = "",
    description: str = "",
    buyer: str = "",
    cpv_codes: str = "",
    profile: ScoringProfile | None = None,
) -> tuple[bool, str]:
    """Hard sector gate — blocks irrelevant sectors before scoring."""
    if profile is None:
        profile = UPPHANDLING_PROFILE

    text = f"{title} {description}".lower()
    buyer_lower = (buyer or "").lower()
    cpv_lower = (cpv_codes or "").lower()
    full_text = f"{text} {buyer_lower} {cpv_lower}"

    # Check blocked sectors
    for sector, keywords in profile.blocked_sectors.items():
        for kw in keywords:
            if kw in full_text:
                return False, f"Blockerad sektor ({sector}): {kw}"

    # Must have education/development signal
    has_signal = any(kw in full_text for kw in profile.gate_keywords)

    if not has_signal and profile.cpv_prefixes:
        # Education CPV counts as signal — check each individual CPV code prefix
        has_signal = _has_cpv_prefix(cpv_lower, profile.cpv_prefixes)

    if not has_signal:
        return False, "Ingen utbildnings-/utvecklingssignal"

    return True, "Passerade sector gate"


def _has_cpv_prefix(cpv_string: str, prefixes: list[str]) -> bool:
    """Check if any individual CPV code starts with one of the given prefixes."""
    if not cpv_string:
        return False
    # CPV codes are comma-separated; split and check each one's prefix
    for code in cpv_string.split(","):
        code = code.strip()
        if any(code.startswith(prefix) for prefix in prefixes):
            return True
    return False


def score_procurement(
    title: str = "",
    description: str = "",
    buyer: str = "",
    cpv_codes: str = "",
    record_type: str = "upphandling",
) -> tuple[int, str, dict]:
    """Score a procurement for HAST relevance. Returns (score, rationale, breakdown)."""
    profile = _PROFILES.get(record_type, UPPHANDLING_PROFILE)

    gate_passed, gate_reason = sector_gate(title, description, buyer, cpv_codes, profile=profile)
    if not gate_passed:
        breakdown = {
            "gate_passed": False,
            "gate_reason": gate_reason,
            "keyword_matches": [],
            "cpv_matches": [],
            "buyer_bonus": 0,
            "total": 0,
        }
        return 0, gate_reason, breakdown

    text = f"{title} {description}".lower()
    cpv_lower = (cpv_codes or "").lower()
    full_text = f"{text} {cpv_lower}"
    buyer_lower = (buyer or "").lower()

    total = 0
    matched: list[str] = []
    keyword_matches: list[dict] = []

    matched.append("Utbildning/utveckling")
    for keyword, weight in profile.all_keywords.items():
        if keyword in full_text:
            total += weight
            matched.append(f"{keyword} (+{weight})")
            keyword_matches.append({"keyword": keyword, "weight": weight})

    # Buyer bonus
    buyer_bonus = 0
    for known in profile.known_buyers:
        if known in buyer_lower:
            buyer_bonus = profile.buyer_bonus
            total += buyer_bonus
            matched.append(f"känd köpare (+{buyer_bonus})")
            break

    # CPV bonus — per-code match with profile-specific weights
    cpv_bonus = 0
    cpv_matched_codes: list[str] = []
    cpv_matches: list[dict] = []
    if cpv_lower and profile.cpv_codes:
        for code in cpv_lower.split(","):
            code = code.strip().split(":")[0].strip()
            if code in profile.cpv_codes and code not in cpv_matched_codes:
                bonus = profile.cpv_codes[code]
                cpv_bonus += bonus
                cpv_matched_codes.append(code)
                cpv_matches.append({"code": code, "bonus": bonus})
    if cpv_bonus:
        total += cpv_bonus
        matched.append(f"CPV-match ({','.join(cpv_matched_codes)}) (+{cpv_bonus})")

    total = max(0, min(total, 100))
    rationale = ", ".join(matched) if matched else "Inga matchande nyckelord"

    breakdown = {
        "gate_passed": True,
        "gate_reason": "Passerade sector gate",
        "keyword_matches": keyword_matches,
        "cpv_matches": cpv_matches,
        "buyer_bonus": buyer_bonus,
        "total": total,
    }

    return total, rationale, breakdown
