"""e-Avrop scraper using httpx + BeautifulSoup.

Scrapes the public procurement listing at e-avrop.com/e-upphandling/Default.aspx.
ASP.NET WebForms with ViewState-based pagination.
Server-side filtering handles relevance — no client-side double-filtering.
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

LIST_URL = "https://www.e-avrop.com/e-upphandling/Default.aspx"
BASE_URL = "https://www.e-avrop.com"
MAX_PAGES = 6


class EAvropScraper(BaseScraper):
    name = "eavrop"

    def fetch(self) -> list[TenderRecord]:
        all_results: list[TenderRecord] = []
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                def _get_initial():
                    r = client.get(LIST_URL)
                    r.raise_for_status()
                    return r
                resp = with_backoff(_get_initial)

                page_results = self._parse_listing(resp.text, client)
                all_results.extend(page_results)

                # Paginate using ASP.NET PostBack
                for page_num in range(2, MAX_PAGES + 1):
                    form_data = self._build_postback(resp.text, page_num)
                    if not form_data:
                        break
                    def _post_page(data=form_data):
                        r = client.post(LIST_URL, data=data)
                        r.raise_for_status()
                        return r
                    resp = with_backoff(_post_page)
                    page_results = self._parse_listing(resp.text, client)
                    if not page_results:
                        break
                    all_results.extend(page_results)

        except Exception as e:
            print(f"[e-Avrop] Fetch error: {e}")

        # No client-side filtering — return all results, scorer handles relevance
        print(f"[e-Avrop] Fetched {len(all_results)} notices")
        return all_results

    def _parse_listing(self, html: str, client: httpx.Client | None = None) -> list[TenderRecord]:
        """Parse all rows from the ASP.NET GridView table."""
        soup = BeautifulSoup(html, "html.parser")
        table = (
            soup.find("table", id="ctl00_mainContent_tenderGridView")
            or soup.find("table", {"id": lambda x: x and "tenderGridView" in x})
        )
        if not table:
            return []

        rows = table.select("tr")
        notices: list[TenderRecord] = []

        for row in rows:
            if row.find("th"):
                continue
            try:
                proc = self._parse_listing_row(row, client)
                if proc:
                    notices.append(proc)
            except Exception as e:
                print(f"[e-Avrop] Error parsing row: {e}")
                continue
        return notices

    def _parse_listing_row(self, row, client: httpx.Client | None = None) -> TenderRecord | None:
        """Extract procurement data from a single table row."""
        cells = row.select("td")
        if len(cells) < 5:
            return None

        # Column order: Rubrik | Publicerad | Organisation | Omrade | Deadline
        link = cells[0].select_one("a[href]")
        title = cells[0].get_text(strip=True)
        if not title:
            return None

        href = link.get("href", "") if link else ""
        url = f"{BASE_URL}/{href.lstrip('/')}" if href and not href.startswith("http") else href

        # Extract source_id from URL query param
        source_id = title[:50]
        if "id=" in href:
            source_id = href.split("id=")[-1].split("&")[0]

        published_date = self._extract_date(cells[1].get_text(strip=True))
        buyer = cells[2].get_text(strip=True) or None
        cpv_codes = cells[3].get_text(strip=True) or None
        deadline = self._extract_date(cells[4].get_text(strip=True))

        # Fetch description and geography from detail page
        description = None
        geography = None
        if client and url:
            description, geography = self._fetch_detail(client, url)

        # Flag as needs_review if title is suspiciously short
        status = "published"
        if len(title) < 5:
            status = "needs_review"
            logger.warning("[e-Avrop] Notice EA-%s has very short title: %s", source_id, title)

        try:
            return TenderRecord(
                source="eavrop",
                source_id=f"EA-{source_id}",
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
            logger.warning("[e-Avrop] Failed to create TenderRecord for EA-%s: %s", source_id, e)
            return None

    @staticmethod
    def _fetch_detail(client: httpx.Client, detail_url: str) -> tuple[str | None, str | None]:
        """Fetch description and geography from the detail page.

        Returns (description, geography).
        """
        try:
            def _get():
                r = client.get(detail_url, timeout=15)
                r.raise_for_status()
                return r
            resp = with_backoff(_get)
            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract description
            description = None
            for label_text in ["Beskrivning", "Beskrivning av upphandlingen", "Varugrupp"]:
                label = soup.find(string=re.compile(label_text, re.IGNORECASE))
                if label:
                    parent = label.find_parent(["dt", "th", "label", "strong", "b", "div", "td"])
                    if parent:
                        sibling = parent.find_next_sibling(["dd", "td", "span", "div", "p"])
                        if sibling:
                            text = sibling.get_text(strip=True)
                            if text and len(text) > 10:
                                description = text[:2000]
                                break

            # Extract geography
            geography = None
            for label_text in ["Leveransort", "Ort", "Kommun", "Region", "NUTS"]:
                label = soup.find(string=re.compile(label_text, re.IGNORECASE))
                if label:
                    parent = label.find_parent(["dt", "th", "label", "strong", "b", "div", "td"])
                    if parent:
                        sibling = parent.find_next_sibling(["dd", "td", "span", "div"])
                        if sibling:
                            text = sibling.get_text(strip=True)
                            if text and len(text) > 1:
                                geography = text
                                break

            return description, geography
        except Exception:
            return None, None

    @staticmethod
    def _extract_date(text: str | None) -> str | None:
        """Extract a YYYY-MM-DD date from cell text."""
        if not text:
            return None
        m = re.search(r"\d{4}-\d{2}-\d{2}", text)
        return m.group(0) if m else text

    @staticmethod
    def _build_postback(html: str, page_num: int) -> dict | None:
        """Build ASP.NET PostBack form data for pagination."""
        soup = BeautifulSoup(html, "html.parser")

        viewstate = soup.find("input", {"name": "__VIEWSTATE"})
        if not viewstate:
            return None

        data = {
            "__EVENTTARGET": "ctl00$mainContent$tenderGridView",
            "__EVENTARGUMENT": f"Page${page_num}",
            "__VIEWSTATE": viewstate.get("value", ""),
        }

        for field_name in ("__VIEWSTATEGENERATOR", "__EVENTVALIDATION", "__VIEWSTATEENCRYPTED"):
            field = soup.find("input", {"name": field_name})
            if field:
                data[field_name] = field.get("value", "")

        return data
