"""generation/style_mirror — auto-style-mirror adapter shell per R2 §4.5.

Per [[1455xl_chassis_goal_driven_funnel]] (reziprok prompt-to-result)
+ [[vulnerable_user_protection_reziprok_ceiling]] (mirror has a ceiling
on certain emotional registers — never mirror despair or self-harm
register, redirect-instead).

This is the SHELL: adapter-injection that delegates to v1
auto_style_mirror_system_msg (wrapper_cc.py:1507) for now. D1.b will
extract the actual register-detection + style-template logic.

Tests can inject a controlled mock-adapter to verify the wiring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


# Adapter signature: takes (user_message, conversation_history) →
# style-mirror system-message-dict (or None to skip mirror).
StyleMirrorAdapter = Callable[[str, list], Optional[dict]]


@dataclass
class StyleMirrorResult:
    """Outcome of style-mirror application."""

    applied: bool
    system_message: Optional[dict] = None
    register: Optional[str] = None  # e.g. "academic" / "casual" / "vulnerable_redirect"
    skip_reason: Optional[str] = None
    notes: list = field(default_factory=list)


_ADAPTER: Optional[StyleMirrorAdapter] = None


def register_style_mirror(adapter: Optional[StyleMirrorAdapter]) -> None:
    """Install adapter (or pass None to clear). Production wires to v1
    auto_style_mirror_system_msg; tests inject mocks."""
    global _ADAPTER
    _ADAPTER = adapter


def apply_style_mirror(
    user_message: str,
    conversation_history: Optional[list] = None,
) -> StyleMirrorResult:
    """Run style-mirror. Returns StyleMirrorResult with applied flag.

    If no adapter registered → applied=False with skip_reason.
    Per [[vulnerable_user_protection_reziprok_ceiling]]: the adapter
    is responsible for detecting vulnerable-register and SUPPRESSING
    mirror in those cases (returning None or a redirect-template).
    """
    if _ADAPTER is None:
        return StyleMirrorResult(
            applied=False,
            skip_reason="no style-mirror adapter registered",
        )
    try:
        sys_msg = _ADAPTER(user_message, conversation_history or [])
    except Exception as exc:
        return StyleMirrorResult(
            applied=False,
            skip_reason=f"adapter raised: {exc!r}",
        )
    if sys_msg is None:
        return StyleMirrorResult(
            applied=False,
            skip_reason="adapter chose to skip (e.g. vulnerable-register)",
        )
    return StyleMirrorResult(
        applied=True,
        system_message=sys_msg,
        register=sys_msg.get("_register") if isinstance(sys_msg, dict) else None,
    )


__all__ = [
    "StyleMirrorAdapter",
    "StyleMirrorResult",
    "register_style_mirror",
    "apply_style_mirror",
]
