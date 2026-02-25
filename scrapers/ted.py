"""TED (Tenders Electronic Daily) API-scraper.

Använder det fria v3 sök-API:et — ingen autentisering krävs för publicerade notices.
Kör flera sökningar för att fånga svenska upphandlingar relevanta för kollektivtrafik-IT.
"""

from __future__ import annotations

import time
import httpx
from .base import BaseScraper

SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"

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

# Smalare sökfrågor — kombinerar CPV med nyckelord för att minska brus
QUERIES = [
    # Kollektivtrafik-IT specifika CPV-koder
    "CY=SWE AND (classification-cpv=48813* OR classification-cpv=48814*) AND publication-date>20250901",
    # IT-tjänster + transport-nyckelord i titel/beskrivning
    'CY=SWE AND classification-cpv=72* AND (TD~"kollektivtrafik" OR TD~"realtid" OR TD~"trafikledning" OR TD~"passagerarinformation") AND publication-date>20250901',
    # Transporttjänster + system-nyckelord
    'CY=SWE AND classification-cpv=60* AND (TD~"system" OR TD~"plattform" OR TD~"realtid" OR TD~"IT") AND publication-date>20250901',
    # Bred sökning — kända transportköpare + IT-CPV
    'CY=SWE AND (classification-cpv=48* OR classification-cpv=72*) AND (BN~"trafik" OR BN~"Skånetrafiken" OR BN~"Västtrafik" OR BN~"Samtrafiken") AND publication-date>20250901',
]

PAGE_SIZE = 50
MAX_PAGES = 4


class TedScraper(BaseScraper):
    name = "ted"

    def fetch(self) -> list[dict]:
        seen_ids: set[str] = set()
        results = []

        for query in QUERIES:
            query_results = self._fetch_query(query, seen_ids)
            results.extend(query_results)

        print(f"[TED] Hämtade {len(results)} upphandlingar totalt")
        return results

    def _fetch_query(self, query: str, seen_ids: set[str]) -> list[dict]:
        results = []
        page = 1

        while page <= MAX_PAGES:
            payload = {
                "query": query,
                "fields": FIELDS,
                "limit": PAGE_SIZE,
                "page": page,
            }
            try:
                resp = httpx.post(SEARCH_URL, json=payload, timeout=30)
                if resp.status_code == 429:
                    print("[TED] Rate limit — väntar 5s...")
                    time.sleep(5)
                    resp = httpx.post(SEARCH_URL, json=payload, timeout=30)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                print(f"[TED] HTTP-fel: {e}")
                break

            time.sleep(0.5)  # Undvik rate limiting

            data = resp.json()
            notices = data.get("notices", [])
            if not notices:
                break

            for notice in notices:
                pub_nr = notice.get("publication-number", "")
                if pub_nr in seen_ids:
                    continue
                seen_ids.add(pub_nr)
                results.append(self._normalize(notice))

            if len(notices) < PAGE_SIZE:
                break
            page += 1

        return results

    def _normalize(self, notice: dict) -> dict:
        """Mappa TED API-fält till vårt schema."""
        title = self._extract_text(notice.get("notice-title"), "Utan titel")
        buyer = self._extract_text(notice.get("organisation-name-buyer"))
        desc = (
            self._extract_text(notice.get("description-proc"))
            or self._extract_text(notice.get("description-lot"))
        )

        # Extrahera geografi från titeln (format: "Sverige-Malmö: Beskrivning")
        geography = "Sverige"
        title_clean = title
        if "–" in title:
            # Nyare format: "Sverige – Kollektivtrafik – ..."
            parts = title.split("–")
            if len(parts) >= 2:
                geography = parts[0].replace("Sverige", "").strip().strip("–").strip()
                if not geography:
                    geography = "Sverige"
        elif title.startswith("Sverige-"):
            parts = title.split(":", 1)
            if parts:
                geography = parts[0].replace("Sverige-", "").strip()

        cpv = notice.get("classification-cpv", [])
        if isinstance(cpv, list):
            cpv = ",".join(str(c) for c in cpv)

        pub_number = notice.get("publication-number", "")

        url_links = notice.get("links", {}).get("html", {})
        url = (
            url_links.get("SWE")
            or url_links.get("ENG")
            or f"https://ted.europa.eu/sv/notice/-/detail/{pub_number}"
        )

        deadline = notice.get("deadline-receipt-tender-date-lot")
        if isinstance(deadline, list) and deadline:
            deadline = deadline[0]

        est_value = notice.get("estimated-value-proc")
        est_cur = notice.get("estimated-value-cur-proc")

        return {
            "source": "ted",
            "source_id": pub_number,
            "title": title_clean,
            "buyer": buyer if buyer else None,
            "geography": geography,
            "cpv_codes": str(cpv) if cpv else None,
            "procedure_type": None,
            "published_date": notice.get("publication-date", "")[:10] if notice.get("publication-date") else None,
            "deadline": str(deadline)[:10] if deadline else None,
            "estimated_value": self._parse_value(est_value),
            "currency": str(est_cur) if est_cur else "SEK",
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
            # Värdet kan vara en sträng eller en lista av strängar
            raw = val.get("swe") or val.get("SWE") or val.get("eng") or val.get("ENG")
            if raw is None:
                raw = next(iter(val.values()), default)
            if isinstance(raw, list):
                return " ".join(str(x) for x in raw) if raw else default
            return str(raw) if raw else default
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
