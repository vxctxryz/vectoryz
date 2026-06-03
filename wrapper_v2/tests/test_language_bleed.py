"""language_bleed — falsifiable tests for CJK-bleed detection.

Production fixture from task #163 (Q5 2026-06-02 16:19): short-tier model
emitted German+Chinese mix on a German-target query. Detector must flag.

Run via: python3 -m wrapper_v2.tests.test_language_bleed
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.pipeline.language_bleed import (
    count_cjk_chars,
    detect_script_bleed,
    has_bleed,
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


def test_t1_count_cjk():
    print(f"\n{_BOLD}[T1]{_RESET} count_cjk_chars — basic count")
    _check("empty string → 0", count_cjk_chars("") == 0)
    _check("pure German → 0", count_cjk_chars("Berlin ist die Hauptstadt") == 0)
    _check("pure English → 0", count_cjk_chars("Hello world") == 0)
    _check("4 Chinese chars → 4", count_cjk_chars("你好世界") == 4,
           f"got {count_cjk_chars('你好世界')}")
    _check("Japanese hiragana → counted",
           count_cjk_chars("こんにちは") == 5)
    _check("Korean hangul → counted",
           count_cjk_chars("안녕하세요") == 5)
    _check("mixed DE+ZH counted only CJK",
           count_cjk_chars("Hallo 你好 Welt") == 2)


def test_t2_q5_fixture_detected():
    """Exact text from task #163 Q5 leak (2026-06-02 16:19)."""
    print(f"\n{_BOLD}[T2]{_RESET} Q5 fixture — DE response with CJK bleed → detected")
    q5_leak = (
        "Die Züge treffen sich nach约3.13小时。它们相向而行的相对速度是200 km/h"
        "（80 km/h + 120 km/h），因此他们将在500 km / 200 km/h = 2.5小时后相遇。"
        "（一个更详细的计算过程如下：）"
    )
    r = detect_script_bleed(q5_leak, "de")
    _check("detected = True", r["detected"] is True, f"reason={r['reason']}")
    _check("cjk_count ≥ 30", r["cjk_count"] >= 30, f"got {r['cjk_count']}")
    _check("ratio > threshold", r["ratio"] > r["threshold"],
           f"ratio={r['ratio']:.3f} threshold={r['threshold']}")


def test_t3_pure_german_not_detected():
    print(f"\n{_BOLD}[T3]{_RESET} pure German text → not detected")
    text = (
        "Die Züge treffen sich nach 2,5 Stunden. Wir addieren ihre "
        "Geschwindigkeiten: 80 km/h + 120 km/h = 200 km/h."
    )
    r = detect_script_bleed(text, "de")
    _check("not detected", r["detected"] is False)
    _check("cjk_count = 0", r["cjk_count"] == 0)


def test_t4_pure_english_not_detected():
    print(f"\n{_BOLD}[T4]{_RESET} pure English text → not detected")
    text = "The trains meet after 2.5 hours of driving toward each other."
    r = detect_script_bleed(text, "en")
    _check("not detected", r["detected"] is False)


def test_t5_target_cjk_languages_skipped():
    print(f"\n{_BOLD}[T5]{_RESET} target=zh/ja/ko → bleed-check skipped (CJK expected)")
    for target in ["zh", "ja", "ko", "zh-CN", "ja-JP", "yue"]:
        r = detect_script_bleed("你好世界，这是中文回答", target)
        _check(f"target={target}: not detected",
               r["detected"] is False,
               f"reason={r['reason']}")


def test_t6_minor_citation_not_detected():
    """Single CJK char in long German text (legitimate quote/citation)
    should NOT trigger — below MIN_CJK_FOR_BLEED."""
    print(f"\n{_BOLD}[T6]{_RESET} minor citation → not detected")
    text = (
        "Das chinesische Wort 你 bedeutet 'du' im Deutschen. Dies ist "
        "ein langes Beispiel mit vielen deutschen Wörtern um zu zeigen, "
        "dass eine kleine Zitierung nicht als Bleed erkannt wird."
    )
    r = detect_script_bleed(text, "de")
    _check(f"not detected (cjk_count={r['cjk_count']})",
           r["detected"] is False)


def test_t7_threshold_band():
    print(f"\n{_BOLD}[T7]{_RESET} threshold band — between MIN_COUNT (3) and ratio cutoff")
    # 3 CJK chars in long German text — meets MIN but below ratio
    long_de = "Berlin ist die Hauptstadt Deutschlands. " * 5
    text_mild = long_de + "你好世界"  # ~4 CJK in ~200 char text
    r = detect_script_bleed(text_mild, "de")
    # The mild case may or may not detect depending on ratio
    print(f"      mild case: cjk={r['cjk_count']} total={r['total_chars']} ratio={r['ratio']:.4f}")

    # 50 CJK chars in 100-char German — clearly above ratio
    text_heavy = "Berlin Hauptstadt " + "你好" * 25
    r = detect_script_bleed(text_heavy, "de")
    _check(f"heavy bleed detected (ratio={r['ratio']:.3f})", r["detected"] is True)


def test_t8_empty_and_none():
    print(f"\n{_BOLD}[T8]{_RESET} empty / None inputs handled")
    for inp in ["", None]:
        r = detect_script_bleed(inp, "de")
        _check(f"input {inp!r}: not detected", r["detected"] is False)
        _check(f"input {inp!r}: cjk_count = 0", r["cjk_count"] == 0)


def test_t9_has_bleed_convenience():
    print(f"\n{_BOLD}[T9]{_RESET} has_bleed convenience returns bool")
    _check("German+CJK → True",
           has_bleed("Hallo 你好世界, das ist 我 ein 是 Test", "de") is True)
    _check("Pure German → False",
           has_bleed("Berlin ist Deutschland", "de") is False)
    _check("Target=zh skipped → False",
           has_bleed("你好世界", "zh") is False)


def main() -> int:
    print(f"{_BOLD}language_bleed — task #163 CJK-bleed detection · falsifiable{_RESET}")
    print("=" * 75)

    test_t1_count_cjk()
    test_t2_q5_fixture_detected()
    test_t3_pure_german_not_detected()
    test_t4_pure_english_not_detected()
    test_t5_target_cjk_languages_skipped()
    test_t6_minor_citation_not_detected()
    test_t7_threshold_band()
    test_t8_empty_and_none()
    test_t9_has_bleed_convenience()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}language_bleed result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
