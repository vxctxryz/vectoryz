"""Retry-similarity — falsifiable benchmark for Phase-2 fix #2 step A.

Triggering observation 2026-06-01: Q5 math test produced 3 wörtlich
identical retry attempts. is_retry_repetition() should detect and signal
abort.

Run via: python3 -m wrapper_v2.tests.test_retry_similarity
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.pipeline.retry_similarity import (
    compute_similarity,
    is_retry_repetition,
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


# ─── Real-world fixture: Q5 retry repetition ──────────────────────────


Q5_DEEP_TIER_OUTPUT = (
    "Um die Zeit zu berechnen, bis sich zwei Züge mit unterschiedlichen "
    "Geschwindigkeiten treffen, müssen wir ihre Relativgeschwindigkeit "
    "bestimmen. In diesem Fall fährt der Zug von A nach B mit 120 km/h "
    "und der Zug von B nach A mit 80 km/h.\n\n"
    "Die Relativgeschwindigkeit ist die Differenz zwischen den beiden "
    "Geschwindigkeiten: 120 km/h - 80 km/h = 40 km/h. Das bedeutet, "
    "dass sich die Züge aufeinander zubewegen, als wäre ein Zug mit "
    "einer Geschwindigkeit von 40 km/h unterwegs.\n\n"
    "Nun können wir die Zeit berechnen, die vergeht, bis sie sich "
    "treffen. Dazu teilen wir den gesamten Abstand (500 km) durch ihre "
    "Relativgeschwindigkeit (40 km/h): 500 km / 40 km/h = 12,5 Stunden.\n\n"
    "Daher werden die Züge sich nach approximately 12,5 Stunden treffen."
)


def test_t1_q5_wörtlich_identisch():
    print(f"\n{_BOLD}[T1]{_RESET} Q5-fixture: 3× wörtlich identical → abort")
    ratio = compute_similarity(Q5_DEEP_TIER_OUTPUT, Q5_DEEP_TIER_OUTPUT)
    _check(f"identical similarity = 1.0 (got {ratio:.3f})", ratio == 1.0)
    _check("is_retry_repetition → True", is_retry_repetition(Q5_DEEP_TIER_OUTPUT, Q5_DEEP_TIER_OUTPUT))


def test_t2_minor_reformatting():
    print(f"\n{_BOLD}[T2]{_RESET} minor whitespace/case variation → still repetition")
    a = "foo bar baz"
    b = "foo  bar BAZ"
    _check("similar after normalization", is_retry_repetition(a, b))
    a = "Berlin ist die Hauptstadt Deutschlands."
    b = "berlin   ist  die hauptstadt deutschlands"
    _check("DE sentence near-identical", is_retry_repetition(a, b))


def test_t3_completely_different():
    print(f"\n{_BOLD}[T3]{_RESET} completely different content → not repetition")
    a = "Die Züge treffen sich nach 2.5 Stunden."
    b = "Wittgenstein diskutiert in §201 das Regelfolgen-Paradox."
    ratio = compute_similarity(a, b)
    _check(f"low similarity (got {ratio:.3f}, expect < 0.4)", ratio < 0.4)
    _check("is_retry_repetition → False", not is_retry_repetition(a, b))


def test_t4_retry_header_ignored():
    print(f"\n{_BOLD}[T4]{_RESET} retry-attempt-headers stripped before comparing")
    base = "Der Nobelpreis 2024 ging an Hopfield und Hinton."
    a = base
    b = (
        "_(verbesserter Versuch 1/2 — Drift erkannt: ...)_\n\n---\n\n"
        + base
    )
    _check("retry-wrapped version matches base",
           is_retry_repetition(a, b),
           f"sim = {compute_similarity(a, b):.3f}")


def test_t5_threshold_band_behavior():
    """Default threshold = 0.70 (2026-06-01 tuned). Verify boundary cases.
    Sample text-pair has similarity ≈ 0.75 (moderate overlap, would be
    Q4-class truncation-paraphrase)."""
    print(f"\n{_BOLD}[T5]{_RESET} moderate overlap → repetition at 0.70 but NOT at 0.85")
    a = "Berlin ist die Hauptstadt. München ist die Hauptstadt Bayerns."
    b = "Berlin ist die Hauptstadt. Hamburg ist eine Hansestadt."
    ratio = compute_similarity(a, b)
    _check(f"moderate overlap (got {ratio:.3f})", 0.65 < ratio < 0.85)
    _check("at default 0.70: IS repetition",
           is_retry_repetition(a, b))
    _check("at strict 0.85: NOT repetition (preserves legitimate restructure)",
           not is_retry_repetition(a, b, threshold=0.85))
    _check("at very-low 0.50: IS repetition",
           is_retry_repetition(a, b, threshold=0.50))


def test_t6_empty_safe():
    print(f"\n{_BOLD}[T6]{_RESET} empty / None inputs handled safely")
    _check("empty new → False", not is_retry_repetition("", "anything"))
    _check("empty prev → False", not is_retry_repetition("anything", ""))
    _check("both empty similarity = 1.0", compute_similarity("", "") == 1.0)
    _check("both empty → still False (no useful signal)",
           not is_retry_repetition("", ""))


def test_t7_threshold_boundaries():
    print(f"\n{_BOLD}[T7]{_RESET} threshold boundary behavior")
    # Construct text-pair with controlled similarity
    a = "the quick brown fox jumps over the lazy dog"
    b = "the slow brown fox sleeps under the busy dog"
    sim = compute_similarity(a, b)
    print(f"      similarity = {sim:.3f}")
    _check("similarity in expected range",
           0.5 < sim < 0.85,
           f"got {sim:.3f}")
    _check("threshold below sim → repetition",
           is_retry_repetition(a, b, threshold=sim - 0.05))
    _check("threshold above sim → NOT repetition",
           not is_retry_repetition(a, b, threshold=sim + 0.05))


def main() -> int:
    print(f"{_BOLD}retry-similarity — Phase-2 fix #2 step A · falsifiable{_RESET}")
    print("=" * 75)

    test_t1_q5_wörtlich_identisch()
    test_t2_minor_reformatting()
    test_t3_completely_different()
    test_t4_retry_header_ignored()
    test_t5_threshold_band_behavior()
    test_t6_empty_safe()
    test_t7_threshold_boundaries()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}retry-similarity result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
