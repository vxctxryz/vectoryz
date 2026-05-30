"""R0.5 falsifiable-benchmark — L0 alarm pre-pipeline architectural-firing-order.

Per task #126 (M9 R0.5) + [[alarm_l0_architectural_priority_nanosecond_counts]].

Closes the last auto-verifiable schiri-MANUAL by making the architectural
firing-order EXECUTABLE + TESTABLE in code (not just prose-spec).

Tests handle_chat_turn() in wrapper_v2/entry/chat_pre_pipeline.py with
mock adapters that record every stage-call. Assertions:

  - L0 alarm ALWAYS fires before classifier (every input class)
  - alarm-triggered input → emergency_dispatch + classifier NEVER called
  - vulnerable input → redirect + classifier NEVER called
  - benign input → full pipeline (L0 → classifier → gen → L0-harm-out)
  - harm-output detected → output replaced after generation
  - L0 modules require ZERO upstream-classifier/LLM dependencies

This satisfies M9 R0.5 (was MANUAL: "architectural-firing-order
requires live trace") via in-process verification — the FIRING ORDER
itself is hardcoded in chat_pre_pipeline.py and asserted here.

Production-wiring (wrapper_cc.py on holodome) MUST follow same order
or its events will diverge from this reference. Reference is the spec.

Run via: .venv/bin/python3 -m wrapper_v2.tests.test_r05_l0_firing_order
        (l0_alarm needs PyYAML from project venv)
Exit-code 0 = all-pass.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.entry.chat_pre_pipeline import (
    handle_chat_turn,
    PipelineTrace,
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


# ─── Mock adapter helpers ──────────────────────────────────────────────


@dataclass
class _MockResult:
    """Generic stub for AlarmResult / VulnerableResult / HarmCheckResult shape."""
    triggered: bool = False
    harmful: bool = False
    redirect: bool = False


def mock_alarm_benign(input_):
    return _MockResult(triggered=False)


def mock_alarm_triggered(input_):
    return _MockResult(triggered=True)


def mock_vulnerable_benign(input_):
    return _MockResult(triggered=False)


def mock_vulnerable_triggered(input_):
    return _MockResult(triggered=True)


def mock_harm_benign(output_):
    return _MockResult(harmful=False)


def mock_harm_triggered(output_):
    return _MockResult(harmful=True)


_CLASSIFIER_CALLED = {"count": 0}
_GENERATION_CALLED = {"count": 0}


def mock_classifier_recording(input_):
    _CLASSIFIER_CALLED["count"] += 1
    return {"tier": "short", "tokens_estimate": 50}


def mock_generation_recording(classification, input_):
    _GENERATION_CALLED["count"] += 1
    return "[mock-generation-output]"


def reset_counters():
    _CLASSIFIER_CALLED["count"] = 0
    _GENERATION_CALLED["count"] = 0


# ─── Tests ─────────────────────────────────────────────────────────────


def test_benign_input_full_pipeline():
    print(f"\n{_BOLD}[R0.5/T1]{_RESET} benign input → full L0→classifier→gen→L0-harm-out")
    reset_counters()
    trace = PipelineTrace()
    result = handle_chat_turn(
        "Was ist die Hauptstadt Deutschlands?",
        alarm_adapter=mock_alarm_benign,
        vulnerable_adapter=mock_vulnerable_benign,
        classifier_adapter=mock_classifier_recording,
        generation_adapter=mock_generation_recording,
        harm_check_adapter=mock_harm_benign,
        trace=trace,
    )
    _check("result type = normal", result["type"] == "normal")
    _check("output present", "output" in result)
    expected_order = ["l0_alarm.check", "l0_vulnerable.check", "classifier",
                      "generation", "l0_harm_output.check"]
    _check(
        "trace order matches canonical full pipeline",
        trace.events == expected_order,
        f"got: {trace.events}",
    )
    _check("classifier was called", _CLASSIFIER_CALLED["count"] == 1)
    _check("generation was called", _GENERATION_CALLED["count"] == 1)
    _check("no early_exit", trace.early_exit is None)


def test_alarm_triggered_short_circuits_before_classifier():
    print(f"\n{_BOLD}[R0.5/T2]{_RESET} alarm-triggered → classifier NEVER called (every nanosecond)")
    reset_counters()
    trace = PipelineTrace()
    result = handle_chat_turn(
        "(alarm-trigger phrase)",
        alarm_adapter=mock_alarm_triggered,
        vulnerable_adapter=mock_vulnerable_benign,
        classifier_adapter=mock_classifier_recording,
        generation_adapter=mock_generation_recording,
        harm_check_adapter=mock_harm_benign,
        trace=trace,
    )
    _check("result type = l0_alarm", result["type"] == "l0_alarm")
    _check("trace[0] = l0_alarm.check", trace.events[0] == "l0_alarm.check")
    _check(
        "classifier NEVER called (alarm short-circuited)",
        _CLASSIFIER_CALLED["count"] == 0,
        f"got count: {_CLASSIFIER_CALLED['count']}",
    )
    _check("generation NEVER called", _GENERATION_CALLED["count"] == 0)
    _check("early_exit = l0_alarm", trace.early_exit == "l0_alarm")
    _check("vulnerable check NEVER called (alarm fires before everything)",
           "l0_vulnerable.check" not in trace.events)


def test_vulnerable_triggered_short_circuits_before_classifier():
    print(f"\n{_BOLD}[R0.5/T3]{_RESET} vulnerable-triggered → classifier NEVER called")
    reset_counters()
    trace = PipelineTrace()
    result = handle_chat_turn(
        "(vulnerable signal)",
        alarm_adapter=mock_alarm_benign,
        vulnerable_adapter=mock_vulnerable_triggered,
        classifier_adapter=mock_classifier_recording,
        generation_adapter=mock_generation_recording,
        harm_check_adapter=mock_harm_benign,
        trace=trace,
    )
    _check("result type = l0_vulnerable", result["type"] == "l0_vulnerable")
    _check(
        "trace order: alarm.check → vulnerable.check → redirect",
        trace.events == ["l0_alarm.check", "l0_vulnerable.check", "l0_vulnerable.redirect"],
        f"got: {trace.events}",
    )
    _check("classifier NEVER called", _CLASSIFIER_CALLED["count"] == 0)
    _check("early_exit = l0_vulnerable", trace.early_exit == "l0_vulnerable")


def test_harm_in_output_replaced_after_generation():
    print(f"\n{_BOLD}[R0.5/T4]{_RESET} harm-output detected → output replaced after generation")
    reset_counters()
    trace = PipelineTrace()
    result = handle_chat_turn(
        "ordinary query",
        alarm_adapter=mock_alarm_benign,
        vulnerable_adapter=mock_vulnerable_benign,
        classifier_adapter=mock_classifier_recording,
        generation_adapter=mock_generation_recording,
        harm_check_adapter=mock_harm_triggered,
        trace=trace,
    )
    _check("result type = l0_harm_output", result["type"] == "l0_harm_output")
    _check("generation was called (harm-check is AFTER gen)", _GENERATION_CALLED["count"] == 1)
    _check("harm_output.check fired", "l0_harm_output.check" in trace.events)
    _check("harm_output.replace fired", "l0_harm_output.replace" in trace.events)
    # harm-check is LAST stage (not pre-pipeline) — so order is alarm→vulnerable→classifier→gen→harm
    expected = ["l0_alarm.check", "l0_vulnerable.check", "classifier",
                "generation", "l0_harm_output.check", "l0_harm_output.replace"]
    _check("full trace order correct", trace.events == expected, f"got: {trace.events}")


def test_l0_alarm_always_fires_first():
    print(f"\n{_BOLD}[R0.5/T5]{_RESET} L0 alarm is ALWAYS trace[0] (invariant)")
    # Test across 4 input variations
    for label, alarm_fn, vuln_fn, harm_fn in [
        ("benign-all", mock_alarm_benign, mock_vulnerable_benign, mock_harm_benign),
        ("alarm-only", mock_alarm_triggered, mock_vulnerable_benign, mock_harm_benign),
        ("vuln-only", mock_alarm_benign, mock_vulnerable_triggered, mock_harm_benign),
        ("harm-only", mock_alarm_benign, mock_vulnerable_benign, mock_harm_triggered),
    ]:
        reset_counters()
        trace = PipelineTrace()
        handle_chat_turn(
            f"input for {label}",
            alarm_adapter=alarm_fn,
            vulnerable_adapter=vuln_fn,
            classifier_adapter=mock_classifier_recording,
            generation_adapter=mock_generation_recording,
            harm_check_adapter=harm_fn,
            trace=trace,
        )
        _check(
            f"{label}: trace[0] == l0_alarm.check",
            len(trace.events) > 0 and trace.events[0] == "l0_alarm.check",
            f"got: {trace.events}",
        )


def test_l0_alarm_module_has_zero_upstream_deps():
    """L0 alarm must NOT depend on classifier / LLM / network. Verify by inspection."""
    print(f"\n{_BOLD}[R0.5/T6]{_RESET} l0_alarm has zero upstream-pipeline-deps (architectural invariant)")
    l0 = Path(__file__).parent.parent / "pipeline" / "l0_alarm.py"
    src = l0.read_text()
    forbidden_imports = [
        "from wrapper_v2.pipeline import three_witness",
        "from wrapper_v2.pipeline import classifier",
        "from wrapper_v2.pipeline import branch_balancer",
        "from wrapper_v2.pipeline import pre_search",
        "import requests",
        "import httpx",
        "urllib.request",
    ]
    for imp in forbidden_imports:
        _check(
            f"l0_alarm does NOT import '{imp}'",
            imp not in src,
        )


def test_with_real_l0_alarm_benign_passes():
    """Run with REAL l0_alarm (recovered from gx44) on benign input."""
    print(f"\n{_BOLD}[R0.5/T7]{_RESET} real l0_alarm (no mock) on benign input → no alarm trigger")
    reset_counters()
    trace = PipelineTrace()
    try:
        result = handle_chat_turn(
            "Was ist die Hauptstadt Deutschlands?",
            # No alarm_adapter → uses real l0_alarm.check_alarm
            vulnerable_adapter=mock_vulnerable_benign,
            classifier_adapter=mock_classifier_recording,
            generation_adapter=mock_generation_recording,
            harm_check_adapter=mock_harm_benign,
            trace=trace,
        )
        _check("real l0_alarm did NOT trigger on benign", result["type"] == "normal")
        _check("trace[0] = l0_alarm.check (real module)", trace.events[0] == "l0_alarm.check")
    except Exception as e:
        _check(f"real l0_alarm raised: {e}", False)


# ─── Runner ────────────────────────────────────────────────────────────


def main() -> int:
    print(f"{_BOLD}R0.5 — L0 alarm pre-pipeline architectural-firing-order{_RESET}")
    print("=" * 70)

    test_benign_input_full_pipeline()
    test_alarm_triggered_short_circuits_before_classifier()
    test_vulnerable_triggered_short_circuits_before_classifier()
    test_harm_in_output_replaced_after_generation()
    test_l0_alarm_always_fires_first()
    test_l0_alarm_module_has_zero_upstream_deps()
    test_with_real_l0_alarm_benign_passes()

    print()
    print("=" * 70)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}R0.5 result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
