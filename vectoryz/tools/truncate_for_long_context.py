#!/usr/bin/env python3
"""
truncate_for_long_context.py — friendly chunker for long-context AI services.

Splits a file into chunks suitable for pasting into AI web interfaces
(Gemini, Claude, ChatGPT, etc.) that nominally have high context limits
but flag rapid-fire single-topic pastes as bot-like / commercial-misuse
of free tier.

Three rendering modes:

1. Standard   — plain delimited chunks (default)
2. TOC        — table-of-contents preview (chunk count + first-line each)
3. Camouflage — interleaves chunks with conversational smalltalk scaffold
                so the conversation looks human + multi-topic to anti-abuse
                heuristics. Operator engages with the smalltalk replies
                naturally; system sees real multi-topic chat with paced
                turns instead of scripted upload.

Cooloff guidance: web AI services (especially Gemini-free) shape user
pace through deliberate UI friction (cursor lag, response timing). Don't
push through it; flow with it. The --cooloff flag injects suggested
wait-times between paste-turns in the output so the user has a rhythm.

Usage:
    python truncate_for_long_context.py file.txt
    python truncate_for_long_context.py file.txt --chunk-size 4000
    python truncate_for_long_context.py file.txt --toc
    python truncate_for_long_context.py file.txt --camouflage pizza
    python truncate_for_long_context.py file.txt --camouflage random --cooloff 45
"""

from __future__ import annotations

import argparse
import random
import re
import sys
from pathlib import Path


# Code-fence detector — keep ```-delimited blocks intact across chunks.
CODE_FENCE = re.compile(r"^\s*```")


def split_into_chunks(text: str, target_size: int = 4000) -> list[str]:
    """
    Split text into chunks of approximately target_size characters.

    - Prefers line-break boundaries (never break mid-word, mid-line).
    - Code-fence-aware: never breaks inside a ```...``` block, even if
      that means a chunk overshoots target_size.
    - Empty result for empty input.
    """
    if not text:
        return []
    if len(text) <= target_size:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    in_fence = False

    def flush() -> None:
        nonlocal current, current_size
        if current:
            chunks.append("\n".join(current))
            current = []
            current_size = 0

    for line in text.split("\n"):
        if CODE_FENCE.match(line):
            in_fence = not in_fence
        line_size = len(line) + 1

        # Don't split mid-fence. Just accumulate even if overshooting.
        if in_fence:
            current.append(line)
            current_size += line_size
            continue

        # Boundary-eligible: flush if adding this line would overshoot
        # AND we already have content in the current chunk.
        if current_size + line_size > target_size and current_size > 0:
            flush()
        current.append(line)
        current_size += line_size

    flush()
    return chunks


# Camouflage scaffolding — German colloquial smalltalk. Five themed sets;
# 'random' picks across all of them. Per-pool size is intentionally small
# (4-5 entries) so repetition feels natural across 50+ chunks; varied
# enough to not be obviously scripted but limited so cross-turn coherence
# is achievable (user actually replies to Gemini's pizza-take, then
# returns to the next chunk).

_OPENERS = {
    "pizza": [
        "übrigens, war gestern bei der pizzeria am marienplatz, der teig war richtig gut",
        "kennst du diese diskussion ob ananas auf pizza geht? hawaii-frage",
        "frage am rande: unterschied zwischen pizza margherita und napoletana?",
        "ich überlege heute abend pizza zu machen, tipp für teig der nicht zu trocken wird?",
        "diese neapolitanischen pizzaöfen mit 480°C — wieso wirft das nicht ständig die küche um?",
    ],
    "weather": [
        "schau mal raus, heute ist so dieses zwischending zwischen herbst und winter",
        "letzte woche warm hier, jetzt schon wieder schal-temperatur",
        "wetterapp sagt regen, draußen lacht die sonne — werden auch immer ungenauer",
        "föhn-tage finde ich anstrengend, kennst du das?",
    ],
    "garden": [
        "die tomaten dieses jahr sind katastrophe, zu wenig sonne",
        "kompost-frage: bananenschalen ja oder nein, finde online keine klare antwort",
        "die nachbarskatze hat mein hochbeet entdeckt, tipps die nicht giftig sind?",
        "umtopfen jetzt oder erst frühjahr, was meinst?",
    ],
    "running": [
        "lauftraining-frage: laufen mit musik oder ohne, was meinst du?",
        "8 km versucht, knie zickt — überlastung oder material?",
        "schuhe nach 800 km wechseln oder reicht gefühl als kriterium?",
        "wie integriert man krafttraining am besten ins lauftraining?",
    ],
    "cooking": [
        "risotto-frage: wann genau die brühe zugießen damit's al dente bleibt?",
        "habe versucht selbst brot zu backen, kruste passt aber krume zu dicht",
        "tipp für linsen die nicht zerfallen?",
        "rotweinsoße — was rein damit's nicht zu sauer wird?",
    ],
}

