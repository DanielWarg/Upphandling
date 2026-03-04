"""SQLite schema and CRUD operations for procurements."""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

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
            record_type TEXT NOT NULL DEFAULT 'upphandling',
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
    if "score_breakdown" not in existing_cols:
        conn.execute("ALTER TABLE procurements ADD COLUMN score_breakdown TEXT")
    if "record_type" not in existing_cols:
        conn.execute("ALTER TABLE procurements ADD COLUMN record_type TEXT NOT NULL DEFAULT 'upphandling'")

    # Index for record_type filtering
    conn.execute("CREATE INDEX IF NOT EXISTS idx_procurements_record_type ON procurements(record_type)")

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
                CHECK(stage IN ('bevakad','kvalificerad','anbud_pagaende','inskickad','vunnen','forlorad',
                                'hittad','matchad','ansokan_pagar','beviljad','avslagen')),
            assigned_to TEXT,
            estimated_value REAL,
            probability INTEGER DEFAULT 0 CHECK(probability BETWEEN 0 AND 100),
            notes TEXT,
            updated_by TEXT,
            company_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (procurement_id) REFERENCES procurements(id),
            FOREIGN KEY (company_id) REFERENCES companies(id)
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
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            website_url TEXT,
            industry TEXT,
            ai_profile TEXT,
            ai_profile_updated_at TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS bidrag_company_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            procurement_id INTEGER NOT NULL REFERENCES procurements(id),
            company_id INTEGER NOT NULL REFERENCES companies(id),
            match_score REAL,
            match_reasoning TEXT,
            status TEXT DEFAULT 'suggested',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(procurement_id, company_id)
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

    # Add company_id to pipeline if missing
    _pipeline_cols = {row[1] for row in conn.execute("PRAGMA table_info(pipeline)").fetchall()}
    if "company_id" not in _pipeline_cols:
        conn.execute("ALTER TABLE pipeline ADD COLUMN company_id INTEGER")

    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_procurements_buyer ON procurements(buyer)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_procurements_account ON procurements(account_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_procurements_source ON procurements(source)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_procurements_status ON procurements(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_procurements_deadline ON procurements(deadline)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_procurements_score ON procurements(score)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_assigned ON pipeline(assigned_to)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_stage ON pipeline(stage)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_company ON pipeline(company_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_username)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_procurement ON notifications(procurement_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_user)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_watch_list_user ON watch_list(user_username)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_calendar_events_procurement ON calendar_events(procurement_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_calendar_events_date ON calendar_events(event_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bidrag_matches_procurement ON bidrag_company_matches(procurement_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bidrag_matches_company ON bidrag_company_matches(company_id)")

    # Seed schema version
    conn.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (2)")

    conn.commit()
    conn.close()


def archive_expired_procurements() -> int:
    """Mark procurements with passed deadline as 'expired'. Returns count."""
    conn = get_connection()
    cur = conn.execute("""
        UPDATE procurements
        SET status = 'expired', updated_at = datetime('now')
        WHERE deadline IS NOT NULL
          AND deadline < date('now')
          AND status != 'expired'
    """)
    count = cur.rowcount
    conn.commit()
    conn.close()
    return count


def purge_old_expired(days: int = 180) -> int:
    """Delete procurements that have been expired for >days days.

    Also cascades to analyses, labels, and pipeline.
    Returns number of deleted procurements.
    """
    conn = get_connection()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    # Find old expired IDs
    rows = conn.execute("""
        SELECT id FROM procurements
        WHERE status = 'expired'
          AND deadline IS NOT NULL
          AND deadline < ?
    """, (cutoff,)).fetchall()

    if not rows:
        conn.close()
        return 0

    ids = [r["id"] for r in rows]
    placeholders = ",".join("?" * len(ids))

    conn.execute(f"DELETE FROM analyses WHERE procurement_id IN ({placeholders})", ids)
    conn.execute(f"DELETE FROM labels WHERE procurement_id IN ({placeholders})", ids)
    conn.execute(f"DELETE FROM pipeline WHERE procurement_id IN ({placeholders})", ids)
    conn.execute(f"DELETE FROM procurement_notes WHERE procurement_id IN ({placeholders})", ids)
    conn.execute(f"DELETE FROM procurements WHERE id IN ({placeholders})", ids)

    conn.commit()
    conn.close()
    return len(ids)


def cross_source_deduplicate() -> int:
    """Deduplicate across sources via fuzzy title+buyer matching.

    Normalizes titles (strips common prefixes like 'Sverige - Typ - '),
    groups by normalized_title + buyer, keeps the row with most complete data,
    and merges non-NULL fields from duplicates into the keeper.
    Returns number of deleted rows.
    """
    import re
    conn = get_connection()
    all_procs = conn.execute("SELECT * FROM procurements ORDER BY id").fetchall()
    all_procs = [dict(r) for r in all_procs]

    def normalize_title(title: str) -> str:
        t = title.lower().strip()
        # Strip common TED prefix patterns: "Sverige – City – " or "Sverige-City:"
        t = re.sub(r"^sverige\s*[-–]\s*[^–:]+\s*[-–:]\s*", "", t)
        # Strip leading/trailing whitespace and punctuation
        t = t.strip(" :-–")
        return t

    def normalize_buyer(buyer: str | None) -> str:
        if not buyer:
            return ""
        return buyer.lower().strip()

    # Group by (normalized_title, normalized_buyer)
    groups: dict[tuple[str, str], list[dict]] = {}
    for p in all_procs:
        key = (normalize_title(p["title"]), normalize_buyer(p.get("buyer")))
        groups.setdefault(key, []).append(p)

    deleted_ids: list[int] = []
    merge_fields = ["buyer", "geography", "cpv_codes", "deadline", "estimated_value",
                    "description", "url", "procedure_type", "published_date"]

    for key, procs in groups.items():
        if len(procs) < 2:
            continue
        # Same source duplicates already handled by deduplicate_procurements
        sources = {p["source"] for p in procs}
        if len(sources) < 2:
            continue

        # Score completeness: count non-NULL fields
        def completeness(p: dict) -> int:
            return sum(1 for f in merge_fields if p.get(f))

        procs.sort(key=lambda p: (completeness(p), p.get("score") or 0, p["id"]), reverse=True)
        keeper = procs[0]

        # Merge fields from duplicates into keeper
        for dupe in procs[1:]:
            updates = {}
            for f in merge_fields:
                if not keeper.get(f) and dupe.get(f):
                    updates[f] = dupe[f]
                    keeper[f] = dupe[f]  # Track merged state

            if updates:
                set_clause = ", ".join(f"{f} = ?" for f in updates)
                conn.execute(
                    f"UPDATE procurements SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                    [*updates.values(), keeper["id"]],
                )

            deleted_ids.append(dupe["id"])

    if deleted_ids:
        placeholders = ",".join("?" * len(deleted_ids))
        conn.execute(f"DELETE FROM analyses WHERE procurement_id IN ({placeholders})", deleted_ids)
        conn.execute(f"DELETE FROM labels WHERE procurement_id IN ({placeholders})", deleted_ids)
        conn.execute(f"DELETE FROM pipeline WHERE procurement_id IN ({placeholders})", deleted_ids)
        conn.execute(f"DELETE FROM procurement_notes WHERE procurement_id IN ({placeholders})", deleted_ids)
        conn.execute(f"DELETE FROM procurements WHERE id IN ({placeholders})", deleted_ids)

    conn.commit()
    conn.close()
    return len(deleted_ids)


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
        for table in ("analyses", "labels", "pipeline", "notifications",
                      "calendar_events", "procurement_notes"):
            conn.execute(f"DELETE FROM {table} WHERE procurement_id IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM procurements WHERE id IN ({placeholders})", ids)
        conn.commit()

    conn.close()
    return deleted


def upsert_procurement(data) -> int:
    """Insert or update a procurement. Returns the row id.

    Accepts a dict or a TenderRecord (converted via to_db_dict()).
    """
    # Support TenderRecord objects
    if hasattr(data, "to_db_dict"):
        data = data.to_db_dict()
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()

    # Try insert first
    try:
        cur = conn.execute("""
            INSERT INTO procurements
                (record_type, source, source_id, title, buyer, geography, cpv_codes,
                 procedure_type, published_date, deadline, estimated_value,
                 currency, status, url, description, score, score_rationale,
                 created_at, updated_at)
            VALUES
                (:record_type, :source, :source_id, :title, :buyer, :geography, :cpv_codes,
                 :procedure_type, :published_date, :deadline, :estimated_value,
                 :currency, :status, :url, :description, :score, :score_rationale,
                 :created_at, :updated_at)
        """, {
            "record_type": data.get("record_type", "upphandling"),
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
                record_type = :record_type,
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
            "record_type": data.get("record_type", "upphandling"),
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


def update_score(procurement_id: int, score: int, rationale: str, breakdown: dict | None = None):
    """Update the lead score for a procurement."""
    conn = get_connection()
    breakdown_json = json.dumps(breakdown, ensure_ascii=False) if breakdown else None
    conn.execute(
        "UPDATE procurements SET score = ?, score_rationale = ?, score_breakdown = ?, updated_at = ? WHERE id = ?",
        (score, rationale, breakdown_json, datetime.now(timezone.utc).isoformat(), procurement_id),
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
    record_type: str = "",
) -> list[dict]:
    """Search procurements with optional filters.

    ai_relevance: "relevant", "irrelevant", "unassessed", or "" (all).
    record_type: "upphandling", "bidrag", or "" (all).
    """
    conn = get_connection()
    sql = "SELECT * FROM procurements WHERE score BETWEEN ? AND ?"
    params: list = [min_score, max_score]

    if record_type:
        sql += " AND record_type = ?"
        params.append(record_type)

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

BIDRAG_PIPELINE_STAGES = ["hittad", "matchad", "ansokan_pagar", "inskickad", "beviljad", "avslagen"]

BIDRAG_STAGE_LABELS = {
    "hittad": "Hittad",
    "matchad": "Matchad",
    "ansokan_pagar": "Ansökan pågår",
    "inskickad": "Inskickad",
    "beviljad": "Beviljad",
    "avslagen": "Avslagen",
}

BIDRAG_STAGE_PROBABILITIES = {
    "hittad": 5,
    "matchad": 15,
    "ansokan_pagar": 40,
    "inskickad": 75,
    "beviljad": 100,
    "avslagen": 0,
}

STAGE_LABELS = {
    "bevakad": "Bevakad",
    "kvalificerad": "Kvalificerad",
    "anbud_pagaende": "Anbud pågår",
    "inskickad": "Inskickad",
    "vunnen": "Vunnen",
    "forlorad": "Förlorad",
    **BIDRAG_STAGE_LABELS,
}

STAGE_PROBABILITIES = {
    "bevakad": 10,
    "kvalificerad": 25,
    "anbud_pagaende": 50,
    "inskickad": 75,
    "vunnen": 100,
    "forlorad": 0,
    **BIDRAG_STAGE_PROBABILITIES,
}


def ensure_pipeline_entry(procurement_id: int, stage: str | None = None, assigned_to: str | None = None) -> int:
    """Create a pipeline entry if one doesn't exist. Returns row id.

    If stage is None, auto-detects: "hittad" for bidrag, "bevakad" for upphandling.
    """
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM pipeline WHERE procurement_id = ?", (procurement_id,)
    ).fetchone()
    if existing:
        conn.close()
        return existing["id"]

    proc = conn.execute(
        "SELECT estimated_value, record_type FROM procurements WHERE id = ?", (procurement_id,)
    ).fetchone()
    est_val = proc["estimated_value"] if proc else None

    if stage is None:
        stage = "hittad" if proc and proc["record_type"] == "bidrag" else "bevakad"

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


def _normalize_buyer_text(text: str) -> str:
    """Normalize buyer text for fuzzy matching.

    Lowercases, strips Swedish chars (a/a/o), removes common suffixes (AB, HB),
    and trims whitespace.
    """
    t = text.lower().strip()
    # Swedish char normalization
    t = t.replace("å", "a").replace("ä", "a").replace("ö", "o")
    # Remove common business suffixes
    for suffix in (" ab", " hb", " kb", " ek. for.", " ek for"):
        if t.endswith(suffix):
            t = t[: -len(suffix)]
    return t.strip()


def auto_link_procurements_to_accounts():
    """Auto-link procurements to accounts based on buyer_aliases.

    Uses normalized text matching + fuzzy fallback (SequenceMatcher > 0.85).
    """
    from difflib import SequenceMatcher

    conn = get_connection()
    accounts = conn.execute("SELECT id, buyer_aliases, normalized_name FROM accounts").fetchall()
    unlinked = conn.execute("SELECT id, buyer FROM procurements WHERE account_id IS NULL AND buyer IS NOT NULL").fetchall()

    linked_count = 0
    for proc in unlinked:
        buyer_raw = proc["buyer"] or ""
        buyer_norm = _normalize_buyer_text(buyer_raw)
        buyer_lower = buyer_raw.lower()
        matched = False

        for acc in accounts:
            aliases = (acc["buyer_aliases"] or "").lower().split(",")
            aliases.append(acc["normalized_name"])

            for alias in aliases:
                alias = alias.strip()
                if not alias:
                    continue
                alias_norm = _normalize_buyer_text(alias)

                # Exact substring match (original behavior)
                if alias in buyer_lower or alias_norm in buyer_norm:
                    conn.execute("UPDATE procurements SET account_id = ? WHERE id = ?", (acc["id"], proc["id"]))
                    linked_count += 1
                    matched = True
                    break
            if matched:
                break

        # Fuzzy fallback if no exact match
        if not matched and buyer_norm:
            best_ratio = 0.0
            best_acc_id = None
            for acc in accounts:
                aliases = (acc["buyer_aliases"] or "").lower().split(",")
                aliases.append(acc["normalized_name"])
                for alias in aliases:
                    alias = alias.strip()
                    if not alias:
                        continue
                    ratio = SequenceMatcher(None, buyer_norm, _normalize_buyer_text(alias)).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_acc_id = acc["id"]
            if best_ratio > 0.85 and best_acc_id is not None:
                conn.execute("UPDATE procurements SET account_id = ? WHERE id = ?", (best_acc_id, proc["id"]))
                linked_count += 1

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


def cleanup_old_calendar_events() -> int:
    """Delete calendar events with passed dates. Returns count deleted."""
    conn = get_connection()
    cur = conn.execute("DELETE FROM calendar_events WHERE event_date < date('now')")
    count = cur.rowcount
    conn.commit()
    conn.close()
    return count


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


def deduplicate_notifications() -> int:
    """Remove duplicate notifications (same user + procurement + title). Returns removed count."""
    conn = get_connection()
    cur = conn.execute("""
        DELETE FROM notifications WHERE id NOT IN (
            SELECT MIN(id) FROM notifications
            GROUP BY user_username, procurement_id, title
        )
    """)
    count = cur.rowcount
    conn.commit()
    conn.close()
    return count


def has_notification(username: str, procurement_id: int, notification_type: str) -> bool:
    """Check if a notification already exists for this user+procurement+type."""
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM notifications WHERE user_username = ? AND procurement_id = ? AND notification_type = ? LIMIT 1",
        (username, procurement_id, notification_type),
    ).fetchone()
    conn.close()
    return row is not None


def remove_zero_score_pipeline_entries() -> int:
    """Remove pipeline entries for procurements that now have score=0. Returns count removed."""
    conn = get_connection()
    cur = conn.execute("""
        DELETE FROM pipeline
        WHERE procurement_id IN (
            SELECT id FROM procurements WHERE COALESCE(score, 0) = 0
        )
    """)
    count = cur.rowcount
    conn.commit()
    conn.close()
    return count


def expire_pipeline_entries() -> int:
    """Move expired procurements in pipeline to 'forlorad' stage. Returns count updated."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute("""
        UPDATE pipeline SET stage = 'forlorad', probability = 0, updated_by = 'system', updated_at = ?
        WHERE procurement_id IN (
            SELECT id FROM procurements WHERE status = 'expired'
        )
        AND stage NOT IN ('vunnen', 'forlorad')
    """, (now,))
    count = cur.rowcount
    conn.commit()
    conn.close()
    return count


# =====================================================================
# User sync & seeding
# =====================================================================

def sync_users_from_yaml() -> int:
    """Sync users table from config/users.yaml. Returns count synced."""
    from pathlib import Path
    import yaml

    config_path = Path(__file__).parent / "config" / "users.yaml"
    if not config_path.exists():
        return 0

    with open(config_path) as f:
        config = yaml.safe_load(f)

    usernames = config.get("credentials", {}).get("usernames", {})
    conn = get_connection()

    # Ensure admin role is valid in CHECK constraint — update if needed
    _user_cols = conn.execute("PRAGMA table_info(users)").fetchall()
    # The CHECK constraint on role only allows kam/saljchef — we need to handle admin separately
    # Admin is not stored in users table (hardcoded in auth.py)

    count = 0
    for username, data in usernames.items():
        role = data.get("role", "kam")
        if role not in ("kam", "saljchef"):
            continue  # Skip non-standard roles
        conn.execute("""
            INSERT INTO users (username, display_name, role, email)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                display_name = excluded.display_name,
                role = excluded.role,
                email = excluded.email
        """, (username, data.get("name", username), role, data.get("email", "")))
        count += 1

    conn.commit()
    conn.close()
    return count


def seed_default_watches(username: str) -> int:
    """Create default watches for a user. Returns count created."""
    conn = get_connection()

    # Default keywords relevant to HAST Utveckling
    default_keywords = [
        "ledarskap", "coaching", "chefsutbildning", "organisationsutveckling",
        "kompetensutveckling", "ledarskapsutveckling",
    ]

    count = 0
    for kw in default_keywords:
        # Check if already exists
        existing = conn.execute(
            "SELECT id FROM watch_list WHERE user_username = ? AND keyword = ? AND watch_type = 'keyword'",
            (username, kw),
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO watch_list (user_username, keyword, watch_type) VALUES (?, ?, 'keyword')",
                (username, kw),
            )
            count += 1

    # Account watches for all seeded accounts
    accounts = conn.execute("SELECT id FROM accounts").fetchall()
    for acc in accounts:
        existing = conn.execute(
            "SELECT id FROM watch_list WHERE user_username = ? AND account_id = ? AND watch_type = 'account'",
            (username, acc["id"]),
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO watch_list (user_username, account_id, watch_type) VALUES (?, ?, 'account')",
                (username, acc["id"]),
            )
            count += 1

    conn.commit()
    conn.close()
    return count


def create_deadline_calendar_events() -> int:
    """Auto-create calendar events for procurements with deadline within 30 days.

    Creates events for the 'admin' user (visible to all).
    Returns count created.
    """
    conn = get_connection()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cutoff = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")

    procs = conn.execute("""
        SELECT id, title, deadline, buyer FROM procurements
        WHERE deadline IS NOT NULL
          AND deadline >= ?
          AND deadline <= ?
          AND status != 'expired'
    """, (today, cutoff)).fetchall()

    count = 0
    for p in procs:
        # Check if event already exists for this procurement+date
        existing = conn.execute(
            "SELECT id FROM calendar_events WHERE procurement_id = ? AND event_date = ?",
            (p["id"], p["deadline"]),
        ).fetchone()
        if not existing:
            title = f"Deadline: {(p['title'] or '')[:60]}"
            desc = f"Kopare: {p['buyer'] or 'Okand'}"
            conn.execute("""
                INSERT INTO calendar_events
                    (user_username, title, event_date, event_type, procurement_id, description)
                VALUES (?, ?, ?, 'deadline', ?, ?)
            """, ("admin", title, p["deadline"], p["id"], desc))
            count += 1

    conn.commit()
    conn.close()
    return count


# =====================================================================
# Seed data
# =====================================================================

SEED_ACCOUNTS = [
    # Kollektivtrafik
    ("Västtrafik", "västtrafik,vasttrafik,vasttrafik ab", "Västra Götaland"),
    ("Skånetrafiken", "skånetrafiken,skanetrafiken", "Skåne"),
    ("Region Uppsala / UL", "uppsalatrafik,ul,region uppsala", "Uppsala"),
    ("Hallandstrafiken", "hallandstrafiken", "Halland"),
    ("Östgötatrafiken", "östgötatrafiken,ostgotatrafiken", "Östergötland"),
    ("SL / Trafiknämnden", "storstockholms lokaltrafik,trafiknämnden,sl,trafiknamnd", "Stockholm"),
    ("Jönköpings Länstrafik", "jönköpings länstrafik,jlt,jonkopings lanstrafik", "Jönköping"),
    ("Länstrafiken Kronoberg", "länstrafiken kronoberg,lanstrafiken kronoberg", "Kronoberg"),
    ("Kalmar Länstrafik", "kalmar länstrafik,klt,kalmar lanstrafik", "Kalmar"),
    ("Blekingetrafiken", "blekingetrafiken", "Blekinge"),
    ("Dalatrafik", "dalatrafik", "Dalarna"),
    ("X-trafik", "x-trafik", "Gävleborg"),
    ("Din Tur", "din tur", "Västernorrland"),
    ("Norrbottens Länstrafik", "norrbottens länstrafik,länstrafiken i norrbotten,norrbottens lanstrafik", "Norrbotten"),
    ("Samtrafiken", "samtrafiken", "Nationell"),
    ("Svealandstrafiken", "svealandstrafiken", "Södermanland/Örebro"),
    # Regioner — vanliga upphandlare av ledarskap/utbildning
    ("Region Värmland", "region värmland,region varmland", "Värmland"),
    ("Region Halland", "region halland", "Halland"),
    ("Region Gotland", "region gotland", "Gotland"),
    ("Region Skåne", "region skåne,region skane", "Skåne"),
    ("Region Stockholm", "region stockholm,stockholms läns landsting,stockholms lans landsting", "Stockholm"),
    ("Region Västra Götaland", "region västra götaland,västra götalandsregionen,vgr,region vastra gotaland,vastra gotalandsregionen", "Västra Götaland"),
    ("Region Östergötland", "region östergötland,region ostergotland", "Östergötland"),
    ("Region Jönköpings län", "region jönköpings län,region jönköping,region jonkopings lan,region jonkoping", "Jönköping"),
    ("Region Norrbotten", "region norrbotten", "Norrbotten"),
    # Kommuner — frekventa upphandlare
    ("Huddinge kommun", "huddinge kommun,huddinge", "Stockholm"),
    ("Umeå kommun", "umeå kommun,umea kommun,umea", "Västerbotten"),
    ("Nacka kommun", "nacka kommun,nacka", "Stockholm"),
    ("Stockholms stad", "stockholms stad,stockholm stad,stockholm", "Stockholm"),
    ("Göteborgs stad", "göteborgs stad,göteborg stad,goteborgs stad,goteborg stad,goteborg", "Västra Götaland"),
    ("Malmö stad", "malmö stad,malmo stad,malmo", "Skåne"),
    # Myndigheter
    ("Specialpedagogiska Skolmyndigheten", "specialpedagogiska skolmyndigheten,spsm", "Nationell"),
    ("Stockholms läns sjukvårdsområde", "stockholms läns sjukvårdsområde,slso,stockholms lans sjukvardsomrade", "Stockholm"),
]


def seed_accounts():
    """Seed accounts table with known HAST Utveckling target customers."""
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


def get_procurements_missing_data(source: str | None = None) -> list[dict]:
    """Get procurements missing buyer, description, or geography for backfill."""
    conn = get_connection()
    sql = """
        SELECT id, source, url, title, buyer, description, geography FROM procurements
        WHERE (buyer IS NULL OR buyer = '' OR description IS NULL OR description = '' OR geography IS NULL OR geography = '')
          AND url IS NOT NULL AND url != ''
          AND status != 'expired'
    """
    params: list = []
    if source:
        sql += " AND source = ?"
        params.append(source)
    sql += " ORDER BY score DESC, id"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def purge_expired(max_age_days: int = 90) -> dict:
    """Delete expired procurements and all related data.

    Removes procurements where:
    - deadline has passed, OR
    - no deadline and published_date is older than max_age_days

    Returns dict with counts: {purged, had_deadline, old_no_deadline}.
    """
    conn = get_connection()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).strftime("%Y-%m-%d")

    # Find IDs to purge
    rows = conn.execute("""
        SELECT id FROM procurements
        WHERE (deadline IS NOT NULL AND deadline != '' AND deadline < ?)
           OR ((deadline IS NULL OR deadline = '') AND published_date < ?)
    """, (today, cutoff)).fetchall()
    ids = [r[0] for r in rows]

    if not ids:
        conn.close()
        return {"purged": 0, "had_deadline": 0, "old_no_deadline": 0}

    placeholders = ",".join("?" * len(ids))

    # Count categories before delete
    had_deadline = conn.execute(
        f"SELECT COUNT(*) FROM procurements WHERE id IN ({placeholders}) AND deadline IS NOT NULL AND deadline != ''",
        ids,
    ).fetchone()[0]
    old_no_deadline = len(ids) - had_deadline

    # Delete from child tables first (foreign keys)
    for table in ("analyses", "labels", "pipeline", "procurement_notes", "bidrag_company_matches"):
        conn.execute(f"DELETE FROM {table} WHERE procurement_id IN ({placeholders})", ids)

    # Delete procurements
    conn.execute(f"DELETE FROM procurements WHERE id IN ({placeholders})", ids)
    conn.commit()
    conn.close()

    return {"purged": len(ids), "had_deadline": had_deadline, "old_no_deadline": old_no_deadline}


def update_procurement_fields(procurement_id: int, **kwargs):
    """Update specific fields on a procurement (for backfill)."""
    allowed = {"buyer", "description", "geography", "estimated_value", "deadline"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v}
    if not updates:
        return
    conn = get_connection()
    fields = [f"{k} = ?" for k in updates]
    fields.append("updated_at = datetime('now')")
    params = list(updates.values())
    params.append(procurement_id)
    conn.execute(f"UPDATE procurements SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    conn.close()


# =====================================================================
# Companies CRUD
# =====================================================================

def create_company(name: str, website_url: str = "", created_by: str = "") -> int:
    """Create a new company. Returns row id."""
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO companies (name, website_url, created_by) VALUES (?, ?, ?)",
        (name, website_url or None, created_by or None),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def update_company(company_id: int, **kwargs):
    """Update company fields (industry, ai_profile, website_url, name)."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    fields = ["updated_at = ?"]
    params: list = [now]
    for key in ("name", "website_url", "industry", "ai_profile", "ai_profile_updated_at"):
        if key in kwargs:
            fields.append(f"{key} = ?")
            params.append(kwargs[key])
    params.append(company_id)
    conn.execute(f"UPDATE companies SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    conn.close()


def get_all_companies() -> list[dict]:
    """Return all companies."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM companies ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_company(company_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_company(company_id: int):
    """Delete a company and its matches."""
    conn = get_connection()
    conn.execute("DELETE FROM bidrag_company_matches WHERE company_id = ?", (company_id,))
    conn.execute("UPDATE pipeline SET company_id = NULL WHERE company_id = ?", (company_id,))
    conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))
    conn.commit()
    conn.close()


# =====================================================================
# Bidrag–Company match CRUD
# =====================================================================

def save_bidrag_match(procurement_id: int, company_id: int, score: float, reasoning: str) -> int:
    """Save or update a bidrag-company match. Preserves dismissed status. Returns row id."""
    conn = get_connection()
    # Try insert first — if the row doesn't exist yet
    cur = conn.execute("""
        INSERT OR IGNORE INTO bidrag_company_matches (procurement_id, company_id, match_score, match_reasoning)
        VALUES (?, ?, ?, ?)
    """, (procurement_id, company_id, score, reasoning))

    if cur.rowcount == 0:
        # Row already exists — update score/reasoning only if not dismissed
        conn.execute("""
            UPDATE bidrag_company_matches
            SET match_score = ?, match_reasoning = ?, created_at = datetime('now')
            WHERE procurement_id = ? AND company_id = ? AND status != 'dismissed'
        """, (score, reasoning, procurement_id, company_id))

    row = conn.execute(
        "SELECT id FROM bidrag_company_matches WHERE procurement_id = ? AND company_id = ?",
        (procurement_id, company_id),
    ).fetchone()
    row_id = row["id"] if row else cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_bidrag_sources() -> list[str]:
    """Return distinct sources for bidrag records, sorted alphabetically."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT source FROM procurements WHERE record_type = 'bidrag' ORDER BY source"
    ).fetchall()
    conn.close()
    return [r["source"] for r in rows]


def get_bidrag_matches(procurement_id: int) -> list[dict]:
    """Get all company matches for a bidrag."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT m.*, c.name as company_name, c.website_url, c.industry
        FROM bidrag_company_matches m
        JOIN companies c ON m.company_id = c.id
        WHERE m.procurement_id = ?
        ORDER BY m.match_score DESC
    """, (procurement_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_company_matches(company_id: int) -> list[dict]:
    """Get all bidrag matches for a company."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT m.*, p.title, p.buyer, p.deadline, p.score, p.source
        FROM bidrag_company_matches m
        JOIN procurements p ON m.procurement_id = p.id
        WHERE m.company_id = ?
        ORDER BY m.match_score DESC
    """, (company_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_match_status(match_id: int, status: str):
    """Update match status (accepted/dismissed/suggested)."""
    conn = get_connection()
    conn.execute(
        "UPDATE bidrag_company_matches SET status = ? WHERE id = ?",
        (status, match_id),
    )
    conn.commit()
    conn.close()


def update_pipeline_company(procurement_id: int, company_id: int | None):
    """Link/unlink a company to a pipeline entry."""
    conn = get_connection()
    conn.execute(
        "UPDATE pipeline SET company_id = ? WHERE procurement_id = ?",
        (company_id, procurement_id),
    )
    conn.commit()
    conn.close()
