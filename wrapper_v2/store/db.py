"""store/db — SQLite connection + schema + migrations per R2 §4.10.

Mirrors v1 wrapper_cc.py init_db schema (lines 5614-5670) exactly so
v2 can read existing production state.db data once wired.

Two integration points:
  - init_db(db_path)         — idempotent: creates tables + indexes,
                               runs encryption-column migrations
  - open_connection(db_path) — returns sqlite3.Connection with WAL +
                               foreign-keys + row_factory=Row + safe
                               cross-thread mode for SSE handlers

Doctrine anchors:
  - [[claude_chat_access_discipline]] — DB access is per-row-sensitive;
    callers must respect aggregate-vs-content boundary
  - [[gx44_truth_local_haystack_doctrine]] — schema mirror-exact with
    v1 production
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Union


# ─── Canonical schema (matches v1 state.db exactly) ───────────────────


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    uuid TEXT PRIMARY KEY,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    owner_session TEXT NOT NULL,
    parent_id TEXT,
    model TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (owner_session) REFERENCES sessions(uuid)
);
CREATE INDEX IF NOT EXISTS idx_chats_owner ON chats(owner_session);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT,
    ts INTEGER NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES chats(id)
);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id, id);
"""


# Idempotent encryption-column migrations (run after schema is in place).
_ENCRYPTION_MIGRATIONS = [
    "ALTER TABLE messages ADD COLUMN ciphertext_b64 TEXT",
    "ALTER TABLE messages ADD COLUMN iv_b64 TEXT",
    "ALTER TABLE chats ADD COLUMN encrypted INTEGER DEFAULT 0",
]


def init_db(db_path: Union[str, Path]) -> None:
    """Initialize DB at db_path: create tables + indexes + run migrations.
    Idempotent — safe to call repeatedly. Creates parent-dirs if missing."""
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(p))) as conn:
        conn.executescript(SCHEMA_SQL)
        cur = conn.cursor()
        for stmt in _ENCRYPTION_MIGRATIONS:
            try:
                cur.execute(stmt)
            except sqlite3.OperationalError:
                # column already exists — idempotent migration
                pass
        conn.commit()


def open_connection(db_path: Union[str, Path]) -> sqlite3.Connection:
    """Open a connection with v1-compat pragma settings.

    Returns sqlite3.Connection with:
      - row_factory = sqlite3.Row (column-access by name)
      - WAL journal-mode (better concurrent-read perf)
      - foreign_keys ON
      - check_same_thread=False (SSE handlers cross threads;
        callers MUST serialize writes via their own lock)
    """
    p = Path(db_path)
    conn = sqlite3.connect(str(p), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


__all__ = [
    "SCHEMA_SQL",
    "init_db",
    "open_connection",
]
