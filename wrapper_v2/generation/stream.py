"""generation/stream — Ollama streaming adapter per R2 §4.5.

Extracted-shell pattern: wraps v1 stream_ollama_chat in an injectable
adapter. Production wires to real Ollama HTTP client; tests pass a
mock-iterator returning controlled token-sequences. This keeps the
generation-loop testable without an Ollama running.

Doctrine: [[basetouch_verified_then_dollschon_overclock]] —
adapter-injection over hardcoded HTTP call so the loop is testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional


# Stream-adapter signature: (model, messages, options) → iterator of
# token-strings (or chunks). Real wrappers honor timeouts +
# cancellation; this protocol is intentionally simple.
OllamaStreamAdapter = Callable[[str, list, Optional[dict]], Iterator[str]]


@dataclass
class StreamConfig:
    """Per-stream config (model + options + tokens-limit)."""

    model: str
    options: dict = field(default_factory=dict)
    max_tokens: Optional[int] = None  # caller-side hard-stop


def stream_via_adapter(
    adapter: OllamaStreamAdapter,
    config: StreamConfig,
    messages: list,
) -> Iterator[str]:
    """Yield tokens from the adapter; enforce max_tokens cap if set.

    Caller is responsible for SSE-emission (use sse.SseEmitter); this
    function ONLY produces the token-stream.
    """
    count = 0
    for token in adapter(config.model, messages, config.options or None):
        if config.max_tokens is not None and count >= config.max_tokens:
            break
        yield token
        count += 1


__all__ = [
    "OllamaStreamAdapter",
    "StreamConfig",
    "stream_via_adapter",
]
