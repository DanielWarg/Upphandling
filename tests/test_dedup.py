"""Tests for deduplication in db.py — uses isolated tmp database."""

from db import upsert_procurement, deduplicate_procurements, get_all_procurements
from models import TenderRecord


class TestDeduplication:
    def test_exact_duplicates_removed(self, tmp_db):
        """Two records with same source+title+buyer should be deduped to one."""
        for i in range(2):
            upsert_procurement({
                "source": "ted",
                "source_id": f"DUP-{i}",
                "title": "Ledarskapsutbildning",
                "buyer": "Region Stockholm",
            })
        removed = deduplicate_procurements()
        assert removed == 1
        remaining = get_all_procurements()
        assert len(remaining) == 1

    def test_different_titles_kept(self, tmp_db):
        upsert_procurement({
            "source": "ted", "source_id": "A1", "title": "Ledarskap",
        })
        upsert_procurement({
            "source": "ted", "source_id": "A2", "title": "Coaching",
        })
        removed = deduplicate_procurements()
        assert removed == 0
        assert len(get_all_procurements()) == 2

    def test_cross_source_not_deduped(self, tmp_db):
        """Same title from different sources should not be deduped."""
        upsert_procurement({
            "source": "ted", "source_id": "X1", "title": "Utbildning",
        })
        upsert_procurement({
            "source": "kommers", "source_id": "KOM-X1", "title": "Utbildning",
        })
        removed = deduplicate_procurements()
        assert removed == 0

    def test_tender_record_upsert(self, tmp_db):
        """TenderRecord objects can be passed to upsert_procurement."""
        record = TenderRecord(
            source="ted", source_id="TR-1", title="Test Record",
            buyer="Test Buyer",
        )
        row_id = upsert_procurement(record)
        assert row_id > 0
        procs = get_all_procurements()
        assert any(p["source_id"] == "TR-1" for p in procs)
