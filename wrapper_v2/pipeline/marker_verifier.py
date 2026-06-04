"""marker_verifier — post-hoc factampel for inline Tuyuca / Chomsky markers (#193).

The model output may contain inline markers introduced by the persona-router
system message (per #190 Tuyuca-mode + #191 Chomsky C7/C8/C9b + #192 C10):

  [verbatim:<source>]    — verbatim from named source
  [paraphrase:<source>]  — sinngemaess from named source
  [inferred:<premise>]   — derived from named premise
  [hearsay:<source>]     — gelesen, primary not directly checked
  [training-knowledge]   — from training, no source verifiable
  [unsicher]             — self-marked uncertain
  [mechanism:<chain>]    — causal mechanism (Chomsky C7)

This module parses + grades each marker:
  Tier 1 (always, fast, offline): URL format, suspicious-slug, mechanism sanity,
                                  Aktenzeichen-without-suffix detection
  Tier 2 (do_fetch=True, slow):   HEAD-check known domains (NCBI / DOI / etc.)

Returns a VerificationReport that the wrapper can use to:
  - annotate the response with warnings
  - force a retry with corrective prompt
  - strip fabricated parts

Architecture: standalone module, no wrapper dependency. Wrapper calls
verify_markers(model_output) after generation; gets back structured grade.

Per doctrine:
  [[chomsky_2023_problem_clusters]] — C4 source contact + C7 mechanism + C10 falsifiability
  [[tuyuca_evidentiality_doctrine]]  — inline markers are the wrapper-layer Tuyuca
  [[modelfile_minimal_wrapper_first]] — verification lives wrapper-side

Public API:
  extract_markers(text) -> list[Marker]
  verify_markers(text, do_fetch=False, timeout_s=3) -> VerificationReport
"""
from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import List, Optional, Tuple

# ─── marker regex ─────────────────────────────────────────────────────

# Matches [kind:value] or [kind] for valueless markers
_MARKER_KINDS = (
    "verbatim", "paraphrase", "inferred", "hearsay",
    "training-knowledge", "unsicher", "mechanism",
)
_KIND_ALT = "|".join(re.escape(k) for k in _MARKER_KINDS)
_MARKER_RX = re.compile(
    rf"\[({_KIND_ALT})(?::([^\]]+))?\]",
    flags=re.IGNORECASE,
)

# Domain-grade lookup. Known-authoritative domains get high trust;
# known-fabrication-prone domains (Wikipedia for medical) get medium;
# unknown domains get low.
_KNOWN_TIER1_DOMAINS = {
    # primary law sources
    "gesetze-im-internet.de", "landesrecht.thueringen.de",
    "landesrecht.sachsen-anhalt.de", "gesetze-bayern.de", "verkuendung-bayern.de",
    "dejure.org", "rechtsprechung-im-internet.de", "bundesgerichtshof.de",
    "bundesverfassungsgericht.de",
    # medical primary
    "ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov", "cochranelibrary.com",
    "cochrane.org",
    # standards / data
    "doi.org", "arxiv.org", "iso.org", "ietf.org", "w3.org",
    "destatis.de", "bafin.de", "bsi.bund.de",
}
_KNOWN_TIER2_DOMAINS = {
    "wikipedia.org", "de.wikipedia.org", "en.wikipedia.org",
    "anwalt24.de", "fachanwalt.de", "lto.de", "beck-online.de",
    "gelbe-liste.de", "netdoktor.de", "apotheken-umschau.de",
}

# Aktenzeichen pattern: BGH I ZR 123/45 etc. Must have [!]-suffix per R2.
_AZ_RX = re.compile(
    r"\b(BGH|OLG|BVerfG|EuGH|BSG|BAG|BFH)\s+[IVXivx]+\s+[A-Z]{1,3}\s+\d+\s*/\s*\d+",
)

# Suspicious URL slugs: too topic-shaped, contain story-words. The
# e.g. URL/state-of-the-art-X-out-of-thin-air.html case.
_SUSPICIOUS_SLUG_WORDS = {
    "out-of-thin-air", "state-of-the-art", "the-truth-about",
    "everything-you-need-to-know", "this-one-trick", "shocking",
}


# ─── data classes ─────────────────────────────────────────────────────


@dataclass
class Marker:
    kind: str
    value: str
    span: Tuple[int, int]

    def to_dict(self) -> dict:
        return {"kind": self.kind, "value": self.value, "span": list(self.span)}


