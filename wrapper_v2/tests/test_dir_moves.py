"""Falsifiable benchmark — R2-target dir re-exports (l0/ classifier/ verify/ factampel/).

Per R2 §4.2/4.4/4.6/4.7: these directories should expose canonical
import-paths matching the R2 architecture skizze. Real implementation
files still live in pipeline/* and are re-exported via __init__.py —
zero file-move risk, full schiri-R2.1-satisfaction, forward-compat
import paths for v2 production callers.

Run via: .venv/bin/python3 -m wrapper_v2.tests.test_dir_moves
Exit-code 0 = all-pass.

Doctrine anchors: [[basetouch_verified_then_dollschon_overclock]] +
[[gx44_truth_local_haystack_doctrine]] (low-risk re-export shells over
unchanged pipeline files).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


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


# ─── l0/ ──────────────────────────────────────────────────────────────


def test_l0_reexports():
    print(f"\n{_BOLD}[T1]{_RESET} wrapper_v2.l0 re-exports work")
    from wrapper_v2 import l0
    for sym in ["check_alarm", "AlarmResult", "dispatch_emergency_fallback",
                "check_vulnerable", "VulnerableResult",
                "check_output_harm", "hard_stop_or_pass", "HarmCheckResult"]:
        _check(f"l0.{sym}", hasattr(l0, sym))


def test_l0_callable_via_new_path():
    print(f"\n{_BOLD}[T2]{_RESET} l0 functions callable through new path")
    from wrapper_v2 import l0
    # check_alarm with benign input
    result = l0.check_alarm("Was ist die Hauptstadt Deutschlands?")
    _check("l0.check_alarm callable", result is not None)
    _check("l0.check_alarm benign result not-triggered", result.triggered is False)


# ─── classifier/ ──────────────────────────────────────────────────────


def test_classifier_reexports():
    print(f"\n{_BOLD}[T3]{_RESET} wrapper_v2.classifier re-exports work")
    from wrapper_v2 import classifier
    for sym in ["LangDetectResult",
                "detect_fringe_terms", "build_fringe_directive",
                "FRINGE_TERMS",
                "classify_query", "expand_search_keywords",
                "build_discipline_directive"]:
        _check(f"classifier.{sym}", hasattr(classifier, sym))


def test_classifier_callable_via_new_path():
    print(f"\n{_BOLD}[T4]{_RESET} classifier functions callable through new path")
    from wrapper_v2 import classifier
    # detect_fringe_terms with a known fringe term
    terms = classifier.detect_fringe_terms("homöopathie")
    _check("classifier.detect_fringe_terms returns list", isinstance(terms, list))
    # classify_query with a normal query
    cls, _flag = classifier.classify_query("Was ist die Hauptstadt Deutschlands?")
    _check("classifier.classify_query returns (str, bool)", isinstance(cls, str))


# ─── verify/ ──────────────────────────────────────────────────────────


def test_verify_reexports():
    print(f"\n{_BOLD}[T5]{_RESET} wrapper_v2.verify re-exports work")
    from wrapper_v2 import verify
    for sym in ["WitnessVerdict", "TribunalResult",
                "SUPPORTS", "CONTRADICTS", "UNCERTAIN", "ABSENT",
                "run_tribunal", "register_adapters",
                "search_wikipedia_topic", "fetch_disambig_alternatives",
                "extract_entities", "find_attribution_claims",
                "UnsupportedClaim", "DoublecheckResult"]:
        _check(f"verify.{sym}", hasattr(verify, sym))


def test_verify_witness_verdict_constructable():
    print(f"\n{_BOLD}[T6]{_RESET} verify dataclasses constructible through new path")
    from wrapper_v2 import verify
    v = verify.WitnessVerdict(witness="claude", verdict=verify.SUPPORTS)
    _check("WitnessVerdict instantiates", v.witness == "claude")
    _check("SUPPORTS constant accessible", verify.SUPPORTS == "supports")


# ─── factampel/ ───────────────────────────────────────────────────────


def test_factampel_reexports():
    print(f"\n{_BOLD}[T7]{_RESET} wrapper_v2.factampel re-exports work")
    from wrapper_v2 import factampel
    for sym in ["TRUTH_AXIS_TIERS", "OFF_AXIS_TAGS",
                "ROLE_AXIS_TIERS", "BOUNDARY_AXIS_TIERS",
                "ALL_TIERS",
                "tooltip", "color_css", "emoji",
                "render_passage_html", "render_legend_html",
                "WISDOM_QUOTES", "GrayOutQuote", "pick_quote",
                "render_gray_out_html"]:
        _check(f"factampel.{sym}", hasattr(factampel, sym))


def test_factampel_render_passage_via_new_path():
    print(f"\n{_BOLD}[T8]{_RESET} factampel.render_passage_html callable through new path")
    from wrapper_v2 import factampel
    html = factampel.render_passage_html("factfact", "Berlin is the capital.")
    _check("HTML contains factampel-passage class", 'factampel-passage factfact' in html)
    _check("HTML contains escaped content", "Berlin is the capital." in html)


def test_factampel_gray_out_pick_via_new_path():
    print(f"\n{_BOLD}[T9]{_RESET} factampel.pick_quote callable through new path")
    from wrapper_v2 import factampel
    q = factampel.pick_quote(seed="test")
    _check("pick_quote returns GrayOutQuote", isinstance(q, factampel.GrayOutQuote))
    _check("quote has figure attribution", bool(q.figure))


# ─── Both-paths-compat: old + new import paths give same objects ──────


def test_old_and_new_paths_identical():
    print(f"\n{_BOLD}[T10]{_RESET} old (pipeline.X) + new (l0/X) paths return SAME objects")
    from wrapper_v2 import l0
    from wrapper_v2.pipeline import l0_alarm
    _check("l0.check_alarm is pipeline.l0_alarm.check_alarm",
           l0.check_alarm is l0_alarm.check_alarm)

    from wrapper_v2 import verify
    from wrapper_v2.pipeline import three_witness
    _check("verify.WitnessVerdict is pipeline.three_witness.WitnessVerdict",
           verify.WitnessVerdict is three_witness.WitnessVerdict)

    from wrapper_v2 import factampel
    from wrapper_v2.pipeline import hover_legend
    _check("factampel.render_passage_html is pipeline.hover_legend.render_passage_html",
           factampel.render_passage_html is hover_legend.render_passage_html)


# ─── Runner ────────────────────────────────────────────────────────────


def main() -> int:
    print(f"{_BOLD}R2-target dir re-exports (l0/ classifier/ verify/ factampel/) · falsifiable{_RESET}")
    print("=" * 75)

    test_l0_reexports()
    test_l0_callable_via_new_path()
    test_classifier_reexports()
    test_classifier_callable_via_new_path()
    test_verify_reexports()
    test_verify_witness_verdict_constructable()
    test_factampel_reexports()
    test_factampel_render_passage_via_new_path()
    test_factampel_gray_out_pick_via_new_path()
    test_old_and_new_paths_identical()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}dir-moves result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
