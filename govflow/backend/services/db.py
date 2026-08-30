"""SQLite connection + schema management for local persistence."""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "govflow.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflows (
    workflow_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    data TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_workflow_id ON events(workflow_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id TEXT NOT NULL,
    data TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_workflow_id ON audit_log(workflow_id);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notifications_workflow_id ON notifications(workflow_id);
"""

_local = threading.local()


def get_db_path() -> Path:
    override = os.environ.get("GOVFLOW_DB_PATH")
    return Path(override) if override else _DEFAULT_DB_PATH


def get_connection() -> sqlite3.Connection:
    """Returns a thread-local SQLite connection, creating/migrating the schema on first use."""
    db_path = get_db_path()
    cached_path = getattr(_local, "db_path", None)
    if getattr(_local, "conn", None) is None or cached_path != str(db_path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(_SCHEMA)
        conn.commit()
        _local.conn = conn
        _local.db_path = str(db_path)
    return _local.conn


def reset_connection_cache() -> None:
    """Test helper: forces get_connection() to reopen (e.g. after changing GOVFLOW_DB_PATH)."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
    _local.conn = None
    _local.db_path = None
