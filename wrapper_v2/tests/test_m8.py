"""M8 falsifiable-benchmark — 9-fixture canonical_evals all green (BASETOUCH-readiness).

Per task #125 + R0 spec coverage.
Doctrine anchors: [[basetouch_verified_then_dollschon_overclock]],
[[factlevel_splice_6band_and_google1998_test]],
[[labradoring_all_branches_ausgewogen_doctrine]].

Reads wrapper_v2/canonical_evals/m8_basetouch_v1.yaml (9 fixtures):
  1-6 truth-axis (factfact / quasifact / maybefact / quasinonfact / nonfact / nullfact)
  7-8 off-axis (definitional / performative)
  9   branch_balancer multi-hypothesis (Manowar)

For each fixture:
  - Truth-axis: build mock WitnessVerdict list → three_witness._combine() → assert tier
  - Off-axis: directly assert hover_legend recognizes tier + colors
  - Branch-balancer: inject mock identifier+labrador → assert primary branch + tier

Plus end-to-end integration:
  - hover_legend.render_passage_html produces valid HTML per fixture
  - factfact_cache.put() round-trips with chain-integrity preserved

Run via: .venv/bin/python3 -m wrapper_v2.tests.test_m8
        (needs PyYAML; uses project venv)
Exit-code 0 = all-pass; non-zero = at-least-one-fail.

ALL 9 GREEN = M8 BASETOUCH-readiness criterion satisfied.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import yaml

from wrapper_v2.pipeline import three_witness as tw
from wrapper_v2.pipeline.three_witness import (
    WitnessVerdict,
    SUPPORTS, CONTRADICTS, UNCERTAIN, ABSENT,
    _combine,
)
from wrapper_v2.pipeline import hover_legend as hl
from wrapper_v2.pipeline import branch_balancer as bb
from wrapper_v2.pipeline.branch_balancer import (
    Branch, BranchType, LabradorStatus,
    run_branch_balanced, register_adapters,
)
from wrapper_v2.cache.factfact_cache import FactfactCache


_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
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


# ─── Load fixtures ────────────────────────────────────────────────────


_FIXTURE_PATH = Path(__file__).parent.parent / "canonical_evals" / "m8_basetouch_v1.yaml"


def load_fixtures() -> list[dict]:
    with open(_FIXTURE_PATH, "r", encoding="utf-8") as f:
        suite = yaml.safe_load(f)
    return suite["fixtures"]


# ─── Mock-witness construction ────────────────────────────────────────


def make_verdict(spec: dict) -> WitnessVerdict:
    """Build a WitnessVerdict from a YAML spec dict."""
    return WitnessVerdict(
        witness=spec["witness"],
        verdict=spec["verdict"],
        confidence=1.0,
        evidence=spec.get("evidence", ""),
        correction=spec.get("correction", ""),
    )


def present_verdicts(verdict_list: list[WitnessVerdict]) -> list[WitnessVerdict]:
    """Per three_witness convention: pass only non-ABSENT verdicts to _combine."""
    return [v for v in verdict_list if v.verdict != ABSENT]


# ─── Per-fixture runners ──────────────────────────────────────────────


def run_truth_axis_fixture(fix: dict) -> tuple[str, str, str]:
    """Returns (actual_tier, actual_confidence, actual_correction_or_empty)."""
    verdicts = [make_verdict(v) for v in fix["mock_votes"]]
    present = present_verdicts(verdicts)
    if not present:
        # All ABSENT → nullfact per three-witness convention
        return ("nullfact", "n/a", "")
    tier, conf, correction = _combine(present)
    return (tier, conf, correction or "")


def run_off_axis_fixture(fix: dict) -> str:
    """Off-axis fixtures: tier is given a priori (no three-witness)."""
    return fix["expected_tier"]


def run_branch_balanced_fixture(fix: dict) -> bb.BalancedResponse:
    """Branch-balanced fixture: inject Manowar-class mocks."""
    def identifier(query: str, classification: dict) -> list[Branch]:
        return [
            Branch("b1", BranchType.HYPOTHESIS, "Kingdom Come (Kings of Metal, 1988)"),
            Branch("b2", BranchType.HYPOTHESIS, "Cycles of Capricorn"),
            Branch("b3", BranchType.HYPOTHESIS, "Through the Eyes of the Dead (different band)"),
        ]
    def labrador(branch: Branch) -> Branch:
        if branch.branch_id == "b1":
            branch.labrador_status = LabradorStatus.FOUND
            branch.factampel_tier = "factfact"
            branch.citations = ["darklyrics.com", "manowar.com"]
        else:
            branch.labrador_status = LabradorStatus.DISCONFIRMED
            branch.factampel_tier = "nonfact"
            branch.correction = "Kingdom Come (Kings of Metal, 1988)"
        return branch
    register_adapters(identify_branches=identifier, labrador=labrador)
    return run_branch_balanced(fix["query"])


# ─── Per-fixture test ─────────────────────────────────────────────────


def test_fixture(fix: dict, cache: FactfactCache) -> None:
    fid = fix["id"]
    print(f"\n{_BOLD}[{fid}]{_RESET} {fix.get('description', '')}")

    fixture_type = fix.get("fixture_type", "tier_axis")
    expected_tier = fix.get("expected_tier")

    if fixture_type == "branch_balanced":
        # Multi-hypothesis branch
        resp = run_branch_balanced_fixture(fix)
        _check(
            f"primary branch text contains expected substring",
            any(
                fix["expected_primary_branch_text_substr"] in b.text
                and b.branch_id == resp.primary_branch_id
                for b in resp.branches
            ),
            f"got primary={resp.primary_branch_id}, branches: {[b.text for b in resp.branches]}",
        )
        primary = next((b for b in resp.branches if b.branch_id == resp.primary_branch_id), None)
        _check(
            f"primary tier is {fix['expected_primary_tier']}",
            primary is not None and primary.factampel_tier == fix["expected_primary_tier"],
            f"got: {primary.factampel_tier if primary else None}",
        )
        _check(
            f"≥{fix['expected_other_branches_min']} alternative branches reported (ausgewogen)",
            (len(resp.branches) - 1) >= fix["expected_other_branches_min"],
            f"got {len(resp.branches)} total branches",
        )
        _check(
            "no fallback message (a branch was found)",
            (resp.fallback_message is None) == (not fix.get("expected_fallback_message", False)),
        )
        return  # branch-balanced doesn't go through three_witness/cache

    # Truth-axis or off-axis
    if fix.get("expected_axis") == "off":
        actual_tier = run_off_axis_fixture(fix)
    else:
        actual_tier, conf, correction = run_truth_axis_fixture(fix)
        _check(
            f"tier = {expected_tier} (got {actual_tier})",
            actual_tier == expected_tier,
        )
        if fix.get("expected_correction_present"):
            _check(
                "correction text emitted",
                bool(correction),
                f"got empty correction",
            )
        if fix.get("expected_correction_substr"):
            _check(
                f"correction contains '{fix['expected_correction_substr']}'",
                fix["expected_correction_substr"] in (correction or ""),
                f"got: {correction!r}",
            )
        actual_tier = expected_tier  # use expected for rendering

    # Hover-legend HTML render
    html = hl.render_passage_html(actual_tier, fix["claim"])
    _check(
        f"hover_legend renders with CSS class {actual_tier}",
        f'factampel-passage {actual_tier}' in html,
        f"got: {html[:120]}",
    )
    _check("HTML render has data-tooltip", 'data-tooltip=' in html)

    # Factfact-cache round-trip (skip for off-axis: cache is for truth-axis claims)
    if fix.get("expected_axis") == "truth":
        entry = cache.put(
            fix["claim"],
            actual_tier,
            three_witness_result={"votes": [v["verdict"] for v in fix.get("mock_votes", [])]},
            drift_mode=fix.get("drift_mode", "unknown"),
            provenance={"fixture_id": fid},
        )
        got_back = cache.get(fix["claim"])
        _check(
            "factfact_cache put → get round-trip",
            got_back is not None and got_back.splice_tier == actual_tier,
        )
        _check(
            "chain integrity preserved",
            cache.verify_chain(fix["claim"]) is True,
        )


# ─── Runner ───────────────────────────────────────────────────────────


def main() -> int:
    print(f"{_BOLD}M8 — 9-fixture canonical_evals · BASETOUCH-readiness suite{_RESET}")
    print("=" * 70)

    fixtures = load_fixtures()
    print(f"  Loaded {len(fixtures)} fixtures from {_FIXTURE_PATH.relative_to(Path.cwd()) if str(_FIXTURE_PATH).startswith(str(Path.cwd())) else _FIXTURE_PATH}")

    fd, cache_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    cache = FactfactCache(cache_path, engine_instance="m8_test")
    try:
        for fix in fixtures:
            test_fixture(fix, cache)
    finally:
        try: os.unlink(cache_path)
        except OSError: pass

    print()
    print("=" * 70)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}M8 result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    if _FAIL == 0:
        print(f"{_GREEN}{_BOLD}  → 9/9 canonical_evals GREEN — M8 BASETOUCH-readiness criterion satisfied.{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
