"""entry/meta — meta-route handlers (D1.a god-class split scaffold).

Thin route-handlers for non-chat-pipeline endpoints. Per R2 §4.1.

Routes covered (per entry/routes.py):
  GET /api/health     → health
  GET /api/engines    → engines
  GET /api/branchmap  → branchmap
  GET /api/version    → version

For D1.a scaffold: handlers return well-typed-dicts. Real adapters
(provide_engines / read_branchmap / etc.) are dependency-injected via
register_adapters() at startup. Production wraps these adapters around
the v1 wrapper_cc data-providers; tests inject mocks.

Doctrine anchors:
  - [[basetouch_verified_then_dollschon_overclock]] — thin-routes
    are the wohlgeformt structural invariant
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional


# ─── Adapter registry ─────────────────────────────────────────────────


# Each adapter has a clear shape; tests inject mocks, production wires
# to real wrapper_cc data-providers.
EnginesAdapter = Callable[[], list[dict]]
BranchmapAdapter = Callable[[], dict]
VersionAdapter = Callable[[], dict]
HealthAdapter = Callable[[], bool]


_ADAPTERS: dict[str, Optional[Callable]] = {
    "engines": None,
    "branchmap": None,
    "version": None,
    "health": None,
}


def register_adapters(**adapters: Callable) -> None:
    """Install adapters by name. Pass None to leave one untouched."""
    for k, v in adapters.items():
        if k in _ADAPTERS and v is not None:
            _ADAPTERS[k] = v


# ─── Result dataclass ─────────────────────────────────────────────────


@dataclass
class MetaResponse:
    """Standard meta-response: HTTP status + JSON body."""

    status: int
    body: Any


# ─── Route handlers ───────────────────────────────────────────────────


def health() -> MetaResponse:
    """GET /api/health — liveness probe."""
    adapter = _ADAPTERS.get("health")
    if adapter is None:
        return MetaResponse(status=200, body={"ok": True, "source": "stub"})
    try:
        ok = adapter()
        return MetaResponse(status=200 if ok else 503, body={"ok": bool(ok)})
    except Exception as exc:
        return MetaResponse(status=503, body={"ok": False, "error": repr(exc)})


def engines() -> MetaResponse:
    """GET /api/engines — list configured engines."""
    adapter = _ADAPTERS.get("engines")
    if adapter is None:
        return MetaResponse(status=200, body={"engines": [], "source": "stub"})
    try:
        eng_list = adapter()
        return MetaResponse(status=200, body={"engines": list(eng_list)})
    except Exception as exc:
        return MetaResponse(status=500, body={"error": repr(exc)})


def branchmap() -> MetaResponse:
    """GET /api/branchmap — live branchmap.json data."""
    adapter = _ADAPTERS.get("branchmap")
    if adapter is None:
        return MetaResponse(status=200, body={"branchmap": {}, "source": "stub"})
    try:
        data = adapter()
        return MetaResponse(status=200, body=data)
    except Exception as exc:
        return MetaResponse(status=500, body={"error": repr(exc)})


def version() -> MetaResponse:
    """GET /api/version — backend version + uptime."""
    adapter = _ADAPTERS.get("version")
    if adapter is None:
        return MetaResponse(
            status=200,
            body={
                "backend_started_at": "stub",
                "wrapper_cc_mtime": "stub",
                "uptime_seconds": 0,
            },
        )
    try:
        data = adapter()
        return MetaResponse(status=200, body=data)
    except Exception as exc:
        return MetaResponse(status=500, body={"error": repr(exc)})


__all__ = [
    "MetaResponse",
    "register_adapters",
    "health", "engines", "branchmap", "version",
]
