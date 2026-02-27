"""SQLite schema and CRUD operations for procurements."""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "upphandlingar.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
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
            user_username TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (procurement_id) REFERENCES procurements(id)
        )
    """)

    # --- Fas2 tables ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('kam', 'saljchef')),
            email TEXT,
            slack_webhook_url TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            procurement_id INTEGER NOT NULL UNIQUE,
            stage TEXT NOT NULL DEFAULT 'bevakad'
                CHECK(stage IN ('bevakad','kvalificerad','anbud_pagaende','inskickad','vunnen','forlorad')),
            assigned_to TEXT,
            estimated_value REAL,
            probability INTEGER DEFAULT 0 CHECK(probability BETWEEN 0 AND 100),
            notes TEXT,
            updated_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (procurement_id) REFERENCES procurements(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS procurement_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            procurement_id INTEGER NOT NULL,
            user_username TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (procurement_id) REFERENCES procurements(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            normalized_name TEXT NOT NULL,
            buyer_aliases TEXT,
            region TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_dashboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_username TEXT NOT NULL,
            account_id INTEGER NOT NULL,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (account_id) REFERENCES accounts(id),
            UNIQUE(user_username, account_id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            title TEXT,
            email TEXT,
            phone TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS watch_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_username TEXT NOT NULL,
            account_id INTEGER,
            keyword TEXT,
            watch_type TEXT NOT NULL CHECK(watch_type IN ('account', 'keyword')),
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS contract_timeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            procurement_id INTEGER,
            title TEXT NOT NULL,
            contract_start TEXT,
            contract_end TEXT,
            option_end TEXT,
            estimated_reprocurement TEXT,
            notes TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user TEXT NOT NULL,
            to_user TEXT,
            procurement_id INTEGER,
            content TEXT NOT NULL,
            read_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_username TEXT NOT NULL,
            title TEXT NOT NULL,
            event_date TEXT NOT NULL,
            event_type TEXT DEFAULT 'meeting'
                CHECK(event_type IN ('meeting','deadline','follow_up','other')),
            procurement_id INTEGER,
            account_id INTEGER,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_username TEXT NOT NULL,
            notification_type TEXT NOT NULL
                CHECK(notification_type IN ('new_procurement','deadline_warning','watch_match','stage_change','message')),
            title TEXT NOT NULL,
            body TEXT,
            procurement_id INTEGER,
            read_at TEXT,
            sent_via_email INTEGER DEFAULT 0,
            sent_via_slack INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Add account_id column to procurements if missing
    if "account_id" not in existing_cols:
        conn.execute("ALTER TABLE procurements ADD COLUMN account_id INTEGER")

    # Add user_username to labels if missing
    _label_cols = {row[1] for row in conn.execute("PRAGMA table_info(labels)").fetchall()}
    if "user_username" not in _label_cols:
        conn.execute("ALTER TABLE labels ADD COLUMN user_username TEXT")

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_procurements_buyer ON procurements(buyer)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_procurements_account ON procurements(account_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_assigned ON pipeline(assigned_to)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_stage ON pipeline(stage)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_username)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_user)")

    # Seed schema version
    conn.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (2)")

    conn.commit()
    conn.close()


def deduplicate_procurements() -> int:
    """Remove duplicate procurements within the same source based on title + buyer.

    Keeps the row with the latest published_date, deletes the rest.
    Returns number of deleted rows.
    """
    conn = get_connection()
    # Find groups with duplicate (source, title, buyer) and pick the keeper (latest published_date, highest id as tiebreaker)
    dupes = conn.execute("""
        SELECT id FROM procurements
        WHERE id NOT IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY source, title, buyer
                           ORDER BY published_date DESC, id DESC
                       ) AS rn
                FROM procurements
            )
            WHERE rn = 1
        )
    """).fetchall()

    deleted = len(dupes)
    if deleted > 0:
        ids = [row["id"] for row in dupes]
        placeholders = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM analyses WHERE procurement_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM labels WHERE procurement_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM procurements WHERE id IN ({placeholders})", ids)
        conn.commit()

    conn.close()
    return deleted


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


# =====================================================================
# Pipeline CRUD
# =====================================================================

PIPELINE_STAGES = ["bevakad", "kvalificerad", "anbud_pagaende", "inskickad", "vunnen", "forlorad"]

STAGE_LABELS = {
    "bevakad": "Bevakad",
    "kvalificerad": "Kvalificerad",
    "anbud_pagaende": "Anbud pågår",
    "inskickad": "Inskickad",
    "vunnen": "Vunnen",
    "forlorad": "Förlorad",
}

STAGE_PROBABILITIES = {
    "bevakad": 10,
    "kvalificerad": 25,
    "anbud_pagaende": 50,
    "inskickad": 75,
    "vunnen": 100,
    "forlorad": 0,
}


def ensure_pipeline_entry(procurement_id: int, stage: str = "bevakad", assigned_to: str | None = None) -> int:
    """Create a pipeline entry if one doesn't exist. Returns row id."""
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM pipeline WHERE procurement_id = ?", (procurement_id,)
    ).fetchone()
    if existing:
        conn.close()
        return existing["id"]

    proc = conn.execute(
        "SELECT estimated_value FROM procurements WHERE id = ?", (procurement_id,)
    ).fetchone()
    est_val = proc["estimated_value"] if proc else None

    cur = conn.execute(
        """INSERT INTO pipeline (procurement_id, stage, assigned_to, estimated_value, probability)
           VALUES (?, ?, ?, ?, ?)""",
        (procurement_id, stage, assigned_to, est_val, STAGE_PROBABILITIES.get(stage, 0)),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def update_pipeline_stage(procurement_id: int, new_stage: str, updated_by: str | None = None):
    """Update pipeline stage for a procurement."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """UPDATE pipeline SET stage = ?, probability = ?, updated_by = ?, updated_at = ?
           WHERE procurement_id = ?""",
        (new_stage, STAGE_PROBABILITIES.get(new_stage, 0), updated_by, now, procurement_id),
    )
    conn.commit()
    conn.close()


def update_pipeline_assignment(procurement_id: int, assigned_to: str | None, updated_by: str | None = None):
    """Assign a pipeline item to a user."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE pipeline SET assigned_to = ?, updated_by = ?, updated_at = ? WHERE procurement_id = ?",
        (assigned_to, updated_by, now, procurement_id),
    )
    conn.commit()
    conn.close()


