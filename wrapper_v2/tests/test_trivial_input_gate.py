"""trivial_input_gate — falsifiable benchmark for Phase-2 fix #3 step (d).

Production motivation: "hi wie gehts" still ran full classifier-chain
(~19s); detect_bare_greeting only catches the bare "hi". This gate
should fast-path greeting+counter-Q, bare counter-Q, thanks, ack,
farewell to sub-200ms.

Run via: python3 -m wrapper_v2.tests.test_trivial_input_gate
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.pipeline.trivial_input_gate import (
    TrivialMatch,
    detect_trivial_input,
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


def test_t1_greeting_counter_q_de():
    print(f"\n{_BOLD}[T1]{_RESET} greeting + counter-Q (DE) → greeting_q / de")
    for msg in [
        "hi wie gehts",
        "Hallo, wie geht's?",
        "Servus wie geht es dir?",
        "Moin, was geht?",
        "Hi, alles klar?",
        "ahoi wie geht's so?",
    ]:
        m = detect_trivial_input(msg)
        _check(f"matched: {msg!r:35s}", m is not None,
               f"got {m}")
        if m is not None:
            _check(f"  category=greeting_q for {msg!r:33s}",
                   m.category == "greeting_q",
                   f"got category={m.category}")
            _check(f"  lang=de for {msg!r:42s}",
                   m.lang_code == "de",
                   f"got lang={m.lang_code}")


def test_t2_greeting_counter_q_en():
    print(f"\n{_BOLD}[T2]{_RESET} greeting + counter-Q (EN) → greeting_q / en")
    for msg in [
        "hi what's up",
        "Hello, how are you?",
        "Hey, how's it going?",
        "Howdy, what's new?",
        "Yo, how ya doing?",
    ]:
        m = detect_trivial_input(msg)
        _check(f"matched: {msg!r:35s}", m is not None and m.lang_code == "en",
               f"got {m}")


def test_t3_bare_counter_q():
    print(f"\n{_BOLD}[T3]{_RESET} bare counter-Q (no greeting) → bare_counter_q")
    for msg, lang in [
        ("wie geht's?", "de"),
        ("wie geht es dir?", "de"),
        ("was geht?", "de"),
        ("alles gut?", "de"),
        ("alles klar?", "de"),
        ("what's up?", "en"),
        ("how are you?", "en"),
        ("how's it going?", "en"),
        ("qué tal?", "es"),
        ("come va?", "it"),
        ("ça va?", "fr"),
    ]:
        m = detect_trivial_input(msg)
        ok = (m is not None
              and m.category == "bare_counter_q"
              and m.lang_code == lang)
        _check(f"{msg!r:25s} → bare_counter_q/{lang}", ok,
               f"got {m}")


def test_t4_thanks():
    print(f"\n{_BOLD}[T4]{_RESET} thanks → thanks tag")
    for msg, lang in [
        ("danke", "de"),
        ("vielen dank", "de"),
        ("danke dir", "de"),
        ("thanks", "en"),
        ("thank you", "en"),
        ("thanks a lot", "en"),
        ("thx", "en"),
        ("gracias", "es"),
        ("muchas gracias", "es"),
        ("grazie", "it"),
        ("grazie mille", "it"),
        ("merci beaucoup", "fr"),
    ]:
        m = detect_trivial_input(msg)
        ok = (m is not None
              and m.category == "thanks"
              and m.lang_code == lang)
        _check(f"{msg!r:25s} → thanks/{lang}", ok,
               f"got {m}")


def test_t5_acknowledgment():
    print(f"\n{_BOLD}[T5]{_RESET} acknowledgment → ack tag")
    # Note: "alles klar" routes to bare_counter_q first (klar shared) — that's
    # acceptable; the reply works for both ack and counter-Q usage.
    for msg, lang in [
        ("ok", "de"),
        ("okay", "de"),
        ("verstanden", "de"),
        ("passt scho", "de"),
        ("got it", "en"),
        ("alright", "en"),
        ("sounds good", "en"),
        ("cool", "en"),
    ]:
        m = detect_trivial_input(msg)
        ok = (m is not None
              and m.category == "ack"
              and m.lang_code == lang)
        _check(f"{msg!r:25s} → ack/{lang}", ok,
               f"got {m}")


def test_t6_farewell():
    print(f"\n{_BOLD}[T6]{_RESET} farewell → farewell tag")
    for msg, lang in [
        ("tschüss", "de"),
        ("bis bald", "de"),
        ("mach's gut", "de"),
        ("schönen abend", "de"),
        ("bye", "en"),
        ("see you", "en"),
        ("take care", "en"),
        ("ciao", "it"),
        ("arrivederci", "it"),
        ("adiós", "es"),
        ("au revoir", "fr"),
    ]:
        m = detect_trivial_input(msg)
        ok = (m is not None
              and m.category == "farewell"
              and m.lang_code == lang)
        _check(f"{msg!r:25s} → farewell/{lang}", ok,
               f"got {m}")


def test_t7_real_queries_dont_match():
    """CRITICAL: real questions must NOT match — false-positive here
    means we'd canned-reply to actual user requests, which would be the
    'doff-faul' worst-case."""
    print(f"\n{_BOLD}[T7]{_RESET} real queries → None (no false positives)")
    for msg in [
        "Was ist die Hauptstadt von Frankreich?",
        "ok, kannst du mir helfen?",
        "danke, aber kannst du das nochmal erklären?",
        "hi, ich brauche Hilfe mit Python",
        "wie kann ich Geld sparen?",
        "Erkläre mir Wittgensteins Sprachspiele",
        "Was geht ab in Berlin diese Woche?",
        "Bye-Aktion bei Amazon — was ist das?",
        "what is the capital of France?",
        "tell me a joke",
        "Berechne 500/200",
        # Pathological: contains a greeting but ALSO real content
        "Hi, was kostet ein Tesla Model Y in Deutschland?",
        "Hallo, ich habe eine Frage zu meinem Vertrag.",
    ]:
        m = detect_trivial_input(msg)
        _check(f"None: {msg!r:55s}", m is None,
               f"FALSE POSITIVE: got {m}")


def test_t8_punctuation_and_emoji_tolerance():
    """Same strip-tolerance as detect_bare_greeting — strip emoticons,
    punctuation, brackets."""
    print(f"\n{_BOLD}[T8]{_RESET} punctuation + emoticons tolerated")
    for msg in [
        "hi wie gehts (:",
        "Hi! Wie geht's? :)",
        "danke :)",
        "ok!",
        "bye!!",
        "  wie geht's?  ",
    ]:
        m = detect_trivial_input(msg)
        _check(f"matched: {msg!r:30s}", m is not None,
               f"got {m}")


def test_t9_empty_and_none():
    print(f"\n{_BOLD}[T9]{_RESET} empty / None → None")
    _check("None → None", detect_trivial_input(None) is None)
    _check("'' → None", detect_trivial_input("") is None)
    _check("'   ' → None", detect_trivial_input("   ") is None)
    _check("'!!!' → None", detect_trivial_input("!!!") is None)


def test_t10_replies_are_warm_and_short():
    """Replies should be short (one sentence) and warm — not preachy."""
    print(f"\n{_BOLD}[T10]{_RESET} canned replies are short + open")
    for msg in [
        "hi wie gehts",
        "danke",
        "ok",
        "bye",
    ]:
        m = detect_trivial_input(msg)
        if m is not None:
            _check(f"{msg!r:20s} reply ≤ 120 chars: {m.reply!r}",
                   len(m.reply) <= 120,
                   f"reply too long ({len(m.reply)} chars)")
            _check(f"{msg!r:20s} reply non-empty",
                   bool(m.reply.strip()),
                   f"empty reply")


def test_t12_slang_counter_q():
    """d.1 2026-06-02: slang variants of "what's up" — whazzup, wassup,
    sup, what up."""
    print(f"\n{_BOLD}[T12]{_RESET} slang counter-Q variants → matched")
    for msg in [
        "whazzup?",
        "wassup",
        "wazzup?",
        "sup?",
        "what up",
        "hi whazzup",      # greeting + slang
        "ahoi whazzup?",   # cross-lang: DE greeting + EN slang
        "hallo sup?",
        "yo bro",
    ]:
        m = detect_trivial_input(msg)
        _check(f"matched: {msg!r:30s}", m is not None,
               f"got {m}")


def test_t12b_ey_and_stacked_greetings():
    """d.1.1 2026-06-02: 'ey' slang opener + stacked greetings ('ey yo')."""
    print(f"\n{_BOLD}[T12b]{_RESET} 'ey' opener + stacked greetings")
    for msg in [
        "ey wie gehts?",
        "ey what's up?",
        "ey yo whazzup",
        "ey yo whazzup (:",
        "ey yo wie gehts",
        "hey yo what's up",
        "hi hello, wie geht's?",
        "n'abend, wie geht's?",
    ]:
        m = detect_trivial_input(msg)
        _check(f"matched: {msg!r:30s}", m is not None,
               f"got {m}")


def test_t13_cross_language_greeting_plus_q():
    """d.1 2026-06-02: greeting from one language + counter-Q from another.
    Already supported via _GREETING_PREFIX (cross-lang); reply uses
    counter-Q lang (the active register)."""
    print(f"\n{_BOLD}[T13]{_RESET} cross-language greeting+counter-Q")
    for msg, expected_lang in [
        ("ahoi whazzup?",       "en"),    # DE greeting + EN counter-Q → EN reply
        ("hi wie gehts?",       "de"),    # EN greeting + DE counter-Q → DE reply
        ("hallo what's up?",    "en"),
        ("hola, wie geht's?",   "de"),
        ("ciao, how are you?",  "en"),
    ]:
        m = detect_trivial_input(msg)
        ok = m is not None and m.lang_code == expected_lang
        _check(f"{msg!r:25s} → lang={expected_lang}", ok,
               f"got {m}")


def test_t11_length_cap():
    """Anything over MAX_TRIVIAL_LEN (60 chars after stripping) must not
    match — even if it starts with a trivial pattern."""
    print(f"\n{_BOLD}[T11]{_RESET} length cap prevents false-positive on long messages")
    long_msg = "hi wie gehts und kannst du mir bei einem komplexen problem helfen"
    m = detect_trivial_input(long_msg)
    _check(f"long msg ({len(long_msg)} chars) → None",
           m is None,
           f"got {m}")


def main() -> int:
    print(f"{_BOLD}trivial_input_gate — Phase-2 fix #3 step (d) · falsifiable{_RESET}")
    print("=" * 75)

    test_t1_greeting_counter_q_de()
    test_t2_greeting_counter_q_en()
    test_t3_bare_counter_q()
    test_t4_thanks()
    test_t5_acknowledgment()
    test_t6_farewell()
    test_t7_real_queries_dont_match()
    test_t8_punctuation_and_emoji_tolerance()
    test_t9_empty_and_none()
    test_t10_replies_are_warm_and_short()
    test_t11_length_cap()
    test_t12_slang_counter_q()
    test_t12b_ey_and_stacked_greetings()
    test_t13_cross_language_greeting_plus_q()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}trivial_input_gate result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
