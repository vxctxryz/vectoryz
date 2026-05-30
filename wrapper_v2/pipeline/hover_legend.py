"""Hover-legend — M4 typed accessor + HTML renderer for the factampel legend.

Per [[factampel_ui_sealed_first_wave]] (sealed 2026-05-19) + R0
(docs/R0_factfact_color_line_schematic.md).

Source of truth: wrapper_v2/config/splice_legend.yaml (120-line config
with all 11 tier-states + colors + bilingual tooltips).

This module:
  1. Loads the legend YAML once (memoized).
  2. Exposes typed accessors (color, tooltip, emoji, position, axis).
  3. Renders per-passage HTML matching the sealed prototype CSS in
     static-www-vectoryz-v1/index.html lines 1273-1313 + the
     legend prototype at benchmark_cc/prototypes/factampel_hover_prototype.html.
  4. Renders a full 11-tier reference legend (used in M4 demo + by R5 schiri).

Why a Python module for client-side UI? Two reasons:
  - The TOOLTIP-TEXT is server-emitted (per-claim) — needs canonical formatter
  - HTML rendering for SSR / static-demo / fixture-tests benefits from typed API

The chat-app inline JS at static-www-vectoryz-v1/index.html::renderFactampelStrip
continues to render dynamically from SSE events. Both paths produce the SAME
visual output because both read the same source-of-truth (splice_legend.yaml
via tooltip_de field).

Doctrine anchors:
  - [[factampel_ui_sealed_first_wave]] — sealed visual-spec
  - [[factlevel_splice_6band_and_google1998_test]] — 6-band truth-axis
  - [[splice_8_octave_completion_schelmisch_wisdom_quotes]] — 8-octave structure
  - [[alarm_l0_architectural_priority_nanosecond_counts]] — L0 outside splice
  - [[death_penalty_void]] — nullfact must always render (never silent)
"""

from __future__ import annotations

from html import escape as _esc
from pathlib import Path
from typing import Optional

import yaml


# ─── Loader (memoized) ─────────────────────────────────────────────────


_CONFIG_PATH = Path(__file__).parent.parent / "config" / "splice_legend.yaml"
_LEGEND: Optional[dict] = None


def _load() -> dict:
    """Load splice_legend.yaml once, cache. Raise if missing."""
    global _LEGEND
    if _LEGEND is None:
        if not _CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"splice_legend.yaml missing at {_CONFIG_PATH}. "
                "Recover via: git show remotes/gx44/main:wrapper_v2/config/splice_legend.yaml"
            )
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            _LEGEND = yaml.safe_load(f) or {}
    return _LEGEND


# ─── Tier inventory ───────────────────────────────────────────────────


TRUTH_AXIS_TIERS = (
    "factfact", "quasifact", "maybefact", "quasinonfact", "nonfact", "nullfact",
)
OFF_AXIS_TAGS = ("definitional", "broken", "performative")
ROLE_AXIS_TIERS = ("fyifact",)
BOUNDARY_AXIS_TIERS = ("gray_out",)
L0_TIERS = ("l0_alarm",)

ALL_TIERS = TRUTH_AXIS_TIERS + ROLE_AXIS_TIERS + BOUNDARY_AXIS_TIERS + L0_TIERS + OFF_AXIS_TAGS
# 6 + 1 + 1 + 1 + 3 = 12 entries. (broken is off-axis-3, total 11 per R0
# canonical count BUT splice_legend.yaml carries 'broken' as 12th — kept here
# for compatibility; R0 listing is 11 because broken is an internal-error
# tag not user-facing-axis.)


def _bucket(tier: str) -> Optional[str]:
    """Return which yaml-section a tier lives in."""
    legend = _load()
    for section in ("truth_axis", "role_axis", "boundary_axis", "off_axis_tags"):
        if tier in legend.get(section, {}):
            return section
    if tier == "l0_alarm" and "l0_alarm" in legend:
        return "l0_alarm"
    return None


# ─── Accessors ─────────────────────────────────────────────────────────


def get_tier_meta(tier: str) -> dict:
    """Return the full meta dict for a tier (or empty dict if unknown)."""
    legend = _load()
    section = _bucket(tier)
    if section is None:
        return {}
    if section == "l0_alarm":
        return legend["l0_alarm"]
    return legend.get(section, {}).get(tier, {})


def color_css(tier: str) -> Optional[str]:
    """Return CSS color string for a tier, or None if not color-coded."""
    return get_tier_meta(tier).get("color_css")


def emoji(tier: str) -> str:
    """Return emoji glyph for a tier (empty string if none)."""
    return get_tier_meta(tier).get("emoji", "")


def tooltip(tier: str, lang: str = "de") -> str:
    """Return tooltip text for a tier in requested language.

    Falls back to label if no tooltip set. Falls back to tier-name if no
    label set. Never raises — labradoring-discipline (every claim must
    have a tooltip).
    """
    meta = get_tier_meta(tier)
    key = f"tooltip_{lang}"
    if key in meta:
        return meta[key]
    label_key = f"label_{lang}"
    if label_key in meta:
        return meta[label_key]
    return tier


def position(tier: str) -> Optional[int]:
    """Splice position (1-8) for truth/role/boundary axes; None for L0 + off-axis."""
    return get_tier_meta(tier).get("position")


