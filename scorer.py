"""Keyword-based lead scoring for public transport procurements."""

from __future__ import annotations

# Weighted keyword groups
HIGH_WEIGHT_KEYWORDS: dict[str, int] = {
    "realtid": 20,
    "realtidsinformation": 20,
    "realtidssystem": 20,
    "trafikledning": 20,
    "trafikledningssystem": 20,
    "dataplattform": 20,
    "informationsplattform": 20,
}

MEDIUM_WEIGHT_KEYWORDS: dict[str, int] = {
    "beställningscentral": 10,
    "bestallningscentral": 10,
    "samordningscentral": 10,
    "passagerarinformation": 10,
    "resenärsinformation": 10,
    "resenarsinformation": 10,
    "netex": 10,
    "siri": 10,
    "gtfs": 10,
    "itxpt": 10,
}

BASE_WEIGHT_KEYWORDS: dict[str, int] = {
    "kollektivtrafik": 5,
    "busstrafik": 5,
    "tågtrafik": 5,
    "tagtrafik": 5,
    "serviceresor": 5,
    "färdtjänst": 5,
    "fardtjanst": 5,
    "sjukresor": 5,
    "skolskjuts": 5,
}

# Known RKM / regions that are high-value buyers
KNOWN_BUYERS = [
    "skånetrafiken",
    "skanetrafiken",
    "sl",
    "stockholms läns landsting",
    "västtrafik",
    "vasttrafik",
    "uppsalatrafik",
    "ul",
    "östgötatrafiken",
    "ostgotatrafiken",
    "jlt",
    "jönköpings länstrafik",
    "länstrafiken kronoberg",
    "kalmar länstrafik",
    "klt",
    "hallandstrafiken",
    "blekingetrafiken",
    "gotlandsbuss",
    "dalatrafik",
    "x-trafik",
    "din tur",
    "länstrafiken västerbotten",
    "norrbottens länstrafik",
    "region stockholm",
    "region skåne",
    "region västra götaland",
    "region östergötland",
    "region uppsala",
    "region jönköpings län",
    "region kronoberg",
    "region kalmar län",
    "region blekinge",
    "region halland",
    "region dalarna",
    "region gävleborg",
    "region västernorrland",
    "region västerbotten",
    "region norrbotten",
    "region sörmland",
    "region värmland",
    "region örebro län",
    "region västmanland",
    "region gotland",
    "samtrafiken",
]

ALL_KEYWORDS = {**HIGH_WEIGHT_KEYWORDS, **MEDIUM_WEIGHT_KEYWORDS, **BASE_WEIGHT_KEYWORDS}


def score_procurement(
    title: str = "",
    description: str = "",
    buyer: str = "",
    cpv_codes: str = "",
) -> tuple[int, str]:
    """Score a procurement and return (score, rationale).

    Searches title, description, buyer, and CPV codes for weighted keywords.
    Adds a buyer bonus if the buyer is a known RKM/region.
    Caps the score at 100.
    """
    text = f"{title} {description} {cpv_codes}".lower()
    buyer_lower = (buyer or "").lower()

    total = 0
    matched: list[str] = []

    for keyword, weight in ALL_KEYWORDS.items():
        if keyword in text:
            total += weight
            matched.append(f"{keyword} (+{weight})")

    # Buyer bonus
    buyer_bonus = False
    for known in KNOWN_BUYERS:
        if known in buyer_lower:
            total += 10
            matched.append(f"känd köpare: {buyer} (+10)")
            buyer_bonus = True
            break

    # Cap at 100
    total = min(total, 100)

    rationale = ", ".join(matched) if matched else "Inga matchande nyckelord"
    return total, rationale
