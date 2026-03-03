"""Tests for pdf_export.py — PDF generation and batch ZIP export."""

import json
import zipfile
import io

import db
import pdf_export
from pdf_export import (
    generate_procurement_pdf, generate_batch_pdf_zip,
    save_procurement_pdf, save_batch_pdfs, save_batch_zip,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_proc(source_id: str = "PDF-1", title: str = "Ledarskapsutbildning",
                 score: int = 72, **kwargs) -> int:
    base = {
        "source": "ted",
        "source_id": source_id,
        "title": title,
        "buyer": "Stockholms Stad",
        "geography": "SE110",
        "cpv_codes": "80530000",
        "procedure_type": "open",
        "published_date": "2026-01-15",
        "deadline": "2026-04-15",
        "estimated_value": 750000,
        "currency": "SEK",
        "status": "published",
        "url": "https://example.com/1",
        "description": "En testupphandling for ledarskapsutbildning.",
        "score": score,
        "score_rationale": "Hog relevans",
    }
    base.update(kwargs)
    return db.upsert_procurement(base)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSinglePDF:
    def test_generates_valid_pdf(self, tmp_db):
        pid = _insert_proc()
        result = generate_procurement_pdf(pid)
        assert result is not None
        assert result[:5] == b"%PDF-"

    def test_returns_none_for_missing(self, tmp_db):
        result = generate_procurement_pdf(99999)
        assert result is None

    def test_minimal_data(self, tmp_db):
        pid = _insert_proc(
            source_id="MIN-1", title="Minimal",
            buyer=None, geography=None, cpv_codes=None,
            deadline=None, estimated_value=None, url=None,
            description=None, score=0, score_rationale=None,
        )
        result = generate_procurement_pdf(pid)
        assert result is not None
        assert result[:5] == b"%PDF-"

    def test_with_score_breakdown(self, tmp_db):
        breakdown = json.dumps({
            "gate_passed": True,
            "gate_reason": "Utbildningssektor",
            "keyword_matches": [{"keyword": "ledarskap", "weight": 15}],
            "cpv_matches": [{"code": "80530000", "bonus": 5}],
            "buyer_bonus": 3,
            "total": 72,
        })
        pid = _insert_proc(source_id="BD-1", score_breakdown=breakdown)
        result = generate_procurement_pdf(pid)
        assert result is not None
        assert len(result) > 500

    def test_with_analysis(self, tmp_db):
        pid = _insert_proc(source_id="AI-1")
        db.save_analysis(pid, {
            "kravsammanfattning": "Krav pa ledarskapsutbildning for kommunal sektor.",
            "matchningsanalys": "HAST har stark kompetens inom detta omrade.",
            "prisstrategi": "Konkurrenskraftigt pris rekommenderas.",
            "anbudshjalp": "Fokusera pa tidigare erfarenhet.",
        })
        result = generate_procurement_pdf(pid)
        assert result is not None
        assert len(result) > 1000

    def test_with_pipeline(self, tmp_db):
        pid = _insert_proc(source_id="PIPE-1", score=65)
        db.ensure_pipeline_entry(pid, assigned_to="anna_lindberg")
        result = generate_procurement_pdf(pid)
        assert result is not None
        assert result[:5] == b"%PDF-"

    def test_with_notes(self, tmp_db):
        pid = _insert_proc(source_id="NOTE-1")
        db.add_procurement_note(pid, "admin", "En testanteckning")
        db.add_procurement_note(pid, "anna_lindberg", "Andra anteckningen")
        result = generate_procurement_pdf(pid)
        assert result is not None
        assert result[:5] == b"%PDF-"

    def test_with_ai_relevance(self, tmp_db):
        pid = _insert_proc(source_id="REL-1")
        conn = db.get_connection()
        conn.execute(
            "UPDATE procurements SET ai_relevance = ?, ai_relevance_reasoning = ? WHERE id = ?",
            ("relevant", "Matchar HAST:s kompetensomrade", pid),
        )
        conn.commit()
        conn.close()
        result = generate_procurement_pdf(pid)
        assert result is not None


class TestBatchZIP:
    def test_generates_zip_with_correct_count(self, tmp_db):
        ids = [_insert_proc(source_id=f"ZIP-{i}") for i in range(3)]
        result = generate_batch_pdf_zip(ids)
        zf = zipfile.ZipFile(io.BytesIO(result))
        assert len(zf.namelist()) == 3
        for name in zf.namelist():
            assert name.endswith(".pdf")

    def test_skips_missing_ids(self, tmp_db):
        pid = _insert_proc(source_id="ZIP-OK")
        result = generate_batch_pdf_zip([pid, 99999])
        zf = zipfile.ZipFile(io.BytesIO(result))
        assert len(zf.namelist()) == 1

    def test_empty_list(self, tmp_db):
        result = generate_batch_pdf_zip([])
        zf = zipfile.ZipFile(io.BytesIO(result))
        assert len(zf.namelist()) == 0


class TestLocalSave:
    def test_save_single_pdf(self, tmp_db, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_export, "EXPORT_DIR", tmp_path / "export")
        pid = _insert_proc(source_id="SAVE-1")
        path = save_procurement_pdf(pid)
        assert path is not None
        assert path.exists()
        assert path.read_bytes()[:5] == b"%PDF-"

    def test_save_returns_none_for_missing(self, tmp_db, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_export, "EXPORT_DIR", tmp_path / "export")
        assert save_procurement_pdf(99999) is None

    def test_save_batch(self, tmp_db, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_export, "EXPORT_DIR", tmp_path / "export")
        ids = [_insert_proc(source_id=f"SAVEB-{i}") for i in range(3)]
        saved = save_batch_pdfs(ids)
        assert len(saved) == 3
        for p in saved:
            assert p.exists()

    def test_save_batch_skips_missing(self, tmp_db, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_export, "EXPORT_DIR", tmp_path / "export")
        pid = _insert_proc(source_id="SAVEB-OK")
        saved = save_batch_pdfs([pid, 99999])
        assert len(saved) == 1

    def test_export_dir_created(self, tmp_db, tmp_path, monkeypatch):
        export_dir = tmp_path / "new_dir" / "export"
        monkeypatch.setattr(pdf_export, "EXPORT_DIR", export_dir)
        pid = _insert_proc(source_id="MKDIR-1")
        save_procurement_pdf(pid)
        assert export_dir.exists()

    def test_save_batch_zip(self, tmp_db, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_export, "EXPORT_DIR", tmp_path / "export")
        ids = [_insert_proc(source_id=f"ZIPLOCAL-{i}") for i in range(3)]
        path = save_batch_zip(ids)
        assert path is not None
        assert path.exists()
        assert path.suffix == ".zip"
        zf = zipfile.ZipFile(path)
        assert len(zf.namelist()) == 3

    def test_save_batch_zip_empty(self, tmp_db, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_export, "EXPORT_DIR", tmp_path / "export")
        assert save_batch_zip([]) is None

    def test_save_batch_zip_size(self, tmp_db, tmp_path, monkeypatch):
        monkeypatch.setattr(pdf_export, "EXPORT_DIR", tmp_path / "export")
        ids = [_insert_proc(source_id=f"SIZE-{i}") for i in range(10)]
        path = save_batch_zip(ids)
        size_kb = path.stat().st_size / 1024
        # 10 simple PDFs should be well under 500 KB
        assert size_kb < 500
