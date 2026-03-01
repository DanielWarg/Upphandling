"""Tests for db.py — CRUD operations, upsert, scoring, pipeline, account linking, analysis."""

import json

import db
from models import TenderRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proc(source_id: str = "TEST-1", title: str = "Test procurement",
               buyer: str = "Test Buyer AB", **kwargs) -> dict:
    """Create a minimal procurement dict for testing."""
    base = {
        "source": "ted",
        "source_id": source_id,
        "title": title,
        "buyer": buyer,
        "geography": "SE110",
        "cpv_codes": "80530000",
        "procedure_type": "open",
        "published_date": "2026-01-15",
        "deadline": "2026-04-01",
        "estimated_value": 500000,
        "currency": "SEK",
        "status": "published",
        "url": "https://example.com/1",
        "description": "En testupphandling for ledarskapsutbildning.",
        "score": 0,
        "score_rationale": None,
    }
    base.update(kwargs)
    return base


def _make_tender_record(**kwargs) -> TenderRecord:
    """Create a TenderRecord for testing."""
    defaults = {
        "source": "kommers",
        "source_id": "KOM-999",
        "title": "Ledarskapsutbildning for chefer",
        "buyer": "Region Stockholm",
        "geography": "SE110",
        "cpv_codes": "80530000",
        "published_date": "2026-01-20",
        "deadline": "2026-05-01",
    }
    defaults.update(kwargs)
    return TenderRecord(**defaults)


# ===========================================================================
# TestUpsertProcurement
# ===========================================================================

class TestUpsertProcurement:
    def test_insert_dict(self, tmp_db):
        row_id = db.upsert_procurement(_make_proc())
        assert row_id > 0
        proc = db.get_procurement(row_id)
        assert proc is not None
        assert proc["title"] == "Test procurement"

    def test_insert_tender_record(self, tmp_db):
        tr = _make_tender_record()
        row_id = db.upsert_procurement(tr)
        assert row_id > 0
        proc = db.get_procurement(row_id)
        assert proc["source"] == "kommers"
        assert proc["buyer"] == "Region Stockholm"

    def test_upsert_updates_existing(self, tmp_db):
        data = _make_proc()
        id1 = db.upsert_procurement(data)
        data["title"] = "Updated title"
        id2 = db.upsert_procurement(data)
        assert id1 == id2
        proc = db.get_procurement(id1)
        assert proc["title"] == "Updated title"

    def test_upsert_unique_constraint(self, tmp_db):
        db.upsert_procurement(_make_proc(source_id="A"))
        db.upsert_procurement(_make_proc(source_id="B"))
        all_procs = db.get_all_procurements()
        assert len(all_procs) == 2

    def test_upsert_preserves_fields(self, tmp_db):
        data = _make_proc(estimated_value=1000000, currency="EUR")
        row_id = db.upsert_procurement(data)
        proc = db.get_procurement(row_id)
        assert proc["estimated_value"] == 1000000
        assert proc["currency"] == "EUR"


# ===========================================================================
# TestGetProcurements
# ===========================================================================

