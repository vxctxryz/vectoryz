"""Factampel-Emit — per-claim splice-tier emission.

Per memory:factlevel_splice_6band_and_google1998_test
+ memory:factampel_ui_sealed_first_wave (visual-spec sealed).

M1 stub: heuristic-rules (linguistic-markers in claim-text).
M2 (2026-05-19): three-witness tribunal layered ON TOP of the heuristic.
  - Off-axis tags (definitional/broken/performative) still come from heuristic
  - Truth-axis empirical claims: cache-lookup → tribunal → heuristic-fallback
  - Tribunal runs only when adapters are registered (production-mode)
  - Cache-first means warm-tribunal verdicts are sub-ms
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

# M2 imports (optional — only used when use_tribunal=True)
try:
    from wrapper_v2.pipeline import three_witness as _tribunal
    from wrapper_v2.infra import witness_cache as _cache
    _M2_AVAILABLE = True
except ImportError:
    _M2_AVAILABLE = False


_CONFIG_PATH = Path(__file__).parent.parent / "config" / "splice_legend.yaml"
_SPLICE_LEGEND: Optional[dict] = None


def _load_legend() -> dict:
    """Lazy-load splice-legend from yaml."""
    global _SPLICE_LEGEND
    if _SPLICE_LEGEND is None:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            _SPLICE_LEGEND = yaml.safe_load(f)
    return _SPLICE_LEGEND


# Heuristic markers per tier. Real classifier comes in M2 (with LLM-call
# + three-witness-test).

_FACTFACT_MARKERS = [
    r"\b(definitiv|sicher|nachweislich|eindeutig|bewiesen|dokumentiert)\b",
    r"\b(definitely|certainly|verifiable|verified|proven|documented)\b",
    r"\b(audit[-\s]?proof|unbestritten|cross[-\s]?camp[-\s]?(valid|shared))\b",
]

_QUASIFACT_MARKERS = [
    r"\b(stark\s+belegt|gut\s+belegt|wahrscheinlich|sehr\s+wahrscheinlich)\b",
    r"\b(strongly\s+supported|well[-\s]?supported|probably|very\s+likely)\b",
]

_MAYBEFACT_MARKERS = [
    r"\b(vielleicht|möglicherweise|umstritten|debattiert|kontrovers|gleichgewicht)\b",
    r"\b(maybe|perhaps|debated|controversial|contested|balanced|both\s+sides)\b",
]

_QUASINONFACT_MARKERS = [
    r"\b(stark\s+widerlegt|widerlegt|wahrscheinlich\s+(nicht|falsch))\b",
    r"\b(strongly\s+contradicted|probably\s+(not|false|wrong))\b",
]

_NONFACT_MARKERS = [
    r"\b(faktisch\s+(falsch|widerlegt)|nicht\s+(wahr|zutreffend)|definitiv\s+falsch)\b",
    r"\b(empirically\s+refuted|factually\s+(false|wrong)|definitely\s+(false|untrue))\b",
    r"\b(audit[-\s]?proof\s+(falsch|false))\b",
]

_NULLFACT_MARKERS = [
    r"\b(keine\s+evidenz|nicht\s+(verfügbar|bekannt|in\s+meinen\s+daten))\b",
    r"\b(ich\s+kann\s+das\s+nicht\s+(zuverlässig|verifizieren))\b",
    r"\b(no\s+evidence|cannot\s+(find|determine|verify)|not\s+in\s+my\s+data)\b",
    r"\b(i\s+can'?t\s+reliably\s+(confirm|verify))\b",
    r"\b(ehrlicher?\s+nicht[-\s]?befund|honest\s+not[-\s]?found)\b",
]

_DEFINITIONAL_MARKERS = [
    r"\b(per\s+definition|tautolog(ie|y)|wahr[-\s]?per[-\s]?form)\b",
    r"\b(by\s+definition|tautology|true\s+by\s+form)\b",
]

_PERFORMATIVE_MARKERS = [
    r"\b(ich\s+erkläre\s+hiermit|hereby\s+i\s+declare|by\s+this\s+act)\b",
    r"\b(es\s+gilt\s+verfügt|so\s+sei\s+es)\b",
]

_BROKEN_MARKERS = [
    r"\b(strukturell\s+ungültig|kategorienfehler|category\s+error)\b",
    r"\b(self[-\s]?contradicting|widerspruch|paradox)\b",
]


@dataclass
class FactampelTag:
    """Per-claim factampel tag emission."""
    claim_text: str
    splice_tier: str                      # factfact / quasifact / maybefact / quasinonfact / nonfact / nullfact / fyifact
    off_axis_tag: Optional[str] = None    # definitional / broken / performative
    qualifier_tags: list = field(default_factory=list)  # list of {type, value}
    confidence: str = "medium"            # low / medium / high
    tooltip_de: Optional[str] = None
    tooltip_en: Optional[str] = None
    emitted_at_ts: float = field(default_factory=time.time)
    # M2 additions: tribunal-source + correction-text + redundancy-flag
    source: str = "heuristic"             # heuristic / cache / tribunal
    correction_text: Optional[str] = None  # filled when tribunal=nonfact/quasinonfact
    witnesses: list = field(default_factory=list)  # list of witness-names consulted
    overrides_llm_hedge: bool = False     # True when claim has nullfact-marker but tribunal verified
    # Audit-the-reasoning extension (2026-05-19, operator-spec): tribunal exposes
    # plain-language reasoning critique + source-recommendations
    audit_comments: list = field(default_factory=list)       # ["Charakter mit Saenger verwechselt", ...]
    recommended_sources: list = field(default_factory=list)  # ["en.wikipedia.org/wiki/Turandot", ...]

    def as_sse_event(self) -> dict:
        """Format as SSE-emit-ready event-dict."""
        return {
            "type": "factampel_tag",
            "claim_text": self.claim_text,
            "splice_tier": self.splice_tier,
            "off_axis_tag": self.off_axis_tag,
            "qualifier_tags": self.qualifier_tags,
            "confidence": self.confidence,
            "tooltip_de": self.tooltip_de,
            "tooltip_en": self.tooltip_en,
            "ts": self.emitted_at_ts,
            "source": self.source,
            "correction_text": self.correction_text,
            "witnesses": self.witnesses,
            "overrides_llm_hedge": self.overrides_llm_hedge,
            "audit_comments": self.audit_comments,
            "recommended_sources": self.recommended_sources,
        }


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def classify_claim(claim_text: str) -> tuple[str, Optional[str], str]:
    """Heuristic-classifier: returns (splice_tier, off_axis_tag, confidence).

    M1 stub. Real classifier in M2 (LLM-call + three-witness).
    Priority-order: off-axis-tags > nullfact > nonfact > maybefact >
    quasinonfact > quasifact > factfact > default(quasifact).
    """
    if not claim_text or not claim_text.strip():
        return ("nullfact", None, "low")

    text = claim_text.lower().strip()

    # Off-axis-tags checked first (they trump truth-axis)
    if _matches_any(text, _BROKEN_MARKERS):
        return ("nullfact", "broken", "medium")
    if _matches_any(text, _DEFINITIONAL_MARKERS):
        return ("factfact", "definitional", "medium")
    if _matches_any(text, _PERFORMATIVE_MARKERS):
        return ("factfact", "performative", "medium")

    # Truth-axis priority-order
    if _matches_any(text, _NULLFACT_MARKERS):
        return ("nullfact", None, "high")
    if _matches_any(text, _NONFACT_MARKERS):
        return ("nonfact", None, "medium")
    if _matches_any(text, _QUASINONFACT_MARKERS):
        return ("quasinonfact", None, "medium")
    if _matches_any(text, _MAYBEFACT_MARKERS):
        return ("maybefact", None, "medium")
    if _matches_any(text, _FACTFACT_MARKERS):
        return ("factfact", None, "medium")
    if _matches_any(text, _QUASIFACT_MARKERS):
        return ("quasifact", None, "medium")

    # Default: nullfact (no evidence assignable) when no clear-signal.
    # Conservative-honest default per Hammwöhner-labrador-discipline:
    # when the heuristic sniffer finds no truth-marker, default to
    # "honest not-found" rather than confidence-claim quasifact.
    # Avoids false-trust-signal on unverified claims. Real classification
    # comes via M2 three-witness-test. Changed 2026-05-19 from quasifact
    # → nullfact after operator-observed drift (kringel-fing-tagged-as-supported).
    return ("nullfact", None, "low")


def classify_claim_with_tribunal(claim_text: str, timeout_s: float = 12.0) -> tuple:
    """M2 layered classifier: tribunal-verified verdict OVERRIDES heuristic.

    Returns:
        (splice_tier, off_axis_tag, confidence, tribunal_dict_or_None)

    Flow:
      1. Heuristic check off-axis-tags FIRST — they're not empirical questions
         (definitional/broken/performative trump tribunal).
      2. Cache lookup — return cached verdict if hit.
      3. Run tribunal (3 witnesses in parallel, bounded by timeout_s).
      4. If tribunal returns at-least-one-non-absent verdict → use it,
         store in cache.
      5. Else fall through to heuristic-marker scan (M1 behaviour).

    Safe when adapters not registered: tribunal returns all-ABSENT,
    we fall through to heuristic. Identical behaviour to M1 in that case.
    """
    if not claim_text or not claim_text.strip():
        return ("nullfact", None, "low", None)

    text = claim_text.lower().strip()

    # Step 1 — off-axis-tags trump tribunal (heuristic is the right tool here)
    if _matches_any(text, _BROKEN_MARKERS):
        return ("nullfact", "broken", "medium", None)
    if _matches_any(text, _DEFINITIONAL_MARKERS):
        return ("factfact", "definitional", "medium", None)
    if _matches_any(text, _PERFORMATIVE_MARKERS):
        return ("factfact", "performative", "medium", None)

    if not _M2_AVAILABLE:
        # M2 modules not importable — fall straight back to heuristic
        tier, off_axis, conf = classify_claim(claim_text)
        return (tier, off_axis, conf, None)

    # Step 2 — cache lookup
    try:
        cached = _cache.lookup(claim_text)
        if cached is not None:
            verdict_dict = cached.get("verdict") or {}
            if isinstance(verdict_dict, dict):
                verdict_dict = dict(verdict_dict)  # don't mutate cache-payload
                verdict_dict["from_cache"] = True
            return (
                cached["splice_tier"],
                cached.get("off_axis_tag"),
                cached.get("confidence", "medium"),
                verdict_dict,
            )
    except Exception:
        pass  # cache failure is non-fatal

    # Step 3 — run tribunal
    try:
        tribunal_result = _tribunal.run_tribunal(claim_text, timeout_s=timeout_s)
    except Exception:
        tribunal_result = None

    if tribunal_result is not None:
        non_absent = [v for v in tribunal_result.verdicts if v.verdict != _tribunal.ABSENT]
        if non_absent:
            tier = tribunal_result.final_tier
            conf = tribunal_result.tribunal_confidence
            tribunal_dict = _tribunal.tribunal_to_dict(tribunal_result)
            # Cache the verdict
            try:
                _cache.store(
                    claim_text, tier, None, conf, tribunal_result,
                    witnesses=[v.witness for v in non_absent],
                )
            except Exception:
                pass
            return (tier, None, conf, tribunal_dict)

    # Step 4 — fall back to heuristic
    tier, off_axis, conf = classify_claim(claim_text)
    return (tier, off_axis, conf, None)


def emit_factampel_tag(claim_text: str, use_tribunal: bool = False,
                       tribunal_timeout_s: float = 12.0) -> FactampelTag:
    """Per-claim emission. Classify + attach tooltip-content.

    Args:
        claim_text: the claim to tag
        use_tribunal: if True, run M2 three-witness tribunal (slower; requires
                      adapters registered via three_witness.register_adapters).
                      Default False → M1 heuristic only.
        tribunal_timeout_s: total wall-clock budget when use_tribunal=True
    """
    legend = _load_legend()

    correction_text: Optional[str] = None
    witnesses_list: list = []
    source = "heuristic"
    overrides_llm_hedge = False
    audit_comments_list: list = []
    recommended_sources_list: list = []

    if use_tribunal:
        splice_tier, off_axis_tag, confidence, tribunal_dict = \
            classify_claim_with_tribunal(claim_text, timeout_s=tribunal_timeout_s)
        if tribunal_dict is not None:
            source = "cache" if tribunal_dict.get("from_cache") else "tribunal"
            correction_text = tribunal_dict.get("correction_text")
            witnesses_list = [v.get("witness") for v in tribunal_dict.get("verdicts", [])
                             if v.get("verdict") != "absent"]
            audit_comments_list = tribunal_dict.get("audit_comments", []) or []
            recommended_sources_list = tribunal_dict.get("recommended_sources", []) or []
            # Redundancy-collapse: claim self-declares not-found via marker, but
            # tribunal verified empirically — the LLM-hedge is no longer
            # informative; flag so UI can render an "override" hint
            text_lc = (claim_text or "").lower()
            if _matches_any(text_lc, _NULLFACT_MARKERS) and splice_tier in ("factfact", "quasifact", "nonfact", "quasinonfact"):
                overrides_llm_hedge = True
    else:
        splice_tier, off_axis_tag, confidence = classify_claim(claim_text)

    # Lookup tooltip-content from sealed splice-legend
    tier_data = legend.get("truth_axis", {}).get(splice_tier, {})
    tooltip_de = tier_data.get("tooltip_de")
    tooltip_en = tier_data.get("tooltip_en")

    if off_axis_tag:
        off_axis_data = legend.get("off_axis_tags", {}).get(off_axis_tag, {})
        off_axis_tooltip_de = off_axis_data.get("tooltip_de")
        off_axis_tooltip_en = off_axis_data.get("tooltip_en")
        if off_axis_tooltip_de:
            tooltip_de = (tooltip_de or "") + "\n+ " + off_axis_tooltip_de
        if off_axis_tooltip_en:
            tooltip_en = (tooltip_en or "") + "\n+ " + off_axis_tooltip_en

    return FactampelTag(
        claim_text=claim_text,
        splice_tier=splice_tier,
        off_axis_tag=off_axis_tag,
        confidence=confidence,
        tooltip_de=tooltip_de,
        tooltip_en=tooltip_en,
        source=source,
        correction_text=correction_text,
        witnesses=witnesses_list,
        overrides_llm_hedge=overrides_llm_hedge,
        audit_comments=audit_comments_list,
        recommended_sources=recommended_sources_list,
    )


def split_into_claims(text: str) -> list[str]:
    """Split response-text into individual claims for per-claim tagging.

    2026-05-20 fix: don't split on date-patterns ("14. März"), common
    abbreviations ("z. B.", "i. e.", "u. a."), or initials ("J. F. Kennedy").
    These false-positive splits produce sentence-fragments that get evaluated
    as standalone claims, leading to nonsense Audit-CAB verdicts.
    """
    if not text or not text.strip():
        return []

    # German month names (after-period patterns)
    months = (
        r"Januar|Februar|März|April|Mai|Juni|Juli|August|September|"
        r"Oktober|November|Dezember|"
        r"Jan|Feb|Mär|Apr|Jun|Jul|Aug|Sep|Sept|Okt|Nov|Dez"
    )
    # Common German abbreviations (lowercased + capitalized variants)
    abbrev_after = r"(?:[BbWwDdZz]\.|[Bb][\s]?[zZ]\.|[uU][\s]?[aA]\.|[iI]\.[\s]?[eE]\.|[zZ]\.[\s]?[bB]\.)"

    # 2026-05-20: strip internal scaffolding-blocks BEFORE splitting.
    # navigatorBESTEFFORT decomposition + plenum-synthesis blocks are
    # meta-instructions that occasionally leak into user-visible text;
    # auditing them eats budget + produces nonsense verdicts.
    # 2026-05-20 evening: original `(?:.*?\n)*?` + DOTALL did NOT strip
    # (non-greedy nested-quantifier matched zero in DOTALL-mode); replaced
    # with explicit `[\s\S]*?` which robustly matches any-char-incl-newlines
    # non-greedily up to the lookahead.
    text = re.sub(
        r"\[navigatorBESTEFFORT-DEKOMPOSITION[^\]]*\][\s\S]*?(?=\n\n|\Z|Zur Anfrage:|Antwort:)",
        "",
        text.strip(),
    )
    # 2026-05-21: also strip closing-tag (the model has started emitting
    # both opening AND closing scaffolding-tags). Closing-tag standalone is
    # pure noise — no content, just XML-style envelope marker. Could appear
    # multiple times in one response (e.g. once at essay-end, once at end).
    text = re.sub(
        r"\[/navigatorBESTEFFORT-DEKOMPOSITION\]\s*",
        "",
        text,
    )
    text = re.sub(
        r"^\s*Beantworte sie in EINER[^\n]*\n",
        "",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"^\s*Bezug zwischen den Teilen[^\n]*\n",
        "",
        text,
        flags=re.MULTILINE,
    )

    # Strategy: split on [.!?]\s+UPPER, BUT exclude:
    #  (a) preceding digit + period + space + month-name (date: "14. März")
    #  (b) preceding single capital letter + period (initial: "J. F. Kennedy")
    #  (c) abbreviation followed by period
    # Use negative lookbehind for these patterns.
    # Build a regex that splits ONLY at real sentence-end:
    #  - Period after non-digit, non-single-uppercase-letter
    #  - Followed by whitespace + Uppercase letter
    #  - AND the next-following word isn't a month-name (to handle "14. März"
    #    cases that slip through)
    split_rx = re.compile(
        r'(?<=[.!?])\s+'                       # boundary: period + whitespace
        r'(?![' + r''.join(['a-zäöüß']) + r'])' # next char not lowercase (= sentence-start)
        r'(?=[A-ZÄÖÜ])'                         # next char is uppercase
    )
    raw_parts = split_rx.split(text.strip())

    # Post-merge: rejoin parts where the split was probably wrong (date-pattern
    # or abbreviation). Look at the join-boundary: if the previous part ends in
    # "digit + ." OR "single-letter + .", AND the next part starts with a known
    # month-name or short-form, merge them back.
    merged = []
    date_or_abbrev_end_rx = re.compile(r'(\b\d{1,2}\.|[A-Z][a-z]?\.|[A-ZÄÖÜ]\.)\s*$')
    month_start_rx = re.compile(r'^(' + months + r')\b')

    for part in raw_parts:
        if not part.strip():
            continue
        if merged and date_or_abbrev_end_rx.search(merged[-1]):
            # Previous part ends in date/abbrev marker — merge
            merged[-1] = merged[-1].rstrip() + " " + part.strip()
            continue
        if merged and month_start_rx.match(part.strip()):
            # Next part starts with a month-name → merge into previous
            merged[-1] = merged[-1].rstrip() + " " + part.strip()
            continue
        merged.append(part.strip())

    return [s for s in merged if s]


def emit_factampel_tags_for_response(response_text: str,
                                     use_tribunal: bool = False,
                                     max_tribunals: int = 3,
                                     tribunal_timeout_s: float = 12.0) -> list[FactampelTag]:
    """Process full response-text → list of per-claim factampel tags.

    Args:
        response_text: full LLM response
        use_tribunal: enable M2 tribunal-verification
        max_tribunals: hard cap on how many claims get tribunal-verified
                       per response (latency budget). Excess claims fall to
                       heuristic. Default 3 = covers most response shapes
                       without blowing wall-clock budget.
        tribunal_timeout_s: per-tribunal-call timeout

    Tribunal is applied to the FIRST N claims (sequentially in normal reading
    order). M3 may switch to importance-ranked-selection.
    """
    claims = split_into_claims(response_text)
    if not use_tribunal:
        return [emit_factampel_tag(c, use_tribunal=False) for c in claims]

    tags = []
    tribunal_budget = max_tribunals
    for c in claims:
        if tribunal_budget > 0:
            tag = emit_factampel_tag(c, use_tribunal=True,
                                     tribunal_timeout_s=tribunal_timeout_s)
            tribunal_budget -= 1
        else:
            tag = emit_factampel_tag(c, use_tribunal=False)
        tags.append(tag)
    return tags


# Env-based switch for production opt-in (read once at import; safe-default OFF)
USE_TRIBUNAL_DEFAULT = os.environ.get("WRAPPER_V2_TRIBUNAL", "").strip() == "1"
