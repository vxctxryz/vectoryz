"""wrapper_v2/verify — three-witness pipeline + verification helpers per R2 §4.6.

Re-exports from pipeline/* for now. Phase-3 will physically reorganize.

Currently covers:
  - three_witness     (M2 tribunal — operator + claude + google_1998 +
                       google_today, with operator-veto rules)
  - wiki_wortwolke    (Wikipedia wortwolke + snap-connect-graph,
                       5th-witness extension)
  - doublecheck       (pre-emit ground-truth verification gate)

Still pending Phase-3 (D6 unification):
  - wayback           (Google-of-1998 dedicated module, extracted from
                       v1 wayback_search)
  - coverage_check    (consolidated from v1's question_coverage_check)
  - coherence_check   (consolidated from v1's coherence_check + cross-turn)
  - audit_retry       (α-retry, extracted from v1 build_audit_retry_messages)

Doctrine: [[factlevel_splice_6band_and_google1998_test]] +
[[factfact_layer_epistemic_doctrine]] — three-witness operationalizes
the factfact tier per R0 §9.
"""

from wrapper_v2.pipeline.three_witness import (
    WitnessVerdict,
    TribunalResult,
    SUPPORTS, CONTRADICTS, UNCERTAIN, ABSENT,
    run_tribunal,
    register_adapters,
)
from wrapper_v2.pipeline.wiki_wortwolke import (
    search_wikipedia_topic,
    search_and_fetch_summary,
    fetch_wiki_summary,
    fetch_disambig_alternatives,
    format_disambig_for_prompt,
)
from wrapper_v2.pipeline.doublecheck import (
    UnsupportedClaim,
    DoublecheckResult,
    extract_entities,
    find_attribution_claims,
)

__all__ = [
    # three-witness tribunal
    "WitnessVerdict", "TribunalResult",
    "SUPPORTS", "CONTRADICTS", "UNCERTAIN", "ABSENT",
    "run_tribunal", "register_adapters",
    # wiki-wortwolke (5th witness)
    "search_wikipedia_topic", "search_and_fetch_summary",
    "fetch_wiki_summary", "fetch_disambig_alternatives",
    "format_disambig_for_prompt",
    # doublecheck (pre-emit gate)
    "UnsupportedClaim", "DoublecheckResult",
    "extract_entities", "find_attribution_claims",
]
