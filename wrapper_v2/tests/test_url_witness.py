"""url_witness — falsifiable tests for ungrounded-URL detection.

Production fixture from task #171 (D-Ticket query): fabricated URL
"https://www.d-festival.de/" graded 🟢 quasifact. Detector must classify
as ungrounded → tier cap nullfact.

Run via: python3 -m wrapper_v2.tests.test_url_witness
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.pipeline.url_witness import (
    extract_urls,
    normalize_url,
    classify_url_claim,
    has_ungrounded_url,
)


_GREEN = "\033[92m"
_RED = "\033[91m"
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


def test_t1_extract_urls():
    print(f"\n{_BOLD}[T1]{_RESET} extract_urls - basic patterns")
    _check("empty -> []", extract_urls("") == [])
    _check("none -> []", extract_urls(None) == [])

    urls = extract_urls("Siehe https://example.com fuer mehr.")
    _check("single URL extracted",
           urls == ["https://example.com"], f"got {urls}")

    urls = extract_urls("Quelle: https://www.d-festival.de/.")
    _check("trailing period stripped",
           urls == ["https://www.d-festival.de/"], f"got {urls}")

    urls = extract_urls("[1] https://a.com [2] https://b.com")
    _check("two URLs in sequence",
           urls == ["https://a.com", "https://b.com"], f"got {urls}")

    urls = extract_urls("Markdown [link](https://example.org/path) here.")
    _check("URL inside markdown link extracted",
           "https://example.org/path" in urls, f"got {urls}")


def test_t2_normalize_url():
    print(f"\n{_BOLD}[T2]{_RESET} normalize_url - case + trailing-slash normalization")
    _check("uppercase scheme/domain lowered",
           normalize_url("HTTPS://Example.COM/Path") == "https://example.com/Path",
           f"got {normalize_url('HTTPS://Example.COM/Path')}")
    _check("trailing slash stripped",
           normalize_url("https://example.com/") == "https://example.com")
    _check("root URL stays valid",
           normalize_url("https://example.com") == "https://example.com")
    _check("path preserved (case-sensitive)",
           normalize_url("https://example.com/Foo") == "https://example.com/Foo")


def test_t3_d_ticket_fixture_ungrounded():
    """The exact #171 failure: fabricated d-festival.de URL not in any
    Deutschland-Ticket search-results.
    """
    print(f"\n{_BOLD}[T3]{_RESET} #171 D-Ticket fixture - fabricated URL ungrounded")
    claim = (
        "Hier ist der Offizielle Website-Link: "
        "[https://www.d-festival.de/](https://www.d-festival.de/)"
    )
    real_search_urls = [
        "https://www.bahn.de/angebot/deutschlandticket",
        "https://www.mvg.de/abos-tickets/abos/deutschlandticket.html",
        "https://www.deutschlandticket.de/",
    ]
    r = classify_url_claim(claim, real_search_urls)
    _check("is_url_claim", r["is_url_claim"] is True)
    _check("d-festival.de in claim_urls",
           any("d-festival" in u for u in r["claim_urls"]),
           f"got {r['claim_urls']}")
    _check("d-festival.de is ungrounded",
           any("d-festival" in u for u in r["ungrounded"]))
    _check("suggested_tier_cap == nullfact",
           r["suggested_tier_cap"] == "nullfact",
           f"got {r['suggested_tier_cap']}")


def test_t4_grounded_url_no_cap():
    print(f"\n{_BOLD}[T4]{_RESET} URL in search context -> no tier cap")
    claim = (
        "Du kannst das D-Ticket ueber die MVG kaufen: "
        "https://www.mvg.de/abos-tickets/abos/deutschlandticket.html"
    )
    search = [
        "https://www.mvg.de/abos-tickets/abos/deutschlandticket.html",
        "https://www.bahn.de/angebot/deutschlandticket",
    ]
    r = classify_url_claim(claim, search)
    _check("is_url_claim", r["is_url_claim"])
    _check("URL in_search", len(r["in_search"]) == 1)
    _check("no ungrounded", r["ungrounded"] == [])
    _check("no tier cap (None)", r["suggested_tier_cap"] is None)


def test_t5_no_url_no_op():
    print(f"\n{_BOLD}[T5]{_RESET} claim without URLs -> no-op")
    r = classify_url_claim("Die Zuege treffen sich nach 2.5 Stunden.", [])
    _check("is_url_claim = False", r["is_url_claim"] is False)
    _check("suggested_tier_cap = None", r["suggested_tier_cap"] is None)
    _check("reason = no_urls_in_claim", r["reason"] == "no_urls_in_claim")


def test_t6_no_search_context_all_ungrounded():
    print(f"\n{_BOLD}[T6]{_RESET} URL claim + empty search context -> ungrounded")
    claim = "Siehe https://example.com/page fuer Details."
    for search in [None, [], ["unrelated"]]:
        r = classify_url_claim(claim, search)
        _check(f"search={search!r:20}: tier cap = nullfact",
               r["suggested_tier_cap"] == "nullfact")


def test_t7_partial_grounding():
    """Claim has 2 URLs, only 1 in search -> still ungrounded (tier-cap)."""
    print(f"\n{_BOLD}[T7]{_RESET} mixed grounded + ungrounded URLs -> tier capped")
    claim = (
        "Echte Quelle: https://www.real.com/page und "
        "der Offizielle Link: https://fake.com/page"
    )
    search = ["https://www.real.com/page", "https://www.real.com/other"]
    r = classify_url_claim(claim, search)
    _check("1 URL in_search", len(r["in_search"]) == 1)
    _check("1 URL ungrounded", len(r["ungrounded"]) == 1)
    _check("tier capped (any ungrounded -> cap)",
           r["suggested_tier_cap"] == "nullfact")
    _check("ungrounded contains fake.com",
           any("fake" in u for u in r["ungrounded"]))


def test_t8_normalization_match():
    """Search URL might have trailing slash; claim URL not. Should match."""
    print(f"\n{_BOLD}[T8]{_RESET} normalization handles trivial format diffs")
    claim = "Siehe https://www.real.com/page."
    search = ["https://www.real.com/page/"]
    r = classify_url_claim(claim, search)
    _check("trailing-slash difference matched",
           r["ungrounded"] == [],
           f"ungrounded={r['ungrounded']}")
    _check("no tier cap", r["suggested_tier_cap"] is None)


def test_t9_has_ungrounded_url_convenience():
    print(f"\n{_BOLD}[T9]{_RESET} has_ungrounded_url convenience")
    _check("fabricated -> True",
           has_ungrounded_url("Siehe https://fake.com", []) is True)
    _check("real grounded -> False",
           has_ungrounded_url("Siehe https://real.com", ["https://real.com"]) is False)
    _check("no URLs -> False",
           has_ungrounded_url("Berlin ist Hauptstadt", []) is False)


def test_tA_cite_token_extraction():
    print(f"\n{_BOLD}[TA]{_RESET} extract_cite_indices - basic patterns")
    from wrapper_v2.pipeline.url_witness import extract_cite_indices
    _check("empty -> []", extract_cite_indices("") == [])
    _check("no markers -> []",
           extract_cite_indices("Berlin is the capital.") == [])
    _check("[1] [2] [3] -> [1,2,3]",
           extract_cite_indices("See [1] and [2] also [3].") == [1, 2, 3])
    _check("duplicates dedup",
           extract_cite_indices("[1] [1] [2]") == [1, 2])
    _check("two-digit cites",
           extract_cite_indices("see [12] and [3]") == [3, 12])
    _check("ignored: [abc] [1.5] [N]",
           extract_cite_indices("[abc] [1.5] [N] no cite") == [])


def test_tB_orphan_cite_detection():
    """Operator fixture (#174 D): ice-breaker response had [1]-[5] but
    only N sources in search results."""
    print(f"\n{_BOLD}[TB]{_RESET} orphan cite detection (Issue D)")
    from wrapper_v2.pipeline.url_witness import classify_cite_tokens, has_orphan_cite

    # Claim cites [3] but only 2 sources in search context
    r = classify_cite_tokens("As shown in [3], this works.",
                              ["https://a.com", "https://b.com"])
    _check("has_cites True", r["has_cites"] is True)
    _check("ungrounded [3] flagged", 3 in r["ungrounded_cites"])
    _check("tier capped to nullfact", r["suggested_tier_cap"] == "nullfact")

    # All cites grounded
    r = classify_cite_tokens("See [1] and [2].",
                              ["https://a.com", "https://b.com"])
    _check("all grounded: no cap",
           r["suggested_tier_cap"] is None and r["ungrounded_cites"] == [])

    # No search context at all - any cite is ungrounded
    r = classify_cite_tokens("See [1].", [])
    _check("no search context: cite ungrounded",
           r["suggested_tier_cap"] == "nullfact")

    # No cites at all - no-op
    r = classify_cite_tokens("Berlin is the capital.", ["https://a.com"])
    _check("no cites: no_cite_tokens",
           r["reason"] == "no_cite_tokens" and r["suggested_tier_cap"] is None)

    # has_orphan_cite convenience
    _check("has_orphan_cite True", has_orphan_cite("[5]", ["a"]))
    _check("has_orphan_cite False (grounded)",
           has_orphan_cite("[1]", ["a"]) is False)


def main() -> int:
    print(f"{_BOLD}url_witness - task #171 L3 + #174 D - falsifiable{_RESET}")
    print("=" * 75)

    test_t1_extract_urls()
    test_t2_normalize_url()
    test_t3_d_ticket_fixture_ungrounded()
    test_t4_grounded_url_no_cap()
    test_t5_no_url_no_op()
    test_t6_no_search_context_all_ungrounded()
    test_t7_partial_grounding()
    test_t8_normalization_match()
    test_t9_has_ungrounded_url_convenience()
    test_tA_cite_token_extraction()
    test_tB_orphan_cite_detection()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}url_witness result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
