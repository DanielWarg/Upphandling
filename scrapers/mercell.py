"""Mercell scraper using Scrapling StealthyFetcher.

Scrapes the Mercell announcement search filtered for Sweden.
"""

from __future__ import annotations

from .base import BaseScraper

SEARCH_URL = "https://app.mercell.com/search?filter=delivery_place_code:SE"


class MercellScraper(BaseScraper):
    name = "mercell"

    def fetch(self) -> list[dict]:
        results = []
        try:
            from scrapling import StealthyFetcher

            fetcher = StealthyFetcher()
            page = fetcher.fetch(SEARCH_URL)

            # Mercell renders search results as cards/rows
            # Try common selectors for result items
            items = (
                page.css(".search-result-item")
                or page.css(".notice-list-item")
                or page.css("table.search-results tbody tr")
                or page.css("[data-testid='search-result']")
                or page.css(".result-item")
            )

            for item in items:
                try:
                    proc = self._parse_item(item)
                    if proc:
                        results.append(proc)
                except Exception as e:
                    print(f"[Mercell] Error parsing item: {e}")
                    continue

        except ImportError:
            print("[Mercell] scrapling not installed — skipping")
        except Exception as e:
            print(f"[Mercell] Fetch error: {e}")

        print(f"[Mercell] Fetched {len(results)} notices")
        return results

    def _parse_item(self, item) -> dict | None:
        # Try to extract link and title
        link_el = item.css_first("a[href]")
        if not link_el:
            return None

        title = link_el.text.strip() if link_el.text else None
        href = link_el.attrib.get("href", "")
        if not title:
            return None

        url = href if href.startswith("http") else f"https://app.mercell.com{href}"

        # Try to extract source_id from URL
        source_id = href.split("/")[-1] if "/" in href else href

        # Try buyer, deadline, etc. from surrounding elements
        buyer = self._extract_field(item, [".buyer", ".organization", ".contracting-authority"])
        deadline = self._extract_field(item, [".deadline", ".tender-deadline", "time"])
        geography = self._extract_field(item, [".location", ".region", ".place"])

        return {
            "source": "mercell",
            "source_id": source_id or title[:50],
            "title": title,
            "buyer": buyer,
            "geography": geography,
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

    @staticmethod
    def _extract_field(item, selectors: list[str]) -> str | None:
        for sel in selectors:
            el = item.css_first(sel)
            if el and el.text:
                return el.text.strip()
        return None
