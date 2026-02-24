"""e-Avrop scraper using Scrapling StealthyFetcher.

Scrapes the e-Avrop public procurement search.
"""

from __future__ import annotations

from .base import BaseScraper

SEARCH_URL = "https://www.e-avrop.com/index.aspx"


class EAvropScraper(BaseScraper):
    name = "eavrop"

    def fetch(self) -> list[dict]:
        results = []
        try:
            from scrapling import StealthyFetcher

            fetcher = StealthyFetcher()
            page = fetcher.fetch(SEARCH_URL)

            # e-Avrop lists procurements in a table/list format
            items = (
                page.css(".procurement-list-item")
                or page.css("table.procurements tr")
                or page.css(".search-result")
                or page.css("table tr")
            )

            for item in items[1:] if items else []:
                try:
                    proc = self._parse_item(item)
                    if proc:
                        results.append(proc)
                except Exception as e:
                    print(f"[e-Avrop] Error parsing item: {e}")
                    continue

        except ImportError:
            print("[e-Avrop] scrapling not installed — skipping")
        except Exception as e:
            print(f"[e-Avrop] Fetch error: {e}")

        print(f"[e-Avrop] Fetched {len(results)} notices")
        return results

    def _parse_item(self, item) -> dict | None:
        link = item.css_first("a[href]")
        title = link.text.strip() if link and link.text else None

        if not title:
            cells = item.css("td")
            if cells:
                title = cells[0].text.strip() if cells[0].text else None
        if not title:
            return None

        href = link.attrib.get("href", "") if link else ""
        url = href if href.startswith("http") else f"https://www.e-avrop.com/{href.lstrip('/')}"

        source_id = href.split("=")[-1] if "=" in href else title[:50]

        cells = item.css("td")
        buyer = cells[1].text.strip() if len(cells) > 1 and cells[1].text else None
        deadline = cells[2].text.strip() if len(cells) > 2 and cells[2].text else None

        return {
            "source": "eavrop",
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
