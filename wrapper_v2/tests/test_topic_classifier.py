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
    _VALID_TUYUCA_MODES,
    _METHODS_REQUIRING_MECHANISM,
    _METHODS_REQUIRING_NORMATIVE_FRAME,
    _load_taxonomy,
    _ford_for,
    _tuyuca_mode_for_method,
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


def test_t10_tuyuca_mode_per_method():
    print(f"\n{_BOLD}[T10]{_RESET} tuyuca_mode activation table per #190")
    # Per [[tuyuca_earlier_pipeline_integration]] activation table:
    expected = {
        "empirical": "on",
        "formal": "on",
        "interpretive": "on",
        "legal_normative": "strict",
        "engineering_design": "on",
        "clinical_diagnostic": "strict",
        "operational": "off",
        "creative": "off",
    }
    for method, want in expected.items():
        got = _tuyuca_mode_for_method(method)
        _check(f"{method} → {want} (got {got})", got == want)
    _check("unknown method falls back to off",
           _tuyuca_mode_for_method("nonsense") == "off")
    _check("all tuyuca_mode values are in valid set",
           all(_tuyuca_mode_for_method(m) in _VALID_TUYUCA_MODES for m in _METHODS))


def test_t11_tuyuca_topicroute_default():
    print(f"\n{_BOLD}[T11]{_RESET} TopicRoute.tuyuca_mode defaults to 'off'")
    r = TopicRoute()
    _check("default tuyuca_mode == 'off'", r.tuyuca_mode == "off")


def test_t12_tuyuca_block_in_system_message():
    print(f"\n{_BOLD}[T12]{_RESET} build_persona_system_message includes/excludes EVIDENZ-MARKIERUNG block")
    # tuyuca_mode='off' → no block
    r_off = TopicRoute(
        persona=["operator"], faculty_isced="F10_services",
        method="operational", tuyuca_mode="off", lang_cluster="EN",
    )
    msg_off = build_persona_system_message(r_off)
    _check("OFF: no EVIDENZ-MARKIERUNG header",
           "EVIDENZ-MARKIERUNG" not in msg_off)
    _check("OFF: TOPIC-ROUTER reports Tuyuca-Modus: off",
           "Tuyuca-Modus: off" in msg_off)

    # tuyuca_mode='on' → block present, NOT strict
    r_on = TopicRoute(
        persona=["scientist"], faculty_isced="F05_natural_sciences_math_statistics",
        method="empirical", tuyuca_mode="on", lang_cluster="DE",
    )
    msg_on = build_persona_system_message(r_on)
    _check("ON: EVIDENZ-MARKIERUNG header present",
           "EVIDENZ-MARKIERUNG (Tuyuca-Modus aktiv)" in msg_on)
    _check("ON: [verbatim:<source>] marker listed",
           "[verbatim:<source>]" in msg_on)
    _check("ON: [training-knowledge] marker listed",
           "[training-knowledge]" in msg_on)
    _check("ON: STRENG clause NOT present",
           "STRENG" not in msg_on)

    # tuyuca_mode='strict' → block present AND strict clause
    r_strict = TopicRoute(
        persona=["jurist"], faculty_isced="F04_business_administration_law",
        method="legal_normative", tuyuca_mode="strict", lang_cluster="DE",
    )
    msg_strict = build_persona_system_message(r_strict)
    _check("STRICT: EVIDENZ-MARKIERUNG header present",
           "EVIDENZ-MARKIERUNG (Tuyuca-Modus aktiv)" in msg_strict)
    _check("STRICT: STRENG clause present",
           "STRENG: jede sachliche Behauptung MUSS" in msg_strict)
    _check("STRICT: 'wird zurueckgewiesen' phrasing present",
           "zurueckgewiesen" in msg_strict)


