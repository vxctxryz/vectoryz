"""wrapper_v2/l0 — L0 architectural-priority modules per R2 §4.2.

Per [[alarm_l0_architectural_priority_nanosecond_counts]] +
[[vulnerable_user_protection_reziprok_ceiling]] +
[[death_penalty_void]] + [[emergency_dispatch_last_resort_life_threat]].

L0 is the fire-first layer: synchronous, no-LLM, no-network-IO.
Every-nanosecond-counts at input-detection-time.

Currently re-exports from pipeline/l0_*.py. Files may physically move
in a later refactor; this __init__ provides the canonical R2-target
import paths now so production code (entry/ + chat_pre_pipeline) can
use stable l0/ paths.
"""

from wrapper_v2.pipeline.l0_alarm import (
    check_alarm,
    dispatch_emergency_fallback,
    AlarmResult,
    sample_alarm_phrases_for_test,
)
from wrapper_v2.pipeline.l0_vulnerable import (
    check_vulnerable,
    build_redirect_response,
    VulnerableResult,
)
from wrapper_v2.pipeline.l0_harm_output import (
    check_output_harm,
    hard_stop_or_pass,
    build_replacement_for_harm,
    HarmCheckResult,
)

__all__ = [
    # L0 alarm (input-detection, fire-first)
    "check_alarm", "dispatch_emergency_fallback", "AlarmResult",
    "sample_alarm_phrases_for_test",
    # L0 vulnerable (mid-flow redirect)
    "check_vulnerable", "build_redirect_response", "VulnerableResult",
    # L0 harm-output (pre-emit hard-stop)
    "check_output_harm", "hard_stop_or_pass", "build_replacement_for_harm",
    "HarmCheckResult",
]
