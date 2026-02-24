"""TED (Tenders Electronic Daily) API-scraper.

Använder det fria v3 sök-API:et — ingen autentisering krävs för publicerade notices.
Filtrerar på svenska transport-upphandlingar (CPV 60*).
"""

from __future__ import annotations

import httpx
from .base import BaseScraper

SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"

# Fält att hämta från API:et
FIELDS = [
    "notice-identifier",
    "notice-title",
    "description-proc",
    "description-lot",
    "organisation-name-buyer",
    "classification-cpv",
    "publication-date",
    "deadline-receipt-tender-date-lot",
    "estimated-value-proc",
    "estimated-value-cur-proc",
]

# Antal resultat per sida (API default är 10)
PAGE_SIZE = 50
MAX_PAGES = 5


class TedScraper(BaseScraper):
    name = "ted"

    def fetch(self) -> list[dict]:
        results = []
        page = 1
        while page <= MAX_PAGES:
            payload = {
                "query": f"CY=SWE AND classification-cpv=60*",
                "fields": FIELDS,
                "limit": PAGE_SIZE,
                "page": page,
            }
            try:
                resp = httpx.post(SEARCH_URL, json=payload, timeout=30)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                print(f"[TED] HTTP-fel på sida {page}: {e}")
                break

            data = resp.json()
            notices = data.get("notices", [])
            if not notices:
                break

            for notice in notices:
                results.append(self._normalize(notice))

            # API returnerar exakt limit antal om det finns fler
            if len(notices) < PAGE_SIZE:
                break
            page += 1

        print(f"[TED] Hämtade {len(results)} upphandlingar")
        return results

    def _normalize(self, notice: dict) -> dict:
        """Mappa TED API-fält till vårt schema."""
        title = self._extract_text(notice.get("notice-title"), "Utan titel")
        buyer = self._extract_text(notice.get("organisation-name-buyer"))
        desc = self._extract_text(notice.get("description-proc")) or self._extract_text(notice.get("description-lot"))

        # Extrahera geografi från titeln (format: "Sverige-Malmö: Beskrivning")
        geography = "Sverige"
        if title.startswith("Sverige-"):
            parts = title.split(":", 1)
            if parts:
                geography = parts[0].replace("Sverige-", "").strip()

        cpv = notice.get("classification-cpv", [])
        if isinstance(cpv, list):
            cpv = ",".join(str(c) for c in cpv)

        pub_number = notice.get("publication-number", "")

        # Bygg URL från publication-number
        url_links = notice.get("links", {}).get("html", {})
        url = url_links.get("SWE") or url_links.get("ENG") or f"https://ted.europa.eu/sv/notice/-/detail/{pub_number}"

        deadline = notice.get("deadline-receipt-tender-date-lot")
        if isinstance(deadline, list) and deadline:
            deadline = deadline[0]

        est_value = notice.get("estimated-value-proc")
        est_cur = notice.get("estimated-value-cur-proc")

        return {
            "source": "ted",
            "source_id": pub_number,
            "title": title,
            "buyer": buyer,
            "geography": geography,
            "cpv_codes": str(cpv) if cpv else None,
            "procedure_type": None,
            "published_date": notice.get("publication-date", "")[:10] if notice.get("publication-date") else None,
            "deadline": str(deadline)[:10] if deadline else None,
            "estimated_value": self._parse_value(est_value),
            "currency": str(est_cur) if est_cur else "EUR",
            "status": "published",
            "url": url,
            "description": str(desc)[:2000] if desc else None,
        }

    @staticmethod
    def _extract_text(val, default: str = "") -> str:
        """Extrahera text från TED:s flerspråkiga fält (föredrar svenska)."""
        if val is None:
            return default
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            return val.get("swe") or val.get("SWE") or val.get("eng") or val.get("ENG") or next(iter(val.values()), default)
        if isinstance(val, list):
            if not val:
                return default
            first = val[0]
            if isinstance(first, dict):
                return TedScraper._extract_text(first, default)
            return str(first)
        return str(val) if val else default

    @staticmethod
    def _parse_value(val) -> float | None:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val.replace(",", ".").replace(" ", ""))
            except ValueError:
                return None
        if isinstance(val, dict):
            return TedScraper._parse_value(val.get("value"))
        if isinstance(val, list) and val:
            return TedScraper._parse_value(val[0])
        return None
