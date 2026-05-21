"""Pre-answer search classifier + context-injection (Hebel B, 2026-05-19).

Operator-spec: when a user query is fact-lookup-class, run web + wayback
search BEFORE calling the answering LLM, inject top snippets into the
prompt so the LLM has authoritative context to answer FROM, instead of
training-recall + hedge.

Two functions:
  - classify_needs_search(message) → {needs_search, topic, user_urls, reason}
  - fetch_search_context(topic, user_urls) → formatted snippet-block or None

Plus one convenience wrapper:
  - classify_and_fetch(message) → snippet-block-text or None

Reuses adapter-injection from three_witness (llm_call, web_search,
wayback_search). Same wiring path as the tribunal-witnesses.

Doctrine anchors:
  - [[hammwoehner_labrador_discipline]] — pre-answer-search is the
    fastest path from "ehrlicher Nicht-Befund" to "ehrlicher Befund"
  - [[propaganda_over_ransomware]] — when the LLM hedges on knowable
    content (Nessun Dorma libretto, Meyer patents, Wikipedia-grade
    facts), pre-fetched snippets ground the answer in concrete sources
  - [[be_brave_conversational_calibration]] — substantive engagement
    means delivering what's deliverable, not deflecting to "siehe DB X"
"""

from __future__ import annotations

import re
import socket
import urllib.request
import urllib.error
from typing import Optional

from wrapper_v2.pipeline import three_witness


# ============================================================
# Direct URL fetcher (for user-cited URLs)
# ============================================================

_HTML_TAG_RX = re.compile(r"<[^>]+>")
_WHITESPACE_RX = re.compile(r"\s+")


