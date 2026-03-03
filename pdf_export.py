"""PDF export for procurements — professional white/orange style with full Unicode."""

import io
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

import db

EXPORT_DIR = Path.home() / "Desktop" / "Upphandling_Export"

# ---------------------------------------------------------------------------
# Colours (RGB tuples)
# ---------------------------------------------------------------------------
ORANGE = (249, 115, 22)
ORANGE_DIM = (255, 247, 237)
DARK = (24, 24, 27)
MID = (63, 63, 70)
GREY = (113, 113, 122)
LIGHT_GREY = (228, 228, 231)
VERY_LIGHT = (250, 250, 250)
WHITE = (255, 255, 255)
GREEN = (22, 163, 74)
GREEN_DIM = (240, 253, 244)
RED = (220, 38, 38)
RED_DIM = (254, 242, 242)

# ---------------------------------------------------------------------------
# Font discovery — macOS system fonts with Helvetica fallback
# ---------------------------------------------------------------------------
_FONT_SEARCH = [
    ("/System/Library/Fonts/Supplemental/Arial.ttf",
     "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
     "/System/Library/Fonts/Supplemental/Arial Italic.ttf"),
]

_FONT_REGULAR = None
_FONT_BOLD = None
_FONT_ITALIC = None

for _reg, _bold, _italic in _FONT_SEARCH:
    if Path(_reg).exists():
        _FONT_REGULAR = _reg
        _FONT_BOLD = _bold if Path(_bold).exists() else _reg
        _FONT_ITALIC = _italic if Path(_italic).exists() else _reg
        break


# ---------------------------------------------------------------------------
# Markdown stripping / cleaning
# ---------------------------------------------------------------------------

def _strip_md(text: str) -> str:
    """Remove **bold** markers, emojis, and clean up markdown artefacts."""
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)   # **bold** → bold
    text = re.sub(r'\*([^*]+)\*', r'\1', text)         # *italic* → italic
    text = re.sub(r'`([^`]+)`', r'\1', text)           # `code` → code
    text = re.sub(r'^#{1,4}\s+', '', text, flags=re.MULTILINE)  # ### heading → heading
    # Remove common emojis that fonts can't render
    text = re.sub(r'[\U0001F300-\U0001F9FF\u2600-\u27BF\u2B50\u2705\u274C\u26A0\u2714\u2716]', '', text)
    return text


def _extract_bold_parts(text: str) -> list[tuple[str, bool]]:
    """Split text into (content, is_bold) segments."""
    parts = re.split(r'(\*\*[^*]+\*\*)', text)
    result = []
    for p in parts:
        if not p:
            continue
        if p.startswith("**") and p.endswith("**"):
            result.append((p[2:-2], True))
        else:
            result.append((p, False))
    return result


# ---------------------------------------------------------------------------
# ProcurementPDF class
# ---------------------------------------------------------------------------

