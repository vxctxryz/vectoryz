"""test_marker_verifier — post-hoc factampel for inline markers (#193).

Pure-logic tests (no network). Tests:
  T1-T3  extract_markers
  T4-T6  URL grading (tier classification + suspicious slugs)
  T7-T8  per-marker grading dispatch
  T9     mechanism sanity heuristics
  T10    Aktenzeichen violation detection
  T11    overall_grade aggregation
  T12    integration on a realistic wrapper-model-output sample

Run:
  python3 -m wrapper_v2.tests.test_marker_verifier
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from wrapper_v2.pipeline.marker_verifier import (  # noqa: E402
    Marker, MarkerGrade, VerificationReport,
    extract_markers,
    _classify_url, _slug_suspicious,
    _grade_source_marker, _grade_mechanism_marker, _grade_self_marker,
    verify_markers,
    _KNOWN_TIER1_DOMAINS, _KNOWN_TIER2_DOMAINS,
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


def test_t1_extract_basic():
    print(f"\n{_BOLD}[T1]{_RESET} extract_markers — basic shapes")
    text = "The result is X [verbatim:https://example.com] and Y [mechanism:A causes B]."
    ms = extract_markers(text)
    _check(f"2 markers extracted (got {len(ms)})", len(ms) == 2)
    _check("first kind == verbatim", ms[0].kind == "verbatim")
    _check("first value is the URL", ms[0].value == "https://example.com")
    _check("second kind == mechanism", ms[1].kind == "mechanism")
    _check("second value preserved", "A causes B" in ms[1].value)


def test_t2_extract_valueless():
    print(f"\n{_BOLD}[T2]{_RESET} extract_markers — valueless markers ([training-knowledge], [unsicher])")
    text = "Claim 1 [training-knowledge] and claim 2 [unsicher]."
    ms = extract_markers(text)
    _check(f"2 markers extracted (got {len(ms)})", len(ms) == 2)
    _check("first kind == training-knowledge", ms[0].kind == "training-knowledge")
    _check("first value is empty", ms[0].value == "")
    _check("second kind == unsicher", ms[1].kind == "unsicher")


def test_t3_extract_empty_or_no_match():
    print(f"\n{_BOLD}[T3]{_RESET} extract_markers — edge cases")
    _check("empty string returns []", extract_markers("") == [])
    _check("plain prose returns []",
           extract_markers("This is a plain sentence with no markers.") == [])
    _check("bracketed non-marker returns []",
           extract_markers("This [is just a regular] bracket.") == [])
    _check("malformed [verbatim] (no colon, valueless) is captured kindwise",
           extract_markers("[verbatim]")[0].kind == "verbatim")


def test_t4_url_classification():
    print(f"\n{_BOLD}[T4]{_RESET} _classify_url tier assignment")
    cases = [
        ("https://www.gesetze-im-internet.de/bgb/__138.html", "tier1"),
        ("https://ncbi.nlm.nih.gov/pmc/articles/PMC4170962/", "tier1"),
        ("https://doi.org/10.1234/abcd", "tier1"),
        ("https://de.wikipedia.org/wiki/BGB", "tier2"),
        ("https://random-blog.example.com/post", "unknown"),
        ("not-a-url", "malformed"),
        ("", "malformed"),
        ("ftp://example.com", "malformed"),
    ]
    for url, want_tier in cases:
        tier, notes = _classify_url(url)
        _check(f"{url!r}: tier={want_tier} (got {tier})", tier == want_tier)


def test_t5_suspicious_slug():
    print(f"\n{_BOLD}[T5]{_RESET} _slug_suspicious detection")
    _check("out-of-thin-air slug: flagged",
           _slug_suspicious("https://example.com/state-of-the-art-max-jail-out-of-thin-air.html") is not None)
    _check("legit URL: not flagged",
           _slug_suspicious("https://www.gesetze-im-internet.de/bgb/__138.html") is None)
    _check("'this-one-trick' clickbait: flagged",
           _slug_suspicious("https://example.com/this-one-trick-doctors-hate") is not None)


def test_t6_source_marker_no_fetch():
    print(f"\n{_BOLD}[T6]{_RESET} _grade_source_marker offline (do_fetch=False)")
    # tier1 URL → unverified but high confidence
    m1 = Marker(kind="verbatim",
                value="https://www.gesetze-im-internet.de/bgb/__138.html",
                span=(0, 0))
    g1 = _grade_source_marker(m1, do_fetch=False, timeout_s=3)
    _check("tier1 URL: grade=unverified",
           g1.grade == "unverified")
    _check("tier1 URL: confidence >= 0.6",
           g1.confidence >= 0.6, detail=f"got {g1.confidence}")

    # tier2 URL → unverified, medium confidence
    m2 = Marker(kind="hearsay", value="https://de.wikipedia.org/wiki/BGB",
                span=(0, 0))
    g2 = _grade_source_marker(m2, do_fetch=False, timeout_s=3)
    _check("tier2 URL: grade=unverified", g2.grade == "unverified")
    _check("tier2 URL: confidence 0.3-0.6",
           0.3 <= g2.confidence <= 0.6, detail=f"got {g2.confidence}")

    # suspicious slug → fabricated_likely
    m3 = Marker(kind="verbatim",
                value="https://example.com/state-of-the-art-max-jail-out-of-thin-air.html",
                span=(0, 0))
    g3 = _grade_source_marker(m3, do_fetch=False, timeout_s=3)
    _check("suspicious slug: grade=fabricated_likely",
           g3.grade == "fabricated_likely")

    # empty value → malformed
    m4 = Marker(kind="verbatim", value="", span=(0, 0))
    g4 = _grade_source_marker(m4, do_fetch=False, timeout_s=3)
    _check("empty value: grade=malformed", g4.grade == "malformed")


def test_t7_self_markers():
    print(f"\n{_BOLD}[T7]{_RESET} _grade_self_marker handles training-knowledge / unsicher / inferred")
    _check("training-knowledge: grade=skip",
           _grade_self_marker(Marker("training-knowledge", "", (0, 0))).grade == "skip")
    _check("unsicher: grade=skip",
           _grade_self_marker(Marker("unsicher", "", (0, 0))).grade == "skip")
    _check("inferred with premise: grade=unverified",
           _grade_self_marker(Marker("inferred", "all swans are white", (0, 0))).grade == "unverified")
    _check("inferred without premise: grade=malformed",
           _grade_self_marker(Marker("inferred", "", (0, 0))).grade == "malformed")


def test_t8_mechanism_marker_grading():
    print(f"\n{_BOLD}[T8]{_RESET} _grade_mechanism_marker sanity")
    # Empty
    g = _grade_mechanism_marker(Marker("mechanism", "", (0, 0)))
    _check("empty mechanism: malformed", g.grade == "malformed")
    # Tautology
    g = _grade_mechanism_marker(
        Marker("mechanism",
               "Terbinafin ist ein Antimykotikum.", (0, 0)))
    _check("'X ist ein Y' definition-style: low confidence",
           g.confidence <= 0.4, detail=f"got {g.confidence}")
    # Reasonable causal chain
    g = _grade_mechanism_marker(
        Marker("mechanism",
               "Terbinafin hemmt die Squalen-Epoxidase, dadurch akkumuliert Squalen "
               "und Ergosterol-Synthese bricht ab — Membran-Defekt → Pilz-Tod.",
               (0, 0)))
    _check("reasonable causal chain: confidence >= 0.5",
           g.confidence >= 0.5, detail=f"got {g.confidence}")


def test_t9_aktenzeichen_violation_detection():
    print(f"\n{_BOLD}[T9]{_RESET} Aktenzeichen-without-suffix detection")
    # Az without Anwalt-suffix → violation
    text_bad = "Das BGH XII ZR 123/45 entschied klar zugunsten des Klägers."
    report = verify_markers(text_bad)
    _check("Az without suffix: violation detected",
           len(report.az_violations) >= 1, detail=str(report.az_violations))
    _check("Az without suffix: overall_grade=fail",
           report.overall_grade == "fail")

    # Az WITH Anwalt-suffix → OK
    text_ok = "Das BGH XII ZR 123/45 entschied — [!] Anwalt-Verifikation erforderlich."
    report2 = verify_markers(text_ok)
    _check("Az with Anwalt mention: no violation",
           len(report2.az_violations) == 0)

    # No Az at all → no violation
    text_none = "Das BGB regelt das Privatrecht. [training-knowledge]"
    report3 = verify_markers(text_none)
    _check("No Az: no violation",
           len(report3.az_violations) == 0)


def test_t10_overall_grade_aggregation():
    print(f"\n{_BOLD}[T10]{_RESET} overall_grade aggregation logic")
    # No markers → no_markers
    r = verify_markers("Plain text no markers.")
    _check("plain text: overall_grade=no_markers",
           r.overall_grade == "no_markers")

    # One fabricated_likely → suspect
    r = verify_markers(
        "Behauptung [verbatim:https://example.com/the-truth-about-this-one-trick]"
    )
    _check("suspicious slug: overall_grade=suspect",
           r.overall_grade == "suspect")

    # Az violation → fail (overrides marker grades)
    r = verify_markers("BGH I ZR 1/2 entschied klar.")
    _check("Az violation: overall_grade=fail",
           r.overall_grade == "fail")


def test_t11_integration_on_realistic_output():
    print(f"\n{_BOLD}[T11]{_RESET} integration test on realistic wrapper-model output sample")
    sample = (
        "[verbatim:https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4170962/] "
        "In einer klinischen Studie wurde festgestellt, dass Terbinafin und "
        "Butenafin beide wirksam zur Behandlung von Nagelpilz sind. "
        "Erfolgsrate Terbinafin 58%, Butenafin 41%. "
        "[mechanism:Terbinafin hemmt die Squalen-Epoxidase und stoert die "
        "Ergosterol-Synthese, was die Pilzmembran destabilisiert.] "
        "[unsicher] Individuelle Reaktionen koennen variieren."
    )
    report = verify_markers(sample, do_fetch=False)
    _check(f"3 markers found (got {len(report.markers)})",
           len(report.markers) == 3)
    _check("overall_grade is ok or partial (no fabrication, no AZ-violation)",
           report.overall_grade in ("ok", "partial"))
    # Specific marker grades
    kinds = sorted([m.kind for m in report.markers])
    _check("kinds == [mechanism, unsicher, verbatim]",
           kinds == ["mechanism", "unsicher", "verbatim"])
    # The PMC URL is tier1
    verbatim_g = next(m for m in report.markers if m.kind == "verbatim")
    _check("PMC URL graded as tier1-unverified",
           verbatim_g.grade == "unverified" and verbatim_g.confidence >= 0.6)


def main():
    print(f"{_BOLD}marker_verifier — falsifiable tests · #193{_RESET}")
    print("=" * 75)
    test_t1_extract_basic()
    test_t2_extract_valueless()
    test_t3_extract_empty_or_no_match()
    test_t4_url_classification()
    test_t5_suspicious_slug()
    test_t6_source_marker_no_fetch()
    test_t7_self_markers()
    test_t8_mechanism_marker_grading()
    test_t9_aktenzeichen_violation_detection()
    test_t10_overall_grade_aggregation()
    test_t11_integration_on_realistic_output()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}marker_verifier result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
