"""wrapper_v2/store — DB + sessions + chats + deploy_stamp per R2 §4.10.

Extracted from v1 wrapper_cc.py lines 5414-5651 (init_db, get_or_create_
session, create_chat, get_chat, append_message, copy_history). Schema
intentionally matches v1's state.db exactly so v2 can read existing
production data once wired.

Per [[claude_chat_access_discipline]]: store/ access boundary.
- Aggregate-only reads (count, max, etc.) are OK to call freely
- Per-row reads (get_chat content, get_message content) require
  explicit-operator-authorization at the call-site, not at this layer

Architecture: each function takes db_path or Connection; no global
STATE_DB constant. Production injects via construct-once; tests use
tempfile sqlite. Mirror-compat with v1: same schema, same row-shapes.
"""

from wrapper_v2.store.db import (
    init_db,
    open_connection,
    SCHEMA_SQL,
)
from wrapper_v2.store.sessions import (
    get_or_create_session,
    SessionResult,
)
from wrapper_v2.store.chats import (
    create_chat,
    get_chat,
    get_chat_count,
    append_message,
    copy_history,
    Chat,
    Message,
)
from wrapper_v2.store.deploy_stamp import (
    compute_deploy_stamp,
    DeployStamp,
)

__all__ = [
    "init_db", "open_connection", "SCHEMA_SQL",
    "get_or_create_session", "SessionResult",
    "create_chat", "get_chat", "get_chat_count",
    "append_message", "copy_history",
    "Chat", "Message",
    "compute_deploy_stamp", "DeployStamp",
]
