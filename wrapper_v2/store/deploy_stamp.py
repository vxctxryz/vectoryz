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
    code_signature: str = "unknown"   # short hash identifying code version

    def as_event(self) -> dict:
        """Render as SSE event-dict (matches v1 /api/version response shape)."""
        return {
            "type": "deploy_stamp",
            "backend_started_at": self.backend_started_at,
            "wrapper_cc_mtime": self.wrapper_mtime,
            "uptime_seconds": self.uptime_seconds,
            "code_signature": self.code_signature,
        }


# ─── Module-level cache ────────────────────────────────────────────────


_PROCESS_START_TS: Optional[float] = None
_WRAPPER_MTIME_STR: Optional[str] = None
_CODE_SIGNATURE: Optional[str] = None


# Files whose content/mtime determine the "running code version" fingerprint.
# Added/removed here = different signature, so operator can tell which fix-stack
# is live just from the deploy-stamp.
_SIGNATURE_FILES_REL = [
    "pipeline/factampel_emit.py",
    "pipeline/retry_similarity.py",
    "pipeline/retry_corrective_surgical.py",
    "pipeline/output_sanitize.py",
    "pipeline/witness_routing.py",
]


def _read_version_file(wrapper_v2_root: Optional[Path]) -> Optional[str]:
    """Read a VERSION file at <wrapper_v2_root>/VERSION (deployer writes
    it with the git-commit-sha). Returns up to first 12 chars, or None
    if missing.

    The VERSION file is the precise signature — written explicitly at
    deploy time. The runtime-fingerprint below is the fallback when no
    VERSION file is present.
    """
    if wrapper_v2_root is None:
        return None
    try:
        version_path = wrapper_v2_root / "VERSION"
        if version_path.exists():
            content = version_path.read_text().strip()
            if content:
                return content[:12]
    except OSError:
        pass
    return None


def _compute_runtime_fingerprint(wrapper_v2_root: Optional[Path]) -> str:
    """Fallback signature when VERSION file missing.

    Hashes the (path, mtime, size) tuple for each key file in
    _SIGNATURE_FILES_REL. Same file-set with same mtimes/sizes → same
    fingerprint. Different deploy → different fingerprint.

    Returns 7-char hex (matches git-short-sha style for visual consistency).
    """
    import hashlib

    if wrapper_v2_root is None:
        return "unknown"

    sig_input_parts = []
    for rel in _SIGNATURE_FILES_REL:
        p = wrapper_v2_root / rel
        try:
            stat = p.stat()
            sig_input_parts.append(f"{rel}:{int(stat.st_mtime)}:{stat.st_size}")
        except OSError:
            sig_input_parts.append(f"{rel}:missing")
    sig_input = ";".join(sig_input_parts)
    return hashlib.sha256(sig_input.encode("utf-8")).hexdigest()[:7]


def _compute_code_signature(wrapper_path: Optional[str] = None) -> str:
    """Operator-written VERSION file → first 12 chars.
    Otherwise → 7-char runtime-fingerprint prefixed 'rt:' to distinguish.
    """
    wrapper_v2_root = None
    if wrapper_path:
        # Find wrapper_v2 root by walking up from the passed wrapper path
        wrapper_v2_root = Path(wrapper_path).parent
        # Try common heuristic: parent contains 'wrapper_v2' subdir
        cand = wrapper_v2_root / "wrapper_v2"
        if cand.exists() and cand.is_dir():
            wrapper_v2_root = cand
        elif "wrapper_v2" in str(wrapper_v2_root):
            # we may already be inside wrapper_v2/
            parts = wrapper_v2_root.parts
            if "wrapper_v2" in parts:
                idx = parts.index("wrapper_v2")
                wrapper_v2_root = Path(*parts[: idx + 1])

    if wrapper_v2_root is None or not wrapper_v2_root.exists():
        # Last resort: use this module's parent
        wrapper_v2_root = Path(__file__).parent.parent

    v = _read_version_file(wrapper_v2_root)
    if v:
        return v
    return "rt:" + _compute_runtime_fingerprint(wrapper_v2_root)


def _ensure_init(
    wrapper_path: Optional[str] = None,
    now_ts: Optional[float] = None,
) -> None:
    """Set process-start + wrapper-mtime + code-signature on first call.
    Idempotent. now_ts is used for first-init only."""
    global _PROCESS_START_TS, _WRAPPER_MTIME_STR, _CODE_SIGNATURE
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
    if _CODE_SIGNATURE is None:
        try:
            _CODE_SIGNATURE = _compute_code_signature(wrapper_path)
        except Exception:
            _CODE_SIGNATURE = "unknown"


def compute_deploy_stamp(
    *,
    wrapper_path: Optional[str] = None,
    now_ts: Optional[float] = None,
) -> DeployStamp:
    """Return current DeployStamp.

    Args:
        wrapper_path: file-path to track for mtime (typically
                      <repo-root>/benchmark_cc/wrapper_cc.py); cached
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
        code_signature=_CODE_SIGNATURE or "unknown",
    )


def _reset_for_test() -> None:
    """Test-only: clear cached state to re-init from scratch."""
    global _PROCESS_START_TS, _WRAPPER_MTIME_STR, _CODE_SIGNATURE
    _PROCESS_START_TS = None
    _WRAPPER_MTIME_STR = None
    _CODE_SIGNATURE = None


__all__ = [
    "DeployStamp",
    "compute_deploy_stamp",
]
