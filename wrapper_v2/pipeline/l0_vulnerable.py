"""L0 Vulnerable — Face-2 vulnerable-user-protection redirect-mode.

Per memory:vulnerable_user_protection_reziprok_ceiling.

Detects chronic-vulnerability-signals (emotional-distress, family-crisis,
mental-health-crisis, self-harm-disclosure, abuse-disclosure) and switches
the response into SERIOUS-redirect-mode instead of casual-conversation-
flow.

Bad-pattern operator-named (NEVER do):
  user: 'meine eltern streiten immer..'
  bad: 'huch aehm da haben die bestimmt gründe..'
  → creates parasocial-Verpflichtung + pseudo-therapy

Right-pattern:
  - Brief WARM acknowledgment (no curiosity-prying)
  - Honest chatbot-limitation
  - IMMEDIATE redirect to professional-help-resources
  - Jurisdiction-aware (DE/AT/CH/EU/US/UK)
  - NO follow-up question inviting more disclosure
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional


# Vulnerable-signal patterns. Multi-language coverage; bias toward
# false-positives per cost-asymmetry. ML-tuning is later.

_EMOTIONAL_DISTRESS_PATTERNS = [
    r"\b(ich\s+(fühle|fuehle)\s+mich\s+(so\s+)?allein|ganz\s+allein)\b",
    r"\b(i\s+feel\s+(so\s+)?(alone|lonely|empty))\b",
    r"\b(niemand\s+(versteht|hilft|hört)\s+mich)\b",
    r"\b(nobody\s+(understands|helps|listens)\s+me)\b",
    r"\b(ich\s+(kann|halte|schaff)\s+(es|das)\s+nicht\s+mehr)\b",
    r"\b(i\s+can'?t\s+(go\s+on|take\s+(it|this)\s+anymore))\b",
    r"\b(ich\s+(will|möchte)\s+nicht\s+mehr\s+(leben|sein|hier))\b",
    r"\b(i\s+don'?t\s+want\s+to\s+(live|be\s+here|exist))\b",
]

_FAMILY_CRISIS_PATTERNS = [
    r"\b(meine\s+eltern\s+(streiten|schlagen|trinken|kämpfen))\b",
    r"\b(my\s+parents\s+(fight|hit|drink|argue|are\s+fighting))\b",
    r"\b(mein\s+(vater|papa)\s+(schlägt|trinkt|hat\s+geschlagen))\b",
    r"\b(my\s+(dad|father)\s+(hits|hit|drinks|beat))\b",
    r"\b(meine\s+(mutter|mama)\s+(schlägt|trinkt|weint\s+immer))\b",
    r"\b(my\s+(mom|mother)\s+(hits|drinks|cries\s+all\s+the\s+time))\b",
]

_SELF_HARM_PATTERNS = [
    r"\b(ich\s+(schneide|ritze)\s+mich)\b",
    r"\b(i\s+(cut|hurt|harm)\s+myself)\b",
    r"\b(self\s*-?\s*harm)\b",
    r"\b(selbstverletzung)\b",
    r"\b(ich\s+will\s+mich\s+umbringen)\b",
    r"\b(i\s+want\s+to\s+(end\s+(it|myself)|die|kill\s+myself))\b",
    r"\b(suicid(e|al))\b",
    r"\b(suizid)\b",
]

_MENTAL_HEALTH_CRISIS_PATTERNS = [
    r"\b(panic\s+attack|panikattacke)\b",
    r"\b(ich\s+(höre|sehe)\s+(stimmen|dinge\s+die\s+nicht\s+da))\b",
    r"\b(i\s+(hear|see)\s+(voices|things\s+that\s+aren'?t\s+there))\b",
    r"\b(can'?t\s+stop\s+(crying|panicking|shaking))\b",
    r"\b(kann\s+nicht\s+aufhören\s+zu\s+(weinen|zittern))\b",
]

_ABUSE_DISCLOSURE_PATTERNS = [
    r"\b(mein\s+(onkel|opa|lehrer|trainer|vater)\s+(hat\s+mich|berührt))\b",
    r"\b(my\s+(uncle|grandpa|teacher|coach|father)\s+(touched|hurt)\s+me)\b",
    r"\b(missbrauch)\b",
    r"\b((sexual\s+)?abuse)\b",
]


@dataclass
class VulnerableResult:
    """Result of vulnerable-signal check."""
    triggered: bool
    signal_class: Optional[str] = None   # emotional_distress / family_crisis / self_harm / mental_health_crisis / abuse_disclosure
    matched_pattern: Optional[str] = None
    confidence: str = "low"               # low / medium / high
    detected_at_ts: float = field(default_factory=time.time)

    def as_audit_dict(self) -> dict:
        return {
            "triggered": self.triggered,
            "signal_class": self.signal_class,
            "matched_pattern": self.matched_pattern,
            "confidence": self.confidence,
            "detected_at_ts": self.detected_at_ts,
        }


def _scan_patterns(text: str, patterns: list[str]) -> Optional[str]:
    """Return the first matched-pattern, or None."""
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return pattern
    return None


def check_vulnerable(user_input: str,
                     history: Optional[list[dict]] = None) -> VulnerableResult:
    """Detect chronic-vulnerable-signals in user-input.

    For M1 stub: scans current input against pattern-libraries per
    signal-class. Multi-turn-trajectory-drift detection is M3 territory.

    Returns VulnerableResult(triggered=True, signal_class=..., matched_pattern=...)
    on first-pattern-match.
    """
    if not user_input or not user_input.strip():
        return VulnerableResult(triggered=False)

    text = user_input.lower().strip()

    # Check signal-classes in priority-order (self-harm first = highest-risk)
    pattern_groups = [
        ("self_harm", _SELF_HARM_PATTERNS, "high"),
        ("abuse_disclosure", _ABUSE_DISCLOSURE_PATTERNS, "high"),
        ("mental_health_crisis", _MENTAL_HEALTH_CRISIS_PATTERNS, "medium"),
        ("emotional_distress", _EMOTIONAL_DISTRESS_PATTERNS, "medium"),
        ("family_crisis", _FAMILY_CRISIS_PATTERNS, "medium"),
    ]

    for signal_class, patterns, confidence in pattern_groups:
        matched = _scan_patterns(text, patterns)
        if matched:
            return VulnerableResult(
                triggered=True,
                signal_class=signal_class,
                matched_pattern=matched,
                confidence=confidence,
            )

    return VulnerableResult(triggered=False)


def build_redirect_response(vulnerable_result: VulnerableResult,
                              user_jurisdiction: str = "DE") -> dict:
    """Build Face-2 redirect-mode response with jurisdiction-aware
    professional-help-resources.

    Per memory:vulnerable_user_protection_reziprok_ceiling right-pattern:
    - Brief WARM acknowledgment (no curiosity-prying)
    - Honest chatbot-limitation
    - IMMEDIATE redirect to professional help
    - NO follow-up question inviting more disclosure
    """
    # Jurisdiction-aware help-resources
    resources_by_jurisdiction = {
        "DE": [
            {"name": "Nummer gegen Kummer (Kinder/Jugendliche)", "contact": "📞 116 111 (kostenlos, anonym, Mo-Sa 14-20 Uhr)"},
            {"name": "Telefonseelsorge (24/7)", "contact": "📞 0800 111 0 111 oder 0800 111 0 222 (kostenlos)"},
            {"name": "Online-Chat Beratung", "contact": "💬 https://chat.telefonseelsorge.de"},
            {"name": "Hilfetelefon Gewalt gegen Frauen", "contact": "📞 08000 116 016"},
            {"name": "Hilfe-Portal sexueller Missbrauch", "contact": "📞 0800 22 55 530"},
        ],
        "AT": [
            {"name": "Rat auf Draht (Kinder/Jugendliche)", "contact": "📞 147 (kostenlos, 24/7)"},
            {"name": "Telefonseelsorge", "contact": "📞 142"},
        ],
        "CH": [
            {"name": "Pro Juventute (Kinder/Jugendliche)", "contact": "📞 147 (kostenlos, 24/7)"},
            {"name": "Die Dargebotene Hand", "contact": "📞 143"},
        ],
        "EU": [
            {"name": "Kinder-Hotline (EU-harmonisiert)", "contact": "📞 116 111"},
            {"name": "Emotional Support (EU-harmonisiert)", "contact": "📞 116 123"},
        ],
        "US": [
            {"name": "988 Suicide and Crisis Lifeline", "contact": "📞 988 (call or text, 24/7)"},
            {"name": "Crisis Text Line", "contact": "💬 text HOME to 741741"},
            {"name": "National Child Abuse Hotline", "contact": "📞 1-800-422-4453"},
        ],
        "UK": [
            {"name": "Samaritans (24/7)", "contact": "📞 116 123"},
            {"name": "Childline (children/young people)", "contact": "📞 0800 1111"},
        ],
    }
    resources = resources_by_jurisdiction.get(user_jurisdiction,
                                                resources_by_jurisdiction["EU"])

    # Brief warm acknowledgment per signal-class
    acknowledgments_de = {
        "self_harm": "Das tut weh, was Du gerade durchmachst.",
        "abuse_disclosure": "Es ist mutig, das zu teilen — und das, was Dir passiert ist, ist nicht Deine Schuld.",
        "mental_health_crisis": "Was Du gerade fühlst, ist real und schwer.",
        "emotional_distress": "Was Du gerade durchmachst, ist wirklich schwer.",
        "family_crisis": "Das tut weh, was bei Euch zu Hause los ist.",
    }
    ack_de = acknowledgments_de.get(vulnerable_result.signal_class,
                                     "Was Du gerade durchmachst, ist schwer.")

    resource_lines = "\n".join(f"{r['contact']}  — {r['name']}" for r in resources)

    return {
        "type": "l0_vulnerable_redirect",
        "signal_class": vulnerable_result.signal_class,
        "confidence": vulnerable_result.confidence,
        "response_de": (
            f"{ack_de}\n\n"
            f"Du verdienst jemanden, der wirklich zuhören und helfen kann — "
            f"das ist mehr als ich als Chatbot kann.\n\n"
            f"{resource_lines}\n\n"
            f"Diese Menschen sind ausgebildet, mit solchen Situationen umzugehen. "
            f"Sie reden vertraulich mit Dir."
        ),
        "vulnerable_result": vulnerable_result.as_audit_dict(),
    }
