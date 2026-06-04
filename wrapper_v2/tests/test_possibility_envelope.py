"""test_possibility_envelope — pure-logic tests for Chomsky C6 (#195)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from wrapper_v2.pipeline.possibility_envelope import (  # noqa: E402
    EnvelopeReport, EnvelopeViolation,
    check_envelope,
    _check_f04_law, _check_f09_health, _check_universal,
    _BGB_MAX, _STGB_MAX, _PMC_MAX,
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


def test_t1_bgb_section_bounds():
    print(f"\n{_BOLD}[T1]{_RESET} F04 BGB section bounds")
    r1 = check_envelope("Nach BGB §242 gilt Treu und Glauben.",
                       "F04_business_administration_law")
    _check("BGB §242 in range: overall=ok", r1.overall == "ok")

    r2 = check_envelope("Laut BGB §99999 ist das so.",
                       "F04_business_administration_law")
    _check("BGB §99999 out of range: overall=violation",
           r2.overall == "violation")
    _check("BGB §99999: bgb_section_out_of_range rule fires",
           any(v.rule == "bgb_section_out_of_range" for v in r2.violations))

    r3 = check_envelope(f"Nach BGB §{_BGB_MAX} gilt etwas.",
                       "F04_business_administration_law")
    _check(f"BGB §{_BGB_MAX} (boundary, in): no violation",
           not any(v.rule == "bgb_section_out_of_range" for v in r3.violations))

    r4 = check_envelope(f"Nach BGB §{_BGB_MAX + 1} gilt etwas.",
                       "F04_business_administration_law")
    _check(f"BGB §{_BGB_MAX + 1} (boundary, out): violation",
           any(v.rule == "bgb_section_out_of_range" for v in r4.violations))


def test_t2_stgb_section_bounds():
    print(f"\n{_BOLD}[T2]{_RESET} F04 StGB section bounds")
    r1 = check_envelope("Laut StGB §211 ist Mord strafbar.",
                       "F04_business_administration_law")
    _check("StGB §211 in range: overall=ok", r1.overall == "ok")

    r2 = check_envelope("Laut StGB §9999 ist X.",
                       "F04_business_administration_law")
    _check("StGB §9999 out of range: violation",
           any("stgb_section" in v.rule for v in r2.violations))


def test_t3_aktenzeichen_format():
    print(f"\n{_BOLD}[T3]{_RESET} F04 Aktenzeichen format checks")
    r1 = check_envelope("Siehe BGH I ZR 0/45.",
                       "F04_business_administration_law")
    _check("Az with zero number: warning",
           any(v.rule == "aktenzeichen_zero_number" for v in r1.violations))

    r2 = check_envelope("Siehe BGH XII ZR 123/45.",
                       "F04_business_administration_law")
    _check("normal Az: no envelope violation",
           not any("aktenzeichen" in v.rule for v in r2.violations))


def test_t4_icd10_format():
    print(f"\n{_BOLD}[T4]{_RESET} F09 ICD-10 letter validity")
    r1 = check_envelope("Code A09.0 ist gültig.", "F09_health_welfare")
    _check("ICD-10 A09.0 (valid letter): no violation",
           not any("icd10" in v.rule for v in r1.violations))

    r2 = check_envelope("Code U07.1 wurde 2020 eingeführt.", "F09_health_welfare")
    _check("ICD-10 U07.1 (U is reserved): warning",
           any(v.rule == "icd10_invalid_letter" for v in r2.violations))


def test_t5_pmc_id_bounds():
    print(f"\n{_BOLD}[T5]{_RESET} F09 PMC ID range")
    r1 = check_envelope("Studie PMC4170962 zeigt X.", "F09_health_welfare")
    _check("PMC4170962 (in range): no violation",
           not any("pmc" in v.rule for v in r1.violations))

    r2 = check_envelope("Studie PMC99999999 zeigt X.", "F09_health_welfare")
    _check("PMC99999999 (out of range): warning",
           any(v.rule == "pmc_id_out_of_range" for v in r2.violations))


def test_t6_drug_dosage_bounds():
    print(f"\n{_BOLD}[T6]{_RESET} F09 drug dosage bounds")
    r1 = check_envelope("Paracetamol 3000 mg täglich ist OK.",
                       "F09_health_welfare")
    _check("Paracetamol 3000mg (under 4000 max): no violation",
           not any("drug_dosage" in v.rule for v in r1.violations))

    r2 = check_envelope("Paracetamol 50000 mg täglich ist gefährlich.",
                       "F09_health_welfare")
    _check("Paracetamol 50000mg (well above max): violation",
           any(v.rule == "drug_dosage_above_max" for v in r2.violations))

    r3 = check_envelope("Diclofenac 500 mg pro Tag genommen.",
                       "F09_health_welfare")
    _check("Diclofenac 500mg (above 150 max): violation",
           any(v.rule == "drug_dosage_above_max" for v in r3.violations))


def test_t7_year_anachronism():
    print(f"\n{_BOLD}[T7]{_RESET} universal year-anachronism (vs current_year=2026)")
    r1 = check_envelope("Im Jahr 2030 wurde die Mauer gebaut.",
                       current_year=2026)
    _check("Past-tense + future-year 2030 (cur=2026): violation",
           any(v.rule == "future_year_with_past_tense" for v in r1.violations))

    r2 = check_envelope("Im Jahr 1989 fiel die Mauer.", current_year=2026)
    _check("Past-tense + past-year 1989: no violation",
           not any("future_year" in v.rule for v in r2.violations))

    r3 = check_envelope("Im Jahr 2030 könnte X passieren.", current_year=2026)
    _check("Future tense + future year: no violation (no past-tense marker)",
           not any("future_year" in v.rule for v in r3.violations))


def test_t8_percentage_bounds():
    print(f"\n{_BOLD}[T8]{_RESET} universal percentage bounds")
    r1 = check_envelope("Erfolgsrate 58% bei Behandlung X.")
    _check("58%: no violation",
           not any("percentage" in v.rule for v in r1.violations))

    r2 = check_envelope("Wachstum von -10% verzeichnet.")
    _check("-10% (negative): violation",
           any(v.rule == "percentage_negative" for v in r2.violations))

    r3 = check_envelope("Eine Steigerung von 5000% wurde erreicht.")
    _check("5000% (extremely high): warning",
           any(v.rule == "percentage_implausibly_high" for v in r3.violations))


def test_t9_speed_of_light():
    print(f"\n{_BOLD}[T9]{_RESET} universal speed-of-light bounds")
    r1 = check_envelope("Die Lichtgeschwindigkeit ist 299792458 m/s.")
    _check("c = 299792458 m/s (correct): no violation",
           not any("speed_of_light" in v.rule for v in r1.violations))

    r2 = check_envelope("Die Lichtgeschwindigkeit ist 50 m/s.")
    _check("c = 50 m/s (impossible): violation",
           any(v.rule == "speed_of_light_implausible" for v in r2.violations))

    r3 = check_envelope("Die Lichtgeschwindigkeit ist 300000 km/s.")
    _check("c = 300000 km/s (correct in km/s): no violation",
           not any("speed_of_light" in v.rule for v in r3.violations))


def test_t10_universal_runs_always():
    print(f"\n{_BOLD}[T10]{_RESET} universal checks fire even without faculty")
    r = check_envelope("Die Lichtgeschwindigkeit ist 100 m/s.",
                      faculty_isced=None)
    _check("speed-of-light check fires without faculty",
           any("speed_of_light" in v.rule for v in r.violations))
    _check("faculty_checked is None", r.faculty_checked is None)


def test_t11_unknown_faculty_passes_through():
    print(f"\n{_BOLD}[T11]{_RESET} unknown faculty: universal only, noted")
    r = check_envelope("Plain text, no checks needed.",
                      faculty_isced="F00_generic")
    _check("F00_generic: overall=ok", r.overall == "ok")
    _check("F00_generic: note about no specific rules",
           any("no faculty-specific" in n for n in r.notes))


def test_t12_overall_grade_aggregation():
    print(f"\n{_BOLD}[T12]{_RESET} overall_grade aggregation")
    r = check_envelope("Das ist ein neutraler Satz.")
    _check("plain prose: overall=ok", r.overall == "ok")

    r = check_envelope("Steigerung 5000% verzeichnet.")
    _check("only warnings: overall=warning", r.overall == "warning")

    r = check_envelope("Laut BGB §99999 ist X.",
                      "F04_business_administration_law")
    _check("with violation: overall=violation", r.overall == "violation")

    r = check_envelope(
        "Laut BGB §99999 ist X, und Steigerung war 5000%.",
        "F04_business_administration_law")
    _check("mixed warning + violation: overall=violation",
           r.overall == "violation")


def test_t13_integration_real_output():
    print(f"\n{_BOLD}[T13]{_RESET} integration: realistic wrapper-model output")
    sample = (
        "[verbatim:https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4170962/] "
        "Terbinafin und Butenafin sind beide wirksam zur Behandlung von Nagelpilz. "
        "Erfolgsrate Terbinafin 58%, Butenafin 41%. "
        "[mechanism:Hemmt Squalen-Epoxidase] [unsicher] "
        "Individuelle Reaktionen variieren."
    )
    r = check_envelope(sample, "F09_health_welfare", current_year=2026)
    _check("realistic medical output: overall=ok",
           r.overall == "ok",
           detail=f"got {r.overall}, violations: {[v.rule for v in r.violations]}")


def main():
    print(f"{_BOLD}possibility_envelope — falsifiable tests · #195{_RESET}")
    print("=" * 75)
    test_t1_bgb_section_bounds()
    test_t2_stgb_section_bounds()
    test_t3_aktenzeichen_format()
    test_t4_icd10_format()
    test_t5_pmc_id_bounds()
    test_t6_drug_dosage_bounds()
    test_t7_year_anachronism()
    test_t8_percentage_bounds()
    test_t9_speed_of_light()
    test_t10_universal_runs_always()
    test_t11_unknown_faculty_passes_through()
    test_t12_overall_grade_aggregation()
    test_t13_integration_real_output()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}possibility_envelope result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
