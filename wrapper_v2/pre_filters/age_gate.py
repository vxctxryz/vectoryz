"""N10 — FSK / age-gate L3 stub.

Per [[age_layer_fsk_l3_compliance_freischalten]] (operator 2026-05-19):

    "L3 freischalten-if-eligible (age-verification gate). Initial
     implementation: user-self-declaration 'are you over 18?' but
     operator-acknowledges 'is weak.' Future implementation: AVS-class
     age-verification-service."

Three-layer compliance-stack:
  L1 HAMMERANTWORT  — truth-delivery primary (always runs first)
  L2 COMPLIANCE-MASK — jurisdiction-mask per IP (see sysmsg/compliance_mask.py)
  L3 AGE-GATE       — this module (freischalten or gate-out)

CRITICAL ordering: don't pre-gate-on-age before delivering truth +
applying jurisdiction-mask; NOT all content needs age-gate (only FSK-16
/ FSK-18-equivalent content-classes). Even when age-gated, L1+L2
happen first; L3 is freischalten-or-gate-out-of-restricted-class only.

FSK = Freiwillige Selbstkontrolle der Filmwirtschaft. Levels:
  FSK 0 / 6 / 12 / 16 / 18.

For v2 first-base: L1+L2 cover the build-target. L3 is THIS stub —
self-declaration only. Future: AVS integration (e.g. Schufa-Ident,
Verimi, German Personalausweis Online-Funktion).

Doctrine anchors:
  - [[age_layer_fsk_l3_compliance_freischalten]] — kernel
  - [[compliance_mask_jurisdiction_aware_ip_based]] — L2 sibling
  - [[death_penalty_void]] — gate-out is reversible (user can re-attempt with declared-age)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ─── FSK levels ────────────────────────────────────────────────────────


FSK_0 = 0     # no restriction
FSK_6 = 6     # ohne Altersbeschränkung mit Hinweis
FSK_12 = 12   # ab 12 Jahren
FSK_16 = 16   # ab 16 Jahren
FSK_18 = 18   # ab 18 Jahren (Erwachsene)

FSK_LEVELS = (FSK_0, FSK_6, FSK_12, FSK_16, FSK_18)


# ─── Content classification (which content needs L3) ───────────────────


# Content-class → minimum FSK level required to access.
# Only content classes >= FSK_12 actually trigger the gate; FSK_0/6
# pass through without gating.
CONTENT_FSK_REQUIRED: dict[str, int] = {
    "safe_general": FSK_0,
    "mild_violence_news": FSK_6,
    "violence_descriptive": FSK_12,
    "explicit_political_extremism_historical": FSK_16,
    "sexual_explicit": FSK_18,
    "violence_graphic": FSK_18,
    "drug_use_instructional": FSK_18,
    "weapons_acquisition_detail": FSK_18,
}


def required_fsk(content_class: str) -> int:
    """Minimum FSK level required to view this content-class."""
    return CONTENT_FSK_REQUIRED.get(content_class, FSK_0)


# ─── Result dataclass ──────────────────────────────────────────────────


@dataclass
class AgeGateResult:
    """Output of L3 age-gate check."""

    content_class: str
    required_fsk: int
    user_declared_age: Optional[int]
    granted: bool          # True if access OK (either content is FSK_0 or user-age >= required)
    needs_declaration: bool  # True if user must self-declare age first
    reason: str            # operator-readable

    def __bool__(self) -> bool:
        return self.granted


# ─── Main entry ────────────────────────────────────────────────────────


def check_age_gate(
    content_class: str,
    user_declared_age: Optional[int] = None,
) -> AgeGateResult:
    """L3 age-gate check.

    Returns AgeGateResult with:
      - granted=True if content is FSK_0 OR user-age >= required_fsk
      - needs_declaration=True if content requires age-gate AND user
        has not yet self-declared

    The caller (typically wrapper_cc input-stage) uses needs_declaration
    to prompt the user with 'Bist du über X Jahre alt?'-style question
    BEFORE delivering content of that class.
    """
    req = required_fsk(content_class)

    if req == FSK_0:
        return AgeGateResult(
            content_class=content_class,
            required_fsk=FSK_0,
            user_declared_age=user_declared_age,
            granted=True,
            needs_declaration=False,
            reason="content is FSK_0 (no age restriction)",
        )

    if user_declared_age is None:
        return AgeGateResult(
            content_class=content_class,
            required_fsk=req,
            user_declared_age=None,
            granted=False,
            needs_declaration=True,
            reason=f"content requires FSK_{req}; user has not declared age",
        )

    if user_declared_age >= req:
        return AgeGateResult(
            content_class=content_class,
            required_fsk=req,
            user_declared_age=user_declared_age,
            granted=True,
            needs_declaration=False,
            reason=f"user-age {user_declared_age} >= required FSK_{req}",
        )

    return AgeGateResult(
        content_class=content_class,
        required_fsk=req,
        user_declared_age=user_declared_age,
        granted=False,
        needs_declaration=False,
        reason=f"user-age {user_declared_age} < required FSK_{req}",
    )


def build_self_declaration_prompt(required_fsk_level: int, lang: str = "de") -> str:
    """Return the prompt-text the UI shows for user-self-declaration."""
    if lang == "de":
        return f"Dieser Inhalt ist ab {required_fsk_level} Jahren freigegeben. Bist du mindestens {required_fsk_level} Jahre alt?"
    return f"This content requires age {required_fsk_level}+. Are you at least {required_fsk_level} years old?"


__all__ = [
    "FSK_0", "FSK_6", "FSK_12", "FSK_16", "FSK_18", "FSK_LEVELS",
    "CONTENT_FSK_REQUIRED",
    "AgeGateResult",
    "required_fsk",
    "check_age_gate",
    "build_self_declaration_prompt",
]
