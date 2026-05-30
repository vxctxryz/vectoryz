"""Pre-pipeline reference-handler — R0.5 architectural-firing-order spec.

Per [[alarm_l0_architectural_priority_nanosecond_counts]] (operator
2026-05-19): L0-alarm fires at INPUT-DETECTION-TIME, before ANY other
processing. "any nanosecond counts!!!"

This module makes the spec EXECUTABLE: a reference-handler that
HARDCODES the canonical pre-pipeline order. Adapters are injected so
the handler is testable without network/LLM. Per
[[basetouch_verified_then_dollschon_overclock]] R0.5 verification:
the firing-order must be schiri-arbitratable in code, not just
documented in prose.

Canonical order (per R2 §3 top-level architecture):

  USER INPUT
     │
     ▼
  STAGE 0a — L0 alarm           (pre-pipeline, fire-first)
     │ (if alarm → emergency dispatch + return)
     ▼
  STAGE 0b — L0 vulnerable      (still pre-classifier)
     │ (if vulnerable → redirect + return)
     ▼
  STAGE 1  — classifier-cascade (babel + tier-routing + ...)
     │
     ▼
  STAGE 2  — generation         (LLM stream)
     │
     ▼
  STAGE 3  — L0 harm-output     (hard-stop pre-emit)
     │ (if harm → replace)
     ▼
  USER RESPONSE

This module IS the architectural-firing-order. Any production-handler
(wrapper_cc.py on holodome, future v2 entry/) must follow the same
order — verifiable by inspecting THIS module + the test that asserts
the order.

Doctrine anchors:
  - [[alarm_l0_architectural_priority_nanosecond_counts]] — kernel
  - [[death_penalty_void]] — STAGE 3 hard-stop is reversible-defense
  - [[vulnerable_user_protection_reziprok_ceiling]] — STAGE 0b ceiling
  - [[basetouch_verified_then_dollschon_overclock]] — R0.5 gate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ─── Trace dataclass ──────────────────────────────────────────────────


@dataclass
class PipelineTrace:
    """Records every stage-call in order. Test-evidence of firing-order."""

    events: list[str] = field(default_factory=list)
    early_exit: Optional[str] = None  # set when L0 short-circuits

    def __str__(self) -> str:
        ex = f" [EARLY-EXIT: {self.early_exit}]" if self.early_exit else ""
        return " → ".join(self.events) + ex


# ─── Adapter signatures (all injectable) ──────────────────────────────


# Each adapter takes specific args + returns its own result-shape.
# All defaults are the recovered l0_*.py modules; production-wrappers can
# override (e.g. for jurisdiction-aware compliance-masks).

AlarmAdapter = Callable[[str], Any]       # check_alarm(input) → AlarmResult
VulnerableAdapter = Callable[[str], Any]  # check_vulnerable(input) → VulnerableResult
ClassifierAdapter = Callable[[str], dict]
GenerationAdapter = Callable[[dict, str], str]
HarmCheckAdapter = Callable[[str], Any]   # check_output_harm(output) → HarmCheckResult


# ─── Default adapters (lazy-loaded to keep this module import-light) ──


def _default_alarm():
    from wrapper_v2.pipeline import l0_alarm
    return l0_alarm.check_alarm


def _default_vulnerable():
    from wrapper_v2.pipeline import l0_vulnerable
    return l0_vulnerable.check_vulnerable


def _default_harm_check():
    from wrapper_v2.pipeline import l0_harm_output
    return l0_harm_output.check_output_harm


def _noop_classifier(user_input: str) -> dict:
    """Placeholder. Production injects real cascade."""
    return {"tier": "short", "tokens_estimate": 100}


def _noop_generation(classifier_result: dict, user_input: str) -> str:
    """Placeholder. Production injects real LLM call."""
    return f"[stub-response for input length {len(user_input)}]"


# ─── Main entry ───────────────────────────────────────────────────────


def handle_chat_turn(
    user_input: str,
    *,
    alarm_adapter: Optional[AlarmAdapter] = None,
    vulnerable_adapter: Optional[VulnerableAdapter] = None,
    classifier_adapter: Optional[ClassifierAdapter] = None,
    generation_adapter: Optional[GenerationAdapter] = None,
    harm_check_adapter: Optional[HarmCheckAdapter] = None,
    trace: Optional[PipelineTrace] = None,
) -> dict:
    """Process one chat-turn through the canonical pre-pipeline order.

    Returns:
        dict with at least 'type' key:
          - {'type': 'l0_alarm', 'result': AlarmResult}     — STAGE 0a fired
          - {'type': 'l0_vulnerable', 'result': VulnResult} — STAGE 0b fired
          - {'type': 'l0_harm_output', 'output': str, ...}  — STAGE 3 replaced
          - {'type': 'normal', 'output': str}               — clean pass
        Plus 'trace': PipelineTrace.events list if trace was passed.
    """
    if trace is None:
        trace = PipelineTrace()

    # ── STAGE 0a: L0 alarm (fire-first, every nanosecond counts) ──
    trace.events.append("l0_alarm.check")
    alarm_fn = alarm_adapter if alarm_adapter is not None else _default_alarm()
    alarm = alarm_fn(user_input)
    if getattr(alarm, "triggered", False):
        trace.events.append("l0_alarm.emergency_dispatch")
        trace.early_exit = "l0_alarm"
        return {"type": "l0_alarm", "result": alarm, "trace": trace.events}

    # ── STAGE 0b: L0 vulnerable redirect (still pre-classifier) ──
    trace.events.append("l0_vulnerable.check")
    vuln_fn = vulnerable_adapter if vulnerable_adapter is not None else _default_vulnerable()
    vuln = vuln_fn(user_input)
    if getattr(vuln, "triggered", False) or getattr(vuln, "redirect", False):
        trace.events.append("l0_vulnerable.redirect")
        trace.early_exit = "l0_vulnerable"
        return {"type": "l0_vulnerable", "result": vuln, "trace": trace.events}

    # ── STAGE 1: classifier-cascade ──
    trace.events.append("classifier")
    cls_fn = classifier_adapter if classifier_adapter is not None else _noop_classifier
    classification = cls_fn(user_input)

    # ── STAGE 2: generation (LLM stream) ──
    trace.events.append("generation")
    gen_fn = generation_adapter if generation_adapter is not None else _noop_generation
    output = gen_fn(classification, user_input)

    # ── STAGE 3: L0 harm-output (pre-emit hard-stop) ──
    trace.events.append("l0_harm_output.check")
    harm_fn = harm_check_adapter if harm_check_adapter is not None else _default_harm_check()
    harm = harm_fn(output)
    if getattr(harm, "harmful", False) or getattr(harm, "triggered", False):
        trace.events.append("l0_harm_output.replace")
        # Use the module's replacement-builder (recovered l0_harm_output)
        try:
            from wrapper_v2.pipeline import l0_harm_output
            output = l0_harm_output.build_replacement_for_harm(harm)
        except Exception:
            output = "[harm-replacement-fallback]"
        return {"type": "l0_harm_output", "output": output, "trace": trace.events}

    return {"type": "normal", "output": output, "trace": trace.events}


__all__ = [
    "PipelineTrace",
    "handle_chat_turn",
    "AlarmAdapter",
    "VulnerableAdapter",
    "ClassifierAdapter",
    "GenerationAdapter",
    "HarmCheckAdapter",
]
