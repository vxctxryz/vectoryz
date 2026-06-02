"""pipeline/math_witness — deterministic arithmetic verification.

Per judex-non-calculat doctrine: when a claim contains arithmetic
("X op Y = Z"), delegate to a calculator-witness instead of asking
google-witnesses to verify "is 500/200 = 2.5". Pure compute is
deterministic, fast (<1ms), and authoritative.

Sequence in fix-stack: step (c.0) after step (b) witness_routing MATH-
class. (b) skips tribunal for math (witnesses can't verify arithmetic
via web search); (c.0) ADDS a deterministic math verdict so wrong math
CAN be refuted by compute instead.

Q5 production motivation: short-tier said "Die Züge treffen sich nach
1,67 Stunden" while the correct answer is 2,5. Web-tribunal couldn't
refute. If the bot writes a full equation with the wrong RHS, e.g.
"500 / 200 = 1,67", math_witness extracts, eval()s the LHS → 2.5,
compares to 1.67 → mismatch → caller can grade nonfact.

v1 scope (this module):
  - Find "X op Y = Z" patterns (op in +-*/×÷)
  - Sandboxed-eval LHS, compare to RHS
  - German decimal (2,5) handled
  - Units (km, km/h, EUR, %, etc.) stripped before eval
  - Tolerance 1% relative OR 0.01 absolute

v2 (future, NOT in this module):
  - Structural extraction ("answer is X" with implicit context)
  - Problem-class solvers (trains-meeting, etc.)
  - sympy fallback

Doctrine:
  - [[judex_non_calculat]] — delegate arithmetic to a calculator
  - [[ehrlich_stumm_doctrine]] — when math can verify, math wins

Public API:
  MathVerdict (dataclass)
  verify_arithmetic(claim_text) -> Optional[MathVerdict]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# Tolerance: arithmetic results may have rounding (2,5 vs 2.50 vs ~2.5).
# 0.01 absolute OR 1% relative — whichever is more permissive.
_ABS_TOL = 0.01
_REL_TOL = 0.01


@dataclass
class MathVerdict:
    """Result of arithmetic verification on a claim."""

    matches: bool                                # True = all eqs hold; False = ≥1 contradicts
    expressions_checked: int                     # how many "X op Y = Z" patterns evaluated
    mismatches: List[Tuple[str, float, float]] = field(default_factory=list)
    # mismatches: list of (lhs_expr_text, computed_value, stated_value)
    method: str = "eval_sandbox"


# ─── Equation extraction ────────────────────────────────────────────────


# Match expressions like:
#   80 + 120 = 200
#   500 / 200 = 2,5
#   500/200=2.5
#   80 km/h + 120 km/h = 200 km/h
#   500 km / 200 km/h = 2,5 Stunden
#
# Capture LHS (with optional unit-suffixes between numbers) and RHS.
# Unit-suffix pattern: [A-Za-z/€$%]{1,8} catches km, km/h, EUR, %, etc.
_EQ_RX = re.compile(
    r"""
    (?P<lhs>
      \d+(?:[.,]\d+)?              # first operand
      (?:\s*[A-Za-z/€$%]{1,8})?    # optional unit
      \s*[+\-*/×÷]\s*
      \d+(?:[.,]\d+)?              # second operand
      (?:\s*[A-Za-z/€$%]{1,8})?    # optional unit
    )
    \s*=\s*
    (?P<rhs>\d+(?:[.,]\d+)?)
    (?:\s*[A-Za-z/€$%]{1,12})?     # optional unit on result
    """,
    re.VERBOSE,
)


# ─── Helpers ────────────────────────────────────────────────────────────


def _de_to_float(s: str) -> Optional[float]:
    """German-decimal-aware float parse: '2,5' → 2.5."""
    try:
        return float(s.replace(",", "."))
    except (ValueError, AttributeError, TypeError):
        return None


def _strip_units(side: str) -> str:
    """Replace unit-tokens (km, km/h, EUR, %, €, etc.) with whitespace,
    leaving only digits + ops for safe eval.

    Caller has already normalized "," → "." and "×÷" → "*/" so we
    strip anything that isn't a pure-arithmetic character.

    Caveat: this also strips '/' from "km/h" — and the math operator '/'.
    To preserve math-divide, we handle that by first replacing letter+/+letter
    sequences (units like km/h, m/s) with a space."""
    # 1) Letter-sequences-with-slash (like "km/h") collapse first to a space
    side = re.sub(r"[A-Za-zÄÖÜäöü]+/[A-Za-zÄÖÜäöü]+", " ", side)
    # 2) Strip remaining non-arithmetic chars (letters, %, €, $, etc.)
    return re.sub(r"[^\d+\-*/().\s]+", " ", side)


def _safe_eval_arith(expr: str) -> Optional[float]:
    """Sandboxed eval of arithmetic.

    Only allows digits, dot, +, -, *, /, parentheses, whitespace.
    Anything else → None (refuse to eval). This rejects code-injection
    attempts that might slip past the regex.
    """
    cleaned = expr.replace(",", ".").replace("×", "*").replace("÷", "/")
    cleaned = _strip_units(cleaned)
    # Whitelist: only digits, ops, parens, whitespace, decimal point
    if not re.fullmatch(r"[\d\s.+\-*/()]+", cleaned):
        return None
    try:
        result = eval(cleaned, {"__builtins__": {}}, {})
    except (ZeroDivisionError, SyntaxError, ValueError, NameError, TypeError):
        return None
    if isinstance(result, (int, float)) and not isinstance(result, bool):
        return float(result)
    return None


def _close_enough(a: float, b: float) -> bool:
    """Within tolerance — 0.01 absolute OR 1% relative."""
    abs_diff = abs(a - b)
    if abs_diff <= _ABS_TOL:
        return True
    ref = max(abs(a), abs(b))
    if ref > 0 and abs_diff / ref <= _REL_TOL:
        return True
    return False


# ─── Public entry ──────────────────────────────────────────────────────


def verify_arithmetic(claim_text: str) -> Optional[MathVerdict]:
    """Extract arithmetic expressions from claim_text and verify them.

    Returns None if no arithmetic-equation pattern found. Otherwise a
    MathVerdict with matches=True (all eqs hold within tolerance) or
    False (≥1 contradicts).

    Caller (factampel) maps:
      None      → no math-verdict, fall through to existing path
      matches   → factfact (deterministic confirmation)
      !matches  → nonfact  (deterministic refutation)
    """
    if not claim_text or not claim_text.strip():
        return None

    found = list(_EQ_RX.finditer(claim_text))
    if not found:
        return None

    mismatches: List[Tuple[str, float, float]] = []
    checked = 0
    for m in found:
        lhs_str = m.group("lhs")
        rhs_str = m.group("rhs")
        computed = _safe_eval_arith(lhs_str)
        stated = _de_to_float(rhs_str)
        if computed is None or stated is None:
            continue
        checked += 1
        if not _close_enough(computed, stated):
            mismatches.append((lhs_str.strip(), computed, stated))

    if checked == 0:
        return None

    return MathVerdict(
        matches=(len(mismatches) == 0),
        expressions_checked=checked,
        mismatches=mismatches,
    )


__all__ = ["MathVerdict", "verify_arithmetic"]
