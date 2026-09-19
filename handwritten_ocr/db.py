"""SQLite database access for job tracking."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    total_pages INTEGER NOT NULL,
    completed_pages INTEGER NOT NULL,
    failed_pages INTEGER NOT NULL,
    error TEXT,
    config_fingerprint TEXT
);

CREATE TABLE IF NOT EXISTS page_jobs (
    page_job_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    page_number INTEGER NOT NULL CHECK (page_number > 0),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    attempt_count INTEGER NOT NULL CHECK (attempt_count >= 0),
    error TEXT,
    raw_text_path TEXT,
    raw_text_sha256 TEXT,
    document_json_path TEXT,
    overlay_path TEXT,
    FOREIGN KEY(job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    UNIQUE(job_id, page_number)
);
"""

class Database:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(
            str(self.db_path),
            isolation_level=None,  # We manage transactions explicitly
            timeout=10.0
        )
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def init_schema(self) -> None:
        with self.connection() as conn:
            conn.executescript(SCHEMA)
