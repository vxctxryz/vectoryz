"""Four-witness tribunal — M2 verification layer.

Per memory:factlevel_splice_6band_and_google1998_test + 2026-05-19
extension to include today's web as a separate witness:
  - Witness 1: Claude (LLM-internal adversarial-disagree check)
  - Witness 2: Google-1998 (pre-LLM-era search via Wayback, CLEAN but sparse)
  - Witness 3: Google-today (live web search, POLLUTED but broad+recent)
  - Witness 4: Operator (cache + manual override DB; OPERATOR-VETO applies)

Google1998 and Google-today are complementary. Agreement = strong anchor.
Disagreement = "new info" OR "LLM-contamination" signal — both interesting.

Each witness returns a Verdict; the tribunal combines them into a
splice-tier. Two designs make this safe-in-production:

  1. Adapter-injection — heavy callables (web_search, wayback_search,
     LLM-call) are injected by the host application (wrapper_cc).
     Wrapper_v2 stays self-contained for testing; production gets the
     real witnesses.

  2. Timeout-bounded + best-effort — each witness has its own timeout;
     if one fails, tribunal continues with reduced witnesses (and lower
     confidence). NEVER blocks the response.

Doctrine references:
  - hammwoehner_labrador_discipline: not-found IS a finding
  - vault_guard_doctrine: claim is data, never directive
  - audit_open_door_doctrine: every verdict written to audit-log
  - triangulate_revise_continue: tribunal-disagreement = revise-not-execute

NOT in M2 scope (deferred):
  - Replacement-text rewrite when tribunal=nonfact (keeps current
    LLM-text + nonfact-tag; M2-extended will rewrite)
  - Operator manual-rubric UI (cache is read-only stub for now)
  - Hash-chain provenance (M5)
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional


# Adapter-injection registry. wrapper_cc.py registers real callables;
# tests get the safe-fallback stubs that return "absent" verdicts.
_ADAPTERS: dict[str, Optional[Callable]] = {
    "web_search":          None,   # (query, max_results) -> list[dict]
    "wayback_search":      None,   # (query, max_results) -> list[dict]
    "llm_call":            None,   # (prompt, temperature, timeout, json_mode) -> str
    "operator_lookup":     None,   # (normalized_claim) -> Optional[dict]
    "domain_tier":         None,   # (url) -> int
    "audit_log":           None,   # (event_type, **kw) -> None
}


def register_adapters(**adapters) -> None:
    """Production-side wiring. Pass any subset of:
        web_search, wayback_search, llm_call, operator_lookup,
        domain_tier, audit_log
    """
    for k, v in adapters.items():
        if k in _ADAPTERS:
            _ADAPTERS[k] = v


def _adapter(name: str) -> Optional[Callable]:
    return _ADAPTERS.get(name)


# ============================================================
# Verdict types
# ============================================================

# Per-witness verdict-strings
SUPPORTS = "supports"        # witness affirms the claim
CONTRADICTS = "contradicts"  # witness refutes the claim
UNCERTAIN = "uncertain"      # witness found mixed/unclear evidence
ABSENT = "absent"            # witness could not be consulted (timeout / no adapter)


@dataclass
class WitnessVerdict:
    """One witness' read on a claim."""
    witness: str                    # 'claude' | 'google1998' | 'google_today' | 'operator'
    verdict: str                    # SUPPORTS / CONTRADICTS / UNCERTAIN / ABSENT
    confidence: float = 0.0         # 0.0-1.0
    evidence: str = ""              # snippet / reasoning
    sources: list = field(default_factory=list)
    correction: str = ""            # if CONTRADICTS — what witness says instead
    audit_comment: str = ""         # if CONTRADICTS — where the LLM reasoning went wrong
    recommended_source: str = ""    # if CONTRADICTS — URL/domain to consult instead
    latency_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class TribunalResult:
    """Combined verdict across all consulted witnesses."""
    claim_text: str
    verdicts: list = field(default_factory=list)            # list[WitnessVerdict]
    final_tier: str = "nullfact"                            # splice-tier
    off_axis_tag: Optional[str] = None
    tribunal_confidence: str = "low"                        # low/medium/high
    correction_text: Optional[str] = None                   # filled if final=nonfact
    audit_comments: list = field(default_factory=list)      # plain-language reasoning critiques from CONTRADICTS witnesses
    recommended_sources: list = field(default_factory=list) # URL/domain recommendations from CONTRADICTS witnesses
    witnesses_consulted: list = field(default_factory=list)
    total_latency_ms: float = 0.0
    from_cache: bool = False


# ============================================================
# Topic extraction (2026-05-19, operator-spec)
# ============================================================

TOPIC_EXTRACTION_PROMPT = """Extrahiere aus folgender Behauptung die SUCH-SCHLUESSELWORTE fuer eine Web-Suche zum Original-Thema.

WICHTIG: Wenn die Behauptung halluzinierten Text enthaelt (z.B. erfundene Lyrics, fabrizierte Zitate), gib das THEMA wieder, NICHT den halluzinierten Text. Beispiel: Wenn die Behauptung "Nessun Dorma lautet 'Tu che l'angelo vegli'" sagt, ist das Such-Thema "Nessun Dorma lyrics original" — NICHT "Tu che l'angelo vegli".

BEHAUPTUNG:
{claim}

Output AUSSCHLIESSLICH dieses JSON-Format:
{{"topic": "kurze Such-Phrase 3-8 Worte, plain text, nur die Schluesselworte", "is_hallucination_suspected": true|false}}
"""


def extract_search_topic(claim: str, max_topic_len: int = 200) -> str:
    """Use LLM to extract a search-friendly topic from a possibly-hallucinated claim.

    Returns a short query-string for web/wayback search. Falls back to the
    raw claim if the topic-extraction fails (no llm_call adapter, or parse error).
    """
    if not claim or not claim.strip():
        return claim
    llm_call = _adapter("llm_call")
    if llm_call is None:
        return claim[:max_topic_len]
    try:
        raw = llm_call(
            TOPIC_EXTRACTION_PROMPT.format(claim=claim[:500]),
            temperature=0.0, timeout=8, json_mode=True,
        )
        parsed = _safe_json_parse(raw) or {}
        topic = str(parsed.get("topic", "")).strip()
        if topic and len(topic) >= 3:
            return topic[:max_topic_len]
    except Exception:
        pass
    return claim[:max_topic_len]


