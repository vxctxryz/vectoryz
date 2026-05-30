"""DOUBLECHECK pipeline — pre-emit ground-truth verification.

Operator-doctrine 2026-05-20 ([[doublecheck_mandatory_doctrine]]):
*"Wenn fakten gesucht: do always DOUBLECHECK."*

Post-hoc Audit CAB tagging is insufficient because user sees the
halluzination before the correction. Einhorn-Novocain-Spermidin-class
fabrications damage first-impression even when tagged.

This pipeline runs BEFORE the response is "finalized" (= before audit-
done event). If unsupported claims are detected, trigger a rewrite-
retry with strict "use only verified context" discipline.

Strategy:
1. Extract named-entity claim-pairs from the LLM draft
   (X is Y, X invented Z, X discovered Q, X = Y, ...)
2. For each pair, check if both entities appear in the available
   ground-truth context (pre-search-snippets + wiki-wortwolken)
3. If not in context → claim is "unsupported"
4. If any unsupported claim found, drift-mode triggers rewrite

This is a heuristic — won't catch every halluzination, but catches
the catastrophic-class (named-person + fake-attribute, like
Einhorn-discovered-Spermidin).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# Patterns that suggest "X is/was/did/invented/discovered/wrote/composed Y"
# — these are the high-risk fact-attribution claims to verify.
_ATTRIBUTION_VERBS_RX = re.compile(
    r"\b("
    # German present/past, common attribution verbs
    r"ist|war|sind|waren|wurde|wurden|"
    r"entdeckte|entdeckt|erfand|erfunden|synthetisierte|isolierte|"
    r"schuf|geschaffen|komponierte|komponiert|"
    r"schrieb|geschrieben|verfasste|verfasst|"
    r"sang|singt|singen|gesungen|"
    r"spielte|spielt|gespielt|patentierte|patentiert|"
    r"veröffentlichte|veröffentlicht|"
    r"benannte|benannt|"
    r"baute|baut|baute|gebaut|"
    r"führte|führt|führten|"
    # English
    r"is|was|are|were|invented|discovered|wrote|written|composed|"
    r"sang|sung|sing|sings|created|founded|established|developed|"
    r"published|patented|built|named|known"
    r")\b",
    re.IGNORECASE,
)


# Capitalized name extraction (German + English): person-like or
# entity-like terms. Multi-word + single-word.
_NAME_RX = re.compile(
    r"\b([A-ZÄÖÜ][a-zäöüß]{2,}(?:\s+[A-ZÄÖÜ][a-zäöüß]{2,}){0,2})\b"
)


# Words that shouldn't be flagged even if capitalized.
# Includes: articles, conjunctions, common German Nomen (capitalized but generic).
_NAME_STOPWORDS = {
    # articles + pronouns + connectors
    "Der", "Die", "Das", "Ein", "Eine", "Einen", "Einer", "Eines", "Einem",
    "Und", "Oder", "Aber", "Auch", "Wenn", "Als", "Wie", "Was", "Wer", "Wo",
    "Hier", "Dort", "Heute", "Bitte", "Danke", "Hallo",
    "Ich", "Wir", "Sie", "Er", "Es", "Du", "Ihr",
    "The", "And", "Or", "But", "When", "Where", "What", "Which",
    # common German Nomen that are not named entities
    "Begriff", "Name", "Wort", "Idee", "Sache", "Aussage", "Behauptung",
    "Konzept", "Theorie", "Argument", "Beispiel", "Bereich",
    "Stoff", "Substanz", "Verbindung", "Molekül", "Element", "Atom",
    "Hormon", "Vitamin", "Mineral", "Säure", "Base", "Salz", "Öl",
    "Person", "Mann", "Frau", "Kind", "Mensch", "Tier", "Pflanze",
    "Buch", "Seite", "Kapitel", "Text", "Lied", "Song", "Album", "Werk",
    "Roman", "Drama", "Stück", "Film", "Aria", "Arie", "Sinfonie",
    "Symphonie", "Sonate", "Konzert", "Quartett", "Duett", "Trio",
    "Ouvertüre", "Kantate", "Operette", "Tragödie", "Komödie", "Oper",
    "Ballade", "Hymne", "Marsch", "Tanz",
    # geographical-common (Länder + Bundesländer + Bezirke + Regionen)
    "Deutschland", "Österreich", "Schweiz", "Frankreich", "Italien",
    "Polen", "England", "Spanien", "Niederlande", "Belgien", "Dänemark",
    "Schweden", "Norwegen", "Finnland", "Portugal", "Griechenland",
    "Russland", "USA", "China", "Japan", "Indien", "Türkei",
    "Bayern", "Brandenburg", "Bremen", "Hamburg", "Hessen",
    "Niedersachsen", "Saarland", "Sachsen", "Thüringen", "Berlin",
    "Baden", "Württemberg", "Mecklenburg", "Vorpommern", "Rheinland",
    "Pfalz", "Anhalt", "Schleswig", "Holstein", "Nordrhein", "Westfalen",
    "Bundesland", "Land", "Region", "Gegend", "Provinz", "Kanton",
    "Kontinent", "Insel", "Bezirk", "Kreis", "Gemeinde",
    "Zeit", "Jahr", "Tag", "Stunde", "Minute", "Sekunde", "Woche", "Monat",
    "Ort", "Land", "Stadt", "Haus", "Raum", "Gegend",
    "Frage", "Antwort", "Idee", "Gedanke", "Meinung", "Hinweis",
    "Forscher", "Wissenschaftler", "Chemiker", "Physiker", "Biologe",
    # generic body / nature
    "Körper", "Zelle", "Organ", "Gewebe", "Blut", "Knochen",
    "Wasser", "Luft", "Erde", "Feuer",
    # generic German actions/concepts (capitalized as Nomen)
    "Entdeckung", "Erfindung", "Forschung", "Studie", "Untersuchung",
    "Methode", "Verfahren", "Prozess", "Ergebnis", "Befund",
    "Konnotation", "Assoziation", "Bedeutung", "Herkunft",
    "Ansicht", "Ansichten", "Meinung", "Position", "Haltung",
    # German chemistry-suffix common-nouns (the operator's case!)
    "Samenflüssigkeit", "Sperma", "Eizelle",
}


@dataclass
class UnsupportedClaim:
    """One specific claim that the draft makes but isn't supported by context."""
    primary_entity: str            # e.g., "Alfred Einhorn"
    attributed_to: str             # e.g., "Spermidin"
    sentence: str                  # the full sentence containing the claim
    reason: str                    # short audit comment


