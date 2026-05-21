"""Wikipedia Wortwolke + Snap-Connect-Graph — 5. Witness + Own-Way Layer.

Operator-vision 2026-05-19 (per memory:eigene_browser_engine_architektur):
- Harvest Wikipedia definitions for terms in user query AND LLM response
- Build snap-connect-graph from direct-mention + related-link edges
- Verify LLM-claimed connections against the graph (5. Witness)
- Inject wortwolken into the LLM prompt as ground-truth (own-way layer)

Wikipedia REST API:
- Summary: GET /api/rest_v1/page/summary/{title} → {extract, content_urls, type}
- Related: GET /api/rest_v1/page/related/{title} → {pages: [...]}

No external dependencies. Uses urllib only. Best-effort with timeouts.

Per [[hammwoehner_haecker_vizor_doctrine]] labrador-mode: "labby sniffs all
socks" — every claimed connection between terms is sniffed against the
Wikipedia graph. No documented edge → bark CONTRADICTS.
"""

from __future__ import annotations

import json
import re
import socket
import time
import urllib.parse
import urllib.request
import urllib.error
from typing import Optional

from wrapper_v2.pipeline import three_witness


# ============================================================
# Wikipedia REST API client
# ============================================================

_WIKI_API_SUMMARY_TEMPLATE = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
_WIKI_API_RELATED_TEMPLATE = "https://{lang}.wikipedia.org/api/rest_v1/page/related/{title}"