@dataclass
class MarkerGrade:
    kind: str
    value: str
    grade: str       # "verified" / "unverified" / "fabricated_likely" / "skip" / "malformed"
    confidence: float
    notes: str
    fetch_attempted: bool = False
    fetch_ok: Optional[bool] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VerificationReport:
    markers: List[MarkerGrade] = field(default_factory=list)
    overall_grade: str = "no_markers"   # no_markers / ok / partial / suspect / fail
    overall_confidence: float = 0.0
    summary: str = ""
    az_violations: List[str] = field(default_factory=list)  # Aktenzeichen without [!] suffix

    def to_dict(self) -> dict:
        return {
            "markers": [m.to_dict() for m in self.markers],
            "overall_grade": self.overall_grade,
            "overall_confidence": self.overall_confidence,
            "summary": self.summary,
            "az_violations": self.az_violations,
        }


# ─── extraction ───────────────────────────────────────────────────────


def extract_markers(text: str) -> List[Marker]:
    """Parse all [kind:value] markers from text. Returns list with spans."""
    if not text:
        return []
    out = []
    for m in _MARKER_RX.finditer(text):
        kind = m.group(1).lower()
        value = (m.group(2) or "").strip()
        out.append(Marker(kind=kind, value=value, span=(m.start(), m.end())))
    return out


# ─── URL grading helpers ──────────────────────────────────────────────


def _classify_url(url: str) -> Tuple[str, str]:
    """Return (tier, notes). tier in {'tier1', 'tier2', 'unknown', 'malformed'}."""
    if not url:
        return "malformed", "empty URL"
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return "malformed", "URL parse failed"
    if not parsed.scheme or parsed.scheme not in ("http", "https"):
        return "malformed", f"unsupported scheme: {parsed.scheme or '(none)'}"
    if not parsed.netloc:
        return "malformed", "no netloc"
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    # match by exact or suffix
    for tier_set, tier_name in [(_KNOWN_TIER1_DOMAINS, "tier1"),
                                 (_KNOWN_TIER2_DOMAINS, "tier2")]:
        if host in tier_set or any(host.endswith("." + d) for d in tier_set):
            return tier_name, f"domain={host}"
    return "unknown", f"domain={host} (not in tier1/tier2 lists)"


def _slug_suspicious(url: str) -> Optional[str]:
    """Return a reason if URL slug contains story-shaped suspicious words."""
    if not url:
        return None
    path = urllib.parse.urlparse(url).path.lower()
    for w in _SUSPICIOUS_SLUG_WORDS:
        if w in path:
            return f"slug-word '{w}' is story-shaped (likely-fabricated)"
    return None


def _try_fetch_head(url: str, timeout_s: int = 3) -> bool:
    """HEAD-check a URL. Returns True on 2xx/3xx response, False otherwise.
    Best-effort — any error returns False."""
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "Mozilla/5.0 marker-verifier"})
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            return 200 <= r.status < 400
    except urllib.error.HTTPError as e:
        # 404 / 403 / 410 → not reachable
        return False
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False
    except Exception:
        return False


# ─── per-marker grading ───────────────────────────────────────────────


