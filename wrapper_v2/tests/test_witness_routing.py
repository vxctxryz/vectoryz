"""Witness-class routing — falsifiable benchmark for Phase-2 fix #3 step 1.

Production Q5 motivation: math claims like "Die Distanz beträgt 500 km"
and "500 ÷ 200 = 2.5 Stunden" got tribunal-graded 🟠 quasinonfact (mis-
calibrated — web witnesses can't verify arithmetic).

Run via: python3 -m wrapper_v2.tests.test_witness_routing
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.pipeline.witness_routing import (
    WitnessClass,
    classify_claim_class,
    user_input_echo_ratio,
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


def test_t1_explicit_equations_are_math():
    print(f"\n{_BOLD}[T1]{_RESET} explicit equation patterns → MATH")
    for claim in [
        "500 ÷ 200 = 2.5 Stunden",
        "80 + 120 = 200 km/h",
        "100 - 30 = 70",
        "500 / 40 = 12,5 Stunden",
        "Zeit = 500 km / 200 km/h = 2.5 Stunden",
    ]:
        cls = classify_claim_class(claim)
        _check(f"MATH: {claim!r:60s}",
               cls == WitnessClass.MATH,
               f"got {cls.value}")


def test_t2_speed_units_are_math():
    print(f"\n{_BOLD}[T2]{_RESET} speed-unit patterns → MATH")
    for claim in [
        "Der Zug fährt mit 120 km/h.",
        "Geschwindigkeit beträgt 200 km/h gemäß Addition.",
        "Die Schallgeschwindigkeit ist 343 m/s.",
    ]:
        cls = classify_claim_class(claim)
        _check(f"MATH: {claim!r:60s}",
               cls == WitnessClass.MATH,
               f"got {cls.value}")


def test_t3_relativvelocity_terms_are_math():
    print(f"\n{_BOLD}[T3]{_RESET} relative-velocity terminology → MATH")
    for claim in [
        "Die Relativgeschwindigkeit ist 40 km/h.",
        "Wir berechnen die Relativgeschwindigkeit als Summe.",
        "Die Gesamtgeschwindigkeit ergibt sich zu 200 km/h.",
    ]:
        cls = classify_claim_class(claim)
        _check(f"MATH: {claim!r:60s}",
               cls == WitnessClass.MATH,
               f"got {cls.value}")


def test_t4_soft_markers_pair_to_math():
    print(f"\n{_BOLD}[T4]{_RESET} ≥2 soft markers (distance + time, etc.) → MATH")
    for claim in [
        "Die Distanz von 500 km wird in 2 Stunden zurückgelegt.",
        "Die Entfernung beträgt 100 km, die Geschwindigkeit 50 km/h.",
        "Bei 80 Euro pro Stunde und 8 Stunden Arbeit.",
        # 2026-06-02: Strecke + Abstand added
        "Die gesamte Strecke zwischen den Zügen beträgt 500 km.",
        "Der Abstand zwischen Berlin und Hamburg beträgt 280 km.",
    ]:
        cls = classify_claim_class(claim)
        _check(f"MATH (2+ soft): {claim!r:60s}",
               cls == WitnessClass.MATH,
               f"got {cls.value}")


def test_t5_single_soft_marker_is_NOT_math():
    print(f"\n{_BOLD}[T5]{_RESET} single soft-marker alone → GENERAL (no over-match)")
    for claim in [
        "Berlin liegt im Nordosten Deutschlands.",       # no soft markers
        "Die Mehrwertsteuer beträgt 19%.",               # 1 soft marker (%)
        "Berlin hat etwa 3,7 Millionen Einwohner.",      # 1 soft (number)
    ]:
        cls = classify_claim_class(claim)
        _check(f"GENERAL (no over-match): {claim!r:60s}",
               cls == WitnessClass.GENERAL,
               f"got {cls.value}")


def test_t6_general_factual_is_general():
    print(f"\n{_BOLD}[T6]{_RESET} factual non-math claims → GENERAL")
    for claim in [
        "Wittgenstein war ein österreichischer Philosoph.",
        "Im Christentum gilt Satan als gefallener Engel.",
        "Die Photosynthese benötigt Sonnenlicht.",
        "Der Nobelpreis wurde 2024 an Hopfield und Hinton verliehen.",
    ]:
        cls = classify_claim_class(claim)
        _check(f"GENERAL: {claim!r:60s}",
               cls == WitnessClass.GENERAL,
               f"got {cls.value}")


def test_t7_empty_handled():
    print(f"\n{_BOLD}[T7]{_RESET} empty / None inputs → GENERAL (safe default)")
    _check("empty string → GENERAL",
           classify_claim_class("") == WitnessClass.GENERAL)
    _check("whitespace-only → GENERAL",
           classify_claim_class("   ") == WitnessClass.GENERAL)
    _check("None → GENERAL",
           classify_claim_class(None) == WitnessClass.GENERAL)


def test_t8_q5_real_claims():
    """Production fixture from Q5 (2026-06-01) — these were mis-graded
    quasinonfact by tribunal. Verify our classifier catches them as MATH."""
    print(f"\n{_BOLD}[T8]{_RESET} real Q5-fixture mis-graded claims → MATH")
    for claim in [
        "Die Züge treffen sich nach 2.5 Stunden.",
        "Da sie entgegenkommend fahren, addieren wir ihre Geschwindigkeiten zu 200 km/h.",
        "Die Distanz zwischen den Zügen beträgt 500 km.",
        "Dazu teilen wir den gesamten Abstand (500 km) durch ihre Relativgeschwindigkeit (40 km/h): 500 km / 40 km/h = 12,5 Stunden.",
        "Daher werden die Züge sich nach approximately 12,5 Stunden treffen.",
    ]:
        cls = classify_claim_class(claim)
        _check(f"MATH: {claim[:60]!r}…",
               cls == WitnessClass.MATH,
               f"got {cls.value}")


def test_t9_user_input_echo_detected():
    """Step (c.1): claim is largely a parrot-back of user_query → USER_INPUT.

    These claims are 'the user said X' — neither math nor web-tribunal can
    verify them; they're the user's own words.
    """
    print(f"\n{_BOLD}[T9]{_RESET} claim ≈ user_query → USER_INPUT")
    user_query = ("Berechne: ein Zug fährt mit 80 km/h, ein anderer mit "
                  "120 km/h. Sie sind 500 km auseinander und fahren "
                  "aufeinander zu. Wann treffen sie sich?")
    echo_claims = [
        # Direct verbatim phrases from the user_query
        "Sie sind 500 km auseinander und fahren aufeinander zu.",
        "ein Zug fährt mit 80 km/h, ein anderer mit 120 km/h.",
        "Die Züge sind 500 km auseinander und fahren aufeinander zu.",
    ]
    for claim in echo_claims:
        cls = classify_claim_class(claim, user_query=user_query)
        ratio = user_input_echo_ratio(claim, user_query)
        _check(f"USER_INPUT: {claim!r:55s} ratio={ratio:.2f}",
               cls == WitnessClass.USER_INPUT,
               f"got {cls.value}, ratio={ratio:.3f}")


def test_t10_synthesis_is_not_user_input():
    """Bot synthesis (combining + rephrasing user input) should NOT
    trigger USER_INPUT — that's a real claim worth verifying."""
    print(f"\n{_BOLD}[T10]{_RESET} bot synthesis (paraphrase + new content) → MATH or GENERAL")
    user_query = ("Berechne: ein Zug fährt mit 80 km/h, ein anderer mit "
                  "120 km/h. Sie sind 500 km auseinander. Wann treffen sie sich?")
    for claim, expected_not in [
        # Bot's conclusion — own claim, not echo
        ("Die Züge treffen sich nach 2,5 Stunden.", WitnessClass.USER_INPUT),
        # Bot's calculation step — own claim, math
        ("500 km / 200 km/h = 2,5 Stunden", WitnessClass.USER_INPUT),
        # Bot adds a fact not in query
        ("Berlin liegt im Nordosten Deutschlands.", WitnessClass.USER_INPUT),
    ]:
        cls = classify_claim_class(claim, user_query=user_query)
        ratio = user_input_echo_ratio(claim, user_query)
        _check(f"NOT USER_INPUT: {claim!r:50s} ratio={ratio:.2f} → got {cls.value}",
               cls != expected_not,
               f"unexpectedly classified as {cls.value}")


