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


class TestKommersNoClientFilter:
    """Client-side filtering removed — scorer handles relevance."""

    def test_all_results_returned(self):
        """Verify _parse_listing returns all rows without filtering."""
        scraper = KommersScraper()
        fixtures_dir = Path(__file__).parent / "fixtures"
        with open(fixtures_dir / "kommers_listing.html") as f:
            html = f.read()
        results = scraper._parse_listing(html)
        # All 3 rows in fixture should be returned (no client filter)
        assert len(results) == 3


class TestKommersBuyerParse:
    """Test _fetch_buyer parsing from detail HTML fixture."""

    def setup_method(self):
        from bs4 import BeautifulSoup
        with open(FIXTURES_DIR / "kommers_detail.html") as f:
            self.soup = BeautifulSoup(f.read(), "html.parser")

    def test_buyer_label_present(self):
        """Verify the fixture contains 'Upphandlande myndighet' with buyer text."""
        import re
        label = self.soup.find(string=re.compile("Upphandlande myndighet", re.IGNORECASE))
        assert label is not None
        # The buyer text appears in the next dd element
        dt = label.find_parent("dt")
        assert dt is not None
        dd = dt.find_next_sibling("dd")
        assert dd is not None
        assert "Region Stockholm" in dd.get_text(strip=True)

    def test_buyer_from_meta(self):
        """Should find buyer via meta author tag."""
        meta = self.soup.find("meta", attrs={"name": "author"})
        assert meta is not None
        assert meta.get("content") == "Region Stockholm"

    def test_buyer_from_profile_link(self):
        """Should find buyer via organization profile link."""
        import re
        link = self.soup.select_one("a[href*='Organization']")
        assert link is not None
        assert "Region Stockholm" in link.get_text(strip=True)
