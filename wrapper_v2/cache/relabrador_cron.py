"""Re-labrador cron — M6 timewindow-since-last delta-search for stale entries.

Per [[factfact_cache_re_labrador_timewindow]] (operator 2026-05-19):

    "maybe all 24hrs recheck (maybe a new song arrived since last
     labradoring-perfect? so in our case search [query] again
     (timewindow 19.May2026 to now of 'now' then) <-- leads to
     're-labrador for timewindow since last'"

Thin shell over M5 factfact_cache's iter_stale() hook. The actual
re-labradoring (search-the-web, run-three-witness, etc.) is adapter-
injected so this module stays testable without network/LLM.

Flow per stale entry:
  1. iter_stale yields entry E (past TTL or WEISS-flagged)
  2. refresher_adapter(E) → new factfact-data (or None if cannot refresh)
  3. cache.put() chains new entry as supersedor of E (audit-trail preserved)
  4. Report counts: checked / refreshed / unchanged / errored

The cron itself (systemd timer, cron entry, etc.) is operator-config-
territory, NOT this module. This module exposes run_relabrador_pass()
as the unit-of-work the scheduler invokes.

Doctrine anchors:
  - [[factfact_cache_re_labrador_timewindow]] — kernel
  - [[hammwoehner_haecker_vizor_doctrine]] — sniff or honest-report
  - [[audit_open_door_doctrine]] — full pass-report logged
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .factfact_cache import FactfactCache, FactfactEntry


# ─── Adapter protocol ──────────────────────────────────────────────────


# Refresher signature: takes the stale entry, returns either:
#   - dict with new {splice_tier, three_witness_result?, provenance?, ...}
#     → cache.put() called, new entry chains
#   - None
#     → entry stays as-is (still stale; will be retried next pass)
RefresherAdapter = Callable[[FactfactEntry], Optional[dict]]


# ─── Report dataclass ──────────────────────────────────────────────────


@dataclass
class RelabradorReport:
    """One re-labrador pass summary."""

    started_at: int = 0
    finished_at: int = 0
    n_stale_total: int = 0
    n_refreshed: int = 0
    n_unchanged: int = 0
    n_errored: int = 0
    errors: list[str] = field(default_factory=list)
    refreshed_claim_ids: list[str] = field(default_factory=list)

    def elapsed_seconds(self) -> int:
        return max(0, self.finished_at - self.started_at)


# ─── Main entry ────────────────────────────────────────────────────────


def run_relabrador_pass(
    cache: FactfactCache,
    refresher: RefresherAdapter,
    *,
    now_ts: Optional[int] = None,
    max_entries: Optional[int] = None,
) -> RelabradorReport:
    """Run one re-labrador pass over stale entries.

    Args:
        cache: M5 FactfactCache instance
        refresher: callable that takes a stale entry and returns refresh-data
                   (or None to skip this entry)
        now_ts: clock override for tests; defaults to time.time()
        max_entries: cap entries processed per pass (None = no cap)

    Returns:
        RelabradorReport with counts + errors
    """
    if now_ts is None:
        now_ts = int(time.time())

    report = RelabradorReport(started_at=now_ts)

    count = 0
    for entry in cache.iter_stale(now_ts=now_ts):
        if max_entries is not None and count >= max_entries:
            break
        count += 1
        report.n_stale_total += 1

        try:
            refresh_data = refresher(entry)
        except Exception as exc:
            report.n_errored += 1
            report.errors.append(f"{entry.claim_id()}: {exc!r}")
            continue

        if refresh_data is None:
            report.n_unchanged += 1
            continue

        # Append new entry — auto-supersedes the stale one
        cache.put(
            claim_text=entry.claim_text,
            splice_tier=refresh_data.get("splice_tier", entry.splice_tier),
            three_witness_result=refresh_data.get("three_witness_result"),
            factfact_3_tests=refresh_data.get("factfact_3_tests"),
            provenance=refresh_data.get("provenance"),
            drift_mode=refresh_data.get("drift_mode", entry.drift_mode),
            off_axis_tag=refresh_data.get("off_axis_tag", entry.off_axis_tag),
            qualifier_tags=refresh_data.get("qualifier_tags", entry.qualifier_tags),
            now_ts=now_ts,
        )
        report.n_refreshed += 1
        report.refreshed_claim_ids.append(entry.claim_id())

    report.finished_at = int(time.time()) if now_ts is None else now_ts
    return report


__all__ = ["RelabradorReport", "RefresherAdapter", "run_relabrador_pass"]
