"""Mercell scraper — unavailable.

Mercell is a JavaScript SPA that requires authentication.
TED already covers the EU procurements that Mercell aggregates,
so this source is skipped until a public API becomes available.
"""

from __future__ import annotations

from .base import BaseScraper


class MercellScraper(BaseScraper):
    name = "mercell"

    def fetch(self) -> list[dict]:
        print(
            "[Mercell] Kräver inloggning — ej tillgänglig. "
            "Använd TED för EU-upphandlingar."
        )
        return []
