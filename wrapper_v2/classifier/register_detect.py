"""classifier/register_detect — D7 dedup: consolidated register detection.

Per R1 D7 drift-target ("multiple register-detection systems") +
R2 §4.4. Consolidates two v1 paths:

  v1: detect_query_register      (cheap regex, tone-only)
  v1: auto_style_mirror_system_msg (consumer of detect_query_register)
  v1: detect_irony_register      (LLM-based, figurative/ironic detection)
  v1: irony_register_system_msg  (consumer of detect_irony_register)

into ONE typed module:
  - RegisterResult dataclass carries BOTH tone-dimension AND irony-
    dimension as separate fields (composable, not collapsed)
  - detect_register(msg) runs the cheap path always; optionally adds
    irony if an LLM adapter is registered (and the message is long
    enough to warrant the cost)
  - build_system_message(result, lang) assembles ONE consolidated
    system-msg-dict that respects both dimensions

Result-shape:
  RegisterResult(
    tone           = "casual" | "professional" | "academic" | "basic",
    irony          = "literal" | "ironic" | "figurative" | None,
    confidence     = float,
    applied_dimensions = ["tone", "irony"]  # which paths fired
  )

Doctrine anchors:
  - [[1455xl_chassis_goal_driven_funnel]] reziprok prompt-to-result
  - [[vulnerable_user_protection_reziprok_ceiling]] mirror has a
    CEILING; never mirror despair/self-harm register, redirect-instead
  - [[basetouch_verified_then_dollschon_overclock]] dedup-before-overclock
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import Callable, Optional


# ─── Enums ──────────────────────────────────────────────────────────────


class Tone(str, enum.Enum):
    CASUAL = "casual"               # locker, gespraechig (operator's term)
    PROFESSIONAL = "professional"   # default — neutral business-register
    ACADEMIC = "academic"           # formal, structured, citation-aware
    BASIC = "basic"                 # too-short-to-classify; fallback


class Irony(str, enum.Enum):
    LITERAL = "literal"             # straight statement / question
    IRONIC = "ironic"               # sarcasm / opposite-meaning marker
    FIGURATIVE = "figurative"       # metaphor / hyperbole / vocab-shift


# ─── Result dataclass ──────────────────────────────────────────────────


@dataclass
class RegisterResult:
    """Consolidated register-detection output. Either dimension may be
    None if the path didn't run (e.g. irony_adapter not registered)."""

    tone: Tone = Tone.BASIC
    irony: Optional[Irony] = None
    confidence: float = 0.0
    applied_dimensions: list = field(default_factory=list)
    notes: str = ""

    def needs_mirror(self) -> bool:
        """True if either dimension warrants a system-message-mirror."""
        return self.tone != Tone.BASIC or self.irony is not None

    def is_vulnerable_register(self) -> bool:
        """Caller-check per [[vulnerable_user_protection_reziprok_ceiling]].

        Currently False (stub) — the actual vulnerable-detector lives in
        l0_vulnerable.py and must be consulted BEFORE this module's
        system-message is applied. Documented here as the doctrinal
        contract: register-mirror MUST NOT proceed if vulnerable.
        """
        return False  # delegated to l0_vulnerable.py at call-site


# ─── Cheap path: tone-only regex ───────────────────────────────────────


# Operator-curated tone-markers (DE-first per DACH-default).
# Pattern-membership counts; threshold tunes the classifier confidence.
_CASUAL_MARKERS = [
    r"\b(naja|gell|halt|oida|alta|dude|bro|mann|kumpel)\b",
    r"\b(passt schon|geht klar|nice|cool|krass)\b",
    r"\b(joa|jo|jup|jep|na klar)\b",
    r"\bhalbsatz\b",
    r"[!]{2,}|[?]{2,}",                # double-punctuation emphasis
    r"\b(ich mein|sag mal|du weißt)\b",
]

_ACADEMIC_MARKERS = [
    r"\b(hierbei|insofern|demgemäss|nichtsdestoweniger|gleichwohl)\b",
    r"\b(methodologisch|paradigmatisch|epistemologisch|hermeneutisch)\b",
    r"\b(operationalisier|signifikant|korreliert)\b",
    r"\b(in der Literatur|nach .{1,30} 20\d\d)\b",  # citation-shaped
    r"\bvgl\.|\bz\.B\.|\bd\.h\.|\bbzw\.",
    r"\b(framework|paradigma|hypothese|operationaliser)",
]

_CASUAL_RX = re.compile("|".join(_CASUAL_MARKERS), re.IGNORECASE)
_ACADEMIC_RX = re.compile("|".join(_ACADEMIC_MARKERS), re.IGNORECASE)


def _detect_tone_cheap(message: str) -> tuple[Tone, float]:
    """Cheap regex-based tone detection. Returns (tone, confidence).

    Confidence is hit-count-normalized (0.0 → no signal, 1.0 → strong).
    Returns BASIC if message is too short OR no markers match.
    """
    if not message or len(message.strip()) < 8:
        return Tone.BASIC, 0.0

    casual_hits = len(_CASUAL_RX.findall(message))
    academic_hits = len(_ACADEMIC_RX.findall(message))

    if academic_hits >= 2 and academic_hits > casual_hits:
        conf = min(1.0, academic_hits / 4.0)
        return Tone.ACADEMIC, conf
    if casual_hits >= 1 and casual_hits > academic_hits:
        conf = min(1.0, casual_hits / 3.0)
        return Tone.CASUAL, conf
    # default for substantial-but-neutral messages
    return Tone.PROFESSIONAL, 0.5


