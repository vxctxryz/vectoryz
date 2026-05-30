"""generation/bare_greeting — fast-path bare-greeting detection per R2 §4.5.

Per [[interaction_model_quengel_to_coalign]] + v1 detect_bare_greeting
(wrapper_cc.py:1179). Minimal extraction: covers DE + EN canonical
patterns; full operator-curated multi-lingual catalog stays in v1 for
D1.b extraction.

A "bare" greeting is one where, after stripping emoticons/punctuation,
nothing remains but the greeting itself. "ahoi (:" matches; "ahoi,
ich brauche hilfe" does not.

For non-bare messages: return None (caller proceeds to full pipeline).
For bare messages: return (mirror_response, follow_up_offer, lang_code).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# ─── Catalogs (DE + EN minimal) ───────────────────────────────────────


# Each entry: (greeting_pattern_lowercase, mirror_response, follow_up_offer)
# Mirror = polite return (operator's reciprocal-mirror per
# [[1455xl_chassis_goal_driven_funnel]]).
# Follow-up = "wie kann ich helfen?"-style invitation.
_GREETINGS_DE: list[tuple[str, str, str]] = [
    ("hallo",  "Hallo!",       "Womit kann ich helfen?"),
    ("hi",     "Hi!",          "Was kann ich für dich tun?"),
    ("hey",    "Hey!",         "Was kann ich für dich tun?"),
    ("servus", "Servus!",      "Wie kann ich helfen?"),
    ("ahoi",   "Ahoi!",        "Was darf's sein?"),
    ("moin",   "Moin!",        "Was kann ich für dich tun?"),
    ("grüß gott", "Grüß Gott!", "Was darf's sein?"),
    ("guten tag", "Guten Tag!", "Wie kann ich helfen?"),
    ("guten morgen", "Guten Morgen!", "Wie kann ich helfen?"),
    ("guten abend", "Guten Abend!", "Wie kann ich helfen?"),
]

_GREETINGS_EN: list[tuple[str, str, str]] = [
    ("hello",   "Hello!",   "How can I help?"),
    ("hi",      "Hi!",      "What can I help you with?"),
    ("hey",     "Hey!",     "What can I help you with?"),
    ("yo",      "Yo!",      "What's up?"),
    ("howdy",   "Howdy!",   "What can I do for you?"),
    ("greetings", "Greetings!", "How can I help?"),
    ("good morning", "Good morning!", "How can I help?"),
    ("good afternoon", "Good afternoon!", "How can I help?"),
    ("good evening", "Good evening!", "How can I help?"),
]


# Strip emoticons + punctuation but keep letters + spaces.
# Order matters: longer emoticons first so they don't get partially-stripped.
_EMOTICON_PATS = [
    r"\(\s*[:;)]\s*\)?", r"[:;)8]-?[)\(D/]", r"<3", r"\^_\^", r"\^\^",
    r"[!?.,;:]+",        # standalone punctuation runs
    r"\s+",
]
_GREETING_STRIP_RX = re.compile("|".join(_EMOTICON_PATS))


@dataclass
class BareGreetingResult:
    """Outcome of bare-greeting detection."""

    matched_pattern: str
    mirror_response: str
    follow_up: str
    lang: str  # "de" or "en"

    def as_response_text(self) -> str:
        return f"{self.mirror_response} {self.follow_up}"


def _normalize(message: str) -> str:
    """Strip emoticons + punctuation + extra whitespace; lowercase."""
    cleaned = _GREETING_STRIP_RX.sub(" ", message).strip().lower()
    return re.sub(r"\s+", " ", cleaned)


def detect_bare_greeting(message: str) -> Optional[BareGreetingResult]:
    """If message is a bare greeting → return result; else None.

    Checks DE patterns first (operator-DACH-default), then EN.
    Returns None if message has any content beyond a greeting.
    """
    if not message or not message.strip():
        return None
    normalized = _normalize(message)
    if not normalized:
        return None

    # DE first (operator-default)
    for pattern, mirror, follow_up in _GREETINGS_DE:
        if normalized == pattern:
            return BareGreetingResult(pattern, mirror, follow_up, "de")
    # then EN
    for pattern, mirror, follow_up in _GREETINGS_EN:
        if normalized == pattern:
            return BareGreetingResult(pattern, mirror, follow_up, "en")
    return None


def is_bare_greeting(message: str) -> bool:
    """Convenience: True iff detect_bare_greeting returns non-None."""
    return detect_bare_greeting(message) is not None


__all__ = [
    "BareGreetingResult",
    "detect_bare_greeting",
    "is_bare_greeting",
]