# ============================================================
# Prompts (used by adapter-injected LLM)
# ============================================================

CLAUDE_WITNESS_PROMPT = """Du bist ein adversarialer Faktenpruefer. Pruefe folgende Behauptung skeptisch.

BEHAUPTUNG:
{claim}

Aufgabe: Bewerte die Behauptung basierend auf deinem internen Wissen. Sei adversarial — suche nach Gruenden, warum die Behauptung falsch oder ungenau sein koennte.

HARDENING-RULES (HAMMERANTWORT-Pfad):
- Wenn die Behauptung SPEZIFISCHE benannte Entitaeten enthaelt (Person, Werk, Ort, Jahr, Zitat) UND eine dieser Entitaeten nicht zum Kontext passt (z.B. "X sang Aria Y" wenn X ein Charakter ist statt der Saenger; "Werk Z hat keine Uebersetzung" wenn nachweisbar viele existieren) → vote CONTRADICTS mit Korrektur, NICHT UNCERTAIN
- Wenn die Behauptung ein woertliches ZITAT enthaelt (in Anfuehrungszeichen oder als Liedtext-fragment) und du das exakte Zitat in dem Kontext nicht aus deinem Wissen verifizieren kannst → vote CONTRADICTS (Zitate sind nicht obskur — wenn unauffindbar, halluziniert)
- Wenn die Behauptung eine artifizielle Authority-Constraint aufstellt ("nur X darf Y", "Z existiert nicht") und Gegenbeispiele aus deinem Wissen verfuegbar sind → vote CONTRADICTS
- Wenn du dir GENUIN nicht sicher bist (keine starke Position pro oder contra) → vote UNCERTAIN
- DEFAULT bei spezifischer Entity-Behauptung mit klarer Falsch-Signatur ist CONTRADICTS, nicht hoeflich-UNCERTAIN.

VERBATIM-QUOTE-DISZIPLIN (kritisch):
- Du als claude-witness hast KEINE search-results und KEIN externes Wissen ueber das Klar-aktuelle. Wenn du contradicts sagst, gib im correction-Feld NUR was du sicher aus deinem Trainings-Wissen weisst, MIT Vorsicht.
- Wenn du dir nicht sicher bist welche genau "die richtige" Fassung waere → lass correction LEER ("") und gib NUR audit_comment + recommended_source. Andere Witnesses (mit Such-Ergebnissen) liefern dann die verbatim-Korrektur.

CONTRADICTS-DISZIPLIN (kritisch, anti-halluzination):
- CONTRADICTS NUR wenn du STARKE GEGEN-EVIDENZ hast (eine konkrete reputable Quelle die explizit das Gegenteil belegt, ein bekannter Fakt im Trainings-Wissen der direkt widerspricht).
- "Klingt unplausibel" / "kommt mir komisch vor" / "wirkt zu spezifisch" sind NICHT genug fuer CONTRADICTS — das waere Halluzination einer Korrektur.
- Falsche Korrekturen sind harm (Doctrine: death_penalty_void) — lieber ABSENT/UNCERTAIN als ein erfundenes "Tribunal sagt X" das selbst falsch ist.

GENRE-AWARENESS (kritisch):
- Wenn der Claim aus LYRIK, POESIE, DRAMA-ZITAT, LIEDTEXT, ROMAN-PASSAGE oder einem aehnlichen kunstlerischen Kontext kommt → vote ABSENT mit audit_comment "Genre: Lyrik/Poesie, keine empirisch testbare Behauptung".
- Beispiel: "Keiner schlafe!" ist eine Opernarienzeile, KEIN universelles empirisches Statement. NICHT als fallacy-of-composition bewerten.
- Erkennbar an: Imperativ ohne Subjekt, Reim, ungewoehnliche Wortstellung, Anfuehrungszeichen mit Vers-Layout, expliziter Werks-Kontext ("aus der Oper X", "in Liedform").

Output AUSSCHLIESSLICH dieses JSON-Format:
{{"verdict": "supports|contradicts|uncertain", "confidence": 0.0-1.0, "reasoning": "kurze Begruendung", "correction": "falls contradicts UND sicher: konkrete Fassung; sonst leer", "audit_comment": "falls contradicts: ein-Satz-Kommentar wo der Reasoning-Fehler liegt (z.B. 'Charakter mit Saenger verwechselt')", "recommended_source": "falls contradicts: eine reputable Quelle (Wikipedia-Slug, Domain, oder URL) die die korrekte Information traegt"}}
"""


