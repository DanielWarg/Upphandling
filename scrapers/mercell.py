"""Mercell scraper — headless browser via Playwright.

Mercell (app.mercell.com) is a JavaScript SPA. We use Playwright to render
search results and BeautifulSoup to parse the rendered HTML.

Search strategy: keyword queries filtered on Sweden via keywords= URL param.
CPV filters don't work on Mercell's SPA — only keywords= is supported.
Max 3 pages per query ≈ 60-90 sec total.
"""

import logging
import re
import time
from typing import Callable

from bs4 import BeautifulSoup

from models import TenderRecord
from .base import BaseScraper

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# --- Selectors (verified against live DOM 2026-03-03) ---
CARD_SEL = '[data-testid^="bopp-card__"]'
TITLE_SEL = '[data-testid="tender-name"]'
PUB_DATE_SEL = '[data-testid="tender-header__publication-date"]'
DEADLINE_SEL = '[data-testid="bid-deadline-date"]'
GEO_SEL = '[data-testid="nuts-list__information"]'
STATUS_SEL = '[data-testid="tender-header__tender-status"]'
NEXT_BTN = "button.p-paginator-next:not(.p-disabled)"
COOKIE_BTN = 'button:has-text("Godkänn alla")'

BASE_URL = "https://app.mercell.com"
SEARCH_PATH = "/search"

MAX_PAGES_PER_QUERY = 3

# Search queries — each runs as a separate search via keywords= param.
# Mercell ignores filter=cpv_code in URLs, but CPV codes work as keywords.
KEYWORD_QUERIES = [
    # CPV codes as keywords (Mercell matches them in tender metadata)
    "80532000",   # Management training services
    "79633000",   # Staff development services
    "79998000",   # Coaching services
    "80570000",   # Personal development training
    # Swedish keyword searches
    "ledarskapsutbildning",
    "kompetensutveckling",
    "organisationsutveckling",
    "teamutveckling",
    "chefsutbildning",
]


def _build_search_urls() -> list[str]:
    """Build Mercell search URLs using keyword queries filtered on Sweden."""
    base = f"{BASE_URL}{SEARCH_PATH}"
    se_filter = "filter=delivery_place_code:SE"

    return [
        f"{base}?keywords={kw}&{se_filter}&page=1"
        for kw in KEYWORD_QUERIES
    ]


def _extract_source_id(url: str) -> str | None:
    """Extract Mercell tender ID from URL path, return as 'MERC-{id}'."""
    m = re.search(r"/tender/(-?\d+)", url)
    if m:
        return f"MERC-{m.group(1)}"
    return None


def _parse_date_text(text: str | None) -> str | None:
    """Parse publication date from various formats.

    Handles both Swedish ("Publicerad 2026-03-03") and English ("Published 2026-03-03"),
    plus DD/MM/YYYY variants.
    """
    if not text:
        return None
    # Try YYYY-MM-DD anywhere in text
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    # Try DD/MM/YYYY
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


def _parse_deadline_text(text: str | None) -> str | None:
    """Parse deadline from various formats.

    Handles YYYY-MM-DD and DD/MM/YYYY (with optional HH:MM).
    """
    if not text:
        return None
    text = text.strip()
    # Try YYYY-MM-DD
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    # Try DD/MM/YYYY
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


