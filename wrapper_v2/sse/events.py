"""sse/events — canonical SSE event-type registry + serialization.

Per R2 §4.11. Snapshot of event-types emitted by v1 wrapper_cc.py
Handler (extracted via baseline_2026_05_30_latency code-scan).
Adding a new event-type? Add it here so the schiri can verify
end-to-end coverage; orphan types in code without registry-entry are
treated as drift.

Doctrine anchors:
  - [[death_penalty_void]] — pre_emit hook may intercept output events
  - [[audit_open_door_doctrine]] — every emitted event is auditable +
    typed (no untracked-payload-leak)
"""

from __future__ import annotations

import enum
import json
from typing import Any


# ─── Canonical event-type registry ────────────────────────────────────


# String literal for now (Python 3.11+ StrEnum would be cleaner; using
# bare str to keep stdlib-old-compat).
EventType = str


KNOWN_EVENT_TYPES: frozenset[EventType] = frozenset([
    # ── Lifecycle ──
    "chat_id",          # new chat created, id returned
    "deploy_stamp",     # backend version + uptime (per task #138)
    "done",             # stream complete
    "error",            # unrecoverable error

    # ── L0 architectural priority ──
    "l0_alarm",         # imminent-life-threat (per [[alarm_l0_…]])
    "l0_vulnerable",    # vulnerable-user redirect
    "l0_harm_hard_stop",  # output-side hard-stop replacement

    # ── Classifier-cascade ──
    "auto_style_mirror",
    "auto_tier_picked",
    "babel_route",
    "classification",
    "classifier_timeout",
    "compound_detected",
    "dial_engaged_via_text",
    "tier_decision",
    "translation_parallel",

    # ── Search + verification ──
    "search_query_debug",
    "search_results",
    "search_results_filtered",
    "search_hop",
    "forced_search",
    "pre_search_done",
    "verifying",
    "fact_check_starting",
    "fact_check_progress",
    "fact_check_complete",
    "fact_check_result",
    "fact_check_warning",
    "cache_hit",

    # ── Generation ──
    "token",
    "status",

    # ── Audit / quality ──
    "coherence_warning",
    "contradiction_warning",
    "doublecheck_unsupported",
    "eloquent_rephrase",
    "eloquent_rephrase_struggled",
    "entity_resolution",

    # ── Factampel emission (R0 verdict-axis) ──
    "factampel_tags",
    "factampel_tag",

    # ── Budget / streaming control ──
    "budget_exceeded",
    "budget_warning",
])


def is_known_type(t: str) -> bool:
    """True if t is a registered SSE event-type."""
    return t in KNOWN_EVENT_TYPES


def serialize_event(event: dict) -> bytes:
    """JSON-serialize an event-dict for SSE wire format ('data: …\\n\\n').

    Raises ValueError if event lacks a 'type' field or the type is
    unknown (catches drift early). To bypass the type-check (e.g. for
    in-flight new event-types), set event['_skip_type_check'] = True
    — drops the marker before serialization.
    """
    if not isinstance(event, dict):
        raise ValueError(f"event must be dict, got {type(event)}")
    t = event.get("type")
    if not t:
        raise ValueError("event missing 'type' field")
    skip_check = event.pop("_skip_type_check", False)
    if not skip_check and t not in KNOWN_EVENT_TYPES:
        raise ValueError(
            f"unknown event-type '{t}' — register in KNOWN_EVENT_TYPES "
            "or set _skip_type_check=True"
        )
    payload = json.dumps(event, ensure_ascii=False)
    return f"data: {payload}\n\n".encode("utf-8")


__all__ = [
    "EventType",
    "KNOWN_EVENT_TYPES",
    "is_known_type",
    "serialize_event",
]