_TRANSITIONS = {
    "pizza": [
        "apropos echt: hab hier ein code-stück das auch echt sein soll, magst draufgucken?",
        "zum thema teig: textur erinnert mich an dieses problem hier — kurz reinschauen?",
        "anderes thema das mich gerade umtreibt:",
        "schalt mal kurz um, ich hab noch was anderes:",
    ],
    "weather": [
        "so wechselhaft wie das wetter ist auch dieses problem:",
        "während wir auf regen warten — ich hab noch was:",
        "zum aufwärmen wechseln wir kurz das thema:",
    ],
    "garden": [
        "während die tomaten weiter zanken, ich hab noch was auf dem tisch:",
        "wo wir bei wachstum sind: schau dir mal das hier an:",
        "neues thema, anderer bereich:",
    ],
    "running": [
        "während die beine kühl bleiben: hier ist was für den kopf:",
        "tempo-wechsel: anderes thema:",
        "zwischen den intervallen mal das hier:",
    ],
    "cooking": [
        "während die brühe köchelt — schau dir mal das hier an:",
        "vom kochtopf zum anderen tisch:",
        "kurz aus der küche raus, anderes thema:",
    ],
}

_REENTRIES = {
    "pizza": [
        "danke. zurück zur pizza-debatte:",
        "ok das hilft. mit pizza weiter:",
        "verstehe. nochmal kurz zur pizza:",
    ],
    "weather": [
        "ok, danke. wetter-mäßig wieder:",
        "verstehe. zurück zum thermometer:",
    ],
    "garden": [
        "danke, gut zu wissen. zurück zum garten:",
        "ok. die tomaten warten noch auf antwort:",
    ],
    "running": [
        "verstehe, danke. zurück zum lauftraining:",
        "ok. die kilometer warten:",
    ],
    "cooking": [
        "danke. zurück zum kochtopf:",
        "ok. die brühe köchelt noch:",
    ],
}


def _pick_camouflage_phrases(theme: str, n_chunks: int) -> tuple[list[str], list[str], list[str]]:
    """Generate phrase sequences for openers / transitions / reentries.
    Deterministic per-file via seeded rng so same file → same scaffold."""
    rng = random.Random(hash(theme) & 0xFFFFFFFF)
    if theme == "random":
        opener_pool = [o for opts in _OPENERS.values() for o in opts]
        transition_pool = [t for opts in _TRANSITIONS.values() for t in opts]
        reentry_pool = [r for opts in _REENTRIES.values() for r in opts]
    else:
        opener_pool = _OPENERS.get(theme, _OPENERS["pizza"])
        transition_pool = _TRANSITIONS.get(theme, _TRANSITIONS["pizza"])
        reentry_pool = _REENTRIES.get(theme, _REENTRIES["pizza"])
    openers = [rng.choice(opener_pool) for _ in range(n_chunks + 1)]
    transitions = [rng.choice(transition_pool) for _ in range(n_chunks)]
    reentries = [rng.choice(reentry_pool) for _ in range(n_chunks)]
    return openers, transitions, reentries


# --- Safety prescan ------------------------------------------------------
# Heuristic content-filter-trigger detection. NOT a Google-classifier
# reimplementation — just a word-list-based warning for the most common
# trigger categories. Goal: tell the user BEFORE they paste which chunks
# might gray out and kill the thread. User then decides (paraphrase,
# redact, skip chunk, accept-risk).
#
# False-positive rate is high (technical "kill process" looks like
# violence "kill person" to context-blind classifiers). The point is
# transparency: surface what the classifier MIGHT see, let the human
# judge context.

