"""wrapper_v2/generation — response-generation primitives per R2 §4.5.

Phase-3 module: thin generation primitives (LLM stream + fast-paths).
Heavy implementation (full bare-greeting detector with operator-curated
regex catalog; full auto-style-mirror with register-detection) stays
in v1 wrapper_cc.py for now; D1.b will extract the executor that
delegates to v1 OR these modules per migration-flag.

Sub-modules:
  stream         — Ollama streaming adapter (writer-agnostic)
  bare_greeting  — fast-path detection (minimal German+English catalog)
  style_mirror   — adapter-shell for D1.b extraction

Doctrine: [[basetouch_verified_then_dollschon_overclock]] —
thin-adapter pattern; production wraps real ollama/wrapper_cc
implementations via injected adapters; tests pass mocks.
"""

from wrapper_v2.generation.stream import (
    OllamaStreamAdapter,
    StreamConfig,
    stream_via_adapter,
)
from wrapper_v2.generation.bare_greeting import (
    BareGreetingResult,
    detect_bare_greeting,
    is_bare_greeting,
)
from wrapper_v2.generation.style_mirror import (
    StyleMirrorAdapter,
    StyleMirrorResult,
    register_style_mirror,
    apply_style_mirror,
)

__all__ = [
    # stream
    "OllamaStreamAdapter", "StreamConfig", "stream_via_adapter",
    # bare_greeting
    "BareGreetingResult", "detect_bare_greeting", "is_bare_greeting",
    # style_mirror
    "StyleMirrorAdapter", "StyleMirrorResult",
    "register_style_mirror", "apply_style_mirror",
]