class TestGetProcurements:
    def test_get_all_empty(self, tmp_db):
        assert db.get_all_procurements() == []

    def test_get_all_returns_dicts(self, tmp_db):
        db.upsert_procurement(_make_proc())
        results = db.get_all_procurements()
        assert len(results) == 1
        assert isinstance(results[0], dict)

    def test_get_procurement_missing(self, tmp_db):
        assert db.get_procurement(9999) is None

    def test_get_procurement_found(self, tmp_db):
        row_id = db.upsert_procurement(_make_proc())
        proc = db.get_procurement(row_id)
        assert proc is not None
        assert proc["id"] == row_id

    def test_search_by_query(self, tmp_db):
        db.upsert_procurement(_make_proc(source_id="A", title="Ledarskapsutbildning", description=""))
        db.upsert_procurement(_make_proc(source_id="B", title="Skolskjuts", description="Transport av elever"))
        results = db.search_procurements(query="Ledarskap")
        assert len(results) == 1
        assert "Ledarskap" in results[0]["title"]

    def test_search_by_source(self, tmp_db):
        db.upsert_procurement(_make_proc(source_id="A", source="ted"))
        db.upsert_procurement(_make_proc(source_id="B", source="kommers"))
        results = db.search_procurements(source="ted")
        assert len(results) == 1
        assert results[0]["source"] == "ted"

    def test_search_by_score_range(self, tmp_db):
        id1 = db.upsert_procurement(_make_proc(source_id="A"))
        id2 = db.upsert_procurement(_make_proc(source_id="B"))
        db.update_score(id1, 80, "high", None)
        db.update_score(id2, 20, "low", None)
        results = db.search_procurements(min_score=50)
        assert len(results) == 1
        assert results[0]["score"] == 80

    def test_search_by_ai_relevance(self, tmp_db):
        id1 = db.upsert_procurement(_make_proc(source_id="A"))
        id2 = db.upsert_procurement(_make_proc(source_id="B"))
        db.update_ai_relevance(id1, "relevant", "match")
        db.update_ai_relevance(id2, "irrelevant", "no match")
        results = db.search_procurements(ai_relevance="relevant")
        assert len(results) == 1


# ===========================================================================
# TestScoreUpdate
# ===========================================================================

class TestScoreUpdate:
    def test_update_score(self, tmp_db):
        row_id = db.upsert_procurement(_make_proc())
        db.update_score(row_id, 75, "Relevant for HAST")
        proc = db.get_procurement(row_id)
        assert proc["score"] == 75
        assert proc["score_rationale"] == "Relevant for HAST"

    def test_update_score_with_breakdown(self, tmp_db):
        row_id = db.upsert_procurement(_make_proc())
        breakdown = {"sector_gate": True, "keyword_score": 50, "buyer_bonus": 10}
        db.update_score(row_id, 60, "Good match", breakdown)
        proc = db.get_procurement(row_id)
        assert proc["score_breakdown"] is not None
        parsed = json.loads(proc["score_breakdown"])
        assert parsed["keyword_score"] == 50

    def test_update_ai_relevance(self, tmp_db):
        row_id = db.upsert_procurement(_make_proc())
        db.update_ai_relevance(row_id, "relevant", "Matches HAST services")
        proc = db.get_procurement(row_id)
        assert proc["ai_relevance"] == "relevant"
        assert proc["ai_relevance_reasoning"] == "Matches HAST services"


# ===========================================================================
# TestPipeline
# ===========================================================================

class TestPipeline:
    def test_ensure_pipeline_entry_creates(self, tmp_db):
        row_id = db.upsert_procurement(_make_proc())
        pipe_id = db.ensure_pipeline_entry(row_id)
        assert pipe_id > 0
        item = db.get_pipeline_item(row_id)
        assert item is not None
        assert item["stage"] == "bevakad"

    def test_ensure_pipeline_entry_idempotent(self, tmp_db):
        row_id = db.upsert_procurement(_make_proc())
        id1 = db.ensure_pipeline_entry(row_id)
        id2 = db.ensure_pipeline_entry(row_id)
        assert id1 == id2

    def test_update_pipeline_stage(self, tmp_db):
        row_id = db.upsert_procurement(_make_proc())
        db.ensure_pipeline_entry(row_id)
        db.update_pipeline_stage(row_id, "kvalificerad", "anna_lindberg")
        item = db.get_pipeline_item(row_id)
        assert item["stage"] == "kvalificerad"
        assert item["updated_by"] == "anna_lindberg"

    def test_pipeline_summary(self, tmp_db):
        id1 = db.upsert_procurement(_make_proc(source_id="A"))
        id2 = db.upsert_procurement(_make_proc(source_id="B"))
        db.ensure_pipeline_entry(id1, stage="bevakad")
        db.ensure_pipeline_entry(id2, stage="kvalificerad")
        summary = db.get_pipeline_summary()
        assert summary["bevakad"]["count"] >= 1
        assert summary["kvalificerad"]["count"] >= 1


# ===========================================================================
# TestAccountLinking
# ===========================================================================

