"""store/sessions — session-uuid + cookie handling per R2 §4.10.

Extracted from v1 get_or_create_session (wrapper_cc.py:5710). Returns
typed SessionResult for caller-visibility of is_new flag.

Per [[claude_chat_access_discipline]] +
[[gx44_truth_local_haystack_doctrine]]: session-UUIDs are linkable
to chats but contain no operator-content; aggregate-only reads OK.
"""

from __future__ import annotations

import sqlite3
import time
import uuid as _uuid
from dataclasses import dataclass
from typing import Optional


@dataclass
class SessionResult:
    """Outcome of session-lookup-or-create."""

    uuid: str
    is_new: bool


def get_or_create_session(
    conn: sqlite3.Connection,
    cookie_val: Optional[str] = None,
    *,
    now_ts: Optional[int] = None,
) -> SessionResult:
    """If cookie_val matches existing session → return it.
    Else create fresh session-uuid + record + return it.

    Caller is responsible for any external lock if multiple writers
    might race. Read-then-write race is fine because session-uuid is
    UUIDv4 (collision-vanishing) and INSERT is idempotent-friendly.

    Args:
        conn: open sqlite3 connection (from store.db.open_connection)
        cookie_val: existing session-uuid from request cookie (or None)
        now_ts: clock override for tests; defaults to time.time()
    """
    if cookie_val:
        row = conn.execute(
            "SELECT uuid FROM sessions WHERE uuid=?", (cookie_val,)
        ).fetchone()
        if row is not None:
            return SessionResult(uuid=row["uuid"], is_new=False)

    new_uuid = str(_uuid.uuid4())
    ts = now_ts if now_ts is not None else int(time.time())
    conn.execute(
        "INSERT INTO sessions (uuid, created_at) VALUES (?, ?)",
        (new_uuid, ts),
    )
    return SessionResult(uuid=new_uuid, is_new=True)


def count_sessions(conn: sqlite3.Connection) -> int:
    """Aggregate-only count — [[claude_chat_access_discipline]] safe."""
    return conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]


__all__ = [
    "SessionResult",
    "get_or_create_session",
    "count_sessions",
]
