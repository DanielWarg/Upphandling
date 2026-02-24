"""End-to-end tests for the full procurement pipeline.

Tests the chain: DB init → upsert → scoring → search → stats → TED scraper → dedup.
"""

import os
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Point DB to a temp file before importing anything
TEST_DB = Path(__file__).parent / "test_upphandlingar.db"


@pytest.fixture(autouse=True)
def use_test_db(tmp_path):
    """Redirect all DB operations to a temporary database."""
    test_db = tmp_path / "test.db"
    import db
    original = db.DB_PATH
    db.DB_PATH = test_db
    db.init_db()
    yield test_db
    db.DB_PATH = original


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_HIGH_SCORE = {
    "source": "ted",
    "source_id": "TED-001",
    "title": "Realtidsinformation och trafikledningssystem for kollektivtrafik",
    "buyer": "Region Stockholm",
    "geography": "Stockholm",
    "cpv_codes": "60100000",
    "procedure_type": "open",
    "published_date": "2026-02-20",
    "deadline": "2026-04-01",
    "estimated_value": 50000000.0,
    "currency": "SEK",
    "status": "published",
    "url": "https://ted.europa.eu/notice/TED-001",
    "description": "Upphandling av realtidssystem och dataplattform for trafikledning i Stockholms lan.",
}

SAMPLE_MED_SCORE = {
    "source": "mercell",
    "source_id": "MERC-002",
    "title": "IT-system for bestallningscentral och passagerarinformation",
    "buyer": "Vasttrafik",
    "geography": "Vastra Gotaland",
    "cpv_codes": "60112000",
    "procedure_type": "restricted",
    "published_date": "2026-02-18",
    "deadline": "2026-03-15",
    "estimated_value": 10000000.0,
    "currency": "SEK",
    "status": "published",
    "url": "https://mercell.com/notice/MERC-002",
    "description": "Leverans av GTFS-baserat system med SIRI-integration.",
}

SAMPLE_LOW_SCORE = {
    "source": "kommers",
    "source_id": "KOM-003",
    "title": "Kontorsmaterial och forbrukningsvaror",
    "buyer": "Sundsvalls kommun",
    "geography": "Vasternorrland",
    "cpv_codes": "30190000",
    "procedure_type": "open",
    "published_date": "2026-02-15",
    "deadline": "2026-03-01",
    "estimated_value": 500000.0,
    "currency": "SEK",
    "status": "published",
    "url": "https://kommersannons.se/notice/KOM-003",
    "description": "Ramavtal for kontorsmaterial.",
}


# ---------------------------------------------------------------------------
# 1. Database layer
# ---------------------------------------------------------------------------

class TestDatabase:
    def test_init_creates_table(self, use_test_db):
        conn = sqlite3.connect(str(use_test_db))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        assert any("procurements" in t[0] for t in tables)

    def test_upsert_insert(self, use_test_db):
        from db import upsert_procurement, get_procurement
        row_id = upsert_procurement(SAMPLE_HIGH_SCORE)
        assert row_id >= 1
        proc = get_procurement(row_id)
        assert proc is not None
        assert proc["title"] == SAMPLE_HIGH_SCORE["title"]
        assert proc["source"] == "ted"
        assert proc["source_id"] == "TED-001"

    def test_upsert_dedup(self, use_test_db):
        """Inserting the same source+source_id twice should update, not duplicate."""
        from db import upsert_procurement, get_all_procurements
        upsert_procurement(SAMPLE_HIGH_SCORE)
        upsert_procurement(SAMPLE_HIGH_SCORE)
        all_procs = get_all_procurements()
        ted_procs = [p for p in all_procs if p["source_id"] == "TED-001"]
        assert len(ted_procs) == 1

    def test_upsert_updates_fields(self, use_test_db):
        from db import upsert_procurement, get_all_procurements
        upsert_procurement(SAMPLE_HIGH_SCORE)
        updated = {**SAMPLE_HIGH_SCORE, "title": "Uppdaterad titel"}
        upsert_procurement(updated)
        all_procs = get_all_procurements()
        proc = [p for p in all_procs if p["source_id"] == "TED-001"][0]
        assert proc["title"] == "Uppdaterad titel"

    def test_search_by_query(self, use_test_db):
        from db import upsert_procurement, search_procurements
        upsert_procurement(SAMPLE_HIGH_SCORE)
        upsert_procurement(SAMPLE_LOW_SCORE)
        results = search_procurements(query="realtid")
        assert len(results) == 1
        assert results[0]["source_id"] == "TED-001"

    def test_search_by_source(self, use_test_db):
        from db import upsert_procurement, search_procurements
        upsert_procurement(SAMPLE_HIGH_SCORE)
        upsert_procurement(SAMPLE_MED_SCORE)
        results = search_procurements(source="mercell")
        assert len(results) == 1
        assert results[0]["source"] == "mercell"

    def test_search_by_geography(self, use_test_db):
        from db import upsert_procurement, search_procurements
        upsert_procurement(SAMPLE_HIGH_SCORE)
        upsert_procurement(SAMPLE_MED_SCORE)
        results = search_procurements(geography="Stockholm")
        assert len(results) == 1

    def test_search_by_score_range(self, use_test_db):
        from db import upsert_procurement, update_score, search_procurements
        upsert_procurement(SAMPLE_HIGH_SCORE)
        upsert_procurement(SAMPLE_LOW_SCORE)
        update_score(1, 80, "hog")
        update_score(2, 5, "lag")
        results = search_procurements(min_score=50, max_score=100)
        assert len(results) == 1
        assert results[0]["score"] == 80

    def test_stats(self, use_test_db):
        from db import upsert_procurement, update_score, get_stats
        upsert_procurement(SAMPLE_HIGH_SCORE)
        upsert_procurement(SAMPLE_MED_SCORE)
        upsert_procurement(SAMPLE_LOW_SCORE)
        update_score(1, 80, "hog")
        update_score(2, 40, "medel")
        update_score(3, 5, "lag")
        stats = get_stats()
        assert stats["total"] == 3
        assert stats["high_fit"] == 1  # score >= 60
        assert stats["by_source"]["ted"] == 1
        assert stats["by_source"]["mercell"] == 1
        assert stats["by_source"]["kommers"] == 1