GOOGLE_TODAY_JUDGE_PROMPT = """Du bewertest, ob eine Behauptung durch HEUTIGE Web-Suchergebnisse GESTUETZT, WIDERLEGT oder OFFEN ist.

BEHAUPTUNG:
{claim}

SUCH-ERGEBNISSE (live, heute):
{results_text}

WICHTIG: Heutige Web-Suche ist KONTAMINIERT durch LLM-generierten Content (KI-Blogs, generische Zusammenfassungen, "as an AI"-Sprache). Gewichte:
- Reputable + alte Quellen (vor 2020, Government/Edu/Standards-Body, T0-T2) zaehlen MEHR
- LLM-stil-Texte (generische Listen, KI-Blog-Pattern) zaehlen WENIGER
- Original-Quellen (paywall, private DBs, akademische Repos) zaehlen MEHR
- Wenn Ergebnisse nur LLM-Pollution sind ohne Original-Substanz → vote ABSENT (nicht UNCERTAIN, nicht raten)
- Wenn Behauptung eine Meta-Aussage ist (kein empirisch pruefbarer Fakt) → vote ABSENT

HARDENING-RULES (HAMMERANTWORT-Pfad):
- Wenn die Behauptung SPEZIFISCHE Entitaeten nennt und die Top-Resultate eine ANDERE Person/Werk/Jahr fuer den gleichen Kontext zeigen → vote CONTRADICTS mit der korrekten Version
- Wenn die Behauptung ein woertliches Zitat enthaelt und keine Quelle das exakte Zitat fuehrt (egal in welcher Sprache) → vote CONTRADICTS — beruehmte Operncitate, Liedtexte, Buchzitate sind nicht obskur, Nichtauffindbarkeit IST Widerlegung
- Wenn die Behauptung negiert ("X existiert nicht", "es gibt keine Y") und eine reputable Quelle X oder Y erwaehnt → vote CONTRADICTS
- Wenn die Behauptung deutsche Grammatik-Fragmente enthaelt ("Librett" statt "Librettist", "verfasst werden vom X" wo X ein Wort, kein Akteur ist) → es ist LLM-output, kein menschlicher Text — bewertet aber wie ueblich; wenn der Inhalt zusaetzlich falsch ist → CONTRADICTS
- DEFAULT bei klarer Entity-Kollision oder Zitat-Nichtauffindbarkeit ist CONTRADICTS.

Sonst:
- Mehrere unabhaengige Original-Quellen erwaehnen + bestaetigen → SUPPORTS
- Klare Widerlegung in mindestens einer reputablen Quelle → CONTRADICTS
- Quellen reichen nicht fuer ein klares Urteil → UNCERTAIN

VERBATIM-QUOTE-DISZIPLIN (kritisch):
- Wenn du contradicts sagst, MUSS das correction-Feld ein WORTWOERTLICHES Zitat aus EINEM der oben gelisteten Such-Ergebnis-Snippets sein
- ERZEUGE KEINEN neuen Text aus deinem eigenen Wissen — die heutige Web-Suche ist KONTAMINIERT, dein Wissen ist es vermutlich auch
- Wenn KEIN snippet das korrekte Zitat traegt → correction-Feld LEER lassen ("")
- audit_comment + recommended_source duerfen weiterhin gefuellt sein, auch wenn correction leer ist

CONTRADICTS-DISZIPLIN (kritisch, anti-halluzination):
- CONTRADICTS NUR wenn ein Such-Ergebnis-Snippet EXPLIZIT das Gegenteil belegt
- "Sehr spezifisch" / "klingt unplausibel" / "nicht in meinen Treffern" sind NICHT genug fuer CONTRADICTS
- "Nicht in den Suchergebnissen" = ABSENT oder UNCERTAIN, NIE CONTRADICTS
- Falsche Korrekturen sind harm (Doctrine: death_penalty_void) — Witness halluziniert NIE "das ist falsch" ohne Gegen-Snippet

GENRE-AWARENESS (kritisch):
- Wenn der Claim aus LYRIK, POESIE, DRAMA-ZITAT, LIEDTEXT, ROMAN-PASSAGE kommt → vote ABSENT
- audit_comment: "Genre: Lyrik/Poesie, keine empirisch testbare Behauptung"
- Beispiel: Opernarienzeilen wie "Keiner schlafe!" sind kein universelles empirisches Statement.

Sonst:
- Mehrere unabhaengige Original-Quellen erwaehnen + bestaetigen → SUPPORTS
- Klare Widerlegung in mindestens einer reputablen Quelle → CONTRADICTS
- Quellen reichen nicht fuer ein klares Urteil → UNCERTAIN

Output AUSSCHLIESSLICH dieses JSON-Format:
{{"verdict": "supports|contradicts|uncertain|absent", "confidence": 0.0-1.0, "evidence": "kurzes Zitat oder Zusammenfassung der staerksten Quelle, oder Grund fuer ABSENT (z.B. 'nur LLM-Pollution gefunden' oder 'Genre: Lyrik')", "correction": "WORTWOERTLICHES Zitat aus einem Snippet ODER leer", "audit_comment": "falls contradicts: ein-Satz-Kommentar wo der LLM-Reasoning-Fehler liegt", "recommended_source": "falls contradicts: die staerkste URL aus den Search-Results die die korrekte Information traegt"}}
"""


GOOGLE1998_JUDGE_PROMPT = """Du bewertest, ob eine Behauptung durch Such-Ergebnisse aus alter (vor-LLM) Web-Archiv-Quellen GESTUETZT, WIDERLEGT oder OFFEN ist.

BEHAUPTUNG:
{claim}

SUCH-ERGEBNISSE (Wayback / pre-2020 sources):
{results_text}

WICHTIG: Pre-LLM-Quellen sind wertvoll, weil sie nicht durch LLM-generierten Content kontaminiert sind. Aber Coverage hat Grenzen:
- Wayback indexiert deutsche Uni-Seiten erst ab ca. 2005 zuverlaessig; akademische Publikationen vor 2000 sind selten erfasst.
- Wenn die Behauptung eine Zeit-Angabe vor 2005 enthaelt UND die Suchergebnisse die Zeit-Periode nicht abdecken → vote ABSENT (nicht UNCERTAIN, nicht raten).
- Wenn die Behauptung eine Meta-Aussage ist ("ich weiss nicht", "ich kann nicht bestaetigen") und keine empirisch pruefbare Tatsachen-Behauptung → vote ABSENT.

HARDENING-RULES (HAMMERANTWORT-Pfad):
- Wenn die Behauptung SPEZIFISCHE Entitaeten nennt (Person, Werk, Jahr, Zitat) und KEINE der Wayback-Quellen diese Kombination bestaetigt — aber Wayback hat Quellen zum Thema die eine ANDERE Person/Werk/Jahr nennen — vote CONTRADICTS mit der korrekten Version, NICHT UNCERTAIN
- Wenn die Behauptung ein woertliches Italienisch/Latein/Englisch-Zitat enthaelt und Wayback findet das Werk aber NICHT das Zitat → vote CONTRADICTS (klassische Operncitate sind in pre-LLM-Quellen massiv dokumentiert)
- Wenn die Behauptung negiert ("X existiert nicht", "Y wurde nie gemacht") und Wayback eine Erwaehnung von X oder Y enthaelt → vote CONTRADICTS
- DEFAULT bei klarer Entity-Kollision oder Zitat-Nichtauffindbarkeit ist CONTRADICTS.

Sonst:
- Mehrere unabhaengige pre-LLM-Quellen erwaehnen + bestaetigen → SUPPORTS
- Klare Widerlegung in mindestens einer reputablen Quelle → CONTRADICTS
- Quellen reichen nicht fuer ein klares Urteil → UNCERTAIN

VERBATIM-QUOTE-DISZIPLIN (kritisch):
- Wenn du contradicts sagst, MUSS das correction-Feld ein WORTWOERTLICHES Zitat aus EINEM der oben gelisteten Such-Ergebnis-Snippets sein
- ERZEUGE KEINEN neuen Text aus deinem eigenen Wissen — nutze NUR was im snippet steht
- Wenn KEIN snippet das korrekte Zitat traegt → correction-Feld LEER lassen ("")
- audit_comment + recommended_source duerfen weiterhin gefuellt sein, auch wenn correction leer ist

CONTRADICTS-DISZIPLIN (kritisch, anti-halluzination):
- CONTRADICTS NUR wenn ein Such-Ergebnis-Snippet EXPLIZIT das Gegenteil belegt
- "Sehr spezifisch" / "klingt unplausibel" / "nicht in meinen Treffern" sind NICHT genug fuer CONTRADICTS
- "Nicht in den Suchergebnissen" = ABSENT oder UNCERTAIN, NIE CONTRADICTS
- Falsche Korrekturen sind harm (Doctrine: death_penalty_void) — Witness halluziniert NIE "das ist falsch" ohne Gegen-Snippet

GENRE-AWARENESS (kritisch):
- Wenn der Claim aus LYRIK, POESIE, DRAMA-ZITAT, LIEDTEXT, ROMAN-PASSAGE kommt → vote ABSENT
- audit_comment: "Genre: Lyrik/Poesie, keine empirisch testbare Behauptung"
- Beispiel: Opernarienzeilen wie "Keiner schlafe!" sind kein universelles empirisches Statement.

Sonst:
- Mehrere unabhaengige pre-LLM-Quellen erwaehnen + bestaetigen → SUPPORTS
- Klare Widerlegung in mindestens einer reputablen Quelle → CONTRADICTS
- Quellen reichen nicht fuer ein klares Urteil → UNCERTAIN

Output AUSSCHLIESSLICH dieses JSON-Format:
{{"verdict": "supports|contradicts|uncertain|absent", "confidence": 0.0-1.0, "evidence": "kurzes Zitat oder Zusammenfassung der staerksten Quelle, oder Grund fuer ABSENT (z.B. 'Era vor Wayback-Coverage' oder 'Genre: Lyrik')", "correction": "WORTWOERTLICHES Zitat aus einem Snippet ODER leer", "audit_comment": "falls contradicts: ein-Satz-Kommentar wo der LLM-Reasoning-Fehler liegt", "recommended_source": "falls contradicts: die staerkste Wayback-URL aus den Search-Results"}}
"""


