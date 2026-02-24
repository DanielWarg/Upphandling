"""Base scraper interface."""

from __future__ import annotations
from abc import ABC, abstractmethod


class BaseScraper(ABC):
    """Common interface for all procurement scrapers."""

    name: str = "base"

    @abstractmethod
    def fetch(self) -> list[dict]:
        """Fetch procurements and return a list of normalized dicts.

        Each dict should have at minimum:
            source, source_id, title
        And optionally:
            buyer, geography, cpv_codes, procedure_type,
            published_date, deadline, estimated_value, currency,
            status, url, description
        """
        ...

    def __repr__(self):
        return f"<{self.__class__.__name__}>"
