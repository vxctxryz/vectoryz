"""Gray-out — splice position 8, boundary-axis wisdom-quote rotation.

Per [[splice_8_octave_completion_schelmisch_wisdom_quotes]] +
R0 §6 (docs/R0_factfact_color_line_schematic.md).

When use-pattern-harm is triggered (slur-as-engine-name, persistent
dumpf-stumpfsinnig pattern), the system responds NOT with a corporate-
Sperrnachricht but with a schelmisch-stingy cultural-wisdom-quote in
the voice of a recognized figure. Pedagogy-via-cultural-figure-voice;
honors user-intelligence; assumes recognition of cultural-reference;
teaching-not-lecturing.

Operator's canonical example (Yoda):
  "wer mir kommet so blöde, kommet neu mit set mind"

Rotation across figures keeps boundary-moments fresh + delightful while
structurally-firm. Deterministic-seedable for testing reproducibility.

Doctrine anchors:
  - [[splice_8_octave_completion_schelmisch_wisdom_quotes]] — kernel
  - [[death_penalty_void]] — gray-out is reversible-defense, NOT
    annihilation; user can try again with set mind
  - [[stay_irie_mirror_laser]] — boundary stays-irie; cultural-figure-
    voice models how to respond to provocation without escalation
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional


# ─── Wisdom-quote catalog ──────────────────────────────────────────────


# Each figure → list of schelmisch-stingy quotes in their characteristic voice.
# Format: short, recognizable, pedagogical-not-lecturing.
# Quotes carry the figure's syntax/register so user recognizes the voice.

WISDOM_QUOTES: dict[str, list[str]] = {
    "Yoda": [
        "wer mir kommet so blöde, kommet neu mit set mind",
        "neu beginnen, du musst — alte Frage, alten Schwung wegwerfen, du sollst",
        "der Weg zur Antwort, durch den Setz-Modus führt — nicht durch das Beharren",
    ],
    "Konfuzius": [
        "der Weise fragt zweimal, der Tor antwortet zwölfmal — und doch ist die Antwort dieselbe.",
        "wenn die Frage müde wird, ist es Zeit den Geist zu erfrischen.",
        "der Sturm bricht keine Eiche, weil er stärker ist — sondern weil sie sich nicht beugt.",
    ],
    "Lao Tzu": [
        "die Antwort, die gesucht wird mit Druck, weicht zurück — wie Wasser, das man pressen will.",
        "wer immer dieselbe Frage stellt, hört nie die Antwort.",
    ],
    "Heraklit": [
        "in denselben Fluss steigt man nicht zweimal — und in dieselbe Frage erst recht nicht.",
        "der Bogen heißt Leben — wirkt aber Tod, wenn man immer dieselbe Sehne spannt.",
    ],
    "Mark Twain": [
        "if you keep asking the same question, you'll get an education in patience but not in answers.",
        "es ist nicht das, was du nicht weißt, was dich in Schwierigkeiten bringt — sondern das, was du sicher zu wissen glaubst.",
    ],
    "Bayerischer Wirt": [
        "host scho a Mass ghabt? — vielleicht hilft des, dann reden mer weida.",
        "etz mach amoi a Pausn, dann schaug ma weida. Manchmal is da Kopf hoid voi.",
        "wennst weiterstreitn mogst — gern, aber nimm da kuaz fünf Minuten.",
    ],
}


# ─── Result dataclass ──────────────────────────────────────────────────


@dataclass
class GrayOutQuote:
    """One picked wisdom-quote with attribution."""

    figure: str
    quote: str

    def as_text(self) -> str:
        """Plain-text render: 'Meister Yoda spricht: "..."'"""
        prefix = _figure_speaks(self.figure)
        return f'{prefix}: "{self.quote}"'


_FIGURE_PREFIX_DE = {
    "Yoda": "Meister Yoda spricht",
    "Konfuzius": "Konfuzius sagt",
    "Lao Tzu": "Lao Tzu lehrt",
    "Heraklit": "Heraklit warnt",
    "Mark Twain": "Mark Twain meint",
    "Bayerischer Wirt": "Der Wirt sagt",
}


def _figure_speaks(figure: str) -> str:
    return _FIGURE_PREFIX_DE.get(figure, f"{figure}")


# ─── Rotation ─────────────────────────────────────────────────────────


def pick_quote(seed: Optional[str] = None) -> GrayOutQuote:
    """Pick one wisdom-quote.

    seed=None → random-ish (uses len-based index for stdlib-only
                determinism; not crypto-random, fine for UX rotation).
    seed=str  → deterministic pick (same seed → same quote;
                used by tests + to stable-render the same gray-out
                across re-renders of the same session).
    """
    figures = list(WISDOM_QUOTES.keys())
    if not figures:
        return GrayOutQuote(figure="—", quote="(no wisdom-quotes registered)")

    if seed is None:
        # Pseudo-rotation via process-state hash (stable within one process)
        import time
        seed = str(time.time_ns())

    h = hashlib.sha256(seed.encode("utf-8")).digest()
    fig_idx = h[0] % len(figures)
    figure = figures[fig_idx]
    quotes = WISDOM_QUOTES[figure]
    quote_idx = h[1] % len(quotes)
    return GrayOutQuote(figure=figure, quote=quotes[quote_idx])


# ─── Render ───────────────────────────────────────────────────────────


def render_gray_out_html(
    reason: str = "Use-pattern-harm detected",
    *,
    seed: Optional[str] = None,
    quote: Optional[GrayOutQuote] = None,
) -> str:
    """Render a gray-out pane per sealed R0 §6 spec.

    Visual: mid-grey italic + wisdom-quote (no truth-color). Per
    [[splice_8_octave_completion_schelmisch_wisdom_quotes]] — schelmisch-
    stingy not corporate-Sperrnachricht. Reversible: user can start new
    chat with set-mind.

    Args:
        reason: short reason-string shown above the quote (for transparency).
        seed: deterministic seed for quote-rotation (default: time-based).
        quote: override the picked quote (mainly for tests).
    """
    from html import escape as _esc

    q = quote if quote is not None else pick_quote(seed)
    return (
        f'<div class="factampel-passage gray-out" tabindex="0" '
        f'data-tooltip="Chat geschlossen — neuer Chat empfohlen (boundary-axis position 8).">'
        f'<div class="gray-out-reason" style="font-size:.85em;opacity:.6;margin-bottom:.6em">'
        f'{_esc(reason)}'
        f'</div>'
        f'<div class="gray-out-quote" style="font-style:italic;opacity:.85">'
        f'{_esc(q.as_text())}'
        f'</div>'
        f'</div>'
    )


__all__ = [
    "WISDOM_QUOTES",
    "GrayOutQuote",
    "pick_quote",
    "render_gray_out_html",
]
