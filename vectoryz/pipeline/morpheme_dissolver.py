"""Morpheme-Dissolution Pass — operator-doctrine 2026-05-20.

C64-Philosophy: with Qwen 7b + simple structured methods we can parse
compound named-entity morphemes from user queries. Don't ask Qwen for
facts (it lacks precision). Ask it for ENTITY-VALIDITY combinatorial
sanity (it can do that reliably).

Example operator-asked: 'Honda CBR1100XX und GSXR750'
- 'Honda CBR1100XX' → valid (Honda makes this)
- 'GSXR750' alone → valid (= Suzuki product)
- 'Honda GSXR750' → INVALID (Honda doesn't make GSXR750, Suzuki does)
- → user likely means Honda CBR1100XX + Suzuki GSXR750

Plus side-way homonym-check: is 'HondaCBR1100XX' famous in another
context (ferenghi stock-exchange?)?

Output flows into pre-search's wortwolke-fetch + LLM-prompt-grounding
so the LLM sees corrected entity-assignments before answering.

Per [[morpheme_disruption_doctrine]] — check morphemes FIRST, then
let the rest of the pipeline work clean.

Limitation-as-feature: a C64 could do this if you give it the right
pseudosearchcode. So can Qwen 7b. The trick is the structured prompt.
"""

from __future__ import annotations

from typing import Optional

from wrapper_v2.pipeline import three_witness


MORPHEME_DISSOLVE_PROMPT = """Aufgabe: Parse die User-Anfrage in Named-Entity-Morpheme und pruefe Combo-Validitaet.

USER:
{message}

Fuer jedes Morphem (Eigenname / Marke / Produkt / Werk / Person):
1. text: das Morphem wie's vorkommt
2. valid: true wenn die Kombination wirklich existiert (z.B. "Honda CBR1100XX" ja, "Honda GSXR750" nein weil GSXR ist Suzuki)
3. correction: falls invalid: die korrekte Form (z.B. "Honda GSXR750" → "Suzuki GSXR750")
4. note: kurzer Hinweis (z.B. "Suzuki-Produkt, nicht Honda")
5. homonyms: bekannte Alternativen in anderen Domaenen (Stadt vs Person, Band vs Auto, etc.)

Beispiel-Output fuer "Honda CBR1100XX und GSXR750":
{{"morphemes": [
  {{"text": "Honda CBR1100XX", "valid": true, "correction": null, "note": "Honda Motorrad-Modell", "homonyms": []}},
  {{"text": "GSXR750", "valid": true, "correction": null, "note": "Suzuki-Motorrad-Modell, der Tippgeber meinte vermutlich Suzuki", "homonyms": []}},
  {{"text": "Honda GSXR750", "valid": false, "correction": "Suzuki GSXR750", "note": "GSXR ist Suzuki, nicht Honda", "homonyms": []}}
]}}

WICHTIG:
- Pruefe NUR Combo-Validitaet (Marke + Modell, Person + Werk, Ort + Region). NICHT Fakten wie Jahre, Eigenschaften, etc.
- Wenn unsicher ob valid → setze valid=true (vorsicht in der ANDEREN richtung als bei Audit).
- Lass den Output kurz, max 5 morpheme.

Output AUSSCHLIESSLICH dieses JSON-Format:
{{"morphemes": [{{"text": "...", "valid": true|false, "correction": null|"...", "note": "...", "homonyms": []}}]}}
"""


def dissolve_morphemes(message: str, timeout_s: float = 10.0) -> dict:
    """Run morpheme-dissolution pass on user query.

    Returns:
        {
          "morphemes": [
            {"text", "valid", "correction", "note", "homonyms"},
            ...
          ],
          "fallback": bool,  # True if no llm_call adapter
          "error": str|None
        }
    """
    if not message or not message.strip():
        return {"morphemes": [], "fallback": False, "error": None}

    llm_call = three_witness._adapter("llm_call")
    if llm_call is None:
        return {"morphemes": [], "fallback": True, "error": "no llm_call adapter"}

    try:
        raw = llm_call(
            MORPHEME_DISSOLVE_PROMPT.format(message=message[:500]),
            temperature=0.1, timeout=int(timeout_s), json_mode=True,
        )
        parsed = three_witness._safe_json_parse(raw) or {}
        morphemes = parsed.get("morphemes", [])
        if not isinstance(morphemes, list):
            morphemes = []
        # Normalize structure
        normalized = []
        for m in morphemes[:5]:  # cap at 5
            if not isinstance(m, dict):
                continue
            normalized.append({
                "text": str(m.get("text", ""))[:120],
                "valid": bool(m.get("valid", True)),
                "correction": (str(m.get("correction") or "")[:120] or None),
                "note": str(m.get("note", ""))[:200],
                "homonyms": [str(h)[:80] for h in (m.get("homonyms") or [])][:3],
            })
        return {"morphemes": normalized, "fallback": False, "error": None}
    except Exception as e:
        return {"morphemes": [], "fallback": False, "error": str(e)[:200]}