@dataclass
class DoublecheckResult:
    """Result of running doublecheck on a draft response."""
    has_unsupported: bool = False
    unsupported_claims: list = field(default_factory=list)  # list[UnsupportedClaim]
    checked_entities: list = field(default_factory=list)     # all entities scanned
    context_entities: list = field(default_factory=list)     # entities found in context


def extract_entities(text: str, max_entities: int = 12) -> list:
    """Extract candidate named entities from text. Excludes stopwords."""
    if not text:
        return []
    entities = []
    seen = set()
    for m in _NAME_RX.finditer(text):
        name = m.group(1).strip()
        # Skip if every word is a stopword
        if all(w in _NAME_STOPWORDS for w in name.split()):
            continue
        # Skip if it's just "Der/Die/Das X" at sentence start
        parts = name.split()
        if parts and parts[0] in _NAME_STOPWORDS and len(parts) <= 2:
            # Try the rest
            name = " ".join(parts[1:])
            if not name or name in _NAME_STOPWORDS:
                continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        entities.append(name)
    return entities[:max_entities]


def _split_sentences(text: str) -> list:
    """German sentence-split. Naive but good enough."""
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ])", text.strip())
    return [s.strip() for s in sentences if s.strip()]


def find_attribution_claims(text: str) -> list:
    """Find sentences that contain attribution-verbs (suggesting fact-claims).

    Returns list of (sentence, [entities_in_sentence]) tuples.
    """
    if not text:
        return []
    out = []
    for sent in _split_sentences(text):
        if not _ATTRIBUTION_VERBS_RX.search(sent):
            continue
        entities = extract_entities(sent, max_entities=5)
        if len(entities) >= 1:
            out.append((sent, entities))
    return out


def is_entity_in_context(entity: str, context_text: str) -> bool:
    """Check if entity (or its key tokens) appears in the context-text.

    Uses substring + token-overlap. Case-insensitive.
    Allows partial-match: "Antoni van Leeuwenhoek" matches if just
    "Leeuwenhoek" is in context (last-token fallback).
    """
    if not entity or not context_text:
        return False
    e_lower = entity.lower()
    ctx_lower = context_text.lower()
    # Full match
    if e_lower in ctx_lower:
        return True
    # Token-level: any 4+-char token from the entity that's in context
    tokens = [t.strip(".,;:!?\"'()[]") for t in e_lower.split()]
    significant = [t for t in tokens if len(t) >= 4 and t not in (
        "der", "die", "das", "ein", "eine", "und", "the", "and", "or",
    )]
    if not significant:
        return False
    # Require at least one significant token to be in context
    for t in significant:
        if t in ctx_lower:
            return True
    return False


