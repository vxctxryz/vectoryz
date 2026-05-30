"""N14 — Google-classic comparative-audit-runner.

Per [[google_classic_comparative_audit_core_in_labby]] (operator 2026-05-19):

    "Use Google-CLASSIC web (NOT AI-mode/SGE — the traditional blue-
     links list-of-results) as 'grundsolides audit' baseline. Compare
     our labby's output against Google-classic output per query."

Three outcomes:
  (a) AGREEMENT → labby in-line
  (b) labby diverges, GOOGLE correct → fix labby
  (c) labby diverges, GOOGLE bullsh*tting → why? + find truth between/beyond

CRITICAL discipline: every audit-divergence-cause gets 'core-this-in-
LABBY' = baked into labrador-DNA at doctrine-level, NOT one-off-patched
at code-level. Per blank-slate + DNA-architecture doctrines: failure-
modes become inheritable-genotype, not phenotype-tinkering.

Side-channel runner: not part of the synchronous chat-pipeline.
Operator/auditor runs this against a fixture-set of queries during
M-track build to catch drift. Output: divergence-report with
operator-actionable categorization per query.

Doctrine anchors:
  - [[google_classic_comparative_audit_core_in_labby]] — kernel
  - [[factlevel_splice_6band_and_google1998_test]] — google-of-1998 cousin
    (google-classic is procedural-fourth-witness, google-1998 is wayback-fifth)
  - [[hammwoehner_haecker_vizor_doctrine]] — labrador not warrior
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Callable, Optional


# ─── Verdict enum ──────────────────────────────────────────────────────


class AuditVerdict(enum.Enum):
    """Per-query comparison outcome."""

    AGREE = "agree"                       # labby + google agree → labby in-line
    LABBY_WRONG = "labby_wrong"           # labby diverges, google correct → fix labby
    GOOGLE_WRONG = "google_wrong"         # labby diverges, google wrong → why?
    BOTH_DIVERGE = "both_diverge"         # neither matches expected/operator-verified
    LABBY_ABSENT = "labby_absent"         # labby returned nothing
    GOOGLE_ABSENT = "google_absent"       # google returned nothing
    OPERATOR_REVIEW = "operator_review"   # too-close-to-call automated; needs human


# ─── Adapter protocols ─────────────────────────────────────────────────


# Each adapter takes a query, returns the answer-text (or None on absent).
# Real implementations call the actual systems; tests inject mocks.
LabbyAdapter = Callable[[str], Optional[str]]
GoogleClassicAdapter = Callable[[str], Optional[str]]


# Optional: per-query operator-verified-answer (for known-truth fixtures).
# Used to disambiguate GOOGLE_WRONG vs BOTH_DIVERGE.
OperatorVerifiedAnswer = Optional[str]


# ─── Result dataclasses ────────────────────────────────────────────────


@dataclass
class QueryAuditResult:
    """One-query comparative-audit result."""

    query: str
    verdict: AuditVerdict
    labby_answer: Optional[str] = None
    google_classic_answer: Optional[str] = None
    operator_verified_answer: OperatorVerifiedAnswer = None
    notes: str = ""

    def needs_doctrine_core(self) -> bool:
        """True if this verdict requires baking-into-labrador-DNA (per kernel)."""
        return self.verdict in (AuditVerdict.LABBY_WRONG, AuditVerdict.GOOGLE_WRONG,
                                AuditVerdict.BOTH_DIVERGE)


@dataclass
class AuditRunReport:
    """Aggregate report of one audit-run across many queries."""

    queries_total: int = 0
    counts: dict = field(default_factory=dict)  # AuditVerdict-value → count
    per_query: list[QueryAuditResult] = field(default_factory=list)

    def needs_doctrine_review_count(self) -> int:
        return sum(1 for r in self.per_query if r.needs_doctrine_core())


# ─── Core comparator (testable without network) ────────────────────────


def compare_one(
    query: str,
    labby_answer: Optional[str],
    google_classic_answer: Optional[str],
    *,
    operator_verified: OperatorVerifiedAnswer = None,
    similarity_threshold: float = 0.6,
) -> QueryAuditResult:
    """Compare two answers for one query, return verdict.

    similarity_threshold: 0.0-1.0 substring/token-overlap min for AGREE.
    Real implementation can swap in better semantic similarity. Stub
    here uses simple normalized-token-set overlap (Jaccard-ish).
    """
    if labby_answer is None and google_classic_answer is None:
        v = AuditVerdict.OPERATOR_REVIEW
        notes = "both adapters returned None"
    elif labby_answer is None:
        v = AuditVerdict.LABBY_ABSENT
        notes = "labby returned no answer"
    elif google_classic_answer is None:
        v = AuditVerdict.GOOGLE_ABSENT
        notes = "google_classic returned no answer"
    else:
        sim = _token_similarity(labby_answer, google_classic_answer)
        if sim >= similarity_threshold:
            v = AuditVerdict.AGREE
            notes = f"similarity {sim:.2f} >= threshold {similarity_threshold}"
        elif operator_verified:
            # Operator-truth lets us disambiguate
            l_match = _token_similarity(labby_answer, operator_verified) >= similarity_threshold
            g_match = _token_similarity(google_classic_answer, operator_verified) >= similarity_threshold
            if l_match and not g_match:
                v = AuditVerdict.GOOGLE_WRONG
                notes = "labby matches operator-truth; google diverges"
            elif g_match and not l_match:
                v = AuditVerdict.LABBY_WRONG
                notes = "google matches operator-truth; labby diverges"
            else:
                v = AuditVerdict.BOTH_DIVERGE
                notes = "neither labby nor google match operator-truth"
        else:
            v = AuditVerdict.OPERATOR_REVIEW
            notes = f"labby vs google diverge (sim {sim:.2f}); no operator-truth — needs human"

    return QueryAuditResult(
        query=query,
        verdict=v,
        labby_answer=labby_answer,
        google_classic_answer=google_classic_answer,
        operator_verified_answer=operator_verified,
        notes=notes,
    )


def _token_similarity(a: str, b: str) -> float:
    """Jaccard-ish on lowercase non-whitespace token-sets."""
    ta = set(a.lower().split())
    tb = set(b.lower().split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta | tb), 1)


# ─── Batch runner ──────────────────────────────────────────────────────


def run_audit_batch(
    queries: list[dict],
    *,
    labby: LabbyAdapter,
    google_classic: GoogleClassicAdapter,
    similarity_threshold: float = 0.6,
) -> AuditRunReport:
    """Run audit over a batch of {query, operator_verified?} dicts.

    Returns an AuditRunReport with per-query results + aggregate counts.
    """
    report = AuditRunReport()
    report.counts = {v.value: 0 for v in AuditVerdict}

    for q in queries:
        query_text = q["query"]
        operator_truth = q.get("operator_verified")
        try:
            la = labby(query_text)
        except Exception as exc:
            la = None
        try:
            ga = google_classic(query_text)
        except Exception as exc:
            ga = None
        result = compare_one(
            query_text, la, ga,
            operator_verified=operator_truth,
            similarity_threshold=similarity_threshold,
        )
        report.per_query.append(result)
        report.counts[result.verdict.value] += 1
        report.queries_total += 1

    return report


__all__ = [
    "AuditVerdict",
    "QueryAuditResult",
    "AuditRunReport",
    "LabbyAdapter",
    "GoogleClassicAdapter",
    "compare_one",
    "run_audit_batch",
]
