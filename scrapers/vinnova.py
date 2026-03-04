"""Vinnova scraper — hämtar utlysningar via Vinnovas öppna data-API.

API: https://data.vinnova.se/api/utlysningar/{datum}
Returnerar utlysningar ändrade sedan angivet datum (ÅÅÅÅ-MM-DD).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx

from .base import BaseScraper
from .backoff import with_backoff
from models import TenderRecord

logger = logging.getLogger(__name__)

API_URL = "https://data.vinnova.se/api/utlysningar"


class VinnovaScraper(BaseScraper):
    """Scraper for Vinnova grant announcements (bidrag/utlysningar)."""

    name = "vinnova"

    def __init__(self, lookback_days: int = 180):
        self.lookback_days = lookback_days

    def fetch(self) -> list[TenderRecord]:
        """Fetch open grant calls from Vinnova API."""
        cutoff = (datetime.now() - timedelta(days=self.lookback_days)).strftime("%Y-%m-%d")
        url = f"{API_URL}/{cutoff}"

        logger.info("Vinnova: fetching utlysningar since %s", cutoff)

        def _do_fetch() -> httpx.Response:
            resp = httpx.get(url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            return resp

        resp = with_backoff(_do_fetch)
        items = resp.json()

        if not isinstance(items, list):
            logger.warning("Vinnova API returned non-list: %s", type(items))
            return []

        records = _parse_items(items)
        logger.info("Vinnova: %d utlysningar parsed", len(records))
        return records


def _parse_items(items: list[dict]) -> list[TenderRecord]:
    """Parse Vinnova API response items into TenderRecords. Pure function for testing."""
    records: list[TenderRecord] = []

    for item in items:
        diarienr = item.get("Diarienummer", "").strip()
        if not diarienr:
            continue

        titel = (item.get("Titel") or "").strip()
        if not titel:
            continue

        # Build source_id
        source_id = f"VINN-{diarienr}"

        # Description — prefer Swedish, fall back to English
        beskrivning = (item.get("Beskrivning") or "").strip()
        if not beskrivning:
            beskrivning = (item.get("BeskrivningEngelska") or "").strip()

        # Published date
        pub_raw = item.get("Publiceringsdatum") or ""
        published_date = _parse_date(pub_raw)

        # URL — construct from diarienummer
        url = f"https://www.vinnova.se/sok-finansiering/hitta-finansiering/{diarienr}/"

        try:
            record = TenderRecord(
                record_type="bidrag",
                source="vinnova",
                source_id=source_id,
                title=titel,
                buyer="Vinnova",
                description=beskrivning or None,
                published_date=published_date,
                url=url,
                status="published",
            )
            records.append(record)
        except Exception as e:
            logger.warning("Vinnova: skipping item %s: %s", diarienr, e)

    return records


def _parse_date(raw: str) -> str | None:
    """Parse Vinnova date formats (ISO 8601 timestamps)."""
    if not raw:
        return None
    # Typical: "2026-01-15T10:00:00" or "2026-01-15"
    return raw.strip()[:10] if len(raw) >= 10 else None