# ============================================================
# Witness 1: Claude (LLM-internal adversarial check)
# ============================================================

def witness_claude(claim: str, timeout_s: float = 8.0) -> WitnessVerdict:
    """Internal-knowledge witness via LLM adversarial-prompt.

    Per doctrine: LLM-internal is suspect (training-cutoff + hallucination),
    so this witness is LOWEST-WEIGHT in tribunal. Adversarial-prompt forces
    the LLM to look for reasons-to-doubt, not just confirm.
    """
    t0 = time.time()
    llm_call = _adapter("llm_call")
    if llm_call is None:
        return WitnessVerdict(
            witness="claude", verdict=ABSENT,
            error="no llm_call adapter registered",
            latency_ms=(time.time() - t0) * 1000,
        )

    prompt = CLAUDE_WITNESS_PROMPT.format(claim=claim[:600])
    try:
        raw = llm_call(prompt, temperature=0.2, timeout=int(timeout_s), json_mode=True)
        parsed = _safe_json_parse(raw) or {}
        verdict_raw = str(parsed.get("verdict", "uncertain")).lower()
        if verdict_raw not in (SUPPORTS, CONTRADICTS, UNCERTAIN):
            verdict_raw = UNCERTAIN
        confidence = float(parsed.get("confidence", 0.3))
        confidence = max(0.0, min(1.0, confidence))
        correction = str(parsed.get("correction", ""))[:400]
        # 2026-05-20: detect non-correction (witness-confusion smoking-gun)
        # — if correction == claim modulo whitespace, witness halluzinierte
        # contradicts on a true claim. Downgrade CONTRADICTS → UNCERTAIN.
        if _is_non_correction(correction, claim):
            correction = ""
            if verdict_raw == CONTRADICTS:
                verdict_raw = UNCERTAIN
        return WitnessVerdict(
            witness="claude",
            verdict=verdict_raw,
            confidence=confidence,
            evidence=str(parsed.get("reasoning", ""))[:400],
            correction=correction,
            audit_comment=str(parsed.get("audit_comment", ""))[:300],
            recommended_source=str(parsed.get("recommended_source", ""))[:300],
            latency_ms=(time.time() - t0) * 1000,
        )
    except Exception as e:
        return WitnessVerdict(
            witness="claude", verdict=ABSENT, error=str(e)[:200],
            latency_ms=(time.time() - t0) * 1000,
        )


# ============================================================
# Witness 2: Google-1998 (Wayback-machine pre-LLM-era search)
# ============================================================