def get_corrected_search_terms(dissolution_result: dict) -> list:
    """Extract clean search-terms from dissolution result.

    For invalid combos, use the correction. For valid, use the text.
    Used by pre_search to fetch wortwolken for the RIGHT entities.
    """
    terms = []
    seen = set()
    for m in dissolution_result.get("morphemes", []):
        if m.get("valid"):
            t = m["text"]
        elif m.get("correction"):
            t = m["correction"]
        else:
            continue
        key = t.lower().strip()
        if key and key not in seen:
            seen.add(key)
            terms.append(t)
    return terms


DIALOG_UNWRAP_PROMPT = """Aufgabe: Parse die User-Anfrage in ihre Dialog-Struktur-Komponenten.

USER:
{message}

Typische Komponenten:
- GREETING: "ahoi", "hi", "hallo", "servus", "moin", "(:" emoticon, etc.
- INTRO/OPENER: "dieses Muster:", "schau mal:", "kennst du das:", "ich habe gehört:", etc.
- CONTENT: das eigentliche Subject das diskutiert/analysiert/beantwortet werden soll
- QUESTION: die explizite Frage ("wo kommt es vor?", "was bedeutet?", "woher stammt?", "wer hat?")
- FILLER: semantisch leere Tokens ("blablabla", "äh", "etc.", "...", platzhalter)

WICHTIG:
- CONTENT extrahieren OHNE die Wrapper-Tokens (kein "dieses Muster:", kein "ahoi", kein "blablabla")
- QUESTION als klare Intent-Frage isolieren
- Wenn keine explizite Frage da ist → question:"" lassen
- Wenn die Anfrage NUR Greeting ist (z.B. "hallo!") → content:"" + question:""

Beispiel-Input: "ahoi (: dieses Muster: blablabla am schluss lachen vieleschnitzlamohr, gell spatzl? wo kommt es vor?"
Beispiel-Output:
{{"greeting": "ahoi (:", "intro_phrase": "dieses Muster", "content": "am schluss lachen vieleschnitzlamohr, gell spatzl?", "question": "wo kommt es vor?", "fillers": ["blablabla"], "has_wrapper": true}}

Beispiel-Input: "wann wurde Albert Einstein geboren?"
Beispiel-Output:
{{"greeting": "", "intro_phrase": "", "content": "Albert Einstein", "question": "wann wurde Albert Einstein geboren?", "fillers": [], "has_wrapper": false}}

Output AUSSCHLIESSLICH dieses JSON-Format:
{{"greeting": "...", "intro_phrase": "...", "content": "...", "question": "...", "fillers": [], "has_wrapper": true|false}}
"""


def unwrap_dialog_structure(message: str, timeout_s: float = 8.0) -> dict:
    """Parse user-message into dialog-structure components.

    Per [[unwrap_before_process_doctrine]] — substantive engagement requires
    recognizing wrapper-vs-content. Returns structured breakdown:
      - greeting: social-opener, acknowledge silently
      - intro_phrase: content-introducer, mark but don't analyze
      - content: actual subject the user wants engaged with
      - question: explicit intent
      - fillers: semantic noise to ignore
      - has_wrapper: True if message has wrapper-structure
    """
    if not message or not message.strip():
        return {"greeting": "", "intro_phrase": "", "content": "",
                "question": "", "fillers": [], "has_wrapper": False,
                "fallback": False}

    llm_call = three_witness._adapter("llm_call")
    if llm_call is None:
        # Fallback: simple regex detection
        import re as _re
        msg = message.strip()
        greeting_rx = _re.compile(
            r"^\s*((?:ahoi|hi|hallo|hey|servus|moin|grüß\s*gott|grüezi|tag|guten\s*tag|"
            r"hello|good\s*morning|good\s*evening|guten\s*morgen|guten\s*abend)"
            r"[\s\.,!?(:;)\-]*)\s*",
            _re.IGNORECASE,
        )
        m = greeting_rx.match(msg)
        greeting = m.group(1).strip() if m else ""
        rest = msg[m.end():] if m else msg
        return {
            "greeting": greeting,
            "intro_phrase": "",
            "content": rest,
            "question": rest,  # naive: rest IS the question
            "fillers": [],
            "has_wrapper": bool(greeting),
            "fallback": True,
        }

    try:
        raw = llm_call(
            DIALOG_UNWRAP_PROMPT.format(message=message[:800]),
            temperature=0.0, timeout=int(timeout_s), json_mode=True,
        )
        parsed = three_witness._safe_json_parse(raw) or {}
        return {
            "greeting": str(parsed.get("greeting", ""))[:120],
            "intro_phrase": str(parsed.get("intro_phrase", ""))[:120],
            "content": str(parsed.get("content", ""))[:600],
            "question": str(parsed.get("question", ""))[:300],
            "fillers": [str(f)[:60] for f in (parsed.get("fillers") or [])][:5],
            "has_wrapper": bool(parsed.get("has_wrapper", False)),
            "fallback": False,
        }
    except Exception as e:
        return {"greeting": "", "intro_phrase": "", "content": message,
                "question": message, "fillers": [], "has_wrapper": False,
                "fallback": False, "error": str(e)[:200]}


