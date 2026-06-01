"""pipeline/output_sanitize — strip internal scaffolding from LLM output.

Per Phase-2 fix #1 (2026-06-01): the T2.d short→deep escalation sends a
system-message containing the short answer + an "Erweitere jetzt"
expand-instruction to the deep-tier model. Some models (qwen-class)
ECHO the system-message in their output instead of writing only the
expansion. Result: the user-visible response contains the short answer
REPEATED + the meta-prompt verbatim, then the actual expansion.

This module strips those echoes BEFORE the deep-tier buffer is assembled
with the short-tier text and emitted to the UI.

Doctrine:
  - [[hammerantwort]] — substance > eloquence; scaffolding must stay invisible
  - [[audit_open_door_doctrine]] — principles are auditable, plumbing is not
  - [[no_regurgitation_doctrine]] — don't repeat what user already saw

Public API:
  strip_short_answer_echo(deep_buf, short_answer) -> str
      Strip leading echo of short_answer + the T2.d meta-prompt block
      from the deep-tier output. Safe no-op if no echo found.
"""

from __future__ import annotations

import re
from typing import Optional


# ─── Meta-prompt verbatim patterns (T2.d short→deep escalation) ─────


# The KURZANTWORT-wrapper that the wrapper_cc.py T2.d code sends.
# Verbatim from wrapper_cc.py:7102-7116 (2026-06-01 inspection).
_META_PROMPT_PATTERNS = [
    # The "KURZANTWORT (User hat das oben gesehen, ...)" header + content
    re.compile(
        r"^\s*KURZANTWORT\s*\(User hat das oben gesehen[^)]*\):\s*\n",
        re.MULTILINE,
    ),
    # The expand-instruction lines
    re.compile(
        r"^\s*Erweitere jetzt die Antwort:[^\n]*\n",
        re.MULTILINE,
    ),
    re.compile(
        r"^\s*Wiederhole die Kurzantwort NICHT[^\n]*\n",
        re.MULTILINE,
    ),
    re.compile(
        r"^\s*Schreibe direkt mit der Erweiterung los[^\n]*\n",
        re.MULTILINE,
    ),
    # Whitespace-only "Kontext, Quellen." line if it leaks (continuation
    # of "Erweitere jetzt..." that may wrap)
    re.compile(
        r"^\s*Kontext,\s*Quellen\.\s*\n",
        re.MULTILINE,
    ),
]


def _strip_short_answer_prefix(deep_buf: str, short_answer: str) -> str:
    """If deep_buf BEGINS with an exact echo of short_answer, strip it.

    Handles common echo variants:
      - exact prefix match
      - prefix match after whitespace
      - prefix match after a `---` separator line
    """
    if not short_answer or not deep_buf:
        return deep_buf

    sa = short_answer.strip()
    if not sa:
        return deep_buf

    candidate = deep_buf.lstrip()
    # Strip a leading `---` separator if present
    if candidate.startswith("---"):
        # Skip to next newline
        nl = candidate.find("\n")
        if nl != -1:
            candidate = candidate[nl + 1 :].lstrip()

    if candidate.startswith(sa):
        return candidate[len(sa) :].lstrip()

    return deep_buf


def strip_short_answer_echo(deep_buf: str, short_answer: Optional[str] = None) -> str:
    """Strip T2.d meta-prompt + short-answer-echo from deep-tier output.

    Args:
      deep_buf: the raw output stream from the deep-tier LLM call
      short_answer: the short-tier text that was passed as KURZANTWORT
                    context. If None, only the meta-prompt patterns are
                    stripped (not the prefix-echo).

    Returns:
      cleaned text — what should be assembled with the short-tier output
      and shown to the user.

    No-op safe: if no echo patterns are found, returns deep_buf unchanged
    (minus leading/trailing whitespace normalization).
    """
    if not deep_buf:
        return deep_buf

    cleaned = deep_buf

    # 1. Strip leading short-answer echo (the most common pattern)
    if short_answer:
        cleaned = _strip_short_answer_prefix(cleaned, short_answer)

    # 2. Strip any of the meta-prompt verbatim line-patterns
    for pat in _META_PROMPT_PATTERNS:
        cleaned = pat.sub("", cleaned)

    # 3. Normalize: collapse 3+ consecutive newlines to 2 (from removed lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # 4. Strip leading `---` separators that may now be orphaned
    cleaned = cleaned.lstrip()
    while cleaned.startswith("---"):
        nl = cleaned.find("\n")
        if nl == -1:
            cleaned = ""
            break
        cleaned = cleaned[nl + 1 :].lstrip()

    return cleaned.strip()


__all__ = ["strip_short_answer_echo"]
