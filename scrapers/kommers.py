"""KommersAnnons scraper using httpx + BeautifulSoup.

Scrapes the public tender notice list at kommersannons.se/Notices/TenderNotices.
"""

from __future__ import annotations

import re
import httpx
from bs4 import BeautifulSoup

from .base import BaseScraper

BASE_URL = "https://www.kommersannons.se"
LIST_URL = f"{BASE_URL}/Notices/TenderNotices"
MAX_PAGES = 3  # ~40 notices per page → ~120 max

# Sökfilter för att minska brus — skickas som formulärdata
SEARCH_FILTERS = {
    "SearchString": "kollektivtrafik realtid trafikledning",
    "SelectedContractType": "",  # Alla typer
}


class KommersScraper(BaseScraper):
    name = "kommers"

    def fetch(self) -> list[dict]:
        results: list[dict] = []
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                # Försök med sökfilter först
                resp = client.get(LIST_URL, params={"SearchString": SEARCH_FILTERS["SearchString"]})
                resp.raise_for_status()
                filtered = self._parse_listing(resp.text)

                if filtered:
                    results.extend(filtered)
                else:
                    # Fallback till ofiltrerad scraping om filtret inte ger resultat
                    print("[Kommers] Sökfiltret gav inga resultat, faller tillbaka till ofiltrerad scraping")
                    resp = client.get(LIST_URL)
                    resp.raise_for_status()
                    results.extend(self._parse_listing(resp.text))

                # Paginate via POST with hidden form fields
                for _ in range(MAX_PAGES - 1):
                    next_form = self._extract_next_form(resp.text)
                    if not next_form:
                        break
                    resp = client.post(LIST_URL, data=next_form)
                    resp.raise_for_status()
                    page_results = self._parse_listing(resp.text)
                    if not page_results:
                        break
                    results.extend(page_results)

        except Exception as e:
            print(f"[Kommers] Fetch error: {e}")

        print(f"[Kommers] Fetched {len(results)} notices")
        return results

    def _parse_listing(self, html: str) -> list[dict]:
        """Parse all notice rows from a listing page."""
        soup = BeautifulSoup(html, "html.parser")
        notices: list[dict] = []

        for row in soup.select("div.row.mt-4.mb-4"):
            try:
                proc = self._parse_notice_row(row)
                if proc:
                    notices.append(proc)
            except Exception as e:
                print(f"[Kommers] Error parsing row: {e}")
                continue
        return notices

    def _parse_notice_row(self, row) -> dict | None:
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
                # "Datum då annonsen skickades för publicering 2026-01-28"
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

        # Days left → approximate deadline
        deadline = None
        days_left_tag = row.select_one("div.col-md-2 h4")
        if days_left_tag:
            try:
                days = int(days_left_tag.get_text(strip=True))
                from datetime import date, timedelta
                deadline = (date.today() + timedelta(days=days)).isoformat()
            except (ValueError, TypeError):
                pass

        return {
            "source": "kommers",
            "source_id": f"KOM-{source_id}",
            "title": title,
            "buyer": None,  # Not on listing page
            "geography": geography,
            "cpv_codes": cpv_codes,
            "procedure_type": None,
            "published_date": published_date,
            "deadline": deadline,
            "estimated_value": None,
            "currency": "SEK",
            "status": "published",
            "url": url,
            "description": description,
        }

    @staticmethod
    def _extract_next_form(html: str) -> dict | None:
        """Extract hidden form data for the 'Nästa' (next) pagination button."""
        soup = BeautifulSoup(html, "html.parser")

        # Find the "Nästa" button/link
        next_btn = soup.find("button", string=re.compile(r"Nästa"))
        if not next_btn:
            next_btn = soup.find("a", string=re.compile(r"Nästa"))
        if not next_btn:
            # Look for the >> icon button
            icon = soup.find("i", class_="fa-angle-double-right")
            if icon:
                next_btn = icon.find_parent("button") or icon.find_parent("a")
        if not next_btn:
            return None

        # Collect all hidden input values from the form
        form = next_btn.find_parent("form")
        if not form:
            return None

        data = {}
        for inp in form.select("input[type='hidden']"):
            name = inp.get("name")
            if name:
                data[name] = inp.get("value", "")
        return data if data else None
