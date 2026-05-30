"""D7 register-dedup — falsifiable benchmark.

Per R1 D7 drift-target + R2 §4.4.

Verifies the consolidated classifier/register_detect.py module:
  - cheap tone-regex classification (BASIC / CASUAL / PROFESSIONAL / ACADEMIC)
  - irony adapter optional + cost-gated by message length
  - composite confidence aggregation
  - build_system_message renders DE+EN per tone + irony
  - empty/short input handled gracefully (BASIC + no system-msg)
  - vulnerable-register stub-API documented contract

Run via: python3 -m wrapper_v2.tests.test_d7_register  (stdlib-only)
Exit-code 0 = all-pass.

Doctrine: [[1455xl_chassis_goal_driven_funnel]] +
[[vulnerable_user_protection_reziprok_ceiling]] +
[[basetouch_verified_then_dollschon_overclock]].
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.classifier.register_detect import (
    Tone, Irony, RegisterResult,
    detect_register, register_irony_adapter, build_system_message,
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


# ─── Cheap tone-detection ──────────────────────────────────────────────


def test_basic_tone_for_short_input():
    print(f"\n{_BOLD}[T1]{_RESET} BASIC tone for short/empty input")
    for msg in ["", "  ", "hi", "ja", "  ok  "]:
        r = detect_register(msg)
        _check(f"'{msg!r}' → BASIC", r.tone == Tone.BASIC)


def test_casual_tone_detected():
    print(f"\n{_BOLD}[T2]{_RESET} CASUAL tone with operator-curated markers")
    casual_msgs = [
        "naja, passt schon, oida, was meinst du?",
        "halt mal kurz, dude — krass cool das",
        "ich mein, jo, geht klar irgendwie!!",
    ]
    for msg in casual_msgs:
        r = detect_register(msg)
        _check(f"'{msg[:30]}…' → CASUAL", r.tone == Tone.CASUAL,
               f"got: {r.tone.value}")


def test_academic_tone_detected():
    print(f"\n{_BOLD}[T3]{_RESET} ACADEMIC tone with formal markers")
    academic_msgs = [
        ("Methodologisch betrachtet wäre es paradigmatisch sinnvoll, "
         "die Hypothese hermeneutisch zu operationalisieren."),
        ("Insofern als die epistemologisch geprägte Literatur "
         "(vgl. Müller 2019) signifikant korreliert mit dem Befund."),
    ]
    for msg in academic_msgs:
        r = detect_register(msg)
        _check(f"'{msg[:30]}…' → ACADEMIC", r.tone == Tone.ACADEMIC,
               f"got: {r.tone.value}")


def test_professional_default_for_substantial_neutral():
    print(f"\n{_BOLD}[T4]{_RESET} PROFESSIONAL default for neutral substantial input")
    msgs = [
        "Was ist die Hauptstadt von Frankreich, bitte?",
        "Bitte erkläre kurz, wie Photosynthese funktioniert.",
    ]
    for msg in msgs:
        r = detect_register(msg)
        _check(f"'{msg[:30]}…' → PROFESSIONAL",
               r.tone == Tone.PROFESSIONAL,
               f"got: {r.tone.value}")


def test_tone_confidence_in_unit_range():
    print(f"\n{_BOLD}[T5]{_RESET} confidence always in [0.0, 1.0]")
    for msg in ["", "naja oida krass!! jo", "Methodologisch insofern"]:
        r = detect_register(msg)
        _check(f"confidence in [0,1] for '{msg[:20]}…'",
               0.0 <= r.confidence <= 1.0,
               f"got: {r.confidence}")


# ─── Irony adapter ─────────────────────────────────────────────────────


def test_irony_adapter_not_registered_no_irony():
    print(f"\n{_BOLD}[T6]{_RESET} no adapter registered → irony stays None")
    register_irony_adapter(None)
    r = detect_register("a" * 200)
    _check("irony = None", r.irony is None)
    _check("only 'tone' in applied_dimensions",
           "tone" in r.applied_dimensions and "irony" not in r.applied_dimensions)


def test_irony_adapter_applied_long_message():
    print(f"\n{_BOLD}[T7]{_RESET} adapter fires for long messages, returns label")
    register_irony_adapter(lambda text: {"label": "ironic", "confidence": 0.85})
    long_msg = "Das ist nun wirklich superintelligent gemacht. " * 5
    r = detect_register(long_msg)
    _check("irony = IRONIC", r.irony == Irony.IRONIC)
    _check("applied_dimensions includes 'irony'", "irony" in r.applied_dimensions)
    register_irony_adapter(None)


def test_irony_adapter_skipped_for_short_messages():
    print(f"\n{_BOLD}[T8]{_RESET} adapter NOT called on short messages (cost-gate)")
    called = {"n": 0}
    def adapter(text):
        called["n"] += 1
        return {"label": "ironic"}
    register_irony_adapter(adapter)
    r = detect_register("short msg here")  # below 80-char threshold
    _check("adapter NOT called", called["n"] == 0)
    _check("irony stays None", r.irony is None)
    register_irony_adapter(None)


def test_irony_adapter_exception_captured():
    print(f"\n{_BOLD}[T9]{_RESET} adapter exception → notes-captured, no raise")
    register_irony_adapter(lambda text: 1/0)
    long_msg = "Hier ist ein ausreichend langer Text, " * 4
    r = detect_register(long_msg)
    _check("irony stays None on exception", r.irony is None)
    _check("notes mentions raised", "raised" in r.notes)
    register_irony_adapter(None)


def test_irony_adapter_unknown_label_ignored():
    print(f"\n{_BOLD}[T10]{_RESET} adapter unknown label → ignored, notes-captured")
    register_irony_adapter(lambda text: {"label": "__bogus__"})
    long_msg = "Hier ist ein ausreichend langer Text, " * 4
    r = detect_register(long_msg)
    _check("irony stays None", r.irony is None)
    _check("notes mentions unknown", "unknown" in r.notes)
    register_irony_adapter(None)


def test_run_irony_false_skips():
    print(f"\n{_BOLD}[T11]{_RESET} run_irony=False short-circuits adapter")
    called = {"n": 0}
    register_irony_adapter(lambda text: (called.__setitem__("n", called["n"] + 1) or {"label": "ironic"}))
    long_msg = "Hier ist ein ausreichend langer Text, " * 4
    r = detect_register(long_msg, run_irony=False)
    _check("adapter NOT called when run_irony=False", called["n"] == 0)
    _check("irony None", r.irony is None)
    register_irony_adapter(None)


# ─── System-message composer ──────────────────────────────────────────


def test_no_sysmsg_for_basic_no_irony():
    print(f"\n{_BOLD}[T12]{_RESET} BASIC tone + no irony → build_system_message returns None")
    r = RegisterResult(tone=Tone.BASIC, irony=None)
    _check("returns None", build_system_message(r) is None)


def test_no_sysmsg_for_literal_irony_only_basic():
    print(f"\n{_BOLD}[T13]{_RESET} BASIC + LITERAL irony → None")
    r = RegisterResult(tone=Tone.BASIC, irony=Irony.LITERAL)
    _check("returns None", build_system_message(r) is None)


def test_sysmsg_for_casual_de():
    print(f"\n{_BOLD}[T14]{_RESET} CASUAL tone → DE system-message")
    r = RegisterResult(tone=Tone.CASUAL, irony=None, confidence=0.8)
    msg = build_system_message(r, lang="de")
    _check("returns dict", msg is not None and msg.get("role") == "system")
    _check("content mentions casual", "casual" in msg["content"].lower())
    _check("_register marker = casual", msg.get("_register") == "casual")


def test_sysmsg_for_academic_en():
    print(f"\n{_BOLD}[T15]{_RESET} ACADEMIC tone → EN system-message")
    r = RegisterResult(tone=Tone.ACADEMIC, irony=None, confidence=0.7)
    msg = build_system_message(r, lang="en")
    _check("returns dict", msg is not None)
    _check("content mentions academic", "academic" in msg["content"].lower())
    _check("content in English (no German umlauts)",
           "ä" not in msg["content"] and "ü" not in msg["content"])


def test_sysmsg_includes_both_tone_and_irony():
    print(f"\n{_BOLD}[T16]{_RESET} CASUAL + IRONIC → system-message includes BOTH")
    r = RegisterResult(tone=Tone.CASUAL, irony=Irony.IRONIC, confidence=0.85)
    msg = build_system_message(r, lang="de")
    _check("returns dict", msg is not None)
    _check("content mentions casual", "casual" in msg["content"].lower())
    _check("content mentions ironisch", "ironisch" in msg["content"].lower())
    _check("_register marker = casual", msg.get("_register") == "casual")
    _check("_irony marker = ironic", msg.get("_irony") == "ironic")


# ─── Vulnerable-register contract ──────────────────────────────────────


def test_vulnerable_register_stub_returns_false():
    print(f"\n{_BOLD}[T17]{_RESET} is_vulnerable_register stub returns False (delegation contract)")
    r = RegisterResult(tone=Tone.CASUAL)
    # Per [[vulnerable_user_protection_reziprok_ceiling]]: this module
    # documents the contract but DELEGATES detection to l0_vulnerable.py.
    _check("returns False (stub)", r.is_vulnerable_register() is False)


# ─── Runner ────────────────────────────────────────────────────────────


def main() -> int:
    print(f"{_BOLD}D7 register-dedup — consolidated tone + irony classifier · falsifiable{_RESET}")
    print("=" * 75)

    test_basic_tone_for_short_input()
    test_casual_tone_detected()
    test_academic_tone_detected()
    test_professional_default_for_substantial_neutral()
    test_tone_confidence_in_unit_range()
    test_irony_adapter_not_registered_no_irony()
    test_irony_adapter_applied_long_message()
    test_irony_adapter_skipped_for_short_messages()
    test_irony_adapter_exception_captured()
    test_irony_adapter_unknown_label_ignored()
    test_run_irony_false_skips()
    test_no_sysmsg_for_basic_no_irony()
    test_no_sysmsg_for_literal_irony_only_basic()
    test_sysmsg_for_casual_de()
    test_sysmsg_for_academic_en()
    test_sysmsg_includes_both_tone_and_irony()
    test_vulnerable_register_stub_returns_false()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}D7 register-dedup result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