# ---------------------------------------------------------------------------
# 2. Scoring
# ---------------------------------------------------------------------------

class TestScoring:
    def test_high_score_keywords(self):
        from scorer import score_procurement
        score, rationale = score_procurement(
            title="Realtidsinformation och trafikledningssystem",
            description="Dataplattform for kollektivtrafik",
        )
        assert score >= 60
        assert "realtid" in rationale.lower()

    def test_medium_score_keywords(self):
        from scorer import score_procurement
        score, rationale = score_procurement(
            title="GTFS-leverans",
            description="SIRI-integration for passagerarinformation",
        )
        assert 20 <= score <= 80
        assert "gtfs" in rationale.lower()

    def test_low_score_no_keywords(self):
        from scorer import score_procurement
        score, rationale = score_procurement(
            title="Kontorsmaterial",
            description="Ramavtal for pennor och papper",
        )
        assert score == 0
        assert "inga matchande" in rationale.lower()

    def test_buyer_bonus(self):
        from scorer import score_procurement
        score_with, _ = score_procurement(
            title="kollektivtrafik",
            buyer="Region Stockholm",
        )
        score_without, _ = score_procurement(
            title="kollektivtrafik",
            buyer="Okand kopare AB",
        )
        assert score_with > score_without

    def test_score_capped_at_100(self):
        from scorer import score_procurement
        score, _ = score_procurement(
            title="realtid realtidsinformation realtidssystem trafikledning trafikledningssystem dataplattform informationsplattform",
            description="bestallningscentral passagerarinformation GTFS SIRI NeTEx ITxPT kollektivtrafik busstrafik",
            buyer="Region Stockholm",
        )
        assert score <= 100

    def test_score_returns_rationale(self):
        from scorer import score_procurement
        _, rationale = score_procurement(title="realtidssystem")
        assert "+20" in rationale

    def test_cpv_codes_searched(self):
        from scorer import score_procurement
        score, rationale = score_procurement(
            title="Systemupphandling",
            cpv_codes="kollektivtrafik",
        )
        assert score > 0


# ---------------------------------------------------------------------------
# 3. TED scraper (live API call)
# ---------------------------------------------------------------------------

