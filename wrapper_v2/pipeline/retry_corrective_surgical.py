"""pipeline/retry_corrective_surgical — surgical claim-listing for retry.

Phase-2 fix #2 step B (2026-06-01): when tribunal-peek flagged N specific
claims as quasinonfact/nonfact, the retry-prompt should list THOSE
specific claim-texts (not just a count). Model gets exact targets to
fix instead of generic "you have N drifted claims" hint.

Triggering observation: Q4 Wittgenstein §201 test — tribunal correctly
flagged the hallucinated claim "Im Abschnitt 201 des Buches diskutiert
Wittgenstein die Frage, ob das Gesichtsbild eines Baumes zusammengesetzt
ist..." as quasinonfact. But the retry-corrective only said "3 of 8
claims flagged" — didn't list WHICH claims. Retry just paraphrased the
same hallucination because it didn't know which specific claim was the
problem.

Doctrine:
  - [[hammerantwort]] — substance over eloquence
  - [[no_regurgitation_doctrine]] — don't repeat what was refuted
  - [[ehrlich_stumm_doctrine]] — substance OR explicit "weiß ich nicht"

Public API:
  build_surgical_refuted_claims_corrective(claims) -> str
"""

from __future__ import annotations

from typing import Sequence


# Max claims to include in the corrective. Beyond this, signal stops being
# useful (model gets overwhelmed). Operator-observation: 8 is the
# max_tribunals cap so we'll never exceed it, but defense in depth.
_MAX_CLAIMS_IN_CORRECTIVE = 5

# Max chars per claim — keep listing scannable
_MAX_CLAIM_CHARS = 200


def build_surgical_refuted_claims_corrective(
    claims: Sequence[str],
) -> str:
    """Build a corrective text listing specific tribunal-refuted claims.

    Args:
      claims: list of claim-texts that were graded quasinonfact/nonfact

    Returns:
      formatted corrective text (German), or empty string if no claims.
      Caller (build_audit_retry_messages in wrapper_cc.py) inserts the
      returned string at the top of the correctives list.
    """
    if not claims:
        return ""

    # Filter out empty/whitespace claims defensively
    cleaned = [
        (c or "").strip().replace("\n", " ").replace("  ", " ")
        for c in claims
        if c and (c or "").strip()
    ]
    if not cleaned:
        return ""

    n_total = len(cleaned)
    cleaned = cleaned[:_MAX_CLAIMS_IN_CORRECTIVE]

    listing_lines = []
    for i, c in enumerate(cleaned, 1):
        text = c if len(c) <= _MAX_CLAIM_CHARS else c[:_MAX_CLAIM_CHARS].rstrip() + "…"
        listing_lines.append(f'  {i}. "{text}"')
    listing = "\n".join(listing_lines)

    overflow_note = ""
    if n_total > _MAX_CLAIMS_IN_CORRECTIVE:
        overflow_note = (
            f" (zeigt die ersten {_MAX_CLAIMS_IN_CORRECTIVE} "
            f"von {n_total} flagged)"
        )

    return (
        f"- TRIBUNAL-REFUTED CLAIMS (chirurgisch{overflow_note}): "
        f"die folgenden {len(cleaned)} aussagen aus deinem vorigen "
        f"versuch wurden vom tribunal als quasinonfact/nonfact "
        f"eingestuft. Für JEDE dieser aussagen ENTSCHEIDE:\n"
        f"  (a) ersetzen mit verifizierter aussage + quelle, ODER\n"
        f"  (b) aus der antwort entfernen, ODER\n"
        f"  (c) explizit sagen \"ich weiß X nicht zuverlässig\".\n"
        f"NICHT die aussage paraphrasiert wiederholen — das ist die "
        f"falle die der retry-loop sonst dreht.\n"
        f"REFUTIERTE AUSSAGEN:\n"
        f"{listing}"
    )


__all__ = ["build_surgical_refuted_claims_corrective"]
