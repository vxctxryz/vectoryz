"""Surgical claim-list corrective — falsifiable benchmark for Step B.

Run via: python3 -m wrapper_v2.tests.test_retry_corrective_surgical
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.pipeline.retry_corrective_surgical import (
    build_surgical_refuted_claims_corrective,
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


def test_t1_empty_returns_empty():
    print(f"\n{_BOLD}[T1]{_RESET} empty / None → empty string")
    _check("empty list → ''", build_surgical_refuted_claims_corrective([]) == "")
    _check("None → ''", build_surgical_refuted_claims_corrective(None) == "")
    _check("list of empty strings → ''",
           build_surgical_refuted_claims_corrective(["", "  ", ""]) == "")


def test_t2_single_claim():
    print(f"\n{_BOLD}[T2]{_RESET} single claim listed")
    claim = "Im Abschnitt 201 diskutiert Wittgenstein das Gesichtsbild eines Baumes."
    out = build_surgical_refuted_claims_corrective([claim])
    _check("contains 'TRIBUNAL-REFUTED'", "TRIBUNAL-REFUTED" in out)
    _check("contains 'chirurgisch'", "chirurgisch" in out)
    _check("contains the claim text", claim in out)
    _check("contains the (a)(b)(c) options",
           "(a)" in out and "(b)" in out and "(c)" in out)
    _check("instructs against paraphrase",
           "NICHT" in out and "paraphrasiert" in out)


def test_t3_multiple_claims_listed():
    print(f"\n{_BOLD}[T3]{_RESET} multiple claims listed individually")
    claims = [
        "Die Distanz zwischen den Zügen beträgt 500 km.",
        "Die Relativgeschwindigkeit ist 40 km/h.",
        "Die Züge treffen sich nach 12,5 Stunden.",
    ]
    out = build_surgical_refuted_claims_corrective(claims)
    for c in claims:
        _check(f"claim listed: {c[:40]}…", c in out)
    _check("1. through 3. numbered",
           "1." in out and "2." in out and "3." in out)


def test_t4_overflow_capped_at_5():
    print(f"\n{_BOLD}[T4]{_RESET} >5 claims → first 5 shown + overflow note")
    claims = [f"Claim number {i}" for i in range(1, 9)]  # 8 claims
    out = build_surgical_refuted_claims_corrective(claims)
    _check("'Claim number 1' shown", "Claim number 1" in out)
    _check("'Claim number 5' shown", "Claim number 5" in out)
    _check("'Claim number 6' NOT shown", "Claim number 6" not in out)
    _check("overflow note", "ersten 5" in out and "von 8" in out)


def test_t5_long_claim_truncated():
    print(f"\n{_BOLD}[T5]{_RESET} claim >200 chars truncated with ellipsis")
    long_claim = "A" * 250
    out = build_surgical_refuted_claims_corrective([long_claim])
    _check("'AAA…' shown", "AAA" in out)
    _check("truncated with ellipsis", "…" in out)
    _check("not full 250 chars shown",
           "A" * 250 not in out)


def test_t6_newlines_in_claim_normalized():
    print(f"\n{_BOLD}[T6]{_RESET} newlines in claim → spaces (listing stays clean)")
    multi_line = "First line.\nSecond line.\nThird line."
    out = build_surgical_refuted_claims_corrective([multi_line])
    _check("newlines in claim normalized to space",
           "First line. Second line. Third line." in out)


def main() -> int:
    print(f"{_BOLD}retry_corrective_surgical — Phase-2 fix #2 step B · falsifiable{_RESET}")
    print("=" * 75)

    test_t1_empty_returns_empty()
    test_t2_single_claim()
    test_t3_multiple_claims_listed()
    test_t4_overflow_capped_at_5()
    test_t5_long_claim_truncated()
    test_t6_newlines_in_claim_normalized()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}retry_corrective_surgical result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