def parse_search_html(html: str) -> list[TenderRecord]:
    """Parse rendered Mercell search HTML into TenderRecords.

    Pure function — no browser needed. Testable with saved HTML fixtures.
    """
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all(attrs={"data-testid": re.compile(r"^bopp-card__")})
    results: list[TenderRecord] = []

    for card in cards:
        # Title + URL
        title_el = card.find(attrs={"data-testid": "tender-name"})
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title:
            continue

        link = title_el.find("a")
        href = link.get("href", "") if link else ""
        source_id = _extract_source_id(href)
        if not source_id:
            # Try from card data-testid: bopp-card__1234
            card_tid = card.get("data-testid", "")
            m = re.search(r"bopp-card__(-?\d+)", card_tid)
            if m:
                source_id = f"MERC-{m.group(1)}"
            else:
                continue

        # Build full URL (strip query params from href)
        tender_path = href.split("?")[0] if href else ""
        url = f"{BASE_URL}{tender_path}" if tender_path else None

        # Publication date
        pub_el = card.find(attrs={"data-testid": "tender-header__publication-date"})
        published_date = _parse_date_text(pub_el.get_text(strip=True)) if pub_el else None

        # Deadline
        dl_el = card.find(attrs={"data-testid": "bid-deadline-date"})
        deadline = _parse_deadline_text(dl_el.get_text(strip=True)) if dl_el else None

        # Geography
        geo_el = card.find(attrs={"data-testid": "nuts-list__information"})
        geography = geo_el.get_text(strip=True) if geo_el else None

        try:
            record = TenderRecord(
                source="mercell",
                source_id=source_id,
                title=title,
                buyer=None,  # Not available in search results
                geography=geography,
                published_date=published_date,
                deadline=deadline,
                url=url,
                status="published",
            )
            results.append(record)
        except Exception as e:
            logger.warning("[Mercell] Failed to create TenderRecord for %s: %s", source_id, e)

    return results


class MercellScraper(BaseScraper):
    name = "mercell"

    def fetch(
        self,
        on_progress: Callable[[str], None] | None = None,
    ) -> list[TenderRecord]:
        if not HAS_PLAYWRIGHT:
            msg = (
                "[Mercell] playwright saknas — installera med: "
                "pip install playwright && playwright install chromium"
            )
            print(msg)
            if on_progress:
                on_progress(msg)
            return []

        urls = _build_search_urls()
        seen_ids: set[str] = set()
        all_results: list[TenderRecord] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()

            for i, url in enumerate(urls, 1):
                if on_progress:
                    on_progress(f"[Mercell] Sökning {i}/{len(urls)}...")
                try:
                    results = self._fetch_search_results(page, url, seen_ids)
                    all_results.extend(results)
                    if on_progress:
                        on_progress(f"[Mercell] Sökning {i}: {len(results)} nya resultat")
                except Exception as e:
                    logger.error("[Mercell] Error on search %d: %s", i, e)
                    if on_progress:
                        on_progress(f"[Mercell] Fel vid sökning {i}: {e}")

            browser.close()

        if on_progress:
            on_progress(f"[Mercell] Totalt {len(all_results)} upphandlingar hämtade")
        print(f"[Mercell] Hämtade {len(all_results)} upphandlingar totalt")
        return all_results

    def _fetch_search_results(
        self,
        page,
        url: str,
        seen_ids: set[str],
    ) -> list[TenderRecord]:
        """Navigate to search URL, dismiss cookie banner, extract cards, paginate."""
        results: list[TenderRecord] = []

        page.goto(url, wait_until="domcontentloaded", timeout=30_000)

        # Dismiss cookie banner if present
        self._dismiss_cookie_banner(page)

        # Wait for cards to render (SPA never reaches networkidle)
        try:
            page.wait_for_selector(CARD_SEL, timeout=15_000)
        except PwTimeout:
            logger.info("[Mercell] No cards found for URL: %s", url)
            return results

        for page_num in range(1, MAX_PAGES_PER_QUERY + 1):
            html = page.content()
            records = parse_search_html(html)

            for rec in records:
                if rec.source_id not in seen_ids:
                    seen_ids.add(rec.source_id)
                    results.append(rec)

            # Try next page
            if page_num < MAX_PAGES_PER_QUERY:
                if not self._go_next_page(page):
                    break

            time.sleep(1)  # Polite delay between pages

        return results

    def _dismiss_cookie_banner(self, page) -> None:
        """Click 'Godkänn alla' cookie button if present."""
        try:
            btn = page.query_selector(COOKIE_BTN)
            if btn:
                btn.click()
                time.sleep(0.5)
        except Exception:
            pass  # Cookie banner not critical

    def _go_next_page(self, page) -> bool:
        """Click next page button if enabled. Returns True if pagination succeeded."""
        try:
            btn = page.query_selector(NEXT_BTN)
            if not btn:
                return False
            btn.click()
            # Wait for new cards to load
            page.wait_for_selector(CARD_SEL, timeout=10_000)
            time.sleep(1)
            return True
        except (PwTimeout, Exception) as e:
            logger.debug("[Mercell] Pagination stopped: %s", e)
            return False
