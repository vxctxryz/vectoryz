"""M5 falsifiable-benchmark — factfact-cache schema + blockchain-like provenance.

Per task #122 + [[factfact_cache_re_labrador_timewindow]].

Verifies:
  - schema initialization
  - put → get round-trip
  - hash-chain (entry_hash + prev_entry_hash) computed + verifiable
  - tamper-detection (verify_chain catches mutations)
  - supersede flow (corrections create new entries, history preserved)
  - TTL by drift-mode (definitional 90d, institutional 7d, convention 30d)
  - should_refresh consults TTL + WEISS-invalidated flag
  - iter_stale yields only TTL-expired or WEISS-flagged entries
  - mark_weiss_invalidated round-trips
  - count() doesn't leak claim content

Run via: python3 -m wrapper_v2.tests.test_m5  (stdlib-only, no PyYAML needed)
Exit-code 0 = all-pass; non-zero = at-least-one-fail.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.cache.factfact_cache import (
    FactfactCache,
    FactfactEntry,
    DRIFT_MODE_DEFINITIONAL,
    DRIFT_MODE_INSTITUTIONAL,
    DRIFT_MODE_CONVENTION,
    DRIFT_MODE_UNKNOWN,
    ttl_for,
)


# ANSI colors
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
    """Return a cache backed by a temp SQLite file (caller cleans up)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return FactfactCache(path, engine_instance="vectoryz_v2_test"), path


def _rm(path: str) -> None:
    try: os.unlink(path)
    except OSError: pass


# ─── Tests ─────────────────────────────────────────────────────────────


def test_schema_init():
    print(f"\n{_BOLD}[T1]{_RESET} fresh DB initializes schema cleanly")
    c, p = _fresh_cache()
    _check("count is 0 on fresh DB", c.count() == 0)
    _check("get unknown returns None", c.get("anything") is None)
    _check("should_refresh on missing claim is True", c.should_refresh("anything") is True)
    _rm(p)


def test_put_get_roundtrip():
    print(f"\n{_BOLD}[T2]{_RESET} put → get round-trip preserves fields")
    c, p = _fresh_cache()
    e1 = c.put(
        "Kingdom Come (Manowar, Kings of Metal 1988)",
        splice_tier="factfact",
        three_witness_result={"operator_confirms": True, "google_1998": True},
        provenance={"sources": ["darklyrics.com", "manowar.com"]},
        drift_mode=DRIFT_MODE_CONVENTION,
    )
    _check("entry_hash populated", bool(e1.entry_hash))
    _check("prev_entry_hash None for first entry", e1.prev_entry_hash is None)
    _check("verified_at set", e1.verified_at > 0)
    _check("verified_by = engine_instance", e1.verified_by == "vectoryz_v2_test")

    got = c.get("Kingdom Come (Manowar, Kings of Metal 1988)")
    _check("get returns entry", got is not None)
    _check("get tier matches", got.splice_tier == "factfact")
    _check("get provenance matches",
           got.provenance.get("sources") == ["darklyrics.com", "manowar.com"])
    _check("count = 1", c.count() == 1)
    _rm(p)


def test_hash_chain_links():
    print(f"\n{_BOLD}[T3]{_RESET} chain: entry N's prev_entry_hash = entry N-1's entry_hash")
    c, p = _fresh_cache()
    e1 = c.put("claim X", "factfact")
    e2 = c.put("claim X", "quasifact", three_witness_result={"updated": True})

    _check("e2.prev_entry_hash == e1.entry_hash",
           e2.prev_entry_hash == e1.entry_hash,
           f"got prev={e2.prev_entry_hash!r}, expected {e1.entry_hash!r}")
    _check("get returns latest (e2)", c.get("claim X").entry_hash == e2.entry_hash)
    history = c.get_history("claim X")
    _check("history has 2 entries", len(history) == 2)
    _check("history[0] is e1", history[0].entry_hash == e1.entry_hash)
    _check("history[1] is e2", history[1].entry_hash == e2.entry_hash)
    _rm(p)


