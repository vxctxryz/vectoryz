"""wrapper_v2/sse — SSE event surface per R2 §4.11.

Phase-3 module: typed SSE event registry + emit helpers extracted
from v1 wrapper_cc.py Handler (begin_sse, sse_send, _v2_pre_emit_hook).

Three sub-modules:
  events       — canonical event-type registry + serialization
  emit         — begin_sse / sse_send / sse_done helpers
  factampel_stream — per-claim emission tied to factampel/emit

Doctrine anchors:
  - [[basetouch_verified_then_dollschon_overclock]] — thin emit-surface
  - [[death_penalty_void]] — pre_emit hook can intercept harm-output
"""

from wrapper_v2.sse.events import (
    KNOWN_EVENT_TYPES,
    EventType,
    serialize_event,
    is_known_type,
)
from wrapper_v2.sse.emit import (
    SseEmitter,
)

__all__ = [
    "KNOWN_EVENT_TYPES",
    "EventType",
    "serialize_event",
    "is_known_type",
    "SseEmitter",
]