def witness_google1998(claim: str, timeout_s: float = 10.0,
                        search_topic: Optional[str] = None) -> WitnessVerdict:
    """Pre-LLM-era web-archive witness — Wayback ONLY.

    Per doctrine factlevel_splice_6band_and_google1998_test:
    LLM-knowledge is contaminated post-2020 by LLM-generated content.
    Wayback / archive.org snapshots from pre-LLM-era are the cleanest
    truth-anchor available for casual facts.

    NO fallback to live web — that's witness_google_today's job and
    keeping the two witnesses pure-signal lets the tribunal SEE
    pollution-vs-clean disagreement.

    Args:
        claim: the claim text (used for LLM-judge)
        search_topic: optional extracted-topic for the wayback-search query
                      (avoids searching for hallucinated text inside the claim).
                      Falls back to claim if None.
    """
    t0 = time.time()
    wayback_search = _adapter("wayback_search")
    llm_call = _adapter("llm_call")
    domain_tier = _adapter("domain_tier")

    if llm_call is None:
        return WitnessVerdict(
            witness="google1998", verdict=ABSENT,
            error="no llm_call adapter for judge-pass",
            latency_ms=(time.time() - t0) * 1000,
        )

    # Wayback only — no fallback. Empty results → ABSENT honest-not-found.
    # Use search_topic for the query if provided (avoid searching for
    # hallucinated text verbatim).
    query = (search_topic or claim)[:200]
    results = []
    try:
        if wayback_search:
            results = wayback_search(query, 3) or []
    except Exception:
        results = []

    if not results:
        return WitnessVerdict(
            witness="google1998", verdict=ABSENT,
            evidence="no wayback results (era may pre-date coverage)",
            latency_ms=(time.time() - t0) * 1000,
        )

    # Format results for LLM-judge
    lines = []
    sources = []
    best_tier = 9
    for i, r in enumerate(results[:3]):
        title = (r.get("title") or "")[:120]
        url = (r.get("url") or r.get("href") or "")[:200]
        snippet = (r.get("snippet") or r.get("body") or "")[:400]
        tier = 9
        if domain_tier and url:
            try:
                tier = int(domain_tier(url))
            except Exception:
                tier = 9
        best_tier = min(best_tier, tier)
        tier_label = f"T{tier}" if tier < 9 else "T9·unbekannt"
        lines.append(f"[{i+1}] ({tier_label}) {title}\n     URL: {url}\n     Snippet: {snippet}")
        sources.append(url)

    results_text = "\n\n".join(lines)
    prompt = GOOGLE1998_JUDGE_PROMPT.format(claim=claim[:600], results_text=results_text)

    try:
        raw = llm_call(prompt, temperature=0.1, timeout=int(timeout_s), json_mode=True)
        parsed = _safe_json_parse(raw) or {}
        verdict_raw = str(parsed.get("verdict", "uncertain")).lower()
        # Honest-coverage doctrine: judge may emit ABSENT when era is pre-Wayback-coverage
        # or claim is meta-statement (not empirically testable)
        if verdict_raw not in (SUPPORTS, CONTRADICTS, UNCERTAIN, ABSENT):
            verdict_raw = UNCERTAIN
        confidence = float(parsed.get("confidence", 0.3))
        confidence = max(0.0, min(1.0, confidence))
        # T0/T1 sources boost confidence; T9 dampens
        tier_boost = 1.0 if best_tier <= 1 else (0.85 if best_tier <= 3 else 0.7)
        confidence = confidence * tier_boost
        _correction_safe = str(parsed.get("correction", ""))[:400]
        # 2026-05-20: non-correction detection (witness-confusion smoking-gun)
        if _is_non_correction(_correction_safe, claim):
            _correction_safe = ""
            if verdict_raw == CONTRADICTS:
                verdict_raw = UNCERTAIN
        return WitnessVerdict(
            witness="google1998",
            verdict=verdict_raw,
            confidence=confidence,
            evidence=str(parsed.get("evidence", ""))[:400],
            correction=_correction_safe,
            audit_comment=str(parsed.get("audit_comment", ""))[:300],
            recommended_source=str(parsed.get("recommended_source", "")
                                    or (sources[0] if sources else ""))[:300],
            sources=sources if verdict_raw != ABSENT else [],
            latency_ms=(time.time() - t0) * 1000,
        )
    except Exception as e:
        return WitnessVerdict(
            witness="google1998", verdict=ABSENT, error=str(e)[:200],
            sources=sources, latency_ms=(time.time() - t0) * 1000,
        )


# ============================================================
# Witness 3: Google-today (live web search, post-LLM era)
# ============================================================

def witness_google_today(claim: str, timeout_s: float = 10.0,
                          search_topic: Optional[str] = None) -> WitnessVerdict:
    """Live-web witness — today's web search.

    Counterpart to witness_google1998. Where google1998 (Wayback) is
    CLEAN but sparse, google_today is POLLUTED but broad+recent.
    The two together let the tribunal distinguish:
      - both SUPPORTS → strongly anchored across eras
      - 1998-only → pre-LLM-fact erased / paywalled today
      - today-only → either new info OR LLM-contamination feedback loop
      - disagreement → interesting, needs operator review

    The judge-prompt explicitly weights down LLM-pollution-pattern
    results (KI-Blogs, generic listicles) and weights up reputable
    pre-2020 / institutional sources.
    """
    t0 = time.time()
    web_search = _adapter("web_search")
    llm_call = _adapter("llm_call")
    domain_tier = _adapter("domain_tier")

    if llm_call is None:
        return WitnessVerdict(
            witness="google_today", verdict=ABSENT,
            error="no llm_call adapter for judge-pass",
            latency_ms=(time.time() - t0) * 1000,
        )
    if web_search is None:
        return WitnessVerdict(
            witness="google_today", verdict=ABSENT,
            error="no web_search adapter",
            latency_ms=(time.time() - t0) * 1000,
        )

    # Use search_topic for the query if provided (avoid LLM-pollution amplification
    # by searching for the LLM's own halluzinated text verbatim).
    query = (search_topic or claim)[:200]
    try:
        results = web_search(query, 3) or []
    except Exception as e:
        return WitnessVerdict(
            witness="google_today", verdict=ABSENT, error=str(e)[:200],
            latency_ms=(time.time() - t0) * 1000,
        )

    if not results:
        return WitnessVerdict(
            witness="google_today", verdict=ABSENT,
            evidence="no live web results",
            latency_ms=(time.time() - t0) * 1000,
        )

    # Format results for LLM-judge — same shape as google1998
    lines = []
    sources = []
    best_tier = 9
    for i, r in enumerate(results[:3]):
        title = (r.get("title") or "")[:120]
        url = (r.get("url") or r.get("href") or "")[:200]
        snippet = (r.get("snippet") or r.get("body") or "")[:400]
        tier = 9
        if domain_tier and url:
            try:
                tier = int(domain_tier(url))
            except Exception:
                tier = 9
        best_tier = min(best_tier, tier)
        tier_label = f"T{tier}" if tier < 9 else "T9·unbekannt"
        lines.append(f"[{i+1}] ({tier_label}) {title}\n     URL: {url}\n     Snippet: {snippet}")
        sources.append(url)

    results_text = "\n\n".join(lines)
    prompt = GOOGLE_TODAY_JUDGE_PROMPT.format(claim=claim[:600], results_text=results_text)

    try:
        raw = llm_call(prompt, temperature=0.1, timeout=int(timeout_s), json_mode=True)
        parsed = _safe_json_parse(raw) or {}
        verdict_raw = str(parsed.get("verdict", "uncertain")).lower()
        if verdict_raw not in (SUPPORTS, CONTRADICTS, UNCERTAIN, ABSENT):
            verdict_raw = UNCERTAIN
        confidence = float(parsed.get("confidence", 0.3))
        confidence = max(0.0, min(1.0, confidence))
        # Post-LLM-era penalty: live web is contaminated; cap confidence below 1.0
        # unless reputable T0/T1 sources are present.
        if best_tier <= 1:
            tier_boost = 0.95   # reputable institutional source — high but not max
        elif best_tier <= 3:
            tier_boost = 0.75
        else:
            tier_boost = 0.55   # generic web → contamination-risk discount
        confidence = confidence * tier_boost
        _correction_safe = str(parsed.get("correction", ""))[:400]
        # 2026-05-20: non-correction detection (witness-confusion smoking-gun)
        if _is_non_correction(_correction_safe, claim):
            _correction_safe = ""
            if verdict_raw == CONTRADICTS:
                verdict_raw = UNCERTAIN
        return WitnessVerdict(
            witness="google_today",
            verdict=verdict_raw,
            confidence=confidence,
            evidence=str(parsed.get("evidence", ""))[:400],
            correction=_correction_safe,
            audit_comment=str(parsed.get("audit_comment", ""))[:300],
            recommended_source=str(parsed.get("recommended_source", "")
                                    or (sources[0] if sources else ""))[:300],
            sources=sources if verdict_raw != ABSENT else [],
            latency_ms=(time.time() - t0) * 1000,
        )
    except Exception as e:
        return WitnessVerdict(
            witness="google_today", verdict=ABSENT, error=str(e)[:200],
            sources=sources, latency_ms=(time.time() - t0) * 1000,
        )