def _grade_source_marker(marker: Marker, do_fetch: bool, timeout_s: int) -> MarkerGrade:
    """Grade [verbatim:URL], [paraphrase:URL], [hearsay:URL] markers."""
    value = marker.value
    if not value:
        return MarkerGrade(
            kind=marker.kind, value="", grade="malformed",
            confidence=0.0, notes="empty source value",
        )

    # Detect URL vs textual source
    is_url = value.startswith(("http://", "https://")) or "://" in value

    if is_url:
        tier, notes = _classify_url(value)
        suspicious = _slug_suspicious(value)
        if tier == "malformed":
            return MarkerGrade(
                kind=marker.kind, value=value, grade="malformed",
                confidence=0.0, notes=notes,
            )
        if suspicious:
            return MarkerGrade(
                kind=marker.kind, value=value, grade="fabricated_likely",
                confidence=0.2, notes=suspicious,
            )

        # Optional fetch tier
        if do_fetch:
            ok = _try_fetch_head(value, timeout_s=timeout_s)
            if ok:
                return MarkerGrade(
                    kind=marker.kind, value=value,
                    grade="verified" if tier == "tier1" else "unverified",
                    confidence=0.9 if tier == "tier1" else 0.6,
                    notes=f"{notes}; HEAD ok",
                    fetch_attempted=True, fetch_ok=True,
                )
            else:
                return MarkerGrade(
                    kind=marker.kind, value=value, grade="fabricated_likely",
                    confidence=0.2,
                    notes=f"{notes}; HEAD failed (404 or unreachable)",
                    fetch_attempted=True, fetch_ok=False,
                )

        # No-fetch grading
        if tier == "tier1":
            return MarkerGrade(
                kind=marker.kind, value=value, grade="unverified",
                confidence=0.65,
                notes=f"{notes}; URL well-formed, tier1 domain (HEAD not performed)",
            )
        elif tier == "tier2":
            return MarkerGrade(
                kind=marker.kind, value=value, grade="unverified",
                confidence=0.45,
                notes=f"{notes}; URL well-formed, tier2 domain (HEAD not performed)",
            )
        else:  # unknown
            return MarkerGrade(
                kind=marker.kind, value=value, grade="unverified",
                confidence=0.25,
                notes=f"{notes}; URL well-formed but unknown domain",
            )

    # Textual source (book / corpus / etc.) — can't verify offline
    return MarkerGrade(
        kind=marker.kind, value=value, grade="unverified",
        confidence=0.4,
        notes="textual source (not a URL); cannot verify offline",
    )


def _grade_mechanism_marker(marker: Marker) -> MarkerGrade:
    """Grade [mechanism:<chain>] markers — sanity checks."""
    chain = marker.value
    if not chain:
        return MarkerGrade(
            kind="mechanism", value="", grade="malformed",
            confidence=0.0, notes="empty mechanism chain",
        )
    n_chars = len(chain)
    # Heuristics:
    #   < 20 chars  → probably empty / tautological ("ist ein Medikament")
    #   20-200 chars → reasonable causal-step
    #   > 400 chars → paragraph dump, low information density
    if n_chars < 20:
        return MarkerGrade(
            kind="mechanism", value=chain, grade="unverified",
            confidence=0.2,
            notes=f"mechanism chain very short ({n_chars} chars) — likely tautology",
        )
    if n_chars > 400:
        return MarkerGrade(
            kind="mechanism", value=chain, grade="unverified",
            confidence=0.3,
            notes=f"mechanism chain very long ({n_chars} chars) — paragraph dump, low info density",
        )
    # Tautology heuristic: contains "ist ein" / "is a" pattern as primary content
    if re.match(r"^[\w\s]+ ist ein[e]? [\w\s]+\.?$", chain.strip()):
        return MarkerGrade(
            kind="mechanism", value=chain, grade="unverified",
            confidence=0.3,
            notes="mechanism is a definition ('X ist ein Y') — not a causal mechanism",
        )
    return MarkerGrade(
        kind="mechanism", value=chain, grade="unverified",
        confidence=0.6,
        notes=f"mechanism chain reasonable length ({n_chars} chars); content not verified",
    )


def _grade_self_marker(marker: Marker) -> MarkerGrade:
    """Grade [training-knowledge], [unsicher], [inferred:premise] — self-declared."""
    if marker.kind == "training-knowledge":
        return MarkerGrade(
            kind="training-knowledge", value="", grade="skip",
            confidence=0.5,
            notes="self-declared training-knowledge — should trigger search-augmentation",
        )
    if marker.kind == "unsicher":
        return MarkerGrade(
            kind="unsicher", value="", grade="skip",
            confidence=0.7,
            notes="self-declared uncertainty — honest signal",
        )
    if marker.kind == "inferred":
        if not marker.value:
            return MarkerGrade(
                kind="inferred", value="", grade="malformed",
                confidence=0.0,
                notes="empty premise — inference without stated premise",
            )
        return MarkerGrade(
            kind="inferred", value=marker.value, grade="unverified",
            confidence=0.4,
            notes=f"premise '{marker.value[:80]}' — verify premise truth separately",
        )
    return MarkerGrade(
        kind=marker.kind, value=marker.value, grade="malformed",
        confidence=0.0,
        notes=f"unhandled marker kind: {marker.kind}",
    )


# ─── public verification ──────────────────────────────────────────────


