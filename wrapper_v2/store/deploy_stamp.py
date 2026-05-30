"""store/deploy_stamp — SSE deploy-stamp event source per R2 §4.10.

Per task #138 ('Deploy-stamp SSE event + UI rendering next to assistant-
timestamp') — the deploy-stamp is the backend's self-identifier that
gets attached to every SSE response stream so the UI can show 'was this
answer pre/post-deploy?' next to the assistant-timestamp.

Two read-points:
  - backend_started_at  — process-start timestamp (engine instance hash)
  - wrapper_cc_mtime    — file modification-time of running wrapper code

Both are read at first-call + cached for process-lifetime. The pair
acts as a coarse deploy-version-fingerprint without requiring a git-sha
lookup at request-time.

Doctrine: [[audit_open_door_doctrine]] — backend identifies itself
plainly with each response.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DeployStamp:
    """A backend deploy-fingerprint snapshot."""

    backend_started_at: str   # ISO-or-epoch string, set at process-start
    wrapper_mtime: str        # file mtime of wrapper code (proxy for deploy-version)
    uptime_seconds: int       # seconds since backend_started_at

    def as_event(self) -> dict:
        """Render as SSE event-dict (matches v1 /api/version response shape)."""
        return {
            "type": "deploy_stamp",
            "backend_started_at": self.backend_started_at,
            "wrapper_cc_mtime": self.wrapper_mtime,
            "uptime_seconds": self.uptime_seconds,
        }


# ─── Module-level cache ────────────────────────────────────────────────


_PROCESS_START_TS: Optional[float] = None
_WRAPPER_MTIME_STR: Optional[str] = None


def _ensure_init(
    wrapper_path: Optional[str] = None,
    now_ts: Optional[float] = None,
) -> None:
    """Set process-start + wrapper-mtime on first call. Idempotent.
    now_ts is used for first-init only (tests inject controlled clock)."""
    global _PROCESS_START_TS, _WRAPPER_MTIME_STR
    if _PROCESS_START_TS is None:
        _PROCESS_START_TS = now_ts if now_ts is not None else time.time()
    if _WRAPPER_MTIME_STR is None and wrapper_path is not None:
        try:
            mtime = os.path.getmtime(wrapper_path)
            _WRAPPER_MTIME_STR = time.strftime("%Y%m%d%H%M%S", time.gmtime(mtime))
        except OSError:
            _WRAPPER_MTIME_STR = "unknown"
    elif _WRAPPER_MTIME_STR is None:
        _WRAPPER_MTIME_STR = "unknown"


def compute_deploy_stamp(
    *,
    wrapper_path: Optional[str] = None,
    now_ts: Optional[float] = None,
) -> DeployStamp:
    """Return current DeployStamp.

    Args:
        wrapper_path: file-path to track for mtime (typically
                      /home/bsr/42/benchmark_cc/wrapper_cc.py); cached
                      after first lookup
        now_ts: clock override for tests; defaults to time.time().
                On first call, also seeds the process-start timestamp.
    """
    _ensure_init(wrapper_path, now_ts=now_ts)
    now = now_ts if now_ts is not None else time.time()
    uptime = int(max(0, now - (_PROCESS_START_TS or now)))
    started_str = time.strftime("%Y%m%d%H%M%S",
                                 time.gmtime(_PROCESS_START_TS or now))
    return DeployStamp(
        backend_started_at=started_str,
        wrapper_mtime=_WRAPPER_MTIME_STR or "unknown",
        uptime_seconds=uptime,
    )


def _reset_for_test() -> None:
    """Test-only: clear cached state to re-init from scratch."""
    global _PROCESS_START_TS, _WRAPPER_MTIME_STR
    _PROCESS_START_TS = None
    _WRAPPER_MTIME_STR = None


__all__ = [
    "DeployStamp",
    "compute_deploy_stamp",
]
