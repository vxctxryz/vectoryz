"""store/ falsifiable benchmark — DB + sessions + chats + deploy_stamp.

Per R2.1b R2-target dir extraction.

Verifies:
  - schema init idempotent
  - sessions: get_or_create + new vs returning
  - chats: create + get round-trip + count
  - messages: append plaintext + ciphertext, order preserved
  - chats: copy_history (fork) duplicates messages
  - get_chat returns None on unknown chat_id
  - encryption field roundtrips (chats.encrypted + messages.ciphertext_b64)
  - deploy_stamp: shape + uptime monotonic

Run via: python3 -m wrapper_v2.tests.test_store  (stdlib-only)
Exit-code 0 = all-pass.

Doctrine: [[claude_chat_access_discipline]] +
[[gx44_truth_local_haystack_doctrine]].
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.store import (
    init_db, open_connection,
    get_or_create_session, SessionResult,
    create_chat, get_chat, get_chat_count,
    append_message, copy_history,
    compute_deploy_stamp,
)
from wrapper_v2.store.chats import get_message_count
from wrapper_v2.store.sessions import count_sessions
from wrapper_v2.store import deploy_stamp as _ds


_GREEN = "\033[92m"
_RED = "\033[91m"
_BOLD = "\033[1m"
_RESET = "\033[0m"

_PASS = 0
_FAIL = 0


def _check(label: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  {_GREEN}✓{_RESET} {label}")
    else:
        _FAIL += 1
        print(f"  {_RED}✗ {label}{_RESET}")
        if detail:
            print(f"      {detail}")


def _fresh_db():
    """Return (conn, path) for a fresh tempfile DB; caller cleans up."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    conn = open_connection(path)
    return conn, path


def _rm(path: str) -> None:
    try: os.unlink(path)
    except OSError: pass


# ─── DB schema ─────────────────────────────────────────────────────────


def test_init_db_idempotent():
    print(f"\n{_BOLD}[T1]{_RESET} init_db is idempotent")
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(p)
    init_db(p)  # second call must not raise
    conn = open_connection(p)
    # Verify tables present
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    _check("sessions table present", "sessions" in tables)
    _check("chats table present", "chats" in tables)
    _check("messages table present", "messages" in tables)
    conn.close()
    _rm(p)


def test_schema_has_encryption_columns():
    print(f"\n{_BOLD}[T2]{_RESET} encryption-column migrations applied")
    conn, p = _fresh_db()
    # chats.encrypted column
    chat_cols = {row[1] for row in conn.execute("PRAGMA table_info(chats)").fetchall()}
    _check("chats.encrypted column", "encrypted" in chat_cols)
    # messages.ciphertext_b64 + iv_b64
    msg_cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
    _check("messages.ciphertext_b64 column", "ciphertext_b64" in msg_cols)
    _check("messages.iv_b64 column", "iv_b64" in msg_cols)
    conn.close(); _rm(p)


# ─── sessions ──────────────────────────────────────────────────────────


def test_session_create_new():
    print(f"\n{_BOLD}[T3]{_RESET} get_or_create_session(None) → new session")
    conn, p = _fresh_db()
    result = get_or_create_session(conn, None)
    _check("returns SessionResult", isinstance(result, SessionResult))
    _check("is_new = True", result.is_new is True)
    _check("uuid populated (36 chars)", len(result.uuid) == 36)
    _check("count_sessions = 1", count_sessions(conn) == 1)
    conn.close(); _rm(p)


def test_session_returning():
    print(f"\n{_BOLD}[T4]{_RESET} get_or_create_session(existing) → returning")
    conn, p = _fresh_db()
    first = get_or_create_session(conn, None)
    second = get_or_create_session(conn, first.uuid)
    _check("same uuid returned", second.uuid == first.uuid)
    _check("is_new = False", second.is_new is False)
    _check("count_sessions still 1", count_sessions(conn) == 1)
    conn.close(); _rm(p)


