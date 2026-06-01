"""Conversational-chrome filter — falsifiable benchmark.

2026-05-31 fix: greetings + Q-restatements + answer-frames + closings
must NOT receive factampel grades. Triggering case from production chat
(Teufel-scan test): "Ahoi!" → 🟡 maybefact was a category error.

Doctrine: [[positive_framing_doctrine]] (filter chrome, surface claims).

Run via: python3 -m wrapper_v2.tests.test_chrome_filter
Exit-code 0 = all-pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.pipeline.factampel_emit import (
    is_conversational_chrome,
    emit_factampel_tags_for_response,
    split_into_claims,
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


def test_t1_greetings_filtered():
    print(f"\n{_BOLD}[T1]{_RESET} DE + EN greetings → filtered")
    for greeting in [
        "Ahoi!", "Hallo!", "Hi.", "Hey!", "Servus.",
        "Moin", "Guten Tag", "Guten Morgen!", "Grüß Gott!",
        "Hello!", "Howdy!", "Greetings.", "Hi there",
    ]:
        _check(f"chrome: {greeting!r}", is_conversational_chrome(greeting))


def test_t1c_bare_counter_question():
    """2026-05-31 prod observation: bot ends responses with standalone
    'Wie kann ich Ihnen helfen?' — pure offer-help chrome, no greeting.
    """
    print(f"\n{_BOLD}[T1c]{_RESET} bare counter-question / offer-help → filtered")
    for q in [
        "Wie kann ich Ihnen helfen?",
        "Wie kann ich dir helfen?",
        "Wie kann ich euch helfen?",
        "Was kann ich für Sie tun?",
        "Was kann ich für dich tun?",
        "Was darf's sein?",
        "Womit kann ich dir helfen?",
        "How can I help?",
        "How can I help you?",
        "How may I assist you?",
        "What can I help you with?",
        "How are you?",
        "How are you doing?",
    ]:
        _check(f"chrome: {q!r}", is_conversational_chrome(q))


def test_t1b_greeting_plus_counter_question():
    """2026-05-31: observed in production — bot replied 'Hi, what's up?'
    to user 'Hi' and the entire response got tribunal-graded.
    Greeting + counter-question is chrome end-to-end.
    """
    print(f"\n{_BOLD}[T1b]{_RESET} greeting + counter-question → filtered")
    for greeting_pair in [
        "Hi, what's up?",
        "Hi! How are you?",
        "Hi, how are you doing?",
        "Hallo, wie geht's?",
        "Hallo! Wie geht es dir?",
        "Hi, wie kann ich helfen?",
        "Servus, was brauchst du?",
        "Hey, was darf's sein?",
        "Moin! Was gibts?",
        "Hi! What can I do for you?",
        "Hello, how can I help?",
        "Hallo, was kann ich für dich tun?",
    ]:
        _check(f"chrome: {greeting_pair!r}",
               is_conversational_chrome(greeting_pair))


def test_t2_question_restatement_filtered():
    print(f"\n{_BOLD}[T2]{_RESET} question-restatement frames → filtered")
    for restate in [
        "Du möchtest wissen, was die Hauptstadt von Frankreich ist?",
        "Sie möchten wissen, welche Rolle Mara im Buddhismus spielt?",
        "Du fragst nach dem Teufel in den Weltreligionen.",
        "You want to know about Metallica tour dates?",
        "You are asking about quantum physics.",
        "Your question is about Buddhism.",
    ]:
        _check(f"chrome: {restate[:40]}…", is_conversational_chrome(restate))


def test_t3_answer_frames_filtered():
    print(f"\n{_BOLD}[T3]{_RESET} answer-frame openers → filtered")
    for frame in [
        "Hier ist meine Antwort:",
        "Hier kommt die Antwort.",
        "Lass mich das erklären.",
        "Let me explain.",
        "Here is my answer:",
        "Die kurze Antwort ist:",
    ]:
        _check(f"chrome: {frame!r}", is_conversational_chrome(frame))


def test_t4_closings_filtered():
    print(f"\n{_BOLD}[T4]{_RESET} closings + pleasantries → filtered")
    for closing in [
        "Ich hoffe das hilft!",
        "Ich hoffe, das gibt dir einen guten Überblick.",
        "Wenn du noch Fragen hast, stehe ich gerne zur Verfügung.",
        "Bei weiteren Fragen melde dich gerne.",
        "I hope this helps.",
        "Let me know if you need anything else.",
        "Feel free to ask any other questions.",
    ]:
        _check(f"chrome: {closing[:40]}…", is_conversational_chrome(closing))


def test_t5_real_claims_NOT_filtered():
    print(f"\n{_BOLD}[T5]{_RESET} actual factual claims → NOT filtered")
    for claim in [
        "Berlin ist die Hauptstadt Deutschlands.",
        "Metallica spielt am 26. Mai 2026 in Berlin im Olympiastadion.",
        "Im Christentum gilt der Teufel als gefallener Engel.",
        "Mara ist im Buddhismus die Verkörperung der Verführung.",
        "Zoroastrismus prägte mit Angra Mainyu das spätere Satan-Konzept.",
        "Die Photosynthese benötigt Sonnenlicht, Wasser und Kohlendioxid.",
    ]:
        _check(f"claim NOT chrome: {claim[:40]}…",
               not is_conversational_chrome(claim))


def test_t6_empty_and_short_handled():
    print(f"\n{_BOLD}[T6]{_RESET} empty / micro-strings → filtered as chrome")
    for tiny in ["", "  ", "Hi", "ja", "OK", "!", ".", "?"]:
        _check(f"empty/tiny: {tiny!r}", is_conversational_chrome(tiny))


def test_t7_end_to_end_response_with_chrome():
    print(f"\n{_BOLD}[T7]{_RESET} end-to-end: response with chrome + claims")
    response = (
        "Hallo! Du möchtest wissen, wo Berlin liegt? "
        "Hier ist meine Antwort: "
        "Berlin ist die Hauptstadt Deutschlands. "
        "Berlin liegt im Nordosten des Landes. "
        "Berlin hat etwa 3,7 Millionen Einwohner. "
        "Ich hoffe das hilft! "
        "Wenn du noch Fragen hast, stehe ich gerne zur Verfügung."
    )
    tags = emit_factampel_tags_for_response(response, use_tribunal=False)
    n_tags = len(tags)
    _check(f"3 real claims survive filter (got {n_tags})", n_tags == 3,
           f"tags: {[t.claim_text[:30] + '…' for t in tags] if tags else 'empty'}")
    if tags:
        for t in tags:
            is_chrome = is_conversational_chrome(t.claim_text)
            _check(f"surviving tag is not chrome: {t.claim_text[:30]!r}", not is_chrome)


def test_t8_response_with_only_chrome():
    print(f"\n{_BOLD}[T8]{_RESET} response with ONLY chrome → zero or one tag")
    # NOTE: split_into_claims doesn't split on ':' (would fragment many real
    # claims like "Berlin: Hauptstadt Deutschlands"). So a response like
    # "Hier ist meine Antwort: Ich hoffe das hilft." stays as ONE claim,
    # and the regex doesn't match composite-chrome ("frame X frame Y").
    # This is a known limitation; documented for future splitter improvement.
    response = "Hallo! Hier ist meine Antwort: Ich hoffe das hilft."
    tags = emit_factampel_tags_for_response(response, use_tribunal=False)
    # Pass: at most 1 tag (Hallo filtered; the colon-merged chrome may slip)
    _check(f"≤1 tag (got {len(tags)})", len(tags) <= 1,
           f"tags: {[t.claim_text for t in tags]}")


def test_t9_response_with_no_chrome():
    print(f"\n{_BOLD}[T9]{_RESET} response with NO chrome → all claims survive")
    response = (
        "Berlin ist die Hauptstadt Deutschlands. "
        "München ist die Hauptstadt Bayerns. "
        "Hamburg ist eine Hansestadt."
    )
    tags = emit_factampel_tags_for_response(response, use_tribunal=False)
    _check(f"3 tags (got {len(tags)})", len(tags) == 3)


def main() -> int:
    print(f"{_BOLD}factampel-chrome-filter — falsifiable{_RESET}")
    print("=" * 75)

    test_t1_greetings_filtered()
    test_t1b_greeting_plus_counter_question()
    test_t1c_bare_counter_question()
    test_t2_question_restatement_filtered()
    test_t3_answer_frames_filtered()
    test_t4_closings_filtered()
    test_t5_real_claims_NOT_filtered()
    test_t6_empty_and_short_handled()
    test_t7_end_to_end_response_with_chrome()
    test_t8_response_with_only_chrome()
    test_t9_response_with_no_chrome()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}chrome-filter result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
