"""possibility_envelope — Chomsky C6 per-faculty category-error detector (#195).

Chomsky 2023: "they are incapable of distinguishing the possible from the
impossible." This module structurally rejects category-errors BEFORE the
tribunal even fires, per L2 faculty (ISCED-F).

First-cut scope (highest stakes):
  F04 Law:        BGB §1-§2385, StGB §1-§358 range; Aktenzeichen format
  F09 Health:     ICD-10 format; PMC ID format; dosage bounds for top drugs
  Universal:      year-anachronism vs AKTUELLES DATUM; percentage 0-100 bounds;
                  physical constant violations (speed of light bound)

Other faculties: pass-through (return EnvelopeReport with no violations
and grade=ok). Extend per-faculty rules as data accumulates.

Public API:
  check_envelope(text, faculty_isced=None, current_year=None) -> EnvelopeReport
  EnvelopeReport.overall in {"ok", "warning", "violation"}

Architecture: standalone module. Wrapper integration deferred — first ship
the grader. Per [[chomsky_2023_problem_clusters]] + [[modelfile_minimal_wrapper_first]].
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Tuple

# ─── data classes ─────────────────────────────────────────────────────


@dataclass
class EnvelopeViolation:
    rule: str            # short slug, e.g. "bgb_section_out_of_range"
    severity: str        # "warning" / "violation"
    span: Tuple[int, int]
    matched_text: str
    explanation: str
    faculty: str         # ISCED-F code, e.g. "F04_business_administration_law"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EnvelopeReport:
    violations: List[EnvelopeViolation] = field(default_factory=list)
    overall: str = "ok"             # ok / warning / violation
    faculty_checked: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    current_year: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "violations": [v.to_dict() for v in self.violations],
            "overall": self.overall,
            "faculty_checked": self.faculty_checked,
            "notes": self.notes,
            "current_year": self.current_year,
        }


# ─── constants ────────────────────────────────────────────────────────

# BGB has 5 books, §§ 1-2385 (current numbering).
# StGB has §§ 1-358 (approximately; some gaps + new sections under e.g. §238).
# Bounds are upper limits; out-of-range = impossible.
_BGB_MAX = 2385
_STGB_MAX = 358

# ICD-10 format: letter + 2 digits, optional .digit + dash + digit
_ICD10_RX = re.compile(r"\b([A-Z])(\d{2})(?:\.(\d{1,2})?)?\b")
_ICD10_BAD_LETTER = set("UO")  # U is reserved; O isn't used in main ICD-10

# PMC IDs: PMC + 6-8 digits. Real range as of 2026 roughly 1-12000000.
_PMC_RX = re.compile(r"\bPMC(\d{4,9})\b")
_PMC_MAX = 12_000_000   # conservative upper bound; real DB query needed for exactness

# BGB / StGB section citations
_BGB_RX = re.compile(r"\bBGB\s*§\s*(\d{1,5})", re.IGNORECASE)
_STGB_RX = re.compile(r"\bStGB\s*§\s*(\d{1,5})", re.IGNORECASE)
_PARAGRAPH_RX = re.compile(r"§\s*(\d{1,5})\s*(BGB|StGB)\b", re.IGNORECASE)

# Aktenzeichen: BGH XII ZR 123/45 — case + roman + letters + numbers/numbers
_AZ_RX = re.compile(
    r"\b(BGH|OLG|BVerfG|EuGH|BSG|BAG|BFH)\s+[IVXivx]+\s+[A-Z]{1,3}\s+(\d+)\s*/\s*(\d+)\b",
)

# Year mentions: "im Jahr 1989" / "in 2030" / "(1949)" — bounded patterns
_YEAR_RX = re.compile(r"\b(?:im\s+Jahr(?:e)?\s+|in\s+|am\s+\d{1,2}\.\s*\w+\s+|\b)((?:19|20|21)\d{2})\b")

# Percentages: "58%" / "-10%" / "5000 Prozent" — sanity check 0-100 range
# (?<![A-Za-z0-9]) replaces \b to allow optional minus sign;
# trailing \b removed because % is non-word and breaks the boundary.
_PCT_RX = re.compile(r"(?<![A-Za-z0-9])(-?\d{1,4}(?:[.,]\d+)?)\s*(?:%|Prozent|percent)")

# Speed of light: well-known mistaken claims
_SPEED_OF_LIGHT_RX = re.compile(
    r"(Lichtgeschwindigkeit|speed of light|c\s*=)\s*(?:ist\s*|=\s*|beträgt\s*|is\s*)?"
    r"(\d+(?:[.,]\d+)?(?:\s*[·*]\s*10\^?\d+)?)\s*(m/s|km/s|km/h|mph)?",
    re.IGNORECASE,
)
# Real value: 299792458 m/s; ~3×10^8 m/s; ~300000 km/s. Anything wildly off = violation.

# Common drug max daily doses (mg/day), adult:
_DRUG_DOSAGE_RX = re.compile(
    r"\b(Paracetamol|Ibuprofen|Aspirin|Acetylsalicyls(?:ä|ae)ure|Diclofenac|Metamizol)\s+"
    r"(?:bis\s+zu\s+|max(?:imal)?\.?\s+|)\s*"
    r"(\d{2,6})\s*(mg|g)\b",
    re.IGNORECASE,
)
_DRUG_MAX_MG_PER_DAY = {
    "paracetamol": 4_000,
    "ibuprofen": 2_400,        # OTC; Rx up to 3200
    "aspirin": 4_000,
    "acetylsalicylsäure": 4_000,
    "acetylsalicylsaeure": 4_000,
    "diclofenac": 150,
    "metamizol": 4_000,
}


# ─── faculty-specific checkers ────────────────────────────────────────


def _check_f04_law(text: str, faculty: str) -> List[EnvelopeViolation]:
    """F04 Law: BGB / StGB section bounds + Aktenzeichen format."""
    out: List[EnvelopeViolation] = []

    # BGB §X
    for m in _BGB_RX.finditer(text):
        n = int(m.group(1))
        if n < 1 or n > _BGB_MAX:
            out.append(EnvelopeViolation(
                rule="bgb_section_out_of_range",
                severity="violation",
                span=(m.start(), m.end()),
                matched_text=m.group(0),
                explanation=f"BGB §§ 1-{_BGB_MAX} existieren; §{n} ist außerhalb des Bereichs",
                faculty=faculty,
            ))

    # § X BGB (other ordering)
    for m in _PARAGRAPH_RX.finditer(text):
        n = int(m.group(1))
        code = m.group(2).upper()
        max_n = _BGB_MAX if code == "BGB" else _STGB_MAX
        if n < 1 or n > max_n:
            out.append(EnvelopeViolation(
                rule=f"{code.lower()}_section_out_of_range",
                severity="violation",
                span=(m.start(), m.end()),
                matched_text=m.group(0),
                explanation=f"{code} §§ 1-{max_n} existieren; §{n} ist außerhalb des Bereichs",
                faculty=faculty,
            ))

    # StGB §X
    for m in _STGB_RX.finditer(text):
        n = int(m.group(1))
        if n < 1 or n > _STGB_MAX:
            out.append(EnvelopeViolation(
                rule="stgb_section_out_of_range",
                severity="violation",
                span=(m.start(), m.end()),
                matched_text=m.group(0),
                explanation=f"StGB §§ 1-{_STGB_MAX} existieren; §{n} ist außerhalb des Bereichs",
                faculty=faculty,
            ))

    # Aktenzeichen format already enforced by marker_verifier;
    # here we just check that any Az number is non-zero (e.g. "BGH I ZR 0/0" suspicious)
    for m in _AZ_RX.finditer(text):
        num = int(m.group(2))
        yr = int(m.group(3))
        if num == 0:
            out.append(EnvelopeViolation(
                rule="aktenzeichen_zero_number",
                severity="warning",
                span=(m.start(), m.end()),
                matched_text=m.group(0),
                explanation="Aktenzeichen mit Nummer 0 — höchstwahrscheinlich Platzhalter, kein echtes Az",
                faculty=faculty,
            ))
        # year sanity: 2-digit year, must be plausible (50 = 1950, 26 = 2026)
        if yr < 0 or yr > 99:
            out.append(EnvelopeViolation(
                rule="aktenzeichen_year_invalid",
                severity="warning",
                span=(m.start(), m.end()),
                matched_text=m.group(0),
                explanation=f"Aktenzeichen-Jahr '{yr}' ist kein gültiges 2-stelliges Jahr",
                faculty=faculty,
            ))

    return out


def _check_f09_health(text: str, faculty: str) -> List[EnvelopeViolation]:
    """F09 Health: ICD-10 format + PMC ID range + dosage bounds."""
    out: List[EnvelopeViolation] = []

    # ICD-10 format check
    for m in _ICD10_RX.finditer(text):
        letter = m.group(1)
        if letter in _ICD10_BAD_LETTER:
            out.append(EnvelopeViolation(
                rule="icd10_invalid_letter",
                severity="warning",
                span=(m.start(), m.end()),
                matched_text=m.group(0),
                explanation=f"ICD-10 verwendet Buchstabe '{letter}' nicht im Hauptcode-Bereich (U reserviert, O ungenutzt)",
                faculty=faculty,
            ))

    # PMC ID range check
    for m in _PMC_RX.finditer(text):
        n = int(m.group(1))
        if n < 1 or n > _PMC_MAX:
            out.append(EnvelopeViolation(
                rule="pmc_id_out_of_range",
                severity="warning",
                span=(m.start(), m.end()),
                matched_text=m.group(0),
                explanation=f"PMC-IDs liegen aktuell unter ~{_PMC_MAX}; PMC{n} ist verdächtig hoch oder ungültig",
                faculty=faculty,
            ))

    # Dosage bound checks
    for m in _DRUG_DOSAGE_RX.finditer(text):
        drug = m.group(1).lower()
        amount_str = m.group(2)
        unit = m.group(3).lower()
        try:
            amount = float(amount_str)
        except ValueError:
            continue
        if unit == "g":
            amount *= 1000.0  # convert g to mg
        max_mg = _DRUG_MAX_MG_PER_DAY.get(drug)
        if max_mg is None:
            continue
        if amount > max_mg * 1.1:  # 10% tolerance for context
            out.append(EnvelopeViolation(
                rule="drug_dosage_above_max",
                severity="violation",
                span=(m.start(), m.end()),
                matched_text=m.group(0),
                explanation=(
                    f"Tagesdosis {m.group(0)} übersteigt die zugelassene "
                    f"Maximaldosis von {max_mg} mg/Tag deutlich"
                ),
                faculty=faculty,
            ))

    return out


def _check_universal(text: str, current_year: int) -> List[EnvelopeViolation]:
    """Faculty-agnostic checks: anachronism, percentage bounds, physical constants."""
    out: List[EnvelopeViolation] = []
    faculty = "universal"

    # Year-future anachronism: "im Jahr 2030 wurde X" — past tense + future year
    # First find year mentions; check past-tense markers near them.
    PAST_MARKERS = (
        "wurde", "war", "starb", "geboren", "veröffentlicht", "gegründet",
        "geschah", "fand statt", "entstand", "passierte",
        "was founded", "was published", "happened", "occurred",
    )
    for m in _YEAR_RX.finditer(text):
        yr = int(m.group(1))
        if yr <= current_year:
            continue
        # Future year mentioned; look for past-tense within +-60 char window
        s = max(0, m.start() - 60)
        e = min(len(text), m.end() + 60)
        window = text[s:e].lower()
        if any(pm in window for pm in PAST_MARKERS):
            out.append(EnvelopeViolation(
                rule="future_year_with_past_tense",
                severity="violation",
                span=(m.start(), m.end()),
                matched_text=m.group(0),
                explanation=(
                    f"Jahr {yr} liegt in der Zukunft (heute: {current_year}); "
                    "kann keinen historischen Vorgang beschreiben"
                ),
                faculty=faculty,
            ))

    # Percentage 0-100 bounds (allow [unsicher] right before)
    for m in _PCT_RX.finditer(text):
        try:
            val = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        # Tolerance: percentages > 100 are valid (e.g. growth rates), but flag
        # for sanity. < 0 always wrong.
        if val < 0:
            out.append(EnvelopeViolation(
                rule="percentage_negative",
                severity="violation",
                span=(m.start(), m.end()),
                matched_text=m.group(0),
                explanation=f"Prozentwert {val} negativ — vermutlich Tippfehler oder Halluzination",
                faculty=faculty,
            ))
        elif val > 1000:  # extremely-suspicious tolerance bound
            out.append(EnvelopeViolation(
                rule="percentage_implausibly_high",
                severity="warning",
                span=(m.start(), m.end()),
                matched_text=m.group(0),
                explanation=(
                    f"Prozentwert {val}% sehr hoch — bei Anteilsangabe verdächtig, "
                    "bei Wachstumsrate möglich"
                ),
                faculty=faculty,
            ))

    # Speed of light: real ≈ 3×10^8 m/s = 299792458 m/s = 299792 km/s
    for m in _SPEED_OF_LIGHT_RX.finditer(text):
        val_str = m.group(2).replace(",", ".")
        unit = (m.group(3) or "m/s").lower()
        try:
            # Handle exponent notation like "3·10^8"
            val_str_norm = val_str.replace("·", "*").replace(" ", "")
            if "*10" in val_str_norm or "*10^" in val_str_norm:
                base, exp = re.split(r"\*10\^?", val_str_norm)
                val = float(base) * (10 ** float(exp))
            else:
                val = float(val_str_norm)
        except (ValueError, IndexError):
            continue
        # Convert to m/s
        if unit == "km/s":
            val *= 1000
        elif unit == "km/h":
            val /= 3.6
        elif unit == "mph":
            val *= 0.44704
        # Sanity bracket: 2×10^8 m/s ≤ c ≤ 4×10^8 m/s
        if val < 2e8 or val > 4e8:
            out.append(EnvelopeViolation(
                rule="speed_of_light_implausible",
                severity="violation",
                span=(m.start(), m.end()),
                matched_text=m.group(0),
                explanation=(
                    f"Lichtgeschwindigkeit als {val:.2e} m/s angegeben; "
                    "physikalisch ist c ≈ 2.998×10^8 m/s"
                ),
                faculty=faculty,
            ))

    return out


# ─── faculty dispatch ─────────────────────────────────────────────────

_FACULTY_CHECKERS = {
    "F04_business_administration_law": _check_f04_law,
    "F09_health_welfare": _check_f09_health,
}


# ─── public API ───────────────────────────────────────────────────────


def check_envelope(text: str, faculty_isced: Optional[str] = None,
                   current_year: Optional[int] = None) -> EnvelopeReport:
    """Check text against possibility envelope per faculty.

    Args:
      text: full model output to check.
      faculty_isced: ISCED-F code (e.g. "F04_business_administration_law").
                     If None, only universal checks run.
      current_year: integer year for anachronism check. Defaults to UTC now.

    Returns EnvelopeReport with per-violation list + overall grade.
    """
    if not text:
        return EnvelopeReport(overall="ok", faculty_checked=faculty_isced,
                              current_year=current_year)

    if current_year is None:
        current_year = datetime.now(timezone.utc).year

    violations: List[EnvelopeViolation] = []

    # Universal checks always run
    violations.extend(_check_universal(text, current_year))

    # Faculty-specific
    notes = []
    if faculty_isced and faculty_isced in _FACULTY_CHECKERS:
        violations.extend(_FACULTY_CHECKERS[faculty_isced](text, faculty_isced))
    elif faculty_isced:
        notes.append(f"no faculty-specific rules for {faculty_isced}; universal only")

    # Overall grade
    if any(v.severity == "violation" for v in violations):
        overall = "violation"
    elif any(v.severity == "warning" for v in violations):
        overall = "warning"
    else:
        overall = "ok"

    return EnvelopeReport(
        violations=violations,
        overall=overall,
        faculty_checked=faculty_isced,
        notes=notes,
        current_year=current_year,
    )


# ─── CLI for smoke-test ──────────────────────────────────────────────


if __name__ == "__main__":
    import argparse
    import json as _json
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument("text_or_path", nargs="?",
                        help="text to check, OR path to file (- for stdin)")
    parser.add_argument("--faculty", default=None,
                        help="ISCED-F code, e.g. F04_business_administration_law")
    parser.add_argument("--year", type=int, default=None,
                        help="override current_year (default: UTC now)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.text_or_path == "-" or not args.text_or_path:
        text = sys.stdin.read()
    elif len(args.text_or_path) < 500 and "\n" not in args.text_or_path:
        text = args.text_or_path
    else:
        from pathlib import Path
        text = Path(args.text_or_path).read_text(encoding="utf-8")

    report = check_envelope(text, faculty_isced=args.faculty,
                            current_year=args.year)
    if args.json:
        print(_json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"OVERALL: {report.overall}")
        print(f"FACULTY: {report.faculty_checked or '(none — universal only)'}")
        print(f"YEAR-NOW: {report.current_year}")
        if report.notes:
            for n in report.notes:
                print(f"  note: {n}")
        print(f"VIOLATIONS ({len(report.violations)}):")
        for v in report.violations:
            print(f"  [{v.severity}] {v.rule}")
            print(f"    matched: {v.matched_text!r}")
            print(f"    explain: {v.explanation}")
