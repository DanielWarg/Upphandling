"""Lead scoring for HAST Utveckling — ledarskap, utbildning & organisationsutveckling.

HAST erbjuder: ledarskapsutbildning, teamutveckling, kommunikationsutbildning,
personaleffektivitet, executive coaching, seminarier och AI-workshops.

Scoring:
1. Sector gate — blockera irrelevanta sektorer (bygg, medicin, IT-drift etc)
2. Utbildningsrelevans — matchar det HAST:s tjänsteområden?
"""

from __future__ import annotations

import re

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
    "arbetsmiljö": 10,
    "stresshantering": 15,
    "konflikthantering": 15,
    "feedbackkultur": 12,
    "gruppdynamik": 15,
    "teambuilding": 12,
    "seminarium": 10,
    "workshop": 10,
    "föreläsning": 8,
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
    "Medicinsk": [
        "ekg", "journal", "antikoagulantia", "medicinsk programvara",
        "läkemedel", "laboratori", "röntgen", "patologi", "klinisk",
    ],
    "VA/vatten": [
        "ultrafilter", "reningsverk", "avlopp", "vattenledning", "vattenverk",
    ],
    "Bygg/anläggning": [
        "totalentreprenad", "markentreprenad", "betongarbeten",
        "asfaltering", "rivning", "schakt", "byggnation",
    ],
    "IT-drift": [
        "serverdrift", "nätverksdrift", "hårdvara", "licenser",
        "systemdrift", "it-infrastruktur",
    ],
    "Transport/drift": [
        "busstrafik", "linjetrafik", "tågtrafik", "färjetrafik",
        "taxitjänst", "godstransport", "bränsle",
    ],
    "Material/varor": [
        "kontorsmaterial", "möbler", "livsmedel", "tryckeri",
        "städ", "tvätt", "fordon", "maskiner",
    ],
}

# ---------------------------------------------------------------------------
# CPV-codes relevant for education/consulting (79=consulting, 80=education)
# ---------------------------------------------------------------------------
EDUCATION_CPV_PREFIXES = ["79", "80"]

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


def sector_gate(
    title: str = "",
    description: str = "",
    buyer: str = "",
    cpv_codes: str = "",
) -> tuple[bool, str]:
    """Hard sector gate — blocks irrelevant sectors before scoring."""
    text = f"{title} {description}".lower()
    buyer_lower = (buyer or "").lower()
    cpv_lower = (cpv_codes or "").lower()
    full_text = f"{text} {buyer_lower} {cpv_lower}"

    # Check blocked sectors
    for sector, keywords in BLOCKED_SECTORS.items():
        for kw in keywords:
            if kw in full_text:
                return False, f"Blockerad sektor ({sector}): {kw}"

    # Must have education/development signal
    has_signal = any(kw in full_text for kw in EDUCATION_GATE_KEYWORDS)

    if not has_signal:
        # Education CPV counts as signal
        has_signal = any(prefix in cpv_lower for prefix in EDUCATION_CPV_PREFIXES)

    if not has_signal:
        return False, "Ingen utbildnings-/utvecklingssignal"

    return True, "Passerade sector gate"


def score_procurement(
    title: str = "",
    description: str = "",
    buyer: str = "",
    cpv_codes: str = "",
) -> tuple[int, str]:
    """Score a procurement for HAST relevance. Returns (score, rationale)."""
    gate_passed, gate_reason = sector_gate(title, description, buyer, cpv_codes)
    if not gate_passed:
        return 0, gate_reason

    text = f"{title} {description}".lower()
    cpv_lower = (cpv_codes or "").lower()
    full_text = f"{text} {cpv_lower}"
    buyer_lower = (buyer or "").lower()

    total = 0
    matched: list[str] = []

    matched.append("Utbildning/utveckling")
    for keyword, weight in ALL_KEYWORDS.items():
        if keyword in full_text:
            total += weight
            matched.append(f"{keyword} (+{weight})")

    # Buyer bonus — offentlig sektor
    for known in KNOWN_BUYERS:
        if known in buyer_lower:
            total += 8
            matched.append(f"offentlig köpare (+8)")
            break

    # CPV bonus
    for prefix in EDUCATION_CPV_PREFIXES:
        if prefix in cpv_lower:
            total += 8
            matched.append(f"Utbildnings-CPV ({prefix}*) (+8)")
            break

    total = max(0, min(total, 100))
    rationale = ", ".join(matched) if matched else "Inga matchande nyckelord"
    return total, rationale
