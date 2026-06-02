"""pipeline/witness_routing — classify claims to right verification path.

Phase-2 fix #3 (2026-06-02): the web-based tribunal (claude + google_today
+ google_1998 + wiki_graph) systematically mis-grades certain claim
classes because its witnesses lack the right kind of evidence:

  MATH claims:
    "Wir addieren 80 + 120 = 200 km/h" → witnesses don't have web-search
    evidence FOR this arithmetic, so absence-of-evidence gets aggregated
    to quasinonfact. Production Q5: "Die Distanz beträgt 500 km" →
    🟠 quasinonfact (it's the USER's input + correct math).

  USER_INPUT claims (parrot-back):
    Bot restates the user's input ("Sie sind 500 km auseinander") —
    tribunal can't verify "did the user say this" via web search.

  AUTHORITATIVE-citation claims:
    "§201 PU sagt X" — needs specific text-source verification, not
    consensus-search. Generic witnesses give moderate confidence at best.

  GENERAL claims:
    Normal factual statements ("Berlin ist Hauptstadt Deutschlands") —
    web-tribunal works fine. Default.

This module classifies claims into WitnessClass; caller (factampel_emit)
uses the class to decide which verification path to take. Step #3.1 ships
MATH detection only — other classes added incrementally.

Doctrine:
  - [[hammerantwort]] — substance over false-refutation
  - [[ehrlich_stumm_doctrine]] — don't mis-grade what witnesses can't verify

Public API:
  WitnessClass (enum)
  classify_claim_class(claim_text) -> WitnessClass
"""

from __future__ import annotations

import enum
import re


class WitnessClass(enum.Enum):
    """How a claim should be verified."""

    MATH = "math"                   # arithmetic / units — deterministic
    USER_INPUT = "user_input"       # parroting user input — not verifiable via web
    AUTHORITATIVE = "authoritative" # specific text/citation — needs targeted lookup
    GENERAL = "general"             # default — existing web-tribunal works


# ─── USER_INPUT detection ───────────────────────────────────────────────


# Default thresholds. Overridable via env if needed.
USER_INPUT_RATIO_THRESHOLD = 0.6   # ≥60% of claim chars come from user_query
USER_INPUT_MIN_MATCH_LEN = 8       # ignore matching substrings shorter than this
                                   # (avoids "die", "der", "und" triggering)


