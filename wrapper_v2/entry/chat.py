"""entry/chat — chat-route handlers (D1.a god-class split scaffold).

Thin route-handlers for chat-pipeline endpoints. Per R2 §4.1.

Routes covered (per entry/routes.py):
  GET  /api/chat/{chat_id}                    → get_chat
  POST /api/chat/new                          → new_chat       (SSE stream)
  POST /api/chat/{chat_id}/turn               → turn           (SSE stream)
  POST /api/chat/{chat_id}/persist-assistant  → persist_assistant
  POST /api/chat/{chat_id}/rollback           → rollback

For D1.a scaffold: handlers PARSE input + DELEGATE to adapter; they do
NOT contain pipeline-execution logic. D1.b will extract the actual
turn-execution from v1's _stream_turn into a dedicated
pipeline/turn_executor.py.

The thin-route pattern that emerges here is what v2 production must
follow to avoid the v1 Handler god-class anti-pattern.

Doctrine anchors:
  - [[basetouch_verified_then_dollschon_overclock]] — thin-routes invariant
  - [[claude_chat_access_discipline]] — get_chat / persist / rollback
    must respect operator's chat-content boundary (encrypted-blob only)
  - [[death_penalty_void]] — rollback is reversible, never destructive
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional


# ─── Adapter registry (chat-side providers) ──────────────────────────


# Lightweight (synchronous) adapters
GetChatAdapter = Callable[[str], Optional[dict]]                  # chat_id → chat-dict or None
PersistAssistantAdapter = Callable[[str, dict], dict]             # chat_id, payload → result-dict
RollbackAdapter = Callable[[str, dict], dict]                     # chat_id, payload → result-dict

# Heavy (SSE-streaming) adapters
NewChatStreamAdapter = Callable[[dict], Iterable[dict]]           # body → stream of SSE-event-dicts
TurnStreamAdapter = Callable[[str, dict], Iterable[dict]]         # chat_id, body → stream of SSE-event-dicts


_ADAPTERS: dict[str, Optional[Callable]] = {
    "get_chat": None,
    "persist_assistant": None,
    "rollback": None,
    "new_chat_stream": None,
    "turn_stream": None,
}


def register_adapters(**adapters: Callable) -> None:
    """Install chat-side adapters by name."""
    for k, v in adapters.items():
        if k in _ADAPTERS and v is not None:
            _ADAPTERS[k] = v


# ─── Response dataclasses ────────────────────────────────────────────


@dataclass
class ChatResponse:
    """Non-streaming chat-route response: status + JSON body."""
    status: int
    body: Any


@dataclass
class SSEStreamResponse:
    """Streaming chat-route response: status + iterable of event-dicts."""
    status: int
    events: Iterable[dict]


# ─── Validation helpers ──────────────────────────────────────────────


def _require_message(body: dict) -> Optional[ChatResponse]:
    """If body lacks a non-empty 'message' field, return 400 ChatResponse.
    Else None (caller proceeds)."""
    message = (body.get("message") or "").strip() if body else ""
    if not message:
        return ChatResponse(status=400, body={"error": "message required"})
    return None


def _require_chat_id(chat_id: Optional[str]) -> Optional[ChatResponse]:
    """If chat_id is None/empty, return 400. Else None."""
    if not chat_id:
        return ChatResponse(status=400, body={"error": "chat_id required"})
    return None


# ─── Non-streaming handlers ──────────────────────────────────────────


def get_chat(chat_id: str) -> ChatResponse:
    """GET /api/chat/{chat_id} — fetch chat history + metadata."""
    err = _require_chat_id(chat_id)
    if err:
        return err
    adapter = _ADAPTERS.get("get_chat")
    if adapter is None:
        return ChatResponse(status=200, body={"chat_id": chat_id, "source": "stub", "messages": []})
    try:
        chat = adapter(chat_id)
        if chat is None:
            return ChatResponse(status=404, body={"error": "chat not found", "chat_id": chat_id})
        return ChatResponse(status=200, body=chat)
    except Exception as exc:
        return ChatResponse(status=500, body={"error": repr(exc)})


def persist_assistant(chat_id: str, body: dict) -> ChatResponse:
    """POST /api/chat/{chat_id}/persist-assistant — persist post-stream
    encrypted assistant ciphertext (per claude_chat_access_discipline,
    server never has plaintext for encrypted chats)."""
    err = _require_chat_id(chat_id)
    if err:
        return err
    adapter = _ADAPTERS.get("persist_assistant")
    if adapter is None:
        return ChatResponse(status=200, body={"persisted": True, "chat_id": chat_id, "source": "stub"})
    try:
        result = adapter(chat_id, body or {})
        return ChatResponse(status=200, body=result)
    except Exception as exc:
        return ChatResponse(status=500, body={"error": repr(exc)})


def rollback(chat_id: str, body: dict) -> ChatResponse:
    """POST /api/chat/{chat_id}/rollback — rollback last assistant turn.
    Per [[death_penalty_void]]: reversible action, never destructive."""
    err = _require_chat_id(chat_id)
    if err:
        return err
    adapter = _ADAPTERS.get("rollback")
    if adapter is None:
        return ChatResponse(status=200, body={"rolled_back": True, "chat_id": chat_id, "source": "stub"})
    try:
        result = adapter(chat_id, body or {})
        return ChatResponse(status=200, body=result)
    except Exception as exc:
        return ChatResponse(status=500, body={"error": repr(exc)})


# ─── SSE-streaming handlers ──────────────────────────────────────────


def new_chat(body: dict) -> SSEStreamResponse:
    """POST /api/chat/new — create new chat + stream first turn.
    Returns SSEStreamResponse with iterable of event-dicts."""
    err = _require_message(body)
    if err:
        # Streaming-routes still need to return an error-response if body invalid.
        # We wrap the error-dict as a single-element iterable so the caller
        # can uniformly handle stream-or-not.
        return SSEStreamResponse(
            status=err.status,
            events=iter([{"type": "error", "error": err.body.get("error")}]),
        )
    adapter = _ADAPTERS.get("new_chat_stream")
    if adapter is None:
        # Stub: emit a known-shape minimal event-sequence
        return SSEStreamResponse(
            status=200,
            events=iter([
                {"type": "chat_id", "chat_id": "stub-chat-id"},
                {"type": "status", "phase": "stubbed_pipeline_not_wired"},
                {"type": "done"},
            ]),
        )
    try:
        events = adapter(body or {})
        return SSEStreamResponse(status=200, events=events)
    except Exception as exc:
        return SSEStreamResponse(
            status=500,
            events=iter([{"type": "error", "error": repr(exc)}]),
        )


def turn(chat_id: str, body: dict) -> SSEStreamResponse:
    """POST /api/chat/{chat_id}/turn — continue or fork chat with next turn."""
    err = _require_chat_id(chat_id)
    if err:
        return SSEStreamResponse(
            status=err.status,
            events=iter([{"type": "error", "error": err.body.get("error")}]),
        )
    err = _require_message(body)
    if err:
        return SSEStreamResponse(
            status=err.status,
            events=iter([{"type": "error", "error": err.body.get("error")}]),
        )
    adapter = _ADAPTERS.get("turn_stream")
    if adapter is None:
        return SSEStreamResponse(
            status=200,
            events=iter([
                {"type": "chat_id", "chat_id": chat_id},
                {"type": "status", "phase": "stubbed_pipeline_not_wired"},
                {"type": "done"},
            ]),
        )
    try:
        events = adapter(chat_id, body or {})
        return SSEStreamResponse(status=200, events=events)
    except Exception as exc:
        return SSEStreamResponse(
            status=500,
            events=iter([{"type": "error", "error": repr(exc)}]),
        )


__all__ = [
    "ChatResponse",
    "SSEStreamResponse",
    "register_adapters",
    "get_chat", "persist_assistant", "rollback",
    "new_chat", "turn",
]
