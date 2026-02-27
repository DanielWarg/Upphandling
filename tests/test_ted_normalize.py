"""Tests for TED scraper _normalize — offline, no network calls."""

import json
from pathlib import Path

from scrapers.ted import TedScraper


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_notices() -> list[dict]:
    with open(FIXTURES_DIR / "ted_notices.json") as f:
        return json.load(f)


class TestTedNormalize:
    def setup_method(self):
        self.scraper = TedScraper()
        self.notices = _load_notices()

    def test_basic_normalization(self):
        record = self.scraper._normalize(self.notices[0])
        assert record is not None
        assert record.source == "ted"
        assert record.source_id == "2026/S 001-000001"
        assert "Ledarskapsutveckling" in record.title
        assert record.buyer == "Region Stockholm"
        assert record.published_date == "2026-01-15"
        assert record.deadline == "2026-03-01"
        assert record.estimated_value == 5000000.0
        assert record.currency == "SEK"

    def test_cpv_as_comma_string(self):
        record = self.scraper._normalize(self.notices[0])
        assert record is not None
        assert "80532000" in record.cpv_codes
        assert "79633000" in record.cpv_codes

    def test_english_fallback(self):
        record = self.scraper._normalize(self.notices[2])
        assert record is not None
        assert "Coaching" in record.title or "coaching" in record.title

    def test_description_from_lot(self):
        """Notice 3 has description-proc=null, should fall back to description-lot."""
        record = self.scraper._normalize(self.notices[2])
        assert record is not None
        assert record.description is not None
        assert "coaching" in record.description.lower()

    def test_nested_value(self):
        """Notice 3 has estimated-value-proc as dict with 'value' key."""
        record = self.scraper._normalize(self.notices[2])
        assert record is not None
        assert record.estimated_value == 2000000.0

    def test_url_generation(self):
        record = self.scraper._normalize(self.notices[0])
        assert record is not None
        assert "ted.europa.eu" in record.url

    def test_missing_pub_number_returns_none(self):
        notice = {"notice-title": "Test"}
        record = self.scraper._normalize(notice)
        assert record is None

    def test_returns_tender_record(self):
        from models import TenderRecord
        record = self.scraper._normalize(self.notices[0])
        assert isinstance(record, TenderRecord)


class TestExtractText:
    def test_string(self):
        assert TedScraper._extract_text("hello") == "hello"

    def test_dict_swe(self):
        assert TedScraper._extract_text({"swe": "Swedish text"}) == "Swedish text"

    def test_dict_eng_fallback(self):
        assert TedScraper._extract_text({"eng": "English text"}) == "English text"

    def test_list_of_dicts(self):
        result = TedScraper._extract_text([{"swe": "First"}])
        assert result == "First"

    def test_none_returns_default(self):
        assert TedScraper._extract_text(None, "default") == "default"

    def test_list_of_strings(self):
        result = TedScraper._extract_text(["text"])
        assert result == "text"
