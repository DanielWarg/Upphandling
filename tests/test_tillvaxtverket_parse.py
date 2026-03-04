"""Tests for scrapers/tillvaxtverket.py — offline parsing of Tillväxtverket RSS feed + detail pages."""

from pathlib import Path

from scrapers.tillvaxtverket import _parse_rss, _parse_detail_html

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


# ===========================================================================
# Detail page parsing
# ===========================================================================
DETAIL_FIXTURE = Path(__file__).parent / "fixtures" / "tillvaxtverket_detail.html"


def _load_detail_fixture() -> str:
    return DETAIL_FIXTURE.read_text(encoding="utf-8")


class TestTillvaxtverketDetailParse:
    def test_extracts_description(self):
        data = _parse_detail_html(_load_detail_fixture())
        assert data["description"] is not None
        assert "konkurrenskraft" in data["description"].lower()

    def test_extracts_deadline(self):
        data = _parse_detail_html(_load_detail_fixture())
        assert data["deadline"] == "2026-02-17"

    def test_empty_html_returns_none(self):
        data = _parse_detail_html("<html><body></body></html>")
        assert data["description"] is None
        assert data["deadline"] is None

    def test_deadline_stanger_format(self):
        html = '<html><body><p>Utlysningen stänger 5 mars 2026</p></body></html>'
        data = _parse_detail_html(html)
        assert data["deadline"] == "2026-03-05"

    def test_deadline_sista_ansokningsdag(self):
        html = '<html><body><p>Sista ansökningsdag: 10 april 2026</p></body></html>'
        data = _parse_detail_html(html)
        assert data["deadline"] == "2026-04-10"

    def test_description_truncated(self):
        long_text = "A" * 5000
        html = f'<html><body><main><p>{long_text}</p></main></body></html>'
        data = _parse_detail_html(html)
        assert data["description"] is not None
        assert len(data["description"]) <= 3000