def fetch_wiki_summary(term: str, lang: str = "de", timeout: float = 5.0) -> Optional[dict]:
    """Fetch Wikipedia article summary.

    Returns:
        {term, title, extract, url, source='wikipedia', is_disambig}
        or None on failure.
    """
    if not term or not term.strip():
        return None
    try:
        title = urllib.parse.quote(term.strip().replace(" ", "_"))
        url = _WIKI_API_SUMMARY_TEMPLATE.format(lang=lang, title=title)
        req = urllib.request.Request(url, headers={
            "User-Agent": "vectoryz-wiki-wortwolke/1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        is_disambig = (data.get("type") == "disambiguation")
        content_url = (data.get("content_urls", {})
                       .get("desktop", {}).get("page", ""))
        return {
            "term": term,
            "title": data.get("title", term),
            "extract": (data.get("extract") or "")[:2000],
            "url": content_url,
            "source": "wikipedia",
            "is_disambig": is_disambig,
        }
    except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout, Exception):
        return None


def fetch_disambig_alternatives(term: str, lang: str = "de",
                                 timeout: float = 5.0) -> Optional[dict]:
    """Fetch Wikipedia disambiguation-page content for a term.

    Per [[morla_master_list]] + [[disambig_coverage_doctrine]] (2026-05-21):
    when user-query is short term/acronym (ECHELON, MK-Ultra), the
    common-sense answer needs to ENUMERATE bedeutungen first, then dive
    into the likely-intended primary. Wikipedia has explicit Begriffsklärung
    pages for ambiguous terms.

    Tries language-specific disambig-suffix patterns:
      lang=de → "<Term> (Begriffsklärung)"
      lang=en → "<Term> (disambiguation)"
      others  → plain term (might BE a disambig page)

    Returns:
        dict with {term, title, extract, url, alternatives} on hit
        None if no disambig page found
    """
    if not term or not term.strip():
        return None
    term = term.strip()
    # Wikipedia is case-sensitive in URLs. Try multiple capitalizations so
    # "ECHELON" + "Echelon" + "echelon" all resolve. Order: original, then
    # capitalize-first (most common Wikipedia title-style), then title-case
    # (for multi-word terms).
    term_variants = []
    seen_variants = set()
    for v in (term, term.capitalize(), term.title(), term.upper()):
        if v not in seen_variants:
            term_variants.append(v)
            seen_variants.add(v)

    if lang == "de":
        suffix = "(Begriffsklärung)"
    elif lang == "en":
        suffix = "(disambiguation)"
    else:
        suffix = None

    result = None
    matched_variant = None
    # First pass: try each capitalization with disambig-suffix
    if suffix:
        for v in term_variants:
            disambig_term = f"{v} {suffix}"
            r = fetch_wiki_summary(disambig_term, lang=lang, timeout=timeout)
            if r is not None and r.get("extract"):
                result = r
                matched_variant = v
                break

    # Second pass: maybe the plain term IS already a disambig page
    if result is None:
        for v in term_variants:
            r = fetch_wiki_summary(v, lang=lang, timeout=timeout)
            if r is not None and r.get("is_disambig"):
                result = r
                matched_variant = v
                break
        if result is None:
            return None

    extract = (result.get("extract") or "").strip()
    if not extract:
        return None

    # Parse alternatives: disambig-extracts use newline-separated bullets in
    # German Wikipedia REST API output. The lead-line ("X steht für:" /
    # "X may refer to:") is OFTEN concatenated with the first alternative on
    # the same line (no whitespace after colon), so strip the lead-prefix
    # inline before splitting.
    # Strip "<Term> steht für:" / "<Term> may refer to:" prefix from extract
    extract_clean = re.sub(
        r"^[\w\-äöüÄÖÜß ]+\s*(?:steht für:|may refer to:|bezeichnet:|verweist auf:)\s*",
        "",
        extract,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    lines = [ln.strip() for ln in extract_clean.split("\n") if ln.strip()]
    alternatives = []
    for ln in lines:
        # Skip remaining lead-text leftovers + very-short noise
        if ln.lower().rstrip(":").endswith(("steht für", "may refer to", "bezeichnet")):
            continue
        if len(ln) < 5:
            continue
        alternatives.append(ln)

    return {
        "term": term,
        "title": result.get("title", disambig_term),
        "extract": extract,
        "url": result.get("url", ""),
        "alternatives": alternatives,
        "lang": lang,
    }


def format_disambig_for_prompt(disambig: dict) -> str:
    """Format disambig-content as a prompt-context-block with antwort-disziplin.

    Output structure: header → list of alternatives → discipline-instruction
    (enumerate first, then deep-dive on the likely primary).
    """
    if not disambig:
        return ""
    alternatives = disambig.get("alternatives") or []
    if not alternatives:
        return ""
    alt_block = "\n".join(f"  • {a}" for a in alternatives[:10])
    return (
        f"[Disambiguation-Erkennung — der Begriff hat mehrere Bedeutungen]\n"
        f"Wikipedia-Begriffsklärung '{disambig.get('title', '')}':\n"
        f"{alt_block}\n"
        f"Quelle: {disambig.get('url', '')}\n"
        f"\n"
        f"ANTWORT-DISZIPLIN: Der User-Begriff ist mehrdeutig. ENUMERIERE "
        f"zuerst KURZ (1-2 Sätze je) ALLE oben gelisteten Bedeutungen, "
        f"dann gehe in die TIEFE auf die wahrscheinlich gemeinte "
        f"Hauptbedeutung. Verschweige keine Variante — auch lokale "
        f"Kontexte (z.B. Festival in Bavaria, oder Sport-Begriff) "
        f"gehören dazu. So bedient die Antwort beide Lager: der "
        f"NSA-Interessierte UND der EDM-Festival-Interessierte."
    )


def fetch_wiki_related(term: str, lang: str = "de", timeout: float = 5.0,
                       max_results: int = 8) -> list:
    """Fetch Wikipedia related-articles."""
    if not term or not term.strip():
        return []
    try:
        title = urllib.parse.quote(term.strip().replace(" ", "_"))
        url = _WIKI_API_RELATED_TEMPLATE.format(lang=lang, title=title)
        req = urllib.request.Request(url, headers={
            "User-Agent": "vectoryz-wiki-wortwolke/1.0",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        pages = (data or {}).get("pages", [])
        return [
            {
                "title": p.get("title", ""),
                "extract": (p.get("extract") or "")[:200],
                "url": p.get("content_urls", {}).get("desktop", {}).get("page", ""),
            }
            for p in pages[:max_results]
        ]
    except Exception:
        return []


# ============================================================
# Term extraction
# ============================================================

_STOPWORDS = {
    # Articles
    "Der", "Die", "Das", "Ein", "Eine", "Einen", "Einer", "Eines", "Einem",
    # Conjunctions
    "Und", "Oder", "Aber", "Doch", "Auch", "Noch", "Nur", "Schon", "Als",
    # Pronouns
    "Ich", "Du", "Er", "Sie", "Es", "Wir", "Ihr", "Mir", "Dir",
    "Mich", "Dich", "Sich", "Mein", "Dein", "Sein",
    # Question words
    "Was", "Wer", "Wie", "Wo", "Wann", "Warum", "Weshalb", "Wieso",
    "Welcher", "Welche", "Welches", "Wieviel",
    # Negation / quantity
    "Ja", "Nein", "Nicht", "Kein", "Keine", "Alle", "Etwas", "Nichts",
    # Prepositions
    "Mit", "Ohne", "Bei", "Von", "Zu", "Auf", "An", "In", "Um", "Über",
    "Vor", "Nach", "Während", "Wenn", "Bis", "Seit", "Durch", "Für",
    # Time
    "Heute", "Gestern", "Morgen", "Jetzt", "Dann", "Damals",
    # Common nouns that aren't entities
    "Frage", "Antwort", "Bitte", "Danke", "Hallo", "Tschüss",
    "Beispiel", "Sache", "Ding", "Mensch", "Leute", "Zeit", "Jahr",
    "Tag", "Woche", "Monat",
}


def extract_terms(text: str, max_terms: int = 6) -> list:
    """Extract candidate terms (Eigennamen + Fachbegriffe) from German text.

    Strategy:
    - Multi-word capitalized sequences ("Stanley Meyer", "Nessun Dorma")
    - Single capitalized words (4+ chars, not stopwords)
    - Scientific terms (lowercase with technical suffix in/-on/-ase/...)
    """
    if not text:
        return []

    # Multi-word capitalized
    multi_re = re.compile(
        r"\b([A-ZÄÖÜ][a-zäöüß]{2,}(?:[\s\-][A-ZÄÖÜ][a-zäöüß]{2,}){1,2})\b"
    )
    # Single capitalized (4+ chars)
    single_re = re.compile(r"\b([A-ZÄÖÜ][a-zäöüß]{3,})\b")
    # Lowercase scientific (technical suffix)
    sci_re = re.compile(
        r"\b([a-zäöü]{3,}(?:in|on|ase|ide|ol|ium|gen|amin|säure|sterol))\b"
    )

    terms = []
    seen = set()

    # Multi-word first (more specific)
    for m in multi_re.finditer(text):
        t = m.group(1).strip()
        key = t.lower()
        if key in seen:
            continue
        # Skip if all parts are stopwords
        if all(w in _STOPWORDS for w in re.split(r"[\s\-]+", t)):
            continue
        seen.add(key)
        terms.append(t)

    # Then single capitalized
    for m in single_re.finditer(text):
        t = m.group(1).strip()
        if t in _STOPWORDS:
            continue
        key = t.lower()
        if key in seen:
            continue
        # Skip if it's a substring of a multi-word already found
        if any(key in s.split() for s in seen):
            continue
        seen.add(key)
        terms.append(t)

    # Scientific terms (lowercase)
    for m in sci_re.finditer(text):
        t = m.group(1).strip()
        key = t.lower()
        if key in seen:
            continue
        # Capitalize for German Nomen convention
        t_cap = t[0].upper() + t[1:]
        seen.add(key)
        terms.append(t_cap)

    return terms[:max_terms]


# ============================================================
# Wortwolken-Builder + Prompt-Format (own-way layer)
# ============================================================

def build_wortwolken_for_query(query: str, max_terms: int = 4,
                                  timeout_each: float = 5.0) -> list:
    """Extract terms from query + fetch wiki-summary for each.

    Returns list of wortwolken-dicts (skips disambig + miss).
    """
    terms = extract_terms(query, max_terms=max_terms)
    wortwolken = []
    for term in terms:
        ww = fetch_wiki_summary(term, timeout=timeout_each)
        if ww and not ww.get("is_disambig") and ww.get("extract"):
            wortwolken.append(ww)
    return wortwolken


def format_wortwolken_for_prompt(wortwolken: list) -> str:
    """Format wortwolken as prompt-injection context-block.

    The 'eigene-Browser-Engine' anchor: these are authoritative Wikipedia
    definitions, treat as truth for the rendered answer.
    """
    if not wortwolken:
        return ""
    lines = [
        "[Wiki-Wortwolke — Wikipedia-Definitionen fuer Terms aus der Anfrage]",
        "ANWEISUNG: Diese Definitionen sind autoritativ. Wenn du in deiner "
        "Antwort eine Verbindung zwischen zwei dieser Terms BEHAUPTEST, MUSS "
        "diese Verbindung in mindestens einer der Definitionen explizit auftauchen — "
        "sonst ist die Verbindung Halluzination und du laesst sie weg.",
        "",
    ]
    for ww in wortwolken:
        lines.append(f"★ {ww['title']}: {ww['extract']}")
        if ww.get("url"):
            lines.append(f"    URL: {ww['url']}")
        lines.append("")
    lines.append("[/Wiki-Wortwolke]")
    return "\n".join(lines)


# ============================================================
# Witness #5: wiki_graph — snap-connect verification
# ============================================================

def witness_wiki_graph(claim: str, timeout_s: float = 10.0,
                       search_topic: Optional[str] = None) -> "three_witness.WitnessVerdict":
    """5. Witness: Wikipedia-graph snap-connect for the claim.

    Per operator-vision: labby sniffs all socks. Check if Wikipedia documents
    the connections the claim asserts:
    - 0 terms → ABSENT (no entities to graph)
    - 1 term → SUPPORTS if term exists in Wikipedia (existence-grade)
    - 2+ terms → SUPPORTS if any pair has documented edge, CONTRADICTS if none
    """
    t0 = time.time()
    terms = extract_terms(claim, max_terms=3)

    if not terms:
        return three_witness.WitnessVerdict(
            witness="wiki_graph",
            verdict=three_witness.ABSENT,
            evidence="keine extrahierbaren Terms",
            latency_ms=(time.time() - t0) * 1000,
        )

    if len(terms) == 1:
        ww = fetch_wiki_summary(terms[0], timeout=timeout_s)
        if ww is None:
            return three_witness.WitnessVerdict(
                witness="wiki_graph",
                verdict=three_witness.ABSENT,
                evidence=f"'{terms[0]}' nicht in Wikipedia",
                latency_ms=(time.time() - t0) * 1000,
            )
        if ww.get("is_disambig"):
            return three_witness.WitnessVerdict(
                witness="wiki_graph",
                verdict=three_witness.UNCERTAIN,
                evidence=f"'{terms[0]}' ist disambig in Wikipedia",
                sources=[ww.get("url", "")],
                latency_ms=(time.time() - t0) * 1000,
            )
        return three_witness.WitnessVerdict(
            witness="wiki_graph",
            verdict=three_witness.SUPPORTS,
            confidence=0.6,
            evidence=f"'{terms[0]}' definiert in Wikipedia: {ww['extract'][:200]}",
            sources=[ww.get("url", "")],
            latency_ms=(time.time() - t0) * 1000,
        )

    # 2+ terms: pairwise connection check
    wortwolken = {}
    for term in terms:
        ww = fetch_wiki_summary(term, timeout=timeout_s)
        if ww and not ww.get("is_disambig"):
            wortwolken[term] = ww

    if len(wortwolken) < 2:
        return three_witness.WitnessVerdict(
            witness="wiki_graph",
            verdict=three_witness.ABSENT,
            evidence=f"konnte nicht beide Terms aufloesen ({list(wortwolken.keys())})",
            latency_ms=(time.time() - t0) * 1000,
        )

    term_list = list(wortwolken.keys())
    connection_found = False
    no_connection_pair = None
    evidence = ""
    sources = []

    for i in range(len(term_list)):
        for j in range(i + 1, len(term_list)):
            a, b = term_list[i], term_list[j]
            wa, wb = wortwolken[a], wortwolken[b]
            sources.extend([wa.get("url", ""), wb.get("url", "")])
            a_text = wa["extract"].lower()
            b_text = wb["extract"].lower()
            a_mentions_b = (b.lower() in a_text or wb["title"].lower() in a_text)
            b_mentions_a = (a.lower() in b_text or wa["title"].lower() in b_text)
            if a_mentions_b or b_mentions_a:
                connection_found = True
                evidence = (
                    f"Wikipedia erwaehnt Verbindung zwischen '{a}' und '{b}' "
                    f"(mention in {'a→b' if a_mentions_b else 'b→a'})"
                )
                break
            else:
                no_connection_pair = (a, b)
        if connection_found:
            break

    if connection_found:
        return three_witness.WitnessVerdict(
            witness="wiki_graph",
            verdict=three_witness.SUPPORTS,
            confidence=0.75,
            evidence=evidence[:400],
            sources=[s for s in sources if s][:3],
            latency_ms=(time.time() - t0) * 1000,
        )

    if no_connection_pair:
        a, b = no_connection_pair
        wa, wb = wortwolken[a], wortwolken[b]
        # 2026-05-21 SMARTFAUL fix per [[pattern_without_semantic_validation]]:
        # OLD bug: no-cross-mention → CONTRADICTS + correction dumped as
        # "'TermA': wiki-def | 'TermB': wiki-def" — structurally identical to
        # the wiki-snippet-echo pattern that _is_non_correction detects.
        # Symptoms (Hammwöhner-Heidelberg case 2026-05-21):
        #   - Hammwöhner isn't notable enough for Uni-Heidelberg's Wiki-article
        #   - wiki_graph sees no cross-mention → emits CONTRADICTS
        #   - "Korrektur" field shows two raw Wikipedia-definitions
        #   - User sees "→ Korrektur: 'Medizinische Informatik': Die med. Inf.
        #     ist die Wissenschaft... | 'Univ Heidelberg': Die Ruprecht-Karls..."
        #     which is NOT a correction — it's just two Wikipedia-disambig-defs.
        # New behavior: downgrade to UNCERTAIN (absence-of-evidence ≠
        # evidence-of-absence), put context in evidence + audit_comment,
        # leave correction empty so non-correction-detector isn't tripped
        # and UI doesn't show fake "Korrektur" text.
        return three_witness.WitnessVerdict(
            witness="wiki_graph",
            verdict=three_witness.UNCERTAIN,
            confidence=0.5,
            evidence=(
                f"Wikipedia dokumentiert KEINE direkte Verbindung zwischen "
                f"'{a}' und '{b}'. Das kann bedeuten: (a) die Behauptung ist "
                f"falsch, ODER (b) eine der Entitaeten ist zu wenig "
                f"Wiki-prominent fuer Cross-Mention."
            ),
            correction="",  # empty — wiki-defs are NOT corrections
            audit_comment=(
                f"absence-of-mention != evidence-of-absence — "
                f"wiki_graph kann hier keine Falsifikation belegen, nur "
                f"non-confirmation"
            ),
            recommended_source=wa.get("url") or wb.get("url"),
            sources=[s for s in sources if s][:3],
            latency_ms=(time.time() - t0) * 1000,
        )

    return three_witness.WitnessVerdict(
        witness="wiki_graph",
        verdict=three_witness.UNCERTAIN,
        evidence="kein klares Urteil",
        latency_ms=(time.time() - t0) * 1000,
    )
