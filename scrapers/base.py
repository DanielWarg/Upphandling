"""Base scraper interface."""

from __future__ import annotations
from abc import ABC, abstractmethod

from models import TenderRecord


class BaseScraper(ABC):
    """Common interface for all procurement scrapers."""

    name: str = "base"

    @abstractmethod
    def fetch(self) -> list[TenderRecord]:
        """Fetch procurements and return a list of TenderRecord objects."""
        ...

    def __repr__(self):
        return f"<{self.__class__.__name__}>"
