"""TED (Tenders Electronic Daily) API-scraper.

Använder det fria v3 sök-API:et — ingen autentisering krävs för publicerade notices.
Kör flera sökningar för att fånga svenska upphandlingar relevanta för kollektivtrafik-IT.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

import httpx
from .base import BaseScraper
from .backoff import with_backoff
from models import TenderRecord

logger = logging.getLogger(__name__)

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

# Dynamic date cutoff — 6 months ago
def _date_cutoff() -> str:
    return (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")


# Sökfrågor — HAST Utveckling: ledarskap, utbildning, organisationsutveckling
# TED v3 API: FT= för fulltext, classification-cpv= för CPV-koder
def _build_queries() -> list[str]:
    cutoff = _date_cutoff()
    return [
        # Kärnkoder — chefsutbildning, personalutveckling, coaching
        f"CY=SWE AND (classification-cpv=80532000 OR classification-cpv=79633000 OR classification-cpv=79632000 OR classification-cpv=79998000) AND publication-date>{cutoff}",
        # Personalutbildning & personlig utveckling
        f"CY=SWE AND (classification-cpv=80511000 OR classification-cpv=80570000 OR classification-cpv=80590000) AND publication-date>{cutoff}",
        # Managementkonsult + utbildnings-nyckelord
        f"CY=SWE AND (classification-cpv=79414000 OR classification-cpv=79411100 OR classification-cpv=79410000) AND (FT=ledarskap OR FT=utbildning OR FT=coaching OR FT=organisation OR FT=kompetens) AND publication-date>{cutoff}",
        # Fulltext — ledarskap & chefsutveckling
        f"CY=SWE AND (FT=ledarskapsutbildning OR FT=ledarskapsutveckling OR FT=chefsutveckling OR FT=chefsutbildning OR FT=ledarskapsprogram) AND publication-date>{cutoff}",
        # Fulltext — organisationsutveckling, teamutveckling, coaching
        f"CY=SWE AND (FT=organisationsutveckling OR FT=teamutveckling OR FT=kompetensutveckling OR FT=förändringsledning OR FT=konflikthantering OR FT=stresshantering) AND publication-date>{cutoff}",
    ]

PAGE_SIZE = 50
MAX_PAGES = 4


class TedScraper(BaseScraper):
    name = "ted"

    def fetch(self) -> list[TenderRecord]:
        seen_ids: set[str] = set()
        results = []

        for query in _build_queries():
            query_results = self._fetch_query(query, seen_ids)
            results.extend(query_results)

        print(f"[TED] Hämtade {len(results)} upphandlingar totalt")
        return results

    def _fetch_query(self, query: str, seen_ids: set[str]) -> list[TenderRecord]:
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
                def _do_request(p=payload):
                    r = httpx.post(SEARCH_URL, json=p, timeout=30)
                    r.raise_for_status()
                    return r
                resp = with_backoff(_do_request)
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
                record = self._normalize(notice)
                if record:
                    results.append(record)

            if len(notices) < PAGE_SIZE:
                break
            page += 1

        return results

    def _normalize(self, notice: dict) -> TenderRecord | None:
        """Mappa TED API-fält till TenderRecord."""
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

        # Determine status — flag as needs_review if key fields are missing
        status = "published"
        if not title or title == "Utan titel":
            status = "needs_review"
            logger.warning("[TED] Notice %s missing title", pub_number)
        if not pub_number:
            logger.warning("[TED] Notice missing publication-number, skipping")
            return None

        try:
            return TenderRecord(
                source="ted",
                source_id=pub_number,
                title=title_clean,
                buyer=buyer if buyer else None,
                geography=geography,
                cpv_codes=str(cpv) if cpv else None,
                procedure_type=None,
                published_date=notice.get("publication-date", "")[:10] if notice.get("publication-date") else None,
                deadline=str(deadline)[:10] if deadline else None,
                estimated_value=self._parse_value(est_value),
                currency=str(est_cur) if est_cur else "SEK",
                status=status,
                url=url,
                description=str(desc)[:2000] if desc else None,
            )
        except Exception as e:
            logger.warning("[TED] Failed to create TenderRecord for %s: %s", pub_number, e)
            return None

    @staticmethod
    def _extract_text(val, default: str = "") -> str:
        """Extrahera text från TED:s flerspråkiga fält (föredrar svenska)."""
        if val is None:
            return default
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
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
