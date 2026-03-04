"""Tests for scrapers/tillvaxtverket.py — offline parsing of Tillväxtverket RSS feed."""

from pathlib import Path

from scrapers.tillvaxtverket import _parse_rss

FIXTURE = Path(__file__).parent / "fixtures" / "tillvaxtverket_utlysningar.rss"


def _load_fixture() -> bytes:
    return FIXTURE.read_bytes()


class TestTillvaxtverketParse:
    def test_parse_returns_records(self):
        records = _parse_rss(_load_fixture())
        assert len(records) == 3

    def test_record_type_is_bidrag(self):
        records = _parse_rss(_load_fixture())
        for r in records:
            assert r.record_type == "bidrag"

    def test_source_is_tillvaxtverket(self):
        records = _parse_rss(_load_fixture())
        for r in records:
            assert r.source == "tillvaxtverket"

    def test_source_id_prefix(self):
        records = _parse_rss(_load_fixture())
        for r in records:
            assert r.source_id.startswith("TV-")

    def test_source_id_numeric(self):
        records = _parse_rss(_load_fixture())
        assert records[0].source_id == "TV-11681"
        assert records[1].source_id == "TV-12345"
        assert records[2].source_id == "TV-99887"

    def test_title_parsed(self):
        records = _parse_rss(_load_fixture())
        assert "kompetensutveckling" in records[0].title.lower()
        assert "ledarskap" in records[1].title.lower()

    def test_buyer_is_tillvaxtverket(self):
        records = _parse_rss(_load_fixture())
        for r in records:
            assert r.buyer == "Tillväxtverket"

    def test_published_date_parsed(self):
        records = _parse_rss(_load_fixture())
        assert records[0].published_date == "2026-01-15"
        assert records[1].published_date == "2026-02-20"

    def test_url_parsed(self):
        records = _parse_rss(_load_fixture())
        assert records[0].url.startswith("https://tillvaxtverket.se/")

    def test_to_db_dict_includes_record_type(self):
        records = _parse_rss(_load_fixture())
        d = records[0].to_db_dict()
        assert d["record_type"] == "bidrag"
        assert d["source"] == "tillvaxtverket"

    def test_empty_xml_returns_empty(self):
        records = _parse_rss(b"<invalid>xml</invalid>")
        assert records == []

    def test_malformed_xml_returns_empty(self):
        records = _parse_rss(b"not xml at all")
        assert records == []
