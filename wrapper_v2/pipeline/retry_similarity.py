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


# Default threshold for SYMMETRIC similarity (Ratcliff-Obershelp ratio).
# Tuned 2026-06-01.
DEFAULT_SIMILARITY_THRESHOLD = 0.70

# Default threshold for ASYMMETRIC containment.
# Detects: "is the new retry mostly already in the previous attempt?"
# Catches the Q4-class pathology where initial = paragraphs + sources
# (3638 chars) and retry = just paragraphs (1294 chars) — retry is 100%
# contained in initial but Ratcliff-Obershelp gives only sim=0.529
# (length-asymmetry bug). Containment gives 1.0 in that case.
DEFAULT_CONTAINMENT_THRESHOLD = 0.85


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
    """SYMMETRIC similarity ratio 0.0-1.0 (1.0 = identical after normalization).

    Ratcliff/Obershelp algorithm via SequenceMatcher. Length-penalizing:
    a fully-contained-but-shorter string gets a moderate ratio (~0.5-0.7)
    not 1.0. Use compute_containment() instead when asking "is A in B?".
    """
    a = _normalize(text_a)
    b = _normalize(text_b)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def compute_containment(new_text: str, prev_text: str) -> float:
    """ASYMMETRIC containment ratio 0.0-1.0.

    Returns "what fraction of new_text is already present in prev_text?".
    Unlike compute_similarity, this doesn't penalize length-difference:
    a fully-contained shorter string gets 1.0 regardless of how much
    extra content prev_text has.

    Use to catch Q4-class pathology: retry-N regenerates the same
    paragraphs as initial but drops the appended source-citations.
    Symmetric similarity gives 0.5 (length-penalized); containment
    gives 1.0 (correctly identifies "no new content").

    Args:
      new_text:  the current retry attempt's text
      prev_text: the previous attempt's text (initial response or prior retry)

    Returns:
      fraction of new_text's characters that are matched in prev_text
      (after normalization). Empty new_text → 1.0 (vacuously contained).
    """
    if not new_text:
        return 1.0
    if not prev_text:
        return 0.0
    a = _normalize(new_text)
    b = _normalize(prev_text)
    if not a:
        return 1.0
    if not b:
        return 0.0
    sm = SequenceMatcher(None, a, b)
    matched = sum(triple.size for triple in sm.get_matching_blocks())
    return matched / len(a)


def is_retry_repetition(
    new_text: str,
    prev_text: str,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    containment_threshold: float = DEFAULT_CONTAINMENT_THRESHOLD,
) -> bool:
    """True if new_text is unproductive-repetition of prev_text.

    Two-signal detection:
      (1) SYMMETRIC similarity ≥ threshold → "they look the same"
          Catches: wörtlich-identical retries (Q5), close paraphrases
      (2) ASYMMETRIC containment ≥ containment_threshold → "new adds no content"
          Catches: retry that's a strict subset of previous (Q4 where
          retry drops the sources but keeps paragraphs identical)

    EITHER signal triggers abort. Both default-thresholds tuned 2026-06-01.

    Args:
      new_text:  the output of the current retry attempt
      prev_text: the output of the previous attempt (initial or prior retry)
      threshold: symmetric-similarity ratio (default 0.70)
      containment_threshold: asymmetric containment ratio (default 0.85)
    """
    if not new_text or not prev_text:
        return False
    if compute_similarity(new_text, prev_text) >= threshold:
        return True
    if compute_containment(new_text, prev_text) >= containment_threshold:
        return True
    return False


__all__ = [
    "DEFAULT_SIMILARITY_THRESHOLD",
    "DEFAULT_CONTAINMENT_THRESHOLD",
    "compute_similarity",
    "compute_containment",
    "is_retry_repetition",
]