def axis(tier: str) -> str:
    """Return axis name: 'truth' / 'role' / 'boundary' / 'off' / 'l0' / 'unknown'."""
    bucket = _bucket(tier)
    return {
        "truth_axis": "truth",
        "role_axis": "role",
        "boundary_axis": "boundary",
        "off_axis_tags": "off",
        "l0_alarm": "l0",
    }.get(bucket or "", "unknown")


def all_tiers() -> list[str]:
    """All tier-names registered in splice_legend.yaml (no order guarantee
    beyond yaml-load order, which is insertion-order in CPython 3.7+)."""
    return list(ALL_TIERS)


# ─── HTML rendering ────────────────────────────────────────────────────


def render_passage_html(
    tier: str,
    content: str,
    *,
    tooltip_override: Optional[str] = None,
    lang: str = "de",
    correction: Optional[str] = None,
    citations: Optional[list[str]] = None,
) -> str:
    """Render a single passage div per sealed UI spec.

    Output mirrors the sealed prototype + chat-app inline JS:
      <div class="factampel-passage TIER" tabindex="0" data-tooltip="…">
        CONTENT
        [optional correction]
      </div>

    All user-supplied content is HTML-escaped (content, correction,
    citations); only the wrapping markup is trusted.
    """
    css_class = "factampel-passage " + _css_tier_class(tier)

    tip = tooltip_override if tooltip_override is not None else tooltip(tier, lang=lang)
    if correction:
        tip = (tip or "") + ("\n→ " + ("Korrektur" if lang == "de" else "Correction") + ": " + correction)
    if citations:
        tip = (tip or "") + "\n[" + ", ".join(citations) + "]"

    parts = [f'<div class="{_esc(css_class)}" tabindex="0" data-tooltip="{_esc(tip)}">']
    parts.append(f'  <span>{_esc(content)}</span>')
    if correction:
        corr_label = "Korrektur" if lang == "de" else "Correction"
        parts.append(
            f'  <div class="factampel-correction" style="margin-top:.2em;margin-left:1.2em;'
            f'font-style:italic;font-size:.85em;opacity:.6">'
            f'→ {_esc(corr_label)}: {_esc(correction)}</div>'
        )
    parts.append('</div>')
    return "\n".join(parts)


def _css_tier_class(tier: str) -> str:
    """Map tier-name to the CSS class-name used by sealed UI.

    sealed UI uses these class-suffixes (from index.html ::1307-1313):
      factfact / quasifact / maybefact / quasinonfact / nonfact / nullfact
      / definitional / performative / fyifact / gray-out / l0-alarm
    The yaml uses gray_out + l0_alarm (snake_case); CSS uses gray-out + l0-alarm
    (kebab-case). This helper normalizes.
    """
    return tier.replace("_", "-")


def render_legend_html(lang: str = "de") -> str:
    """Render the full 11-tier reference legend as HTML.

    Used by M4 demo page + R5 schiri visual-arbitration. Each tier
    appears once with its glyph, label, color-line, tooltip.
    """
    title = "Factampel — Legende (alle 11 Stufen)" if lang == "de" else "Factampel — Legend (all 11 tiers)"
    parts = [f'<section class="factampel-legend">', f'  <h2>{_esc(title)}</h2>']

    sections = [
        ("Wahrheits-Achse" if lang == "de" else "Truth axis", TRUTH_AXIS_TIERS),
        ("Off-Axis Tags", OFF_AXIS_TAGS),
        ("Rolle" if lang == "de" else "Role", ROLE_AXIS_TIERS),
        ("Grenze" if lang == "de" else "Boundary", BOUNDARY_AXIS_TIERS),
        ("L0 (architektonische Priorität)" if lang == "de" else "L0 (architectural priority)", L0_TIERS),
    ]
    for sec_label, tiers in sections:
        parts.append(f'  <h3>{_esc(sec_label)}</h3>')
        for tier in tiers:
            meta = get_tier_meta(tier)
            if not meta:
                continue
            example_de = {
                "factfact": "Die Erde ist (in erster Näherung) ein Geoid.",
                "quasifact": "Mediterrane Diät korreliert mit reduziertem Herz-Kreislauf-Risiko.",
                "maybefact": "Ob Veganismus für individuelle Longevity besser ist als Omnivor.",
                "quasinonfact": "Die Behauptung, Zucker sei generell süchtig-machend wie Heroin.",
                "nonfact": "Der Eiffelturm steht in Berlin.",
                "nullfact": "Welches Lied bei der Punk-Party Berlin 17.10.1981 als drittes gespielt wurde.",
                "definitional": "Alle Junggesellen sind unverheiratet.",
                "broken": "(struktureller Widerspruch)",
                "performative": "Ich erkläre hiermit die Sitzung für eröffnet.",
                "fyifact": "Doktrin-Kontext: …",
                "gray_out": "(Sperr-Pane mit Weisheits-Zitat)",
                "l0_alarm": "(Notfall-Pane — Hilfe wurde geschickt)",
            }.get(tier, _esc(tier))
            example = example_de
            parts.append(render_passage_html(tier, example, lang=lang))
    parts.append('</section>')
    return "\n".join(parts)


# ─── Module API summary ────────────────────────────────────────────────


__all__ = [
    "TRUTH_AXIS_TIERS",
    "OFF_AXIS_TAGS",
    "ROLE_AXIS_TIERS",
    "BOUNDARY_AXIS_TIERS",
    "L0_TIERS",
    "ALL_TIERS",
    "get_tier_meta",
    "color_css",
    "emoji",
    "tooltip",
    "position",
    "axis",
    "all_tiers",
    "render_passage_html",
    "render_legend_html",
]