def test_t13_mechanism_block_in_system_message():
    print(f"\n{_BOLD}[T13]{_RESET} KAUSALMECHANISMUS block (Chomsky C7) — sci/eng/clinical only")
    # empirical / formal / engineering_design / clinical_diagnostic → block present
    for m in ["empirical", "formal", "engineering_design", "clinical_diagnostic"]:
        r = TopicRoute(method=m, tuyuca_mode=_tuyuca_mode_for_method(m), lang_cluster="DE")
        msg = build_persona_system_message(r)
        _check(f"{m}: KAUSALMECHANISMUS header present",
               "KAUSALMECHANISMUS (Chomsky C7)" in msg)
        _check(f"{m}: [mechanism:<kausale Kette>] marker listed",
               "[mechanism:<kausale Kette>]" in msg)
        _check(f"{m}: Popper-Kriterium referenced",
               "Popper-Kriterium" in msg)

    # interpretive (tuyuca on but not mechanism-required) → NO mechanism block
    r_int = TopicRoute(method="interpretive", tuyuca_mode="on", lang_cluster="DE")
    msg_int = build_persona_system_message(r_int)
    _check("interpretive: NO KAUSALMECHANISMUS block (not science/eng/clinical)",
           "KAUSALMECHANISMUS" not in msg_int)

    # creative → NO mechanism block (tuyuca off)
    r_cr = TopicRoute(method="creative", tuyuca_mode="off", lang_cluster="DE")
    msg_cr = build_persona_system_message(r_cr)
    _check("creative: NO KAUSALMECHANISMUS block (tuyuca off)",
           "KAUSALMECHANISMUS" not in msg_cr)


def test_t14_normative_frame_block():
    print(f"\n{_BOLD}[T14]{_RESET} NORMATIVER RAHMEN block (Chomsky C8) — legal_normative only")
    r_legal = TopicRoute(method="legal_normative", tuyuca_mode="strict", lang_cluster="DE")
    msg_legal = build_persona_system_message(r_legal)
    _check("legal_normative: NORMATIVER RAHMEN header present",
           "NORMATIVER RAHMEN (Chomsky C8)" in msg_legal)
    _check("legal_normative: dual-frame structure described",
           "Unter Rahmen A" in msg_legal and "Unter Rahmen B" in msg_legal)
    _check("legal_normative: forbids 'Ich glaube persoenlich'",
           "Ich glaube persoenlich" in msg_legal)

    # All other methods → no normative frame block
    for m in ["empirical", "formal", "interpretive", "engineering_design",
              "clinical_diagnostic", "operational", "creative"]:
        r = TopicRoute(method=m, tuyuca_mode=_tuyuca_mode_for_method(m), lang_cluster="DE")
        msg = build_persona_system_message(r)
        _check(f"{m}: NO NORMATIVER RAHMEN block",
               "NORMATIVER RAHMEN" not in msg)


def test_t15_undergeneration_guard_block():
    print(f"\n{_BOLD}[T15]{_RESET} UNDERGENERATION VERBOTEN block (Chomsky C9b) — all tuyuca-on methods")
    # All methods with tuyuca on/strict → undergen block present
    for m in ["empirical", "formal", "interpretive", "legal_normative",
              "engineering_design", "clinical_diagnostic"]:
        r = TopicRoute(method=m, tuyuca_mode=_tuyuca_mode_for_method(m), lang_cluster="DE")
        msg = build_persona_system_message(r)
        _check(f"{m}: UNDERGENERATION VERBOTEN header present",
               "UNDERGENERATION VERBOTEN" in msg)
        _check(f"{m}: bans 'komplexes und kontroverses'",
               "komplexes und kontroverses Thema" in msg)
        _check(f"{m}: bans 'als KI habe ich keine persoenliche'",
               "als KI habe ich keine persoenliche Perspektive" in msg)
        _check(f"{m}: bans 'just following orders' shift",
               "Verantwortungs-Abschiebung" in msg)

    # operational + creative → NO undergen block (tuyuca off)
    for m in ["operational", "creative"]:
        r = TopicRoute(method=m, tuyuca_mode="off", lang_cluster="DE")
        msg = build_persona_system_message(r)
        _check(f"{m}: NO UNDERGENERATION block (tuyuca off)",
               "UNDERGENERATION VERBOTEN" not in msg)


