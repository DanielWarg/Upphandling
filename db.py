"""SQLite schema and CRUD operations for procurements."""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "upphandlingar.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS procurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_id TEXT NOT NULL,
            title TEXT NOT NULL,
            buyer TEXT,
            geography TEXT,
            cpv_codes TEXT,
            procedure_type TEXT,
            published_date TEXT,
            deadline TEXT,
            estimated_value REAL,
            currency TEXT,
            status TEXT,
            url TEXT,
            description TEXT,
            score INTEGER DEFAULT 0,
            score_rationale TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(source, source_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            procurement_id INTEGER NOT NULL UNIQUE,
            full_notice_text TEXT,
            kravsammanfattning TEXT,
            matchningsanalys TEXT,
            prisstrategi TEXT,
            anbudshjalp TEXT,
            model TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (procurement_id) REFERENCES procurements(id)
        )
    """)
    # Add AI relevance columns if they don't exist
    _cur = conn.execute("PRAGMA table_info(procurements)")
    existing_cols = {row[1] for row in _cur.fetchall()}
    if "ai_relevance" not in existing_cols:
        conn.execute("ALTER TABLE procurements ADD COLUMN ai_relevance TEXT")
    if "ai_relevance_reasoning" not in existing_cols:
        conn.execute("ALTER TABLE procurements ADD COLUMN ai_relevance_reasoning TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            procurement_id INTEGER NOT NULL,
            label TEXT NOT NULL CHECK(label IN ('relevant', 'irrelevant')),
            reason TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (procurement_id) REFERENCES procurements(id)
        )
    """)
    conn.commit()
    conn.close()


def upsert_procurement(data: dict) -> int:
    """Insert or update a procurement. Returns the row id."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()

    # Try insert first
    try:
        cur = conn.execute("""
            INSERT INTO procurements
                (source, source_id, title, buyer, geography, cpv_codes,
                 procedure_type, published_date, deadline, estimated_value,
                 currency, status, url, description, score, score_rationale,
                 created_at, updated_at)
            VALUES
                (:source, :source_id, :title, :buyer, :geography, :cpv_codes,
                 :procedure_type, :published_date, :deadline, :estimated_value,
                 :currency, :status, :url, :description, :score, :score_rationale,
                 :created_at, :updated_at)
        """, {
            "source": data["source"],
            "source_id": data["source_id"],
            "title": data["title"],
            "buyer": data.get("buyer"),
            "geography": data.get("geography"),
            "cpv_codes": data.get("cpv_codes"),
            "procedure_type": data.get("procedure_type"),
            "published_date": data.get("published_date"),
            "deadline": data.get("deadline"),
            "estimated_value": data.get("estimated_value"),
            "currency": data.get("currency"),
            "status": data.get("status"),
            "url": data.get("url"),
            "description": data.get("description"),
            "score": data.get("score", 0),
            "score_rationale": data.get("score_rationale"),
            "created_at": now,
            "updated_at": now,
        })
        row_id = cur.lastrowid
    except sqlite3.IntegrityError:
        # Already exists — update
        conn.execute("""
            UPDATE procurements SET
                title = :title,
                buyer = :buyer,
                geography = :geography,
                cpv_codes = :cpv_codes,
                procedure_type = :procedure_type,
                published_date = :published_date,
                deadline = :deadline,
                estimated_value = :estimated_value,
                currency = :currency,
                status = :status,
                url = :url,
                description = :description,
                score = :score,
                score_rationale = :score_rationale,
                updated_at = :updated_at
            WHERE source = :source AND source_id = :source_id
        """, {
            "source": data["source"],
            "source_id": data["source_id"],
            "title": data["title"],
            "buyer": data.get("buyer"),
            "geography": data.get("geography"),
            "cpv_codes": data.get("cpv_codes"),
            "procedure_type": data.get("procedure_type"),
            "published_date": data.get("published_date"),
            "deadline": data.get("deadline"),
            "estimated_value": data.get("estimated_value"),
            "currency": data.get("currency"),
            "status": data.get("status"),
            "url": data.get("url"),
            "description": data.get("description"),
            "score": data.get("score", 0),
            "score_rationale": data.get("score_rationale"),
            "updated_at": now,
        })
        cur = conn.execute(
            "SELECT id FROM procurements WHERE source = ? AND source_id = ?",
            (data["source"], data["source_id"]),
        )
        row_id = cur.fetchone()["id"]

    conn.commit()
    conn.close()
    return row_id


def update_score(procurement_id: int, score: int, rationale: str):
    """Update the lead score for a procurement."""
    conn = get_connection()
    conn.execute(
        "UPDATE procurements SET score = ?, score_rationale = ?, updated_at = ? WHERE id = ?",
        (score, rationale, datetime.now(timezone.utc).isoformat(), procurement_id),
    )
    conn.commit()
    conn.close()


def update_ai_relevance(procurement_id: int, relevance: str, reasoning: str):
    """Update AI relevance assessment for a procurement."""
    conn = get_connection()
    conn.execute(
        "UPDATE procurements SET ai_relevance = ?, ai_relevance_reasoning = ?, updated_at = ? WHERE id = ?",
        (relevance, reasoning, datetime.now(timezone.utc).isoformat(), procurement_id),
    )
    conn.commit()
    conn.close()


def get_all_procurements() -> list[dict]:
    """Return all procurements as a list of dicts."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM procurements ORDER BY score DESC, published_date DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_procurement(procurement_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM procurements WHERE id = ?", (procurement_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def search_procurements(
    query: str = "",
    source: str = "",
    min_score: int = 0,
    max_score: int = 100,
    geography: str = "",
    ai_relevance: str = "",
) -> list[dict]:
    """Search procurements with optional filters.

    ai_relevance: "relevant", "irrelevant", "unassessed", or "" (all).
    """
    conn = get_connection()
    sql = "SELECT * FROM procurements WHERE score BETWEEN ? AND ?"
    params: list = [min_score, max_score]

    if query:
        sql += " AND (title LIKE ? OR description LIKE ? OR buyer LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like, like])

    if source:
        sql += " AND source = ?"
        params.append(source)

    if geography:
        sql += " AND geography LIKE ?"
        params.append(f"%{geography}%")

    if ai_relevance == "relevant":
        sql += " AND ai_relevance = 'relevant'"
    elif ai_relevance == "irrelevant":
        sql += " AND ai_relevance = 'irrelevant'"
    elif ai_relevance == "unassessed":
        sql += " AND ai_relevance IS NULL"

    sql += " ORDER BY score DESC, published_date DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_analysis(procurement_id: int, analysis: dict):
    """Insert or update an AI analysis for a procurement."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO analyses
            (procurement_id, full_notice_text, kravsammanfattning, matchningsanalys,
             prisstrategi, anbudshjalp, model, input_tokens, output_tokens)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(procurement_id) DO UPDATE SET
            full_notice_text = excluded.full_notice_text,
            kravsammanfattning = excluded.kravsammanfattning,
            matchningsanalys = excluded.matchningsanalys,
            prisstrategi = excluded.prisstrategi,
            anbudshjalp = excluded.anbudshjalp,
            model = excluded.model,
            input_tokens = excluded.input_tokens,
            output_tokens = excluded.output_tokens,
            created_at = datetime('now')
    """, (
        procurement_id,
        analysis.get("full_notice_text"),
        analysis.get("kravsammanfattning"),
        analysis.get("matchningsanalys"),
        analysis.get("prisstrategi"),
        analysis.get("anbudshjalp"),
        analysis.get("model"),
        analysis.get("input_tokens"),
        analysis.get("output_tokens"),
    ))
    conn.commit()
    conn.close()


