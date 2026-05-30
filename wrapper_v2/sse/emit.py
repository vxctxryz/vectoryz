"""sse/emit — SSE emission helpers (writer-agnostic).

Per R2 §4.11. Extracted from v1 wrapper_cc.py Handler.begin_sse +
sse_send + _safe_sse. SseEmitter is the writer-shaped adapter; tests
pass a list-collector to capture emitted events.

Doctrine: [[death_penalty_void]] — emitters never silently-swallow
errors that would hide a hard-stop event from the user.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from wrapper_v2.sse.events import serialize_event, is_known_type


# Writer protocol: takes raw bytes (or None to signal flush-only-no-write
# for begin_sse headers). Production wires this to HTTP wfile.write;
# tests use a list-collector or BytesIO.
WriteBytesFn = Callable[[bytes], None]


@dataclass
class SseEmitter:
    """Stateful SSE writer wrapping a byte-sink."""

    write_bytes: WriteBytesFn
    on_error: Optional[Callable[[Exception, dict], None]] = None
    started: bool = False
    n_emitted: int = 0
    errors: list = field(default_factory=list)

    # ── Lifecycle ────────────────────────────────────────────────────

    def begin(self) -> None:
        """Mark stream as started. Production-side writes the HTTP
        headers via begin_sse(); this method only flips the started
        flag for in-process emitters (tests, integration shells)."""
        self.started = True

    def end(self) -> None:
        """Emit the done event. Idempotent — calling twice is safe."""
        if not self.started:
            return
        try:
            self.write_bytes(serialize_event({"type": "done"}))
            self.n_emitted += 1
        except Exception as exc:
            self._handle_error(exc, {"type": "done"})
        self.started = False

    # ── Per-event ────────────────────────────────────────────────────

    def send(self, event: dict) -> None:
        """Emit one event. Validates type-registry; silently-skips
        when stream is not started (caller-bug-tolerant)."""
        if not self.started:
            return
        try:
            self.write_bytes(serialize_event(event))
            self.n_emitted += 1
        except Exception as exc:
            self._handle_error(exc, event)

    def send_unchecked(self, event: dict) -> None:
        """Emit one event WITHOUT type-registry check (escape hatch
        for in-flight new event-types). Use sparingly."""
        if not self.started:
            return
        try:
            ev = dict(event)
            ev["_skip_type_check"] = True
            self.write_bytes(serialize_event(ev))
            self.n_emitted += 1
        except Exception as exc:
            self._handle_error(exc, event)

    # ── Internals ────────────────────────────────────────────────────

    def _handle_error(self, exc: Exception, event: dict) -> None:
        self.errors.append((repr(exc), event.get("type", "?")))
        if self.on_error is not None:
            try:
                self.on_error(exc, event)
            except Exception:
                pass


__all__ = [
    "SseEmitter",
    "WriteBytesFn",
]
