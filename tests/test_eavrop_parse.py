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


class TestEAvropNoClientFilter:
    """Client-side filtering removed — scorer handles relevance."""

    def test_all_results_returned(self):
        """Verify _parse_listing returns all rows without filtering."""
        scraper = EAvropScraper()
        fixtures_dir = Path(__file__).parent / "fixtures"
        with open(fixtures_dir / "eavrop_listing.html") as f:
            html = f.read()
        results = scraper._parse_listing(html)
        # All 3 rows in fixture should be returned (no client filter)
        assert len(results) == 3


class TestEAvropDetailParse:
    """Test _extract_description and _extract_geography from detail HTML."""

    def setup_method(self):
        from bs4 import BeautifulSoup
        with open(FIXTURES_DIR / "eavrop_detail.html") as f:
            self.soup = BeautifulSoup(f.read(), "html.parser")

    def test_extract_description(self):
        desc = EAvropScraper._extract_description(self.soup)
        assert desc is not None
        assert "ledarskapsutbildning" in desc.lower()
        assert len(desc) > 20

    def test_extract_geography(self):
        geo = EAvropScraper._extract_geography(self.soup)
        assert geo is not None
        # Should find "Goteborg, SE232" via label or NUTS regex
        assert "SE232" in geo or "Goteborg" in geo

    def test_description_truncated(self):
        desc = EAvropScraper._extract_description(self.soup)
        assert desc is not None
        assert len(desc) <= 2000


class TestEAvropAuthWall:
    """Test auth wall detection for e-Avrop detail pages."""

    def setup_method(self):
        from bs4 import BeautifulSoup
        with open(FIXTURES_DIR / "eavrop_auth_wall.html") as f:
            self.soup = BeautifulSoup(f.read(), "html.parser")

    def test_auth_wall_detected(self):
        assert EAvropScraper._is_auth_wall(self.soup) is True

    def test_normal_page_not_auth_wall(self):
        from bs4 import BeautifulSoup
        with open(FIXTURES_DIR / "eavrop_detail.html") as f:
            normal_soup = BeautifulSoup(f.read(), "html.parser")
        assert EAvropScraper._is_auth_wall(normal_soup) is False

    def test_fetch_detail_skips_auth_wall(self):
        """_fetch_detail should return (None, None) for auth wall pages."""
        from unittest.mock import MagicMock, patch
        import httpx

        with open(FIXTURES_DIR / "eavrop_auth_wall.html") as f:
            html = f.read()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = html

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_resp

        desc, geo = EAvropScraper._fetch_detail(mock_client, "https://www.e-avrop.com/org/visa/upphandling.aspx?id=99999")
        assert desc is None
        assert geo is None
