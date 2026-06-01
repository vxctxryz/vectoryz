"""Output-sanitize — falsifiable benchmark for T2.d meta-prompt echo strip.

Per Phase-2 fix #1 (2026-06-01). Triggering observation: Q5 math test
in production deployment showed the full system-message ("Erweitere
jetzt die Antwort...") echo'd in the user-visible response, with
factampel even grading the echoed lines as claims.

Run via: python3 -m wrapper_v2.tests.test_output_sanitize
Exit-code 0 = all-pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.pipeline.output_sanitize import strip_short_answer_echo


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


# ─── Real-world fixture: Q5 leak ──────────────────────────────────────


SHORT_ANSWER_Q5 = (
    "Die Züge treffen sich nach 2.5 Stunden. Da sie entgegenkommend "
    "fahren, addieren wir ihre Geschwindigkeiten zu 200 km/h. Die "
    "Entfernung zwischen ihnen ist 500 km, also benötigen sie 500 ÷ "
    "200 = 2.5 Stunden, um sich beizusetzen."
)


# The deep-tier buffer as actually observed in production Q5 test
DEEP_BUF_Q5 = (
    SHORT_ANSWER_Q5 + "\n\n"
    "Erweitere jetzt die Antwort: tiefer, mit Beispielen, Kontext, Quellen. "
    "Wiederhole die Kurzantwort NICHT — bau auf ihr auf. "
    "Schreibe direkt mit der Erweiterung los, keine erneute Vorrede.\n\n"
    "Um die Zeit zu berechnen, bis sich die beiden Züge begegnen, müssen "
    "wir ihre Geschwindigkeiten addieren und diese durch die gesamte "
    "Entfernung teilen. Da der erste Zug mit 80 km/h fährt und der zweite "
    "Zug mit 120 km/h, ergibt sich eine Gesamtgeschwindigkeit von 200 km/h."
)


def test_t1_echo_stripped():
    print(f"\n{_BOLD}[T1]{_RESET} short-answer echo + meta-prompt stripped from Q5-fixture")
    cleaned = strip_short_answer_echo(DEEP_BUF_Q5, SHORT_ANSWER_Q5)
    _check("short-answer NOT in cleaned",
           SHORT_ANSWER_Q5[:50] not in cleaned,
           f"first 200 of cleaned: {cleaned[:200]!r}")
    _check("'Erweitere jetzt' NOT in cleaned",
           "Erweitere jetzt" not in cleaned)
    _check("'Wiederhole die Kurzantwort' NOT in cleaned",
           "Wiederhole die Kurzantwort" not in cleaned)
    _check("'Schreibe direkt mit der Erweiterung' NOT in cleaned",
           "Schreibe direkt mit der Erweiterung" not in cleaned)
    _check("actual expansion content survives",
           "Um die Zeit zu berechnen" in cleaned)
    _check("'Gesamtgeschwindigkeit von 200 km/h' survives",
           "Gesamtgeschwindigkeit von 200 km/h" in cleaned)


def test_t2_no_echo_passes_through():
    print(f"\n{_BOLD}[T2]{_RESET} no echo present → text passes through unchanged")
    clean_input = (
        "Der Nobelpreis für Physik 2024 wurde an John Hopfield und "
        "Geoffrey Hinton vergeben. Sie wurden für ihre Arbeiten zu "
        "künstlichen neuronalen Netzen ausgezeichnet."
    )
    out = strip_short_answer_echo(clean_input, "irrelevant short answer")
    _check("clean text returned unchanged (modulo strip)",
           out.strip() == clean_input.strip(),
           f"in:  {clean_input[:80]!r}\n      out: {out[:80]!r}")


def test_t3_meta_only_strip_no_short():
    print(f"\n{_BOLD}[T3]{_RESET} meta-prompt-only strip (no short_answer arg)")
    buf = (
        "Erweitere jetzt die Antwort: tiefer, mit Beispielen, Kontext, Quellen.\n"
        "Wiederhole die Kurzantwort NICHT — bau auf ihr auf.\n\n"
        "Hier ist die eigentliche Antwort."
    )
    out = strip_short_answer_echo(buf, short_answer=None)
    _check("'Erweitere jetzt' gone", "Erweitere jetzt" not in out)
    _check("'Wiederhole die Kurzantwort' gone", "Wiederhole die Kurzantwort" not in out)
    _check("'Hier ist die eigentliche Antwort' survives",
           "Hier ist die eigentliche Antwort" in out)


def test_t4_empty_input():
    print(f"\n{_BOLD}[T4]{_RESET} empty / None inputs handled")
    _check("empty deep_buf → empty out", strip_short_answer_echo("", "anything") == "")
    _check("None short_answer + clean buf passes through",
           "x" in strip_short_answer_echo("x y z", None))


def test_t5_kurzantwort_header_stripped():
    print(f"\n{_BOLD}[T5]{_RESET} 'KURZANTWORT (User hat das oben gesehen...)' header stripped")
    buf = (
        "KURZANTWORT (User hat das oben gesehen, gefolgt vom '---' Trenner):\n"
        "Berlin ist die Hauptstadt.\n\n"
        "Erweitere jetzt die Antwort: tiefer, mit Beispielen.\n\n"
        "Das tatsächliche Expansion-Material kommt hier."
    )
    out = strip_short_answer_echo(buf, "Berlin ist die Hauptstadt.")
    _check("KURZANTWORT-header gone", "KURZANTWORT" not in out)
    _check("'Erweitere jetzt' gone", "Erweitere jetzt" not in out)
    _check("actual content survives",
           "Das tatsächliche Expansion-Material" in out)


def test_t6_leading_separator_stripped():
    print(f"\n{_BOLD}[T6]{_RESET} leading `---` orphans cleaned up")
    buf = (
        "---\n\n"
        "---\n"
        "Eigentlicher Content nach Separator-Orphans."
    )
    out = strip_short_answer_echo(buf, None)
    _check("leading --- stripped", not out.startswith("-"))
    _check("content survives", "Eigentlicher Content" in out)


def main() -> int:
    print(f"{_BOLD}output-sanitize — T2.d meta-prompt echo strip · falsifiable{_RESET}")
    print("=" * 75)

    test_t1_echo_stripped()
    test_t2_no_echo_passes_through()
    test_t3_meta_only_strip_no_short()
    test_t4_empty_input()
    test_t5_kurzantwort_header_stripped()
    test_t6_leading_separator_stripped()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}output-sanitize result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
