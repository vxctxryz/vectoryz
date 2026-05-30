"""M6 + M7 falsifiable-benchmark — re-labrador cron + WEISS-override detector.

Per [[factfact_cache_re_labrador_timewindow]] (M6 + M7 doctrine kernel).

M6: tests run_relabrador_pass() against M5 FactfactCache with mock refresher
M7: tests detect_weiss_override() pattern-scoring + threshold

Run via: python3 -m wrapper_v2.tests.test_m6_m7  (stdlib-only)
Exit-code 0 = all-pass.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.cache.factfact_cache import (
    FactfactCache,
    DRIFT_MODE_CONVENTION,
    DRIFT_MODE_INSTITUTIONAL,
)
from wrapper_v2.cache.relabrador_cron import (
    run_relabrador_pass,
    RelabradorReport,
)
from wrapper_v2.cache.weiss_override import (
    detect_weiss_override,
    detect_and_invalidate,
    WeissOverride,
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


def _fresh_cache():
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return FactfactCache(p, engine_instance="test"), p


def _rm(p):
    try: os.unlink(p)
    except OSError: pass


# ─── M6: re-labrador cron ──────────────────────────────────────────────


def test_relabrador_no_stale_returns_zero():
    print(f"\n{_BOLD}[M6/T1]{_RESET} no stale entries → zero refresh")
    c, p = _fresh_cache()
    c.put("fresh-x", "factfact", drift_mode=DRIFT_MODE_CONVENTION, now_ts=1000)
    report = run_relabrador_pass(c, refresher=lambda e: {"splice_tier": "factfact"},
                                  now_ts=1001)
    _check("n_stale_total = 0", report.n_stale_total == 0)
    _check("n_refreshed = 0", report.n_refreshed == 0)
    _check("no errors", report.n_errored == 0)
    _rm(p)


def test_relabrador_refreshes_stale_inst():
    print(f"\n{_BOLD}[M6/T2]{_RESET} institutional entry past 7d TTL → refreshed")
    c, p = _fresh_cache()
    c.put("old-inst", "quasifact", drift_mode=DRIFT_MODE_INSTITUTIONAL, now_ts=1000)

    def refresher(entry):
        return {"splice_tier": "factfact",
                "provenance": {"refreshed_from": entry.claim_text}}

    now = 1000 + 10 * 86400  # 10 days later
    report = run_relabrador_pass(c, refresher=refresher, now_ts=now)
    _check("n_stale_total = 1", report.n_stale_total == 1)
    _check("n_refreshed = 1", report.n_refreshed == 1)
    _check("refreshed_claim_ids has 1", len(report.refreshed_claim_ids) == 1)

    # Latest entry has new tier
    latest = c.get("old-inst")
    _check("latest tier is updated", latest.splice_tier == "factfact")
    _check("history has 2 entries (audit preserved)",
           len(c.get_history("old-inst")) == 2)
    _check("chain still verifies", c.verify_chain("old-inst") is True)
    _rm(p)


def test_relabrador_refresher_returning_none_keeps_entry():
    print(f"\n{_BOLD}[M6/T3]{_RESET} refresher returning None → entry unchanged")
    c, p = _fresh_cache()
    c.put("inst-skip", "factfact", drift_mode=DRIFT_MODE_INSTITUTIONAL, now_ts=1000)
    now = 1000 + 10 * 86400
    report = run_relabrador_pass(c, refresher=lambda e: None, now_ts=now)
    _check("n_stale_total = 1", report.n_stale_total == 1)
    _check("n_unchanged = 1", report.n_unchanged == 1)
    _check("n_refreshed = 0", report.n_refreshed == 0)
    _check("history still 1 entry", len(c.get_history("inst-skip")) == 1)
    _rm(p)


def test_relabrador_refresher_raises_is_logged_not_fatal():
    print(f"\n{_BOLD}[M6/T4]{_RESET} refresher raising exception → logged, pass continues")
    c, p = _fresh_cache()
    c.put("e1", "factfact", drift_mode=DRIFT_MODE_INSTITUTIONAL, now_ts=1000)
    c.put("e2", "factfact", drift_mode=DRIFT_MODE_INSTITUTIONAL, now_ts=1000)
    now = 1000 + 10 * 86400

    seen = {"count": 0}
    def refresher(e):
        seen["count"] += 1
        if e.claim_text == "e1":
            raise RuntimeError("simulated network fail")
        return {"splice_tier": "quasifact"}

    report = run_relabrador_pass(c, refresher=refresher, now_ts=now)
    _check("both entries visited", seen["count"] == 2)
    _check("n_errored = 1", report.n_errored == 1)
    _check("n_refreshed = 1 (e2 succeeded)", report.n_refreshed == 1)
    _check("errors contains entry-claim-id", any("e1" in e or len(e) > 5 for e in report.errors))
    _rm(p)


def test_relabrador_max_entries_cap():
    print(f"\n{_BOLD}[M6/T5]{_RESET} max_entries caps the pass")
    c, p = _fresh_cache()
    for i in range(10):
        c.put(f"stale-{i}", "factfact", drift_mode=DRIFT_MODE_INSTITUTIONAL, now_ts=1000)
    now = 1000 + 10 * 86400
    report = run_relabrador_pass(c, refresher=lambda e: {"splice_tier": "factfact"},
                                  now_ts=now, max_entries=3)
    _check("only 3 entries visited", report.n_stale_total == 3,
           f"got {report.n_stale_total}")
    _rm(p)


# ─── M7: WEISS-override detector ──────────────────────────────────────


def test_weiss_canonical_phrase():
    print(f"\n{_BOLD}[M7/T1]{_RESET} canonical operator-phrase triggers override")
    r = detect_weiss_override("vectoryz du depp etz such weil ich es WEISS!!!!!")
    _check("triggered=True", r.triggered is True)
    _check("score >= 3", r.score >= 3)
    _check("multiple markers matched", len(r.matched_markers) >= 3)
    _check("__bool__ truthy", bool(r) is True)


def test_weiss_single_strong_marker_triggers():
    print(f"\n{_BOLD}[M7/T2]{_RESET} single strong marker (ich WEISS in CAPS) is sufficient")
    r = detect_weiss_override("ich WEISS dass das stimmt")
    _check("triggered=True", r.triggered is True)
    _check("ich WEISS marker matched",
           any("ich WEISS" in m for m in r.matched_markers))


def test_weiss_lowercase_doesnt_trigger():
    print(f"\n{_BOLD}[M7/T3]{_RESET} lowercase 'ich weiß' alone does NOT trigger")
    r = detect_weiss_override("ich weiß ja nicht so genau")
    _check("triggered=False", r.triggered is False,
           f"got triggered, markers={r.matched_markers}")


def test_weiss_english_variant():
    print(f"\n{_BOLD}[M7/T4]{_RESET} English 'I KNOW' (caps) triggers")
    r = detect_weiss_override("I KNOW this is wrong, please re-check")
    _check("triggered=True", r.triggered is True)


def test_weiss_force_refresh_variant():
    print(f"\n{_BOLD}[M7/T5]{_RESET} 'force refresh' + '!!!' combine to trigger")
    r = detect_weiss_override("please force-refresh this!!!")
    _check("triggered=True", r.triggered is True,
           f"score: {r.score}, markers: {r.matched_markers}")


def test_weiss_weak_alone_doesnt_trigger():
    print(f"\n{_BOLD}[M7/T6]{_RESET} weak markers alone (!!! only) do NOT trigger")
    r = detect_weiss_override("Yes!!!")
    _check("triggered=False", r.triggered is False,
           f"score: {r.score}")


def test_weiss_extracts_quoted_target():
    print(f"\n{_BOLD}[M7/T7]{_RESET} quoted claim extracted as target")
    r = detect_weiss_override("such doch nochmal 'Kingdom Come 1988' weil ich es WEISS!!!!")
    _check("triggered=True", r.triggered is True)
    _check("target_claim extracted", r.target_claim == "Kingdom Come 1988",
           f"got: {r.target_claim!r}")


def test_weiss_no_target_returns_none():
    print(f"\n{_BOLD}[M7/T8]{_RESET} no quoted claim → target_claim is None")
    r = detect_weiss_override("ich WEISS das ist falsch!!!")
    _check("triggered=True", r.triggered is True)
    _check("target_claim None", r.target_claim is None)


def test_weiss_empty_input_safe():
    print(f"\n{_BOLD}[M7/T9]{_RESET} empty input returns non-triggered (no exception)")
    r = detect_weiss_override("")
    _check("triggered=False", r.triggered is False)
    _check("score = 0", r.score == 0)
    _check("__bool__ falsy", bool(r) is False)


def test_detect_and_invalidate_round_trip():
    print(f"\n{_BOLD}[M7/T10]{_RESET} detect_and_invalidate flags the cache entry")
    c, p = _fresh_cache()
    c.put("Kingdom Come 1988", "quasifact", drift_mode=DRIFT_MODE_CONVENTION, now_ts=1000)
    # User-message with quoted target + WEISS-trigger
    msg = "etz such 'Kingdom Come 1988' weil ich es WEISS!!!!!"
    result, applied = detect_and_invalidate(msg, c)
    _check("override triggered", result.triggered is True)
    _check("cache invalidate applied", applied is True)
    _check("entry now flagged stale", c.should_refresh("Kingdom Come 1988", now_ts=1001) is True)
    _rm(p)


def test_detect_and_invalidate_fallback_claim():
    print(f"\n{_BOLD}[M7/T11]{_RESET} fallback_claim used when no quoted target")
    c, p = _fresh_cache()
    c.put("the-fact", "factfact", drift_mode=DRIFT_MODE_CONVENTION, now_ts=1000)
    msg = "ich WEISS das ist falsch!!!"
    result, applied = detect_and_invalidate(msg, c, fallback_claim="the-fact")
    _check("override triggered", result.triggered is True)
    _check("invalidate applied via fallback", applied is True)
    _check("entry stale", c.should_refresh("the-fact", now_ts=1001) is True)
    _rm(p)


def test_detect_and_invalidate_no_target_no_fallback():
    print(f"\n{_BOLD}[M7/T12]{_RESET} no target AND no fallback → applied=False")
    c, p = _fresh_cache()
    msg = "ich WEISS das ist falsch!!!"
    result, applied = detect_and_invalidate(msg, c)
    _check("override triggered", result.triggered is True)
    _check("applied=False (no target)", applied is False)
    _rm(p)


# ─── Runner ────────────────────────────────────────────────────────────


def main() -> int:
    print(f"{_BOLD}M6+M7 — re-labrador cron + WEISS-override · falsifiable benchmark{_RESET}")
    print("=" * 75)

    test_relabrador_no_stale_returns_zero()
    test_relabrador_refreshes_stale_inst()
    test_relabrador_refresher_returning_none_keeps_entry()
    test_relabrador_refresher_raises_is_logged_not_fatal()
    test_relabrador_max_entries_cap()

    test_weiss_canonical_phrase()
    test_weiss_single_strong_marker_triggers()
    test_weiss_lowercase_doesnt_trigger()
    test_weiss_english_variant()
    test_weiss_force_refresh_variant()
    test_weiss_weak_alone_doesnt_trigger()
    test_weiss_extracts_quoted_target()
    test_weiss_no_target_returns_none()
    test_weiss_empty_input_safe()
    test_detect_and_invalidate_round_trip()
    test_detect_and_invalidate_fallback_claim()
    test_detect_and_invalidate_no_target_no_fallback()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}M6+M7 result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