def _is_likely_proper_name(entity: str) -> bool:
    """Heuristic: is this a proper-name (catastrophe-class candidate)?

    True if:
    - Multi-word capitalized (Antoni van Leeuwenhoek, Alfred Einhorn)
    - Single word NOT in stopwords AND NOT a common German Nomen-suffix

    False if:
    - Single word in stopwords
    - Common German Nomen ending (-keit, -ung, -heit, -schaft, etc.)
    """
    if not entity:
        return False
    parts = entity.split()
    if len(parts) >= 2:
        # Multi-word: high-confidence proper name
        return True
    # Single word
    word = parts[0]
    if word in _NAME_STOPWORDS:
        return False
    # Common German Nomen-endings → likely abstract concept
    common_endings = ("ung", "heit", "keit", "schaft", "tum", "nis",
                      "chen", "lein", "ologie", "graphie", "ismus",
                      "ionen", "ungen", "heiten", "schaften")  # plural forms too
    word_lower = word.lower()
    if any(word_lower.endswith(e) for e in common_endings):
        return False
    return True


def _check_wiki_anchored(entity: str, anchors: list, _wiki_cache: dict) -> bool:
    """Check if Wikipedia documents a connection between entity and any anchor.

    2026-05-20 fix for DOUBLECHECK over-trigger: well-known entities that the
    LLM correctly names (Einstein, Ulm, Goethe, etc.) shouldn't be flagged
    just because pre-search returned poor snippets.

    Returns True (entity is wiki-anchored) if:
      - Wikipedia(entity) extract mentions any anchor by name OR
      - Wikipedia(anchor) extract mentions entity by name

    Catastrophe-class (Einhorn-Spermidin) still fails this check because
    Wikipedia(Einhorn) talks about Novocain, not Spermidin, AND
    Wikipedia(Spermidin) doesn't mention Einhorn.

    The _wiki_cache dict is the per-request cache (avoids re-fetching same
    Wikipedia page within one doublecheck pass).
    """
    if not entity or not anchors:
        return False
    try:
        from wrapper_v2.pipeline import wiki_wortwolke as _ww
    except Exception:
        return False

    def _get(term):
        if term in _wiki_cache:
            return _wiki_cache[term]
        result = _ww.fetch_wiki_summary(term, timeout=5.0)
        _wiki_cache[term] = result
        return result

    # Direction 1: Wikipedia(entity) mentions any anchor
    wiki_e = _get(entity)
    if wiki_e and not wiki_e.get("is_disambig"):
        extract = (wiki_e.get("extract") or "").lower()
        for anchor in anchors:
            a_low = anchor.lower()
            if a_low in extract:
                return True
            # Token-level fallback: all anchor-tokens (4+ chars) in extract
            tokens = [t for t in a_low.split() if len(t) >= 4]
            if tokens and all(t in extract for t in tokens):
                return True

    # Direction 2: Wikipedia(any anchor) mentions entity
    for anchor in anchors:
        wiki_a = _get(anchor)
        if wiki_a and not wiki_a.get("is_disambig"):
            extract = (wiki_a.get("extract") or "").lower()
            e_low = entity.lower()
            if e_low in extract:
                return True
            tokens = [t for t in e_low.split() if len(t) >= 4]
            if tokens and all(t in extract for t in tokens):
                return True

    return False