# ─── Optional LLM path: irony-detection adapter ───────────────────────


# Irony-adapter takes a text + returns dict-like: {label: "literal"/
# "ironic"/"figurative", confidence: 0.0-1.0}. Real impl wraps v1
# detect_irony_register (LLM-based); tests pass mocks.
IronyAdapter = Callable[[str], Optional[dict]]


_IRONY_ADAPTER: Optional[IronyAdapter] = None


def register_irony_adapter(adapter: Optional[IronyAdapter]) -> None:
    """Install the LLM-based irony classifier (or None to clear)."""
    global _IRONY_ADAPTER
    _IRONY_ADAPTER = adapter


# Cost-gate: only run the LLM adapter for messages long enough to
# warrant the latency. Short messages get cheap-tone-only.
_IRONY_MIN_CHARS = 80


# ─── Public entry ──────────────────────────────────────────────────────


def detect_register(
    message: str,
    *,
    run_irony: bool = True,
) -> RegisterResult:
    """Consolidated register-detection. Single public entry per D7 dedup.

    Always runs cheap tone-regex. Conditionally runs irony adapter:
      - only if run_irony=True AND adapter registered AND
        len(message) >= _IRONY_MIN_CHARS

    Returns RegisterResult with both dimensions populated as available.
    """
    tone, tone_conf = _detect_tone_cheap(message)
    applied = ["tone"]
    irony_label: Optional[Irony] = None
    irony_conf = 0.0
    notes = []

    if (run_irony
            and _IRONY_ADAPTER is not None
            and message
            and len(message) >= _IRONY_MIN_CHARS):
        try:
            ir = _IRONY_ADAPTER(message)
            if isinstance(ir, dict):
                lbl = ir.get("label") or ir.get("register")
                if lbl in {"literal", "ironic", "figurative"}:
                    irony_label = Irony(lbl)
                    irony_conf = float(ir.get("confidence", 0.5))
                    applied.append("irony")
                else:
                    notes.append(f"irony adapter returned unknown label: {lbl!r}")
        except Exception as exc:
            notes.append(f"irony adapter raised: {exc!r}")

    # Composite confidence: weighted avg of dimensions that fired
    confidences = [tone_conf]
    if irony_label is not None:
        confidences.append(irony_conf)
    composite_conf = sum(confidences) / max(len(confidences), 1)

    return RegisterResult(
        tone=tone,
        irony=irony_label,
        confidence=composite_conf,
        applied_dimensions=applied,
        notes="; ".join(notes),
    )


# ─── System-message composer ───────────────────────────────────────────


_TONE_SYSMSG = {
    Tone.CASUAL: {
        "de": ("ANTWORT-REGISTER: casual / gespraechig. Spiegele den Ton: "
               "locker, freundlich, kurz. 1-4 Saetze."),
        "en": ("RESPONSE-REGISTER: casual / conversational. Mirror the tone: "
               "relaxed, friendly, brief. 1-4 sentences."),
    },
    Tone.ACADEMIC: {
        "de": ("ANTWORT-REGISTER: academic / strukturiert. Formaler Stil mit "
               "Quellenhinweisen wo passend; Hypothese → Befund → Diskussion."),
        "en": ("RESPONSE-REGISTER: academic / structured. Formal style with "
               "citations where appropriate; hypothesis → finding → discussion."),
    },
    Tone.PROFESSIONAL: {
        "de": ("ANTWORT-REGISTER: professional / neutral. Klare Fakten, "
               "respektvoll, moderate Laenge."),
        "en": ("RESPONSE-REGISTER: professional / neutral. Clear facts, "
               "respectful, moderate length."),
    },
    Tone.BASIC: {
        "de": "",  # default: no system-msg
        "en": "",
    },
}

_IRONY_SYSMSG = {
    Irony.IRONIC: {
        "de": "Achtung: Eingabe ist ironisch / sarkastisch — interpretiere im uebertragenen Sinn.",
        "en": "Note: input is ironic / sarcastic — interpret figuratively.",
    },
    Irony.FIGURATIVE: {
        "de": "Achtung: Eingabe nutzt figurative / metaphorische Sprache.",
        "en": "Note: input uses figurative / metaphorical language.",
    },
    Irony.LITERAL: {
        "de": "",  # default: no extra
        "en": "",
    },
}


def build_system_message(
    result: RegisterResult,
    *,
    lang: str = "de",
) -> Optional[dict]:
    """Assemble ONE consolidated system-message-dict from a RegisterResult.

    Returns None if nothing to add (BASIC tone + no irony or LITERAL irony).
    Lang defaults to DE per DACH-default.
    """
    if not result.needs_mirror():
        return None

    tone_part = _TONE_SYSMSG.get(result.tone, {}).get(lang, "")
    irony_part = ""
    if result.irony is not None:
        irony_part = _IRONY_SYSMSG.get(result.irony, {}).get(lang, "")

    parts = [p for p in (tone_part, irony_part) if p]
    if not parts:
        return None

    content = "\n\n".join(parts)
    return {
        "role": "system",
        "content": content,
        "_register": result.tone.value,
        "_irony": result.irony.value if result.irony else None,
    }


__all__ = [
    "Tone", "Irony", "RegisterResult",
    "IronyAdapter", "register_irony_adapter",
    "detect_register", "build_system_message",
]
