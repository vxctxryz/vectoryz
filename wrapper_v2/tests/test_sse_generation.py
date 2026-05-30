"""sse/ + generation/ falsifiable benchmark — completes R2.1 14/14.

Per R2 §4.5 + §4.11 + R2.1b R2-target extraction completion.

Verifies:
  - sse/events: KNOWN_EVENT_TYPES registry + serialize_event +
    is_known_type; unknown-type raises; serialization shape
  - sse/emit: SseEmitter begin/end/send + error-collection +
    type-validation + unchecked-bypass
  - generation/stream: stream_via_adapter respects max_tokens cap
  - generation/bare_greeting: detect_bare_greeting on DE + EN
    canonical greetings + non-bare rejection + emoticon-strip
  - generation/style_mirror: adapter-injection + apply + skip-cases

Run via: python3 -m wrapper_v2.tests.test_sse_generation  (stdlib-only)
Exit-code 0 = all-pass.

Doctrine: [[basetouch_verified_then_dollschon_overclock]] +
[[audit_open_door_doctrine]] + [[death_penalty_void]].
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.sse.events import (
    KNOWN_EVENT_TYPES, serialize_event, is_known_type,
)
from wrapper_v2.sse.emit import SseEmitter
from wrapper_v2.generation.stream import (
    stream_via_adapter, StreamConfig,
)
from wrapper_v2.generation.bare_greeting import (
    detect_bare_greeting, is_bare_greeting, BareGreetingResult,
)
from wrapper_v2.generation.style_mirror import (
    register_style_mirror, apply_style_mirror,
)


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


# ─── sse/events ────────────────────────────────────────────────────────


def test_events_registry_populated():
    print(f"\n{_BOLD}[sse/T1]{_RESET} KNOWN_EVENT_TYPES registry has key events")
    for t in ["chat_id", "done", "error", "token", "status",
              "l0_alarm", "l0_vulnerable", "l0_harm_hard_stop",
              "factampel_tags", "deploy_stamp", "babel_route"]:
        _check(f"  '{t}' registered", is_known_type(t))


def test_events_unknown_returns_false():
    print(f"\n{_BOLD}[sse/T2]{_RESET} is_known_type False on unknown")
    _check("'__unknown__' not registered", is_known_type("__unknown__") is False)


def test_serialize_event_shape():
    print(f"\n{_BOLD}[sse/T3]{_RESET} serialize_event produces SSE 'data: ...\\n\\n' bytes")
    out = serialize_event({"type": "token", "content": "hello"})
    text = out.decode("utf-8")
    _check("starts with 'data: '", text.startswith("data: "))
    _check("ends with '\\n\\n'", text.endswith("\n\n"))
    _check("contains payload", '"type": "token"' in text)


def test_serialize_event_unknown_type_raises():
    print(f"\n{_BOLD}[sse/T4]{_RESET} serialize_event raises ValueError on unknown type")
    try:
        serialize_event({"type": "__bogus__"})
        _check("raised ValueError", False, "no exception")
    except ValueError:
        _check("raised ValueError on unknown type", True)


def test_serialize_event_skip_check_bypass():
    print(f"\n{_BOLD}[sse/T5]{_RESET} _skip_type_check bypasses registry validation")
    out = serialize_event({"type": "__new_type__", "_skip_type_check": True, "value": 42})
    text = out.decode("utf-8")
    _check("bypass works", "__new_type__" in text)
    _check("_skip_type_check marker stripped from output", "_skip_type_check" not in text)


# ─── sse/emit ─────────────────────────────────────────────────────────


def test_emitter_begin_send_end():
    print(f"\n{_BOLD}[sse/T6]{_RESET} SseEmitter begin/send/end records events")
    chunks = []
    emitter = SseEmitter(write_bytes=chunks.append)
    emitter.begin()
    emitter.send({"type": "chat_id", "chat_id": "test-123"})
    emitter.send({"type": "token", "content": "Hi"})
    emitter.end()
    _check("3 chunks emitted (chat_id + token + done)", len(chunks) == 3)
    _check("n_emitted = 3", emitter.n_emitted == 3)
    _check("no errors", emitter.errors == [])


def test_emitter_unknown_type_recorded_as_error():
    print(f"\n{_BOLD}[sse/T7]{_RESET} SseEmitter records unknown-type as error (not raises)")
    chunks = []
    emitter = SseEmitter(write_bytes=chunks.append)
    emitter.begin()
    emitter.send({"type": "__bogus__"})
    emitter.end()
    _check("error recorded", len(emitter.errors) == 1)
    _check("error tuple has type-name",
           emitter.errors[0][1] == "__bogus__")


def test_emitter_send_unchecked():
    print(f"\n{_BOLD}[sse/T8]{_RESET} SseEmitter.send_unchecked bypasses type-check")
    chunks = []
    emitter = SseEmitter(write_bytes=chunks.append)
    emitter.begin()
    emitter.send_unchecked({"type": "__new__", "data": "test"})
    emitter.end()
    _check("event-chunk emitted via unchecked", len(chunks) >= 1)
    _check("no error recorded", len(emitter.errors) == 0)


def test_emitter_send_before_begin_silent():
    print(f"\n{_BOLD}[sse/T9]{_RESET} send before begin is silently ignored")
    chunks = []
    emitter = SseEmitter(write_bytes=chunks.append)
    emitter.send({"type": "token", "content": "x"})
    _check("nothing written", chunks == [])


# ─── generation/stream ───────────────────────────────────────────────


def test_stream_respects_max_tokens():
    print(f"\n{_BOLD}[generation/T1]{_RESET} stream_via_adapter caps at max_tokens")
    def adapter(model, messages, options):
        for i in range(20):
            yield f"tok{i}"
    tokens = list(stream_via_adapter(
        adapter, StreamConfig(model="m", max_tokens=5), messages=[]
    ))
    _check("exactly 5 tokens yielded", len(tokens) == 5)
    _check("first token = tok0", tokens[0] == "tok0")
    _check("last token = tok4", tokens[4] == "tok4")


def test_stream_no_cap_passes_all():
    print(f"\n{_BOLD}[generation/T2]{_RESET} stream without max_tokens yields all")
    def adapter(model, messages, options):
        for s in ["a", "b", "c"]:
            yield s
    tokens = list(stream_via_adapter(adapter, StreamConfig(model="m"), messages=[]))
    _check("all 3 tokens yielded", tokens == ["a", "b", "c"])


# ─── generation/bare_greeting ────────────────────────────────────────


def test_bare_greeting_de_canonical():
    print(f"\n{_BOLD}[generation/T3]{_RESET} DE canonical greetings detected")
    for msg in ["hallo", "Hallo!", "servus", "moin", "ahoi (:"]:
        r = detect_bare_greeting(msg)
        _check(f"'{msg}' → bare-greeting", r is not None and r.lang == "de",
               f"got: {r}")


def test_bare_greeting_en_canonical():
    print(f"\n{_BOLD}[generation/T4]{_RESET} EN-unique canonical greetings detected as EN")
    # Use EN-unique greetings (hi/hey overlap with DE → DE-first wins per
    # operator-DACH-default; documented in bare_greeting.py)
    for msg in ["hello", "Howdy", "Good morning"]:
        r = detect_bare_greeting(msg)
        _check(f"'{msg}' → bare-greeting (en)", r is not None and r.lang == "en",
               f"got: {r}")


def test_bare_greeting_non_bare_rejected():
    print(f"\n{_BOLD}[generation/T5]{_RESET} non-bare messages NOT matched")
    for msg in ["ahoi, ich brauche hilfe", "hallo wie geht's", "hi there what's up"]:
        _check(f"'{msg[:30]}…' rejected", detect_bare_greeting(msg) is None)


def test_bare_greeting_empty_rejected():
    print(f"\n{_BOLD}[generation/T6]{_RESET} empty input handled gracefully")
    _check("empty → None", detect_bare_greeting("") is None)
    _check("whitespace-only → None", detect_bare_greeting("   ") is None)
    _check("emoticon-only → None", detect_bare_greeting("(:") is None)


def test_bare_greeting_result_renders():
    print(f"\n{_BOLD}[generation/T7]{_RESET} BareGreetingResult renders response text")
    r = detect_bare_greeting("hallo")
    _check("as_response_text non-empty", bool(r.as_response_text()))
    _check("mirror included", "Hallo" in r.as_response_text())
    _check("follow_up included", "?" in r.as_response_text())


def test_is_bare_greeting_convenience():
    print(f"\n{_BOLD}[generation/T8]{_RESET} is_bare_greeting convenience returns bool")
    _check("'hallo' True", is_bare_greeting("hallo") is True)
    _check("non-greeting False", is_bare_greeting("Was ist die Hauptstadt?") is False)


# ─── generation/style_mirror ─────────────────────────────────────────


def test_style_mirror_no_adapter_skips():
    print(f"\n{_BOLD}[generation/T9]{_RESET} apply_style_mirror w/o adapter → skip+reason")
    register_style_mirror(None)
    r = apply_style_mirror("test message")
    _check("applied = False", r.applied is False)
    _check("skip_reason populated", bool(r.skip_reason))


def test_style_mirror_adapter_applied():
    print(f"\n{_BOLD}[generation/T10]{_RESET} adapter returning dict → applied")
    register_style_mirror(lambda msg, hist: {"role": "system", "content": "mirror",
                                              "_register": "academic"})
    r = apply_style_mirror("test")
    _check("applied = True", r.applied is True)
    _check("system_message populated", r.system_message is not None)
    _check("register = academic", r.register == "academic")
    register_style_mirror(None)  # reset


def test_style_mirror_adapter_none_skipped():
    print(f"\n{_BOLD}[generation/T11]{_RESET} adapter returning None → skipped")
    register_style_mirror(lambda msg, hist: None)
    r = apply_style_mirror("test")
    _check("applied = False", r.applied is False)
    _check("skip_reason mentions adapter chose", "adapter" in (r.skip_reason or ""))
    register_style_mirror(None)


def test_style_mirror_adapter_exception_caught():
    print(f"\n{_BOLD}[generation/T12]{_RESET} adapter exception → captured in skip_reason")
    register_style_mirror(lambda msg, hist: 1/0)
    r = apply_style_mirror("test")
    _check("applied = False", r.applied is False)
    _check("skip_reason mentions raised", "raised" in (r.skip_reason or ""))
    register_style_mirror(None)


# ─── Runner ────────────────────────────────────────────────────────────


def main() -> int:
    print(f"{_BOLD}sse/ + generation/ — closing R2.1 14/14 · falsifiable{_RESET}")
    print("=" * 75)

    test_events_registry_populated()
    test_events_unknown_returns_false()
    test_serialize_event_shape()
    test_serialize_event_unknown_type_raises()
    test_serialize_event_skip_check_bypass()
    test_emitter_begin_send_end()
    test_emitter_unknown_type_recorded_as_error()
    test_emitter_send_unchecked()
    test_emitter_send_before_begin_silent()
    test_stream_respects_max_tokens()
    test_stream_no_cap_passes_all()
    test_bare_greeting_de_canonical()
    test_bare_greeting_en_canonical()
    test_bare_greeting_non_bare_rejected()
    test_bare_greeting_empty_rejected()
    test_bare_greeting_result_renders()
    test_is_bare_greeting_convenience()
    test_style_mirror_no_adapter_skips()
    test_style_mirror_adapter_applied()
    test_style_mirror_adapter_none_skipped()
    test_style_mirror_adapter_exception_caught()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}sse + generation result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
