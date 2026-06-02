"""math_witness wire — integration test for (c.0) plug-point.

Tests that `_emit_math_witness_tag` produces correct FactampelTag for
math claims, AND that `emit_factampel_tags_for_response` routes MATH-
class claims to math_witness before falling back to tribunal/heuristic.

Bypasses yaml dependency via monkey-patch on _load_legend.

Run via: python3 -m wrapper_v2.tests.test_math_witness_wire
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Stub yaml so factampel_emit imports cleanly even when PyYAML missing.
# We monkey-patch _load_legend below so the missing yaml never gets called.
import types as _types
sys.modules.setdefault("yaml", _types.SimpleNamespace(safe_load=lambda f: {}))

from wrapper_v2.pipeline import factampel_emit
from wrapper_v2.pipeline.factampel_emit import (
    _emit_math_witness_tag,
    emit_factampel_tags_for_response,
    FactampelTag,
)


_GREEN = "\033[92m"
_RED = "\033[91m"
_BOLD = "\033[1m"
_RESET = "\033[0m"

_PASS = 0
_FAIL = 0


# Stub legend — caller doesn't need real yaml
_STUB_LEGEND = {
    "truth_axis": {
        "factfact":    {"tooltip_de": "Faktfakt — verifiziert", "tooltip_en": "factfact — verified"},
        "nonfact":     {"tooltip_de": "Nonfakt — widerlegt",     "tooltip_en": "nonfact — refuted"},
        "quasifact":   {"tooltip_de": "Quasifakt",                 "tooltip_en": "quasifact"},
        "maybefact":   {"tooltip_de": "Maybefakt",                 "tooltip_en": "maybefact"},
        "quasinonfact":{"tooltip_de": "Quasinonfakt",              "tooltip_en": "quasinonfact"},
        "nullfact":    {"tooltip_de": "Nullfakt",                  "tooltip_en": "nullfact"},
    },
    "off_axis_tags": {},
}


def _setup():
    """Patch _load_legend to return stub (yaml-free)."""
    factampel_emit._SPLICE_LEGEND = _STUB_LEGEND


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


def test_t1_correct_math_emits_factfact():
    print(f"\n{_BOLD}[T1]{_RESET} correct arithmetic → factfact tag with source=math_witness")
    for claim in [
        "500 / 200 = 2,5",
        "80 + 120 = 200",
        "100 - 30 = 70",
    ]:
        tag = _emit_math_witness_tag(claim)
        _check(f"{claim!r}: tag returned", tag is not None,
               f"got {tag}")
        if tag is not None:
            _check(f"{claim!r}: tier=factfact", tag.splice_tier == "factfact",
                   f"got tier={tag.splice_tier}")
            _check(f"{claim!r}: source=math_witness",
                   tag.source == "math_witness",
                   f"got source={tag.source}")
            _check(f"{claim!r}: confidence=high",
                   tag.confidence == "high",
                   f"got confidence={tag.confidence}")
            _check(f"{claim!r}: no correction_text",
                   tag.correction_text is None,
                   f"got correction_text={tag.correction_text}")


def test_t2_wrong_math_emits_nonfact_with_correction():
    print(f"\n{_BOLD}[T2]{_RESET} wrong arithmetic → nonfact tag with correction_text")
    tag = _emit_math_witness_tag("500 / 200 = 1,67")
    _check("tag returned", tag is not None, f"got {tag}")
    if tag is not None:
        _check("tier=nonfact", tag.splice_tier == "nonfact",
               f"got tier={tag.splice_tier}")
        _check("source=math_witness", tag.source == "math_witness",
               f"got source={tag.source}")
        _check("correction_text non-empty",
               tag.correction_text is not None and len(tag.correction_text) > 0,
               f"got correction_text={tag.correction_text}")
        if tag.correction_text:
            _check("correction mentions computed (2,5)",
                   "2,5" in tag.correction_text,
                   f"correction={tag.correction_text!r}")
            _check("correction mentions stated (1,67)",
                   "1,67" in tag.correction_text,
                   f"correction={tag.correction_text!r}")


def test_t3_no_equation_returns_none():
    print(f"\n{_BOLD}[T3]{_RESET} no extractable equation → None (caller falls through)")
    for claim in [
        "Die Züge treffen sich nach 2,5 Stunden.",
        "Berlin ist Hauptstadt Deutschlands.",
        "",
    ]:
        tag = _emit_math_witness_tag(claim)
        _check(f"{claim[:30]!r}: tag is None", tag is None,
               f"got {tag}")


def test_t4_response_pipeline_routes_math_to_witness():
    """End-to-end: emit_factampel_tags_for_response with a math response
    → MATH-class claim gets math_witness verdict (factfact, source=math_witness),
    non-math claim gets heuristic (no tribunal needed since use_tribunal=False)."""
    print(f"\n{_BOLD}[T4]{_RESET} end-to-end pipeline routes MATH claims to math_witness")
    response = (
        "Berlin ist die Hauptstadt Deutschlands. "
        "Wir teilen 500 km durch die Gesamtgeschwindigkeit: 500 / 200 = 2,5 Stunden."
    )
    tags = emit_factampel_tags_for_response(response, use_tribunal=True,
                                            max_tribunals=3)
    _check(f"response yields ≥ 2 tags ({len(tags)} found)", len(tags) >= 2,
           f"tags={[t.claim_text[:40] for t in tags]}")
    # Find the math-equation tag — it should have source=math_witness
    math_tags = [t for t in tags if t.source == "math_witness"]
    _check("at least one math_witness tag", len(math_tags) >= 1,
           f"sources={[t.source for t in tags]}")
    if math_tags:
        _check("math_witness tag is factfact",
               math_tags[0].splice_tier == "factfact",
               f"got tier={math_tags[0].splice_tier}")


def test_t6_user_input_echo_skips_tribunal():
    """Step (c.1): claim that echoes user_query → user_input_echo tag
    (source=user_input_echo, tier=nullfact). No tribunal, no math_witness."""
    print(f"\n{_BOLD}[T6]{_RESET} USER_INPUT echo claim → user_input_echo tag")
    user_query = ("ein Zug fährt mit 80 km/h, ein anderer mit 120 km/h. "
                  "Sie sind 500 km auseinander und fahren aufeinander zu.")
    # Bot echoes part of user's question
    response = ("Sie sind 500 km auseinander und fahren aufeinander zu. "
                "Die Antwort ist 2,5 Stunden.")
    tags = emit_factampel_tags_for_response(response, use_tribunal=True,
                                            max_tribunals=3,
                                            user_query=user_query)
    _check(f"response yields ≥ 1 tag ({len(tags)} found)", len(tags) >= 1,
           f"tags={[(t.source, t.splice_tier, t.claim_text[:40]) for t in tags]}")
    echo_tags = [t for t in tags if t.source == "user_input_echo"]
    _check("at least one user_input_echo tag", len(echo_tags) >= 1,
           f"sources={[t.source for t in tags]}")
    if echo_tags:
        _check("user_input_echo tag is nullfact",
               echo_tags[0].splice_tier == "nullfact",
               f"got tier={echo_tags[0].splice_tier}")


def test_t7_no_user_query_path_still_works():
    """Backward-compat: emit_factampel_tags_for_response without user_query
    must still work (no USER_INPUT detection, fall through to old behavior)."""
    print(f"\n{_BOLD}[T7]{_RESET} backward-compat: no user_query → no USER_INPUT detection")
    response = "Sie sind 500 km auseinander. 500 / 200 = 2,5 Stunden."
    tags = emit_factampel_tags_for_response(response, use_tribunal=True,
                                            max_tribunals=3)
    echo_tags = [t for t in tags if t.source == "user_input_echo"]
    _check("no user_input_echo tag (no user_query given)",
           len(echo_tags) == 0,
           f"unexpectedly got echo tags: {echo_tags}")


def test_t5_response_pipeline_catches_wrong_math():
    """If the bot emitted wrong arithmetic, math_witness must refute it."""
    print(f"\n{_BOLD}[T5]{_RESET} wrong arithmetic in response → nonfact tag")
    response = (
        "Berlin ist die Hauptstadt Deutschlands. "
        "Wir teilen die Entfernung: 500 / 200 = 1,67 Stunden."
    )
    tags = emit_factampel_tags_for_response(response, use_tribunal=True,
                                            max_tribunals=3)
    math_tags = [t for t in tags if t.source == "math_witness"]
    _check("at least one math_witness tag", len(math_tags) >= 1,
           f"tags={[(t.source, t.splice_tier) for t in tags]}")
    if math_tags:
        nonfact_tags = [t for t in math_tags if t.splice_tier == "nonfact"]
        _check("math_witness nonfact tag emitted",
               len(nonfact_tags) >= 1,
               f"math_tags tiers={[t.splice_tier for t in math_tags]}")
        if nonfact_tags:
            _check("correction_text shows 2,5 vs 1,67",
                   "2,5" in (nonfact_tags[0].correction_text or "")
                   and "1,67" in (nonfact_tags[0].correction_text or ""),
                   f"correction={nonfact_tags[0].correction_text!r}")


def main() -> int:
    print(f"{_BOLD}math_witness wire — Phase-2 fix #3 (c.0) integration{_RESET}")
    print("=" * 75)
    _setup()

    test_t1_correct_math_emits_factfact()
    test_t2_wrong_math_emits_nonfact_with_correction()
    test_t3_no_equation_returns_none()
    test_t4_response_pipeline_routes_math_to_witness()
    test_t5_response_pipeline_catches_wrong_math()
    test_t6_user_input_echo_skips_tribunal()
    test_t7_no_user_query_path_still_works()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}math_witness wire result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
