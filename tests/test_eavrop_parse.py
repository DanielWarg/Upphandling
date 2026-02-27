"""Tests for e-Avrop scraper _parse_listing — offline."""

from pathlib import Path

from scrapers.eavrop import EAvropScraper
from models import TenderRecord

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestEAvropParse:
    def setup_method(self):
        self.scraper = EAvropScraper()
        with open(FIXTURES_DIR / "eavrop_listing.html") as f:
            self.html = f.read()

    def test_parse_count(self):
        results = self.scraper._parse_listing(self.html)
        assert len(results) == 3

    def test_first_record(self):
        results = self.scraper._parse_listing(self.html)
        r = results[0]
        assert isinstance(r, TenderRecord)
        assert r.source == "eavrop"
        assert r.source_id == "EA-5001"
        assert "Kompetensutveckling" in r.title
        assert r.published_date == "2026-02-05"
        assert r.deadline == "2026-03-20"
        assert r.buyer == "Goteborgs kommun"

    def test_cpv_from_column(self):
        results = self.scraper._parse_listing(self.html)
        assert results[0].cpv_codes == "80532000"

    def test_url_built(self):
        results = self.scraper._parse_listing(self.html)
        assert "e-avrop.com" in results[0].url
        assert "id=5001" in results[0].url


class TestEAvropRelevanceFilter:
    def test_relevant_passes(self):
        record = TenderRecord(
            source="eavrop", source_id="EA-1", title="Ledarskapsutbildning",
        )
        assert EAvropScraper._is_potentially_relevant(record)

    def test_irrelevant_blocked(self):
        record = TenderRecord(
            source="eavrop", source_id="EA-2", title="Serverunderhall",
        )
        assert not EAvropScraper._is_potentially_relevant(record)
