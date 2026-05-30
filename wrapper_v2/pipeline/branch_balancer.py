"""Branch-balanced labradoring — M3 multi-hypothesis response layer.

Per [[labradoring_all_branches_ausgewogen_doctrine]] (operator 2026-05-19):

    "the soph will be 'labradoring all branches ausgewogen' — like you
    do very very good and google.com webface ai does"

Apply labrador-discipline (sniff-and-find OR honest report-not-found,
per [[hammwoehner_haecker_vizor_doctrine]]) across ALL relevant
decision/interpretation/source/hypothesis branches in BALANCED weighting,
without prematurely collapsing the hypothesis-space. Each branch carries
its own factampel-tier (per R0 spec) — most-probable-branch AND
alternatives all reported.

Composes with the foundation triplet:
  - R0 (docs/R0_factfact_color_line_schematic.md) — verdict-axis per branch
  - verify/three_witness.py — tier-assignment via tribunal
  - factampel_emit.py — per-claim emission (each branch is a claim)

Differentiator vs Claude/Google-AI-overview (operator-noted exemplars):
  Both Claude and Google show branches but DON'T tier them
  factfact/quasifact/nullfact. wrapper v2 = branches + per-branch tier.

This module is the orchestrator. Heavy callables (branch-identification
via LLM, three-witness tribunal) are adapter-injected so the module
stays testable without network/LLM. Same wiring pattern as
three_witness.py.

Doctrine anchors:
  - [[labradoring_all_branches_ausgewogen_doctrine]] — kernel
  - [[hammwoehner_haecker_vizor_doctrine]] — labrador-discipline + not-found IS a finding
  - [[1455xl_chassis_goal_driven_funnel]] — HAMMERANTWORT funnel
  - [[fyifact_category_7_labrador_shows_what_master_missed]] — labrador
    can surface what the master-classifier missed
  - [[death_penalty_void]] — never collapse to silence; always report
    branches even if all nullfact
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Callable, Optional


# ─── Enums ─────────────────────────────────────────────────────────────


class BranchType(enum.Enum):
    """Kind of branch in the hypothesis-space.

    HYPOTHESIS: alternative possible answers to a fact-lookup query
                (e.g. "Kingdom Come" vs "Through the Eyes of the Dead"
                for the Manowar lyric attribution).
    INTERPRETATION: alternative readings of an ambiguous query.
    SOURCE: alternative authoritative sources to consult.
    DECISION: alternative decisions/actions in an open-ended query.
    """

    HYPOTHESIS = "hypothesis"
    INTERPRETATION = "interpretation"
    SOURCE = "source"
    DECISION = "decision"


class LabradorStatus(enum.Enum):
    """Per-branch labrador-discipline outcome.

    UNRESOLVED:  not yet labradored (initial state).
    FOUND:       branch supported by evidence (search returned positive).
    NOT_FOUND:   branch labradored, no evidence found (honest report,
                 NOT silent skip — per labrador-discipline doctrine).
    DISCONFIRMED: branch labradored, evidence CONTRADICTS it.
    TIMEOUT:     labrador-call timed out, status unknown.
    """

    UNRESOLVED = "unresolved"
    FOUND = "found"
    NOT_FOUND = "not_found"
    DISCONFIRMED = "disconfirmed"
    TIMEOUT = "timeout"


# Factampel-tier names from R0 spec. String-type kept for forward-compat
# with the canonical R0 taxonomy without an enum-coupling here.
FactampelTier = str  # one of: factfact|quasifact|maybefact|quasinonfact|nonfact|nullfact|definitional|performative


# ─── Data classes ──────────────────────────────────────────────────────


@dataclass
class Branch:
    """A single labradored hypothesis-branch.

    Invariant: every branch carries (a) text, (b) labrador-status,
    (c) factampel-tier once labradored. No silently-dropped branches.
    """

    branch_id: str
    branch_type: BranchType
    text: str
    weight: float = 1.0  # ausgewogen weight; default equal across branches
    labrador_status: LabradorStatus = LabradorStatus.UNRESOLVED
    factampel_tier: Optional[FactampelTier] = None
    citations: list[str] = field(default_factory=list)
    correction: Optional[str] = None  # if branch DISCONFIRMED, what's the corrected value?
    notes: Optional[str] = None


@dataclass
class BalancedResponse:
    """Output of a branch-balanced labradoring pass.

    Contains all branches with their per-branch verdicts. Even if
    every branch ended up nullfact, this struct REPORTS them all —
    silence is forbidden per [[death_penalty_void]].
    """

    query: str
    branches: list[Branch]
    primary_branch_id: Optional[str] = None  # highest-tier+weight if any
    fallback_message: Optional[str] = None  # set iff no branch is FOUND


# ─── Adapter protocol ──────────────────────────────────────────────────


# Branch-identifier: query -> candidate branches (no labradoring yet).
# Real implementation calls an LLM with a "list 3-5 hypotheses" prompt;
# tests inject a mock returning fixed branches.
BranchIdentifier = Callable[[str, dict], list[Branch]]


# Labrador: per-branch sniff-and-find. Returns Branch with status
# + tier + citations populated. Real implementation calls
# verify/three_witness.run_tribunal(); tests inject a mock.
LabradorAdapter = Callable[[Branch], Branch]


# Module-level adapter registry. Production code calls register_adapters()
# at startup; tests inject per-test mocks.
_ADAPTERS: dict[str, Optional[Callable]] = {
    "identify_branches": None,
    "labrador": None,
}


def register_adapters(
    identify_branches: Optional[BranchIdentifier] = None,
    labrador: Optional[LabradorAdapter] = None,
) -> None:
    """Install adapters. Pass None to leave one untouched."""
    if identify_branches is not None:
        _ADAPTERS["identify_branches"] = identify_branches
    if labrador is not None:
        _ADAPTERS["labrador"] = labrador


def _get_adapter(name: str) -> Optional[Callable]:
    return _ADAPTERS.get(name)


# ─── Main orchestrator ─────────────────────────────────────────────────


def run_branch_balanced(
    query: str,
    classification: Optional[dict] = None,
    max_branches: int = 5,
) -> BalancedResponse:
    """Full branch-balanced labradoring pass.

    1. Identify candidate branches via the identify_branches adapter.
    2. Labrador each branch independently (sniff-and-find or honest
       report-not-found).
    3. Assemble BalancedResponse with all branches + per-branch tier.
    4. Mark primary_branch_id = highest-tier branch by weight.
    5. If no branch FOUND, populate fallback_message (NEVER silence).
    """
    classification = classification or {}

    identifier = _get_adapter("identify_branches")
    labrador = _get_adapter("labrador")

    # Step 1 — identify
    if identifier is None:
        # No adapter → degrade to single-branch placeholder.
        # Doctrine: never silence; emit a known-unknowable nullfact branch.
        branches = [
            Branch(
                branch_id="b0",
                branch_type=BranchType.HYPOTHESIS,
                text=query,
                labrador_status=LabradorStatus.NOT_FOUND,
                factampel_tier="nullfact",
                notes="branch-identifier adapter not registered",
            )
        ]
    else:
        branches = list(identifier(query, classification))[:max_branches]

    if not branches:
        # Identifier returned empty: degrade to nullfact placeholder.
        branches = [
            Branch(
                branch_id="b0",
                branch_type=BranchType.HYPOTHESIS,
                text=query,
                labrador_status=LabradorStatus.NOT_FOUND,
                factampel_tier="nullfact",
                notes="branch-identifier returned no branches",
            )
        ]

    # Step 2 — labrador per branch
    if labrador is None:
        for b in branches:
            b.labrador_status = LabradorStatus.UNRESOLVED
            b.factampel_tier = b.factampel_tier or "nullfact"
            b.notes = (b.notes or "") + " | labrador adapter not registered"
    else:
        labradored: list[Branch] = []
        for b in branches:
            try:
                result = labrador(b)
                labradored.append(result if result is not None else b)
            except Exception as exc:  # adapter-failure is itself information
                b.labrador_status = LabradorStatus.TIMEOUT
                b.factampel_tier = b.factampel_tier or "nullfact"
                b.notes = (b.notes or "") + f" | labrador exception: {exc!r}"
                labradored.append(b)
        branches = labradored

    # Step 3+4 — assemble; pick primary
    primary = _pick_primary(branches)

    # Step 5 — fallback message if nothing FOUND
    fallback = None
    if not any(b.labrador_status == LabradorStatus.FOUND for b in branches):
        fallback = (
            "No branch returned a confirmed finding. "
            "All hypotheses are reported below with their honest "
            "not-found / disconfirmed / uncertain status."
        )

    return BalancedResponse(
        query=query,
        branches=branches,
        primary_branch_id=primary,
        fallback_message=fallback,
    )


def _pick_primary(branches: list[Branch]) -> Optional[str]:
    """Pick highest-confidence branch as primary for display.

    Priority order (highest to lowest):
      1. FOUND + tier in (factfact, quasifact)
      2. FOUND + any tier
      3. UNRESOLVED + tier in (factfact, quasifact)
      4. None (no winner; all branches are weak)
    """
    strong_tiers = {"factfact", "quasifact"}

    def rank(b: Branch) -> tuple[int, float]:
        score = 0
        if b.labrador_status == LabradorStatus.FOUND:
            score += 100
        if b.factampel_tier in strong_tiers:
            score += 10
        return (score, b.weight)

    if not branches:
        return None
    best = max(branches, key=rank)
    if rank(best) == (0, best.weight):
        return None  # no branch passes any quality threshold
    return best.branch_id


# ─── Rendering ─────────────────────────────────────────────────────────


def render_balanced_text(response: BalancedResponse) -> str:
    """Plain-text render of a balanced response.

    Used by tests + as reference for UI-rendering. Production UI
    renders per branch with factampel color-line per R0 §3.
    """
    lines: list[str] = []
    lines.append(f"Query: {response.query}")
    lines.append("")

    if response.fallback_message:
        lines.append(f"[fallback] {response.fallback_message}")
        lines.append("")

    primary_id = response.primary_branch_id
    for b in response.branches:
        marker = "★" if b.branch_id == primary_id else "·"
        tier = b.factampel_tier or "?"
        status = b.labrador_status.value
        lines.append(f"  {marker} [{tier}|{status}] {b.text}")
        if b.correction:
            lines.append(f"      correction: {b.correction}")
        if b.citations:
            lines.append(f"      citations: {', '.join(b.citations)}")
        if b.notes:
            lines.append(f"      notes: {b.notes}")
    return "\n".join(lines)


# ─── Module API summary ────────────────────────────────────────────────


__all__ = [
    "Branch",
    "BranchType",
    "LabradorStatus",
    "FactampelTier",
    "BalancedResponse",
    "register_adapters",
    "run_branch_balanced",
    "render_balanced_text",
]
