"""Vinnova scraper — hämtar utlysningar via Vinnovas öppna data-API + Playwright-detaljer.

API: https://data.vinnova.se/api/utlysningar/{datum}
Returnerar utlysningar ändrade sedan angivet datum (ÅÅÅÅ-MM-DD).
Detail pages scraped via Playwright for deadline (sista ansökningsdag).
"""

from __future__ import annotations

import logging
import re as re_mod
from datetime import datetime, timedelta

import httpx
from bs4 import BeautifulSoup

from .base import BaseScraper
from .backoff import with_backoff
from models import TenderRecord

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

API_URL = "https://data.vinnova.se/api/utlysningar"

MAX_DETAIL_PAGES = 20


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

        # Enrich with deadline from detail pages
        if HAS_PLAYWRIGHT:
            records = _fetch_deadlines(records)
        else:
            logger.warning("Vinnova: Playwright ej installerat — detaljsidor (deadline) hoppas över")

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


# ---------------------------------------------------------------------------
# Detail page scraping (Playwright) — deadline extraction
# ---------------------------------------------------------------------------

# Swedish month names → month number
_SV_MONTHS = {
    "jan": "01", "feb": "02", "mars": "03", "mar": "03", "apr": "04",
    "maj": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "okt": "10", "nov": "11", "dec": "12",
    "januari": "01", "februari": "02", "april": "04",
    "juni": "06", "juli": "07", "augusti": "08",
    "september": "09", "oktober": "10", "november": "11", "december": "12",
}


def _parse_detail_html(html: str) -> dict:
    """Parse a Vinnova detail page. Returns {'deadline': str|None}.

    Looks for 'Sista ansökningsdag' followed by a date, or 'Stänger den DD månad YYYY'.
    Pure function for testing.
    """
    soup = BeautifulSoup(html, "html.parser")
    full_text = soup.get_text(" ", strip=True)

    deadline = None
    months_pattern = "|".join(_SV_MONTHS.keys())

    # Pattern 1: "Stänger den DD månad YYYY" or "Stänger DD månad YYYY"
    dl_match = re_mod.search(
        rf'[Ss]tänger\s+(?:den\s+)?(\d{{1,2}})\s+({months_pattern})\.?\s+(\d{{4}})',
        full_text,
    )
    if dl_match:
        day = dl_match.group(1).zfill(2)
        month = _SV_MONTHS.get(dl_match.group(2).lower().rstrip("."), "01")
        year = dl_match.group(3)
        deadline = f"{year}-{month}-{day}"

    # Pattern 2: date under "Sista ansökningsdag" in "Viktiga datum" section
    if not deadline:
        # "DD månad YYYY" followed/preceded by "Sista ansökningsdag"
        dl_match2 = re_mod.search(
            rf'(\d{{1,2}})\s+({months_pattern})\.?\s+(\d{{4}})\s+(?:kl\s+\d{{1,2}}:\d{{2}}\s+)?Sista\s+ansökningsdag',
            full_text,
        )
        if dl_match2:
            day = dl_match2.group(1).zfill(2)
            month = _SV_MONTHS.get(dl_match2.group(2).lower().rstrip("."), "01")
            year = dl_match2.group(3)
            deadline = f"{year}-{month}-{day}"

    # Pattern 3: "Sista ansökningsdag DD månad YYYY"
    if not deadline:
        dl_match3 = re_mod.search(
            rf'[Ss]ista\s+ansökningsdag[:\s]+(\d{{1,2}})\s+({months_pattern})\.?\s+(\d{{4}})',
            full_text,
        )
        if dl_match3:
            day = dl_match3.group(1).zfill(2)
            month = _SV_MONTHS.get(dl_match3.group(2).lower().rstrip("."), "01")
            year = dl_match3.group(3)
            deadline = f"{year}-{month}-{day}"

    return {"deadline": deadline}


def _fetch_deadlines(records: list[TenderRecord]) -> list[TenderRecord]:
    """Enrich records with deadline from Vinnova detail pages via Playwright.

    Only fetches records missing deadline. Limited to MAX_DETAIL_PAGES per run.
    """
    if not HAS_PLAYWRIGHT:
        return records

    to_fetch = [r for r in records if not r.deadline and r.url][:MAX_DETAIL_PAGES]
    if not to_fetch:
        return records

    logger.info("Vinnova: fetching %d detail pages for deadlines", len(to_fetch))
    url_to_data: dict[str, dict] = {}

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()

            for record in to_fetch:
                try:
                    page.goto(record.url, wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(1000)
                    html = page.content()
                    data = _parse_detail_html(html)
                    url_to_data[record.url] = data
                except Exception as e:
                    logger.warning("Vinnova: detail page error %s: %s", record.url, e)

            browser.close()
    except Exception as e:
        logger.error("Vinnova: Playwright error: %s", e)
        return records

    # Build updated records
    updated: list[TenderRecord] = []
    for record in records:
        data = url_to_data.get(record.url) if record.url else None
        if data and data.get("deadline"):
            updated.append(record.model_copy(update={"deadline": data["deadline"]}))
        else:
            updated.append(record)

    enriched = sum(1 for u in url_to_data.values() if u.get("deadline"))
    logger.info("Vinnova: enriched %d records with deadlines", enriched)
    return updated
