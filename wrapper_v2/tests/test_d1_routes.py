"""D1.a falsifiable-benchmark — Handler god-class split: routes-table + handlers.

Per task #126 (M9 R2.7b D1) + R2 §4.1.

Verifies:
  - routes-table covers all 9 v1 routes (do_GET + do_POST)
  - path-pattern matching works (incl. {chat_id} parameter capture)
  - each handler is callable + returns proper-shape response
  - validation rejects missing message / chat_id
  - adapter-injection works (mocks replace defaults)
  - SSE-stream-responses yield iterable event-dicts

D1.b will extract the actual pipeline-execution into
wrapper_v2/pipeline/turn_executor.py; this test verifies the
SCAFFOLD is shape-correct without requiring full pipeline-impl.

Doctrine anchors: [[basetouch_verified_then_dollschon_overclock]],
[[gx44_truth_local_haystack_doctrine]], [[death_penalty_void]].

Run via: python3 -m wrapper_v2.tests.test_d1_routes  (stdlib-only)
Exit-code 0 = all-pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.entry import routes, chat, meta


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


# ─── Route-table tests ─────────────────────────────────────────────────


def test_route_table_completeness():
    print(f"\n{_BOLD}[D1.a/T1]{_RESET} route-table covers all v1 routes")
    paths = {(r.method, r.pattern) for r in routes.ROUTES}
    expected = {
        ("GET", "/api/health"),
        ("GET", "/api/engines"),
        ("GET", "/api/branchmap"),
        ("GET", "/api/version"),
        ("GET", "/api/chat/{chat_id}"),
        ("POST", "/api/chat/new"),
        ("POST", "/api/chat/{chat_id}/turn"),
        ("POST", "/api/chat/{chat_id}/persist-assistant"),
        ("POST", "/api/chat/{chat_id}/rollback"),
    }
    missing = expected - paths
    _check(f"all {len(expected)} v1 routes present", not missing,
           f"missing: {missing}")
    _check("no extra routes (table matches v1)", not (paths - expected),
           f"extra: {paths - expected}")


def test_match_route_static():
    print(f"\n{_BOLD}[D1.a/T2]{_RESET} match_route resolves static paths")
    m = routes.match_route("GET", "/api/version")
    _check("GET /api/version matched", m is not None and m.spec.handler_fn == "version")
    m = routes.match_route("GET", "/api/health")
    _check("GET /api/health matched", m is not None and m.spec.handler_fn == "health")
    m = routes.match_route("POST", "/api/chat/new")
    _check("POST /api/chat/new matched", m is not None and m.spec.handler_fn == "new_chat")


def test_match_route_parameterized():
    print(f"\n{_BOLD}[D1.a/T3]{_RESET} match_route captures {{chat_id}} parameter")
    m = routes.match_route("GET", "/api/chat/abc-123")
    _check("path matched", m is not None)
    _check("chat_id captured", m.path_params.get("chat_id") == "abc-123")
    _check("handler_fn = get_chat", m.spec.handler_fn == "get_chat")

    m = routes.match_route("POST", "/api/chat/xyz-456/turn")
    _check("turn-pattern matched", m is not None)
    _check("turn chat_id captured", m.path_params.get("chat_id") == "xyz-456")
    _check("handler_fn = turn", m.spec.handler_fn == "turn")


def test_match_route_method_discrimination():
    print(f"\n{_BOLD}[D1.a/T4]{_RESET} match_route discriminates by method")
    # POST /api/chat/new → new_chat handler
    pm = routes.match_route("POST", "/api/chat/new")
    _check("POST /api/chat/new → new_chat",
           pm is not None and pm.spec.handler_fn == "new_chat")
    # GET /api/chat/new gets matched as get_chat with chat_id="new"
    # (the /api/chat/{chat_id} pattern accepts "new" as a literal id).
    # That's a real-but-narrow semantic edge — get_chat handler can
    # 404 it via adapter. This test documents the behavior, not a bug.
    gm = routes.match_route("GET", "/api/chat/new")
    _check("GET /api/chat/new → get_chat (with chat_id='new')",
           gm is not None and gm.spec.handler_fn == "get_chat"
           and gm.path_params.get("chat_id") == "new")


def test_match_route_unknown_returns_none():
    print(f"\n{_BOLD}[D1.a/T5]{_RESET} match_route returns None for unknown paths")
    _check("/nope returns None", routes.match_route("GET", "/nope") is None)
    _check("/api/nonexistent returns None", routes.match_route("GET", "/api/nonexistent") is None)
    _check("wrong-shape chat path",
           routes.match_route("POST", "/api/chat/") is None)


def test_list_routes_filter():
    print(f"\n{_BOLD}[D1.a/T6]{_RESET} list_routes filters by method")
    all_routes = routes.list_routes()
    gets = routes.list_routes("GET")
    posts = routes.list_routes("POST")
    _check("all routes >= 9", len(all_routes) >= 9)
    _check("GET subset >= 5", len(gets) >= 5)
    _check("POST subset >= 4", len(posts) >= 4)
    _check("GET + POST = all", len(gets) + len(posts) == len(all_routes))


# ─── meta handlers ─────────────────────────────────────────────────────


def test_meta_health_default_stub():
    print(f"\n{_BOLD}[D1.a/T7]{_RESET} meta.health default-stub returns 200")
    resp = meta.health()
    _check("status 200", resp.status == 200)
    _check("body.ok = True", resp.body.get("ok") is True)


def test_meta_engines_default_stub():
    print(f"\n{_BOLD}[D1.a/T8]{_RESET} meta.engines default-stub returns []")
    resp = meta.engines()
    _check("status 200", resp.status == 200)
    _check("body has engines key", "engines" in resp.body)


def test_meta_with_adapter():
    print(f"\n{_BOLD}[D1.a/T9]{_RESET} meta-adapter injection works")
    meta.register_adapters(version=lambda: {"backend_started_at": "test", "uptime_seconds": 42})
    resp = meta.version()
    _check("status 200", resp.status == 200)
    _check("uptime = 42 from adapter", resp.body.get("uptime_seconds") == 42)
    # Reset
    meta._ADAPTERS["version"] = None


# ─── chat handlers ─────────────────────────────────────────────────────


def test_chat_get_chat_requires_id():
    print(f"\n{_BOLD}[D1.a/T10]{_RESET} get_chat returns 400 when chat_id empty")
    resp = chat.get_chat("")
    _check("status 400", resp.status == 400)


def test_chat_get_chat_stub():
    print(f"\n{_BOLD}[D1.a/T11]{_RESET} get_chat default-stub returns shape-correct")
    resp = chat.get_chat("test-chat-id")
    _check("status 200", resp.status == 200)
    _check("body.chat_id matches", resp.body.get("chat_id") == "test-chat-id")


def test_chat_get_chat_with_adapter_404():
    print(f"\n{_BOLD}[D1.a/T12]{_RESET} get_chat with adapter returning None → 404")
    chat.register_adapters(get_chat=lambda cid: None)
    resp = chat.get_chat("missing-id")
    _check("status 404", resp.status == 404)
    chat._ADAPTERS["get_chat"] = None


def test_chat_new_chat_requires_message():
    print(f"\n{_BOLD}[D1.a/T13]{_RESET} new_chat requires message in body")
    resp = chat.new_chat({})
    _check("status 400 on empty body", resp.status == 400)
    events = list(resp.events)
    _check("error event in stream", any(e.get("type") == "error" for e in events))


def test_chat_new_chat_stub_stream():
    print(f"\n{_BOLD}[D1.a/T14]{_RESET} new_chat default-stub yields shape-correct events")
    resp = chat.new_chat({"message": "Hello"})
    _check("status 200", resp.status == 200)
    events = list(resp.events)
    types = [e.get("type") for e in events]
    _check("contains chat_id event", "chat_id" in types)
    _check("contains done event", "done" in types)


def test_chat_turn_with_adapter_stream():
    print(f"\n{_BOLD}[D1.a/T15]{_RESET} turn with adapter streams adapter-events")
    def mock_turn_stream(chat_id, body):
        yield {"type": "chat_id", "chat_id": chat_id}
        yield {"type": "token", "text": "Hello "}
        yield {"type": "token", "text": "world"}
        yield {"type": "done"}
    chat.register_adapters(turn_stream=mock_turn_stream)
    resp = chat.turn("test-id", {"message": "ping"})
    _check("status 200", resp.status == 200)
    events = list(resp.events)
    _check("4 events streamed", len(events) == 4)
    _check("token events present", sum(1 for e in events if e.get("type") == "token") == 2)
    chat._ADAPTERS["turn_stream"] = None


def test_chat_rollback_stub():
    print(f"\n{_BOLD}[D1.a/T16]{_RESET} rollback default-stub returns shape-correct")
    resp = chat.rollback("test-id", {})
    _check("status 200", resp.status == 200)
    _check("body.rolled_back = True", resp.body.get("rolled_back") is True)


def test_chat_persist_assistant_stub():
    print(f"\n{_BOLD}[D1.a/T17]{_RESET} persist_assistant default-stub returns shape-correct")
    resp = chat.persist_assistant("test-id", {"ciphertext_b64": "..."})
    _check("status 200", resp.status == 200)
    _check("body.persisted = True", resp.body.get("persisted") is True)


# ─── Runner ────────────────────────────────────────────────────────────


def main() -> int:
    print(f"{_BOLD}D1.a — Handler god-class split: routes + handlers · falsifiable benchmark{_RESET}")
    print("=" * 75)

    test_route_table_completeness()
    test_match_route_static()
    test_match_route_parameterized()
    test_match_route_method_discrimination()
    test_match_route_unknown_returns_none()
    test_list_routes_filter()
    test_meta_health_default_stub()
    test_meta_engines_default_stub()
    test_meta_with_adapter()
    test_chat_get_chat_requires_id()
    test_chat_get_chat_stub()
    test_chat_get_chat_with_adapter_404()
    test_chat_new_chat_requires_message()
    test_chat_new_chat_stub_stream()
    test_chat_turn_with_adapter_stream()
    test_chat_rollback_stub()
    test_chat_persist_assistant_stub()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}D1.a result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
