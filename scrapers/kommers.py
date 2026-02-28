"""KommersAnnons scraper using httpx + BeautifulSoup.

Scrapes the public tender notice list at kommersannons.se/Notices/TenderNotices.
Server-side search filter handles relevance — no client-side double-filtering.
"""

from __future__ import annotations

import logging
import re
import httpx
from bs4 import BeautifulSoup

from .base import BaseScraper
from .backoff import with_backoff
from models import TenderRecord

logger = logging.getLogger(__name__)

BASE_URL = "https://www.kommersannons.se"
LIST_URL = f"{BASE_URL}/Notices/TenderNotices"
MAX_PAGES = 5

# Server-side search filter — matches sent to KommersAnnons search
SEARCH_FILTERS = {
    "SearchString": "utbildning ledarskap coaching organisationsutveckling",
    "SelectedContractType": "",
}


class KommersScraper(BaseScraper):
    name = "kommers"

    def fetch(self) -> list[TenderRecord]:
        results: list[TenderRecord] = []
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                def _get_filtered():
                    r = client.get(LIST_URL, params={"SearchString": SEARCH_FILTERS["SearchString"]})
                    r.raise_for_status()
                    return r
                resp = with_backoff(_get_filtered)
                filtered = self._parse_listing(resp.text, client)

                if filtered:
                    results.extend(filtered)
                else:
                    print("[Kommers] Sokfiltret gav inga resultat, faller tillbaka till ofiltrerad scraping")
                    def _get_unfiltered():
                        r = client.get(LIST_URL)
                        r.raise_for_status()
                        return r
                    resp = with_backoff(_get_unfiltered)
                    results.extend(self._parse_listing(resp.text, client))

                # Paginate via POST with hidden form fields
                for _ in range(MAX_PAGES - 1):
                    next_form = self._extract_next_form(resp.text)
                    if not next_form:
                        break
                    def _post_next(data=next_form):
                        r = client.post(LIST_URL, data=data)
                        r.raise_for_status()
                        return r
                    resp = with_backoff(_post_next)
                    page_results = self._parse_listing(resp.text, client)
                    if not page_results:
                        break
                    results.extend(page_results)

        except Exception as e:
            print(f"[Kommers] Fetch error: {e}")

        # No client-side filtering — server search handles relevance
        print(f"[Kommers] Fetched {len(results)} notices")
        return results

    def _parse_listing(self, html: str, client: httpx.Client | None = None) -> list[TenderRecord]:
        """Parse all notice rows from a listing page."""
        soup = BeautifulSoup(html, "html.parser")
        notices: list[TenderRecord] = []

        for row in soup.select("div.row.mt-4.mb-4"):
            try:
                proc = self._parse_notice_row(row, client)
                if proc:
                    notices.append(proc)
            except Exception as e:
                print(f"[Kommers] Error parsing row: {e}")
                continue
        return notices

    def _parse_notice_row(self, row, client: httpx.Client | None = None) -> TenderRecord | None:
        """Extract procurement data from a single notice row."""
        link = row.select_one("h4 > a[href]")
        if not link:
            return None

        href = link.get("href", "")
        raw_title = link.get_text(strip=True)
        if not raw_title:
            return None

        # Extract numeric ID from /Notices/TenderNotice/{id}
        id_match = re.search(r"/Notices/TenderNotice/(\d+)", href)
        source_id = id_match.group(1) if id_match else raw_title[:50]

        # Title may contain "REF - Title", split on first " - "
        if " - " in raw_title:
            _ref, title = raw_title.split(" - ", 1)
        else:
            title = raw_title

        url = f"{BASE_URL}{href}" if href.startswith("/") else href

        # Parse <small> tags for metadata
        smalls = row.select("small")
        published_date = None
        geography = None
        cpv_codes = None
        for sm in smalls:
            text = sm.get_text(strip=True)
            if "publicering" in text.lower():
                date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
                if date_match:
                    published_date = date_match.group(1)
            elif text.startswith("NUTS:"):
                geography = text.replace("NUTS:", "").strip()
            elif text.startswith("CPV:"):
                cpv_codes = text.replace("CPV:", "").strip()

        # Description from <p> tag
        desc_tag = row.select_one("p")
        description = desc_tag.get_text(strip=True) if desc_tag else None

        # Days left -> approximate deadline
        deadline = None
        days_left_tag = row.select_one("div.col-md-2 h4")
        if days_left_tag:
            try:
                days = int(days_left_tag.get_text(strip=True))
                from datetime import date, timedelta
                deadline = (date.today() + timedelta(days=days)).isoformat()
            except (ValueError, TypeError):
                pass

        # Extract buyer from detail page if available
        buyer = None
        if client and href:
            buyer = self._fetch_buyer(client, url)

        # Flag as needs_review if title looks incomplete
        status = "published"
        if not title or len(title) < 5:
            status = "needs_review"
            logger.warning("[Kommers] Notice KOM-%s has very short title", source_id)

        try:
            return TenderRecord(
                source="kommers",
                source_id=f"KOM-{source_id}",
                title=title,
                buyer=buyer,
                geography=geography,
                cpv_codes=cpv_codes,
                procedure_type=None,
                published_date=published_date,
                deadline=deadline,
                estimated_value=None,
                currency="SEK",
                status=status,
                url=url,
                description=description,
            )
        except Exception as e:
            logger.warning("[Kommers] Failed to create TenderRecord for KOM-%s: %s", source_id, e)
            return None

    @staticmethod
    def _fetch_buyer(client: httpx.Client, detail_url: str) -> str | None:
        """Fetch buyer name from the detail page."""
        try:
            def _get():
                r = client.get(detail_url, timeout=15)
                r.raise_for_status()
                return r
            resp = with_backoff(_get)
            soup = BeautifulSoup(resp.text, "html.parser")

            # Look for buyer/organization in detail page
            # Common patterns: label "Upphandlande myndighet" or "Organisation"
            for label_text in ["Upphandlande myndighet", "Organisation", "Myndighet"]:
                label = soup.find(string=re.compile(label_text, re.IGNORECASE))
                if label:
                    parent = label.find_parent(["dt", "th", "label", "strong", "b", "div"])
                    if parent:
                        # Try next sibling dd/td/span
                        sibling = parent.find_next_sibling(["dd", "td", "span", "div"])
                        if sibling:
                            buyer = sibling.get_text(strip=True)
                            if buyer and len(buyer) > 2:
                                return buyer
            return None
        except Exception:
            return None

    @staticmethod
    def _extract_next_form(html: str) -> dict | None:
        """Extract hidden form data for the 'Nasta' (next) pagination button."""
        soup = BeautifulSoup(html, "html.parser")

        next_btn = soup.find("button", string=re.compile(r"Nästa"))
        if not next_btn:
            next_btn = soup.find("a", string=re.compile(r"Nästa"))
        if not next_btn:
            icon = soup.find("i", class_="fa-angle-double-right")
            if icon:
                next_btn = icon.find_parent("button") or icon.find_parent("a")
        if not next_btn:
            return None

        form = next_btn.find_parent("form")
        if not form:
            return None

        data = {}
        for inp in form.select("input[type='hidden']"):
            name = inp.get("name")
            if name:
                data[name] = inp.get("value", "")
        return data if data else None