def test_session_unknown_cookie_creates_new():
    print(f"\n{_BOLD}[T5]{_RESET} unknown cookie → new session")
    conn, p = _fresh_db()
    result = get_or_create_session(conn, "00000000-0000-0000-0000-000000000000")
    _check("is_new = True", result.is_new is True)
    _check("uuid != cookie", result.uuid != "00000000-0000-0000-0000-000000000000")
    conn.close(); _rm(p)


# ─── chats ─────────────────────────────────────────────────────────────


def test_chat_create_get_roundtrip():
    print(f"\n{_BOLD}[T6]{_RESET} create_chat + get_chat round-trip")
    conn, p = _fresh_db()
    session = get_or_create_session(conn, None)
    chat_id = create_chat(conn, session.uuid, model="test-model")
    _check("chat_id is 12-hex chars", len(chat_id) == 12)

    chat = get_chat(conn, chat_id)
    _check("get_chat returns chat", chat is not None)
    _check("chat.id matches", chat.id == chat_id)
    _check("chat.owner_session matches", chat.owner_session == session.uuid)
    _check("chat.model = 'test-model'", chat.model == "test-model")
    _check("chat.encrypted = False (default)", chat.encrypted is False)
    _check("chat.messages empty", chat.messages == [])
    _check("get_chat_count = 1", get_chat_count(conn) == 1)
    conn.close(); _rm(p)


def test_chat_get_unknown_returns_none():
    print(f"\n{_BOLD}[T7]{_RESET} get_chat on unknown id returns None")
    conn, p = _fresh_db()
    _check("returns None", get_chat(conn, "nonexistent") is None)
    conn.close(); _rm(p)


def test_chat_encrypted_flag_roundtrip():
    print(f"\n{_BOLD}[T8]{_RESET} encrypted=True chat roundtrips with encryption_info")
    conn, p = _fresh_db()
    sess = get_or_create_session(conn, None)
    cid = create_chat(conn, sess.uuid, model="m", encrypted=True)
    chat = get_chat(conn, cid)
    _check("chat.encrypted = True", chat.encrypted is True)
    _check("encryption_info populated", bool(chat.encryption_info))
    _check("encryption_info mentions AES-256-GCM",
           "AES-256-GCM" in (chat.encryption_info or ""))
    conn.close(); _rm(p)


# ─── messages ──────────────────────────────────────────────────────────


def test_append_plaintext_message():
    print(f"\n{_BOLD}[T9]{_RESET} append + get plaintext messages preserve order")
    conn, p = _fresh_db()
    sess = get_or_create_session(conn, None)
    cid = create_chat(conn, sess.uuid, model="m")
    append_message(conn, cid, "user", content="hello", now_ts=1000)
    append_message(conn, cid, "assistant", content="hi back", now_ts=1001)
    append_message(conn, cid, "user", content="follow-up", now_ts=1002)
    chat = get_chat(conn, cid)
    _check("3 messages stored", len(chat.messages) == 3)
    _check("order preserved (user/assistant/user)",
           [m.role for m in chat.messages] == ["user", "assistant", "user"])
    _check("content roundtrip",
           chat.messages[0].content == "hello"
           and chat.messages[1].content == "hi back")
    _check("get_message_count = 3", get_message_count(conn) == 3)
    conn.close(); _rm(p)


def test_append_ciphertext_message():
    print(f"\n{_BOLD}[T10]{_RESET} ciphertext message stored without plaintext")
    conn, p = _fresh_db()
    sess = get_or_create_session(conn, None)
    cid = create_chat(conn, sess.uuid, model="m", encrypted=True)
    append_message(conn, cid, "user",
                   ciphertext_b64="ABC123==", iv_b64="IVxx==", now_ts=2000)
    chat = get_chat(conn, cid)
    _check("1 message stored", len(chat.messages) == 1)
    msg = chat.messages[0]
    _check("ciphertext_b64 preserved", msg.ciphertext_b64 == "ABC123==")
    _check("iv_b64 preserved", msg.iv_b64 == "IVxx==")
    _check("content empty (legacy NOT NULL)", msg.content == "")
    conn.close(); _rm(p)


