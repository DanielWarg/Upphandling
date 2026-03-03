"""Tests for Mercell scraper parse_search_html — offline."""

import re
from pathlib import Path
from unittest.mock import patch

from scrapers.mercell import (
    MercellScraper,
    parse_search_html,
    _extract_source_id,
    _parse_date_text,
    _parse_deadline_text,
)
from models import TenderRecord

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestParseSearchHtml:
    def setup_method(self):
        with open(FIXTURES_DIR / "mercell_search.html") as f:
            self.html = f.read()
        self.results = parse_search_html(self.html)

    def test_parse_count(self):
        assert len(self.results) >= 1

    def test_source_is_mercell(self):
        for r in self.results:
            assert r.source == "mercell"

    def test_source_id_format(self):
        for r in self.results:
            assert r.source_id.startswith("MERC-")

    def test_title_extracted(self):
        for r in self.results:
            assert isinstance(r.title, str)
            assert len(r.title) > 0

    def test_deadline_format(self):
        """Deadlines should be YYYY-MM-DD."""
        for r in self.results:
            if r.deadline:
                assert re.match(r"\d{4}-\d{2}-\d{2}$", r.deadline), f"Bad deadline: {r.deadline}"

    def test_publication_date_format(self):
        """Published dates should be YYYY-MM-DD."""
        for r in self.results:
            if r.published_date:
                assert re.match(r"\d{4}-\d{2}-\d{2}$", r.published_date), (
                    f"Bad pub date: {r.published_date}"
                )

    def test_geography_extracted(self):
        geo_found = [r for r in self.results if r.geography]
        assert len(geo_found) > 0

    def test_url_built(self):
        for r in self.results:
            if r.url:
                assert "mercell.com/tender/" in r.url

    def test_all_records_are_tenderrecord(self):
        for r in self.results:
            assert isinstance(r, TenderRecord)

    def test_twenty_results_from_fixture(self):
        """The fixture has exactly 20 cards (one page of results)."""
        assert len(self.results) == 20


class TestExtractSourceId:
    def test_positive_id(self):
        assert _extract_source_id("/tender/1000497131?filter=foo") == "MERC-1000497131"

    def test_negative_id(self):
        assert _extract_source_id("/tender/-2026344967?filter=bar") == "MERC--2026344967"

    def test_no_match(self):
        assert _extract_source_id("/search?q=test") is None

    def test_full_url(self):
        assert _extract_source_id("https://app.mercell.com/tender/12345") == "MERC-12345"


class TestParseDateText:
    def test_publicerad_prefix(self):
        assert _parse_date_text("Publicerad 2026-03-03") == "2026-03-03"

    def test_published_prefix(self):
        assert _parse_date_text("Published 2026-03-03") == "2026-03-03"

    def test_plain_date(self):
        assert _parse_date_text("2026-03-03") == "2026-03-03"

    def test_dd_mm_yyyy(self):
        assert _parse_date_text("03/03/2026") == "2026-03-03"

    def test_empty(self):
        assert _parse_date_text("") is None

    def test_none(self):
        assert _parse_date_text(None) is None


class TestParseDeadlineText:
    def test_datetime(self):
        assert _parse_deadline_text("2026-04-02 23:59") == "2026-04-02"

    def test_date_only(self):
        assert _parse_deadline_text("2026-04-02") == "2026-04-02"

    def test_dd_mm_yyyy(self):
        assert _parse_deadline_text("02/04/2026 23:59") == "2026-04-02"

    def test_empty(self):
        assert _parse_deadline_text("") is None


class TestNoPlaywright:
    def test_no_playwright_returns_empty(self):
        with patch("scrapers.mercell.HAS_PLAYWRIGHT", False):
            scraper = MercellScraper()
            result = scraper.fetch()
            assert result == []

    def test_no_playwright_prints_warning(self, capsys):
        with patch("scrapers.mercell.HAS_PLAYWRIGHT", False):
            scraper = MercellScraper()
            scraper.fetch()
            captured = capsys.readouterr()
            assert "playwright saknas" in captured.out
