"""store/chats — chat CRUD per R2 §4.10.

Extracted from v1 wrapper_cc.py:
  create_chat   (5722) — INSERT new chat with short URL-friendly id
  copy_history  (5731) — fork: copy all messages from src → dst
  get_chat      (5742) — fetch chat + ordered messages (per-row READ)
  append_message(5778) — INSERT message (plaintext or ciphertext)

Per [[claude_chat_access_discipline]]: get_chat is a per-row content
read; callers must respect the operator-authorization-boundary at
the call-site. count + aggregate APIs (get_chat_count, etc.) are
free to use.

Per [[death_penalty_void]]: no DELETE operations exposed; deletion
is operator-tool-only via separate cleanup script.
"""

from __future__ import annotations

import sqlite3
import time
import uuid as _uuid
from dataclasses import dataclass, field
from typing import Optional


# ─── Dataclasses ──────────────────────────────────────────────────────


@dataclass
class Message:
    """One message in a chat. Either content (plaintext) or
    ciphertext_b64+iv_b64 (encrypted), never both."""

    role: str
    content: Optional[str] = None
    ciphertext_b64: Optional[str] = None
    iv_b64: Optional[str] = None
    ts: int = 0


@dataclass
class Chat:
    """A chat record + its ordered messages."""

    id: str
    owner_session: str
    parent_id: Optional[str]
    model: str
    created_at: int
    encrypted: bool = False
    encryption_info: Optional[str] = None
    messages: list = field(default_factory=list)


_ENCRYPTION_INFO_TEXT = (
    "Chat contents are encrypted AES-256-GCM. Key lives in the client URL "
    "fragment, browser-side only; the server never receives it and cannot "
    "decrypt. Each message has chat_contents (ciphertext) + chat_iv (IV)."
)


# ─── Writes ───────────────────────────────────────────────────────────


def create_chat(
    conn: sqlite3.Connection,
    owner_session: str,
    model: str,
    *,
    parent_id: Optional[str] = None,
    encrypted: bool = False,
    now_ts: Optional[int] = None,
) -> str:
    """INSERT a new chat row. Returns the new short chat-id (12 hex chars)."""
    chat_id = _uuid.uuid4().hex[:12]
    ts = now_ts if now_ts is not None else int(time.time())
    conn.execute(
        "INSERT INTO chats (id, owner_session, parent_id, model, created_at, encrypted) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, owner_session, parent_id, model, ts, 1 if encrypted else 0),
    )
    return chat_id


def append_message(
    conn: sqlite3.Connection,
    chat_id: str,
    role: str,
    *,
    content: Optional[str] = None,
    ciphertext_b64: Optional[str] = None,
    iv_b64: Optional[str] = None,
    now_ts: Optional[int] = None,
) -> None:
    """INSERT one message. Either content (plaintext) OR
    ciphertext_b64+iv_b64 (encrypted) — caller must pass at least one.

    For legacy schemas where content is NOT NULL, empty-string is written
    when ciphertext is used. Semantic is carried by ciphertext_b64.
    """
    if content is None:
        content = ""  # NOT NULL legacy constraint
    ts = now_ts if now_ts is not None else int(time.time())
    conn.execute(
        "INSERT INTO messages (chat_id, role, content, ciphertext_b64, iv_b64, ts) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, role, content, ciphertext_b64, iv_b64, ts),
    )


def copy_history(
    conn: sqlite3.Connection,
    src_chat_id: str,
    dst_chat_id: str,
) -> int:
    """Copy all messages from src_chat → dst_chat. Returns count copied.
    For fork-chat operations per parent_id chain."""
    rows = conn.execute(
        "SELECT role, content, ciphertext_b64, iv_b64, ts FROM messages "
        "WHERE chat_id=? ORDER BY id",
        (src_chat_id,),
    ).fetchall()
    for r in rows:
        conn.execute(
            "INSERT INTO messages (chat_id, role, content, ciphertext_b64, iv_b64, ts) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (dst_chat_id, r["role"], r["content"], r["ciphertext_b64"],
             r["iv_b64"], r["ts"]),
        )
    return len(rows)


# ─── Reads ────────────────────────────────────────────────────────────


def get_chat(conn: sqlite3.Connection, chat_id: str) -> Optional[Chat]:
    """PER-ROW READ — fetch chat-record + ordered messages.

    Per [[claude_chat_access_discipline]]: caller must respect operator-
    authorization-boundary. Use get_chat_count() for non-content queries.

    Returns None if chat_id not found.
    """
    row = conn.execute("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone()
    if row is None:
        return None
    msg_rows = conn.execute(
        "SELECT role, content, ciphertext_b64, iv_b64, ts FROM messages "
        "WHERE chat_id=? ORDER BY id",
        (chat_id,),
    ).fetchall()
    keys = set(row.keys()) if hasattr(row, "keys") else set()
    encrypted = bool(row["encrypted"]) if "encrypted" in keys else False
    messages = [
        Message(
            role=r["role"],
            content=r["content"],
            ciphertext_b64=r["ciphertext_b64"],
            iv_b64=r["iv_b64"],
            ts=r["ts"],
        )
        for r in msg_rows
    ]
    return Chat(
        id=row["id"],
        owner_session=row["owner_session"],
        parent_id=row["parent_id"],
        model=row["model"],
        created_at=row["created_at"],
        encrypted=encrypted,
        encryption_info=_ENCRYPTION_INFO_TEXT if encrypted else None,
        messages=messages,
    )


def get_chat_count(conn: sqlite3.Connection) -> int:
    """Aggregate-only count — [[claude_chat_access_discipline]] safe."""
    return conn.execute("SELECT COUNT(*) FROM chats").fetchone()[0]


def get_message_count(conn: sqlite3.Connection) -> int:
    """Aggregate-only count."""
    return conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]


__all__ = [
    "Chat", "Message",
    "create_chat", "append_message", "copy_history",
    "get_chat", "get_chat_count", "get_message_count",
]