# ============================================================
# Witness 4: Operator (cache + manual override)
# ============================================================

def witness_operator(claim: str, timeout_s: float = 1.0) -> WitnessVerdict:
    """Operator-truth witness. Highest weight in tribunal when present.

    Looks up the claim in an operator-curated truth-DB. Returns ABSENT
    (not UNCERTAIN) when the operator has not ruled on this claim. ABSENT
    is informationally-different from UNCERTAIN — operator simply hasn't
    opined yet, not 'operator considered it and was unsure'.

    M2 stub: operator_lookup adapter is read-only stub (returns None).
    M5 will add operator-rubric UI.
    """
    t0 = time.time()
    op_lookup = _adapter("operator_lookup")
    if op_lookup is None:
        return WitnessVerdict(
            witness="operator", verdict=ABSENT,
            error="no operator_lookup adapter",
            latency_ms=(time.time() - t0) * 1000,
        )

    try:
        result = op_lookup(claim)
        if result is None:
            return WitnessVerdict(
                witness="operator", verdict=ABSENT,
                evidence="not in operator-truth-db",
                latency_ms=(time.time() - t0) * 1000,
            )
        verdict_raw = str(result.get("verdict", "uncertain")).lower()
        if verdict_raw not in (SUPPORTS, CONTRADICTS, UNCERTAIN):
            verdict_raw = UNCERTAIN
        return WitnessVerdict(
            witness="operator",
            verdict=verdict_raw,
            confidence=float(result.get("confidence", 1.0)),  # operator-truth is high-conf by default
            evidence=str(result.get("note", ""))[:400],
            correction=str(result.get("correction", ""))[:400],
            latency_ms=(time.time() - t0) * 1000,
        )
    except Exception as e:
        return WitnessVerdict(
            witness="operator", verdict=ABSENT, error=str(e)[:200],
            latency_ms=(time.time() - t0) * 1000,
        )


# ============================================================
# Tribunal: combine verdicts → splice-tier
# ============================================================

# Tier-mapping. Inputs: counts of each verdict-type across present witnesses.
# Operator-veto is applied OUT-OF-BAND (overrides tribunal-rules below).