class TestAccountLinking:
    def test_seed_accounts(self, tmp_db):
        db.seed_accounts()
        accounts = db.get_all_accounts()
        assert len(accounts) == len(db.SEED_ACCOUNTS)

    def test_create_account(self, tmp_db):
        acc_id = db.create_account("Test AB", buyer_aliases="test,testing", region="Stockholm")
        assert acc_id > 0
        acc = db.get_account(acc_id)
        assert acc["name"] == "Test AB"

    def test_auto_link_matches(self, tmp_db):
        db.create_account("Region Stockholm", buyer_aliases="region stockholm", region="Stockholm")
        db.upsert_procurement(_make_proc(buyer="Region Stockholm"))
        linked = db.auto_link_procurements_to_accounts()
        assert linked >= 1

    def test_auto_link_no_match(self, tmp_db):
        db.create_account("Region Stockholm", buyer_aliases="region stockholm", region="Stockholm")
        db.upsert_procurement(_make_proc(buyer="Totally Different Org"))
        linked = db.auto_link_procurements_to_accounts()
        assert linked == 0

    def test_auto_link_alias_match(self, tmp_db):
        db.create_account("Västtrafik", buyer_aliases="vasttrafik,västtrafik", region="VG")
        db.upsert_procurement(_make_proc(buyer="Västtrafik AB"))
        linked = db.auto_link_procurements_to_accounts()
        assert linked >= 1


# ===========================================================================
# TestAnalysisCRUD
# ===========================================================================

class TestAnalysisCRUD:
    def test_save_and_get_analysis(self, tmp_db):
        row_id = db.upsert_procurement(_make_proc())
        analysis = {
            "procurement_id": row_id,
            "full_notice_text": "Full text here",
            "kravsammanfattning": "Krav...",
            "matchningsanalys": "Match...",
            "prisstrategi": "Pris...",
            "anbudshjalp": "Anbud...",
            "model": "test-model",
            "input_tokens": 100,
            "output_tokens": 200,
        }
        db.save_analysis(row_id, analysis)
        result = db.get_analysis(row_id)
        assert result is not None
        assert result["kravsammanfattning"] == "Krav..."

    def test_get_analysis_missing(self, tmp_db):
        assert db.get_analysis(9999) is None

    def test_save_analysis_upsert(self, tmp_db):
        row_id = db.upsert_procurement(_make_proc())
        analysis1 = {
            "kravsammanfattning": "Version 1",
            "matchningsanalys": "M1",
            "prisstrategi": "P1",
            "anbudshjalp": "A1",
            "model": "m1",
        }
        db.save_analysis(row_id, analysis1)
        analysis2 = {
            "kravsammanfattning": "Version 2",
            "matchningsanalys": "M2",
            "prisstrategi": "P2",
            "anbudshjalp": "A2",
            "model": "m2",
        }
        db.save_analysis(row_id, analysis2)
        result = db.get_analysis(row_id)
        assert result["kravsammanfattning"] == "Version 2"


# ===========================================================================
# TestMissingData
# ===========================================================================

class TestMissingData:
    def test_get_missing_buyer(self, tmp_db):
        db.upsert_procurement(_make_proc(source_id="A", buyer=None))
        db.upsert_procurement(_make_proc(source_id="B", buyer="Has Buyer"))
        missing = db.get_procurements_missing_data()
        # get_procurements_missing_data only selects id, source, url, title, buyer, description, geography
        assert any(m["title"] == "Test procurement" and m["buyer"] is None for m in missing)

    def test_get_missing_by_source(self, tmp_db):
        db.upsert_procurement(_make_proc(source_id="A", source="kommers", buyer=None))
        db.upsert_procurement(_make_proc(source_id="B", source="ted", buyer=None))
        missing = db.get_procurements_missing_data(source="kommers")
        assert all(m["source"] == "kommers" for m in missing)

    def test_update_procurement_fields(self, tmp_db):
        row_id = db.upsert_procurement(_make_proc(buyer=None, description=None))
        db.update_procurement_fields(row_id, buyer="New Buyer", description="New desc")
        proc = db.get_procurement(row_id)
        assert proc["buyer"] == "New Buyer"
        assert proc["description"] == "New desc"
