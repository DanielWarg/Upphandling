"""Tests for db.py — CRUD operations, upsert, scoring, pipeline, account linking, analysis."""

import json
import sqlite3

import pytest

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

class TestRecordType:
    def test_upsert_default_record_type(self, tmp_db):
        row_id = db.upsert_procurement(_make_proc())
        proc = db.get_procurement(row_id)
        assert proc["record_type"] == "upphandling"

    def test_upsert_bidrag_record_type(self, tmp_db):
        data = _make_proc(source="vinnova", source_id="VINN-123", record_type="bidrag")
        row_id = db.upsert_procurement(data)
        proc = db.get_procurement(row_id)
        assert proc["record_type"] == "bidrag"

    def test_upsert_tender_record_with_record_type(self, tmp_db):
        tr = _make_tender_record(source="vinnova", source_id="VINN-456", record_type="bidrag")
        row_id = db.upsert_procurement(tr)
        proc = db.get_procurement(row_id)
        assert proc["record_type"] == "bidrag"

    def test_search_by_record_type(self, tmp_db):
        db.upsert_procurement(_make_proc(source_id="A", record_type="upphandling"))
        db.upsert_procurement(_make_proc(source="vinnova", source_id="B", record_type="bidrag"))
        results = db.search_procurements(record_type="bidrag")
        assert len(results) == 1
        assert results[0]["record_type"] == "bidrag"

    def test_search_all_record_types(self, tmp_db):
        db.upsert_procurement(_make_proc(source_id="A", record_type="upphandling"))
        db.upsert_procurement(_make_proc(source="vinnova", source_id="B", record_type="bidrag"))
        results = db.search_procurements(record_type="")
        assert len(results) == 2


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


class TestPurgeExpired:
    def test_purges_expired_deadline(self, tmp_db):
        db.upsert_procurement(_make_proc(source_id="OLD-1", deadline="2020-01-01"))
        db.upsert_procurement(_make_proc(source_id="NEW-1", deadline="2099-12-31"))
        result = db.purge_expired()
        assert result["purged"] == 1
        assert result["had_deadline"] == 1
        assert db.get_procurement(1) is None  # OLD-1 gone
        assert db.get_procurement(2) is not None  # NEW-1 kept

    def test_purges_old_without_deadline(self, tmp_db):
        db.upsert_procurement(_make_proc(source_id="OLD-ND", deadline=None, published_date="2020-01-01"))
        db.upsert_procurement(_make_proc(source_id="NEW-ND", deadline=None, published_date="2099-01-01"))
        result = db.purge_expired()
        assert result["purged"] == 1
        assert result["old_no_deadline"] == 1

    def test_purges_related_data(self, tmp_db):
        pid = db.upsert_procurement(_make_proc(source_id="REL-1", deadline="2020-01-01", score=50))
        db.save_analysis(pid, {"kravsammanfattning": "test"})
        db.ensure_pipeline_entry(pid)
        db.add_procurement_note(pid, "admin", "en anteckning")
        result = db.purge_expired()
        assert result["purged"] == 1
        assert db.get_analysis(pid) is None
        assert db.get_pipeline_item(pid) is None
        assert db.get_procurement_notes(pid) == []

    def test_nothing_to_purge(self, tmp_db):
        db.upsert_procurement(_make_proc(source_id="FRESH", deadline="2099-12-31"))
        result = db.purge_expired()
        assert result["purged"] == 0

    def test_custom_max_age(self, tmp_db):
        db.upsert_procurement(_make_proc(source_id="AGE-1", deadline=None, published_date="2026-02-01"))
        # 30 days ago should be purged with max_age=10
        result = db.purge_expired(max_age_days=10)
        assert result["purged"] == 1


# ===========================================================================
# TestSaveBidragMatch
# ===========================================================================

