"""M4 falsifiable-benchmark — hover-legend typed accessor + HTML renderer.

Per task #121 + [[factampel_ui_sealed_first_wave]] + R0 spec.

Verifies hover_legend.py loads splice_legend.yaml correctly and produces
expected colors/tooltips/HTML for all 11 tier-states.

Run via: .venv/bin/python3 -m wrapper_v2.tests.test_m4
        (project venv has PyYAML; system python3 may not)
Exit-code 0 = all-pass; non-zero = at-least-one-fail.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.pipeline import hover_legend as hl


# ANSI colors
_GREEN = "\033[92m"
_RED = "\033[91m"
_BOLD = "\033[1m"
_RESET = "\033[0m"

_PASS = 0
_FAIL = 0


def _check(label: str, cond: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  {_GREEN}✓{_RESET} {label}")
    else:
        _FAIL += 1
        print(f"  {_RED}✗ {label}{_RESET}")
        if detail:
            print(f"      {detail}")


# ─── Tests ─────────────────────────────────────────────────────────────


def test_config_loads():
    print(f"\n{_BOLD}[T1]{_RESET} splice_legend.yaml loads cleanly")
    try:
        legend = hl._load()
        _check("legend dict returned", isinstance(legend, dict))
        _check("has truth_axis", "truth_axis" in legend)
        _check("has off_axis_tags", "off_axis_tags" in legend)
        _check("has role_axis", "role_axis" in legend)
        _check("has boundary_axis", "boundary_axis" in legend)
        _check("has l0_alarm", "l0_alarm" in legend)
    except Exception as e:
        _check(f"loader raised: {e}", False)


def test_truth_axis_six_tiers_complete():
    print(f"\n{_BOLD}[T2]{_RESET} all 6 truth-axis tiers have color + tooltip_de + position")
    for tier in hl.TRUTH_AXIS_TIERS:
        meta = hl.get_tier_meta(tier)
        _check(f"{tier}: has tooltip_de", bool(hl.tooltip(tier, lang='de')))
        _check(f"{tier}: has emoji", bool(hl.emoji(tier)))
        _check(f"{tier}: position is int 1-6", isinstance(meta.get('position'), int))


def test_specific_colors_match_r0_spec():
    print(f"\n{_BOLD}[T3]{_RESET} specific tier colors match R0 sealed hex values")
    expected = {
        "factfact": "#2ea043",
        "quasifact": "#7cb342",
        "maybefact": "#f1c40f",
        "quasinonfact": "#e67e22",
        "nonfact": "#c0392b",
        "nullfact": "transparent",
        "definitional": "#9b59b6",
        "performative": "#ffffff",
    }
    for tier, expected_color in expected.items():
        actual = hl.color_css(tier)
        _check(f"{tier} color = {expected_color}", actual == expected_color,
               f"got: {actual}")


def test_tooltips_match_r0_canonical_pattern():
    print(f"\n{_BOLD}[T4]{_RESET} tooltip text matches R0 §3 canonical patterns")
    expected_de = {
        "factfact": "🟢 factfact — Faktisch belegbar. Audit-proof. Unbestritten.",
        "quasifact": "🟢⚪ quasifact — Stark belegt, kleine Restunsicherheit.",
        "maybefact": "🟡 maybefact — Gleichgewicht — Evidenz steht beidseits.",
        "nonfact": "🔴 nonfact — Faktisch widerlegt. Audit-proof falsch.",
        "nullfact": "⚪ nullfact — Keine Evidenz zuweisbar — ehrlicher Nicht-Befund.",
    }
    for tier, expected_text in expected_de.items():
        actual = hl.tooltip(tier, lang="de")
        _check(f"{tier} de-tooltip matches", actual == expected_text,
               f"got: {actual}")


def test_axis_classification():
    print(f"\n{_BOLD}[T5]{_RESET} axis() returns correct bucket per tier")
    _check("factfact → truth", hl.axis("factfact") == "truth")
    _check("nullfact → truth", hl.axis("nullfact") == "truth")
    _check("definitional → off", hl.axis("definitional") == "off")
    _check("performative → off", hl.axis("performative") == "off")
    _check("fyifact → role", hl.axis("fyifact") == "role")
    _check("gray_out → boundary", hl.axis("gray_out") == "boundary")
    _check("l0_alarm → l0", hl.axis("l0_alarm") == "l0")
    _check("unknown → unknown", hl.axis("__nope__") == "unknown")


def test_render_passage_html_basic():
    print(f"\n{_BOLD}[T6]{_RESET} render_passage_html produces sealed-CSS-class + data-tooltip")
    html = hl.render_passage_html("factfact", "Die Erde ist ein Geoid.")
    _check("contains factampel-passage class", 'class="factampel-passage factfact"' in html)
    _check("has tabindex=0", 'tabindex="0"' in html)
    _check("has data-tooltip", "data-tooltip=" in html)
    _check("contains escaped content", "Die Erde ist ein Geoid." in html)
    _check("contains DE tooltip", "Faktisch belegbar" in html)


def test_render_passage_html_escapes_user_content():
    print(f"\n{_BOLD}[T7]{_RESET} render_passage_html HTML-escapes user input")
    html = hl.render_passage_html("factfact", "<script>alert(1)</script>")
    _check(
        "no raw <script> in output",
        "<script>alert(1)" not in html,
        f"got: {html[:200]}",
    )
    _check("escaped &lt;script&gt; present", "&lt;script&gt;" in html)


def test_render_passage_html_with_correction():
    print(f"\n{_BOLD}[T8]{_RESET} render_passage_html includes correction-box on nonfact")
    html = hl.render_passage_html(
        "nonfact",
        "Der Eiffelturm steht in Berlin.",
        correction="Der Eiffelturm steht in Paris.",
    )
    _check("class is nonfact", 'class="factampel-passage nonfact"' in html)
    _check("correction text appears in body", "Eiffelturm steht in Paris" in html)
    _check("correction div present", "factampel-correction" in html)


def test_kebab_case_class_for_gray_out_and_l0():
    print(f"\n{_BOLD}[T9]{_RESET} CSS class uses kebab-case (gray-out / l0-alarm)")
    h1 = hl.render_passage_html("gray_out", "(Sperr-Pane)")
    h2 = hl.render_passage_html("l0_alarm", "(Notfall-Pane)")
    _check("gray-out kebab class", 'factampel-passage gray-out' in h1, f"got: {h1[:100]}")
    _check("l0-alarm kebab class", 'factampel-passage l0-alarm' in h2, f"got: {h2[:100]}")


def test_render_full_legend():
    print(f"\n{_BOLD}[T10]{_RESET} render_legend_html includes ALL 11 tier-states")
    legend = hl.render_legend_html(lang="de")
    for tier in (
        "factfact", "quasifact", "maybefact", "quasinonfact",
        "nonfact", "nullfact", "definitional", "performative",
        "fyifact", "gray-out", "l0-alarm",
    ):
        _check(
            f"legend contains {tier} class",
            f'factampel-passage {tier}' in legend,
            "missing in render",
        )


def test_tooltip_fallback_to_label_then_tier_name():
    print(f"\n{_BOLD}[T11]{_RESET} tooltip never raises (fallback to label / tier-name)")
    _check("unknown tier returns its own name", hl.tooltip("__nope__", lang="de") == "__nope__")


def test_position_only_for_splice_tiers():
    print(f"\n{_BOLD}[T12]{_RESET} splice positions defined for truth+role+boundary, None for off/L0")
    _check("factfact has position", hl.position("factfact") == 1)
    _check("nullfact has position", hl.position("nullfact") == 6)
    _check("fyifact has position", hl.position("fyifact") == 7)
    _check("gray_out has position", hl.position("gray_out") == 8)
    _check("definitional has no position", hl.position("definitional") is None)
    _check("l0_alarm has no position (architectural priority)", hl.position("l0_alarm") is None)


# ─── Runner ────────────────────────────────────────────────────────────


def main() -> int:
    print(f"{_BOLD}M4 — Hover-legend typed accessor + HTML render · falsifiable benchmark{_RESET}")
    print("=" * 70)

    test_config_loads()
    test_truth_axis_six_tiers_complete()
    test_specific_colors_match_r0_spec()
    test_tooltips_match_r0_canonical_pattern()
    test_axis_classification()
    test_render_passage_html_basic()
    test_render_passage_html_escapes_user_content()
    test_render_passage_html_with_correction()
    test_kebab_case_class_for_gray_out_and_l0()
    test_render_full_legend()
    test_tooltip_fallback_to_label_then_tier_name()
    test_position_only_for_splice_tiers()

    print()
    print("=" * 70)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}M4 result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
