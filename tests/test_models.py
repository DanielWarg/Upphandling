"""Tests for models.py — TenderRecord validation, coercion, hash."""

from datetime import date, datetime

import pytest

from models import TenderRecord


def _make_record(**overrides) -> TenderRecord:
    defaults = {
        "source": "ted",
        "source_id": "2026/S-001",
        "title": "Test Procurement",
    }
    defaults.update(overrides)
    return TenderRecord(**defaults)


class TestBasicValidation:
    def test_minimal_record(self):
        r = _make_record()
        assert r.source == "ted"
        assert r.source_id == "2026/S-001"
        assert r.title == "Test Procurement"
        assert r.score == 0

    def test_all_sources(self):
        for src in ("ted", "mercell", "kommers", "eavrop"):
            r = _make_record(source=src)
            assert r.source == src

    def test_invalid_source_rejected(self):
        with pytest.raises(Exception):
            _make_record(source="invalid")

    def test_empty_source_id_rejected(self):
        with pytest.raises(Exception):
            _make_record(source_id="")

    def test_empty_title_rejected(self):
        with pytest.raises(Exception):
            _make_record(title="")

    def test_whitespace_only_title_rejected(self):
        with pytest.raises(Exception):
            _make_record(title="   ")


class TestWhitespaceStripping:
    def test_title_stripped(self):
        r = _make_record(title="  Hello World  ")
        assert r.title == "Hello World"

    def test_buyer_stripped(self):
        r = _make_record(buyer="  Region Stockholm  ")
        assert r.buyer == "Region Stockholm"

    def test_empty_string_becomes_none(self):
        r = _make_record(buyer="   ")
        assert r.buyer is None


class TestDateCoercion:
    def test_date_string_truncated(self):
        r = _make_record(published_date="2026-01-15T10:00:00Z")
        assert r.published_date == "2026-01-15"

    def test_date_object_converted(self):
        r = _make_record(published_date=date(2026, 3, 1))
        assert r.published_date == "2026-03-01"

    def test_datetime_object_converted(self):
        r = _make_record(deadline=datetime(2026, 5, 15, 14, 30))
        assert r.deadline == "2026-05-15"

    def test_none_date_stays_none(self):
        r = _make_record(published_date=None)
        assert r.published_date is None


class TestDescriptionTruncation:
    def test_short_description_unchanged(self):
        r = _make_record(description="Short desc")
        assert r.description == "Short desc"

    def test_long_description_truncated(self):
        long_desc = "x" * 3000
        r = _make_record(description=long_desc)
        assert len(r.description) == 2000

    def test_none_description(self):
        r = _make_record(description=None)
        assert r.description is None


class TestValueCoercion:
    def test_int_value(self):
        r = _make_record(estimated_value=5000000)
        assert r.estimated_value == 5000000.0

    def test_float_value(self):
        r = _make_record(estimated_value=1.5)
        assert r.estimated_value == 1.5

    def test_string_value(self):
        r = _make_record(estimated_value="1 000 000")
        assert r.estimated_value == 1000000.0

    def test_comma_decimal(self):
        r = _make_record(estimated_value="1500,50")
        assert r.estimated_value == 1500.50

    def test_invalid_string_becomes_none(self):
        r = _make_record(estimated_value="not a number")
        assert r.estimated_value is None


class TestHashFingerprint:
    def test_deterministic(self):
        r1 = _make_record(title="Test", buyer="Buyer", deadline="2026-01-01")
        r2 = _make_record(title="Test", buyer="Buyer", deadline="2026-01-01")
        assert r1.hash_fingerprint == r2.hash_fingerprint

    def test_case_insensitive(self):
        r1 = _make_record(title="Test Title", buyer="BUYER")
        r2 = _make_record(title="test title", buyer="buyer")
        assert r1.hash_fingerprint == r2.hash_fingerprint

    def test_different_records_different_hash(self):
        r1 = _make_record(title="Title A")
        r2 = _make_record(title="Title B")
        assert r1.hash_fingerprint != r2.hash_fingerprint

    def test_hash_length(self):
        r = _make_record()
        assert len(r.hash_fingerprint) == 16


class TestToDbDict:
    def test_returns_dict(self):
        r = _make_record(buyer="Test Buyer", estimated_value=100.0)
        d = r.to_db_dict()
        assert isinstance(d, dict)
        assert d["source"] == "ted"
        assert d["source_id"] == "2026/S-001"
        assert d["title"] == "Test Procurement"
        assert d["buyer"] == "Test Buyer"
        assert d["estimated_value"] == 100.0

    def test_no_hash_in_db_dict(self):
        r = _make_record()
        d = r.to_db_dict()
        assert "hash_fingerprint" not in d
