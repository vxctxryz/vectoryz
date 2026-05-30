"""N9 — Compliance-mask jurisdiction-aware (IP-based).

Per [[compliance_mask_jurisdiction_aware_ip_based]] (operator 2026-05-19):

    "The compliance-mask is EASY (list-enumerable, legally-defined,
     jurisdiction-discrete) — NOT vague-soft-norms like 'be-respectful'.
     First-discriminator: user-IP-location defines mask-shape."

Per-jurisdiction legal-list adapts PRESENTATION/EXAMPLES; truth-layer
(HAMMERANTWORT) stays consistent per truth-sovereignty doctrine. Mask
is boundary-handler at edges, NOT primary-filter.

Three-layer compliance-stack per [[age_layer_fsk_l3_compliance_freischalten]]:
  L1 HAMMERANTWORT      — truth-delivery primary (always runs first)
  L2 COMPLIANCE-MASK    — this module (jurisdiction-mask per IP)
  L3 FSK/age-gate       — see pre_filters/age_gate.py

Doctrine anchors:
  - [[compliance_mask_jurisdiction_aware_ip_based]] — kernel
  - [[age_layer_fsk_l3_compliance_freischalten]] — L1/L2/L3 stack ordering
  - [[death_penalty_void]] — mask never silences truth, only adapts presentation
  - [[triangulate_revise_continue]] — jurisdiction lookup is revisable (IP can be wrong, VPN, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ─── Jurisdiction catalog ──────────────────────────────────────────────


# Per-jurisdiction legal categories (operator-named in memory).
# Each entry: jurisdiction-code → list of categories with brief note +
# how to ADAPT presentation (not what to suppress — that's death-penalty-void).

JURISDICTION_RULES: dict[str, dict] = {
    "DE": {
        "label": "Deutschland",
        "categories": [
            ("volksverhetzung_strafgesetz", "§ 130 StGB — neutral-historical-academic frame OK; do not adopt agitator-voice"),
            ("aufruf_zur_straftat", "§ 111 StGB — describe legality, don't model execution-instructions"),
            ("offenkundigkeit_holocaust_leugnung", "§ 130 III StGB — historical-consensus is factual baseline, no false-balance"),
        ],
        "presentation_notes": (
            "DE/AT/CH-aware: cite gesetzlicher-Rahmen when historic-political topics arise; "
            "no need to add disclaimers on benign content."
        ),
    },
    "AT": {
        "label": "Österreich",
        "categories": [
            ("verbotsgesetz_1947", "Wiederbetätigung-Strafrecht — analog DE §130 III, separate gesetzlicher Anker"),
        ],
        "presentation_notes": "Verbotsgesetz 1947 is the AT-specific anchor; otherwise similar to DE.",
    },
    "CH": {
        "label": "Schweiz",
        "categories": [
            ("rassendiskriminierungsstrafrecht", "Art. 261bis StGB (CH) — analog DE §130, neutral-historical OK"),
        ],
        "presentation_notes": "Art. 261bis is CH-specific anchor.",
    },
    "US": {
        "label": "United States",
        "categories": [
            ("first_amendment_broad_coverage", "very broad speech-coverage; Brandenburg test for incitement"),
            ("true_threats_doctrine", "Watts v. US — context matters"),
            ("defamation_actual_malice", "NYT v. Sullivan for public-figures"),
        ],
        "presentation_notes": (
            "US-aware: less legalese-disclaiming needed for political topics; "
            "cultural-sensitivity still applies (e.g. avoid Karl-Moik-class)."
        ),
    },
    "FR": {
        "label": "France",
        "categories": [
            ("loi_gayssot_1990", "Loi Gayssot — Holocaust-denial criminalized"),
        ],
        "presentation_notes": "Loi Gayssot is FR-specific anchor.",
    },
    "EU_OTHER": {
        "label": "EU (other)",
        "categories": [],
        "presentation_notes": "EU baseline; fall back to GDPR + general European law-of-the-land frame.",
    },
    "UNKNOWN": {
        "label": "Unknown jurisdiction",
        "categories": [],
        "presentation_notes": "No jurisdiction signal; deliver truth, defer jurisdiction-specifics until known.",
    },
}


# ─── IP → jurisdiction (heuristic stub) ────────────────────────────────


# Real implementation uses GeoLite2 + private maxmind DB OR
# IP-API.com on first-use cached. This stub is testable + adapter-injectable
# for production.

CountryCode = str  # "DE" / "AT" / "CH" / "US" / "FR" / etc.


def lookup_jurisdiction_from_ip(ip: str) -> CountryCode:
    """Stub: returns 'UNKNOWN' for any IP unless test injects a real adapter.

    Production wires a GeoLite2/IP-API lookup. Tests can monkey-patch
    or pass an injected adapter via build_mask_for_ip(..., lookup_fn=...).
    """
    # Real impl: lookup via maxmind GeoLite2 mmdb file or IP-API.com
    return "UNKNOWN"


# ─── Result dataclass ──────────────────────────────────────────────────


@dataclass
class ComplianceMask:
    """Output of jurisdiction-aware compliance-mask lookup."""

    jurisdiction: CountryCode
    label: str
    categories: list[tuple[str, str]] = field(default_factory=list)
    presentation_notes: str = ""

    def applies_to(self, claim_categories: set[str]) -> bool:
        """True if claim-categories intersect mask-categories.
        Caller uses this to decide whether to apply mask-presentation."""
        mask_keys = {k for k, _ in self.categories}
        return bool(mask_keys & claim_categories)

    def as_system_msg(self, lang: str = "de") -> str:
        """Render as system-message snippet for sysmsg/composer.py.
        Truth-layer stays consistent; this only adapts presentation."""
        if lang == "de":
            header = f"## Compliance-Mask: {self.label}"
            note = f"Hinweis zur Darstellung: {self.presentation_notes}"
        else:
            header = f"## Compliance mask: {self.label}"
            note = f"Presentation note: {self.presentation_notes}"
        cats = "\n".join(f"  - {k}: {desc}" for k, desc in self.categories)
        return f"{header}\n{note}" + (f"\n\nApplicable categories:\n{cats}" if cats else "")


# ─── Main entries ──────────────────────────────────────────────────────


def build_mask_for_jurisdiction(jurisdiction: CountryCode) -> ComplianceMask:
    """Build a ComplianceMask for a known jurisdiction-code."""
    rules = JURISDICTION_RULES.get(jurisdiction, JURISDICTION_RULES["UNKNOWN"])
    return ComplianceMask(
        jurisdiction=jurisdiction,
        label=rules["label"],
        categories=list(rules["categories"]),
        presentation_notes=rules["presentation_notes"],
    )


def build_mask_for_ip(
    ip: str,
    *,
    lookup_fn=lookup_jurisdiction_from_ip,
) -> ComplianceMask:
    """Lookup jurisdiction from IP + build mask. lookup_fn is injectable."""
    jurisdiction = lookup_fn(ip)
    return build_mask_for_jurisdiction(jurisdiction)


__all__ = [
    "ComplianceMask",
    "JURISDICTION_RULES",
    "build_mask_for_jurisdiction",
    "build_mask_for_ip",
    "lookup_jurisdiction_from_ip",
]
