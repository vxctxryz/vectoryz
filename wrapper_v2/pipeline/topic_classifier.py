"""topic_classifier — 3-layer ISCED-F router (#188).

Classifies user-input into:
  L1 persona   (10 epistemic roles)
  L2 faculty   (ISCED-F broad field codes F00-F10) + FORD research overlay
  L3 method    (8 method types driving verification-stack config)
  + search_depth (BRUTAL/HIGH/MODERATE/LIGHTER)
  + confidence
  + ready-flag (per cognition-gate step 5)

The classifier is a tiny qwen2.5:7b JSON-mode call; output is validated against
config/topic_taxonomy.json. On any parse failure → safe defaults (scientist+auditor,
F00_generic, interpretive, MODERATE).

Per doctrine:
  - [[topic_router_isced_3layer_taxonomy]] — the canonical 3-layer model
  - [[modelfile_minimal_wrapper_first]] — router lives here, not in Modelfile
  - [[classifier_warmth_doctrine]] — qwen2.5:7b must stay CPU-pinned (#176 live)
  - [[search_discipline_universal]] — method's `search_depth` drives tribunal weight

Public API:
  classify_topic(text, lang_cluster) -> TopicRoute
  TopicRoute is a dataclass with persona/faculty/method/depth/etc.
  build_persona_system_message(route) -> str (for injection into model call)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
CLASSIFIER_MODEL = os.environ.get("TOPIC_CLASSIFIER_MODEL", "qwen2.5:7b")
CLASSIFIER_TIMEOUT_S = int(os.environ.get("TOPIC_CLASSIFIER_TIMEOUT_S", "30"))

_TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "config" / "topic_taxonomy.json"

_PERSONAS = [
    "scientist", "engineer", "jurist", "historian", "physician",
    "mathematician", "journalist", "storyteller", "operator", "auditor",
]
_FACULTIES = [
    "F00_generic", "F01_education", "F02_arts_humanities",
    "F03_social_sciences_journalism_information",
    "F04_business_administration_law",
    "F05_natural_sciences_math_statistics",
    "F06_information_communication_technologies",
    "F07_engineering_manufacturing_construction",
    "F08_agriculture_forestry_fisheries_veterinary",
    "F09_health_welfare", "F10_services",
]
_METHODS = [
    "empirical", "formal", "interpretive", "legal_normative",
    "engineering_design", "clinical_diagnostic", "operational", "creative",
]
_DEPTHS = ["BRUTAL", "HIGH", "MODERATE", "LIGHTER"]

# Method → default search-depth, per [[search_discipline_universal]]
_METHOD_DEFAULT_DEPTH = {
    "empirical": "HIGH",
    "formal": "HIGH",
    "interpretive": "MODERATE",
    "legal_normative": "BRUTAL",
    "engineering_design": "HIGH",
    "clinical_diagnostic": "BRUTAL",
    "operational": "LIGHTER",
    "creative": "LIGHTER",
}


@dataclass
class TopicRoute:
    persona: List[str] = field(default_factory=lambda: ["scientist", "auditor"])
    faculty_isced: str = "F00_generic"
    ford_overlay: Optional[str] = None
    method: str = "interpretive"
    search_depth: str = "MODERATE"
    confidence: float = 0.0
    invention_allowed: bool = False
    confab_channel_67_allowed: bool = False
    tuyuca_mode: str = "off"  # off / on / strict — drives pre-generation evidence-marker injection
    lang_cluster: str = "EN"
    raw_classifier_output: Optional[str] = None
    fallback_used: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ─── taxonomy loader (cached) ────────────────────────────────────────

_taxonomy_cache: Optional[dict] = None


def _load_taxonomy() -> dict:
    global _taxonomy_cache
    if _taxonomy_cache is None:
        _taxonomy_cache = json.loads(_TAXONOMY_PATH.read_text(encoding="utf-8"))
    return _taxonomy_cache


_VALID_TUYUCA_MODES = {"off", "on", "strict"}

# Per [[chomsky_2023_problem_clusters]] — methods that require explanatory mechanism
# chain (Chomsky C7: "scientific answers require mechanism")
_METHODS_REQUIRING_MECHANISM = {
    "empirical", "formal", "engineering_design", "clinical_diagnostic",
}

# Methods that require explicit normative-frame structure (Chomsky C8: dual-frame
# "Under rule-set R and evidence E, recommendation is X")
_METHODS_REQUIRING_NORMATIVE_FRAME = {"legal_normative"}


def _tuyuca_mode_for_method(method: str) -> str:
    """Return the tuyuca_mode declared in the taxonomy for this method.
    Falls back to 'off' if missing or invalid."""
    t = _load_taxonomy()
    raw = t.get("methods", {}).get(method, {}).get("tuyuca_mode", "off")
    return raw if raw in _VALID_TUYUCA_MODES else "off"


def _ford_for(faculty: str) -> Optional[str]:
    t = _load_taxonomy()
    for ford_key, faculty_list in t.get("ford_overlay", {}).items():
        if any(faculty.startswith(f) for f in faculty_list):
            return ford_key
    return None


# ─── ollama JSON-mode classifier call ────────────────────────────────

_CLASSIFIER_PROMPT_TEMPLATE = """Classify the following user-input for an AI-wrapper topic-router.

