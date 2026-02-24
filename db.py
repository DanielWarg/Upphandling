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
) -> list[dict]:
    """Search procurements with optional filters."""
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

    sql += " ORDER BY score DESC, published_date DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
