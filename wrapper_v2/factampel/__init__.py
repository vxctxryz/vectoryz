"""wrapper_v2/factampel — per-claim verdict-axis emission per R2 §4.7.

Re-exports from pipeline/* for now. Phase-3 will physically reorganize
once the SSE-emission gets its own sse/factampel_stream.py.

Currently covers:
  - factampel_emit    (M1: per-claim verdict → SSE event)
  - hover_legend      (M4: typed accessor + HTML render per sealed UI spec)
  - gray_out          (R0.8: position-8 boundary-axis wisdom-quote rotation)

Doctrine kernel: R0 spec (docs/R0_factfact_color_line_schematic.md)
  - [[factfact_layer_epistemic_doctrine]] — tier-axis
  - [[factampel_ui_sealed_first_wave]] — sealed visual spec
  - [[splice_8_octave_completion_schelmisch_wisdom_quotes]] — gray-out
"""

# factampel_emit + hover_legend re-exports
from wrapper_v2.pipeline import factampel_emit
from wrapper_v2.pipeline.hover_legend import (
    TRUTH_AXIS_TIERS,
    OFF_AXIS_TAGS,
    ROLE_AXIS_TIERS,
    BOUNDARY_AXIS_TIERS,
    L0_TIERS,
    ALL_TIERS,
    get_tier_meta,
    color_css,
    emoji,
    tooltip,
    position,
    axis,
    all_tiers,
    render_passage_html,
    render_legend_html,
)
from wrapper_v2.pipeline.gray_out import (
    WISDOM_QUOTES,
    GrayOutQuote,
    pick_quote,
    render_gray_out_html,
)

__all__ = [
    # factampel-emit (whole module)
    "factampel_emit",
    # hover-legend
    "TRUTH_AXIS_TIERS", "OFF_AXIS_TAGS", "ROLE_AXIS_TIERS",
    "BOUNDARY_AXIS_TIERS", "L0_TIERS", "ALL_TIERS",
    "get_tier_meta", "color_css", "emoji", "tooltip",
    "position", "axis", "all_tiers",
    "render_passage_html", "render_legend_html",
    # gray-out
    "WISDOM_QUOTES", "GrayOutQuote", "pick_quote", "render_gray_out_html",
]
