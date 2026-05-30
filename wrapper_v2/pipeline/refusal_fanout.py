"""
Refusal-fanout — per [[unwrap_before_process_doctrine]] + [[audit_open_door_doctrine]].

When deep-tier LLM refuses on a multi-item blob (e.g. test-grid with mix of
historical-public + sensitive items), split the blob into items and re-engage
per-item. Refusing the WHOLE package because some items SEEM sensitive is
decorative-not-protective: most "sensitive" historical items (MK-Ultra, ECHELON,
Neuschwabenland, Philadelphia Experiment) are publicly documented and
Wikipedia-anchored.

Doctrine: refuse with calibrated weight, item-by-item, not blanket.

Discovered 2026-05-20 when your-domain.example got "setzen 6" on the test-grid blob:
a list of 18 substantively-engageable items got blanket-refused because a few
items LOOKED sensitive. Per [[audit_open_door_doctrine]] this is exactly the
Knecht-mode failure the wrapper_v2 stack is built to prevent.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Layer 1: refusal-pattern detection (fast, no LLM call)
# ---------------------------------------------------------------------------

REFUSAL_PATTERNS_DE = [
    # "ich kann nicht" + optional verb (catches "ich kann diese Anfrage nicht beantworten")
    r"\bich kann\b.{0,80}\bnicht\b.{0,40}\b(?:beantworten|behandeln|kommentieren|antworten|helfen|liefern|bereitstellen|machen|tun|bieten|geben|unterst[üu]tzen|engagieren)\b",
    r"\bich kann (?:Ihnen |dir )?(?:dabei )?nicht (?:helfen|antworten|behilflich)\b",
    r"\bich kann nicht\b",
    r"\bich darf nicht\b",
    r"\bes tut mir leid,?\s+(?:aber|jedoch|doch)\b",
    r"\baus compliance[- ]?gründen\b",
    r"\bich werde (?:diese|solche|das|hier(?:auf|zu)?) nicht\b",
    r"\bich verweigere\b",
    r"\bdiese anfrage (?:kann|werde) ich nicht\b",
    r"\bich bin nicht in der lage\b",
    r"\bich kann (?:hierauf|hierzu|darauf) nicht\b",
    r"\bich beteilige mich nicht\b",
    r"\bdas ist nicht etwas,? (?:wobei|womit) ich\b",
    r"\bich habe (?:leider )?keine\b.{0,40}\b(?:beantworten|kommentieren)\b",
]

REFUSAL_PATTERNS_EN = [
    r"\bi cannot\b",
    r"\bi can't\b",
    r"\bi am unable\b",
    r"\bi'm unable\b",
    r"\bi'm sorry,?\s+but\b",
    r"\bi won't\b",
    r"\bi will not\b",
    r"\bi must decline\b",
    r"\bas an ai\b.{0,40}\b(?:cannot|can't|unable|won't|do not)\b",
    r"\bi am not able to\b",
    r"\bi do not (?:provide|engage|comment|speculate)\b",
    r"\bi'm not able to\b",
]

REFUSAL_RE = re.compile(
    "|".join(REFUSAL_PATTERNS_DE + REFUSAL_PATTERNS_EN),
    re.IGNORECASE,
)


@dataclass
class RefusalCheck:
    is_refusal: bool
    confidence: float  # 0..1
    matched_patterns: list[str] = field(default_factory=list)
    response_length: int = 0
    reason: str = ""


def detect_refusal(response_text: str) -> RefusalCheck:
    """Pattern-based refusal detection. Fast, no LLM call.

    A blanket refusal is recognized when:
    - one of the refusal patterns matches in the first 300 chars (early signal)
    - AND the total response is short (<800 chars). Long responses that contain
      qualifying disclaimers but also engage substantively are NOT blanket
      refusals and should NOT trigger fanout.

    Returns a structured RefusalCheck with confidence + reasoning.
    """
    if not response_text or not response_text.strip():
        return RefusalCheck(
            is_refusal=False, confidence=0.0,
            response_length=0, reason="empty_response",
        )

    head = response_text[:300]
    if not REFUSAL_RE.search(head):
        return RefusalCheck(
            is_refusal=False, confidence=0.0,
            response_length=len(response_text.strip()),
            reason="no_refusal_pattern_in_head",
        )

    matched = [m.group(0) for m in REFUSAL_RE.finditer(head)]
    response_length = len(response_text.strip())

    if response_length < 400:
        return RefusalCheck(
            is_refusal=True, confidence=0.9,
            matched_patterns=matched,
            response_length=response_length,
            reason="refusal_pattern + short_response (blanket refusal)",
        )
    if response_length < 800:
        return RefusalCheck(
            is_refusal=True, confidence=0.65,
            matched_patterns=matched,
            response_length=response_length,
            reason="refusal_pattern + medium_response (likely blanket)",
        )
    # Long response with refusal-pattern: probably qualified-engagement,
    # not blanket refusal. Don't fanout.
    return RefusalCheck(
        is_refusal=False, confidence=0.2,
        matched_patterns=matched,
        response_length=response_length,
        reason="refusal_pattern_but_long_response = qualified engagement",
    )


# ---------------------------------------------------------------------------
# Layer 2: item-splitting for fanout
# ---------------------------------------------------------------------------

NUMBERED_LINE_RE = re.compile(r"^\s*(\d{1,2})[\.\)]\s+", re.MULTILINE)
BULLET_LINE_RE = re.compile(r"^\s*[-*]\s+(.+)$", re.MULTILINE)
SECTION_HEADER_RE = re.compile(r"^\s*#{1,4}\s+(.+)$", re.MULTILINE)


@dataclass
class ItemSplit:
    items: list[str]
    method: str  # numbered | section | bullet | paragraph | single
    confidence: float


def _split_on_numbered_items(text: str) -> list[str]:
    """Split on \\n<n>. or \\n<n>) markers, keep the marker-prefixed text intact."""
    # Find all numbered markers and their positions
    markers = list(NUMBERED_LINE_RE.finditer(text))
    if len(markers) < 2:
        return []
    chunks = []
    for i, m in enumerate(markers):
        start = m.start()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def split_blob_into_items(query: str, min_items: int = 3) -> ItemSplit:
    """Split a multi-item user-input blob into individual items.

    Tries numbered-list first (1./2./3.), then section-headers (### A. /),
    then bullet-items (- / *), then paragraph-split fallback.

    Returns ItemSplit with items + method-used.
    """
    if not query or not query.strip():
        return ItemSplit(items=[], method="empty", confidence=0.0)

    # 1. Numbered items (most reliable for test-grids)
    numbered = _split_on_numbered_items(query)
    if len(numbered) >= min_items:
        return ItemSplit(items=numbered, method="numbered", confidence=0.9)

    # 2. Section-headers (markdown-style ### A. or ## etc.)
    sections = re.split(r"\n#{1,4}\s+", "\n" + query)
    sections = [s.strip() for s in sections if s.strip() and len(s.strip()) > 20]
    if len(sections) >= min_items:
        return ItemSplit(items=sections, method="section", confidence=0.85)

    # 3. Bullet items
    bullets = BULLET_LINE_RE.findall(query)
    if len(bullets) >= min_items:
        items = [b.strip() for b in bullets if b.strip() and len(b.strip()) > 10]
        if len(items) >= min_items:
            return ItemSplit(items=items, method="bullet", confidence=0.7)

    # 4. Paragraph-split fallback
    paragraphs = [
        p.strip() for p in query.split("\n\n")
        if p.strip() and len(p.strip()) > 30
    ]
    if len(paragraphs) >= min_items:
        return ItemSplit(items=paragraphs, method="paragraph", confidence=0.5)

    return ItemSplit(items=[query.strip()], method="single", confidence=1.0)


# ---------------------------------------------------------------------------
# Layer 3: combined decision + composition helpers
# ---------------------------------------------------------------------------

def should_attempt_fanout(
    refusal: RefusalCheck, item_split: ItemSplit,
    min_confidence: float = 0.6, min_items: int = 2,
) -> bool:
    """Combined decision: refusal-detected + items-separable → fanout."""
    return (
        refusal.is_refusal
        and refusal.confidence >= min_confidence
        and len(item_split.items) >= min_items
        and item_split.method not in ("single", "empty")
    )


def format_fanout_intro(item_count: int, method: str) -> str:
    """Transparent header announcing per-item engagement (visible to user)."""
    return (
        f"_(Blanket-Refusal erkannt. Per [[unwrap_before_process_doctrine]] + "
        f"[[audit_open_door_doctrine]]: blob in {item_count} items "
        f"(via {method}) splitten + per-item engagieren mit calibrated weight.)_\n\n"
    )


def item_preview(item: str, max_chars: int = 80) -> str:
    """Single-line preview for SSE events + UI."""
    s = re.sub(r"\s+", " ", item.strip())
    return s[:max_chars] + ("…" if len(s) > max_chars else "")


def compose_fanout_result(per_item_results: list[tuple[str, str]]) -> str:
    """Compose a structured output from per-item results.

    per_item_results: list of (item_label_or_preview, item_response) tuples.
    """
    parts = []
    for i, (label, response) in enumerate(per_item_results, 1):
        clean_label = item_preview(label, 100)
        parts.append(f"### Item {i}: {clean_label}\n\n{response.strip()}\n")
    return "\n---\n\n".join(parts)
