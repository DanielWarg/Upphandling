"""TED (Tenders Electronic Daily) API scraper.

Uses the free v3 search API — no authentication required for published notices.
Filters for Swedish transport procurements (CPV 60*).
"""

from __future__ import annotations

import httpx
from .base import BaseScraper

SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"

# Query: Swedish notices with transport CPV codes
QUERY_PARAMS = {
    "query": "country=SWE AND cpv=60*",
    "fields": [
        "notice-id",
        "title",
        "buyer-name",
        "place-of-performance",
        "cpv-code",
        "procedure-type",
        "publication-date",
        "deadline-receipt-tenders",
        "estimated-total-value",
        "notice-url",
        "description",
    ],
    "pageSize": 50,
    "page": 1,
    "scope": "ALL",
}


class TedScraper(BaseScraper):
    name = "ted"

    def fetch(self) -> list[dict]:
        results = []
        page = 1
        while True:
            payload = {**QUERY_PARAMS, "page": page}
            try:
                resp = httpx.post(SEARCH_URL, json=payload, timeout=30)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                print(f"[TED] HTTP error on page {page}: {e}")
                break

            data = resp.json()
            notices = data.get("notices", [])
            if not notices:
                break

            for notice in notices:
                results.append(self._normalize(notice))

            # Stop if we've fetched all pages
            total_pages = data.get("totalPages", 1)
            if page >= total_pages:
                break
            page += 1

        print(f"[TED] Fetched {len(results)} notices")
        return results

    def _normalize(self, notice: dict) -> dict:
        """Map TED API fields to our schema."""
        # TED v3 returns fields in various formats; handle flexibly
        title_data = notice.get("title", "")
        if isinstance(title_data, dict):
            title = title_data.get("sv") or title_data.get("en") or str(title_data)
        elif isinstance(title_data, list) and title_data:
            title = str(title_data[0])
        else:
            title = str(title_data) if title_data else "Utan titel"

        buyer = notice.get("buyer-name", "")
        if isinstance(buyer, list) and buyer:
            buyer = buyer[0]
        if isinstance(buyer, dict):
            buyer = buyer.get("sv") or buyer.get("en") or str(buyer)

        cpv = notice.get("cpv-code", "")
        if isinstance(cpv, list):
            cpv = ",".join(str(c) for c in cpv)

        desc = notice.get("description", "")
        if isinstance(desc, dict):
            desc = desc.get("sv") or desc.get("en") or str(desc)
        elif isinstance(desc, list) and desc:
            desc = str(desc[0])

        place = notice.get("place-of-performance", "")
        if isinstance(place, list) and place:
            place = place[0]
        if isinstance(place, dict):
            place = place.get("sv") or place.get("en") or str(place)

        return {
            "source": "ted",
            "source_id": str(notice.get("notice-id", "")),
            "title": title,
            "buyer": str(buyer) if buyer else None,
            "geography": str(place) if place else None,
            "cpv_codes": str(cpv) if cpv else None,
            "procedure_type": notice.get("procedure-type"),
            "published_date": notice.get("publication-date"),
            "deadline": notice.get("deadline-receipt-tenders"),
            "estimated_value": self._parse_value(notice.get("estimated-total-value")),
            "currency": "EUR",
            "status": "published",
            "url": notice.get("notice-url") or f"https://ted.europa.eu/en/notice/-/detail/{notice.get('notice-id', '')}",
            "description": str(desc)[:2000] if desc else None,
        }

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
        return None
