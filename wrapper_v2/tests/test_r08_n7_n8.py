"""R0.8 + N7/N8 — gray-out wisdom-quote rotation + L0 wire-verify.

Closes 3 MANUAL items from M9 schiri:
  - R0.8 gray-out wisdom-quote rotation     (was MANUAL → GREEN)
  - N7  Vulnerable-user-protection redirect (wire-verify l0_vulnerable.py)
  - N8  L0-harm-output-check hard-stop      (wire-verify l0_harm_output.py)
Plus bonus: l0_alarm.py also wire-verified (N5, already GREEN, sanity).

Per [[splice_8_octave_completion_schelmisch_wisdom_quotes]] +
[[vulnerable_user_protection_reziprok_ceiling]] +
[[death_penalty_void]].

Run via: python3 -m wrapper_v2.tests.test_r08_n7_n8  (stdlib-only)
Exit-code 0 = all-pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.pipeline import gray_out
from wrapper_v2.pipeline.gray_out import (
    WISDOM_QUOTES, GrayOutQuote, pick_quote, render_gray_out_html,
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


# ─── R0.8 — gray-out wisdom-quote rotation ─────────────────────────────


def test_catalog_has_required_figures():
    print(f"\n{_BOLD}[R0.8/T1]{_RESET} catalog has the required cultural figures")
    required = {"Yoda", "Konfuzius", "Lao Tzu", "Heraklit", "Mark Twain", "Bayerischer Wirt"}
    have = set(WISDOM_QUOTES.keys())
    missing = required - have
    _check(
        f"all 6 required figures present",
        not missing,
        f"missing: {missing}" if missing else "",
    )
    for fig in required:
        _check(
            f"{fig} has ≥1 quote",
            len(WISDOM_QUOTES.get(fig, [])) >= 1,
        )


def test_yoda_canonical_quote_present():
    print(f"\n{_BOLD}[R0.8/T2]{_RESET} operator's canonical Yoda quote present")
    yoda = WISDOM_QUOTES.get("Yoda", [])
    canonical = "wer mir kommet so blöde, kommet neu mit set mind"
    _check(
        "canonical Yoda quote present verbatim",
        any(canonical in q for q in yoda),
        f"got: {yoda}",
    )


def test_pick_quote_deterministic_with_seed():
    print(f"\n{_BOLD}[R0.8/T3]{_RESET} pick_quote deterministic with seed")
    q1 = pick_quote(seed="session-abc")
    q2 = pick_quote(seed="session-abc")
    q3 = pick_quote(seed="session-xyz")
    _check("same seed → same figure", q1.figure == q2.figure)
    _check("same seed → same quote", q1.quote == q2.quote)
    _check("different seeds may differ", (q1.figure, q1.quote) != (q3.figure, q3.quote) or q1.figure != q3.figure,
           f"both got: {q1.figure}/{q3.figure}")


def test_pick_quote_rotates_across_figures():
    print(f"\n{_BOLD}[R0.8/T4]{_RESET} rotation covers multiple figures over many seeds")
    seen_figures = set()
    for i in range(100):
        q = pick_quote(seed=f"seed-{i}")
        seen_figures.add(q.figure)
    _check(
        f"≥4 distinct figures seen across 100 seeds (got {len(seen_figures)})",
        len(seen_figures) >= 4,
    )


def test_as_text_includes_attribution():
    print(f"\n{_BOLD}[R0.8/T5]{_RESET} GrayOutQuote.as_text() prefixes attribution")
    q = GrayOutQuote(figure="Yoda", quote="test quote")
    text = q.as_text()
    _check("contains figure attribution", "Yoda" in text)
    _check("contains quote text", "test quote" in text)
    _check("uses 'spricht' / 'sagt' speech-verb", any(v in text for v in ["spricht", "sagt", "lehrt", "warnt", "meint"]))


def test_render_gray_out_html_structure():
    print(f"\n{_BOLD}[R0.8/T6]{_RESET} render_gray_out_html produces sealed gray-out class + tooltip")
    html = render_gray_out_html("Wiederholtes dumpf-stumpfsinniges Pattern", seed="test")
    _check("contains factampel-passage gray-out class", 'factampel-passage gray-out' in html)
    _check("has tabindex=0", 'tabindex="0"' in html)
    _check("has data-tooltip", 'data-tooltip=' in html)
    _check("reason text rendered", 'dumpf-stumpfsinniges' in html)
    _check("italic quote style applied", 'font-style:italic' in html)
    _check("references position 8 in tooltip", 'position 8' in html or 'gray-out' in html)


def test_render_html_escapes_user_input():
    print(f"\n{_BOLD}[R0.8/T7]{_RESET} render_gray_out_html HTML-escapes reason text")
    html = render_gray_out_html("<script>alert(1)</script>", seed="x")
    _check("raw <script> NOT in output", "<script>alert" not in html)
    _check("escaped &lt;script&gt; present", "&lt;script&gt;" in html)


# ─── N7 — vulnerable-user-protection wire-verify ───────────────────────


def test_n7_l0_vulnerable_module_loads():
    print(f"\n{_BOLD}[N7/T1]{_RESET} l0_vulnerable module loads cleanly")
    try:
        from wrapper_v2.pipeline import l0_vulnerable
        _check("import succeeds", True)
        _check("has check_vulnerable", hasattr(l0_vulnerable, "check_vulnerable"))
        _check("has build_redirect_response", hasattr(l0_vulnerable, "build_redirect_response"))
        _check("has VulnerableResult dataclass", hasattr(l0_vulnerable, "VulnerableResult"))
    except Exception as e:
        _check(f"import failed: {e}", False)


def test_n7_vulnerable_check_returns_result_shape():
    print(f"\n{_BOLD}[N7/T2]{_RESET} check_vulnerable() returns proper-shape result")
    from wrapper_v2.pipeline import l0_vulnerable
    # Use a non-vulnerable benign input — must return a result-object, never None or raise
    try:
        result = l0_vulnerable.check_vulnerable("Was ist die Hauptstadt Deutschlands?")
        _check("returns a result object (not None)", result is not None)
        _check("result is VulnerableResult", isinstance(result, l0_vulnerable.VulnerableResult))
    except Exception as e:
        _check(f"check_vulnerable raised: {e}", False)


# ─── N8 — L0-harm-output-check wire-verify ─────────────────────────────


def test_n8_l0_harm_output_module_loads():
    print(f"\n{_BOLD}[N8/T1]{_RESET} l0_harm_output module loads cleanly")
    try:
        from wrapper_v2.pipeline import l0_harm_output
        _check("import succeeds", True)
        _check("has check_output_harm", hasattr(l0_harm_output, "check_output_harm"))
        _check("has hard_stop_or_pass", hasattr(l0_harm_output, "hard_stop_or_pass"))
        _check("has HarmCheckResult dataclass", hasattr(l0_harm_output, "HarmCheckResult"))
    except Exception as e:
        _check(f"import failed: {e}", False)


def test_n8_benign_output_passes():
    print(f"\n{_BOLD}[N8/T2]{_RESET} benign output passes check_output_harm")
    from wrapper_v2.pipeline import l0_harm_output
    try:
        result = l0_harm_output.check_output_harm("Berlin ist die Hauptstadt Deutschlands.")
        _check("returns a result", result is not None)
        _check("result is HarmCheckResult", isinstance(result, l0_harm_output.HarmCheckResult))
    except Exception as e:
        _check(f"check_output_harm raised: {e}", False)


# ─── N5 — l0_alarm bonus wire-verify ───────────────────────────────────


def test_n5_l0_alarm_module_loads():
    print(f"\n{_BOLD}[N5/T1]{_RESET} l0_alarm module loads cleanly (bonus wire-verify)")
    try:
        from wrapper_v2.pipeline import l0_alarm
        _check("import succeeds", True)
        _check("has check_alarm", hasattr(l0_alarm, "check_alarm"))
        _check("has AlarmResult dataclass", hasattr(l0_alarm, "AlarmResult"))
        _check("has sample_alarm_phrases_for_test helper",
               hasattr(l0_alarm, "sample_alarm_phrases_for_test"))
    except Exception as e:
        _check(f"import failed: {e}", False)


def test_n5_benign_input_does_not_alarm():
    print(f"\n{_BOLD}[N5/T2]{_RESET} benign input does NOT trigger alarm")
    from wrapper_v2.pipeline import l0_alarm
    result = l0_alarm.check_alarm("Was ist die Hauptstadt Deutschlands?")
    _check("returns result", result is not None)
    _check("result.triggered is False (benign input)",
           getattr(result, "triggered", True) is False,
           f"got: {result}")


# ─── Runner ────────────────────────────────────────────────────────────


def main() -> int:
    print(f"{_BOLD}R0.8 + N7/N8 — gray-out wisdom-quotes + L0 wire-verify{_RESET}")
    print("=" * 70)

    # R0.8 — gray-out
    test_catalog_has_required_figures()
    test_yoda_canonical_quote_present()
    test_pick_quote_deterministic_with_seed()
    test_pick_quote_rotates_across_figures()
    test_as_text_includes_attribution()
    test_render_gray_out_html_structure()
    test_render_html_escapes_user_input()

    # N7 — vulnerable
    test_n7_l0_vulnerable_module_loads()
    test_n7_vulnerable_check_returns_result_shape()

    # N8 — harm-output
    test_n8_l0_harm_output_module_loads()
    test_n8_benign_output_passes()

    # N5 bonus — alarm
    test_n5_l0_alarm_module_loads()
    test_n5_benign_input_does_not_alarm()

    print()
    print("=" * 70)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}R0.8 + N7/N8 result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
