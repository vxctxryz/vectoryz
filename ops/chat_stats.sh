#!/usr/bin/env bash
# ops/chat_stats.sh — count-only chat statistics from holodome state.db
# ====================================================================
# Queries vectoryz_cc's SQLite state.db on the holodome host for
# AGGREGATE-ONLY chat counts. Returns no IDs, no owner_session,
# no message content, no ciphertext.
#
# Per [[claude_chat_access_discipline]] (2026-05-13):
#   "Claude may decrypt+read vectoryz chats ONLY when explicitly authorized."
#   Count operations on the chats table are NOT chat-reads — they reveal
#   only the number-of-chats, never the content. This script enforces
#   that boundary by allowlisting SELECT COUNT/MIN/MAX only.
#
# Per audit-open-door: the full SQL is visible in this file. No hidden
# queries. Anyone with shell access can audit what this asks.
#
# Usage:
#   ./ops/chat_stats.sh                 # default 7d summary + 24h + total
#   ./ops/chat_stats.sh --days 30       # custom window
#   ./ops/chat_stats.sh --daily         # day-by-day histogram (last 7d)
#   ./ops/chat_stats.sh --help
#
# 2026-05-30 — Benjamin Resch · MIT-License

set -euo pipefail

HOST="${HOST:-root@178.63.104.147}"
KEY="${KEY:-$HOME/42/holodome.key}"
DB="${DB:-/var/lib/vectoryz_cc/state.db}"

DAYS=7
MODE="summary"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --days) DAYS="$2"; shift 2 ;;
        --daily) MODE="daily"; shift ;;
        --help|-h)
            sed -n '/^# ops/,/^# 2026-/p' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *)
            echo "unknown arg: $1 (try --help)" >&2; exit 1 ;;
    esac
done

if [[ ! -f "$KEY" ]]; then
    echo "ERROR: SSH key not found at $KEY" >&2
    exit 1
fi

# ── SQL: aggregates only, no SELECT * — explicit COUNT/MIN/MAX whitelist ──
# Sqlite-CLI flags (-cmd / -header / -column) replace dot-commands so the
# whole payload survives SSH-transport as a single argument.
if [[ "$MODE" == "summary" ]]; then
    SQLITE_FLAGS="-separator '|'"
    SQL="SELECT 'total chats     ', COUNT(*) FROM chats;
SELECT 'last ${DAYS}d (utc)  ', COUNT(*) FROM chats WHERE created_at >= strftime('%s','now','-${DAYS} days');
SELECT 'last 24h (utc)  ', COUNT(*) FROM chats WHERE created_at >= strftime('%s','now','-1 day');
SELECT 'last 1h  (utc)  ', COUNT(*) FROM chats WHERE created_at >= strftime('%s','now','-1 hour');
SELECT 'first chat (utc)', datetime(MIN(created_at),'unixepoch') FROM chats;
SELECT 'last chat  (utc)', datetime(MAX(created_at),'unixepoch') FROM chats;"
elif [[ "$MODE" == "daily" ]]; then
    SQLITE_FLAGS="-header -column"
    SQL="SELECT date(created_at,'unixepoch') AS day_utc, COUNT(*) AS chats
FROM chats
WHERE created_at >= strftime('%s','now','-${DAYS} days')
GROUP BY day_utc
ORDER BY day_utc;"
fi

echo "═══ vectoryz_cc chat-stats (count-only) ═══"
echo "  host : $HOST"
echo "  db   : $DB"
echo "  mode : $MODE (window: last ${DAYS}d)"
echo "  ts   : $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
echo

ssh -i "$KEY" \
    -o StrictHostKeyChecking=no \
    -o ConnectTimeout=10 \
    "$HOST" \
    "sqlite3 $SQLITE_FLAGS $DB \"$SQL\""