def _normalize_for_overlap(text: str) -> str:
    """Lowercase + collapse whitespace; preserves chars for substring-match."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.lower()).strip()


def user_input_echo_ratio(claim_text: str, user_query: str) -> float:
    """Fraction of claim_text whose content comes from user_query.

    Uses difflib.SequenceMatcher to find matching blocks ≥ USER_INPUT_MIN_MATCH_LEN
    chars and sums their lengths. Ratio = matched / len(claim).

    Returns 0.0 if either input is empty.

    Example:
      claim = "Die Züge sind 500 km auseinander."
      user  = "Sie sind 500 km auseinander und fahren aufeinander zu."
      → matches " sind 500 km auseinander" (~25 chars) of 33-char claim → ~0.76
    """
    from difflib import SequenceMatcher

    c = _normalize_for_overlap(claim_text)
    u = _normalize_for_overlap(user_query)
    if not c or not u:
        return 0.0

    sm = SequenceMatcher(None, c, u, autojunk=False)
    blocks = sm.get_matching_blocks()
    matched = sum(b.size for b in blocks if b.size >= USER_INPUT_MIN_MATCH_LEN)
    return matched / max(1, len(c))


def _is_user_input_echo(claim_text: str, user_query: str) -> bool:
    """True if claim_text is largely a parrot-back of user_query."""
    if not user_query:
        return False
    return user_input_echo_ratio(claim_text, user_query) >= USER_INPUT_RATIO_THRESHOLD


# ─── MATH detection ────────────────────────────────────────────────────


# Strong markers (any one match → MATH)
_MATH_STRONG = [
    # Explicit equation with =
    re.compile(r"\b\d+(?:[.,]\d+)?\s*[+\-*/×÷]\s*\d+(?:[.,]\d+)?\s*=\s*\d+(?:[.,]\d+)?"),
    # Division with ÷
    re.compile(r"\d+(?:[.,]\d+)?\s*÷\s*\d+(?:[.,]\d+)?\s*=\s*\d+(?:[.,]\d+)?"),
    # Standalone division-with-result "500 km / 200 km/h = 2.5 Stunden"
    re.compile(r"\d+(?:[.,]\d+)?\s*[^/]?/\s*\d+(?:[.,]\d+)?\s*[^/]?\s*=\s*\d+(?:[.,]\d+)?"),
    # Speed units
    re.compile(r"\b\d+(?:[.,]\d+)?\s*km/h\b"),
    re.compile(r"\b\d+(?:[.,]\d+)?\s*m/s\b"),
    # Relativ-/Gesamt-geschwindigkeit terms (calculation-specific)
    re.compile(r"\bRelativ(?:e\s+)?geschwindigkeit\b", re.IGNORECASE),
    re.compile(r"\bGesamt(?:geschwindigkeit|distanz|strecke)\b", re.IGNORECASE),
    # Explicit math-only calc verbs paired with numbers (tightened 2026-06-02:
    # dropped 'beträgt|ergibt|ergeben' — too generic, fired false-positive on
    # "Mehrwertsteuer beträgt 19%". Kept only verbs that imply ACTIVE calculation.)
    re.compile(
        r"\b(?:addieren|subtrahieren|multiplizieren|dividieren|"
        r"berechnen|teilen\s+(?:wir|durch))\b.{0,30}\d",
        re.IGNORECASE,
    ),
    # Decimal-time as conclusion-marker — "2.5 Stunden", "12,5 Stunden" etc.
    # Whole-number times can be real durations ("3 Stunden") but decimals are
    # almost always math-derived in chat context.
    re.compile(r"\b\d+[.,]\d+\s*(?:Stunden|Minuten|Sekunden|Stunde|Minute)\b", re.IGNORECASE),
]


# Soft markers — need TWO of these to count as MATH
_MATH_SOFT = [
    re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:Stunden|Minuten|Sekunden|Stunde|Minute)\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:km|m|cm|mm)\b"),
    re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:Euro|EUR|€|CHF|USD|\$)\b"),
    re.compile(r"\b\d+(?:[.,]\d+)?\s*%"),
    # 2026-06-02: added Strecke (production Q5 fixture: "Die gesamte Strecke
    # zwischen den Zügen beträgt 500 km" was 1-soft (just 500 km) → GENERAL →
    # tribunal called + maybefact-mis-graded. With Strecke as soft, 2-soft → MATH).
    re.compile(r"\b(?:Distanz|Entfernung|Strecke|Abstand|Geschwindigkeit|Zeit|Dauer)\b", re.IGNORECASE),
    re.compile(r"\b(?:Summe|Differenz|Produkt|Quotient)\b", re.IGNORECASE),
]


def _count_soft_matches(text: str) -> int:
    """How many independent SOFT markers match."""
    return sum(1 for p in _MATH_SOFT if p.search(text))


def _is_math_claim(claim_text: str) -> bool:
    """True if claim is arithmetic/units/calculation."""
    if not claim_text:
        return False
    text = claim_text.strip()
    if not text:
        return False

    # Strong markers — single match is enough
    if any(p.search(text) for p in _MATH_STRONG):
        return True

    # Soft markers — need at least 2
    if _count_soft_matches(text) >= 2:
        return True

    return False


# ─── Public entry ──────────────────────────────────────────────────────


def classify_claim_class(
    claim_text: str,
    user_query: str = "",
) -> WitnessClass:
    """Route a claim to its appropriate witness-class.

    Args:
        claim_text: the claim to classify
        user_query: (optional) the user's question/message; if provided,
                    enables USER_INPUT detection (claim is largely a
                    parrot-back of user's words → not verifiable via web).

    Order of precedence:
      1. USER_INPUT (if user_query given + echo-ratio ≥ threshold) —
         bot is restating user, not making its own claim.
      2. MATH — arithmetic/units, deterministically verifiable.
      3. GENERAL — default, web-tribunal handles.

    Step (c.0) added MATH. Step (c.1) adds USER_INPUT.
    AUTHORITATIVE pending (future).
    """
    if not claim_text or not claim_text.strip():
        return WitnessClass.GENERAL

    # USER_INPUT takes precedence — if bot is echoing the user, no witness
    # (math or web) can verify "did the user say this".
    if user_query and _is_user_input_echo(claim_text, user_query):
        return WitnessClass.USER_INPUT

    if _is_math_claim(claim_text):
        return WitnessClass.MATH

    return WitnessClass.GENERAL


__all__ = [
    "WitnessClass",
    "classify_claim_class",
    "user_input_echo_ratio",
    "USER_INPUT_RATIO_THRESHOLD",
]
