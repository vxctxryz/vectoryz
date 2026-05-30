"""Route-table for wrapper_v2 entry layer — D1.a god-class split scaffold.

Per R2 §4.1: v1 Handler class (2112 lines) routes-table + per-route
pipeline-dispatch all collapsed inline. D1.a extracts the route-table
+ thin handler-stubs. D1.b will extract the pipeline-execution logic
into wrapper_v2/pipeline/turn_executor.py.

For now (D1.a): routes-table maps URL → handler-fn-name. Handler
modules (entry/chat.py + entry/meta.py) provide thin parse+delegate
shells. Pipeline-execution adapter is injected at runtime so the
shell stays testable + the v1 code keeps running while we extract.

Route inventory (matches v1 Handler do_GET + do_POST):

  GET  /api/health                            → meta.health
  GET  /api/engines                           → meta.engines
  GET  /api/branchmap                         → meta.branchmap
  GET  /api/version                           → meta.version
  GET  /api/chat/{chat_id}                    → chat.get_chat
  POST /api/chat/new                          → chat.new_chat
  POST /api/chat/{chat_id}/turn               → chat.turn
  POST /api/chat/{chat_id}/persist-assistant  → chat.persist_assistant
  POST /api/chat/{chat_id}/rollback           → chat.rollback

Doctrine anchors:
  - [[basetouch_verified_then_dollschon_overclock]] — extraction
    before optimization; routes-thin is the wohlgeformt invariant
  - [[gx44_truth_local_haystack_doctrine]] — v1 still authoritative
    while we extract; never destroy what's running
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional


# ─── Route-spec ────────────────────────────────────────────────────────


@dataclass
class RouteSpec:
    """One route in the table."""

    method: str               # "GET" or "POST"
    pattern: str              # e.g. "/api/chat/new" or "/api/chat/{chat_id}/turn"
    handler_module: str       # "chat" or "meta"
    handler_fn: str           # function-name in that module
    needs_body: bool = False  # POST routes typically yes
    sse_stream: bool = False  # routes returning SSE streams (new_chat, turn)
    description: str = ""


# ─── The canonical route-table ─────────────────────────────────────────


ROUTES: list[RouteSpec] = [
    # ── GET routes (meta) ──
    RouteSpec(
        method="GET", pattern="/api/health",
        handler_module="meta", handler_fn="health",
        description="Liveness probe",
    ),
    RouteSpec(
        method="GET", pattern="/api/engines",
        handler_module="meta", handler_fn="engines",
        description="List configured engines",
    ),
    RouteSpec(
        method="GET", pattern="/api/branchmap",
        handler_module="meta", handler_fn="branchmap",
        description="Live branchmap.json endpoint",
    ),
    RouteSpec(
        method="GET", pattern="/api/version",
        handler_module="meta", handler_fn="version",
        description="Backend version + uptime",
    ),

    # ── GET routes (chat) ──
    RouteSpec(
        method="GET", pattern="/api/chat/{chat_id}",
        handler_module="chat", handler_fn="get_chat",
        description="Fetch existing chat (history + metadata)",
    ),

    # ── POST routes (chat) ──
    RouteSpec(
        method="POST", pattern="/api/chat/new",
        handler_module="chat", handler_fn="new_chat",
        needs_body=True, sse_stream=True,
        description="Create new chat + stream first turn",
    ),
    RouteSpec(
        method="POST", pattern="/api/chat/{chat_id}/turn",
        handler_module="chat", handler_fn="turn",
        needs_body=True, sse_stream=True,
        description="Continue or fork chat with next turn",
    ),
    RouteSpec(
        method="POST", pattern="/api/chat/{chat_id}/persist-assistant",
        handler_module="chat", handler_fn="persist_assistant",
        needs_body=True,
        description="Persist (encrypted) assistant message ciphertext after stream",
    ),
    RouteSpec(
        method="POST", pattern="/api/chat/{chat_id}/rollback",
        handler_module="chat", handler_fn="rollback",
        needs_body=True,
        description="Rollback last assistant turn",
    ),
]


# ─── Path-matching helpers ─────────────────────────────────────────────


def _pattern_to_regex(pattern: str) -> re.Pattern:
    """Convert /api/chat/{chat_id}/turn → regex with named group chat_id."""
    parts = pattern.split("/")
    regex_parts = []
    for p in parts:
        if p.startswith("{") and p.endswith("}"):
            name = p[1:-1]
            regex_parts.append(f"(?P<{name}>[^/]+)")
        else:
            regex_parts.append(re.escape(p))
    return re.compile("^" + "/".join(regex_parts) + "$")


# Pre-compile all routes for fast lookup
_COMPILED: list[tuple[RouteSpec, re.Pattern]] = [(r, _pattern_to_regex(r.pattern)) for r in ROUTES]


@dataclass
class RouteMatch:
    """Result of matching a request to the route-table."""
    spec: RouteSpec
    path_params: dict  # captured {chat_id: "abc123", ...}


def match_route(method: str, path: str) -> Optional[RouteMatch]:
    """Find the RouteSpec matching this method + path. None if no match."""
    method = method.upper()
    for spec, regex in _COMPILED:
        if spec.method != method:
            continue
        m = regex.match(path)
        if m:
            return RouteMatch(spec=spec, path_params=m.groupdict())
    return None


def list_routes(method: Optional[str] = None) -> list[RouteSpec]:
    """List all routes, optionally filtered by HTTP method."""
    if method is None:
        return list(ROUTES)
    method = method.upper()
    return [r for r in ROUTES if r.method == method]


__all__ = [
    "RouteSpec",
    "RouteMatch",
    "ROUTES",
    "match_route",
    "list_routes",
]
