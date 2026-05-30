"""WEISS-override detector — M7 user-explicit force-fresh-search.

Per [[factfact_cache_re_labrador_timewindow]] (operator 2026-05-19):

    "when user says 'engine du depp etz such weil ich es WEISS!!!!!'
     dann suchen wir."

The canonical operator-vernacular for WEISS-override is "ich WEISS"
(capitalized + emphatic), often paired with "du depp" (operator-
register), "etz such" / "jetzt such" (Bavarian-imperative), and
multiple "!!!!!" markers.

Detection is intentionally PERMISSIVE: any user expressing "I KNOW
better than the cache, search again" should trigger the override.
False-positives are cheap (one extra search); false-negatives are
expensive (user-frustration, ignored explicit knowledge).

This module:
  1. Pattern-detects WEISS-class messages
  2. Returns a WeissOverride struct with confidence + matched markers
  3. Optionally extracts the target-claim if explicitly mentioned
  4. Caller (chat-app) calls cache.mark_weiss_invalidated() then triggers
     fresh-search bypassing cache

Doctrine anchors:
  - [[factfact_cache_re_labrador_timewindow]] — kernel
  - [[claude_chat_access_discipline]] — user-explicit-claim authorizes operation
    (parallel pattern: explicit user-statement supersedes cache discipline)
  - [[death_penalty_void]] — never silence operator's explicit knowledge
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ─── Patterns ──────────────────────────────────────────────────────────


# Operator-vernacular markers — DE + EN variants. Each match adds score.
# Threshold for trigger: score >= 2 (two distinct markers OR one strong).
_PATTERNS: list[tuple[str, int, str]] = [
    # Strong (single-marker-sufficient) — emphasis-capitalized WEISS variants
    (r"\bich\s+(?:es\s+)?WEISS\b", 3, "ich WEISS (CAPS)"),
    (r"\bI\s+KNOW\b", 3, "I KNOW (CAPS)"),
    (r"\bWEIS+\b", 3, "WEIS… (German-capitalized variant)"),

    # Medium — vernacular force-search markers
    (r"\bdu\s+depp\b", 2, "du depp (operator-register)"),
    (r"\betz\s+such\b", 2, "etz such (Bavarian imperative)"),
    (r"\bjetzt\s+such\b", 2, "jetzt such"),
    (r"\bsuch\s+(?:doch|halt|mal)\b", 2, "such doch/halt/mal"),
    (r"\bfresh\s+search\b", 2, "fresh search (EN)"),
    (r"\bforce[- ]?refresh\b", 2, "force refresh (EN)"),
    (r"\bbypass\s+(?:the\s+)?cache\b", 2, "bypass cache (EN)"),
    (r"\b(?:re)?check\s+(?:das|that|this|nochmal|again)\b", 1, "recheck"),

    # Weak (must combine with another marker) — emphasis/exasperation
    (r"!{3,}", 1, "!!! emphasis"),
    (r"\?{3,}", 1, "??? emphasis"),
    (r"\bweil\s+ich\b", 1, "weil ich (because-I)"),
    (r"\bbecause\s+I\b", 1, "because I (EN)"),
]

_TRIGGER_SCORE = 3


# ─── Result dataclass ──────────────────────────────────────────────────


@dataclass
class WeissOverride:
    """Detector output. truthy via `bool(result)` iff override fired."""

    triggered: bool = False
    score: int = 0
    matched_markers: list[str] = field(default_factory=list)
    target_claim: Optional[str] = None  # extracted if quoted in message

    def __bool__(self) -> bool:
        return self.triggered


# ─── Detector ──────────────────────────────────────────────────────────


def detect_weiss_override(user_message: str) -> WeissOverride:
    """Scan user-message for WEISS-override patterns.

    Returns WeissOverride(triggered=True, ...) if total score >= 3,
    else WeissOverride(triggered=False, score=N, matched_markers=[...]).
    Always returns an object (never None) so callers can inspect partial
    matches for debugging.
    """
    if not user_message:
        return WeissOverride()

    score = 0
    matched: list[str] = []
    for pat, weight, label in _PATTERNS:
        if re.search(pat, user_message):
            score += weight
            matched.append(label)

    target = _extract_quoted_claim(user_message) if score >= _TRIGGER_SCORE else None

    return WeissOverride(
        triggered=(score >= _TRIGGER_SCORE),
        score=score,
        matched_markers=matched,
        target_claim=target,
    )


def _extract_quoted_claim(message: str) -> Optional[str]:
    """Extract a target-claim if user quoted it (in 'single', \"double\", or „German" quotes).

    Returns the first quoted span (stripped, non-empty). None if no quote.
    """
    for pat in (r'"([^"]+)"', r"„([^\"]+)\"", r"„([^“]+)“", r"'([^']+)'"):
        m = re.search(pat, message)
        if m:
            text = m.group(1).strip()
            if text:
                return text
    return None


# ─── Convenience: detect-and-apply ────────────────────────────────────


def detect_and_invalidate(
    user_message: str,
    cache,
    *,
    fallback_claim: Optional[str] = None,
) -> tuple["WeissOverride", bool]:
    """If WEISS-override detected, call cache.mark_weiss_invalidated(target).

    target = WeissOverride.target_claim if quoted, else fallback_claim
    (caller can pass the last-assistant-claim-id if no quoted target).

    Returns (WeissOverride, applied: bool).
    """
    result = detect_weiss_override(user_message)
    if not result.triggered:
        return result, False
    target = result.target_claim or fallback_claim
    if target is None:
        return result, False
    applied = cache.mark_weiss_invalidated(target)
    return result, applied


__all__ = [
    "WeissOverride",
    "detect_weiss_override",
    "detect_and_invalidate",
]
