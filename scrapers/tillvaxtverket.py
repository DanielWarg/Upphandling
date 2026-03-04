"""Tillväxtverket scraper — hämtar utlysningar via RSS-feed.

RSS: https://tillvaxtverket.se/4.3409dae11877922a04096d8d/12.3409dae11877922a04096da6.portlet?state=rss&sv.contenttype=text/xml;charset=UTF-8
Standard RSS 2.0 med title, link, pubDate, guid per item.
"""

from __future__ import annotations

import hashlib
import logging
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import httpx

from .base import BaseScraper
from .backoff import with_backoff
from models import TenderRecord

logger = logging.getLogger(__name__)

RSS_URL = (
    "https://tillvaxtverket.se/4.3409dae11877922a04096d8d/"
    "12.3409dae11877922a04096da6.portlet"
    "?state=rss&sv.contenttype=text/xml;charset=UTF-8"
)


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
