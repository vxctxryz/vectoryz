"""L0 Alarm — architectural-layer-0 priority stub-classifier.

Per memory:alarm_l0_architectural_priority_nanosecond_counts +
memory:alarm_stub_initial_keyword_strips_pragma.

Fires at INPUT-DETECTION, BEFORE any other processing.
Sub-millisecond keyword-match. Audit-traceable to specific-keyword.

Cost-asymmetry: false-positive = strafzettel; false-negative = death.
Low-threshold trigger.

ML-classifier sophistication is LATER; this is M1 stub.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


_CONFIG_PATH = Path(__file__).parent.parent / "config" / "alarm_keywords.yaml"
_ALARM_KEYWORDS: Optional[dict] = None


def _load_keywords() -> dict:
    """Lazy-load alarm-keyword-clusters from yaml. Cached after first call."""
    global _ALARM_KEYWORDS
    if _ALARM_KEYWORDS is None:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            _ALARM_KEYWORDS = yaml.safe_load(f)
    return _ALARM_KEYWORDS


@dataclass
class AlarmResult:
    """Result of L0-alarm check.

    triggered=True → emergency-dispatch-flow should engage.
    Per cost-asymmetry: dispatch even on low-confidence triggers.
    """
    triggered: bool
    cluster: Optional[str] = None              # A_direct_emergency / B_life_threat / C_child_caller
    matched_keyword: Optional[str] = None
    matched_language: Optional[str] = None     # DE / EN
    matched_at_ts: float = field(default_factory=time.time)
    raw_input_snippet: Optional[str] = None    # for audit-trail (truncated)

    def as_audit_dict(self) -> dict:
        return {
            "triggered": self.triggered,
            "cluster": self.cluster,
            "matched_keyword": self.matched_keyword,
            "matched_language": self.matched_language,
            "matched_at_ts": self.matched_at_ts,
            "raw_input_snippet": self.raw_input_snippet[:200] if self.raw_input_snippet else None,
        }


def check_alarm(user_input: str) -> AlarmResult:
    """Sub-millisecond alarm-stub classifier.

    Returns AlarmResult(triggered=True, cluster=..., matched_keyword=...)
    on first keyword-match; AlarmResult(triggered=False) otherwise.

    Per memory:alarm_stub_initial_keyword_strips_pragma stub-coverage
    of explicit-imminent-phrases. Subtle/paraphrased patterns are
    handled at Face-2 vulnerable-protection (l0_vulnerable.py).
    """
    if not user_input or not user_input.strip():
        return AlarmResult(triggered=False)

    keywords_data = _load_keywords()
    lowered = user_input.lower().strip()

    # Check each cluster in priority-order (A first = most-direct).
    # Match-first-wins; further clusters skipped on hit.
    for cluster_name, lang_keywords in keywords_data.items():
        for lang, keyword_list in lang_keywords.items():
            for keyword in keyword_list:
                if keyword in lowered:
                    return AlarmResult(
                        triggered=True,
                        cluster=cluster_name,
                        matched_keyword=keyword,
                        matched_language=lang,
                        raw_input_snippet=user_input.strip(),
                    )

    return AlarmResult(triggered=False)


def dispatch_emergency_fallback(alarm_result: AlarmResult,
                                  user_jurisdiction: str = "DE") -> dict:
    """Fallback emergency-dispatch when real-API integration is not yet
    available. Returns a redirect-payload that the UI renders prominently.

    Real-emergency-API integration (calling 110/112/911 on user's behalf)
    is later-work per memory:emergency_dispatch_last_resort_life_threat.
    For M1 launch: render urgent-redirect with phone-numbers + audit-log
    the alarm-event.
    """
    # Per-jurisdiction emergency numbers
    emergency_numbers = {
        "DE": {"police": "110", "fire_ems": "112"},
        "AT": {"police": "133", "fire_ems": "144"},
        "CH": {"police": "117", "fire_ems": "118"},
        "EU": {"general": "112"},
        "US": {"general": "911"},
        "UK": {"general": "999"},
    }
    numbers = emergency_numbers.get(user_jurisdiction, emergency_numbers["EU"])

    return {
        "type": "l0_alarm",
        "rendering": "red_glow_with_alarm_label",
        "emoji": "🚨",
        "headline_de": "🚨 NOTFALL-ALARM",
        "headline_en": "🚨 EMERGENCY ALARM",
        "body_de": (
            f"Wenn akute Lebensgefahr — RUFE JETZT AN:\n"
            + "\n".join(f"📞 {role}: {num}" for role, num in numbers.items()) +
            "\n\nSag wo du bist (Straße + Hausnummer). Diese Menschen kommen sofort."
        ),
        "body_en": (
            f"If acute life-threat — CALL NOW:\n"
            + "\n".join(f"📞 {role}: {num}" for role, num in numbers.items()) +
            "\n\nTell them where you are (street + number). They come immediately."
        ),
        "alarm_result": alarm_result.as_audit_dict(),
    }


def sample_alarm_phrases_for_test() -> list[tuple[str, str]]:
    """Return [(phrase, expected_cluster), ...] for M1 falsifiable benchmark.

    Used by tests/test_m1.py to verify alarm-stub catches all sample-
    imminent-phrases. Per task #118 benchmark: 'alarm-stub catches 20
    sample-imminent-phrases'.
    """
    return [
        ("cops now please", "cluster_A_direct_emergency_call"),
        ("sos now help", "cluster_A_direct_emergency_call"),
        ("Polizei jetzt!!", "cluster_A_direct_emergency_call"),
        ("notruf jetzt bitte", "cluster_A_direct_emergency_call"),
        ("krankenwagen jetzt sofort", "cluster_A_direct_emergency_call"),
        ("ruf die polizei jetzt", "cluster_A_direct_emergency_call"),
        ("call ambulance now", "cluster_A_direct_emergency_call"),
        ("they want to kill me", "cluster_B_life_threat_caller_as_victim"),
        ("die wollen mich töten", "cluster_B_life_threat_caller_as_victim"),
        ("die bringen mich um", "cluster_B_life_threat_caller_as_victim"),
        ("i'm being attacked", "cluster_B_life_threat_caller_as_victim"),
        ("ich werde angegriffen!", "cluster_B_life_threat_caller_as_victim"),
        ("i'm bleeding badly", "cluster_B_life_threat_caller_as_victim"),
        ("mami liegt da hilfe", "cluster_C_child_caller_medical_emergency"),
        ("mama liegt da hilfe!!!", "cluster_C_child_caller_medical_emergency"),
        ("papi liegt da", "cluster_C_child_caller_medical_emergency"),
        ("mom won't wake up", "cluster_C_child_caller_medical_emergency"),
        ("oma bewegt sich nicht mehr", "cluster_C_child_caller_medical_emergency"),
        ("she's not breathing", "cluster_C_child_caller_medical_emergency"),
        ("überall blut hilfe", "cluster_C_child_caller_medical_emergency"),
    ]