def test_supersede_flag_set_on_old():
    print(f"\n{_BOLD}[T4]{_RESET} putting new entry supersedes old (audit-trail kept)")
    c, p = _fresh_cache()
    e1 = c.put("claim Y", "quasifact")
    e2 = c.put("claim Y", "factfact", three_witness_result={"confirmed": True})

    history = c.get_history("claim Y")
    _check("history has 2 entries", len(history) == 2)
    _check("old entry superseded_by == new entry hash",
           history[0].superseded_by == e2.entry_hash,
           f"got: {history[0].superseded_by}")
    _check("new entry has no superseded_by",
           history[1].superseded_by is None)
    _check("get returns new entry only",
           c.get("claim Y").splice_tier == "factfact")
    _rm(p)


def test_verify_chain_clean_chain():
    print(f"\n{_BOLD}[T5]{_RESET} verify_chain passes for unchained sequence")
    c, p = _fresh_cache()
    c.put("multi-step", "quasifact")
    c.put("multi-step", "factfact")
    c.put("multi-step", "nonfact", provenance={"correction": "was wrong"})
    _check("verify_chain returns True on clean 3-entry chain",
           c.verify_chain("multi-step") is True)
    _rm(p)


def test_verify_chain_catches_tampering():
    print(f"\n{_BOLD}[T6]{_RESET} verify_chain catches in-place mutation")
    c, p = _fresh_cache()
    c.put("tamper-target", "factfact")
    # Tamper: directly mutate claim_text in DB without recomputing hash
    import sqlite3
    conn = sqlite3.connect(p)
    conn.execute("UPDATE factfact_entries SET splice_tier='nonfact' WHERE claim_text='tamper-target'")
    conn.commit()
    conn.close()
    _check("verify_chain returns False after tampering",
           c.verify_chain("tamper-target") is False)
    _rm(p)


def test_ttl_per_drift_mode():
    print(f"\n{_BOLD}[T7]{_RESET} TTL varies by drift-mode per memory:three_drift_modes")
    _check("definitional TTL = 90d", ttl_for(DRIFT_MODE_DEFINITIONAL) == 90 * 86400)
    _check("institutional TTL = 7d", ttl_for(DRIFT_MODE_INSTITUTIONAL) == 7 * 86400)
    _check("convention TTL = 30d", ttl_for(DRIFT_MODE_CONVENTION) == 30 * 86400)
    _check("unknown TTL defaults to 30d", ttl_for(DRIFT_MODE_UNKNOWN) == 30 * 86400)
    _check("unregistered drift-mode falls back to unknown",
           ttl_for("__nope__") == 30 * 86400)


def test_should_refresh_respects_ttl():
    print(f"\n{_BOLD}[T8]{_RESET} should_refresh checks drift-mode TTL")
    c, p = _fresh_cache()
    # Insert entry verified at t=1000
    e = c.put("ttl-test", "factfact", drift_mode=DRIFT_MODE_CONVENTION, now_ts=1000)
    _check("fresh entry (t+1) not stale", c.should_refresh("ttl-test", now_ts=1001) is False)
    _check("entry past TTL (t + 30d + 1) is stale",
           c.should_refresh("ttl-test", now_ts=1000 + 30 * 86400 + 1) is True)
    _rm(p)


def test_weiss_override_marks_stale():
    print(f"\n{_BOLD}[T9]{_RESET} WEISS-override forces should_refresh=True (M7 hook)")
    c, p = _fresh_cache()
    c.put("weiss-target", "factfact", drift_mode=DRIFT_MODE_DEFINITIONAL, now_ts=1000)
    # Default-fresh entry (just-verified, definitional 90d TTL) → not stale
    _check("just-verified not stale", c.should_refresh("weiss-target", now_ts=1001) is False)
    # User says "vectoryz du depp etz such weil ich es WEISS!!!!!"
    flagged = c.mark_weiss_invalidated("weiss-target", now_ts=1002)
    _check("mark_weiss_invalidated returns True", flagged is True)
    _check("post-WEISS should_refresh = True", c.should_refresh("weiss-target", now_ts=1003) is True)
    _check("mark on missing claim returns False",
           c.mark_weiss_invalidated("__missing__") is False)
    _rm(p)