class ProcurementPDF(FPDF):
    """A4 PDF with HAST Utveckling branding and full Unicode support."""

    def __init__(self, export_date: str | None = None):
        super().__init__()
        self.export_date = export_date or datetime.now().strftime("%Y-%m-%d")

        if _FONT_REGULAR:
            self.add_font("HastFont", "", _FONT_REGULAR)
            self.add_font("HastFont", "B", _FONT_BOLD)
            self.add_font("HastFont", "I", _FONT_ITALIC)
            self._fn = "HastFont"
        else:
            self._fn = "Helvetica"

        self.set_auto_page_break(auto=True, margin=18)
        self.add_page()

    # --- Header / Footer ---------------------------------------------------

    def header(self):
        # Full-width orange bar at top
        self.set_fill_color(*ORANGE)
        self.rect(0, 0, self.w, 3, "F")

        self.set_y(7)
        self.set_font(self._fn, "B", 10)
        self.set_text_color(*DARK)
        self.cell(0, 5, "HAST Utveckling")

        self.set_font(self._fn, "", 7.5)
        self.set_text_color(*GREY)
        self.cell(0, 5, self.export_date, align="R", new_x="LMARGIN", new_y="NEXT")

        y = self.get_y() + 2
        self.set_draw_color(*LIGHT_GREY)
        self.line(10, y, self.w - 10, y)
        self.set_y(y + 4)

    def footer(self):
        self.set_y(-13)
        self.set_draw_color(*LIGHT_GREY)
        self.line(10, self.get_y(), self.w - 10, self.get_y())
        self.set_y(-11)
        self.set_font(self._fn, "", 6.5)
        self.set_text_color(*GREY)
        self.cell(0, 8, f"HAST Utveckling  \u00b7  Upphandlingsbevakning  \u00b7  Sida {self.page_no()}", align="C")

    # --- Section header with orange accent bar -----------------------------

    def section_title(self, title: str):
        self.ln(5)
        x, y = self.get_x(), self.get_y()
        h = 8
        # Orange left bar
        self.set_fill_color(*ORANGE)
        self.rect(x, y, 2.5, h, "F")
        # Light background
        self.set_fill_color(*VERY_LIGHT)
        self.rect(x + 2.5, y, self.w - 20 - 2.5, h, "F")
        self.set_xy(x + 6, y + 0.5)
        self.set_font(self._fn, "B", 9.5)
        self.set_text_color(*DARK)
        self.cell(0, h - 1, title.upper(), new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    # --- Sub-heading (for AI analysis parts) --------------------------------

    def sub_heading(self, title: str):
        self.ln(2)
        x, y = self.get_x(), self.get_y()
        # Small orange dot before title
        self.set_fill_color(*ORANGE)
        self.ellipse(x + 1, y + 2.5, 3, 3, "F")
        self.set_xy(x + 6, y)
        self.set_font(self._fn, "B", 9)
        self.set_text_color(*MID)
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    # --- Metadata row -------------------------------------------------------

    def label_value_row(self, label: str, value: str, stripe: bool = True):
        x, y = self.get_x(), self.get_y()
        row_h = 6.5
        if stripe:
            self.set_fill_color(*VERY_LIGHT)
            self.rect(x, y, self.w - 20, row_h, "F")
        self.set_xy(x + 3, y)
        self.set_font(self._fn, "", 8)
        self.set_text_color(*GREY)
        self.cell(38, row_h, label.upper())
        self.set_font(self._fn, "", 8.5)
        self.set_text_color(*DARK)
        self.set_xy(x + 42, y)
        self.multi_cell(self.w - 64, row_h, value or "Ej angivet", new_x="LMARGIN", new_y="NEXT")
        if self.get_y() < y + row_h:
            self.set_y(y + row_h)
        self.ln(0.3)

    # --- Score bar ----------------------------------------------------------

    def score_bar(self, score: int):
        bar_w = 90
        bar_h = 8
        x, y = self.get_x(), self.get_y()

        # Track
        self.set_fill_color(*LIGHT_GREY)
        self.rect(x, y, bar_w, bar_h, style="F", round_corners=True, corner_radius=bar_h / 2)

        # Fill
        if score > 0:
            fill_w = max(bar_w * min(score, 100) / 100, bar_h)
            if score >= 60:
                self.set_fill_color(*ORANGE)
            elif score >= 30:
                self.set_fill_color(234, 179, 8)
            else:
                self.set_fill_color(*GREY)
            self.rect(x, y, fill_w, bar_h, style="F", round_corners=True, corner_radius=bar_h / 2)

        # Score number on bar
        self.set_xy(x + 4, y)
        self.set_font(self._fn, "B", 8)
        self.set_text_color(*WHITE)
        self.cell(bar_w - 8, bar_h, f"{score}/100")

        # Priority text
        self.set_xy(x + bar_w + 4, y)
        self.set_font(self._fn, "B", 9)
        if score >= 60:
            self.set_text_color(*ORANGE)
            txt = "Hög prioritet"
        elif score >= 30:
            self.set_text_color(180, 140, 8)
            txt = "Medel prioritet"
        else:
            self.set_text_color(*GREY)
            txt = "Låg prioritet"
        self.cell(50, bar_h, txt)
        self.set_xy(x, y + bar_h + 2)

    # --- Badge (pill shape) -------------------------------------------------

    def badge(self, label: str, fg: tuple, bg: tuple):
        """Coloured pill badge."""
        x, y = self.get_x(), self.get_y()
        self.set_font(self._fn, "B", 7.5)
        w = self.get_string_width(label) + 10
        h = 6
        self.set_fill_color(*bg)
        self.rect(x, y, w, h, style="F", round_corners=True, corner_radius=h / 2)
        self.set_text_color(*fg)
        self.set_xy(x, y)
        self.cell(w, h, label, align="C")
        self.set_xy(x + w + 3, y)

    # --- Rich text (markdown → PDF) ----------------------------------------

    def rich_text(self, text: str):
        """Render markdown-like text: headings, bullets, numbered lists, bold, paragraphs."""
        if not text:
            return
        lines = text.split("\n")
        for line in lines:
            stripped = line.strip()
            if not stripped:
                self.ln(2)
                continue

            # Markdown heading: ## Title or ### Title
            heading_m = re.match(r'^(#{1,4})\s+(.+)', stripped)
            if heading_m:
                self._heading(heading_m.group(2), len(heading_m.group(1)))
                continue

            # Detect indent level (sub-bullet)
            indent = len(line) - len(line.lstrip())
            indent_level = min(indent // 2, 3)

            # Bullet: - or * or unicode bullet
            bullet_m = re.match(r'^[\-\*\u2022]\s+(.+)', stripped)
            # Numbered: 1. or 1)
            num_m = re.match(r'^(\d+)[\.\)]\s+(.+)', stripped)

            if bullet_m:
                self._bullet(bullet_m.group(1), indent_level)
            elif num_m:
                self._numbered(num_m.group(1), num_m.group(2), indent_level)
            else:
                self._paragraph(stripped)

    def _heading(self, text: str, level: int):
        """Render a markdown heading as a styled sub-heading."""
        clean = _strip_md(text)
        self.ln(2)
        self.set_font(self._fn, "B", 10 - level)
        self.set_text_color(*MID)
        self.cell(0, 6, clean, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def _bullet(self, text: str, indent: int = 0):
        x_base = self.get_x() + indent * 5
        self.set_x(x_base)
        self.set_font(self._fn, "", 9)
        self.set_text_color(*ORANGE)
        self.cell(5, 5, "\u2022")
        self.set_text_color(*DARK)
        clean = _strip_md(text)
        self.multi_cell(self.w - 22 - x_base + 10, 5, clean, new_x="LMARGIN", new_y="NEXT")

    def _numbered(self, num: str, text: str, indent: int = 0):
        x_base = self.get_x() + indent * 5
        self.set_x(x_base)
        self.set_font(self._fn, "B", 8)
        self.set_text_color(*ORANGE)
        self.cell(7, 5, f"{num}.")
        self.set_font(self._fn, "", 9)
        self.set_text_color(*DARK)
        clean = _strip_md(text)
        self.multi_cell(self.w - 27 - x_base + 10, 5, clean, new_x="LMARGIN", new_y="NEXT")

    def _paragraph(self, text: str):
        """Render a paragraph with inline bold."""
        parts = _extract_bold_parts(text)
        self.set_text_color(*DARK)
        if len(parts) == 1 and not parts[0][1]:
            self.set_font(self._fn, "", 9)
            self.multi_cell(0, 5, parts[0][0], new_x="LMARGIN", new_y="NEXT")
            return
        for content, is_bold in parts:
            if is_bold:
                self.set_font(self._fn, "B", 9)
                self.set_text_color(*MID)
                self.write(5, content)
                self.set_text_color(*DARK)
            else:
                self.set_font(self._fn, "", 9)
                self.write(5, content)
        self.ln(5)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(val, fallback: str = "Ej angivet") -> str:
    if val is None:
        return fallback
    s = str(val).strip()
    return s if s else fallback


def _fmt_value(val, cur) -> str:
    if not val:
        return "Ej angivet"
    try:
        v = float(val)
        c = cur or "SEK"
        if v >= 1_000_000:
            return f"{v/1_000_000:.1f}M {c}"
        if v >= 1_000:
            return f"{v/1_000:.0f}k {c}"
        return f"{v:.0f} {c}"
    except (ValueError, TypeError):
        return "Ej angivet"


def _title_slug(title: str | None) -> str:
    slug = (title or "upphandling")[:60]
    slug = re.sub(r'[^\w\s\-]', '', slug, flags=re.UNICODE)
    slug = re.sub(r'\s+', '_', slug.strip())
    return slug or "upphandling"


# ---------------------------------------------------------------------------
# Single PDF generation
# ---------------------------------------------------------------------------

def generate_procurement_pdf(procurement_id: int) -> bytes | None:
    """Generate a professional PDF for one procurement."""
    proc = db.get_procurement(procurement_id)
    if not proc:
        return None

    pdf = ProcurementPDF()
    fn = pdf._fn
    score = proc.get("score") or 0

    # ── Title ──────────────────────────────────────────────────────────────
    pdf.set_font(fn, "B", 15)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(0, 7.5, _safe(proc.get("title"), "Utan titel"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Source badge + score bar
    source = _safe(proc.get("source"), "").upper()
    pdf.badge(source, WHITE, ORANGE)
    pdf.ln(6)
    pdf.score_bar(score)

    # Score rationale
    rationale = proc.get("score_rationale")
    if rationale:
        pdf.set_font(fn, "I", 7.5)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(0, 4, _strip_md(rationale), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # ── Metadata ───────────────────────────────────────────────────────────
    pdf.section_title("Metadata")
    rows = [
        ("Köpare", _safe(proc.get("buyer"), "Okänd")),
        ("Geografi", _safe(proc.get("geography"), "Ej angiven")),
        ("CPV-koder", _safe(proc.get("cpv_codes"))),
        ("Förfarandetyp", _safe(proc.get("procedure_type"), "Ej angiven")),
        ("Publicerad", _safe(proc.get("published_date"), "Okänt")),
        ("Deadline", _safe(proc.get("deadline"), "Ej angiven")),
        ("Uppskattat värde", _fmt_value(proc.get("estimated_value"), proc.get("currency"))),
    ]
    if proc.get("url"):
        rows.append(("Länk", proc["url"]))
    for i, (lbl, val) in enumerate(rows):
        pdf.label_value_row(lbl, val, stripe=(i % 2 == 0))

    # ── Score breakdown ────────────────────────────────────────────────────
    raw_bd = proc.get("score_breakdown")
    if raw_bd:
        try:
            bd = json.loads(raw_bd) if isinstance(raw_bd, str) else raw_bd
        except (json.JSONDecodeError, TypeError):
            bd = None
        if bd:
            pdf.section_title("Poänganalys")

            gate_pass = bd.get("gate_passed", False)
            if gate_pass:
                pdf.badge("PASSERAD", GREEN, GREEN_DIM)
            else:
                pdf.badge("BLOCKERAD", RED, RED_DIM)
            reason = bd.get("gate_reason", "")
            if reason:
                pdf.set_font(fn, "", 8.5)
                pdf.set_text_color(*MID)
                pdf.cell(0, 6, reason, new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.ln(7)
            pdf.ln(2)

            # Keywords
            kw = bd.get("keyword_matches", [])
            if kw:
                pdf.set_font(fn, "B", 7)
                pdf.set_text_color(*GREY)
                pdf.cell(0, 5, "NYCKELORD", new_x="LMARGIN", new_y="NEXT")
                for m in kw:
                    pdf.set_x(pdf.get_x() + 3)
                    pdf.set_font(fn, "", 8.5)
                    pdf.set_text_color(*ORANGE)
                    pdf.cell(4, 5, "\u2022")
                    pdf.set_text_color(*DARK)
                    pdf.cell(0, 5, f'{m["keyword"]}  +{m["weight"]}', new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)

            # CPV
            cpv = bd.get("cpv_matches", [])
            if cpv:
                pdf.set_font(fn, "B", 7)
                pdf.set_text_color(*GREY)
                pdf.cell(0, 5, "CPV-MATCHNINGAR", new_x="LMARGIN", new_y="NEXT")
                for m in cpv:
                    pdf.set_x(pdf.get_x() + 3)
                    pdf.set_font(fn, "", 8.5)
                    pdf.set_text_color(*ORANGE)
                    pdf.cell(4, 5, "\u2022")
                    pdf.set_text_color(*DARK)
                    pdf.cell(0, 5, f'{m["code"]}  +{m["bonus"]}', new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)

            bb = bd.get("buyer_bonus", 0)
            if bb:
                pdf.set_font(fn, "", 8.5)
                pdf.set_text_color(*DARK)
                pdf.cell(0, 5, f"Köparbonus: +{bb}", new_x="LMARGIN", new_y="NEXT")

            # Total — highlighted box
            pdf.ln(2)
            total = bd.get("total", 0)
            x, y = pdf.get_x(), pdf.get_y()
            pdf.set_fill_color(*ORANGE_DIM)
            pdf.rect(x, y, 60, 8, style="F", round_corners=True, corner_radius=3)
            pdf.set_xy(x + 3, y)
            pdf.set_font(fn, "B", 10)
            pdf.set_text_color(*ORANGE)
            pdf.cell(54, 8, f"Totalpoäng: {total}/100", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

    # ── AI Relevance ───────────────────────────────────────────────────────
    ai_rel = proc.get("ai_relevance")
    ai_reason = proc.get("ai_relevance_reasoning") or ""
    if ai_rel:
        pdf.section_title("AI-relevans")
        if ai_rel == "relevant":
            pdf.badge("RELEVANT", GREEN, GREEN_DIM)
        else:
            pdf.badge("INTE RELEVANT", RED, RED_DIM)
        if ai_reason:
            pdf.ln(7)
            pdf.set_font(fn, "", 8.5)
            pdf.set_text_color(*MID)
            pdf.multi_cell(0, 5, _strip_md(ai_reason), new_x="LMARGIN", new_y="NEXT")

    # ── AI Analysis ────────────────────────────────────────────────────────
    analysis = db.get_analysis(procurement_id)
    if analysis:
        pdf.section_title("AI-analys")
        sections = [
            ("kravsammanfattning", "Kravsammanfattning"),
            ("matchningsanalys", "Matchningsanalys"),
            ("prisstrategi", "Prisstrategi"),
            ("anbudshjalp", "Anbudshjälp"),
        ]
        for key, label in sections:
            text = analysis.get(key)
            if text:
                # Strip redundant top-level heading (e.g. "# Kravsammanfattning")
                text = re.sub(r'^#\s+\S+.*\n?', '', text, count=1).strip()
                pdf.sub_heading(label)
                pdf.rich_text(text)
                pdf.ln(2)

    # ── Pipeline ───────────────────────────────────────────────────────────
    pipeline = db.get_pipeline_item(procurement_id)
    if pipeline:
        pdf.section_title("Pipeline")
        stage = pipeline.get("stage", "")
        stage_label = db.STAGE_LABELS.get(stage, stage)
        assigned = pipeline.get("assigned_to") or "Ej tilldelad"
        prob = pipeline.get("probability", 0)

        if stage == "vunnen":
            pdf.badge(stage_label, GREEN, GREEN_DIM)
        elif stage == "forlorad":
            pdf.badge(stage_label, RED, RED_DIM)
        elif stage in ("anbud_pagaende", "inskickad"):
            pdf.badge(stage_label, ORANGE, ORANGE_DIM)
        else:
            pdf.badge(stage_label, MID, VERY_LIGHT)
        pdf.ln(8)
        pdf.label_value_row("Tilldelad", assigned)
        pdf.label_value_row("Sannolikhet", f"{prob}%", stripe=False)

    # ── Notes ──────────────────────────────────────────────────────────────
    notes = db.get_procurement_notes(procurement_id)
    if notes:
        pdf.section_title("Anteckningar")
        for i, note in enumerate(notes):
            author = note.get("user_username", "")
            date_str = (note.get("created_at") or "")[:10]
            content = note.get("content", "")

            # Author + date
            pdf.set_font(fn, "B", 7.5)
            pdf.set_text_color(*ORANGE)
            pdf.cell(0, 5, f"{author}  \u00b7  {date_str}", new_x="LMARGIN", new_y="NEXT")
            # Content
            pdf.set_font(fn, "", 8.5)
            pdf.set_text_color(*DARK)
            pdf.multi_cell(0, 4.5, content, new_x="LMARGIN", new_y="NEXT")
            # Separator (except after last)
            if i < len(notes) - 1:
                pdf.set_draw_color(*LIGHT_GREY)
                pdf.line(12, pdf.get_y() + 1.5, pdf.w - 12, pdf.get_y() + 1.5)
                pdf.ln(4)
            else:
                pdf.ln(2)

    return pdf.output()


# ---------------------------------------------------------------------------
# Batch ZIP generation
# ---------------------------------------------------------------------------

def generate_batch_pdf_zip(procurement_ids: list[int]) -> bytes:
    """Generate a ZIP containing one PDF per procurement. Skips missing IDs."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for pid in procurement_ids:
            pdf_bytes = generate_procurement_pdf(pid)
            if pdf_bytes:
                proc = db.get_procurement(pid)
                slug = _title_slug(proc.get("title"))
                zf.writestr(f"{pid}_{slug}.pdf", pdf_bytes)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Save to local export folder (~/Desktop/Upphandling_Export/)
# ---------------------------------------------------------------------------

def save_procurement_pdf(procurement_id: int) -> Path | None:
    """Save a single PDF to EXPORT_DIR. Returns the file path or None."""
    pdf_bytes = generate_procurement_pdf(procurement_id)
    if not pdf_bytes:
        return None
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    proc = db.get_procurement(procurement_id)
    slug = _title_slug(proc.get("title"))
    path = EXPORT_DIR / f"{procurement_id}_{slug}.pdf"
    path.write_bytes(pdf_bytes)
    return path


def save_batch_pdfs(procurement_ids: list[int]) -> list[Path]:
    """Save one PDF per procurement to EXPORT_DIR. Returns list of saved paths."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    for pid in procurement_ids:
        p = save_procurement_pdf(pid)
        if p:
            saved.append(p)
    return saved


def save_batch_zip(procurement_ids: list[int]) -> Path | None:
    """Save a ZIP with all PDFs to EXPORT_DIR. Returns the ZIP path or None if empty."""
    zip_bytes = generate_batch_pdf_zip(procurement_ids)
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    if not zf.namelist():
        return None
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = EXPORT_DIR / f"upphandlingar_{timestamp}.zip"
    path.write_bytes(zip_bytes)
    return path
