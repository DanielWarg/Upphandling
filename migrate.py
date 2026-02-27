#!/usr/bin/env python3
"""Database migration handler.

Manages schema upgrades from Fas1 (version 1) to Fas2 (version 2).

Usage:
    python migrate.py              # Apply all pending migrations
    python migrate.py --status     # Show current version
"""

import argparse

from db import get_connection, init_db, ensure_pipeline_entry, get_all_procurements, seed_accounts


def get_schema_version() -> int:
    """Get current schema version, 0 if no version table exists."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT MAX(version) as v FROM schema_version").fetchone()
        version = row["v"] if row and row["v"] else 0
    except Exception:
        version = 0
    conn.close()
    return version


def migrate_v1_to_v2():
    """Migrate from Fas1 to Fas2 schema."""
    print("Migrerar v1 → v2...")

    # init_db() creates all new tables and adds columns
    init_db()

    # Seed accounts
    print("  Seedar konton...")
    seed_accounts()

    # Migrate existing relevant procurements to pipeline
    print("  Migrerar relevanta upphandlingar till pipeline...")
    procs = get_all_procurements()
    count = 0
    for p in procs:
        score = p.get("score") or 0
        ai_rel = p.get("ai_relevance")
        if score > 0 and (ai_rel == "relevant" or ai_rel is None):
            ensure_pipeline_entry(p["id"])
            count += 1
    print(f"  {count} upphandlingar tillagda i pipeline")

    # Auto-link procurements to accounts
    from db import auto_link_procurements_to_accounts
    linked = auto_link_procurements_to_accounts()
    print(f"  {linked} upphandlingar länkade till konton")

    # Seed users table from YAML config
    print("  Seedar användare...")
    _seed_users_from_yaml()

    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (2)")
    conn.commit()
    conn.close()

    print("Migration v1 → v2 klar!")


def _seed_users_from_yaml():
    """Populate users table from config/users.yaml."""
    try:
        from pathlib import Path
        import yaml

        config_path = Path(__file__).parent / "config" / "users.yaml"
        if not config_path.exists():
            print("  users.yaml ej funnen, hoppar över")
            return

        with open(config_path) as f:
            config = yaml.safe_load(f)

        conn = get_connection()
        for username, data in config["credentials"]["usernames"].items():
            conn.execute(
                "INSERT OR IGNORE INTO users (username, display_name, role, email) VALUES (?, ?, ?, ?)",
                (username, data.get("name", username), data.get("role", "kam"), data.get("email", "")),
            )
        conn.commit()
        conn.close()
        print("  Användare seedade")
    except Exception as e:
        print(f"  Kunde inte seeda användare: {e}")


def main():
    parser = argparse.ArgumentParser(description="Databasmigrering")
    parser.add_argument("--status", action="store_true", help="Visa nuvarande schemaversion")
    args = parser.parse_args()

    if args.status:
        version = get_schema_version()
        print(f"Schemaversion: {version}")
        return

    current = get_schema_version()
    print(f"Nuvarande schemaversion: {current}")

    if current < 2:
        migrate_v1_to_v2()
    else:
        print("Databasen är redan uppdaterad.")


if __name__ == "__main__":
    main()