class TestSaveBidragMatch:
    def _make_bidrag(self, source_id: str = "VINN-BM1") -> int:
        return db.upsert_procurement(_make_proc(
            source="vinnova", source_id=source_id, record_type="bidrag",
        ))

    def test_insert_new_match(self, tmp_db):
        pid = self._make_bidrag()
        cid = db.create_company("TestCo", "", "admin")
        row_id = db.save_bidrag_match(pid, cid, 75.0, "Good match")
        assert row_id > 0
        matches = db.get_company_matches(cid)
        assert len(matches) == 1
        assert matches[0]["match_score"] == 75.0

    def test_update_existing_match(self, tmp_db):
        pid = self._make_bidrag()
        cid = db.create_company("TestCo", "", "admin")
        id1 = db.save_bidrag_match(pid, cid, 50.0, "OK")
        id2 = db.save_bidrag_match(pid, cid, 80.0, "Better")
        assert id1 == id2
        matches = db.get_company_matches(cid)
        assert len(matches) == 1
        assert matches[0]["match_score"] == 80.0

    def test_dismissed_preserved_on_rematch(self, tmp_db):
        pid = self._make_bidrag()
        cid = db.create_company("TestCo", "", "admin")
        row_id = db.save_bidrag_match(pid, cid, 50.0, "OK")
        db.update_match_status(row_id, "dismissed")
        # Re-match should not overwrite dismissed
        db.save_bidrag_match(pid, cid, 90.0, "Great")
        matches = db.get_company_matches(cid)
        assert len(matches) == 1
        assert matches[0]["match_score"] == 50.0  # unchanged
        assert matches[0]["status"] == "dismissed"

    def test_returns_correct_row_id(self, tmp_db):
        pid = self._make_bidrag()
        cid = db.create_company("TestCo", "", "admin")
        row_id = db.save_bidrag_match(pid, cid, 60.0, "Fine")
        match = db.get_company_matches(cid)[0]
        assert match["id"] == row_id


# ===========================================================================
# TestGetBidragSources
# ===========================================================================

class TestGetBidragSources:
    def test_returns_unique_sources(self, tmp_db):
        db.upsert_procurement(_make_proc(source="vinnova", source_id="V1", record_type="bidrag"))
        db.upsert_procurement(_make_proc(source="tillvaxtverket", source_id="TV1", record_type="bidrag"))
        db.upsert_procurement(_make_proc(source="vinnova", source_id="V2", record_type="bidrag"))
        sources = db.get_bidrag_sources()
        assert sorted(sources) == ["tillvaxtverket", "vinnova"]

    def test_empty_without_bidrag(self, tmp_db):
        db.upsert_procurement(_make_proc(source="ted", source_id="T1"))
        sources = db.get_bidrag_sources()
        assert sources == []


# ===========================================================================
# TestEnsurePipelineEntryBidrag
# ===========================================================================

class TestEnsurePipelineEntryBidrag:
    def test_default_stage_upphandling(self, tmp_db):
        pid = db.upsert_procurement(_make_proc())
        db.ensure_pipeline_entry(pid)
        item = db.get_pipeline_item(pid)
        assert item["stage"] == "bevakad"

    def test_default_stage_bidrag(self, tmp_db):
        pid = db.upsert_procurement(_make_proc(
            source="vinnova", source_id="VINN-PIPE", record_type="bidrag",
        ))
        db.ensure_pipeline_entry(pid)
        item = db.get_pipeline_item(pid)
        assert item["stage"] == "hittad"

    def test_explicit_stage_overrides(self, tmp_db):
        pid = db.upsert_procurement(_make_proc(
            source="vinnova", source_id="VINN-OVR", record_type="bidrag",
        ))
        db.ensure_pipeline_entry(pid, stage="matchad")
        item = db.get_pipeline_item(pid)
        assert item["stage"] == "matchad"

    def test_idempotent(self, tmp_db):
        pid = db.upsert_procurement(_make_proc())
        id1 = db.ensure_pipeline_entry(pid)
        id2 = db.ensure_pipeline_entry(pid)
        assert id1 == id2


# ===========================================================================
# TestCompanyCrud
# ===========================================================================

class TestCompanyCrud:
    def test_create_company(self, tmp_db):
        cid = db.create_company("HAST AB", "https://hast.se", "admin")
        assert cid > 0
        company = db.get_company(cid)
        assert company["name"] == "HAST AB"
        assert company["website_url"] == "https://hast.se"

    def test_get_all_companies(self, tmp_db):
        db.create_company("Alpha", "", "admin")
        db.create_company("Beta", "", "admin")
        companies = db.get_all_companies()
        assert len(companies) == 2
        names = [c["name"] for c in companies]
        assert "Alpha" in names
        assert "Beta" in names

    def test_update_company(self, tmp_db):
        cid = db.create_company("TestCo", "", "admin")
        db.update_company(cid, industry="Konsult", website_url="https://test.se")
        company = db.get_company(cid)
        assert company["industry"] == "Konsult"
        assert company["website_url"] == "https://test.se"

    def test_delete_company(self, tmp_db):
        cid = db.create_company("DeleteMe", "", "admin")
        db.delete_company(cid)
        assert db.get_company(cid) is None

    def test_duplicate_name_raises(self, tmp_db):
        db.create_company("Unique", "", "admin")
        with pytest.raises(sqlite3.IntegrityError):
            db.create_company("Unique", "", "admin")