def doublecheck_draft(draft: str, context_text: str,
                       user_query: Optional[str] = None) -> DoublecheckResult:
    """Run doublecheck on a draft response — focus on catastrophe-class.

    Catastrophe-class = named-person attribution that's NOT in ground-truth
    AND not documented in Wikipedia as a real connection to the user-query
    anchor.

    2026-05-20 AUTHORITY-SPLIT UNBUNDLING ([[authority_split_doctrine]] +
    [[baal_whipper_doctrine]]): the `context_text` parameter is now IGNORED.
    Reason: pre-search-context IS the labby's scent-trail (guidance-layer).
    If we use it as ground-truth for the audit-layer, the audit becomes
    Baal-whipper — confirms the labby instead of independently verifying.
    DOUBLECHECK must run on INDEPENDENT sources only:
      - user_query (operator's explicit mention is always allowed)
      - Wikipedia-direct-fetch via wiki_wortwolke (independent ground-truth)

    Single-word common-nouns (Begriff, Samenflüssigkeit, Hormon) are
    skipped — they're not catastrophe-class even if not in context.

    Callers may still pass context_text for backwards-compatibility; the
    parameter is silently dropped from the truth-pool. To re-enable, the
    operator must explicitly opt out of authority-split discipline.
    """
    if not draft or not draft.strip():
        return DoublecheckResult()

    # 2026-05-20 authority-split: context_text is INTENTIONALLY EXCLUDED from
    # the allow-list. Pre-search-context belongs to the guidance-layer, not
    # the audit-layer. Witnesses must work independently. Per
    # [[baal_whipper_doctrine]]: "the verifiers must not share the
    # producer's leash".
    _ = context_text  # silently dropped (kept in signature for back-compat)
    allow_text = (user_query or "")

    # Extract anchors from user-query — these are the user-named entities
    # that the LLM's answer SHOULD reference. Used for wiki-graph-anchoring.
    user_anchors = extract_entities(user_query or "", max_entities=4)
    # Per-request wiki-fetch cache so multiple sentences don't re-fetch
    _wiki_cache: dict = {}

    claims = find_attribution_claims(draft)
    unsupported = []
    all_entities = []
    context_entities = []

    for sent, ents in claims:
        # Filter to likely-proper-names only — skip common-nouns
        proper_names = [e for e in ents if _is_likely_proper_name(e)]
        all_entities.extend(proper_names)
        if not proper_names:
            continue
        unsupp_in_sent = [e for e in proper_names if not is_entity_in_context(e, allow_text)]
        if not unsupp_in_sent:
            context_entities.extend(proper_names)
            continue
        # 2026-05-20 wiki-augmentation: for each unsupported entity, check
        # if Wikipedia documents a connection to any user-query anchor.
        # If yes → auto-anchored (well-known entity, LLM is allowed to use it).
        # If no → keep flagged (true unsupported attribution).
        still_unsupp = []
        for entity in unsupp_in_sent:
            if user_anchors and _check_wiki_anchored(entity, user_anchors, _wiki_cache):
                # Wiki documents connection — auto-anchored
                context_entities.append(entity)
                continue
            still_unsupp.append(entity)

        for primary in still_unsupp:
            others = [e for e in ents if e != primary]
            attributed_to = others[0] if others else "(self-claim)"
            unsupported.append(UnsupportedClaim(
                primary_entity=primary,
                attributed_to=attributed_to,
                sentence=sent[:300],
                reason=(
                    f"Proper-Name '{primary}' weder in pre-search/wiki-"
                    f"context NOCH Wikipedia-verknüpft zu User-Anker — "
                    f"Attribut-Behauptung ohne Beleg"
                ),
            ))

    return DoublecheckResult(
        has_unsupported=bool(unsupported),
        unsupported_claims=unsupported,
        checked_entities=all_entities,
        context_entities=context_entities,
    )


def build_doublecheck_summary(result: DoublecheckResult) -> dict:
    """Format DoublecheckResult as SSE-emit-ready dict."""
    return {
        "type": "doublecheck_result",
        "has_unsupported": result.has_unsupported,
        "unsupported_count": len(result.unsupported_claims),
        "unsupported": [
            {
                "primary_entity": c.primary_entity,
                "attributed_to": c.attributed_to,
                "sentence": c.sentence,
                "reason": c.reason,
            }
            for c in result.unsupported_claims
        ],
        "checked_count": len(result.checked_entities),
        "anchored_count": len(result.context_entities),
    }


def build_doublecheck_corrective(unsupported_claims: list) -> str:
    """Build a corrective system-msg for the rewrite-retry."""
    if not unsupported_claims:
        return ""
    lines = [
        "DOUBLECHECK-VERSTOSS — die vorige Antwort enthielt Behauptungen "
        "die NICHT im Such-Kontext belegt sind:",
    ]
    for c in unsupported_claims[:5]:  # cap at 5
        lines.append(
            f"  - '{c.primary_entity}' verknüpft mit '{c.attributed_to}': "
            f"'{c.sentence[:120]}...'"
        )
    lines.extend([
        "",
        "REGEL: In der neuen Antwort darfst du AUSSCHLIESSLICH Entitaeten + "
        "Verknuepfungen erwaehnen, die im pre-search-Block / wiki-wortwolke / "
        "user-query selbst vorkommen. Wenn dein Wissen nicht ausreicht: "
        "ehrlich sagen ('ich kann das aus den Quellen nicht belegen') statt "
        "Namen / Ereignisse / Verbindungen zu erfinden.",
        "",
        "Beispiel-Verstoss: Wenn der Kontext sagt 'Spermidin = Polyamin von "
        "Leeuwenhoek 1678' und du erfindest 'Spermidin wurde von Alfred "
        "Einhorn entdeckt' — das ist Halluzination. Bleib bei Leeuwenhoek.",
    ])
    return "\n".join(lines)
