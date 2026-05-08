from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "state" / "work_ledger.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS work_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    owner TEXT NOT NULL,
    due_at TEXT,
    needs_approval INTEGER NOT NULL DEFAULT 0,
    approval_status TEXT NOT NULL DEFAULT 'NOT_REQUIRED',
    approved_at TEXT,
    completion_signal TEXT,
    next_step TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '[]',
    result TEXT,
    idempotency_key TEXT UNIQUE,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_work_items_status ON work_items(status);
CREATE INDEX IF NOT EXISTS idx_work_items_due_at ON work_items(due_at);
CREATE INDEX IF NOT EXISTS idx_work_items_source ON work_items(source);

CREATE TABLE IF NOT EXISTS work_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_item_id TEXT NOT NULL REFERENCES work_items(id),
    event_type TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    existing = conn.execute("SELECT version FROM schema_version WHERE version = 1").fetchone()
    if existing is None:
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (1, utc_now()),
        )
    conn.commit()