def format_dialog_unwrap_for_prompt(unwrap_result: dict) -> str:
    """Format dialog-unwrap as prompt-injection block.

    Used to tell the LLM what is wrapper vs content. Prevents Knecht-mode
    (analyzing the wrapper instead of engaging the content).
    """
    if not unwrap_result or not unwrap_result.get("has_wrapper"):
        return ""

    greeting = unwrap_result.get("greeting", "")
    intro = unwrap_result.get("intro_phrase", "")
    content = unwrap_result.get("content", "")
    question = unwrap_result.get("question", "")
    fillers = unwrap_result.get("fillers", [])

    if not (greeting or intro or fillers):
        return ""

    lines = [
        "[Dialog-Struktur-Erkennung]",
        "ANWEISUNG: die User-Anfrage hat eine Wrapper-Struktur. Behandle die "
        "Komponenten unterschiedlich:",
        "",
    ]
    if greeting:
        lines.append(f"  GREETING: '{greeting}' — kurz erwidern (ein Wort reicht), NICHT analysieren oder definieren.")
    if intro:
        lines.append(f"  INTRO-PHRASE: '{intro}' — dient nur als Einleitung zum Content, NICHT diskutieren.")
    if fillers:
        lines.append(f"  FILLER (ignorieren): {', '.join(repr(f) for f in fillers)} — semantisch leer.")
    if content:
        lines.append(f"  CONTENT (das eigentliche Subject): '{content}'")
    if question:
        lines.append(f"  INTENT-Frage: '{question}'")
    lines.extend([
        "",
        "Antwort-Disziplin: erwidere kurz das Greeting (falls present), dann "
        "antworte AUF DIE INTENT-Frage MIT BEZUG AUF DEN CONTENT. NICHT die "
        "Wrapper-Tokens definieren. Nicht 'ahoi bedeutet hallo' wenn der User "
        "geahoit hat — der will nicht das Wort 'ahoi' erklärt bekommen, er "
        "begrüsst dich.",
        "[/Dialog-Struktur-Erkennung]",
    ])
    return "\n".join(lines)


def format_morpheme_dissolution_for_prompt(dissolution_result: dict) -> str:
    """Format dissolution result as prompt-injection block.

    Used to inject into LLM-prompt so it sees the corrected entity-mappings
    before answering. Prevents Honda-GSXR750-confusion-class errors.
    """
    morphemes = dissolution_result.get("morphemes", [])
    if not morphemes:
        return ""
    # Only inject if there ARE corrections or notes worth showing
    has_correction = any(not m.get("valid") or m.get("correction") for m in morphemes)
    has_homonyms = any(m.get("homonyms") for m in morphemes)
    has_notes = any(m.get("note") for m in morphemes)
    if not (has_correction or has_homonyms or has_notes):
        return ""
    lines = [
        "[Morpheme-Check fuer die Anfrage — combo-validitaet bevor LLM antwortet]",
        "ANWEISUNG: Diese Pruefung wurde gemacht. Wenn correction angegeben, "
        "behandle den User-Term als wahrscheinliches Versehen + nutze die "
        "korrekte Form in deiner Antwort. Wenn homonyms gelistet, sei dir "
        "der Mehrdeutigkeit bewusst.",
        "",
    ]
    for m in morphemes:
        line = f"- '{m['text']}'"
        if not m["valid"] and m["correction"]:
            line += f" → INVALID, korrekt: '{m['correction']}'"
        elif m["correction"]:
            line += f" → siehe auch: '{m['correction']}'"
        if m["note"]:
            line += f" ({m['note']})"
        if m["homonyms"]:
            line += f" [homonyms: {', '.join(m['homonyms'])}]"
        lines.append(line)
    lines.append("[/Morpheme-Check]")
    return "\n".join(lines)
