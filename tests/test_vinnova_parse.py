"""Tests for scrapers/vinnova.py — offline parsing of Vinnova API responses + detail pages."""

import json
from pathlib import Path

from scrapers.vinnova import _parse_items, _parse_detail_html

FIXTURE = Path(__file__).parent / "fixtures" / "vinnova_utlysningar.json"


def _load_fixture() -> list[dict]:
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


class TestVinnovaParse:
    def test_parse_returns_records(self):
        items = _load_fixture()
        records = _parse_items(items)
        assert len(records) == 3

    def test_record_type_is_bidrag(self):
        items = _load_fixture()
        records = _parse_items(items)
        for r in records:
            assert r.record_type == "bidrag"

    def test_source_is_vinnova(self):
        items = _load_fixture()
        records = _parse_items(items)
        for r in records:
            assert r.source == "vinnova"

    def test_source_id_prefix(self):
        items = _load_fixture()
        records = _parse_items(items)
        for r in records:
            assert r.source_id.startswith("VINN-")

    def test_source_id_contains_diarienummer(self):
        items = _load_fixture()
        records = _parse_items(items)
        assert records[0].source_id == "VINN-2026-00123"
        assert records[1].source_id == "VINN-2026-00456"

    def test_title_parsed(self):
        items = _load_fixture()
        records = _parse_items(items)
        assert "Kompetensutveckling" in records[0].title
        assert "ledarskapsutveckling" in records[1].title

    def test_buyer_is_vinnova(self):
        items = _load_fixture()
        records = _parse_items(items)
        for r in records:
            assert r.buyer == "Vinnova"

    def test_description_parsed(self):
        items = _load_fixture()
        records = _parse_items(items)
        assert records[0].description is not None
        assert "regioner" in records[0].description.lower()

    def test_published_date_parsed(self):
        items = _load_fixture()
        records = _parse_items(items)
        assert records[0].published_date == "2026-01-15"
        assert records[1].published_date == "2026-02-01"

    def test_url_contains_diarienummer(self):
        items = _load_fixture()
        records = _parse_items(items)
        assert "2026-00123" in records[0].url

    def test_skips_empty_diarienummer(self):
        items = [{"Diarienummer": "", "Titel": "Test"}]
        records = _parse_items(items)
        assert len(records) == 0

    def test_skips_empty_title(self):
        items = [{"Diarienummer": "2026-99999", "Titel": ""}]
        records = _parse_items(items)
        assert len(records) == 0

    def test_to_db_dict_includes_record_type(self):
        items = _load_fixture()
        records = _parse_items(items)
        d = records[0].to_db_dict()
        assert d["record_type"] == "bidrag"
        assert d["source"] == "vinnova"


# ===========================================================================
# Detail page parsing
# ===========================================================================
DETAIL_FIXTURE = Path(__file__).parent / "fixtures" / "vinnova_detail.html"


def _load_detail_fixture() -> str:
    return DETAIL_FIXTURE.read_text(encoding="utf-8")


class TestVinnovaDetailParse:
    def test_extracts_deadline_stanger_den(self):
        data = _parse_detail_html(_load_detail_fixture())
        assert data["deadline"] == "2026-03-24"

    def test_empty_html_returns_none(self):
        data = _parse_detail_html("<html><body></body></html>")
        assert data["deadline"] is None

    def test_deadline_sista_ansokningsdag_inline(self):
        html = '<html><body><p>24 mars 2026 kl 14:00 Sista ansökningsdag</p></body></html>'
        data = _parse_detail_html(html)
        assert data["deadline"] == "2026-03-24"

    def test_deadline_sista_ansokningsdag_label(self):
        html = '<html><body><p>Sista ansökningsdag: 5 maj 2026</p></body></html>'
        data = _parse_detail_html(html)
        assert data["deadline"] == "2026-05-05"

    def test_deadline_abbreviated_month(self):
        html = '<html><body><p>Stänger den 19 dec. 2025</p></body></html>'
        data = _parse_detail_html(html)
        assert data["deadline"] == "2025-12-19"

    def test_deadline_without_den(self):
        html = '<html><body><p>Stänger 1 november 2026</p></body></html>'
        data = _parse_detail_html(html)
        assert data["deadline"] == "2026-11-01"
