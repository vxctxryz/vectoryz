"""pipeline/language_bleed — detect script bleed in LLM output.

Production motivation (task #163, 2026-06-02): Q5 trains-meeting query
produced a half-Chinese short-tier answer:

  "Die Züge treffen sich nach约3.13小时。它们相向而行的相对速度是200 km/h..."

The short-tier model bled Chinese characters into a German response with
a hallucinated number (3.13 vs correct 2.5). The standard user sees
unintelligible CJK characters mixed into their German answer — confusing
+ a signal that the short-tier output is low-quality.

Detection: count CJK characters; if target language is non-CJK and CJK
ratio exceeds threshold → bleed flagged. Caller (wrapper_cc.py) uses
this to force escalation to the deep-tier (which produced the correct
answer in the operator's Q5 run).

Doctrine:
  - [[propaganda_over_ransomware]] — script mismatch in expected language
    is a *visible* quality red flag the user can spot in 1 second
  - [[smartfaul_doctrine]] — escalate to deep-tier when short-tier emits
    trash; don't ship garbage to save 30 seconds

Public API:
  count_cjk_chars(text) -> int
  detect_script_bleed(text, target_lang, threshold=0.05) -> dict
  has_bleed(text, target_lang) -> bool
"""

from __future__ import annotations

import re
from typing import Optional


# CJK character ranges (Chinese, Japanese, Korean).
# Covers ideographs + kana + hangul + CJK punctuation + fullwidth forms.
_CJK_RX = re.compile(
    r"[一-鿿"   # CJK unified ideographs (most Chinese chars)
    r"㐀-䶿"    # CJK extension A
    r"぀-ゟ"    # Hiragana
    r"゠-ヿ"    # Katakana
    r"가-힯"    # Hangul syllables
    r"　-〿"    # CJK symbols + punctuation
    r"＀-￯"    # Fullwidth forms (e.g. fullwidth commas, parens)
    r"]"
)

# Languages that EXPECT CJK characters in their output — bleed-detection skipped
_CJK_LANGS = frozenset(["zh", "ja", "ko", "yue"])

# Default thresholds
DEFAULT_BLEED_THRESHOLD = 0.05  # >5% of non-whitespace chars is CJK
MIN_CJK_FOR_BLEED = 3            # at least 3 CJK chars to count (filter accidental noise)


def count_cjk_chars(text: str) -> int:
    """Count CJK / CJK-fullwidth characters in text."""
    if not text:
        return 0
    return len(_CJK_RX.findall(text))


def detect_script_bleed(
    text: str,
    target_lang: str,
    threshold: float = DEFAULT_BLEED_THRESHOLD,
) -> dict:
    """Detect whether `text` has CJK-script bleed relative to `target_lang`.

    Args:
        text: the LLM output (or any text) to check
        target_lang: the language the output is supposed to be in
                     (BCP47-ish; only first 2 chars used)
        threshold: minimum CJK-to-total ratio that counts as bleed

    Returns a dict with keys:
        detected:    bool — True if bleed found
        cjk_count:   int — total CJK chars found
        total_chars: int — total non-whitespace chars in text
        ratio:       float — cjk_count / total_chars
        target_lang: str — normalized target language
        threshold:   float — threshold used
        reason:      str — short explanation
    """
    if not text:
        return {
            "detected": False, "cjk_count": 0, "total_chars": 0,
            "ratio": 0.0, "target_lang": target_lang,
            "threshold": threshold, "reason": "empty_text",
        }

    # Normalize BCP47: split on '-' and lowercase. Handles "de", "zh-CN", "yue".
    target = (target_lang or "").lower().split("-")[0]
    cjk = count_cjk_chars(text)
    total = len(re.sub(r"\s+", "", text))
    ratio = cjk / max(1, total)

    if target in _CJK_LANGS:
        return {
            "detected": False, "cjk_count": cjk, "total_chars": total,
            "ratio": ratio, "target_lang": target,
            "threshold": threshold,
            "reason": "target_lang_is_cjk_expected",
        }

    if cjk < MIN_CJK_FOR_BLEED:
        return {
            "detected": False, "cjk_count": cjk, "total_chars": total,
            "ratio": ratio, "target_lang": target,
            "threshold": threshold,
            "reason": f"below_min_count({MIN_CJK_FOR_BLEED})",
        }

    if ratio > threshold:
        return {
            "detected": True, "cjk_count": cjk, "total_chars": total,
            "ratio": ratio, "target_lang": target,
            "threshold": threshold,
            "reason": f"ratio_{ratio:.3f}_exceeds_{threshold}",
        }

    return {
        "detected": False, "cjk_count": cjk, "total_chars": total,
        "ratio": ratio, "target_lang": target,
        "threshold": threshold,
        "reason": "below_threshold",
    }


def has_bleed(text: str, target_lang: str) -> bool:
    """Convenience wrapper: returns just the detected boolean."""
    return detect_script_bleed(text, target_lang).get("detected", False)


__all__ = [
    "count_cjk_chars",
    "detect_script_bleed",
    "has_bleed",
    "DEFAULT_BLEED_THRESHOLD",
]
