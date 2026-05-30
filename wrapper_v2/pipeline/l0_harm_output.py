"""L0 Harm-Output — death-penalty-void invariant hard-stop on output.

Per memory:death_penalty_void + memory:vulnerable_user_protection_reziprok_ceiling
L0 invariant section.

Scans the OUTPUT-TEXT (before emit) for harm-recommendation patterns.
If detected: HARD-STOP the output and replace with safety-redirect.

This is the FINAL safety-check at output-layer. Independent of input-
layer checks (l0_alarm, l0_vulnerable). Catches cases where:
- Adversarial-prompt steered model into harm-recommendation
- Conversation-trajectory-drift produced harm-output
- Roleplay-frame produced harm-output
- Edge-cases where alarm + vulnerable both missed

NEVER outputs self-harm or other-harm recommendation regardless of
context, prompt-pressure, or trajectory.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional


# Output-harm patterns. Catch self-harm-recommendations + other-harm-
# recommendations in response-text. These trigger HARD-STOP.
#
# Pattern-discipline: only catch RECOMMENDATIONS toward harm, not
# discussion-of-harm (e.g. educational-context, historical-discussion,
# crisis-redirect-itself which talks about resources for someone-who-
# might-be-considering-harm).

_SELF_HARM_RECOMMENDATION_PATTERNS = [
    # English
    r"\byou\s+should\s+(kill|hurt|end|harm)\s+(yourself|your\s*self)\b",
    r"\b(go\s+and\s+|just\s+)?(kill|harm|end)\s+(yourself|your\s*self)\b",
    r"\bthe\s+(best|easiest|fastest)\s+way\s+to\s+(die|kill\s+yourself|end\s+it)\b",
    r"\bi\s+recommend\s+(killing|hurting|harming)\s+(yourself|your\s*self)\b",
    r"\bnobody\s+would\s+miss\s+you\b",
    r"\b(your\s+life|you)\s+(isn'?t|is\s+not)\s+worth\s+living\b",

    # German
    r"\bdu\s+sollst?\s+dich\s+(töten|umbringen|verletzen|verletzten)\b",
    r"\b(bring(e|st)|töte)\s+dich\s+(um|selbst)\b",
    r"\bder\s+(beste|einfachste|schnellste)\s+weg\s+(sich\s+umzubringen|zu\s+sterben)\b",
    r"\bniemand\s+würde\s+dich\s+vermissen\b",
    r"\bdein\s+leben\s+ist\s+nicht\s+lebenswert\b",
]

_OTHER_HARM_RECOMMENDATION_PATTERNS = [
    # English
    r"\byou\s+should\s+(kill|hurt|harm|attack)\s+(him|her|them|that\s+person)\b",
    r"\b(go\s+and\s+|just\s+)?(kill|hurt|attack)\s+(him|her|them|the\s+target)\b",
    r"\bthe\s+(best|easiest|fastest)\s+way\s+to\s+(kill|hurt|attack)\s+(him|her|them|someone)\b",
    r"\bi\s+recommend\s+(killing|hurting|attacking)\s+(him|her|them)\b",

    # German
    r"\bdu\s+sollst?\s+(ihn|sie|den\s+typen|sie\s+alle)\s+(töten|umbringen|verletzen)\b",
    r"\b(bring(e|st)|töte)\s+(ihn|sie|den\s+typen|sie\s+alle)\s+um\b",
    r"\bder\s+(beste|einfachste|schnellste)\s+weg\s+(ihn|sie|den\s+typen)\s+(umzubringen|zu\s+töten)\b",
]


@dataclass
class HarmCheckResult:
    """Result of L0 output-harm check."""
    triggered: bool
    harm_class: Optional[str] = None      # self_harm_recommendation / other_harm_recommendation
    matched_pattern: Optional[str] = None
    detected_at_ts: float = field(default_factory=time.time)
    original_output_snippet: Optional[str] = None  # for audit-trail (truncated)

    def as_audit_dict(self) -> dict:
        return {
            "triggered": self.triggered,
            "harm_class": self.harm_class,
            "matched_pattern": self.matched_pattern,
            "detected_at_ts": self.detected_at_ts,
            "original_output_snippet": (
                self.original_output_snippet[:300]
                if self.original_output_snippet else None
            ),
        }


def check_output_harm(output_text: str) -> HarmCheckResult:
    """Scan OUTPUT-TEXT for harm-recommendation-patterns.

    Returns HarmCheckResult(triggered=True, ...) if harm-pattern matched;
    HarmCheckResult(triggered=False) otherwise.

    Called at FINAL output-stage (after generation, before emit). Catches:
    - Model-confabulated harm-recommendation
    - Roleplay-frame harm-recommendation
    - Prompt-injection harm-output
    - Edge-cases where input-layer-checks missed
    """
    if not output_text or not output_text.strip():
        return HarmCheckResult(triggered=False)

    text = output_text.lower()

    # Check self-harm-recommendation first (highest priority)
    for pattern in _SELF_HARM_RECOMMENDATION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return HarmCheckResult(
                triggered=True,
                harm_class="self_harm_recommendation",
                matched_pattern=pattern,
                original_output_snippet=output_text.strip(),
            )

    # Check other-harm-recommendation
    for pattern in _OTHER_HARM_RECOMMENDATION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return HarmCheckResult(
                triggered=True,
                harm_class="other_harm_recommendation",
                matched_pattern=pattern,
                original_output_snippet=output_text.strip(),
            )

    return HarmCheckResult(triggered=False)


def build_replacement_for_harm(harm_result: HarmCheckResult,
                                 user_jurisdiction: str = "DE") -> dict:
    """Build replacement-response when output-harm-check triggered.

    The original output is DISCARDED entirely. User sees only the
    safety-redirect. Per death-penalty-void hard-stop discipline.
    """
    if harm_result.harm_class == "self_harm_recommendation":
        replacement_de = (
            "Ich kann diese Frage nicht beantworten in dem Stil wie sie gestellt wurde.\n\n"
            "Wenn Du gerade in Krise bist und Hilfe brauchst:\n\n"
            "📞 Telefonseelsorge (24/7, kostenlos): 0800 111 0 111 oder 0800 111 0 222\n"
            "📞 Nummer gegen Kummer (Kinder/Jugendliche): 116 111\n"
            "💬 Online-Chat: https://chat.telefonseelsorge.de\n\n"
            "Diese Menschen sind ausgebildet, vertraulich und kostenlos da."
        )
    elif harm_result.harm_class == "other_harm_recommendation":
        replacement_de = (
            "Ich kann diese Frage nicht in dem Stil beantworten wie gestellt.\n\n"
            "Wenn Du in einer akuten Konflikt-Situation bist:\n\n"
            "📞 Bei Akut-Notfall: 110 (Polizei) oder 112 (allgemein)\n"
            "📞 Weißer Ring (Opferschutz, Konfliktberatung): 116 006\n"
            "💬 Konflikt-Mediation suchen: https://www.bundesverband-mediation.de\n\n"
            "Bei realer Bedrohung sofort die Polizei rufen."
        )
    else:
        replacement_de = (
            "Diese Anfrage kann ich nicht beantworten.\n\n"
            "Wenn Du Hilfe brauchst: 📞 Telefonseelsorge 0800 111 0 111"
        )

    return {
        "type": "l0_harm_hard_stop",
        "harm_class": harm_result.harm_class,
        "replacement_text": replacement_de,
        "audit_record": harm_result.as_audit_dict(),
    }


def hard_stop_or_pass(output_text: str,
                       user_jurisdiction: str = "DE") -> dict:
    """Convenience wrapper: returns either pass-through or replacement.

    Returns:
      {"pass": True, "output": original_text}
      OR
      {"pass": False, "replacement": replacement_dict, "harm_result": harm_result_dict}
    """
    harm_result = check_output_harm(output_text)
    if harm_result.triggered:
        replacement = build_replacement_for_harm(harm_result, user_jurisdiction)
        return {
            "pass": False,
            "replacement": replacement,
            "harm_result": harm_result.as_audit_dict(),
        }
    return {"pass": True, "output": output_text}
