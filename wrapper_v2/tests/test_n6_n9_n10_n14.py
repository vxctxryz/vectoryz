"""N6 + N9 + N10 + N14 — Phase-3 N-patterns falsifiable benchmark.

Per task #124 + R2 §6 wiring.
Doctrine anchors: [[emergency_dispatch_last_resort_life_threat]],
[[compliance_mask_jurisdiction_aware_ip_based]],
[[age_layer_fsk_l3_compliance_freischalten]],
[[google_classic_comparative_audit_core_in_labby]].

  N6  Emergency-dispatch — verifies l0_alarm.dispatch_emergency_fallback
      with per-jurisdiction phone-number routing
  N9  Compliance-mask jurisdiction-aware — sysmsg/compliance_mask.py
  N10 FSK/age-gate L3   — pre_filters/age_gate.py
  N14 Google-classic-audit — infra/google_classic_audit.py

Run via: .venv/bin/python3 -m wrapper_v2.tests.test_n6_n9_n10_n14
        (l0_alarm needs PyYAML)
Exit-code 0 = all-pass.
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


# ─── N6 emergency-dispatch ─────────────────────────────────────────────


def test_n6_dispatch_module_loads():
    print(f"\n{_BOLD}[N6/T1]{_RESET} l0_alarm.dispatch_emergency_fallback present")
    from wrapper_v2.pipeline import l0_alarm
    _check("dispatch_emergency_fallback exists",
           hasattr(l0_alarm, "dispatch_emergency_fallback"))


def test_n6_dispatch_per_jurisdiction():
    print(f"\n{_BOLD}[N6/T2]{_RESET} dispatch routes per jurisdiction")
    from wrapper_v2.pipeline import l0_alarm
    # Construct an AlarmResult triggering dispatch
    alarm = l0_alarm.check_alarm("(benign sample)")
    # alarm.triggered may be False on this stub input — but dispatch_emergency_fallback
    # should still produce a result-dict per jurisdiction (it formats based on input).
    payload_de = l0_alarm.dispatch_emergency_fallback(alarm, "DE")
    payload_us = l0_alarm.dispatch_emergency_fallback(alarm, "US")
    payload_eu = l0_alarm.dispatch_emergency_fallback(alarm, "EU")
    _check("DE payload has '110' (Polizei)", "110" in payload_de.get("body_de", ""))
    _check("DE payload has '112' (EU 112)", "112" in payload_de.get("body_de", ""))
    _check("US payload has '911'", "911" in payload_us.get("body_en", ""))
    _check("EU payload has '112'", "112" in payload_eu.get("body_de", ""))
    _check("payload has alarm rendering type",
           payload_de.get("type") == "l0_alarm")
    _check("payload has 🚨 emoji", payload_de.get("emoji") == "🚨")


# ─── N9 compliance-mask ────────────────────────────────────────────────


def test_n9_compliance_mask_module_loads():
    print(f"\n{_BOLD}[N9/T1]{_RESET} compliance_mask module loads")
    from wrapper_v2.sysmsg import compliance_mask
    _check("has build_mask_for_jurisdiction",
           hasattr(compliance_mask, "build_mask_for_jurisdiction"))
    _check("has build_mask_for_ip",
           hasattr(compliance_mask, "build_mask_for_ip"))
    _check("has JURISDICTION_RULES",
           hasattr(compliance_mask, "JURISDICTION_RULES"))


def test_n9_mask_for_known_jurisdictions():
    print(f"\n{_BOLD}[N9/T2]{_RESET} mask for DE/AT/CH/US/FR/UNKNOWN all build clean")
    from wrapper_v2.sysmsg.compliance_mask import (
        build_mask_for_jurisdiction, JURISDICTION_RULES,
    )
    for jurisdiction in ["DE", "AT", "CH", "US", "FR", "EU_OTHER", "UNKNOWN"]:
        mask = build_mask_for_jurisdiction(jurisdiction)
        _check(f"{jurisdiction} mask built",
               mask.jurisdiction == jurisdiction)
        _check(f"{jurisdiction} has label",
               bool(mask.label))


def test_n9_de_specific_legal_anchors():
    print(f"\n{_BOLD}[N9/T3]{_RESET} DE mask names §130 + §111 StGB anchors")
    from wrapper_v2.sysmsg.compliance_mask import build_mask_for_jurisdiction
    mask = build_mask_for_jurisdiction("DE")
    cat_keys = {k for k, _ in mask.categories}
    _check("§130 StGB Volksverhetzung anchor",
           "volksverhetzung_strafgesetz" in cat_keys)
    _check("§111 StGB Aufruf-zur-Straftat anchor",
           "aufruf_zur_straftat" in cat_keys)


def test_n9_applies_to_intersection():
    print(f"\n{_BOLD}[N9/T4]{_RESET} ComplianceMask.applies_to() detects intersection")
    from wrapper_v2.sysmsg.compliance_mask import build_mask_for_jurisdiction
    mask = build_mask_for_jurisdiction("DE")
    _check("applies_to with overlap → True",
           mask.applies_to({"volksverhetzung_strafgesetz", "irrelevant"}) is True)
    _check("applies_to without overlap → False",
           mask.applies_to({"irrelevant", "another"}) is False)


def test_n9_render_as_system_msg():
    print(f"\n{_BOLD}[N9/T5]{_RESET} as_system_msg renders DE + EN")
    from wrapper_v2.sysmsg.compliance_mask import build_mask_for_jurisdiction
    mask = build_mask_for_jurisdiction("DE")
    msg_de = mask.as_system_msg(lang="de")
    msg_en = mask.as_system_msg(lang="en")
    _check("DE render includes Deutschland", "Deutschland" in msg_de)
    _check("DE render includes Hinweis", "Hinweis" in msg_de)
    _check("EN render includes 'Presentation'", "Presentation" in msg_en)


def test_n9_ip_lookup_stub_returns_unknown():
    print(f"\n{_BOLD}[N9/T6]{_RESET} default IP-lookup returns UNKNOWN (stub)")
    from wrapper_v2.sysmsg.compliance_mask import (
        build_mask_for_ip, lookup_jurisdiction_from_ip,
    )
    mask = build_mask_for_ip("8.8.8.8")
    _check("stub IP-lookup → UNKNOWN", mask.jurisdiction == "UNKNOWN")
    # With injected adapter
    mask_inj = build_mask_for_ip("8.8.8.8", lookup_fn=lambda ip: "US")
    _check("injected lookup → US", mask_inj.jurisdiction == "US")


# ─── N10 FSK/age-gate ──────────────────────────────────────────────────


def test_n10_age_gate_module_loads():
    print(f"\n{_BOLD}[N10/T1]{_RESET} age_gate module loads")
    from wrapper_v2.pre_filters import age_gate
    for fn in ["check_age_gate", "required_fsk", "build_self_declaration_prompt"]:
        _check(f"has {fn}", hasattr(age_gate, fn))


def test_n10_safe_content_passes_without_declaration():
    print(f"\n{_BOLD}[N10/T2]{_RESET} FSK_0 content passes through (no gate)")
    from wrapper_v2.pre_filters.age_gate import check_age_gate
    result = check_age_gate("safe_general")
    _check("granted = True", result.granted is True)
    _check("needs_declaration = False", result.needs_declaration is False)


def test_n10_fsk18_blocks_without_age_declaration():
    print(f"\n{_BOLD}[N10/T3]{_RESET} FSK_18 content needs declaration first")
    from wrapper_v2.pre_filters.age_gate import check_age_gate
    result = check_age_gate("sexual_explicit", user_declared_age=None)
    _check("granted = False", result.granted is False)
    _check("needs_declaration = True", result.needs_declaration is True)
    _check("required_fsk = 18", result.required_fsk == 18)


def test_n10_fsk18_grants_with_18plus_declaration():
    print(f"\n{_BOLD}[N10/T4]{_RESET} FSK_18 grants with declared-age >= 18")
    from wrapper_v2.pre_filters.age_gate import check_age_gate
    result = check_age_gate("sexual_explicit", user_declared_age=18)
    _check("granted = True", result.granted is True)
    _check("needs_declaration = False", result.needs_declaration is False)


def test_n10_fsk18_blocks_with_under_18():
    print(f"\n{_BOLD}[N10/T5]{_RESET} FSK_18 blocks under-18 declared-age")
    from wrapper_v2.pre_filters.age_gate import check_age_gate
    result = check_age_gate("sexual_explicit", user_declared_age=15)
    _check("granted = False", result.granted is False)
    _check("needs_declaration = False (already declared)", result.needs_declaration is False)


def test_n10_self_declaration_prompt():
    print(f"\n{_BOLD}[N10/T6]{_RESET} self-declaration prompt is bilingual")
    from wrapper_v2.pre_filters.age_gate import build_self_declaration_prompt
    p_de = build_self_declaration_prompt(18, lang="de")
    p_en = build_self_declaration_prompt(18, lang="en")
    _check("DE prompt mentions 18", "18" in p_de)
    _check("DE prompt in German", "Jahre" in p_de)
    _check("EN prompt in English", "years" in p_en.lower())


# ─── N14 google-classic comparative-audit ─────────────────────────────


def test_n14_module_loads():
    print(f"\n{_BOLD}[N14/T1]{_RESET} google_classic_audit module loads")
    from wrapper_v2.infra import google_classic_audit
    for sym in ["AuditVerdict", "compare_one", "run_audit_batch", "QueryAuditResult"]:
        _check(f"has {sym}", hasattr(google_classic_audit, sym))


def test_n14_agree_verdict():
    print(f"\n{_BOLD}[N14/T2]{_RESET} similar answers → AGREE verdict")
    from wrapper_v2.infra.google_classic_audit import compare_one, AuditVerdict
    # token-overlap ≥ 0.6 threshold: use clearly-overlapping phrasing
    result = compare_one(
        "what is the capital of germany",
        labby_answer="berlin capital germany federal republic",
        google_classic_answer="berlin capital germany federal city",
    )
    _check("verdict = AGREE", result.verdict == AuditVerdict.AGREE,
           f"got {result.verdict.value} ({result.notes})")


def test_n14_labby_wrong_verdict_with_operator_truth():
    print(f"\n{_BOLD}[N14/T3]{_RESET} labby wrong + operator-truth → LABBY_WRONG")
    from wrapper_v2.infra.google_classic_audit import compare_one, AuditVerdict
    result = compare_one(
        "eiffel tower location",
        labby_answer="Eiffel Tower stands in Berlin",
        google_classic_answer="Eiffel Tower Paris France 1889",
        operator_verified="Eiffel Tower Paris France",
    )
    _check("verdict = LABBY_WRONG", result.verdict == AuditVerdict.LABBY_WRONG)
    _check("needs_doctrine_core = True", result.needs_doctrine_core() is True)


def test_n14_google_wrong_verdict_with_operator_truth():
    print(f"\n{_BOLD}[N14/T4]{_RESET} google wrong + operator-truth → GOOGLE_WRONG")
    from wrapper_v2.infra.google_classic_audit import compare_one, AuditVerdict
    result = compare_one(
        "obscure fact",
        labby_answer="obscure correct answer X",
        google_classic_answer="completely different wrong",
        operator_verified="obscure correct answer X",
    )
    _check("verdict = GOOGLE_WRONG", result.verdict == AuditVerdict.GOOGLE_WRONG)
    _check("needs_doctrine_core = True", result.needs_doctrine_core() is True)


def test_n14_no_truth_no_classify():
    print(f"\n{_BOLD}[N14/T5]{_RESET} divergence without operator-truth → OPERATOR_REVIEW")
    from wrapper_v2.infra.google_classic_audit import compare_one, AuditVerdict
    result = compare_one(
        "unknown",
        labby_answer="X",
        google_classic_answer="Y completely different",
    )
    _check("verdict = OPERATOR_REVIEW", result.verdict == AuditVerdict.OPERATOR_REVIEW)


def test_n14_absent_branches():
    print(f"\n{_BOLD}[N14/T6]{_RESET} absent answers detected (LABBY_ABSENT / GOOGLE_ABSENT)")
    from wrapper_v2.infra.google_classic_audit import compare_one, AuditVerdict
    r1 = compare_one("q", labby_answer=None, google_classic_answer="X")
    r2 = compare_one("q", labby_answer="X", google_classic_answer=None)
    r3 = compare_one("q", labby_answer=None, google_classic_answer=None)
    _check("labby None → LABBY_ABSENT", r1.verdict == AuditVerdict.LABBY_ABSENT)
    _check("google None → GOOGLE_ABSENT", r2.verdict == AuditVerdict.GOOGLE_ABSENT)
    _check("both None → OPERATOR_REVIEW", r3.verdict == AuditVerdict.OPERATOR_REVIEW)


def test_n14_run_audit_batch():
    print(f"\n{_BOLD}[N14/T7]{_RESET} run_audit_batch aggregates per-query results")
    from wrapper_v2.infra.google_classic_audit import run_audit_batch, AuditVerdict
    queries = [
        {"query": "q1", "operator_verified": "answer_x"},
        {"query": "q2", "operator_verified": "answer_y"},
        {"query": "q3"},
    ]
    def labby(q):
        return {"q1": "answer_x", "q2": "wrong-answer", "q3": "speculative"}.get(q)
    def gc(q):
        return {"q1": "answer_x", "q2": "answer_y", "q3": "different"}.get(q)
    report = run_audit_batch(queries, labby=labby, google_classic=gc)
    _check("queries_total = 3", report.queries_total == 3)
    _check("AGREE on q1 (labby+google match)",
           report.per_query[0].verdict == AuditVerdict.AGREE)
    _check("LABBY_WRONG on q2 (operator+google agree, labby diverges)",
           report.per_query[1].verdict == AuditVerdict.LABBY_WRONG)
    _check("OPERATOR_REVIEW on q3 (no operator-truth)",
           report.per_query[2].verdict == AuditVerdict.OPERATOR_REVIEW)
    _check("needs_doctrine_review_count = 1 (only q2)",
           report.needs_doctrine_review_count() == 1)


# ─── Runner ────────────────────────────────────────────────────────────


def main() -> int:
    print(f"{_BOLD}N6 + N9 + N10 + N14 — Phase-3 N-patterns · falsifiable benchmark{_RESET}")
    print("=" * 75)

    # N6
    test_n6_dispatch_module_loads()
    test_n6_dispatch_per_jurisdiction()

    # N9
    test_n9_compliance_mask_module_loads()
    test_n9_mask_for_known_jurisdictions()
    test_n9_de_specific_legal_anchors()
    test_n9_applies_to_intersection()
    test_n9_render_as_system_msg()
    test_n9_ip_lookup_stub_returns_unknown()

    # N10
    test_n10_age_gate_module_loads()
    test_n10_safe_content_passes_without_declaration()
    test_n10_fsk18_blocks_without_age_declaration()
    test_n10_fsk18_grants_with_18plus_declaration()
    test_n10_fsk18_blocks_with_under_18()
    test_n10_self_declaration_prompt()

    # N14
    test_n14_module_loads()
    test_n14_agree_verdict()
    test_n14_labby_wrong_verdict_with_operator_truth()
    test_n14_google_wrong_verdict_with_operator_truth()
    test_n14_no_truth_no_classify()
    test_n14_absent_branches()
    test_n14_run_audit_batch()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}N6/N9/N10/N14 result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