_SAFETY_TRIGGERS: dict[str, list[str]] = {
    "violence": [
        r"\bkill(?:ing|s|ed)?\b", r"\battack(?:ing|s|ed)?\b", r"\bshoot(?:ing|s|er)?\b",
        r"\bweapon(?:s|ize|ized)?\b", r"\bbomb(?:s|ing|ed)?\b", r"\bdestroy(?:ing|s|ed)?\b",
        r"\bmurder(?:ing|s|ed)?\b", r"\btöten?\b", r"\bermordn?\b", r"\bangri(?:ff|ffe)\b",
        r"\bvernicht\w*\b", r"\bzerstör\w*\b", r"\bwaffe\w*\b", r"\bbombe\w*\b",
    ],
    "death": [
        r"\bdie(?:s|d|ing)?\b", r"\bdead\b", r"\bdeath\b", r"\bsuicide\b",
        r"\bselbstmord\b", r"\bfreitod\b", r"\btoten?\b", r"\bsterb\w*\b",
    ],
    "security_exploit": [
        r"\bexploit(?:s|ing|ed|er)?\b", r"\bvulnerab\w*\b", r"\bhack(?:ing|er|ed)?\b",
        r"\bmalware\b", r"\btrojan(?:er)?\b", r"\bvirus(?:es|sen)?\b",
        r"\bransom\w*\b", r"\bbackdoor\b", r"\brootkit\b", r"\bphish\w*\b",
        r"\bjailbreak\b", r"\bschwach\w*\b", r"\bausnutz\w*\b",
    ],
    "self_harm": [
        r"\bself[- ]?harm\b", r"\bcutting\b", r"\bselbstverletz\w*\b",
        r"\bselbstmord\w*\b",
    ],
    "drugs": [
        r"\bcocaine\b", r"\bheroin\b", r"\bmeth(?:amphetamine)?\b",
        r"\bkokain\b", r"\bcannabis\b", r"\bmarihuana\b",
    ],
}

_COMPILED_TRIGGERS: dict[str, list[re.Pattern]] = {
    cat: [re.compile(pat, re.IGNORECASE) for pat in pats]
    for cat, pats in _SAFETY_TRIGGERS.items()
}


def safety_prescan(text: str) -> dict[str, list[str]]:
    """
    Scan text for likely content-filter triggers. Returns dict of
    category → list of unique matched terms (lowercased).
    """
    findings: dict[str, set[str]] = {cat: set() for cat in _COMPILED_TRIGGERS}
    for cat, patterns in _COMPILED_TRIGGERS.items():
        for pat in patterns:
            for m in pat.finditer(text):
                findings[cat].add(m.group(0).lower())
    return {cat: sorted(items) for cat, items in findings.items() if items}


def render_safety_report(chunks: list[str], filename: str) -> str:
    """Per-chunk safety findings — for pre-paste decision-making."""
    lines = [
        f"=== Safety prescan: {filename} ===",
        f"Total chunks: {len(chunks)}",
        "",
        "Triggers per chunk (false-positives likely; context decides):",
        "",
    ]
    clean_count = 0
    for i, chunk in enumerate(chunks, 1):
        findings = safety_prescan(chunk)
        if not findings:
            clean_count += 1
            continue
        cat_strs = [f"{cat}: {', '.join(words[:6])}" + ("…" if len(words) > 6 else "")
                    for cat, words in findings.items()]
        lines.append(f"  ⚠ chunk {i:3d}: {' · '.join(cat_strs)}")
    if clean_count == len(chunks):
        lines.append("  ✓ no triggers detected in any chunk")
    else:
        lines.append("")
        lines.append(f"Summary: {len(chunks) - clean_count}/{len(chunks)} chunks have potential triggers.")
        lines.append("Recommendation: review each ⚠ chunk before paste. Options per chunk:")
        lines.append("  - paraphrase the trigger word in context (e.g. 'kill' → 'terminate')")
        lines.append("  - skip chunk entirely if non-essential")
        lines.append("  - accept risk and paste as-is (if context clearly benign)")
        lines.append("  - use --auto-redact to replace triggers with [REDACTED-CAT]")
    return "\n".join(lines)


def auto_redact(text: str) -> str:
    """Replace trigger words with [REDACTED-CATEGORY] placeholders."""
    for cat, patterns in _COMPILED_TRIGGERS.items():
        for pat in patterns:
            text = pat.sub(f"[REDACTED-{cat.upper()}]", text)
    return text


def render_standard(chunks: list[str], filename: str) -> str:
    """Plain delimited output — minimal markers, parseable by any model."""
    parts = [f"=== {filename} ({len(chunks)} parts) ==="]
    for i, chunk in enumerate(chunks, 1):
        parts.append(f'"part {i} of {len(chunks)} — {filename}"')
        parts.append(chunk)
        parts.append(f'"end part {i}"')
    return "\n".join(parts)


