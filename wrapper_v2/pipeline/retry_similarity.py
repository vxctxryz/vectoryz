"""pipeline/retry_similarity — detect unproductive retry-loop repetition.

Phase-2 fix #2 step A (2026-06-01): when the audit-retry loop produces
N consecutive outputs with high similarity to the previous attempt, abort
remaining retries. The model isn't going to suddenly find new ground-truth
by re-running with the same context.

Triggering observation: Q5 math test produced 3 retry attempts that were
WÖRTLICH identical ("Um die Zeit zu berechnen... 500/40 = 12,5 Stunden")
× 3. Each retry took ~1min generation time. Saves 2-4min per drift-
detected response when repetition is detected.

Doctrine:
  - [[hammerantwort]] — substance over eloquent re-attempts
  - [[ehrlich_stumm_doctrine]] — if model can't improve, accept + degrade
    gracefully; don't waste compute on stalled retries
  - "Fleissig-effizient" 2026-06-01 doctrine

Public API:
  compute_similarity(text_a, text_b) -> float       # 0.0-1.0 ratio
  is_retry_repetition(new, prev, threshold=0.85) -> bool
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher


# Default threshold: if ≥85% of normalized content matches, treat as
# "unproductive retry" and abort. Observed Q5 case had 100% identical
# content (wörtlich), so even higher thresholds would catch it; 0.85
# gives tolerance for minor reformatting variance.
DEFAULT_SIMILARITY_THRESHOLD = 0.85


def _normalize(text: str) -> str:
    """Collapse whitespace, strip, lowercase. Strips retry-header markers
    so comparison ignores '(verbesserter Versuch X/N ...)' wrapper-text.
    """
    if not text:
        return ""
    # Strip retry-attempt headers that the wrapper inserts between attempts
    t = re.sub(
        r"_\(verbesserter Versuch[^)]*\)_",
        "",
        text,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"---+", "", t)
    t = re.sub(r"\s+", " ", t.strip().lower())
    return t


def compute_similarity(text_a: str, text_b: str) -> float:
    """Return similarity ratio 0.0-1.0 (1.0 = identical after normalization).

    Whitespace + case + retry-header markers normalized. Uses difflib's
    SequenceMatcher (Ratcliff/Obershelp algorithm, O(n²) but fine for
    typical chat-response sizes 200-5000 chars).
    """
    a = _normalize(text_a)
    b = _normalize(text_b)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def is_retry_repetition(
    new_text: str,
    prev_text: str,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> bool:
    """True if new_text ≈ prev_text (similarity ≥ threshold).

    Use to short-circuit the retry-loop when the model is producing
    identical/near-identical output across attempts — i.e. the corrective
    isn't getting through.

    Args:
      new_text:  the output of the current retry attempt
      prev_text: the output of the previous attempt (initial response, or
                 prior retry)
      threshold: similarity ratio above which we declare repetition
                 (default 0.85 — see DEFAULT_SIMILARITY_THRESHOLD)
    """
    if not new_text or not prev_text:
        return False
    return compute_similarity(new_text, prev_text) >= threshold


__all__ = [
    "DEFAULT_SIMILARITY_THRESHOLD",
    "compute_similarity",
    "is_retry_repetition",
]