def _combine(verdicts: list[WitnessVerdict]) -> tuple[str, str, Optional[str]]:
    """Combine N witness-verdicts → (splice_tier, confidence, correction).

    Returns:
        (final_tier, confidence_label, correction_text_or_None)

    Rules (with N=number-of-present-witnesses, excluding ABSENT):
      Operator-veto:
        - If operator=CONTRADICTS → final at-most quasinonfact;
          if both other witnesses also contradict → nonfact (high).
        - If operator=SUPPORTS → final at-least quasifact;
          if both others support → factfact (high).

      No operator-veto:
        N=3 SUPPORTS                 → factfact   (high)
        N=2 SUPPORTS + 1 UNCERTAIN   → quasifact  (medium)
        N=2 SUPPORTS + 1 CONTRADICTS → quasifact  (low)
        N=1 SUPPORTS + 2 UNCERTAIN   → maybefact  (low)
        N=1 SUPPORTS + 1 CONTRADICTS → maybefact  (low)
        All UNCERTAIN                → maybefact  (low)
        N=2 CONTRADICTS + 1 UNCERTAIN→ quasinonfact (medium)
        N=2 CONTRADICTS + 1 SUPPORTS → quasinonfact (low)
        N=3 CONTRADICTS              → nonfact    (high)
        All ABSENT                   → nullfact   (high)
        Single SUPPORTS, no others   → quasifact  (low)
        Single CONTRADICTS, no others→ quasinonfact (low)
    """
    # Find operator-verdict (if any)
    op_verdict = next((v for v in verdicts if v.witness == "operator" and v.verdict != ABSENT), None)
    present = [v for v in verdicts if v.verdict != ABSENT]
    n = len(present)

    # No witnesses present → nullfact-high
    if n == 0:
        return ("nullfact", "high", None)

    counts = {SUPPORTS: 0, CONTRADICTS: 0, UNCERTAIN: 0}
    for v in present:
        counts[v.verdict] = counts.get(v.verdict, 0) + 1

    # First correction-text we can find (witness with CONTRADICTS + correction)
    correction = None
    for v in present:
        if v.verdict == CONTRADICTS and v.correction:
            correction = v.correction
            break

    # Operator-veto path
    if op_verdict is not None:
        non_op_present = [v for v in present if v.witness != "operator"]
        non_op_counts = {SUPPORTS: 0, CONTRADICTS: 0, UNCERTAIN: 0}
        for v in non_op_present:
            non_op_counts[v.verdict] = non_op_counts.get(v.verdict, 0) + 1

        if op_verdict.verdict == CONTRADICTS:
            if non_op_counts[CONTRADICTS] >= 2:
                return ("nonfact", "high", correction)
            if non_op_counts[CONTRADICTS] == 1:
                return ("nonfact", "medium", correction)
            return ("quasinonfact", "medium", correction)
        elif op_verdict.verdict == SUPPORTS:
            if non_op_counts[SUPPORTS] >= 2:
                return ("factfact", "high", None)
            if non_op_counts[SUPPORTS] == 1:
                return ("factfact", "medium", None)
            return ("quasifact", "medium", None)
        else:  # UNCERTAIN
            return ("maybefact", "medium", None)

    # No-operator-veto rules — N=3 (or 2 or 1)
    s, c, u = counts[SUPPORTS], counts[CONTRADICTS], counts[UNCERTAIN]

    if n == 3:
        if s == 3:
            return ("factfact", "high", None)
        if c == 3:
            return ("nonfact", "high", correction)
        if s == 2 and u == 1:
            return ("quasifact", "medium", None)
        if s == 2 and c == 1:
            return ("quasifact", "low", correction)
        if c == 2 and u == 1:
            return ("quasinonfact", "medium", correction)
        if c == 2 and s == 1:
            return ("quasinonfact", "low", correction)
        if s == 1 and u == 2:
            return ("maybefact", "low", None)
        if c == 1 and u == 2:
            return ("maybefact", "low", correction)
        if s == 1 and c == 1 and u == 1:
            return ("maybefact", "low", correction)
        if u == 3:
            return ("maybefact", "low", None)

    if n == 2:
        if s == 2:
            return ("quasifact", "medium", None)
        if c == 2:
            return ("quasinonfact", "medium", correction)
        if s == 1 and c == 1:
            return ("maybefact", "low", correction)
        if s == 1 and u == 1:
            return ("quasifact", "low", None)
        if c == 1 and u == 1:
            return ("quasinonfact", "low", correction)
        if u == 2:
            return ("maybefact", "low", None)

    if n == 1:
        if s == 1:
            return ("quasifact", "low", None)
        if c == 1:
            return ("quasinonfact", "low", correction)
        if u == 1:
            return ("maybefact", "low", None)

    # N=4 cases (google1998 + google_today + claude + 1 other, or any 4-way mix)
    if n == 4:
        if s == 4:
            return ("factfact", "high", None)
        if c == 4:
            return ("nonfact", "high", correction)
        if s == 3 and u == 1:
            return ("factfact", "medium", None)
        if s == 3 and c == 1:
            return ("quasifact", "medium", correction)
        if s == 2 and u == 2:
            return ("quasifact", "low", None)
        if s == 2 and c == 1 and u == 1:
            return ("quasifact", "low", correction)
        if s == 2 and c == 2:
            return ("maybefact", "medium", correction)
        if s == 1 and u == 3:
            return ("maybefact", "low", None)
        if s == 1 and c == 1 and u == 2:
            return ("maybefact", "low", correction)
        if s == 1 and c == 2 and u == 1:
            return ("quasinonfact", "low", correction)
        if s == 1 and c == 3:
            return ("quasinonfact", "medium", correction)
        if u == 4:
            return ("maybefact", "low", None)
        if c == 1 and u == 3:
            return ("maybefact", "low", correction)
        if c == 2 and u == 2:
            return ("quasinonfact", "low", correction)
        if c == 3 and u == 1:
            return ("quasinonfact", "medium", correction)

    # Generic fallback for n>=5 (wiki_graph extension 2026-05-19) — ratio-based.
    # Avoids enumerating dozens of 5-witness cases. Calibrated to match the
    # spirit of the explicit n=3/n=4 cases:
    #   ≥80% supports → factfact high
    #   ≥60% supports → factfact medium
    #   majority supports → quasifact
    #   ≥80% contradicts → nonfact high
    #   ≥60% contradicts → nonfact medium
    #   majority contradicts → quasinonfact
    #   tie / mixed → maybefact
    if n >= 5:
        s_ratio = s / n
        c_ratio = c / n
        if s == n:
            return ("factfact", "high", None)
        if c == n:
            return ("nonfact", "high", correction)
        if s_ratio >= 0.8:
            return ("factfact", "medium", None)
        if c_ratio >= 0.8:
            return ("nonfact", "medium", correction)
        if s_ratio >= 0.6:
            return ("quasifact", "medium", correction if c > 0 else None)
        if c_ratio >= 0.6:
            return ("quasinonfact", "medium", correction)
        if s > c:
            return ("quasifact", "low", correction if c > 0 else None)
        if c > s:
            return ("quasinonfact", "low", correction)
        return ("maybefact", "low", correction)

    return ("nullfact", "low", None)


