"""Shared fixtures for the test suite."""

import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path so imports work
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import db as _db


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Provide an isolated temporary database for tests.

    Patches db.DB_PATH so all db functions use a fresh SQLite file.
    Returns the Path to the temporary database file.
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(_db, "DB_PATH", db_path)
    _db.init_db()
    return db_path