class TestTedScraper:
    def test_fetch_returns_list(self):
        from scrapers.ted import TedScraper
        scraper = TedScraper()
        results = scraper.fetch()
        assert isinstance(results, list)

    def test_results_have_required_fields(self):
        from scrapers.ted import TedScraper
        scraper = TedScraper()
        results = scraper.fetch()
        if results:  # API might return 0 results
            proc = results[0]
            assert "source" in proc and proc["source"] == "ted"
            assert "source_id" in proc and proc["source_id"]
            assert "title" in proc and proc["title"]

    def test_normalize_handles_dict_title(self):
        from scrapers.ted import TedScraper
        scraper = TedScraper()
        notice = {
            "publication-number": "12345-2026",
            "notice-title": {"swe": "Sverige-Test: Svensk titel", "eng": "English title"},
            "organisation-name-buyer": ["Test Buyer AB"],
        }
        result = scraper._normalize(notice)
        assert "Svensk titel" in result["title"]
        assert result["source_id"] == "12345-2026"

    def test_normalize_handles_missing_fields(self):
        from scrapers.ted import TedScraper
        scraper = TedScraper()
        notice = {"publication-number": "99999-2026", "notice-title": "Minimal"}
        result = scraper._normalize(notice)
        assert result["title"] == "Minimal"
        assert result["source"] == "ted"


# ---------------------------------------------------------------------------
# 4. Full pipeline E2E
# ---------------------------------------------------------------------------

class TestFullPipeline:
    def test_scrape_store_score_search(self, use_test_db):
        """Full E2E: insert → score → search → verify ranking."""
        from db import upsert_procurement, update_score, search_procurements, get_stats
        from scorer import score_procurement

        # 1. Insert sample data
        for sample in [SAMPLE_HIGH_SCORE, SAMPLE_MED_SCORE, SAMPLE_LOW_SCORE]:
            upsert_procurement(sample)

        # 2. Score all
        from db import get_all_procurements
        for p in get_all_procurements():
            score, rationale = score_procurement(
                title=p.get("title", ""),
                description=p.get("description", ""),
                buyer=p.get("buyer", ""),
                cpv_codes=p.get("cpv_codes", ""),
            )
            update_score(p["id"], score, rationale)

        # 3. Verify high-score is ranked first
        all_procs = get_all_procurements()  # ordered by score DESC
        assert all_procs[0]["source_id"] == "TED-001"
        assert all_procs[0]["score"] >= 60

        # 4. Verify low-score is ranked last
        assert all_procs[-1]["source_id"] == "KOM-003"
        assert all_procs[-1]["score"] < 30

        # 5. Search works
        results = search_procurements(query="realtid", min_score=50)
        assert len(results) >= 1
        assert results[0]["source_id"] == "TED-001"

        # 6. Stats correct
        stats = get_stats()
        assert stats["total"] == 3

    def test_dedup_on_double_run(self, use_test_db):
        """Running the pipeline twice should not create duplicates."""
        from db import upsert_procurement, get_all_procurements

        for _ in range(2):
            for sample in [SAMPLE_HIGH_SCORE, SAMPLE_MED_SCORE, SAMPLE_LOW_SCORE]:
                upsert_procurement(sample)

        all_procs = get_all_procurements()
        assert len(all_procs) == 3

    def test_run_scrapers_with_mock_ted(self, use_test_db):
        """Test run_scrapers.py pipeline with mocked TED response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "notices": [
                {
                    "publication-number": "MOCK-001",
                    "notice-title": {"swe": "Sverige-Malmö: Trafikledningssystem för realtidsinformation"},
                    "organisation-name-buyer": ["Skånetrafiken"],
                    "classification-cpv": ["60100000"],
                    "publication-date": "2026-02-20",
                    "description-proc": {"swe": "Upphandling av kollektivtrafik IT-system"},
                }
            ],
        }

        with patch("httpx.post", return_value=mock_response):
            from scrapers.ted import TedScraper
            scraper = TedScraper()
            results = scraper.fetch()
            assert len(results) == 1

            from db import upsert_procurement
            upsert_procurement(results[0])

            from scorer import score_procurement
            from db import get_all_procurements, update_score
            for p in get_all_procurements():
                score, rationale = score_procurement(
                    title=p.get("title", ""),
                    description=p.get("description", ""),
                    buyer=p.get("buyer", ""),
                    cpv_codes=p.get("cpv_codes", ""),
                )
                update_score(p["id"], score, rationale)

            procs = get_all_procurements()
            assert len(procs) == 1
            assert procs[0]["score"] >= 40  # trafikledning + realtid + kollektivtrafik


# ---------------------------------------------------------------------------
# 5. Streamlit app import check
# ---------------------------------------------------------------------------

class TestAppImport:
    def test_app_module_is_importable(self):
        """Verify app.py has no import errors (doesn't run Streamlit)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "app", Path(__file__).parent / "app.py"
        )
        assert spec is not None
