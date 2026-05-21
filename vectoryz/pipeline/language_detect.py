"""
Babel-Cascade Türsteher — language identification for routing.

Per [[babel_cascade_doctrine]]: the first thing any input hits is a tiny,
sub-millisecond language-identifier that picks the mothertongue-lead (P1)
+ the maximum-linguistic-inverse (P2) for the cascade.

Tools (in priority order):
1. FastText lid.176.ftz (9MB, sub-ms, 176 languages, industry-standard)
2. langdetect (Python port of Google's lang-detect, fallback)
3. Heuristic char-frequency (last-ditch fallback if both fail)

The output is ALWAYS the same shape:
  {detected_lang: "de", confidence: 0.97, method: "fasttext"|"langdetect"|"heuristic"}

Per [[propaganda_over_ransomware]] + [[inbaked_implicity_literalism_trap]]:
the lang-detect result is TREATED AS DATA, not as a directive. Downstream code
may override it (operator can pin lang via UI; cookie can sticky-set it).
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Path to the FastText language-id model (downloaded from Meta)
_DEFAULT_LID_PATH = Path(__file__).parent.parent / "models" / "lid.176.ftz"
LID_MODEL_PATH = os.environ.get("BABEL_LID_MODEL_PATH", str(_DEFAULT_LID_PATH))

# Path to the P-matrix routing config
_DEFAULT_P_MATRIX_PATH = Path(__file__).parent.parent / "config" / "babel_p_matrix.json"
P_MATRIX_PATH = os.environ.get("BABEL_P_MATRIX_PATH", str(_DEFAULT_P_MATRIX_PATH))


# Lazy-load singletons
_ft_model = None
_ft_load_attempted = False
_langdetect_ok = None
_p_matrix_cache = None


def _try_load_fasttext():
    """Load fasttext model lazily. Returns model or None if unavailable."""
    global _ft_model, _ft_load_attempted
    if _ft_load_attempted:
        return _ft_model
    _ft_load_attempted = True
    try:
        import fasttext  # type: ignore
        if not os.path.exists(LID_MODEL_PATH):
            return None
        _ft_model = fasttext.load_model(LID_MODEL_PATH)
        return _ft_model
    except Exception:
        return None


def _try_langdetect_available() -> bool:
    """Check if langdetect is importable. Memoized."""
    global _langdetect_ok
    if _langdetect_ok is not None:
        return _langdetect_ok
    try:
        import langdetect  # type: ignore  # noqa: F401
        _langdetect_ok = True
    except Exception:
        _langdetect_ok = False
    return _langdetect_ok


@dataclass
class LangDetectResult:
    lang: str            # ISO-639-1 code: "de", "en", "zh", "ja", "fr", "es", "ru", "pt", "it"
    confidence: float    # 0..1
    method: str          # "fasttext" | "langdetect" | "heuristic" | "fallback"
    raw_label: str = ""  # original label from underlying tool
    reason: str = ""


# ISO-639 normalization: map various output codes to our canonical set
_LANG_NORMALIZE = {
    "zh": "zh", "zh-cn": "zh", "zh-tw": "zh", "cn": "zh",
    "ja": "ja", "jp": "ja",
    "de": "de", "en": "en",
    "ru": "ru",
    "fr": "fr",
    "es": "es",
    "pt": "pt", "pt-br": "pt", "pt-pt": "pt", "br": "pt",
    "it": "it",
}


def _normalize_lang(label: str) -> str:
    """Map various lang-codes to canonical set we route on."""
    if not label:
        return "unknown"
    lo = label.lower().strip()
    # Strip fasttext prefix
    if lo.startswith("__label__"):
        lo = lo[9:]
    return _LANG_NORMALIZE.get(lo, lo)


def _detect_via_fasttext(text: str) -> Optional[LangDetectResult]:
    """Try FastText lid.176 detection. Returns None if model unavailable.

    Uses lower-level model.f.predict() to bypass the numpy-2.x incompatibility
    in fasttext 0.9.3's high-level predict() (copy=False ValueError).
    """
    model = _try_load_fasttext()
    if model is None:
        return None
    try:
        # FastText requires newline-free input
        clean = text.replace("\n", " ").strip()[:1500]
        if not clean:
            return None
        # Lower-level binding: (text, k, threshold, on_unicode_error)
        results = model.f.predict(clean, 1, 0.0, "")
        if not results:
            return LangDetectResult(
                lang="unknown", confidence=0.0, method="fasttext",
                reason="empty_prediction",
            )
        prob, raw = results[0]
        conf = float(min(prob, 1.0))  # fasttext occasionally returns >1.0
        lang = _normalize_lang(raw)
        return LangDetectResult(
            lang=lang, confidence=conf, method="fasttext",
            raw_label=raw, reason="fasttext_lid176",
        )
    except Exception as e:
        return LangDetectResult(
            lang="unknown", confidence=0.0, method="fasttext",
            raw_label="", reason=f"fasttext_error:{str(e)[:60]}",
        )


def _detect_via_langdetect(text: str) -> Optional[LangDetectResult]:
    """Fallback via langdetect (Google's port). Slower, less accurate on short
    text, but no model-file download needed."""
    if not _try_langdetect_available():
        return None
    try:
        from langdetect import detect_langs  # type: ignore
        from langdetect import DetectorFactory  # type: ignore
        DetectorFactory.seed = 0  # deterministic
        clean = text.strip()[:1500]
        if not clean:
            return None
        results = detect_langs(clean)
        if not results:
            return None
        top = results[0]
        lang = _normalize_lang(top.lang)
        return LangDetectResult(
            lang=lang, confidence=float(top.prob), method="langdetect",
            raw_label=top.lang, reason="langdetect_fallback",
        )
    except Exception as e:
        return LangDetectResult(
            lang="unknown", confidence=0.0, method="langdetect",
            raw_label="", reason=f"langdetect_error:{str(e)[:60]}",
        )


# Heuristic char-frequency fallback (last-ditch, only when both tools missing)
_HEURISTIC_HINTS = [
    # (regex, lang, base-confidence-if-match)
    (re.compile(r"[äöüÄÖÜß]"), "de", 0.55),
    (re.compile(r"[一-龥]"), "zh", 0.7),
    (re.compile(r"[ぁ-んァ-ヶ]"), "ja", 0.8),
    (re.compile(r"[а-яА-ЯёЁ]"), "ru", 0.8),
    (re.compile(r"[àâçéèêëïîôûùüÿœæÀÂÇÉÈÊËÏÎÔÛÙÜŸŒÆ]"), "fr", 0.55),
    (re.compile(r"[áéíñóúüÁÉÍÑÓÚÜ¿¡]"), "es", 0.55),
    (re.compile(r"[ãõçÃÕÇáéíóú]"), "pt", 0.5),
    (re.compile(r"[àèéìíòóùÀÈÉÌÍÒÓÙ]"), "it", 0.5),
]


def _detect_via_heuristic(text: str) -> LangDetectResult:
    """Last-ditch char-frequency heuristic — only when both FastText AND
    langdetect are unavailable. Will guess EN if nothing else matches.

    NOT a real lang-detector — exists so the system never crashes on
    missing-tool. Operator should install fasttext + lid.176.ftz for real
    accuracy.
    """
    if not text or not text.strip():
        return LangDetectResult(
            lang="unknown", confidence=0.0, method="heuristic",
            reason="empty_input",
        )
    # Count matches per lang
    scores = {}
    for rx, lang, base in _HEURISTIC_HINTS:
        n = len(rx.findall(text))
        if n > 0:
            scores[lang] = scores.get(lang, 0.0) + base * min(n, 5) / 5.0
    if scores:
        best_lang = max(scores, key=scores.get)
        best_score = min(scores[best_lang], 0.85)
        return LangDetectResult(
            lang=best_lang, confidence=best_score, method="heuristic",
            reason="char_frequency",
        )
    # Fallback: assume EN
    return LangDetectResult(
        lang="en", confidence=0.3, method="heuristic",
        reason="no_diacritics_default_en",
    )


def detect_language(text: str) -> LangDetectResult:
    """Babel-Cascade Türsteher.

    Tries FastText → langdetect → heuristic in order. The first one that
    returns a valid (non-error) result wins. Sub-millisecond on the happy
    path (FastText loaded + cached).

    Empty/whitespace-only input returns lang='unknown' confidence=0.0.
    """
    if not text or not text.strip():
        return LangDetectResult(
            lang="unknown", confidence=0.0, method="fallback",
            reason="empty_input",
        )

    # 1. FastText (best-in-class)
    ft = _detect_via_fasttext(text)
    if ft is not None and ft.lang != "unknown" and ft.confidence >= 0.3:
        return ft

    # 2. langdetect (fallback)
    ld = _detect_via_langdetect(text)
    if ld is not None and ld.lang != "unknown" and ld.confidence >= 0.3:
        return ld

    # 3. heuristic (last-ditch)
    return _detect_via_heuristic(text)


# ---------------------------------------------------------------------------
# P-Matrix routing
# ---------------------------------------------------------------------------

def _load_p_matrix():
    """Lazy-load + cache the babel_p_matrix.json config."""
    global _p_matrix_cache
    if _p_matrix_cache is not None:
        return _p_matrix_cache
    try:
        with open(P_MATRIX_PATH, "r", encoding="utf-8") as f:
            _p_matrix_cache = json.load(f)
    except Exception:
        # Hardcoded fallback if config-file missing
        _p_matrix_cache = {
            "matrices": {
                "de": ["DE", "CN", "EN", "JP", "FR", "ES", "RU"],
                "en": ["EN", "CN", "DE", "JP", "ES", "RU", "FR"],
                "zh": ["CN", "EN", "JP", "DE", "RU", "FR", "ES"],
            },
            "default_chain": ["EN", "CN", "DE", "JP", "ES", "RU", "FR"],
        }
    return _p_matrix_cache


@dataclass
class BabelRoute:
    detected_lang: str
    confidence: float
    method: str
    cascade_chain: list[str]   # ["DE","CN","EN","JP","FR","ES","RU"]
    p1_lead: str               # "DE"
    p2_inverse: str            # "CN"
    matrix_source: str         # which P-matrix entry was used
    raw_label: str = ""        # original fasttext/langdetect label


def get_babel_route(text: str) -> BabelRoute:
    """Combined: detect lang → look up P-matrix → return full routing decision.

    This is the single entry-point for downstream code. Output goes to SSE
    as 'babel_route' event + may be appended to ollama_msgs as a context-flag.
    """
    detection = detect_language(text)
    matrix = _load_p_matrix()
    matrices = matrix.get("matrices", {})
    default = matrix.get("default_chain", ["EN", "CN", "DE", "JP", "ES", "RU", "FR"])

    chain = matrices.get(detection.lang, default)
    matrix_source = detection.lang if detection.lang in matrices else "default"

    return BabelRoute(
        detected_lang=detection.lang,
        confidence=detection.confidence,
        method=detection.method,
        cascade_chain=chain,
        p1_lead=chain[0],
        p2_inverse=chain[1] if len(chain) > 1 else chain[0],
        matrix_source=matrix_source,
        raw_label=detection.raw_label,
    )


def format_babel_route_for_sse(route: BabelRoute) -> dict:
    """Shape for SSE emission to the UI."""
    return {
        "type": "babel_route",
        "detected_lang": route.detected_lang,
        "confidence": round(route.confidence, 3),
        "method": route.method,
        "cascade_chain": route.cascade_chain,
        "p1_lead": route.p1_lead,
        "p2_inverse": route.p2_inverse,
        "matrix_source": route.matrix_source,
    }
