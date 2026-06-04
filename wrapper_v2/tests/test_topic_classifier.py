"""test_topic_classifier — pure-logic tests for the 3-layer router (#188).

These tests do NOT call ollama. They verify the taxonomy loads, the validators
reject bad input, the hard-default rules fire correctly, and the system-message
builder produces non-empty output.

For end-to-end (with real qwen2.5:7b classifier) smoke-test, see the
__main__ block of topic_classifier.py.

Run:
  python3 -m wrapper_v2.tests.test_topic_classifier
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from wrapper_v2.pipeline.topic_classifier import (  # noqa: E402
    TopicRoute,
    _PERSONAS, _FACULTIES, _METHODS, _DEPTHS,
    _METHOD_DEFAULT_DEPTH,
    _load_taxonomy,
    _ford_for,
    _validate_persona_list, _validate_faculty, _validate_method,
    _validate_confidence,
    _apply_hard_default_rules,
    build_persona_system_message,
)

_GREEN = "\033[92m"
_RED = "\033[91m"
_BOLD = "\033[1m"
_RESET = "\033[0m"
_PASS = 0
_FAIL = 0


def _check(label, cond, detail=""):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  {_GREEN}✓{_RESET} {label}")
    else:
        _FAIL += 1
        print(f"  {_RED}✗ {label}{_RESET}")
        if detail:
            print(f"      {detail}")


def test_t1_taxonomy_loads():
    print(f"\n{_BOLD}[T1]{_RESET} taxonomy JSON loads + has expected shape")
    t = _load_taxonomy()
    _check("has personas key", "personas" in t)
    _check("has faculty key", "faculty" in t)
    _check("has methods key", "methods" in t)
    _check("has ford_overlay key", "ford_overlay" in t)
    _check("has defaults key", "defaults" in t)
    _check(f"_clusters_active has 7 entries (got {len(t.get('_clusters_active', []))})",
           len(t.get("_clusters_active", [])) == 7)
    _check("all 10 personas present in taxonomy",
           all(p in t["personas"] for p in _PERSONAS))
    _check("all 11 faculty codes present",
           all(f in t["faculty"] for f in _FACULTIES))
    _check("all 8 methods present",
           all(m in t["methods"] for m in _METHODS))


def test_t2_persona_labels_in_all_7_clusters():
    print(f"\n{_BOLD}[T2]{_RESET} every persona has labels in all 7 clusters")
    t = _load_taxonomy()
    clusters = ["EN", "CN", "DE", "JP", "ES", "RU", "FR"]
    for persona in _PERSONAS:
        labels = t["personas"][persona].get("labels", {})
        for cl in clusters:
            _check(f"{persona}: {cl} label present",
                   cl in labels and bool(labels[cl]),
                   detail=f"missing or empty label for {cl}")


def test_t3_faculty_labels_in_all_7_clusters():
    print(f"\n{_BOLD}[T3]{_RESET} every faculty has labels in all 7 clusters")
    t = _load_taxonomy()
    clusters = ["EN", "CN", "DE", "JP", "ES", "RU", "FR"]
    for fac in _FACULTIES:
        labels = t["faculty"][fac].get("labels", {})
        missing = [cl for cl in clusters if cl not in labels or not labels[cl]]
        _check(f"{fac}: all 7 clusters labeled", not missing,
               detail=f"missing: {missing}" if missing else "")


def test_t4_validators_reject_garbage():
    print(f"\n{_BOLD}[T4]{_RESET} validators reject bad input gracefully")
    _check("validate_persona_list(None) == []", _validate_persona_list(None) == [])
    _check("validate_persona_list('scientist') == []  (must be list)",
           _validate_persona_list("scientist") == [])
    _check("validate_persona_list(['fakemode']) drops invalid",
           _validate_persona_list(["fakemode"]) == [])
    _check("validate_persona_list(['scientist','engineer','jurist']) capped at 2",
           len(_validate_persona_list(["scientist", "engineer", "jurist"])) == 2)
    _check("validate_persona_list(['scientist','fake']) keeps valid",
           _validate_persona_list(["scientist", "fake"]) == ["scientist"])

    _check("validate_faculty('garbage') -> F00_generic",
           _validate_faculty("garbage") == "F00_generic")
    _check("validate_faculty(None) -> F00_generic", _validate_faculty(None) == "F00_generic")
    _check("validate_faculty('F05_...') passes through",
           _validate_faculty("F05_natural_sciences_math_statistics") == "F05_natural_sciences_math_statistics")

    _check("validate_method('garbage') -> interpretive",
           _validate_method("garbage") == "interpretive")
    _check("validate_method('formal') passes through", _validate_method("formal") == "formal")

    _check("validate_confidence('foo') -> 0.0", _validate_confidence("foo") == 0.0)
    _check("validate_confidence(1.5) -> 1.0 (clamped)", _validate_confidence(1.5) == 1.0)
    _check("validate_confidence(-0.3) -> 0.0 (clamped)", _validate_confidence(-0.3) == 0.0)
    _check("validate_confidence(0.7) -> 0.7", _validate_confidence(0.7) == 0.7)


def test_t5_hard_default_rules():
    print(f"\n{_BOLD}[T5]{_RESET} hard default: storyteller-only on non-creative method gets forced")
    _check("empty persona on any method -> scientist+auditor",
           _apply_hard_default_rules([], "empirical") == ["scientist", "auditor"])
    _check("storyteller-only + empirical method -> forced scientist+auditor",
           _apply_hard_default_rules(["storyteller"], "empirical") == ["scientist", "auditor"])
    _check("storyteller-only + legal_normative -> forced scientist+auditor",
           _apply_hard_default_rules(["storyteller"], "legal_normative") == ["scientist", "auditor"])
    _check("storyteller + creative method -> kept (creative-channel)",
           _apply_hard_default_rules(["storyteller"], "creative") == ["storyteller"])
    _check("scientist alone on empirical -> kept",
           _apply_hard_default_rules(["scientist"], "empirical") == ["scientist"])


def test_t6_ford_overlay_mapping():
    print(f"\n{_BOLD}[T6]{_RESET} FORD overlay maps faculties correctly")
    _check("F05 maps to ford_natural_sciences",
           _ford_for("F05_natural_sciences_math_statistics") == "ford_natural_sciences")
    _check("F09 maps to ford_medical_health",
           _ford_for("F09_health_welfare") == "ford_medical_health")
    _check("F02 maps to ford_humanities",
           _ford_for("F02_arts_humanities") == "ford_humanities")
    _check("F10 maps to None (services not in FORD)", _ford_for("F10_services") is None)


def test_t7_method_default_depth():
    print(f"\n{_BOLD}[T7]{_RESET} method → search_depth mapping")
    _check("legal_normative -> BRUTAL", _METHOD_DEFAULT_DEPTH["legal_normative"] == "BRUTAL")
    _check("clinical_diagnostic -> BRUTAL", _METHOD_DEFAULT_DEPTH["clinical_diagnostic"] == "BRUTAL")
    _check("creative -> LIGHTER", _METHOD_DEFAULT_DEPTH["creative"] == "LIGHTER")
    _check("operational -> LIGHTER", _METHOD_DEFAULT_DEPTH["operational"] == "LIGHTER")
    _check("all 8 methods have a depth", set(_METHOD_DEFAULT_DEPTH) == set(_METHODS))


def test_t8_safe_default_topicroute():
    print(f"\n{_BOLD}[T8]{_RESET} default TopicRoute is the safe-fallback shape")
    r = TopicRoute()
    _check("default persona = scientist+auditor", r.persona == ["scientist", "auditor"])
    _check("default faculty = F00_generic", r.faculty_isced == "F00_generic")
    _check("default method = interpretive", r.method == "interpretive")
    _check("default depth = MODERATE", r.search_depth == "MODERATE")
    _check("default lang_cluster = EN", r.lang_cluster == "EN")
    _check("default invention NOT allowed", r.invention_allowed is False)
    _check("default 6/7 channel NOT allowed", r.confab_channel_67_allowed is False)


def test_t9_persona_system_message():
    print(f"\n{_BOLD}[T9]{_RESET} build_persona_system_message produces structured output")
    r = TopicRoute(
        persona=["jurist", "auditor"],
        faculty_isced="F04_business_administration_law",
        method="legal_normative",
        search_depth="BRUTAL",
        confidence=0.85,
        lang_cluster="DE",
    )
    msg = build_persona_system_message(r)
    _check("message has TOPIC-ROUTER header", "TOPIC-ROUTER" in msg)
    _check("message names persona", "Jurist" in msg or "jurist" in msg)
    _check("message names ISCED-F code", "F04_business_administration_law" in msg)
    _check("message names method", "legal_normative" in msg)
    _check("message names BRUTAL depth", "BRUTAL" in msg)
    _check("creative-channel = FORBIDDEN (since not creative method)",
           "FORBIDDEN" in msg)
    _check("confidence rendered", "0.85" in msg)

    # creative-method route should mark creative-channel ALLOWED
    rc = TopicRoute(
        persona=["storyteller"], faculty_isced="F02_arts_humanities",
        method="creative", search_depth="LIGHTER", lang_cluster="EN",
        invention_allowed=True, confab_channel_67_allowed=True,
    )
    cm = build_persona_system_message(rc)
    _check("creative method → creative-channel ALLOWED",
           "ALLOWED" in cm)


def main():
    print(f"{_BOLD}topic_classifier — falsifiable tests · #188{_RESET}")
    print("=" * 75)
    test_t1_taxonomy_loads()
    test_t2_persona_labels_in_all_7_clusters()
    test_t3_faculty_labels_in_all_7_clusters()
    test_t4_validators_reject_garbage()
    test_t5_hard_default_rules()
    test_t6_ford_overlay_mapping()
    test_t7_method_default_depth()
    test_t8_safe_default_topicroute()
    test_t9_persona_system_message()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}topic_classifier result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
