"""Tests for KommersAnnons scraper _parse_listing — offline."""

from pathlib import Path

from scrapers.kommers import KommersScraper
from models import TenderRecord

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestKommersParse:
    def setup_method(self):
        self.scraper = KommersScraper()
        with open(FIXTURES_DIR / "kommers_listing.html") as f:
            self.html = f.read()

    def test_parse_count(self):
        results = self.scraper._parse_listing(self.html)
        assert len(results) == 3

    def test_first_record(self):
        results = self.scraper._parse_listing(self.html)
        r = results[0]
        assert isinstance(r, TenderRecord)
        assert r.source == "kommers"
        assert r.source_id == "KOM-12345"
        assert "Ledarskapsutbildning" in r.title
        assert r.published_date == "2026-02-10"
        assert "80532000" in r.cpv_codes

    def test_title_ref_stripped(self):
        results = self.scraper._parse_listing(self.html)
        # "REF-001 - Ledarskapsutbildning..." should strip the REF prefix
        assert not results[0].title.startswith("REF-001")

    def test_geography_parsed(self):
        results = self.scraper._parse_listing(self.html)
        assert results[0].geography == "SE224"

    def test_deadline_approximate(self):
        results = self.scraper._parse_listing(self.html)
        # First record has 14 days left
        assert results[0].deadline is not None

    def test_description_present(self):
        results = self.scraper._parse_listing(self.html)
        assert results[0].description is not None
        assert "ledarskapsutbildning" in results[0].description.lower()


class TestKommersRelevanceFilter:
    def test_relevant_passes(self):
        record = TenderRecord(
            source="kommers", source_id="KOM-1", title="Ledarskapsutbildning",
        )
        assert KommersScraper._is_potentially_relevant(record)

    def test_irrelevant_blocked(self):
        record = TenderRecord(
            source="kommers", source_id="KOM-2", title="Kontorsstolar",
        )
        assert not KommersScraper._is_potentially_relevant(record)

    def test_cpv_makes_relevant(self):
        record = TenderRecord(
            source="kommers", source_id="KOM-3", title="Tjanster",
            cpv_codes="80500000",
        )
        assert KommersScraper._is_potentially_relevant(record)
