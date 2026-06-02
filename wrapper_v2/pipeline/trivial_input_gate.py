"""pipeline/trivial_input_gate — pre-classifier fast-path for trivial inputs.

Sibling of `detect_bare_greeting` in wrapper_cc.py — that one catches a
bare greeting like "Hi" or "Hallo" and short-circuits to a canned mirror
reply at ~100ms. This module extends the catalog to:

  - greeting + counter-Q     ("hi wie gehts", "hallo, wie geht's?")
  - bare counter-Q           ("wie geht's?", "what's up?", "alles gut?")
  - thanks                   ("danke", "thanks", "merci")
  - acknowledgment           ("ok", "alles klar", "verstanden")
  - farewell                 ("bye", "tschüss", "ciao")

All match the FULL stripped message (case-insensitive). "ok kannst du
mir helfen?" does NOT match — only standalone trivials short-circuit.

Production motivation: "hi wie gehts" still ran full classifier-chain
(~19s) because detect_bare_greeting requires exact-greeting match. This
gate plugs that gap so all conversational pleasantries get sub-200ms
canned replies.

Doctrine:
  - [[wirkung_driven_choice_principle]] — reciprocal short reply matches
    the user's register; LLM-generated etymology-lecture would not.
  - [[smartfaul_doctrine]] — gate as cheap filter; full pipeline only
    when content actually warrants it.

Public API:
  TrivialMatch (dataclass)
  detect_trivial_input(message) -> Optional[TrivialMatch]
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class TrivialMatch:
    """A matched trivial-input + the canned reply to send."""
    category: str       # greeting_q | bare_counter_q | thanks | ack | farewell
    reply: str          # what to send back
    lang_code: str      # for downstream language-priming (de/en/es/...)


# ─── Strip / normalization ─────────────────────────────────────────────


# Same strip-set as wrapper_cc._GREETING_STRIP_RX: whitespace, punctuation,
# brackets, emoticons, greeting emoji.
_STRIP_RX = re.compile(
    r"[\s!.,;:?~\-_]+|"
    r"[(){}\[\]<>]+|"
    r"[:;=8][\-^']?[)\(DPpoO/\\\|]"
    r"|[)\(DPpoO/\\\|][\-^']?[:;=8]"
    r"|[😀-🙏✨💫⭐️🌟❤️♥️👋🤗🫶]+",
)


def _strip(message: str) -> str:
    """Strip emoticons + punctuation + brackets like detect_bare_greeting does."""
    if not message:
        return ""
    cleaned = _STRIP_RX.sub(" ", message).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.lower()


# ─── Pattern table ─────────────────────────────────────────────────────


# Greeting prefixes (DE/EN/ES/IT/FR/PT) — kept tight, must precede a counter-Q
_GREETING_PREFIX = (
    r"(?:hi+|hello+|hey+|howdy|yo+|"
    r"hallo+|hallöchen|ahoi+|moin(?:\s*moin)?|servus(?:\s+auch)?|servas(?:\s+oida)?|"
    r"gr(?:ü|ue)(?:ss|ß)\s+(?:di|gott|dich|euch)|tach(?:chen)?|na(?:\s+du)?|"
    r"hola+|buenas|"
    r"ciao+|salve|"
    r"salut|bonjour|coucou|"
    r"ol(?:á|a))"
)

# Counter-question phrases (DE/EN/ES/IT/FR)
_COUNTER_Q_DE = (
    r"(?:"
    r"wie\s+geht'?s(?:\s+(?:dir|euch|ihnen|so))?|"
    r"wie\s+geht\s+es\s+(?:dir|euch|ihnen|so)?|"
    r"was\s+geht|"
    r"was\s+machst\s+du(?:\s+so)?|"
    r"was\s+gibt'?s(?:\s+neues)?|"
    r"alles\s+(?:gut|klar|in\s+ordnung|paletti)|"
    r"wie\s+läuft'?s|"
    r"na\s+wie\s+geht'?s"
    r")"
)
_COUNTER_Q_EN = (
    r"(?:"
    r"what'?s\s+up|"
    r"how\s+are\s+(?:you|things|you\s+doing)|"
    r"how'?s\s+it\s+going|"
    r"how\s+have\s+you\s+been|"
    r"how\s+goes\s+it|"
    r"what'?s\s+new|"
    r"how\s+ya\s+doing|"
    # slang variants (d.1 2026-06-02) — "whazzup", "wassup", "sup", "wazzup"
    r"wh?[ae][sz]+[au]p|"
    r"sup|"
    r"what\s+up|"
    r"yo+\s+(?:bro|man|dude)"
    r")"
)
_COUNTER_Q_ES = r"(?:qu(?:é|e)\s+tal|c(?:ó|o)mo\s+est(?:á|a)s|qu(?:é|e)\s+pasa)"
_COUNTER_Q_IT = r"(?:come\s+(?:va|stai|state))"
_COUNTER_Q_FR = r"(?:(?:ça|ca)\s+va|comment\s+(?:ça|ca)\s+va|quoi\s+de\s+neuf)"

_COUNTER_Q_ANY = (
    rf"(?:{_COUNTER_Q_DE}|{_COUNTER_Q_EN}|{_COUNTER_Q_ES}|"
    rf"{_COUNTER_Q_IT}|{_COUNTER_Q_FR})"
)

# Separators between greeting and counter-Q (or none, or just whitespace)
_SEP = r"(?:\s*[,;.!:—–-]?\s+)"


# Patterns. Order matters — first match wins.
# Each entry: (compiled_full_match_regex, category, reply, lang_code)
_PATTERNS: list = []


def _add(pat: str, category: str, reply: str, lang: str) -> None:
    _PATTERNS.append((re.compile(rf"^{pat}$", re.IGNORECASE | re.UNICODE),
                      category, reply, lang))


# ─── (1) Greeting + counter-Q  (lang-tagged from counter-Q phrase) ────

# Cross-language greeting+counter-Q (d.1 2026-06-02): allow ANY greeting
# prefix + ANY counter-Q. Reply language picks from counter-Q (since that's
# the more recent active register — "ahoi whazzup" → EN reply).
# Order: language-specific counter-Q determines reply language.
_add(rf"{_GREETING_PREFIX}{_SEP}{_COUNTER_Q_DE}",
     "greeting_q",
     "Hi! Mir geht's gut, danke. Was kann ich für dich tun?",
     "de")
_add(rf"{_GREETING_PREFIX}{_SEP}{_COUNTER_Q_EN}",
     "greeting_q",
     "Hey! Doing well, thanks. What's on your mind?",
     "en")
_add(rf"{_GREETING_PREFIX}{_SEP}{_COUNTER_Q_ES}",
     "greeting_q",
     "¡Hola! Todo bien, gracias. ¿En qué te ayudo?",
     "es")
_add(rf"{_GREETING_PREFIX}{_SEP}{_COUNTER_Q_IT}",
     "greeting_q",
     "Ciao! Tutto bene, grazie. Come posso aiutarti?",
     "it")
_add(rf"{_GREETING_PREFIX}{_SEP}{_COUNTER_Q_FR}",
     "greeting_q",
     "Salut ! Ça va bien, merci. Comment puis-je t'aider ?",
     "fr")


# ─── (2) Bare counter-Q ─────────────────────────────────────────────────

_add(_COUNTER_Q_DE,
     "bare_counter_q",
     "Mir geht's gut, danke. Was beschäftigt dich?",
     "de")
_add(_COUNTER_Q_EN,
     "bare_counter_q",
     "Doing well, thanks. What's on your mind?",
     "en")
_add(_COUNTER_Q_ES,
     "bare_counter_q",
     "Todo bien, gracias. ¿En qué te ayudo?",
     "es")
_add(_COUNTER_Q_IT,
     "bare_counter_q",
     "Tutto bene, grazie. Come posso aiutarti?",
     "it")
_add(_COUNTER_Q_FR,
     "bare_counter_q",
     "Ça va bien, merci. Comment puis-je t'aider ?",
     "fr")


# ─── (3) Thanks ─────────────────────────────────────────────────────────

_add(r"(?:vielen\s+)?(?:dank(?:e|eschön|e\s+sehr|e\s+dir|e\s+vielmals)?|"
     r"merci(?:\s+vielmals)?)",
     "thanks",
     "Bitte gern! Sag Bescheid, wenn noch was ist.",
     "de")
_add(r"(?:thanks(?:\s+a\s+lot|\s+a\s+bunch)?|thank\s+you(?:\s+so\s+much|\s+very\s+much)?|"
     r"thx|ty|cheers)",
     "thanks",
     "You're welcome! Let me know if anything else comes up.",
     "en")
_add(r"(?:gracias(?:\s+mil)?|muchas\s+gracias)",
     "thanks",
     "¡De nada! Avísame si surge algo más.",
     "es")
_add(r"(?:grazie(?:\s+mille)?)",
     "thanks",
     "Prego! Fammi sapere se hai bisogno di altro.",
     "it")
_add(r"(?:merci\s+beaucoup|merci(?:\s+bien)?)",
     "thanks",
     "Avec plaisir ! N'hésite pas si tu as besoin d'autre chose.",
     "fr")


# ─── (4) Acknowledgments ────────────────────────────────────────────────

_add(r"(?:ok(?:ay|i+)?|alles\s+klar|verstanden|passt(?:\s+scho)?|"
     r"in\s+ordnung)",
     "ack",
     "Alles klar. Sag Bescheid, wenn was kommt.",
     "de")
_add(r"(?:got\s+it|alright|all\s+right|gotcha|sounds\s+good|cool|"
     r"makes\s+sense|understood)",
     "ack",
     "Got it. Let me know if anything else comes up.",
     "en")


# ─── (5) Farewell ───────────────────────────────────────────────────────

_add(r"(?:tsch(?:ü|ue)ss(?:i+)?|tschau|ade|bis\s+(?:bald|sp(?:ä|ae)ter|dann)|"
     r"bis\s+(?:morgen|gleich)|mach'?s\s+gut|mach'?s\s+besser|"
     r"sch(?:ö|oe)nen\s+(?:tag|abend|feierabend))",
     "farewell",
     "Tschüss, bis später!",
     "de")
_add(r"(?:bye(?:\s+bye)?|see\s+(?:ya|you)(?:\s+later)?|goodbye|"
     r"take\s+care|catch\s+you\s+later|later)",
     "farewell",
     "Bye! Take care.",
     "en")
_add(r"(?:ciao(?:\s+ciao)?|arrivederci|a\s+presto)",
     "farewell",
     "Ciao, a presto!",
     "it")
_add(r"(?:adi(?:ó|o)s|hasta\s+(?:luego|pronto|ma(?:ñ|n)ana))",
     "farewell",
     "¡Adiós, hasta luego!",
     "es")
_add(r"(?:au\s+revoir|salut(?:\s+les?)?|(?:à|a)\s+(?:plus|bient(?:ô|o)t|demain))",
     "farewell",
     "Au revoir, à bientôt !",
     "fr")


# ─── Public entry ──────────────────────────────────────────────────────


# Length-cap: trivial inputs are short by definition. Anything > 60 chars
# (after stripping) likely contains real content even if it starts with a
# pleasantry — don't fast-path it, let the full pipeline handle.
_MAX_TRIVIAL_LEN = 60


def detect_trivial_input(message: str) -> Optional[TrivialMatch]:
    """If `message` is a trivial input (pleasantry, ack, thanks, farewell,
    or greeting+counter-Q), return a TrivialMatch with canned reply.
    Otherwise None.

    Match is FULL — the entire stripped message must fit the pattern.
    "ok, kannst du mir helfen?" does NOT match (extra content after "ok").
    "hi wie gehts" DOES match (greeting + counter-Q only).
    """
    if not message:
        return None
    cleaned = _strip(message)
    if not cleaned or len(cleaned) > _MAX_TRIVIAL_LEN:
        return None

    for rx, category, reply, lang in _PATTERNS:
        if rx.match(cleaned):
            return TrivialMatch(category=category, reply=reply, lang_code=lang)
    return None


__all__ = ["TrivialMatch", "detect_trivial_input"]