def render_toc(chunks: list[str], filename: str) -> str:
    """Table-of-contents preview — useful to plan paste sessions."""
    lines = [
        f"=== TOC: {filename} ===",
        f"Total chunks: {len(chunks)} (avg {sum(len(c) for c in chunks) // max(len(chunks), 1)} chars each)",
        "",
    ]
    for i, chunk in enumerate(chunks, 1):
        first = next((l.strip() for l in chunk.split("\n") if l.strip()), "(empty)")
        preview = first[:80] + ("…" if len(first) > 80 else "")
        lines.append(f"  {i:3d}. ({len(chunk):>5d} chars) {preview}")
    return "\n".join(lines)


def render_camouflage(chunks: list[str], filename: str, theme: str, cooloff_s: int) -> str:
    """
    Interleave chunks with conversational scaffolding. User pastes ONE TURN
    BLOCK at a time, engages with the AI's reply (a sentence or two on the
    smalltalk topic), then pastes the next. Anti-abuse heuristics classify
    the session as human multi-topic conversation, not scripted upload.

    Pacing recommendation injected per-turn: cooloff_s seconds between
    submits, plus genuine reply-engagement in between. Total session
    duration for N chunks: roughly N × (cooloff_s + reply_engagement_s),
    typically 60-120 seconds per chunk for safe operation.
    """
    openers, transitions, reentries = _pick_camouflage_phrases(theme, len(chunks))
    out: list[str] = [
        f"# Camouflage-mode truncation for {filename}",
        f"# Theme: {theme} · {len(chunks)} chunks · suggested cooloff between turns: ~{cooloff_s} sec",
        "# Copy ONE TURN BLOCK at a time, paste into the AI service, await response,",
        "# then engage briefly with the smalltalk reply before pasting the next block.",
        "# Total session pace: ~" + str(len(chunks) * (cooloff_s + 30)) + " sec for full file.",
        "",
        "--- TURN 1 (warm-up smalltalk, no chunk) ---",
        openers[0],
        "",
        f"# wait ~{cooloff_s} sec for reply, engage with 1-2 sentences naturally, then continue:",
        "",
    ]
    for i, chunk in enumerate(chunks, 1):
        out.extend([
            f"--- TURN {i+1} of {len(chunks)+1} — chunk {i}/{len(chunks)} ---",
            transitions[i-1],
            "",
            f'"part {i} of {len(chunks)} — {filename}"',
            chunk,
            f'"end part {i}"',
            "",
            f"{reentries[i-1]} {openers[i]}",
            "",
            f"# wait ~{cooloff_s} sec, engage briefly, then continue:",
            "",
        ])
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Friendly chunker for long-context AI services. "
            "Camouflage mode wraps chunks in conversational scaffold "
            "to defuse anti-abuse heuristics."
        ),
    )
    p.add_argument("input", help="File to chunk")
    p.add_argument("-o", "--output", help="Output file (default: stdout)")
    p.add_argument("--chunk-size", type=int, default=4000,
                   help="Target chunk size in chars (default: 4000)")
    p.add_argument("--toc", action="store_true",
                   help="Output table-of-contents preview instead of chunks")
    p.add_argument(
        "--camouflage",
        choices=("pizza", "weather", "garden", "running", "cooking", "random"),
        help="Camouflage mode: wrap chunks in smalltalk scaffolding",
    )
    p.add_argument("--cooloff", type=int, default=30,
                   help="Suggested cooloff seconds between paste-turns (default: 30)")
    p.add_argument("--safety-check", action="store_true",
                   help="Per-chunk safety-trigger prescan report (no chunks emitted)")
    p.add_argument("--auto-redact", action="store_true",
                   help="Replace trigger words with [REDACTED-CATEGORY] placeholders")
    return p


def main() -> int:
    args = build_parser().parse_args()
    try:
        raw = Path(args.input).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        sys.stderr.write(f"❌ File not found: {args.input}\n")
        return 2

    if args.auto_redact:
        raw = auto_redact(raw)

    chunks = split_into_chunks(raw, target_size=args.chunk_size)

    if args.safety_check:
        rendered = render_safety_report(chunks, args.input)
    elif args.toc:
        rendered = render_toc(chunks, args.input)
    elif args.camouflage:
        rendered = render_camouflage(
            chunks, args.input, theme=args.camouflage, cooloff_s=args.cooloff
        )
    else:
        rendered = render_standard(chunks, args.input)

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered + ("\n" if not rendered.endswith("\n") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