# ─── copy_history (fork) ───────────────────────────────────────────────


def test_copy_history_fork():
    print(f"\n{_BOLD}[T11]{_RESET} copy_history duplicates messages from src→dst")
    conn, p = _fresh_db()
    sess = get_or_create_session(conn, None)
    src = create_chat(conn, sess.uuid, model="m")
    append_message(conn, src, "user", content="q1", now_ts=1000)
    append_message(conn, src, "assistant", content="a1", now_ts=1001)
    append_message(conn, src, "user", content="q2", now_ts=1002)

    dst = create_chat(conn, sess.uuid, model="m", parent_id=src)
    copied = copy_history(conn, src, dst)
    _check("copy_history returns 3", copied == 3)
    dst_chat = get_chat(conn, dst)
    _check("dst has 3 messages", len(dst_chat.messages) == 3)
    _check("dst.parent_id = src", dst_chat.parent_id == src)
    _check("messages content matches",
           [m.content for m in dst_chat.messages] == ["q1", "a1", "q2"])
    conn.close(); _rm(p)


# ─── deploy_stamp ──────────────────────────────────────────────────────


def test_deploy_stamp_shape():
    print(f"\n{_BOLD}[T12]{_RESET} deploy_stamp has correct shape")
    _ds._reset_for_test()
    stamp = compute_deploy_stamp(now_ts=1700000000.0)
    _check("backend_started_at populated", bool(stamp.backend_started_at))
    _check("wrapper_mtime = 'unknown' (no path passed)",
           stamp.wrapper_mtime == "unknown")
    _check("uptime_seconds >= 0", stamp.uptime_seconds >= 0)
    event = stamp.as_event()
    _check("as_event type=deploy_stamp", event["type"] == "deploy_stamp")
    _check("as_event has all keys",
           {"type", "backend_started_at", "wrapper_cc_mtime", "uptime_seconds"} <= set(event.keys()))


def test_deploy_stamp_uptime_grows():
    print(f"\n{_BOLD}[T13]{_RESET} deploy_stamp uptime grows monotonically")
    _ds._reset_for_test()
    s1 = compute_deploy_stamp(now_ts=1700000000.0)
    s2 = compute_deploy_stamp(now_ts=1700000005.0)
    s3 = compute_deploy_stamp(now_ts=1700000100.0)
    _check("s2.uptime >= s1.uptime", s2.uptime_seconds >= s1.uptime_seconds)
    _check("s3.uptime > s2.uptime", s3.uptime_seconds > s2.uptime_seconds)
    _check("s3.uptime around 100s", 99 <= s3.uptime_seconds <= 101)


def test_deploy_stamp_with_wrapper_path():
    print(f"\n{_BOLD}[T14]{_RESET} deploy_stamp reads wrapper-mtime from given path")
    _ds._reset_for_test()
    # Use this test file itself as wrapper-path target (exists, has mtime)
    this_file = str(Path(__file__).absolute())
    stamp = compute_deploy_stamp(wrapper_path=this_file)
    _check("wrapper_mtime != 'unknown'", stamp.wrapper_mtime != "unknown")
    _check("wrapper_mtime is YYYYMMDDHHMMSS format (14 chars)",
           len(stamp.wrapper_mtime) == 14 and stamp.wrapper_mtime.isdigit())


# ─── Runner ────────────────────────────────────────────────────────────


def main() -> int:
    print(f"{_BOLD}store/ — DB + sessions + chats + deploy_stamp · falsifiable{_RESET}")
    print("=" * 75)

    test_init_db_idempotent()
    test_schema_has_encryption_columns()
    test_session_create_new()
    test_session_returning()
    test_session_unknown_cookie_creates_new()
    test_chat_create_get_roundtrip()
    test_chat_get_unknown_returns_none()
    test_chat_encrypted_flag_roundtrip()
    test_append_plaintext_message()
    test_append_ciphertext_message()
    test_copy_history_fork()
    test_deploy_stamp_shape()
    test_deploy_stamp_uptime_grows()
    test_deploy_stamp_with_wrapper_path()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}store/ result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