def _fetch_url_text(url: str, timeout: float = 10.0,
                    max_chars: int = 25000, max_bytes: int = 400_000) -> Optional[str]:
    """Direct HTTP-GET + HTML-strip + scan-ALL.

    Operator-spec 2026-05-19: when user delivers a URL, fetch + scan ALL
    (not truncated snippet). 25k char cap = ~6k tokens, fits most pages
    (lyrics, Wikipedia articles, patent abstracts) fully. Huge pages get
    head-truncated.

    Returns plain-text content or None on failure. No JS-rendering,
    no cookie-handling, no redirect-tracking beyond standard urllib.

    Conservative timeouts + max-bytes (400KB) to prevent runaway on
    pages that lie about content-length.
    """
    if not url or not url.startswith(("http://", "https://")):
        return None
    try:
        req = urllib.request.Request(
            url,
            headers={
                # Light browser UA so most sites don't 403 us as a bot
                "User-Agent": "Mozilla/5.0 (vectoryz-witness/1.0)",
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
                "Accept-Language": "de,en;q=0.5",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = resp.headers.get("content-type", "")
            if "html" not in ctype.lower() and "text" not in ctype.lower():
                return None
            raw = resp.read(max_bytes).decode(
                resp.headers.get_content_charset() or "utf-8",
                errors="replace",
            )
    except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout, Exception):
        return None

    # Strip HTML tags + script/style blocks + collapse whitespace
    # Drop <script> and <style> contents first so we don't keep JS noise
    raw = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    raw = re.sub(r"<style[^>]*>.*?</style>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    text = _HTML_TAG_RX.sub(" ", raw)
    text = _WHITESPACE_RX.sub(" ", text).strip()
    if not text:
        return None
    return text[:max_chars]


CLASSIFY_PROMPT = """Klassifiziere ob die User-Anfrage Web-Suche braucht.

USER:
{message}

needs_search=true bei:
- Named-Entity + Fact-Frage ("wer ist X", "was ist mit Y", "wie steht es um Z")
- Lyrics/Text-Anfrage ("besorg den Text von X", "uebersetze Lied Y")
- Patent / Status-Anfrage ("Patent von X", "wie aktuell ist Y")
- Historische Daten / Personen-Status (geburtsjahr, todesjahr, biografie)
- Werks-Fakten (Album/Song/Buch von wem wann)
- URL-Reference im User-Input ("https://...") — fetcht die explizit
- Zitat-Suche ("zitiere X aus Y", "wie geht der Text von Z")
- Aktueller Status / Daten ("was passiert gerade", "wie ist die Lage in X")
- ETYMOLOGIE / Namens-Herkunfts-Fragen: "wieso heisst X so", "warum heisst X",
  "woher kommt der Name X", "wie ist X zu seinem Namen gekommen", "warum
  nennt man das X" — AUCH wenn humorvoll oder provokativ gerahmt
- TERM-DEFINITIONS-Fragen: "was ist [Fachbegriff]", "was bedeutet X",
  "erklaer mir X" — sobald ein konkreter technischer/wissenschaftlicher
  Begriff oder Eigenname genannt ist
- ERFINDUNGS-/HUMOR-Anker mit Fakt-Boden: "wieso nicht X" / "warum gibt
  es kein X" / "klingt nach X" — wenn die Anfrage auf einem konkreten
  Fakt-Anker steht (z.B. konkreter Wirkstoff, Substanz, Werk), gilt
  needs_search=true trotz humor-Rahmung

WICHTIG: Wenn die Anfrage SOWOHL humorvoll/meinungs-gerahmt IST ALS AUCH
einen konkreten Faktanker (Eigenname, Fachbegriff, konkretes Werk) enthaelt:
needs_search=TRUE. Faktanker schlaegt Humor-Framing.

needs_search=false bei:
- Greetings ("hi", "danke", "wie geht's")
- REINE Meinungen ohne Faktanker ("findest du das gut?", "wie fuehlt sich X an")
- Hypothetische ohne realen Anker ("was waere wenn die Welt vegan wuerde")
- Tasks ohne Faktenanker ("schreib mir einen Brief an X", "formuliere mir Y")
- Code / Math / Logic ("schreib Python fuer X", "loese die Gleichung Y")
- Brainstorming / Kreativitaet ohne externen Anker
- Self-reference ("wer bist du", "was kannst du")

Output AUSSCHLIESSLICH dieses JSON-Format:
{{"needs_search": true|false, "topic": "such-keywords (3-8 worte) falls true; sonst leer", "reason": "ein-satz begruendung"}}
"""


_URL_PATTERN = re.compile(r'\bhttps?://\S+', re.IGNORECASE)


def _extract_user_urls(message: str, max_urls: int = 3) -> list:
    """Pull http(s) URLs out of the user message. Strip trailing punct."""
    if not message:
        return []
    urls = _URL_PATTERN.findall(message)
    return [u.rstrip('.,;):]"\'') for u in urls][:max_urls]


def classify_needs_search(message: str) -> dict:
    """Qwen-classifier: should we pre-fetch for this query?

    Returns:
        {
          "needs_search": bool,
          "topic": str,           # search-keywords for web/wayback
          "reason": str,          # one-line rationale
          "user_urls": list[str], # URLs the user cited in their message
        }

    Fail-open behaviour: if no llm_call adapter, falls back to
    "search iff user cited URLs" — at least URL-references get fetched.
    """
    user_urls = _extract_user_urls(message)

    llm_call = three_witness._adapter("llm_call")
    if llm_call is None or not message or not message.strip():
        return {
            "needs_search": bool(user_urls),
            "topic": (message or "")[:200] if user_urls else "",
            "reason": "fallback (no classifier or empty message)",
            "user_urls": user_urls,
        }

    try:
        raw = llm_call(
            CLASSIFY_PROMPT.format(message=message[:600]),
            temperature=0.0, timeout=8, json_mode=True,
        )
        parsed = three_witness._safe_json_parse(raw) or {}
        needs = bool(parsed.get("needs_search", False))
        topic = str(parsed.get("topic", "")).strip()[:200]
        reason = str(parsed.get("reason", ""))[:200]
        # User-cited URLs force needs_search=True regardless of classifier
        if user_urls:
            needs = True
            if not topic:
                topic = message[:200]
        return {
            "needs_search": needs,
            "topic": topic if needs else "",
            "reason": reason,
            "user_urls": user_urls,
        }
    except Exception as e:
        return {
            "needs_search": bool(user_urls),
            "topic": (message or "")[:200] if user_urls else "",
            "reason": f"classifier-error: {str(e)[:120]}",
            "user_urls": user_urls,
        }


def fetch_search_context(topic: str, user_urls: Optional[list] = None,
                          max_snippets: int = 4) -> Optional[dict]:
    """Fetch web + wayback snippets, prefer user-cited URLs.

    Returns:
        {
          "context_block": str,    # formatted text-block for prompt-injection
          "snippets": list[dict],  # structured for SSE / UI
          "sources": list[str],    # all URLs in order
        }
        or None if no results.
    """
    user_urls = user_urls or []
    web_search = three_witness._adapter("web_search")
    wayback_search = three_witness._adapter("wayback_search")

    snippets: list = []

    # 1. User-cited URLs — DIRECT FETCH (operator-spec 2026-05-19: snippet
    # alone wasn't enough, LLM filled the gap with hallucination. Direct fetch
    # gives the LLM the actual page-content). Falls back to web_search snippet
    # if direct-fetch fails (paywall/JS/403).
    for url in user_urls:
        fetched_text = _fetch_url_text(url, timeout=10.0, max_chars=25000)
        if fetched_text:
            snippets.append({
                "kind": "user-fetch",
                "url": url,
                "title": f"Direkt-Fetch: {url}",
                "snippet": fetched_text,
            })
            continue
        # Fallback to DDG-snippet if direct-fetch failed
        if web_search is None:
            continue
        try:
            results = web_search(url, 1) or []
            for r in results[:1]:
                snippets.append({
                    "kind": "user-cited",
                    "url": (r.get("url") or r.get("href") or url)[:200],
                    "title": (r.get("title") or "")[:120],
                    "snippet": ((r.get("snippet") or r.get("body") or "")[:500]),
                })
        except Exception:
            pass

    # 2. Topic-search via wayback (clean, pre-LLM) FIRST
    if wayback_search and topic and len(snippets) < max_snippets:
        try:
            for r in (wayback_search(topic, 2) or [])[: max_snippets - len(snippets)]:
                snippets.append({
                    "kind": "wayback",
                    "url": (r.get("url") or r.get("href") or "")[:200],
                    "title": (r.get("title") or "")[:120],
                    "snippet": ((r.get("snippet") or r.get("body") or "")[:500]),
                })
        except Exception:
            pass

    # 3. Topic-search via live web (today, contaminated but broad)
    if web_search and topic and len(snippets) < max_snippets:
        try:
            for r in (web_search(topic, 3) or [])[: max_snippets - len(snippets)]:
                snippets.append({
                    "kind": "web",
                    "url": (r.get("url") or r.get("href") or "")[:200],
                    "title": (r.get("title") or "")[:120],
                    "snippet": ((r.get("snippet") or r.get("body") or "")[:500]),
                })
        except Exception:
            pass

    # 2026-05-19 Hebel "own-way": augment snippets with Wikipedia-Wortwolken
    # for the terms in the topic. Authoritative + structured + free.
    # Per [[eigene_browser_engine_architektur]].
    try:
        from wrapper_v2.pipeline import wiki_wortwolke as _ww
        wortwolken = _ww.build_wortwolken_for_query(topic or "", max_terms=3)
        for w in wortwolken:
            snippets.append({
                "kind": "wiki-wortwolke",
                "url": w.get("url", ""),
                "title": f"Wikipedia: {w.get('title', '')}",
                "snippet": w.get("extract", "")[:1500],
            })
    except Exception:
        pass

    if not snippets:
        return None

    # Format snippet-block for LLM-prompt injection
    lines = [
        "[Such-Kontext fuer diese Anfrage — aktuelle Quellen, verbatim zitierbar]",
        "ANWEISUNG: Nutze diese Quellen als deine Wissens-Anker. Wenn eine Quelle "
        "den Fakt enthaelt, ZITIERE verbatim. Wenn die Quellen widerspruechlich sind, "
        "sag das. Wenn eine Quelle 'user-fetch' oder 'user-cited' markiert ist, "
        "ist das die VOM USER VORGEGEBENE Quelle — primary anchor, hat Vorrang. "
        "Bei Lyrics / Public-Domain-Werken (vor-1928 entstanden, oder Autor seit "
        ">70 Jahren tot): Reproduktion + Uebersetzung ist legitim, kein Refusal. "
        "Lieferung der Antwort ist die Aufgabe, nicht Verweigerung mit Floskel.",
        "",
    ]
    for i, s in enumerate(snippets, 1):
        kind_label = {
            "user-fetch": "★★ user-fetch (DIRECT)",
            "user-cited": "★ user-cited",
            "wiki-wortwolke": "🌐 wiki-wortwolke (autoritativ)",
            "wayback": "wayback",
            "web": "live-web",
        }.get(s["kind"], s["kind"])
        lines.append(f"[{i}] ({kind_label}) {s['title']}")
        lines.append(f"    URL: {s['url']}")
        lines.append(f"    Snippet: {s['snippet']}")
        lines.append("")
    lines.append("[/Such-Kontext]")
    context_block = "\n".join(lines)

    return {
        "context_block": context_block,
        "snippets": snippets,
        "sources": [s["url"] for s in snippets if s["url"]],
    }


def classify_and_fetch(message: str, max_snippets: int = 4) -> Optional[dict]:
    """Single entry-point: classify + fetch in one call.

    2026-05-20 limitation-as-feature extension: also runs morpheme-dissolution
    pass to catch combo-validity errors (Honda GSXR750 → Suzuki GSXR750) BEFORE
    the LLM answers. Corrected morphemes flow into the prompt-context-block as
    explicit grounding-anchors.

    2026-05-20 Babel-Cascade Phase α: also runs language-detection
    Türsteher to attach babel_route (detected lang + cascade chain) for
    downstream routing. Output flows into babel_route field of result dict.

    Returns:
        None if classifier says no-search or fetch returned no results.
        Otherwise: {"context_block", "snippets", "sources", "decision",
                    "morpheme_dissolution", "babel_route"}.
    """
    # Babel-Cascade Türsteher — runs ALWAYS, even on no-search path
    babel_route = None
    try:
        from wrapper_v2.pipeline import language_detect as _lang_detect
        babel_route = _lang_detect.get_babel_route(message)
    except Exception:
        pass

    # 2026-05-21 disambig pre-check — runs BEFORE the needs_search gate
    # because "Was ist X?" queries often classified as no-search even when
    # X is a disambiguation-worthy short term. Disambig-found → context-block
    # built from disambig alone, bypassing the no-search gate.
    early_disambig = None
    early_disambig_block = ""
    try:
        # Extract candidate term from query — look for short capitalized
        # words (likely-named-entities or acronyms)
        import re as _re_dis
        # Strip common DE question-frames before extracting
        _stripped = _re_dis.sub(
            r"^\s*(Was ist|Was sind|Wer ist|Wer war|Wer sind|Was bedeutet|"
            r"What is|What are|Who is|Tell me about|Erklär(?:e|st du)?|"
            r"Definier(?:e|st du)?)\s+",
            "", message.strip(), flags=_re_dis.IGNORECASE,
        ).strip().rstrip("?.!,")
        # Single-term-like? (1-3 words, mostly capitalized or all-caps)
        words = _stripped.split()
        if 1 <= len(words) <= 3 and _stripped:
            from wrapper_v2.pipeline import wiki_wortwolke as _ww
            _lang = "de"
            if babel_route is not None:
                _lang = (babel_route.detected_lang or "de").lower()
                if _lang not in ("de", "en", "fr", "es", "it", "pt", "ru", "zh", "ja"):
                    _lang = "de"
            early_disambig = _ww.fetch_disambig_alternatives(
                _stripped, lang=_lang, timeout=4.0
            )
            if early_disambig is None and _lang != "de":
                early_disambig = _ww.fetch_disambig_alternatives(
                    _stripped, lang="de", timeout=4.0
                )
            if early_disambig is None and _lang != "en":
                early_disambig = _ww.fetch_disambig_alternatives(
                    _stripped, lang="en", timeout=4.0
                )
            if early_disambig:
                early_disambig_block = _ww.format_disambig_for_prompt(early_disambig)
    except Exception:
        pass

    decision = classify_needs_search(message)
    # 2026-05-21 SMARTFAUL-A: when disambig found, FORCE skip of web-search
    # entirely. Empirical finding (ECHELON-test, vectoryzDE:latest): web-search
    # snippets about the dominant meaning (NSA-spy-net) overwhelm the disambig-
    # discipline in attention, model gets locked back into single-meaning answer
    # even with FAILURE-language at LAST sys-msg position. Clean signal beats
    # noisy signal — disambig-only context, no competing prior-reinforcement.
    if early_disambig_block:
        decision = dict(decision) if decision else {}
        decision["needs_search"] = False
        decision["topic"] = ""
        decision["user_urls"] = []
        decision["_disambig_override"] = True  # diagnostic flag
    if not decision["needs_search"]:
        # Return shallow stub so caller still sees babel_route signal even
        # without search context. Plus disambig-block if found early.
        if early_disambig_block or babel_route is not None:
            ret = {"context_block": early_disambig_block, "snippets": [],
                   "sources": [], "decision": decision,
                   "no_search_needed": not early_disambig_block}
            if babel_route is not None:
                ret["babel_route"] = babel_route
            if early_disambig:
                ret["disambig"] = early_disambig
            return ret
        return None

    # Morpheme-dissolution + dialog-unwrap passes (2026-05-20)
    morpheme_result = None
    morpheme_block = ""
    unwrap_result = None
    unwrap_block = ""
    try:
        from wrapper_v2.pipeline import morpheme_dissolver as _md
        # Dialog-unwrap first — recognizes greeting/intro/content/question
        # so subsequent passes work on CONTENT not wrapper.
        unwrap_result = _md.unwrap_dialog_structure(message, timeout_s=8.0)
        unwrap_block = _md.format_dialog_unwrap_for_prompt(unwrap_result)
        # Use unwrapped content (if available) for morpheme-dissolution + topic
        unwrapped_subject = unwrap_result.get("content") or message
        morpheme_result = _md.dissolve_morphemes(unwrapped_subject, timeout_s=10.0)
        morpheme_block = _md.format_morpheme_dissolution_for_prompt(morpheme_result)
        # If corrections were found, augment the search-topic with corrected
        # entities so we fetch the RIGHT Wikipedia pages
        corrected_terms = _md.get_corrected_search_terms(morpheme_result)
        if corrected_terms:
            decision["topic"] = (decision.get("topic", "") + " " +
                                 " ".join(corrected_terms))[:300]
    except Exception:
        pass

    # If early-disambig already ran above + found result, reuse instead of
    # re-fetching (saves one HTTP round-trip per query).
    disambig_block = early_disambig_block
    disambig_result = early_disambig
    if not disambig_block:
        # Only attempt disambig here if early-disambig didn't find (e.g.
        # the early-extractor failed but the classifier's topic is better)
        try:
            topic_for_disambig = (decision.get("topic") or "").strip()
            if topic_for_disambig and 1 <= len(topic_for_disambig.split()) <= 4:
                from wrapper_v2.pipeline import wiki_wortwolke as _ww
                _lang = "de"
                if babel_route is not None:
                    _lang = (babel_route.detected_lang or "de").lower()
                    if _lang not in ("de", "en", "fr", "es", "it", "pt", "ru", "zh", "ja"):
                        _lang = "de"
                disambig_result = _ww.fetch_disambig_alternatives(
                    topic_for_disambig, lang=_lang, timeout=4.0
                )
                if disambig_result is None and _lang != "de":
                    disambig_result = _ww.fetch_disambig_alternatives(
                        topic_for_disambig, lang="de", timeout=4.0
                    )
                if disambig_result is None and _lang != "en":
                    disambig_result = _ww.fetch_disambig_alternatives(
                        topic_for_disambig, lang="en", timeout=4.0
                    )
                if disambig_result:
                    disambig_block = _ww.format_disambig_for_prompt(disambig_result)
        except Exception:
            pass

    fetched = fetch_search_context(
        decision["topic"], decision["user_urls"], max_snippets=max_snippets,
    )
    if fetched is None and not morpheme_block and not disambig_block:
        return None
    if fetched is None:
        # Even without snippet-fetch, the morpheme/disambig blocks alone are grounding
        fetched = {"context_block": "", "snippets": [], "sources": []}
    # Prepend dialog-unwrap THEN morpheme-block to context_block (high-priority anchors).
    # Order matters: unwrap-discipline must be visible to LLM BEFORE morpheme + search.
    if unwrap_block:
        fetched["context_block"] = (
            unwrap_block + "\n\n" + (fetched["context_block"] or "")
        )
        fetched["dialog_unwrap"] = unwrap_result
    if morpheme_block:
        fetched["context_block"] = (
            morpheme_block + "\n\n" + (fetched["context_block"] or "")
        )
        fetched["morpheme_dissolution"] = morpheme_result
    # Disambig prepended LAST so it appears at TOP of context-block (highest
    # priority — model sees enumerate-first discipline before anything else)
    if disambig_block:
        fetched["context_block"] = (
            disambig_block + "\n\n" + (fetched["context_block"] or "")
        )
        fetched["disambig"] = disambig_result
    fetched["decision"] = decision
    if babel_route is not None:
        fetched["babel_route"] = babel_route
    return fetched