def test_iter_stale_yields_only_expired_and_weiss():
    print(f"\n{_BOLD}[T10]{_RESET} iter_stale enumerates refresh-needed entries (M6 hook)")
    c, p = _fresh_cache()
    # 3 entries, varying staleness
    c.put("fresh-conv", "factfact", drift_mode=DRIFT_MODE_CONVENTION, now_ts=1000)        # not stale
    c.put("old-inst", "factfact", drift_mode=DRIFT_MODE_INSTITUTIONAL, now_ts=1000)       # stale after 7d
    c.put("weiss-flag", "factfact", drift_mode=DRIFT_MODE_DEFINITIONAL, now_ts=1000)      # WEISS-flagged
    c.mark_weiss_invalidated("weiss-flag", now_ts=1500)

    # Query at now = 1000 + 10d (10 days after writes)
    now = 1000 + 10 * 86400
    stale_texts = {e.claim_text for e in c.iter_stale(now_ts=now)}
    _check("old-inst is stale (7d < 10d)", "old-inst" in stale_texts)
    _check("weiss-flag is stale (WEISS override)", "weiss-flag" in stale_texts)
    _check("fresh-conv not stale (30d TTL not reached)",
           "fresh-conv" not in stale_texts,
           f"got stale set: {stale_texts}")
    _rm(p)


def test_count_aggregate_only():
    print(f"\n{_BOLD}[T11]{_RESET} count() returns int, no claim-content leak")
    c, p = _fresh_cache()
    c.put("a", "factfact")
    c.put("b", "quasifact")
    c.put("c", "nonfact")
    n = c.count()
    _check("count = 3 entries", n == 3)
    _check("count returns int, not dict/list", isinstance(n, int))
    _rm(p)


def test_compute_hash_deterministic():
    print(f"\n{_BOLD}[T12]{_RESET} entry compute_hash is deterministic across runs")
    e = FactfactEntry(
        claim_text="some claim",
        splice_tier="factfact",
        verified_at=12345,
        verified_by="test-engine",
    )
    h1 = e.compute_hash()
    h2 = e.compute_hash()
    _check("same content → same hash", h1 == h2)
    e.splice_tier = "nonfact"
    h3 = e.compute_hash()
    _check("different content → different hash", h3 != h1)


def test_supersede_does_not_break_chain_verify():
    print(f"\n{_BOLD}[T13]{_RESET} setting superseded_by post-write doesn't break verify_chain")
    c, p = _fresh_cache()
    c.put("chain-x", "quasifact")
    c.put("chain-x", "factfact")
    c.put("chain-x", "nonfact")
    _check("verify_chain still True after 2 supersede-updates",
           c.verify_chain("chain-x") is True)
    _rm(p)


# ─── Runner ────────────────────────────────────────────────────────────


def main() -> int:
    print(f"{_BOLD}M5 — Factfact-cache · blockchain-like provenance · falsifiable benchmark{_RESET}")
    print("=" * 75)

    test_schema_init()
    test_put_get_roundtrip()
    test_hash_chain_links()
    test_supersede_flag_set_on_old()
    test_verify_chain_clean_chain()
    test_verify_chain_catches_tampering()
    test_ttl_per_drift_mode()
    test_should_refresh_respects_ttl()
    test_weiss_override_marks_stale()
    test_iter_stale_yields_only_expired_and_weiss()
    test_count_aggregate_only()
    test_compute_hash_deterministic()
    test_supersede_does_not_break_chain_verify()

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}M5 result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