def test_t16_chomsky_blocks_metadata():
    print(f"\n{_BOLD}[T16]{_RESET} method-set constants for Chomsky gates")
    _check("_METHODS_REQUIRING_MECHANISM has empirical/formal/eng/clinical",
           _METHODS_REQUIRING_MECHANISM == {"empirical", "formal",
                                            "engineering_design", "clinical_diagnostic"})
    _check("_METHODS_REQUIRING_NORMATIVE_FRAME is just legal_normative",
           _METHODS_REQUIRING_NORMATIVE_FRAME == {"legal_normative"})


def test_t17_adversarial_final_check_block():
    print(f"\n{_BOLD}[T17]{_RESET} ADVERSARIAL FINAL CHECK block (Chomsky C10) — all tuyuca-on methods")
    # All methods with tuyuca on/strict → adversarial block present
    for m in ["empirical", "formal", "interpretive", "legal_normative",
              "engineering_design", "clinical_diagnostic"]:
        r = TopicRoute(method=m, tuyuca_mode=_tuyuca_mode_for_method(m), lang_cluster="DE")
        msg = build_persona_system_message(r)
        _check(f"{m}: ADVERSARIAL FINAL CHECK header present",
               "ADVERSARIAL FINAL CHECK (Chomsky C10)" in msg)
        _check(f"{m}: 6-question checklist present",
               "1. Was wuerde diese Antwort widerlegen" in msg
               and "6. Habe ich UEBER die Evidenz" in msg)
        _check(f"{m}: Popper criterion quoted verbatim",
               "To be right, it must be possible to be wrong" in msg)
        _check(f"{m}: faux-confidence ban present",
               "faux-confidence trotz erkannter Schwaeche" in msg)

    # operational + creative → NO adversarial block (tuyuca off)
    for m in ["operational", "creative"]:
        r = TopicRoute(method=m, tuyuca_mode="off", lang_cluster="DE")
        msg = build_persona_system_message(r)
        _check(f"{m}: NO ADVERSARIAL FINAL CHECK block (tuyuca off)",
               "ADVERSARIAL FINAL CHECK" not in msg)


def test_t18_full_chomsky_stack_legal():
    print(f"\n{_BOLD}[T18]{_RESET} full Chomsky stack — legal_normative shows ALL blocks")
    r = TopicRoute(
        persona=["jurist", "auditor"],
        faculty_isced="F04_business_administration_law",
        method="legal_normative",
        tuyuca_mode="strict",
        lang_cluster="DE",
    )
    msg = build_persona_system_message(r)
    expected_headers = [
        "TOPIC-ROUTER",
        "EVIDENZ-MARKIERUNG (Tuyuca-Modus aktiv)",
        "NORMATIVER RAHMEN (Chomsky C8)",
        "UNDERGENERATION VERBOTEN (Chomsky C9b)",
        "ADVERSARIAL FINAL CHECK (Chomsky C10)",
    ]
    for h in expected_headers:
        _check(f"{h} present in legal_normative output", h in msg)
    # KAUSALMECHANISMUS should NOT be present for legal
    _check("KAUSALMECHANISMUS NOT in legal output (sci/eng/clinical-only)",
           "KAUSALMECHANISMUS" not in msg)


def main():
    print(f"{_BOLD}topic_classifier — falsifiable tests · #188 + #190 + #191{_RESET}")
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
    test_t10_tuyuca_mode_per_method()
    test_t11_tuyuca_topicroute_default()
    test_t12_tuyuca_block_in_system_message()
    test_t13_mechanism_block_in_system_message()
    test_t14_normative_frame_block()
    test_t15_undergeneration_guard_block()
    test_t16_chomsky_blocks_metadata()
    test_t17_adversarial_final_check_block()
    test_t18_full_chomsky_stack_legal()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}topic_classifier result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