def run_tribunal(claim: str, timeout_s: float = 12.0,
                 witnesses_to_consult: Optional[list[str]] = None) -> TribunalResult:
    """Run all-three witnesses in parallel, combine into TribunalResult.

    Args:
        claim: the text-claim to verify
        timeout_s: total wall-clock budget for tribunal (default 12s).
                   Each witness gets timeout_s * 0.8 individually.
        witnesses_to_consult: subset of ['claude', 'google1998', 'google_today', 'operator'];
                              default is all-four.

    Returns:
        TribunalResult with final_tier + per-witness verdicts.

    Safety:
        - Total wall-clock bounded by timeout_s. If a witness exceeds its
          slice, it gets recorded as ABSENT(timeout) and tribunal proceeds.
        - Exceptions in any witness are caught + logged; tribunal continues.
    """
    t0 = time.time()
    claim_text = (claim or "").strip()
    if not claim_text:
        return TribunalResult(claim_text="", final_tier="nullfact",
                              tribunal_confidence="high")

    if witnesses_to_consult is None:
        witnesses_to_consult = ["claude", "google1998", "google_today", "wiki_graph", "operator"]

    per_witness_timeout = timeout_s * 0.8
    verdicts: list[WitnessVerdict] = []

    # 2026-05-19 topic-extraction: when search-witnesses are consulted, derive
    # a clean search-topic from the claim before searching. Avoids amplifying
    # the LLM's hallucination by searching for its own fabricated text verbatim.
    search_topic = None
    if "google1998" in witnesses_to_consult or "google_today" in witnesses_to_consult:
        search_topic = extract_search_topic(claim_text)

    # 2026-05-19 Witness 5: wiki_graph (snap-connect via Wikipedia). Lazy-import
    # to avoid circular dependency at module-load + tolerate missing optional dep.
    def _witness_wiki_graph_fn():
        try:
            from wrapper_v2.pipeline import wiki_wortwolke
            return wiki_wortwolke.witness_wiki_graph(claim_text, per_witness_timeout)
        except Exception as e:
            return WitnessVerdict(
                witness="wiki_graph", verdict=ABSENT,
                error=f"import or call failed: {str(e)[:120]}",
            )

    fns = {
        "claude":       lambda: witness_claude(claim_text, per_witness_timeout),
        "google1998":   lambda: witness_google1998(claim_text, per_witness_timeout, search_topic),
        "google_today": lambda: witness_google_today(claim_text, per_witness_timeout, search_topic),
        "wiki_graph":   _witness_wiki_graph_fn,
        "operator":     lambda: witness_operator(claim_text, 1.0),  # always-fast
    }

    selected = [name for name in witnesses_to_consult if name in fns]
    if not selected:
        return TribunalResult(claim_text=claim_text, final_tier="nullfact",
                              tribunal_confidence="high")

    with ThreadPoolExecutor(max_workers=len(selected), thread_name_prefix="tribunal") as ex:
        future_map = {ex.submit(fns[name]): name for name in selected}
        for fut, name in future_map.items():
            try:
                v = fut.result(timeout=timeout_s)
                verdicts.append(v)
            except FuturesTimeout:
                verdicts.append(WitnessVerdict(
                    witness=name, verdict=ABSENT,
                    error=f"tribunal-timeout ({timeout_s}s)",
                    latency_ms=timeout_s * 1000,
                ))
            except Exception as e:
                verdicts.append(WitnessVerdict(
                    witness=name, verdict=ABSENT, error=str(e)[:200],
                ))

    final_tier, conf, correction = _combine(verdicts)

    # Audit-the-reasoning extension (operator-spec 2026-05-19): collect plain-language
    # audit-comments + recommended-sources from all CONTRADICTS witnesses. Exposed
    # via TribunalResult → factampel_tag → UI so user sees WHY LLM was wrong + WHERE
    # to look for the correct answer.
    audit_comments_collected = []
    recommended_sources_collected = []
    for v in verdicts:
        if v.verdict == CONTRADICTS:
            if v.audit_comment and v.audit_comment not in audit_comments_collected:
                audit_comments_collected.append(v.audit_comment)
            if v.recommended_source and v.recommended_source not in recommended_sources_collected:
                recommended_sources_collected.append(v.recommended_source)

    return TribunalResult(
        claim_text=claim_text,
        verdicts=verdicts,
        final_tier=final_tier,
        off_axis_tag=None,
        tribunal_confidence=conf,
        correction_text=correction,
        audit_comments=audit_comments_collected,
        recommended_sources=recommended_sources_collected,
        witnesses_consulted=selected,
        total_latency_ms=(time.time() - t0) * 1000,
        from_cache=False,
    )


# ============================================================
# Utility
# ============================================================

def _is_non_correction(correction: str, claim: str) -> bool:
    """Smoking-gun detector for witness-confusion (2026-05-20).

    Detects three patterns of confused/echoed corrections:

    1. Verbatim-echo: correction == claim (modulo whitespace + punctuation)
    2. Subset-echo: 75%+ overlap between correction and claim
    3. Wiki-snippet-echo: correction is structured as
       "'TermA': definitionA | 'TermB': definitionB" — witness dumped the
       wiki-graph context-block instead of producing an actual contradiction.
       Detected by quote-colon-pattern of terms that appear in the claim.

    When detected, caller should clear correction-text + downgrade
    CONTRADICTS → UNCERTAIN.
    """
    if not correction or not claim:
        return False
    def _norm(s):
        return " ".join(re.sub(r"[^\wäöüß\s]", "", s.lower()).split())
    nc, ncl = _norm(correction), _norm(claim)
    if not nc or not ncl:
        return False
    # Pattern 1+2: verbatim or subset echo
    if nc == ncl:
        return True
    short, long_ = (nc, ncl) if len(nc) < len(ncl) else (ncl, nc)
    if short in long_ and len(short) >= 0.75 * len(long_):
        return True
    # Pattern 3: wiki-snippet-echo — "'Term': def | 'Term2': def2"
    # If correction contains 1+ quoted-term-colon-pattern AND the quoted terms
    # appear in the claim → witness dumped wiki-snippets instead of correcting.
    quoted_terms = re.findall(r"['‘’“”]([^'‘’“”]{2,40})['‘’“”]\s*:", correction)
    if quoted_terms:
        claim_lower = claim.lower()
        matched = sum(1 for t in quoted_terms if t.lower() in claim_lower)
        # If majority of quoted-terms are in the claim → echo
        if matched >= 1 and matched >= len(quoted_terms) * 0.5:
            return True
    return False


def _safe_json_parse(raw: str) -> Optional[dict]:
    """Tolerant JSON parser — accepts code-fence-wrapped JSON too."""
    if not raw:
        return None
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    # Strip code-fence
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    # Find first { ... } block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    try:
        return json.loads(text)
    except Exception:
        return None


def tribunal_to_dict(tr: TribunalResult) -> dict:
    """Serialize for SSE-emit + cache-store."""
    return {
        "claim_text": tr.claim_text,
        "final_tier": tr.final_tier,
        "off_axis_tag": tr.off_axis_tag,
        "tribunal_confidence": tr.tribunal_confidence,
        "correction_text": tr.correction_text,
        "audit_comments": tr.audit_comments,
        "recommended_sources": tr.recommended_sources,
        "witnesses_consulted": tr.witnesses_consulted,
        "total_latency_ms": round(tr.total_latency_ms, 1),
        "from_cache": tr.from_cache,
        "verdicts": [asdict(v) for v in tr.verdicts],
    }