def update_pipeline_details(procurement_id: int, estimated_value: float | None = None,
                            probability: int | None = None, notes: str | None = None,
                            updated_by: str | None = None):
    """Update pipeline item details."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    fields = ["updated_by = ?", "updated_at = ?"]
    params: list = [updated_by, now]

    if estimated_value is not None:
        fields.append("estimated_value = ?")
        params.append(estimated_value)
    if probability is not None:
        fields.append("probability = ?")
        params.append(probability)
    if notes is not None:
        fields.append("notes = ?")
        params.append(notes)

    params.append(procurement_id)
    conn.execute(f"UPDATE pipeline SET {', '.join(fields)} WHERE procurement_id = ?", params)
    conn.commit()
    conn.close()


def get_pipeline_items(stage: str | None = None, assigned_to: str | None = None) -> list[dict]:
    """Get pipeline items with procurement details."""
    conn = get_connection()
    sql = """
        SELECT p.*, pi.stage, pi.assigned_to, pi.estimated_value as pipeline_value,
               pi.probability, pi.notes as pipeline_notes, pi.updated_by, pi.updated_at as pipeline_updated
        FROM pipeline pi
        JOIN procurements p ON pi.procurement_id = p.id
        WHERE 1=1
    """
    params: list = []
    if stage:
        sql += " AND pi.stage = ?"
        params.append(stage)
    if assigned_to:
        sql += " AND (pi.assigned_to = ? OR pi.assigned_to IS NULL)"
        params.append(assigned_to)

    sql += " ORDER BY pi.updated_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pipeline_item(procurement_id: int) -> dict | None:
    """Get a single pipeline item with procurement details."""
    conn = get_connection()
    row = conn.execute("""
        SELECT p.*, pi.stage, pi.assigned_to, pi.estimated_value as pipeline_value,
               pi.probability, pi.notes as pipeline_notes, pi.updated_by, pi.updated_at as pipeline_updated
        FROM pipeline pi
        JOIN procurements p ON pi.procurement_id = p.id
        WHERE pi.procurement_id = ?
    """, (procurement_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_pipeline_summary() -> dict:
    """Return pipeline summary: count and weighted value per stage."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT stage,
               COUNT(*) as count,
               SUM(COALESCE(estimated_value, 0) * probability / 100.0) as weighted_value,
               SUM(COALESCE(estimated_value, 0)) as total_value
        FROM pipeline
        GROUP BY stage
    """).fetchall()
    conn.close()
    return {row["stage"]: {"count": row["count"], "weighted_value": row["weighted_value"] or 0,
                           "total_value": row["total_value"] or 0} for row in rows}


def get_pipeline_summary_by_user() -> dict:
    """Return pipeline summary grouped by assigned_to."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT assigned_to, stage, COUNT(*) as count,
               SUM(COALESCE(estimated_value, 0) * probability / 100.0) as weighted_value
        FROM pipeline
        WHERE assigned_to IS NOT NULL
        GROUP BY assigned_to, stage
    """).fetchall()
    conn.close()
    result: dict = {}
    for row in rows:
        user = row["assigned_to"]
        if user not in result:
            result[user] = {}
        result[user][row["stage"]] = {"count": row["count"], "weighted_value": row["weighted_value"] or 0}
    return result


# =====================================================================
# Procurement notes CRUD
# =====================================================================

def add_procurement_note(procurement_id: int, username: str, content: str) -> int:
    """Add a note to a procurement."""
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO procurement_notes (procurement_id, user_username, content) VALUES (?, ?, ?)",
        (procurement_id, username, content),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_procurement_notes(procurement_id: int) -> list[dict]:
    """Get all notes for a procurement, newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM procurement_notes WHERE procurement_id = ? ORDER BY created_at DESC",
        (procurement_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# =====================================================================
# Accounts CRUD
# =====================================================================

def create_account(name: str, buyer_aliases: str = "", region: str = "", notes: str = "") -> int:
    """Create a new account. Returns row id."""
    conn = get_connection()
    normalized = name.lower().strip()
    cur = conn.execute(
        """INSERT OR IGNORE INTO accounts (name, normalized_name, buyer_aliases, region, notes)
           VALUES (?, ?, ?, ?, ?)""",
        (name, normalized, buyer_aliases, region, notes),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_all_accounts() -> list[dict]:
    """Return all accounts."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM accounts ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_account(account_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_account(account_id: int, **kwargs):
    """Update account fields."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    fields = ["updated_at = ?"]
    params: list = [now]
    for key in ("name", "buyer_aliases", "region", "notes"):
        if key in kwargs:
            fields.append(f"{key} = ?")
            params.append(kwargs[key])
            if key == "name":
                fields.append("normalized_name = ?")
                params.append(kwargs[key].lower().strip())
    params.append(account_id)
    conn.execute(f"UPDATE accounts SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def link_procurement_to_account(procurement_id: int, account_id: int):
    """Link a procurement to an account."""
    conn = get_connection()
    conn.execute("UPDATE procurements SET account_id = ? WHERE id = ?", (account_id, procurement_id))
    conn.commit()
    conn.close()


def get_procurements_for_account(account_id: int) -> list[dict]:
    """Get all procurements linked to an account."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM procurements WHERE account_id = ? ORDER BY published_date DESC",
        (account_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def auto_link_procurements_to_accounts():
    """Auto-link procurements to accounts based on buyer_aliases."""
    conn = get_connection()
    accounts = conn.execute("SELECT id, buyer_aliases, normalized_name FROM accounts").fetchall()
    unlinked = conn.execute("SELECT id, buyer FROM procurements WHERE account_id IS NULL AND buyer IS NOT NULL").fetchall()

    linked_count = 0
    for proc in unlinked:
        buyer_lower = (proc["buyer"] or "").lower()
        for acc in accounts:
            aliases = (acc["buyer_aliases"] or "").lower().split(",")
            aliases.append(acc["normalized_name"])
            for alias in aliases:
                alias = alias.strip()
                if alias and alias in buyer_lower:
                    conn.execute("UPDATE procurements SET account_id = ? WHERE id = ?", (acc["id"], proc["id"]))
                    linked_count += 1
                    break
            else:
                continue
            break

    conn.commit()
    conn.close()
    return linked_count


# =====================================================================
# User dashboard CRUD
# =====================================================================

def get_user_dashboard(username: str) -> list[dict]:
    """Get accounts on a user's dashboard, with account details."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT ud.*, a.name, a.region, a.notes as account_notes
        FROM user_dashboard ud
        JOIN accounts a ON ud.account_id = a.id
        WHERE ud.user_username = ?
        ORDER BY ud.sort_order
    """, (username,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_to_dashboard(username: str, account_id: int, sort_order: int = 0):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO user_dashboard (user_username, account_id, sort_order) VALUES (?, ?, ?)",
        (username, account_id, sort_order),
    )
    conn.commit()
    conn.close()


def remove_from_dashboard(username: str, account_id: int):
    conn = get_connection()
    conn.execute(
        "DELETE FROM user_dashboard WHERE user_username = ? AND account_id = ?",
        (username, account_id),
    )
    conn.commit()
    conn.close()


# =====================================================================
# Contacts CRUD
# =====================================================================

def add_contact(account_id: int, name: str, title: str = "", email: str = "",
                phone: str = "", notes: str = "") -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO contacts (account_id, name, title, email, phone, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (account_id, name, title, email, phone, notes),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_contacts(account_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM contacts WHERE account_id = ? ORDER BY name", (account_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_contact(contact_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()


# =====================================================================
# Watch list CRUD
# =====================================================================

def add_watch(username: str, watch_type: str, account_id: int | None = None, keyword: str | None = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO watch_list (user_username, account_id, keyword, watch_type) VALUES (?, ?, ?, ?)",
        (username, account_id, keyword, watch_type),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_watches(username: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT w.*, a.name as account_name
           FROM watch_list w
           LEFT JOIN accounts a ON w.account_id = a.id
           WHERE w.user_username = ? AND w.active = 1
           ORDER BY w.created_at DESC""",
        (username,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def remove_watch(watch_id: int):
    conn = get_connection()
    conn.execute("UPDATE watch_list SET active = 0 WHERE id = ?", (watch_id,))
    conn.commit()
    conn.close()


def get_all_active_watches() -> list[dict]:
    """Get all active watches across all users (for scraper matching)."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT w.*, a.buyer_aliases, a.normalized_name as account_normalized
           FROM watch_list w
           LEFT JOIN accounts a ON w.account_id = a.id
           WHERE w.active = 1"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# =====================================================================
# Contract timeline CRUD
# =====================================================================

def add_contract(account_id: int, title: str, contract_start: str = "",
                 contract_end: str = "", option_end: str = "",
                 estimated_reprocurement: str = "", notes: str = "",
                 created_by: str = "", procurement_id: int | None = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO contract_timeline
           (account_id, procurement_id, title, contract_start, contract_end,
            option_end, estimated_reprocurement, notes, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (account_id, procurement_id, title, contract_start, contract_end,
         option_end, estimated_reprocurement, notes, created_by),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_contracts(account_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM contract_timeline WHERE account_id = ? ORDER BY contract_end",
        (account_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_contracts() -> list[dict]:
    """Get all contracts with account names."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT ct.*, a.name as account_name
        FROM contract_timeline ct
        JOIN accounts a ON ct.account_id = a.id
        ORDER BY ct.contract_end
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# =====================================================================
# Messages CRUD
# =====================================================================

def send_message(from_user: str, content: str, to_user: str | None = None,
                 procurement_id: int | None = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO messages (from_user, to_user, procurement_id, content) VALUES (?, ?, ?, ?)",
        (from_user, to_user, procurement_id, content),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_messages(username: str, other_user: str | None = None, limit: int = 50) -> list[dict]:
    """Get messages for a user. If other_user specified, get conversation between them."""
    conn = get_connection()
    if other_user:
        rows = conn.execute("""
            SELECT * FROM messages
            WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
            ORDER BY created_at DESC LIMIT ?
        """, (username, other_user, other_user, username, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT * FROM messages
            WHERE to_user = ? OR to_user IS NULL OR from_user = ?
            ORDER BY created_at DESC LIMIT ?
        """, (username, username, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unread_count(username: str) -> int:
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) as c FROM messages WHERE to_user = ? AND read_at IS NULL",
        (username,),
    ).fetchone()["c"]
    conn.close()
    return count


def mark_messages_read(username: str, from_user: str | None = None):
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    if from_user:
        conn.execute(
            "UPDATE messages SET read_at = ? WHERE to_user = ? AND from_user = ? AND read_at IS NULL",
            (now, username, from_user),
        )
    else:
        conn.execute(
            "UPDATE messages SET read_at = ? WHERE to_user = ? AND read_at IS NULL",
            (now, username),
        )
    conn.commit()
    conn.close()


def get_conversations(username: str) -> list[dict]:
    """Get list of conversations with latest message preview."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            CASE WHEN from_user = ? THEN to_user ELSE from_user END as other_user,
            content as last_message,
            created_at as last_message_at,
            MAX(id) as last_id
        FROM messages
        WHERE (from_user = ? OR to_user = ?) AND to_user IS NOT NULL
        GROUP BY other_user
        ORDER BY last_id DESC
    """, (username, username, username)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# =====================================================================
# Calendar CRUD
# =====================================================================

def add_calendar_event(username: str, title: str, event_date: str,
                       event_type: str = "meeting", procurement_id: int | None = None,
                       account_id: int | None = None, description: str = "") -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO calendar_events
           (user_username, title, event_date, event_type, procurement_id, account_id, description)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (username, title, event_date, event_type, procurement_id, account_id, description),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_calendar_events(username: str | None = None, start_date: str = "", end_date: str = "") -> list[dict]:
    """Get calendar events. If username is None, get all events."""
    conn = get_connection()
    sql = "SELECT * FROM calendar_events WHERE 1=1"
    params: list = []
    if username:
        sql += " AND user_username = ?"
        params.append(username)
    if start_date:
        sql += " AND event_date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND event_date <= ?"
        params.append(end_date)
    sql += " ORDER BY event_date"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_calendar_event(event_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()


# =====================================================================
# Notifications CRUD
# =====================================================================

def create_notification(username: str, notification_type: str, title: str,
                        body: str = "", procurement_id: int | None = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO notifications (user_username, notification_type, title, body, procurement_id)
           VALUES (?, ?, ?, ?, ?)""",
        (username, notification_type, title, body, procurement_id),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_notifications(username: str, unread_only: bool = False, limit: int = 50) -> list[dict]:
    conn = get_connection()
    sql = "SELECT * FROM notifications WHERE user_username = ?"
    params: list = [username]
    if unread_only:
        sql += " AND read_at IS NULL"
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unread_notification_count(username: str) -> int:
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) as c FROM notifications WHERE user_username = ? AND read_at IS NULL",
        (username,),
    ).fetchone()["c"]
    conn.close()
    return count


def mark_notification_read(notification_id: int):
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("UPDATE notifications SET read_at = ? WHERE id = ?", (now, notification_id))
    conn.commit()
    conn.close()


def mark_all_notifications_read(username: str):
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("UPDATE notifications SET read_at = ? WHERE user_username = ? AND read_at IS NULL", (now, username))
    conn.commit()
    conn.close()


# =====================================================================
# Seed data
# =====================================================================

SEED_ACCOUNTS = [
    ("Västtrafik", "västtrafik,vasttrafik", "Västra Götaland"),
    ("Skånetrafiken", "skånetrafiken,skanetrafiken", "Skåne"),
    ("Region Uppsala / UL", "uppsalatrafik,ul,region uppsala", "Uppsala"),
    ("Hallandstrafiken", "hallandstrafiken", "Halland"),
    ("Östgötatrafiken", "östgötatrafiken,ostgotatrafiken", "Östergötland"),
    ("SL / Trafiknämnden", "storstockholms lokaltrafik,trafiknämnden,sl", "Stockholm"),
    ("Jönköpings Länstrafik", "jönköpings länstrafik,jlt", "Jönköping"),
    ("Länstrafiken Kronoberg", "länstrafiken kronoberg", "Kronoberg"),
    ("Kalmar Länstrafik", "kalmar länstrafik,klt", "Kalmar"),
    ("Blekingetrafiken", "blekingetrafiken", "Blekinge"),
    ("Dalatrafik", "dalatrafik", "Dalarna"),
    ("X-trafik", "x-trafik", "Gävleborg"),
    ("Din Tur", "din tur", "Västernorrland"),
    ("Norrbottens Länstrafik", "norrbottens länstrafik,länstrafiken i norrbotten", "Norrbotten"),
    ("Samtrafiken", "samtrafiken", "Nationell"),
    ("Svealandstrafiken", "svealandstrafiken", "Södermanland/Örebro"),
]


def seed_accounts():
    """Seed accounts table with known Hogia customers."""
    conn = get_connection()
    for name, aliases, region in SEED_ACCOUNTS:
        conn.execute(
            "INSERT OR IGNORE INTO accounts (name, normalized_name, buyer_aliases, region) VALUES (?, ?, ?, ?)",
            (name, name.lower().strip(), aliases, region),
        )
    conn.commit()
    conn.close()


def get_recent_activity(limit: int = 20, username: str | None = None) -> list[dict]:
    """Get recent pipeline changes and notes as activity feed."""
    conn = get_connection()
    activities: list[dict] = []

    # Pipeline changes
    sql_pipeline = """
        SELECT pi.updated_at as timestamp, pi.updated_by as user,
               'stage_change' as type, pi.stage,
               p.title as procurement_title, p.id as procurement_id
        FROM pipeline pi
        JOIN procurements p ON pi.procurement_id = p.id
        WHERE pi.updated_by IS NOT NULL
    """
    params: list = []
    if username:
        sql_pipeline += " AND pi.assigned_to = ?"
        params.append(username)
    sql_pipeline += " ORDER BY pi.updated_at DESC LIMIT ?"
    params.append(limit)

    for row in conn.execute(sql_pipeline, params).fetchall():
        activities.append(dict(row))

    # Notes
    sql_notes = """
        SELECT pn.created_at as timestamp, pn.user_username as user,
               'note' as type, pn.content,
               p.title as procurement_title, p.id as procurement_id
        FROM procurement_notes pn
        JOIN procurements p ON pn.procurement_id = p.id
    """
    params2: list = []
    if username:
        sql_notes += " WHERE pn.user_username = ?"
        params2.append(username)
    sql_notes += " ORDER BY pn.created_at DESC LIMIT ?"
    params2.append(limit)

    for row in conn.execute(sql_notes, params2).fetchall():
        activities.append(dict(row))

    conn.close()

    # Sort by timestamp descending
    activities.sort(key=lambda a: a.get("timestamp") or "", reverse=True)
    return activities[:limit]