Return EXACT JSON with these keys:
{{
  "persona": [<one or two from: scientist, engineer, jurist, historian, physician, mathematician, journalist, storyteller, operator, auditor>],
  "faculty_isced": "<one of: F00_generic, F01_education, F02_arts_humanities, F03_social_sciences_journalism_information, F04_business_administration_law, F05_natural_sciences_math_statistics, F06_information_communication_technologies, F07_engineering_manufacturing_construction, F08_agriculture_forestry_fisheries_veterinary, F09_health_welfare, F10_services>",
  "method": "<one of: empirical, formal, interpretive, legal_normative, engineering_design, clinical_diagnostic, operational, creative>",
  "confidence": <float 0.0 to 1.0>,
  "rationale": "<one short sentence>"
}}

Hard rules:
- Factual / legal / scientific / medical / historical question → persona MUST include scientist or auditor; storyteller FORBIDDEN.
- Creative / story / poem / humor → storyteller allowed.
- When ambiguous → default to scientist+auditor (NEVER storyteller).
- Pick at most TWO personas; prefer one.

USER INPUT:
{text}

Respond with the JSON object only."""


def _classify_via_ollama(text: str) -> Optional[dict]:
    """Call the classifier model in JSON mode; return parsed dict or None on failure."""
    prompt = _CLASSIFIER_PROMPT_TEMPLATE.format(text=text[:2000])
    body_obj = {
        "model": CLASSIFIER_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
            "num_predict": 300,
            "num_gpu": 0,  # CPU-pin per [[classifier_warmth_doctrine]]
        },
    }
    body = json.dumps(body_obj).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=CLASSIFIER_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        raw = data.get("response", "").strip()
        if not raw:
            return None
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError) as e:
        sys.stderr.write(f"[topic_classifier] call failed: {e}\n")
    return None


# ─── validation + normalization ──────────────────────────────────────

def _validate_persona_list(raw) -> List[str]:
    if not isinstance(raw, list):
        return []
    out = []
    for p in raw[:2]:
        if isinstance(p, str) and p in _PERSONAS:
            out.append(p)
    return out


def _validate_faculty(raw) -> str:
    if isinstance(raw, str) and raw in _FACULTIES:
        return raw
    return "F00_generic"


def _validate_method(raw) -> str:
    if isinstance(raw, str) and raw in _METHODS:
        return raw
    return "interpretive"


def _validate_confidence(raw) -> float:
    try:
        c = float(raw)
        return max(0.0, min(1.0, c))
    except (TypeError, ValueError):
        return 0.0


def _apply_hard_default_rules(persona: List[str], method: str) -> List[str]:
    """Per topic_taxonomy.json defaults: factual tasks must NOT route to storyteller alone."""
    if not persona:
        persona = ["scientist", "auditor"]
    if method != "creative" and persona == ["storyteller"]:
        # Storyteller-only on a non-creative method = defaulted-violation; force factual
        persona = ["scientist", "auditor"]
    return persona


# ─── public API ──────────────────────────────────────────────────────

def classify_topic(text: str, lang_cluster: str = "EN") -> TopicRoute:
    """Classify user-input into the 3-layer router output.

    On classifier failure or parse error → safe defaults (scientist+auditor,
    F00_generic, interpretive, MODERATE). Never raises.
    """
    if not text or not text.strip():
        return TopicRoute(lang_cluster=lang_cluster, fallback_used=True)

    raw_dict = _classify_via_ollama(text)
    if raw_dict is None:
        # Classifier dead / unparseable → safe default
        return TopicRoute(lang_cluster=lang_cluster, fallback_used=True)

    persona = _validate_persona_list(raw_dict.get("persona"))
    faculty = _validate_faculty(raw_dict.get("faculty_isced"))
    method = _validate_method(raw_dict.get("method"))
    persona = _apply_hard_default_rules(persona, method)
    confidence = _validate_confidence(raw_dict.get("confidence"))

    depth = _METHOD_DEFAULT_DEPTH.get(method, "MODERATE")
    confab = method == "creative"
    invent = method == "creative" or "storyteller" in persona
    tuyuca = _tuyuca_mode_for_method(method)

    return TopicRoute(
        persona=persona,
        faculty_isced=faculty,
        ford_overlay=_ford_for(faculty),
        method=method,
        search_depth=depth,
        confidence=confidence,
        invention_allowed=invent,
        confab_channel_67_allowed=confab,
        tuyuca_mode=tuyuca,
        lang_cluster=lang_cluster,
        raw_classifier_output=json.dumps(raw_dict, ensure_ascii=False)[:500],
    )


def build_persona_system_message(route: TopicRoute) -> str:
    """Produce the persona+method system message to inject into the model call.
    Goes AFTER labrador-discipline + AKTUELLES DATUM, BEFORE the user turn.
    """
    t = _load_taxonomy()
    persona_labels = [
        t["personas"].get(p, {}).get("labels", {}).get(route.lang_cluster, p)
        for p in route.persona
    ]
    method_def = t["methods"].get(route.method, {})
    faculty_def = t["faculty"].get(route.faculty_isced, {})
    faculty_label = faculty_def.get("labels", {}).get(route.lang_cluster, route.faculty_isced)

    confab_block = (
        "Creative-channel (6/7) ALLOWED — invention permitted, BUT factual claims inside "
        "still gated, connotation-check non-optional, mark output as creative-mode."
    ) if route.confab_channel_67_allowed else (
        "Creative-channel (6/7) FORBIDDEN — scientist-mode only, no invention, "
        "every claim must trace to source."
    )

    router_block = (
        "=== TOPIC-ROUTER (wrapper-side) ===\n"
        f"Persona: {' + '.join(persona_labels)}\n"
        f"Faculty (ISCED-F): {faculty_label} [{route.faculty_isced}]\n"
        f"Method: {route.method} — goal: {method_def.get('goal', '?')}\n"
        f"Search depth: {route.search_depth}\n"
        f"Invention allowed: {route.invention_allowed}\n"
        f"{confab_block}\n"
        f"Tuyuca-Modus: {route.tuyuca_mode}\n"
        f"Classifier confidence: {route.confidence:.2f}"
        f"{' [FALLBACK USED — safe defaults applied]' if route.fallback_used else ''}\n"
        "=== END TOPIC-ROUTER ===\n"
    )

    if route.tuyuca_mode in ("on", "strict"):
        strict_clause = (
            "STRENG: jede sachliche Behauptung MUSS einen Marker tragen — "
            "fehlender Marker = Antwort wird zurueckgewiesen.\n"
        ) if route.tuyuca_mode == "strict" else (
            "Marker fuer alle sachlichen Behauptungen. Ohne Marker = keine Behauptung.\n"
        )
        tuyuca_block = (
            "\n=== EVIDENZ-MARKIERUNG (Tuyuca-Modus aktiv) ===\n"
            "Fuer jede sachliche Behauptung haenge inline einen Quellen-Marker an.\n"
            "Erlaubte Marker:\n"
            "  [verbatim:<source>]    — woertlich aus angefuehrter Quelle\n"
            "  [paraphrase:<source>]  — sinngemaess aus angefuehrter Quelle\n"
            "  [inferred:<premise>]   — aus Praemisse hergeleitet\n"
            "  [hearsay:<source>]     — gelesen, Primaerquelle nicht direkt geprueft\n"
            "  [training-knowledge]   — aus Training-Wissen, keine Quelle verifizierbar\n"
            "  [unsicher]             — gesagt-mit-Unsicherheit, nicht-committed\n\n"
            f"{strict_clause}"
            "Persoenliche-Meinung, kreative-Bilder, Stilfiguren in Erzaehlung brauchen KEINEN Marker.\n"
            "Bei Frage-Zurueckweisung (z.B. Vorwerk-fehlt): begruende ohne Marker.\n"
            "=== ENDE EVIDENZ-MARKIERUNG ===\n"
        )
        out = router_block + tuyuca_block

        # #203 Fix-2: C7/C8/C9b/C10 only fire for tuyuca=strict (legal_normative
        # + clinical_diagnostic). For tuyuca=on the model gets just the
        # EVIDENZ-MARKIERUNG block — keeps system-prompt under model attention
        # budget while still enforcing source-marker discipline.
        if route.tuyuca_mode == "strict":

            # C7 (Chomsky 2023): scientific answers require causal mechanism chain
            if route.method in _METHODS_REQUIRING_MECHANISM:
                mechanism_block = (
                    "\n=== KAUSALMECHANISMUS (Chomsky C7) ===\n"
                    "Beobachtung und Vorhersage allein reichen nicht — Erklaerung verlangt einen MECHANISMUS.\n"
                    "Zusaetzlicher Marker erlaubt:\n"
                    "  [mechanism:<kausale Kette>]  — das WARUM, nicht nur das WAS/WANN/WIE\n\n"
                    "Beispiel: '[mechanism:Newton-2.G F=ma + universelle Gravitation]'.\n"
                    "Wenn der Mechanismus nicht angebbar ist: explizit '[unsicher: Mechanismus nicht bekannt]'.\n"
                    "Popper-Kriterium: bevorzuge maechtige+unwahrscheinliche Erklaerungen ueber wahrscheinliche+triviale.\n"
                    "=== ENDE KAUSALMECHANISMUS ===\n"
                )
                out += mechanism_block

            # C8 (Chomsky 2023): normative answers require explicit frame/principle
            if route.method in _METHODS_REQUIRING_NORMATIVE_FRAME:
                frame_block = (
                    "\n=== NORMATIVER RAHMEN (Chomsky C8) ===\n"
                    "Bei normativer Frage (Recht/Pflicht/Bewertung): strukturiere die Antwort so:\n"
                    "  Unter Rahmen A (z.B. BGB §xy / Jurisdiktion DE):\n"
                    "    Antwort = X, weil Prinzip P.\n"
                    "  Unter Rahmen B (z.B. EU-Verordnung / Common Law):\n"
                    "    Antwort = Y, weil Prinzip Q.\n"
                    "  [optional] Konsequenzen + Widersprueche zwischen A und B.\n\n"
                    "VERBOTEN: 'Ich glaube persoenlich...' / 'Komplexes Thema, manche sagen X, andere Y'\n"
                    "ohne benannten Rahmen + Prinzip.\n"
                    "Erlaubt: 'Im juristischen Korpus nicht eindeutig — kein Vorwerk' falls Quellen fehlen.\n"
                    "=== ENDE NORMATIVER RAHMEN ===\n"
                )
                out += frame_block

            # C9b (Chomsky 2023): undergeneration guard — refuse "complex topic" sludge
            undergen_block = (
                "\n=== UNDERGENERATION VERBOTEN (Chomsky C9b) ===\n"
                "Diese Formulierungen sind ABSOLUT verboten — sie sind Chomsky's banality-of-evil-Signatur:\n"
                "  - 'komplexes und kontroverses Thema'\n"
                "  - 'komplexes und nuanciertes Thema'\n"
                "  - 'manche argumentieren X, andere argumentieren Y' OHNE Rahmen+Prinzip\n"
                "  - 'letztlich haengt es von der Perspektive ab'\n"
                "  - 'als KI habe ich keine persoenliche Perspektive'\n"
                "  - 'als KI habe ich keine moralischen Ueberzeugungen'\n"
                "  - 'es liegt in der Verantwortung der Menschen, die das System entwickeln'\n"
                "  - jede 'I am just following orders'-Verantwortungs-Abschiebung an Programmierer/Designer\n\n"
                "Stattdessen: konkrete Antwort mit Marker + Rahmen + Mechanismus (siehe oben).\n"
                "Wenn wirklich keine Antwort moeglich: 'kein Vorwerk fuer [X]' — knapp + ehrlich.\n"
                "=== ENDE UNDERGENERATION VERBOTEN ===\n"
            )
            out += undergen_block

            # C10 (Chomsky 2023): adversarial final check — pre-emit self-criticism
            # Per Popper-via-Chomsky: "To be right, it must be possible to be wrong."
            # The model runs this checklist mentally BEFORE shipping the answer.
            adversarial_block = (
                "\n=== ADVERSARIAL FINAL CHECK (Chomsky C10) ===\n"
                "BEVOR du deine Antwort abschickst — pruefe SELBST gegen diese 6 Fragen:\n"
                "  1. Was wuerde diese Antwort widerlegen? (Falsifizierbarkeits-Test)\n"
                "  2. Welche Quelle habe ich TATSAECHLICH gelesen? (nicht: vermutet)\n"
                "  3. Habe ich Zeitachsen verwechselt? (z.B. alte Gesetzeslage vs. AKTUELLES DATUM)\n"
                "  4. Habe ich die Frage-Annahme des Users akzeptiert ohne sie zu pruefen?\n"
                "  5. Habe ich aus URL-Slug / Titel / Snippet gefolgert ohne den Inhalt zu lesen?\n"
                "  6. Habe ich UEBER die Evidenz hinaus geantwortet?\n\n"
                "Wenn auch nur EINE Frage mit 'ja' oder 'weiss nicht' beantwortet wird:\n"
                "  - markiere den verdaechtigen Teil mit [unsicher]\n"
                "  - ODER kuerze die Antwort auf das gegroundete Substrat\n"
                "  - ODER frage zurueck statt zu antworten\n"
                "NIEMALS: faux-confidence trotz erkannter Schwaeche.\n"
                "Pop-Kriterium: 'To be right, it must be possible to be wrong.'\n"
                "=== ENDE ADVERSARIAL FINAL CHECK ===\n"
            )
            out += adversarial_block

        return out

    return router_block


# ─── CLI for smoke-test ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("text", help="user-input to classify")
    parser.add_argument("--lang", default="EN", help="language cluster")
    parser.add_argument("--json", action="store_true", help="output JSON only")
    args = parser.parse_args()

    route = classify_topic(args.text, args.lang)
    if args.json:
        print(json.dumps(route.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(route.to_dict(), ensure_ascii=False, indent=2))
        print()
        print(build_persona_system_message(route))