def get_analysis(procurement_id: int) -> dict | None:
    """Return a cached AI analysis for a procurement, or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM analyses WHERE procurement_id = ?", (procurement_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_label(procurement_id: int, label: str, reason: str = "") -> int:
    """Save a feedback label for a procurement. Returns the row id."""
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO labels (procurement_id, label, reason) VALUES (?, ?, ?)",
        (procurement_id, label, reason or None),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_label(procurement_id: int) -> dict | None:
    """Return the latest feedback label for a procurement, or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM labels WHERE procurement_id = ? ORDER BY id DESC LIMIT 1",
        (procurement_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_labels() -> list[dict]:
    """Return all labels with procurement titles, newest first."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT l.*, p.title, p.buyer, p.score, p.score_rationale
        FROM labels l
        JOIN procurements p ON l.procurement_id = p.id
        ORDER BY l.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_label_stats() -> dict:
    """Return label statistics."""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) as c FROM labels").fetchone()["c"]
    relevant = conn.execute(
        "SELECT COUNT(*) as c FROM labels WHERE label = 'relevant'"
    ).fetchone()["c"]
    irrelevant = conn.execute(
        "SELECT COUNT(*) as c FROM labels WHERE label = 'irrelevant'"
    ).fetchone()["c"]
    conn.close()
    return {"total": total, "relevant": relevant, "irrelevant": irrelevant}


def get_stats() -> dict:
    """Return dashboard statistics."""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) as c FROM procurements").fetchone()["c"]
    avg_score = conn.execute("SELECT AVG(score) as a FROM procurements").fetchone()["a"] or 0
    high_fit = conn.execute("SELECT COUNT(*) as c FROM procurements WHERE score >= 60").fetchone()["c"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_today = conn.execute(
        "SELECT COUNT(*) as c FROM procurements WHERE created_at LIKE ?",
        (f"{today}%",),
    ).fetchone()["c"]
    by_source = {}
    for row in conn.execute("SELECT source, COUNT(*) as c FROM procurements GROUP BY source"):
        by_source[row["source"]] = row["c"]
    conn.close()
    return {
        "total": total,
        "avg_score": round(avg_score, 1),
        "high_fit": high_fit,
        "new_today": new_today,
        "by_source": by_source,
    }
