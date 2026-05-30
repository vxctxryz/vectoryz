"""M3 falsifiable-benchmark — branch-balanced labradoring.

Per task #120 + [[labradoring_all_branches_ausgewogen_doctrine]].

Tests the branch-balancer orchestrator with mock adapters:
  - branch-identifier injects 3 fixed branches per known query
  - labrador adapter injects controlled per-branch verdicts
  - assertions cover: tier-attached, status-attached, primary-picking,
    fallback-message when nothing FOUND, never-silence invariant

Run via: python3 -m wrapper_v2.tests.test_m3
Exit-code 0 = all-pass; non-zero = at-least-one-fail.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from /home/bsr/42
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.pipeline import branch_balancer as bb
from wrapper_v2.pipeline.branch_balancer import (
    Branch,
    BranchType,
    LabradorStatus,
    run_branch_balanced,
    register_adapters,
    render_balanced_text,
)


# ANSI colors
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


# ─── Mock adapters ─────────────────────────────────────────────────────


def _mock_identifier_manowar(query: str, classification: dict) -> list[Branch]:
    """Three plausible candidates for the Manowar lyric attribution query."""
    return [
        Branch("b1", BranchType.HYPOTHESIS, "Kingdom Come (Kings of Metal, 1988)"),
        Branch("b2", BranchType.HYPOTHESIS, "Cycles of Capricorn"),  # confabulation example
        Branch("b3", BranchType.HYPOTHESIS, "Through the Eyes of the Dead (different band)"),
    ]


def _mock_identifier_empty(query: str, classification: dict) -> list[Branch]:
    return []


def _mock_labrador_kingdom_come_wins(branch: Branch) -> Branch:
    """Realistic labrador outcome for the Manowar fixture:
    - Kingdom Come: FOUND, factfact
    - Cycles of Capricorn: DISCONFIRMED, nonfact + correction
    - Through the Eyes: DISCONFIRMED (different band), nonfact
    """
    if branch.branch_id == "b1":
        branch.labrador_status = LabradorStatus.FOUND
        branch.factampel_tier = "factfact"
        branch.citations = ["darklyrics.com", "manowar.com"]
    elif branch.branch_id == "b2":
        branch.labrador_status = LabradorStatus.DISCONFIRMED
        branch.factampel_tier = "nonfact"
        branch.correction = "Kingdom Come (Kings of Metal, 1988)"
    elif branch.branch_id == "b3":
        branch.labrador_status = LabradorStatus.DISCONFIRMED
        branch.factampel_tier = "nonfact"
        branch.correction = "Through the Eyes of the Dead is a Deathcore band, not a Manowar song"
    return branch


def _mock_labrador_all_unknown(branch: Branch) -> Branch:
    """All branches come back NOT_FOUND — tests fallback-message path."""
    branch.labrador_status = LabradorStatus.NOT_FOUND
    branch.factampel_tier = "nullfact"
    return branch


def _mock_labrador_raises(branch: Branch) -> Branch:
    raise RuntimeError("simulated labrador failure")


# ─── Tests ─────────────────────────────────────────────────────────────


def test_no_adapter_degrades_gracefully():
    print(f"\n{_BOLD}[T1]{_RESET} no adapters → degrades to nullfact placeholder")
    register_adapters(identify_branches=None, labrador=None)
    # explicit clear since module-state can persist between tests
    bb._ADAPTERS["identify_branches"] = None
    bb._ADAPTERS["labrador"] = None

    response = run_branch_balanced("any query")
    _check("returns response", response is not None)
    _check("has at least 1 branch", len(response.branches) >= 1)
    _check(
        "branch tier is nullfact",
        response.branches[0].factampel_tier == "nullfact",
        f"got: {response.branches[0].factampel_tier}",
    )
    _check(
        "fallback message emitted (never silent)",
        response.fallback_message is not None,
    )


def test_empty_identifier_degrades():
    print(f"\n{_BOLD}[T2]{_RESET} identifier returns empty → nullfact placeholder")
    register_adapters(identify_branches=_mock_identifier_empty,
                      labrador=_mock_labrador_all_unknown)

    response = run_branch_balanced("any query")
    _check("at least 1 branch (never empty)", len(response.branches) >= 1)
    _check(
        "branch tier is nullfact",
        response.branches[0].factampel_tier == "nullfact",
    )
    _check("fallback message emitted", response.fallback_message is not None)


def test_manowar_fixture_factfact_wins():
    print(f"\n{_BOLD}[T3]{_RESET} Manowar fixture → Kingdom Come wins as primary")
    register_adapters(identify_branches=_mock_identifier_manowar,
                      labrador=_mock_labrador_kingdom_come_wins)

    response = run_branch_balanced(
        "welches Manowar-Lied: 'the rightful are waiting but not all are rightful'?"
    )
    _check("3 branches returned", len(response.branches) == 3)
    _check(
        "primary is b1 (Kingdom Come)",
        response.primary_branch_id == "b1",
        f"got: {response.primary_branch_id}",
    )
    _check(
        "b1 has factfact tier",
        response.branches[0].factampel_tier == "factfact",
    )
    _check(
        "b1 has citations",
        len(response.branches[0].citations) >= 1,
    )
    _check(
        "b2 has correction (confabulation → corrected)",
        response.branches[1].correction is not None,
    )
    _check(
        "no fallback message (something WAS found)",
        response.fallback_message is None,
    )


def test_all_nullfact_emits_fallback():
    print(f"\n{_BOLD}[T4]{_RESET} all branches NOT_FOUND → fallback message present")
    register_adapters(identify_branches=_mock_identifier_manowar,
                      labrador=_mock_labrador_all_unknown)

    response = run_branch_balanced("any query")
    _check("3 branches still returned (never silenced)",
           len(response.branches) == 3)
    _check(
        "all branches nullfact",
        all(b.factampel_tier == "nullfact" for b in response.branches),
    )
    _check(
        "primary_branch_id is None (no quality winner)",
        response.primary_branch_id is None,
    )
    _check(
        "fallback message present",
        response.fallback_message is not None,
    )


def test_labrador_exception_marked_as_timeout():
    print(f"\n{_BOLD}[T5]{_RESET} labrador adapter exception → branch marked TIMEOUT")
    register_adapters(identify_branches=_mock_identifier_manowar,
                      labrador=_mock_labrador_raises)

    response = run_branch_balanced("any query")
    _check("3 branches still returned", len(response.branches) == 3)
    _check(
        "all branches marked TIMEOUT",
        all(b.labrador_status == LabradorStatus.TIMEOUT for b in response.branches),
    )
    _check(
        "all branches default to nullfact",
        all(b.factampel_tier == "nullfact" for b in response.branches),
    )
    _check(
        "notes contain exception trace",
        all("labrador exception" in (b.notes or "") for b in response.branches),
    )


def test_render_balanced_text_includes_all_branches():
    print(f"\n{_BOLD}[T6]{_RESET} render shows ALL branches with per-branch tier")
    register_adapters(identify_branches=_mock_identifier_manowar,
                      labrador=_mock_labrador_kingdom_come_wins)

    response = run_branch_balanced("manowar query")
    text = render_balanced_text(response)

    _check("render includes b1 text", "Kingdom Come" in text)
    _check("render includes b2 text", "Cycles of Capricorn" in text)
    _check("render includes b3 text", "Through the Eyes" in text)
    _check("render shows factfact tier", "factfact" in text)
    _check("render shows nonfact tier", "nonfact" in text)
    _check("render shows correction", "correction:" in text)
    _check("render shows ★ primary marker", "★" in text)


def test_max_branches_cap():
    print(f"\n{_BOLD}[T7]{_RESET} max_branches caps over-eager identifier")
    def many(query, classification):
        return [Branch(f"b{i}", BranchType.HYPOTHESIS, f"branch {i}") for i in range(20)]
    register_adapters(identify_branches=many,
                      labrador=_mock_labrador_all_unknown)
    response = run_branch_balanced("any", max_branches=5)
    _check("capped at 5 branches", len(response.branches) == 5,
           f"got: {len(response.branches)}")


# ─── Runner ────────────────────────────────────────────────────────────


def main() -> int:
    print(f"{_BOLD}M3 — Branch-balanced labradoring · falsifiable benchmark{_RESET}")
    print("=" * 60)

    test_no_adapter_degrades_gracefully()
    test_empty_identifier_degrades()
    test_manowar_fixture_factfact_wins()
    test_all_nullfact_emits_fallback()
    test_labrador_exception_marked_as_timeout()
    test_render_balanced_text_includes_all_branches()
    test_max_branches_cap()

    print()
    print("=" * 60)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}M3 result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
