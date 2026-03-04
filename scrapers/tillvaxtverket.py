"""Tillväxtverket scraper — hämtar utlysningar via RSS-feed + Playwright-detaljer.

RSS: https://tillvaxtverket.se/4.3409dae11877922a04096d8d/12.3409dae11877922a04096da6.portlet?state=rss&sv.contenttype=text/xml;charset=UTF-8
Standard RSS 2.0 med title, link, pubDate, guid per item.
Detail pages scraped via Playwright for description + deadline.
"""

from __future__ import annotations

import hashlib
import logging
import re as re_mod
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

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

RSS_URL = (
    "https://tillvaxtverket.se/4.3409dae11877922a04096d8d/"
    "12.3409dae11877922a04096da6.portlet"
    "?state=rss&sv.contenttype=text/xml;charset=UTF-8"
)

MAX_DETAIL_PAGES = 20


class TillvaxtverketScraper(BaseScraper):
    """Scraper for Tillväxtverket grant announcements (bidrag/utlysningar)."""

    name = "tillvaxtverket"

    def fetch(self) -> list[TenderRecord]:
        """Fetch grant calls from Tillväxtverket RSS feed."""
        logger.info("Tillväxtverket: fetching RSS feed")

        def _do_fetch() -> httpx.Response:
            resp = httpx.get(RSS_URL, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            return resp

        resp = with_backoff(_do_fetch)
        records = _parse_rss(resp.content)
        logger.info("Tillväxtverket: %d utlysningar parsed", len(records))

        # Enrich with detail page data (description + deadline)
        if HAS_PLAYWRIGHT:
            records = _fetch_detail_pages(records)
        else:
            logger.warning("Tillväxtverket: Playwright ej installerat — detaljsidor (description/deadline) hoppas över")

        return records


def _parse_rss(xml_bytes: bytes) -> list[TenderRecord]:
    """Parse Tillväxtverket RSS XML into TenderRecords. Pure function for testing."""
    records: list[TenderRecord] = []

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        logger.error("Tillväxtverket: RSS parse error: %s", e)
        return []

    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pub_date_el = item.find("pubDate")
        guid_el = item.find("guid")

        title = (title_el.text or "").strip() if title_el is not None else ""
        link = (link_el.text or "").strip() if link_el is not None else ""
        guid = (guid_el.text or "").strip() if guid_el is not None else ""

        if not title:
            continue

        # Build source_id from guid or link
        source_id = _extract_source_id(guid or link)

        # Parse publication date from RFC 822
        published_date = None
        if pub_date_el is not None and pub_date_el.text:
            published_date = _parse_rfc822_date(pub_date_el.text.strip())

        try:
            record = TenderRecord(
                record_type="bidrag",
                source="tillvaxtverket",
                source_id=source_id,
                title=title,
                buyer="Tillväxtverket",
                url=link or None,
                published_date=published_date,
                status="published",
            )
            records.append(record)
        except Exception as e:
            logger.warning("Tillväxtverket: skipping item: %s", e)

    return records


def _extract_source_id(url_or_guid: str) -> str:
    """Extract a stable source ID from the URL or GUID.

    URLs look like: ...utlysningar/forstudierinomforbattring...11681.html
    We extract the numeric suffix if present, else hash the URL.
    """
    if not url_or_guid:
        return "TV-unknown"

    # Try to find trailing numeric ID (e.g., "...11681.html")
    import re
    match = re.search(r"(\d{4,})\.html", url_or_guid)
    if match:
        return f"TV-{match.group(1)}"

    # Fallback: short hash of the URL
    url_hash = hashlib.md5(url_or_guid.encode()).hexdigest()[:8]
    return f"TV-{url_hash}"


def _parse_rfc822_date(date_str: str) -> str | None:
    """Parse RFC 822 date (e.g., 'Wed, 25 Feb 2026 13:41:04 +0100') to ISO date string."""
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.date().isoformat()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Detail page scraping (Playwright)
# ---------------------------------------------------------------------------

# Swedish month names → month number
_SV_MONTHS = {
    "januari": "01", "februari": "02", "mars": "03", "april": "04",
    "maj": "05", "juni": "06", "juli": "07", "augusti": "08",
    "september": "09", "oktober": "10", "november": "11", "december": "12",
}


def _parse_detail_html(html: str) -> dict:
    """Parse a Tillväxtverket detail page. Returns {'description': str|None, 'deadline': str|None}.

    Pure function for testing.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove nav/header/footer
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # --- Description: main body text ---
    description = None
    # Look for the main content area — typically after the h1 title
    main = soup.find("main") or soup.find("article") or soup
    paragraphs = main.find_all("p")
    text_parts = []
    for p in paragraphs:
        t = p.get_text(strip=True)
        if t and len(t) > 20:
            text_parts.append(t)
    if text_parts:
        description = " ".join(text_parts)[:3000]

    # --- Deadline: look for "Stängd DD månad YYYY" or "stänger DD månad YYYY" ---
    deadline = None
    full_text = soup.get_text(" ", strip=True)

    # Pattern: "Stängd 17 februari 2026" or "stänger 17 februari 2026"
    months_pattern = "|".join(_SV_MONTHS.keys())
    dl_match = re_mod.search(
        rf'(?:stäng(?:d|er))\s+(\d{{1,2}})\s+({months_pattern})\s+(\d{{4}})',
        full_text,
        re_mod.IGNORECASE,
    )
    if dl_match:
        day = dl_match.group(1).zfill(2)
        month = _SV_MONTHS.get(dl_match.group(2).lower(), "01")
        year = dl_match.group(3)
        deadline = f"{year}-{month}-{day}"

    # Fallback: "Sista ansökningsdag: DD månad YYYY" or similar
    if not deadline:
        dl_match2 = re_mod.search(
            rf'sista\s+ansökningsdag[:\s]+(\d{{1,2}})\s+({months_pattern})\s+(\d{{4}})',
            full_text,
            re_mod.IGNORECASE,
        )
        if dl_match2:
            day = dl_match2.group(1).zfill(2)
            month = _SV_MONTHS.get(dl_match2.group(2).lower(), "01")
            year = dl_match2.group(3)
            deadline = f"{year}-{month}-{day}"

    return {"description": description, "deadline": deadline}


def _fetch_detail_pages(records: list[TenderRecord]) -> list[TenderRecord]:
    """Enrich records with description and deadline from detail pages via Playwright.

    Only fetches records missing description. Limited to MAX_DETAIL_PAGES per run.
    """
    if not HAS_PLAYWRIGHT:
        return records

    to_fetch = [r for r in records if not r.description and r.url][:MAX_DETAIL_PAGES]
    if not to_fetch:
        return records

    logger.info("Tillväxtverket: fetching %d detail pages", len(to_fetch))
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
                    logger.warning("Tillväxtverket: detail page error %s: %s", record.url, e)

            browser.close()
    except Exception as e:
        logger.error("Tillväxtverket: Playwright error: %s", e)
        return records

    # Build updated records
    updated: list[TenderRecord] = []
    for record in records:
        data = url_to_data.get(record.url) if record.url else None
        if data:
            updated.append(record.model_copy(update={
                "description": data["description"] or record.description,
                "deadline": data["deadline"] or record.deadline,
            }))
        else:
            updated.append(record)

    enriched = sum(1 for u in url_to_data.values() if u.get("description"))
    logger.info("Tillväxtverket: enriched %d records with detail data", enriched)
    return updated