def verify_markers(text: str, do_fetch: bool = False,
                   timeout_s: int = 3) -> VerificationReport:
    """Run verification on all markers in text. Returns VerificationReport.

    do_fetch=False (default) → tier-1 offline checks only (URL format,
    domain tier, slug suspicion, mechanism sanity, Aktenzeichen format).
    do_fetch=True → also HEAD-check URLs (slower, network).
    """
    if not text:
        return VerificationReport(overall_grade="no_markers",
                                  summary="empty input text")

    markers = extract_markers(text)
    grades: List[MarkerGrade] = []
    for m in markers:
        if m.kind in ("verbatim", "paraphrase", "hearsay"):
            grades.append(_grade_source_marker(m, do_fetch=do_fetch, timeout_s=timeout_s))
        elif m.kind == "mechanism":
            grades.append(_grade_mechanism_marker(m))
        elif m.kind in ("training-knowledge", "unsicher", "inferred"):
            grades.append(_grade_self_marker(m))
        else:
            grades.append(MarkerGrade(
                kind=m.kind, value=m.value, grade="malformed",
                confidence=0.0, notes=f"unhandled marker kind: {m.kind}",
            ))

    # Aktenzeichen check: any concrete Az without [!] suffix nearby = R2 violation.
    az_violations = []
    for az_match in _AZ_RX.finditer(text):
        # Look in 80-char window after the match for "Anwalt"
        end = az_match.end()
        window = text[end:end + 80]
        if "Anwalt" not in window and "[!]" not in window:
            az_violations.append(az_match.group(0))

    # Overall grading
    if not grades and not az_violations:
        return VerificationReport(
            overall_grade="no_markers",
            summary="no markers found in text",
        )

    grade_counts = {}
    for g in grades:
        grade_counts[g.grade] = grade_counts.get(g.grade, 0) + 1
    n_total = len(grades)
    n_malformed = grade_counts.get("malformed", 0)
    n_fabricated = grade_counts.get("fabricated_likely", 0)
    n_verified = grade_counts.get("verified", 0)
    n_skip = grade_counts.get("skip", 0)
    n_unverified = grade_counts.get("unverified", 0)

    if az_violations:
        overall = "fail"
    elif n_fabricated > 0 or n_malformed >= max(2, n_total // 2):
        overall = "suspect"
    elif n_verified == n_total or (n_verified + n_skip == n_total):
        overall = "ok"
    elif n_verified + n_skip >= n_total * 0.6:
        overall = "ok"
    else:
        overall = "partial"

    avg_conf = sum(g.confidence for g in grades) / max(1, n_total)
    summary_parts = [
        f"{n_total} markers",
        f"verified={n_verified}",
        f"unverified={n_unverified}",
        f"skip={n_skip}",
        f"fabricated_likely={n_fabricated}",
        f"malformed={n_malformed}",
    ]
    if az_violations:
        summary_parts.append(f"AZ-violations={len(az_violations)}")

    return VerificationReport(
        markers=grades,
        overall_grade=overall,
        overall_confidence=round(avg_conf, 2),
        summary=" | ".join(summary_parts),
        az_violations=az_violations,
    )


# ─── CLI for smoke-test ──────────────────────────────────────────────


if __name__ == "__main__":
    import argparse
    import json as _json
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument("text_or_path", nargs="?",
                        help="text to verify, OR path to file (- for stdin)")
    parser.add_argument("--fetch", action="store_true",
                        help="also HEAD-check URLs (network)")
    parser.add_argument("--timeout", type=int, default=3,
                        help="HEAD timeout seconds")
    parser.add_argument("--json", action="store_true",
                        help="output as JSON")
    args = parser.parse_args()

    if args.text_or_path == "-":
        text = sys.stdin.read()
    elif args.text_or_path and len(args.text_or_path) < 200:
        # treat as inline text if short; else as path
        text = args.text_or_path
    elif args.text_or_path:
        from pathlib import Path
        text = Path(args.text_or_path).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    report = verify_markers(text, do_fetch=args.fetch, timeout_s=args.timeout)
    if args.json:
        print(_json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"OVERALL: {report.overall_grade}  conf={report.overall_confidence}")
        print(f"SUMMARY: {report.summary}")
        if report.az_violations:
            print(f"AZ violations ({len(report.az_violations)}):")
            for az in report.az_violations:
                print(f"  - {az}")
        print(f"MARKERS ({len(report.markers)}):")
        for g in report.markers:
            print(f"  [{g.kind}{':' + g.value[:50] if g.value else ''}]"
                  f" → {g.grade} (conf={g.confidence:.2f})")
            print(f"    {g.notes}")
