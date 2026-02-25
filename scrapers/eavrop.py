"""e-Avrop scraper using httpx + BeautifulSoup.

Scrapes the public procurement listing at e-avrop.com/e-upphandling/Default.aspx.
ASP.NET WebForms with ViewState-based pagination.
"""

from __future__ import annotations

import re
import httpx
from bs4 import BeautifulSoup

from .base import BaseScraper

LIST_URL = "https://www.e-avrop.com/e-upphandling/Default.aspx"
BASE_URL = "https://www.e-avrop.com"
MAX_PAGES = 4  # ~25 per page → ~100 max

# Klientsidigt relevansfilter — nyckelord som indikerar potentiell relevans
RELEVANCE_KEYWORDS = [
    "kollektivtrafik", "realtid", "trafikledning", "it-system",
    "biljettsystem", "passagerarinformation", "72000000", "48000000",
    "reseplanerare", "anropsstyrd", "färdtjänst", "serviceresor",
    "trafikinformation", "hållplats", "realtidsinformation",
]


class EAvropScraper(BaseScraper):
    name = "eavrop"

    def fetch(self) -> list[dict]:
        all_results: list[dict] = []
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                resp = client.get(LIST_URL)
                resp.raise_for_status()

                page_results = self._parse_listing(resp.text)
                all_results.extend(page_results)

                # Paginate using ASP.NET PostBack
                for page_num in range(2, MAX_PAGES + 1):
                    form_data = self._build_postback(resp.text, page_num)
                    if not form_data:
                        break
                    resp = client.post(LIST_URL, data=form_data)
                    resp.raise_for_status()
                    page_results = self._parse_listing(resp.text)
                    if not page_results:
                        break
                    all_results.extend(page_results)

        except Exception as e:
            print(f"[e-Avrop] Fetch error: {e}")

        # Klientsidigt relevansfilter
        filtered = [r for r in all_results if self._is_potentially_relevant(r)]
        if filtered:
            print(f"[e-Avrop] Fetched {len(all_results)} notices, {len(filtered)} potentiellt relevanta efter filtrering")
            return filtered
        else:
            # Om inga matchar, returnera allt så vi inte tappar data
            print(f"[e-Avrop] Fetched {len(all_results)} notices (inget matchade filtret, returnerar alla)")
            return all_results

    @staticmethod
    def _is_potentially_relevant(proc: dict) -> bool:
        """Check if a procurement is potentially relevant based on keywords."""
        text = f"{proc.get('title', '')} {proc.get('cpv_codes', '')} {proc.get('buyer', '')}".lower()
        return any(kw in text for kw in RELEVANCE_KEYWORDS)

    def _parse_listing(self, html: str) -> list[dict]:
        """Parse all rows from the ASP.NET GridView table."""
        soup = BeautifulSoup(html, "html.parser")
        table = (
            soup.find("table", id="ctl00_mainContent_tenderGridView")
            or soup.find("table", {"id": lambda x: x and "tenderGridView" in x})
        )
        if not table:
            return []

        rows = table.select("tr")
        notices: list[dict] = []

        # Skip header row(s) — they contain <th> elements
        for row in rows:
            if row.find("th"):
                continue
            try:
                proc = self._parse_listing_row(row)
                if proc:
                    notices.append(proc)
            except Exception as e:
                print(f"[e-Avrop] Error parsing row: {e}")
                continue
        return notices

    def _parse_listing_row(self, row) -> dict | None:
        """Extract procurement data from a single table row."""
        cells = row.select("td")
        if len(cells) < 5:
            return None

        # Column order: Rubrik | Publicerad | Organisation | Område | Deadline
        link = cells[0].select_one("a[href]")
        title = cells[0].get_text(strip=True)
        if not title:
            return None

        href = link.get("href", "") if link else ""
        # Detail URL: /[org]/visa/upphandling.aspx?id=[id]
        url = f"{BASE_URL}/{href.lstrip('/')}" if href and not href.startswith("http") else href

        # Extract source_id from URL query param
        source_id = title[:50]
        if "id=" in href:
            source_id = href.split("id=")[-1].split("&")[0]

        published_date = self._extract_date(cells[1].get_text(strip=True))
        buyer = cells[2].get_text(strip=True) or None
        cpv_codes = cells[3].get_text(strip=True) or None
        deadline = self._extract_date(cells[4].get_text(strip=True))

        return {
            "source": "eavrop",
            "source_id": f"EA-{source_id}",
            "title": title,
            "buyer": buyer,
            "geography": None,
            "cpv_codes": cpv_codes,
            "procedure_type": None,
            "published_date": published_date,
            "deadline": deadline,
            "estimated_value": None,
            "currency": "SEK",
            "status": "published",
            "url": url,
            "description": None,
        }

    @staticmethod
    def _extract_date(text: str | None) -> str | None:
        """Extract a YYYY-MM-DD date from cell text, stripping trailing labels."""
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

        # Include other ASP.NET hidden fields if present
        for field_name in ("__VIEWSTATEGENERATOR", "__EVENTVALIDATION", "__VIEWSTATEENCRYPTED"):
            field = soup.find("input", {"name": field_name})
            if field:
                data[field_name] = field.get("value", "")

        return data
