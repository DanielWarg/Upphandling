"""KommersAnnons scraper using Scrapling Fetcher.

Scrapes the public notice list at kommersannons.se.
"""

from __future__ import annotations

from .base import BaseScraper

SEARCH_URL = "https://www.kommersannons.se/elite/notice/noticelist.aspx"


class KommersScraper(BaseScraper):
    name = "kommers"

    def fetch(self) -> list[dict]:
        results = []
        try:
            from scrapling import Fetcher

            fetcher = Fetcher()
            page = fetcher.fetch(SEARCH_URL)

            # KommersAnnons uses a table-based layout
            rows = (
                page.css("table.notice-list tr")
                or page.css("#ctl00_ContentPlaceHolder1_resultGrid tr")
                or page.css("table tr")
            )

            # Skip header row
            for row in rows[1:] if rows else []:
                try:
                    proc = self._parse_row(row)
                    if proc:
                        results.append(proc)
                except Exception as e:
                    print(f"[Kommers] Error parsing row: {e}")
                    continue

        except ImportError:
            print("[Kommers] scrapling not installed — skipping")
        except Exception as e:
            print(f"[Kommers] Fetch error: {e}")

        print(f"[Kommers] Fetched {len(results)} notices")
        return results

    def _parse_row(self, row) -> dict | None:
        cells = row.css("td")
        if len(cells) < 2:
            return None

        # Try to find a link in the row
        link = row.css_first("a[href]")
        title = link.text.strip() if link and link.text else None
        if not title and cells:
            title = cells[0].text.strip() if cells[0].text else None
        if not title:
            return None

        href = link.attrib.get("href", "") if link else ""
        url = href if href.startswith("http") else f"https://www.kommersannons.se{href}"

        source_id = href.split("id=")[-1] if "id=" in href else title[:50]

        # Extract fields from table cells (layout varies)
        buyer = cells[1].text.strip() if len(cells) > 1 and cells[1].text else None
        deadline = cells[2].text.strip() if len(cells) > 2 and cells[2].text else None

        return {
            "source": "kommers",
            "source_id": source_id,
            "title": title,
            "buyer": buyer,
            "geography": None,
            "cpv_codes": None,
            "procedure_type": None,
            "published_date": None,
            "deadline": deadline,
            "estimated_value": None,
            "currency": "SEK",
            "status": "published",
            "url": url,
            "description": None,
        }
