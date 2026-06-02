"""math_witness — falsifiable benchmark for Phase-2 fix #3 step (c.0).

Judex-non-calculat: explicit "X op Y = Z" patterns get sandboxed eval,
compared to stated RHS within tolerance. Production Q5 motivation:
short-tier said '1.67 hours' for 500/200; if it had written the
explicit equation '500/200 = 1.67' math_witness would catch it.

Run via: python3 -m wrapper_v2.tests.test_math_witness
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.pipeline.math_witness import (
    MathVerdict,
    verify_arithmetic,
)


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


def test_t1_simple_correct():
    print(f"\n{_BOLD}[T1]{_RESET} simple correct arithmetic → matches=True")
    for claim in [
        "80 + 120 = 200",
        "500 / 200 = 2,5",
        "100 - 30 = 70",
        "5 * 4 = 20",
        "10 × 10 = 100",
        "100 ÷ 4 = 25",
        "0,5 + 0,5 = 1",
    ]:
        v = verify_arithmetic(claim)
        ok = v is not None and v.matches
        _check(f"matches: {claim!r:45s}", ok,
               f"got verdict={v}")


def test_t2_simple_wrong():
    print(f"\n{_BOLD}[T2]{_RESET} simple WRONG arithmetic → matches=False")
    for claim in [
        "80 + 120 = 250",
        "500 / 200 = 1,67",        # the Q5 bug case
        "100 - 30 = 80",
        "5 * 4 = 25",
        "10 × 10 = 50",
    ]:
        v = verify_arithmetic(claim)
        ok = v is not None and not v.matches
        _check(f"!matches: {claim!r:45s}", ok,
               f"got verdict={v}")


def test_t3_german_decimals():
    print(f"\n{_BOLD}[T3]{_RESET} German-decimal (2,5) handled correctly")
    for claim in [
        "1,5 + 2,5 = 4",
        "500 / 200 = 2,5",
        "10,0 * 0,5 = 5,0",
        "0,1 + 0,2 = 0,3",
    ]:
        v = verify_arithmetic(claim)
        ok = v is not None and v.matches
        _check(f"DE-decimal: {claim!r:45s}", ok,
               f"got verdict={v}")


def test_t4_units_ignored():
    print(f"\n{_BOLD}[T4]{_RESET} units (km, km/h, EUR, %) stripped before eval")
    for claim, expected_correct in [
        ("80 km/h + 120 km/h = 200 km/h", True),
        ("500 km / 200 km/h = 2,5 Stunden", True),
        ("5 EUR + 5 EUR = 10 EUR", True),
        ("100 m + 50 m = 150 m", True),
        ("10% + 10% = 20%", True),
        # wrong version of unit-bearing equation
        ("80 km/h + 120 km/h = 250 km/h", False),
    ]:
        v = verify_arithmetic(claim)
        ok = v is not None and v.matches == expected_correct
        _check(f"units: {claim!r:55s} → {expected_correct}", ok,
               f"got verdict={v}")


def test_t5_no_equation_returns_none():
    print(f"\n{_BOLD}[T5]{_RESET} no arithmetic-equation found → None")
    for claim in [
        "Die Züge treffen sich nach 2,5 Stunden.",
        "Berlin ist Hauptstadt Deutschlands.",
        "Die Mehrwertsteuer beträgt 19%.",
        "Berlin hat etwa 3,7 Millionen Einwohner.",
        "",
        "    ",
        None,
    ]:
        v = verify_arithmetic(claim)
        _check(f"None: {(claim or '<none>')[:50]!r:55s}",
               v is None,
               f"got verdict={v}")


def test_t6_tolerance_band():
    print(f"\n{_BOLD}[T6]{_RESET} tolerance band — rounded values within tolerance")
    for claim, expected_match in [
        # Within 1% relative — should match
        ("1 / 3 = 0,3333", True),       # exact-ish
        ("10 / 3 = 3,33", True),        # 3.333... → 3.33 ≈ within abs tol
        # Outside tolerance — should NOT match
        ("1 / 3 = 0,5", False),
        ("22 / 7 = 3,5", False),
    ]:
        v = verify_arithmetic(claim)
        ok = v is not None and v.matches == expected_match
        _check(f"tolerance: {claim!r:30s} → {expected_match}", ok,
               f"got verdict={v}")


def test_t7_sandbox_safety():
    print(f"\n{_BOLD}[T7]{_RESET} eval sandbox — code injection refused")
    # These patterns should either not match the regex OR
    # the eval should refuse (return None). Critically: no side-effects.
    test_cases = [
        "import os = 1",
        "__import__('os') = 1",
        "eval('1+1') = 2",
        "print('pwned') = 1",
        "[1,2,3] = 1",
        "1 if True else 2 = 1",
    ]
    for claim in test_cases:
        try:
            v = verify_arithmetic(claim)
            # Acceptable: None (no regex match), or matches=False (eval refused)
            # Critical: must not crash, must not execute
            safe = v is None or not v.matches or v.expressions_checked == 0
            _check(f"sandbox: {claim!r:40s}", safe,
                   f"got verdict={v}")
        except Exception as e:
            _check(f"sandbox: {claim!r:40s}", False,
                   f"CRASHED: {e}")


def test_t8_zero_division_safe():
    print(f"\n{_BOLD}[T8]{_RESET} division by zero → safe (no crash)")
    for claim in [
        "100 / 0 = 0",
        "10 / 0 = 999",
    ]:
        try:
            v = verify_arithmetic(claim)
            # Should not crash. Verdict can be None or have 0 expressions checked.
            ok = v is None or v.expressions_checked == 0
            _check(f"÷0 safe: {claim!r:30s}", ok,
                   f"got verdict={v}")
        except Exception as e:
            _check(f"÷0 safe: {claim!r:30s}", False,
                   f"CRASHED: {e}")


def test_t9_q5_real_correct_fixture():
    """Q5 production (2026-06-02, post-(b)-validate) — the bot wrote
    correct math, math_witness must agree."""
    print(f"\n{_BOLD}[T9]{_RESET} Q5 real fixture — correct math agrees")
    claim = (
        "Da sie entgegenkommend fahren, addieren wir ihre Geschwindigkeiten: "
        "80 km/h + 120 km/h = 200 km/h. Teilen wir die Entfernung durch die "
        "zusammengerechnete Geschwindigkeit: 500 km / 200 km/h = 2,5 Stunden."
    )
    v = verify_arithmetic(claim)
    _check("Q5 correct: verdict returned", v is not None,
           f"got verdict={v}")
    if v is not None:
        _check("Q5 correct: matches=True", v.matches,
               f"mismatches={v.mismatches}")
        _check("Q5 correct: expressions_checked ≥ 2",
               v.expressions_checked >= 2,
               f"checked={v.expressions_checked}")


def test_t10_q5_hallucination_fixture():
    """Hypothetical: if the bot had written 500/200=1,67 explicitly,
    math_witness must REFUTE it."""
    print(f"\n{_BOLD}[T10]{_RESET} hypothetical hallucination — wrong math refuted")
    claim = (
        "Wir teilen die Entfernung durch die Geschwindigkeit: "
        "500 / 200 = 1,67 Stunden."
    )
    v = verify_arithmetic(claim)
    _check("hallu: verdict returned", v is not None,
           f"got verdict={v}")
    if v is not None:
        _check("hallu: matches=False (refuted)", not v.matches,
               f"matches unexpectedly true; mismatches={v.mismatches}")
        # The single mismatch should report computed≈2.5 vs stated≈1.67
        if v.mismatches:
            lhs, computed, stated = v.mismatches[0]
            _check("hallu: computed ≈ 2.5",
                   abs(computed - 2.5) < 0.01,
                   f"computed={computed}")
            _check("hallu: stated ≈ 1.67",
                   abs(stated - 1.67) < 0.01,
                   f"stated={stated}")


def test_t11_mixed_correct_and_wrong():
    """If a claim contains multiple equations and ANY is wrong → matches=False."""
    print(f"\n{_BOLD}[T11]{_RESET} mixed correct+wrong → matches=False")
    claim = "Zuerst: 80 + 120 = 200. Dann: 500 / 200 = 1,67."
    v = verify_arithmetic(claim)
    _check("mixed: verdict returned", v is not None,
           f"got verdict={v}")
    if v is not None:
        _check("mixed: matches=False (one wrong)", not v.matches,
               f"matches={v.matches}; mismatches={v.mismatches}")
        _check("mixed: expressions_checked == 2",
               v.expressions_checked == 2,
               f"checked={v.expressions_checked}")
        _check("mixed: exactly 1 mismatch reported",
               len(v.mismatches) == 1,
               f"mismatches={v.mismatches}")


def main() -> int:
    print(f"{_BOLD}math_witness — Phase-2 fix #3 step (c.0) · falsifiable{_RESET}")
    print("=" * 75)

    test_t1_simple_correct()
    test_t2_simple_wrong()
    test_t3_german_decimals()
    test_t4_units_ignored()
    test_t5_no_equation_returns_none()
    test_t6_tolerance_band()
    test_t7_sandbox_safety()
    test_t8_zero_division_safe()
    test_t9_q5_real_correct_fixture()
    test_t10_q5_hallucination_fixture()
    test_t11_mixed_correct_and_wrong()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}math_witness result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