def test_t11_no_user_query_falls_through():
    """When user_query is None or empty, USER_INPUT check is skipped —
    classify proceeds as if it weren't given (MATH/GENERAL only)."""
    print(f"\n{_BOLD}[T11]{_RESET} empty user_query → no USER_INPUT detection")
    claim = "Sie sind 500 km auseinander und fahren aufeinander zu."
    # Without user_query → GENERAL (no math markers)
    for uq in ["", None]:
        cls = classify_claim_class(claim, user_query=uq or "")
        _check(f"no-user_query ({uq!r}): not USER_INPUT",
               cls != WitnessClass.USER_INPUT,
               f"got {cls.value} unexpectedly USER_INPUT")


def test_t12_user_input_takes_precedence_over_math():
    """If a math-like claim is also a user_query echo, USER_INPUT wins —
    we don't need math_witness to verify the user's own input."""
    print(f"\n{_BOLD}[T12]{_RESET} USER_INPUT precedence over MATH")
    user_query = "Wir wissen: 500 / 200 = 2.5. Stimmt das?"
    claim = "500 / 200 = 2.5"
    cls = classify_claim_class(claim, user_query=user_query)
    ratio = user_input_echo_ratio(claim, user_query)
    _check(f"echo-of-math ratio={ratio:.2f} → USER_INPUT",
           cls == WitnessClass.USER_INPUT,
           f"got {cls.value}")


def main() -> int:
    print(f"{_BOLD}witness_routing — Phase-2 fix #3 step 1 · falsifiable{_RESET}")
    print("=" * 75)

    test_t1_explicit_equations_are_math()
    test_t2_speed_units_are_math()
    test_t3_relativvelocity_terms_are_math()
    test_t4_soft_markers_pair_to_math()
    test_t5_single_soft_marker_is_NOT_math()
    test_t6_general_factual_is_general()
    test_t7_empty_handled()
    test_t8_q5_real_claims()
    test_t9_user_input_echo_detected()
    test_t10_synthesis_is_not_user_input()
    test_t11_no_user_query_falls_through()
    test_t12_user_input_takes_precedence_over_math()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}witness_routing result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
