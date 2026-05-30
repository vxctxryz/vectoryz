"""Factfact-cache — M5 blockchain-like provenance cache for verified claims.

Per [[factfact_cache_re_labrador_timewindow]] (operator 2026-05-19):

    "effort will decrease as we will have our own database for the infos
     collected... a blockchain-like thing... all 24hrs recheck...
     when user says 'vectoryz du depp etz such weil ich es WEISS!!!!!'
     dann suchen wir."

Per [[three_drift_modes_of_factfact]]: even Tier-0 factfacts drift along
three orthogonal dimensions (definitional / institutional / convention).
TTL-policy must be drift-mode-aware.

Architecture:
  - SQLite backing (matches state.db production-discipline)
  - Append-only entries (immutable post-write per [[audit_open_door_doctrine]])
  - Each entry references previous-entry-hash → tamper-evident chain
  - Corrections create NEW entries with `superseded_by` pointer (history preserved)
  - `verify_chain()` re-hashes entries to detect tampering
  - `should_refresh()` consults TTL-policy per drift-mode

NOT actual blockchain:
  - no proof-of-work, no distributed consensus
  - just the AUDIT-TRAIL property applied to a local DB
  - any auditor can ask: when verified? by which engine? which witnesses?
    has it been tampered with?

Hooks for M6 (re-labrador cron):
  - `iter_stale(now)` yields entries needing refresh
Hooks for M7 (WEISS-override):
  - `mark_weiss_invalidated(claim_text)` flags entry as needing fresh-search

Doctrine anchors:
  - [[factfact_cache_re_labrador_timewindow]] — kernel
  - [[three_drift_modes_of_factfact]] — drift-aware TTL
  - [[audit_open_door_doctrine]] — full provenance always inspectable
  - [[claude_chat_access_discipline]] — cache-read OK aggregate-only
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager, closing
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterator, Optional


# ─── Drift-mode TTL policy ────────────────────────────────────────────


DRIFT_MODE_DEFINITIONAL = "definitional"   # category-rules change rarely (90d)
DRIFT_MODE_INSTITUTIONAL = "institutional"  # naming/status shifts (7d)
DRIFT_MODE_CONVENTION = "convention"        # counting/partitioning varies (30d)
DRIFT_MODE_UNKNOWN = "unknown"              # default fallback (30d)

DRIFT_TTL_SECONDS = {
    DRIFT_MODE_DEFINITIONAL: 90 * 24 * 3600,
    DRIFT_MODE_INSTITUTIONAL: 7 * 24 * 3600,
    DRIFT_MODE_CONVENTION: 30 * 24 * 3600,
    DRIFT_MODE_UNKNOWN: 30 * 24 * 3600,
}


def ttl_for(drift_mode: str) -> int:
    """Return TTL in seconds for a drift-mode (defaults to UNKNOWN if not registered)."""
    return DRIFT_TTL_SECONDS.get(drift_mode, DRIFT_TTL_SECONDS[DRIFT_MODE_UNKNOWN])


# ─── Entry dataclass ──────────────────────────────────────────────────


@dataclass
class FactfactEntry:
    """One immutable cache entry. Per memory:factfact_cache schema."""

    claim_text: str
    splice_tier: str                            # factfact / quasifact / ... / nullfact
    off_axis_tag: Optional[str] = None          # definitional / performative / etc.
    qualifier_tags: list = field(default_factory=list)
    three_witness_result: dict = field(default_factory=dict)
    factfact_3_tests: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    drift_mode: str = DRIFT_MODE_UNKNOWN
    verified_at: int = 0                        # unix epoch; 0 = "set me"
    verified_by: str = ""                       # engine-instance-hash
    prev_entry_hash: Optional[str] = None       # chain link
    entry_hash: str = ""                        # computed; immutable
    superseded_by: Optional[str] = None         # set when revised
    weiss_invalidated_at: Optional[int] = None  # M7 hook

    def claim_id(self) -> str:
        """Stable hash of claim_text (= cache key)."""
        return hashlib.sha256(self.claim_text.encode("utf-8")).hexdigest()[:16]

    def compute_hash(self) -> str:
        """Compute entry_hash from all content-fields + prev-link.

        Hash domain explicitly excludes:
          - entry_hash itself (avoid circular)
          - superseded_by (mutable supersede-pointer is the EXPLICIT exception
            to immutability; chain-integrity stays intact regardless)
          - weiss_invalidated_at (mutable WEISS flag, same exception)
        """
        payload = {
            "claim_text": self.claim_text,
            "splice_tier": self.splice_tier,
            "off_axis_tag": self.off_axis_tag,
            "qualifier_tags": self.qualifier_tags,
            "three_witness_result": self.three_witness_result,
            "factfact_3_tests": self.factfact_3_tests,
            "provenance": self.provenance,
            "drift_mode": self.drift_mode,
            "verified_at": self.verified_at,
            "verified_by": self.verified_by,
            "prev_entry_hash": self.prev_entry_hash,
        }
        payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


# ─── Schema ───────────────────────────────────────────────────────────


_SCHEMA = """
CREATE TABLE IF NOT EXISTS factfact_entries (
    entry_hash         TEXT PRIMARY KEY,
    claim_id           TEXT NOT NULL,
    claim_text         TEXT NOT NULL,
    splice_tier        TEXT NOT NULL,
    off_axis_tag       TEXT,
    qualifier_tags     TEXT NOT NULL DEFAULT '[]',
    three_witness_json TEXT NOT NULL DEFAULT '{}',
    factfact_3_json    TEXT NOT NULL DEFAULT '{}',
    provenance_json    TEXT NOT NULL DEFAULT '{}',
    drift_mode         TEXT NOT NULL DEFAULT 'unknown',
    verified_at        INTEGER NOT NULL,
    verified_by        TEXT NOT NULL,
    prev_entry_hash    TEXT,
    superseded_by      TEXT,
    weiss_invalidated_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_factfact_claim_id ON factfact_entries(claim_id);
CREATE INDEX IF NOT EXISTS idx_factfact_verified_at ON factfact_entries(verified_at);
CREATE INDEX IF NOT EXISTS idx_factfact_superseded ON factfact_entries(superseded_by);
"""


# ─── Store ────────────────────────────────────────────────────────────


class FactfactCache:
    """SQLite-backed factfact cache with hash-chain provenance."""

    def __init__(self, db_path: str, engine_instance: str = "vectoryz_v2"):
        self.db_path = db_path
        self.engine_instance = engine_instance
        self._init_db()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    @contextmanager
    def _conn(self):
        # check_same_thread=False because cache may be hit from worker-threads
        c = sqlite3.connect(self.db_path, check_same_thread=False)
        try:
            yield c
        finally:
            c.close()

    # ── Writes ────────────────────────────────────────────────────────

    def put(
        self,
        claim_text: str,
        splice_tier: str,
        *,
        three_witness_result: Optional[dict] = None,
        factfact_3_tests: Optional[dict] = None,
        provenance: Optional[dict] = None,
        drift_mode: str = DRIFT_MODE_UNKNOWN,
        off_axis_tag: Optional[str] = None,
        qualifier_tags: Optional[list] = None,
        now_ts: Optional[int] = None,
    ) -> FactfactEntry:
        """Append a new verified entry. Chains to previous-latest if exists.

        If a non-superseded entry already exists for this claim, this new
        entry SUPERSEDES it (the old entry's superseded_by field gets set
        to this new entry's hash; old entry stays in DB for audit-trail).
        """
        if now_ts is None:
            now_ts = int(time.time())

        # Find current latest non-superseded entry (= prev-link for new entry)
        latest = self.get(claim_text)
        prev_hash = latest.entry_hash if latest else None

        entry = FactfactEntry(
            claim_text=claim_text,
            splice_tier=splice_tier,
            off_axis_tag=off_axis_tag,
            qualifier_tags=qualifier_tags or [],
            three_witness_result=three_witness_result or {},
            factfact_3_tests=factfact_3_tests or {},
            provenance=provenance or {},
            drift_mode=drift_mode,
            verified_at=now_ts,
            verified_by=self.engine_instance,
            prev_entry_hash=prev_hash,
        )
        entry.entry_hash = entry.compute_hash()

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO factfact_entries
                  (entry_hash, claim_id, claim_text, splice_tier, off_axis_tag,
                   qualifier_tags, three_witness_json, factfact_3_json,
                   provenance_json, drift_mode, verified_at, verified_by,
                   prev_entry_hash, superseded_by, weiss_invalidated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    entry.entry_hash,
                    entry.claim_id(),
                    entry.claim_text,
                    entry.splice_tier,
                    entry.off_axis_tag,
                    json.dumps(entry.qualifier_tags, ensure_ascii=False),
                    json.dumps(entry.three_witness_result, ensure_ascii=False),
                    json.dumps(entry.factfact_3_tests, ensure_ascii=False),
                    json.dumps(entry.provenance, ensure_ascii=False),
                    entry.drift_mode,
                    entry.verified_at,
                    entry.verified_by,
                    entry.prev_entry_hash,
                ),
            )
            if prev_hash is not None:
                conn.execute(
                    "UPDATE factfact_entries SET superseded_by=? WHERE entry_hash=?",
                    (entry.entry_hash, prev_hash),
                )
            conn.commit()
        return entry

    def mark_weiss_invalidated(self, claim_text: str, now_ts: Optional[int] = None) -> bool:
        """M7 hook: flag latest entry as needing fresh-search (WEISS-override).
        Returns True if an entry was flagged, False if no entry exists yet."""
        if now_ts is None:
            now_ts = int(time.time())
        latest = self.get(claim_text)
        if latest is None:
            return False
        with self._conn() as conn:
            conn.execute(
                "UPDATE factfact_entries SET weiss_invalidated_at=? WHERE entry_hash=?",
                (now_ts, latest.entry_hash),
            )
            conn.commit()
        return True

    # ── Reads ─────────────────────────────────────────────────────────

    def get(self, claim_text: str) -> Optional[FactfactEntry]:
        """Return latest non-superseded entry for this claim (or None)."""
        claim_id = hashlib.sha256(claim_text.encode("utf-8")).hexdigest()[:16]
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM factfact_entries
                WHERE claim_id=? AND superseded_by IS NULL
                ORDER BY verified_at DESC LIMIT 1
                """,
                (claim_id,),
            ).fetchone()
        return _row_to_entry(row) if row else None

    def get_history(self, claim_text: str) -> list[FactfactEntry]:
        """All entries for a claim, oldest first (chain order)."""
        claim_id = hashlib.sha256(claim_text.encode("utf-8")).hexdigest()[:16]
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM factfact_entries WHERE claim_id=? ORDER BY verified_at ASC",
                (claim_id,),
            ).fetchall()
        return [_row_to_entry(r) for r in rows]

    def iter_stale(self, now_ts: Optional[int] = None) -> Iterator[FactfactEntry]:
        """Yield non-superseded entries past their drift-mode TTL.
        Hook for M6 re-labrador cron."""
        if now_ts is None:
            now_ts = int(time.time())
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM factfact_entries WHERE superseded_by IS NULL"
            ).fetchall()
        for row in rows:
            e = _row_to_entry(row)
            ttl = ttl_for(e.drift_mode)
            if now_ts - e.verified_at >= ttl:
                yield e
            elif e.weiss_invalidated_at is not None:
                yield e  # WEISS-override also marks stale

    def should_refresh(self, claim_text: str, now_ts: Optional[int] = None) -> bool:
        """True if entry is missing, stale per TTL, or WEISS-invalidated."""
        if now_ts is None:
            now_ts = int(time.time())
        latest = self.get(claim_text)
        if latest is None:
            return True
        if latest.weiss_invalidated_at is not None:
            return True
        ttl = ttl_for(latest.drift_mode)
        return (now_ts - latest.verified_at) >= ttl

    def count(self) -> int:
        """Total entries (including superseded). Aggregate-only — no leak."""
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM factfact_entries").fetchone()[0]

    # ── Integrity ─────────────────────────────────────────────────────

    def verify_chain(self, claim_text: str) -> bool:
        """Re-hash all entries for a claim and verify chain integrity.

        Returns False if:
          - any entry's stored entry_hash doesn't match recomputed hash
          - any entry's prev_entry_hash doesn't match actual-previous-entry's hash
        """
        history = self.get_history(claim_text)
        prev_hash: Optional[str] = None
        for e in history:
            if e.prev_entry_hash != prev_hash:
                return False
            recomputed = e.compute_hash()
            if recomputed != e.entry_hash:
                return False
            prev_hash = e.entry_hash
        return True


# ─── Row mapping ──────────────────────────────────────────────────────


def _row_to_entry(row) -> FactfactEntry:
    """Map sqlite3.Row tuple → FactfactEntry. Column order matches CREATE TABLE."""
    return FactfactEntry(
        # entry_hash gets set at end
        claim_text=row[2],
        splice_tier=row[3],
        off_axis_tag=row[4],
        qualifier_tags=json.loads(row[5]) if row[5] else [],
        three_witness_result=json.loads(row[6]) if row[6] else {},
        factfact_3_tests=json.loads(row[7]) if row[7] else {},
        provenance=json.loads(row[8]) if row[8] else {},
        drift_mode=row[9],
        verified_at=row[10],
        verified_by=row[11],
        prev_entry_hash=row[12],
        superseded_by=row[13],
        weiss_invalidated_at=row[14],
        entry_hash=row[0],
    )


__all__ = [
    "FactfactCache",
    "FactfactEntry",
    "DRIFT_MODE_DEFINITIONAL",
    "DRIFT_MODE_INSTITUTIONAL",
    "DRIFT_MODE_CONVENTION",
    "DRIFT_MODE_UNKNOWN",
    "DRIFT_TTL_SECONDS",
    "ttl_for",
]
