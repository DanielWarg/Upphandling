"""KommersAnnons scraper using httpx + BeautifulSoup.

Scrapes the public tender notice list at kommersannons.se/Notices/TenderNotices.
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
MAX_PAGES = 3  # ~40 notices per page → ~120 max

# Sökfilter — HAST Utveckling: ledarskap, utbildning, organisationsutveckling
SEARCH_FILTERS = {
    "SearchString": "utbildning ledarskap coaching organisationsutveckling",
    "SelectedContractType": "",  # Alla typer
}

# Klientsidigt relevansfilter — nyckelord som indikerar potentiell relevans för HAST
RELEVANCE_KEYWORDS = [
    "utbildning", "ledarskap", "ledarskapsutveckling", "chefsutveckling",
    "chefsutbildning", "kompetensutveckling", "organisationsutveckling",
    "teamutveckling", "coaching", "coachning", "mentorskap", "handledning",
    "konflikthantering", "stresshantering", "arbetsmiljö", "förändringsledning",
    "seminarium", "workshop", "föreläsning", "teambuilding",
    "personalutveckling", "medarbetarutveckling", "hr-tjänster",
    "kompetensförsörjning", "ledarskapsprogram", "chefsprogram",
    "managementkonsult", "organisationskonsult", "feedbackkultur",
    "80000000", "80500000", "80530000", "80570000",  # CPV utbildning
    "79414000", "79411000",  # CPV HR/management-konsult
]


class KommersScraper(BaseScraper):
    name = "kommers"

    def fetch(self) -> list[TenderRecord]:
        results: list[TenderRecord] = []
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                # Försök med sökfilter först
                def _get_filtered():
                    r = client.get(LIST_URL, params={"SearchString": SEARCH_FILTERS["SearchString"]})
                    r.raise_for_status()
                    return r
                resp = with_backoff(_get_filtered)
                filtered = self._parse_listing(resp.text)

                if filtered:
                    results.extend(filtered)
                else:
                    # Fallback till ofiltrerad scraping om filtret inte ger resultat
                    print("[Kommers] Sökfiltret gav inga resultat, faller tillbaka till ofiltrerad scraping")
                    def _get_unfiltered():
                        r = client.get(LIST_URL)
                        r.raise_for_status()
                        return r
                    resp = with_backoff(_get_unfiltered)
                    results.extend(self._parse_listing(resp.text))

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
                    page_results = self._parse_listing(resp.text)
                    if not page_results:
                        break
                    results.extend(page_results)

        except Exception as e:
            print(f"[Kommers] Fetch error: {e}")

        # Klientsidigt relevansfilter — ta bort uppenbart irrelevanta
        filtered = [r for r in results if self._is_potentially_relevant(r)]
        print(f"[Kommers] Fetched {len(results)} notices, {len(filtered)} potentiellt relevanta efter filtrering")
        return filtered

    @staticmethod
    def _is_potentially_relevant(proc: TenderRecord) -> bool:
        """Check if a procurement is potentially relevant based on keywords."""
        text = f"{proc.title or ''} {proc.description or ''} {proc.cpv_codes or ''}".lower()
        return any(kw in text for kw in RELEVANCE_KEYWORDS)

    def _parse_listing(self, html: str) -> list[TenderRecord]:
        """Parse all notice rows from a listing page."""
        soup = BeautifulSoup(html, "html.parser")
        notices: list[TenderRecord] = []

        for row in soup.select("div.row.mt-4.mb-4"):
            try:
                proc = self._parse_notice_row(row)
                if proc:
                    notices.append(proc)
            except Exception as e:
                print(f"[Kommers] Error parsing row: {e}")
                continue
        return notices

    def _parse_notice_row(self, row) -> TenderRecord | None:
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
                buyer=None,  # Not on listing page
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
