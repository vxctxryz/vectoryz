#!/usr/bin/env bash
# ops/cookie_audit.sh — pre-publish cookie/storage audit
# ====================================================
# Greps for ALL cookie-emission + browser-storage patterns across vectoryz
# codebase. Designed as MANDATORY gate before MIT-publish or holodome-deploy.
#
# Per [[incident_2026_05_22_brosselfrei_cookie]] — self-found contradiction
# between datenschutz.html "bröselfrei" claim and wrapper Set-Cookie emission.
# This script catches the same class of bug pre-publish.
#
# Per audit-open-door + bröselfrei doctrine: public-statement = code-reality.
#
# Exit codes:
#   0 = audit-clean (only-expected emissions found)
#   1 = unexpected emissions found → BLOCK deploy
#
# Usage:
#   ./ops/cookie_audit.sh
#   ./ops/cookie_audit.sh --verbose
#   ./ops/cookie_audit.sh --live    # also curl-check live vectoryz.de

set -uo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
VERBOSE="${VERBOSE:-0}"
LIVE_CHECK="${LIVE_CHECK:-0}"
EXIT_CODE=0

for arg in "$@"; do
    case "$arg" in
        --verbose) VERBOSE=1 ;;
        --live)    LIVE_CHECK=1 ;;
    esac
done

echo "=== vectoryz cookie/storage AUDIT ==="
echo "  REPO_ROOT: ${REPO_ROOT}"
echo

# ---------------------------------------------------------------------------
# A. BACKEND (Python wrapper) — Set-Cookie emission paths
# ---------------------------------------------------------------------------
echo "--- A. Backend Python: Set-Cookie patterns ---"
BACKEND_HITS=$(grep -rEni \
    "set-cookie|set_cookie\(|send_header.*[Cc]ookie|response\.cookies\[" \
    "${REPO_ROOT}/wrapper_v2/" \
    "${REPO_ROOT}/benchmark_cc/wrapper_cc.py" \
    2>/dev/null | grep -v "Max-Age=0" || true)

if [[ -n "$BACKEND_HITS" ]]; then
    echo "  ⚠  Set-Cookie emission patterns found (review each):"
    echo "$BACKEND_HITS" | sed 's/^/    /'
    # Check if all are part of the delete-instruction
    if echo "$BACKEND_HITS" | grep -q "Set-Cookie.*vctz_session"; then
        # Check the actual line is a delete-instruction (Max-Age=0)
        DELETE_OK=$(grep -A 1 "set_session_cookie" \
            "${REPO_ROOT}/benchmark_cc/wrapper_cc.py" 2>/dev/null \
            | grep -c "Max-Age=0" || true)
        if [[ "$DELETE_OK" -gt 0 ]]; then
            echo "  ✓  vctz_session emission is DELETE-instruction (Max-Age=0) — OK"
        else
            echo "  ✗  vctz_session emission is NOT delete-only — BLOCK"
            EXIT_CODE=1
        fi
    else
        echo "  ✗  Unexpected Set-Cookie pattern — BLOCK"
        EXIT_CODE=1
    fi
else
    echo "  ✓ no Set-Cookie emission patterns found"
fi
echo

# ---------------------------------------------------------------------------
# B. FRONTEND (HTML/JS) — document.cookie / localStorage / sessionStorage
# ---------------------------------------------------------------------------
echo "--- B. Frontend HTML/JS: storage-API patterns ---"
STATIC_DIRS=$(find "${REPO_ROOT}" -maxdepth 2 -type d -name "static-www-*" 2>/dev/null)
if [[ -z "$STATIC_DIRS" ]]; then
    echo "  (no static-www-* dirs found, skipping)"
else
    # 1. document.cookie writes — should be ZERO
    DOC_COOKIE=$(grep -rEni "document\.cookie\s*=" $STATIC_DIRS 2>/dev/null || true)
    if [[ -n "$DOC_COOKIE" ]]; then
        echo "  ✗  document.cookie writes found — BLOCK:"
        echo "$DOC_COOKIE" | sed 's/^/    /' | head -10
        EXIT_CODE=1
    else
        echo "  ✓ document.cookie writes: 0"
    fi

    # 2. localStorage — should match approved-list only
    LS_HITS=$(grep -rEni "localStorage\.setItem" $STATIC_DIRS 2>/dev/null || true)
    if [[ -n "$LS_HITS" ]]; then
        # Approved keys: vctz-theme (theme-preference)
        UNAPPROVED=$(echo "$LS_HITS" | grep -v "vctz-theme" || true)
        if [[ -n "$UNAPPROVED" ]]; then
            echo "  ✗  Unapproved localStorage keys — BLOCK:"
            echo "$UNAPPROVED" | sed 's/^/    /' | head -10
            EXIT_CODE=1
        else
            HITS_COUNT=$(echo "$LS_HITS" | wc -l)
            echo "  ✓ localStorage.setItem: ${HITS_COUNT} hits, all approved key 'vctz-theme'"
        fi
    else
        echo "  ✓ localStorage.setItem: 0"
    fi

    # 3. sessionStorage — should be ZERO unless added to approved list
    SS_HITS=$(grep -rEni "sessionStorage\.setItem" $STATIC_DIRS 2>/dev/null || true)
    if [[ -n "$SS_HITS" ]]; then
        echo "  ✗  sessionStorage.setItem found — BLOCK (no approved sessionStorage uses):"
        echo "$SS_HITS" | sed 's/^/    /' | head -10
        EXIT_CODE=1
    else
        echo "  ✓ sessionStorage.setItem: 0"
    fi

    # 4. indexedDB — flag if present
    IDB_HITS=$(grep -rEni "indexedDB\|IDBKeyRange\|IDBDatabase" $STATIC_DIRS 2>/dev/null || true)
    if [[ -n "$IDB_HITS" ]]; then
        echo "  ✗  indexedDB references found — BLOCK:"
        echo "$IDB_HITS" | sed 's/^/    /' | head -5
        EXIT_CODE=1
    else
        echo "  ✓ indexedDB: 0"
    fi

    # 5. meta http-equiv Set-Cookie (deprecated but possible)
    META_COOKIE=$(grep -rEni "<meta\s+http-equiv=[\"']?Set-Cookie" $STATIC_DIRS 2>/dev/null || true)
    if [[ -n "$META_COOKIE" ]]; then
        echo "  ✗  meta http-equiv=Set-Cookie found — BLOCK:"
        echo "$META_COOKIE" | sed 's/^/    /' | head -5
        EXIT_CODE=1
    else
        echo "  ✓ meta http-equiv Set-Cookie: 0"
    fi
fi
echo

# ---------------------------------------------------------------------------
# C. THIRD-PARTY trackers — these MUST be zero
# ---------------------------------------------------------------------------
echo "--- C. Third-party trackers ---"
if [[ -n "$STATIC_DIRS" ]]; then
    TRACKERS=$(grep -rEni \
        "google-analytics|googletagmanager|gtag\(|ga\.js|facebook\.net|fbq\(|doubleclick|hotjar|matomo|piwik|cloudflare-insights|<iframe.*src=.*track" \
        $STATIC_DIRS 2>/dev/null || true)
    if [[ -n "$TRACKERS" ]]; then
        echo "  ✗  3rd-party tracker references found — BLOCK:"
        echo "$TRACKERS" | sed 's/^/    /' | head -10
        EXIT_CODE=1
    else
        echo "  ✓ no 3rd-party trackers found"
    fi
else
    echo "  (no static dirs to scan)"
fi
echo

# ---------------------------------------------------------------------------
# D. LIVE check (optional, --live) — verify production wrapper
# ---------------------------------------------------------------------------
if [[ "$LIVE_CHECK" == "1" ]]; then
    echo "--- D. Live production wrapper check ---"
    # Static page
    LIVE_STATIC=$(curl -sI --max-time 5 https://vectoryz.de 2>/dev/null \
        | grep -i "set-cookie" || true)
    if [[ -n "$LIVE_STATIC" ]]; then
        echo "  ⚠  static page emits Set-Cookie:"
        echo "$LIVE_STATIC" | sed 's/^/    /'
        # Check if it's delete-instruction
        if echo "$LIVE_STATIC" | grep -q "Max-Age=0"; then
            echo "  ✓  is delete-instruction — OK"
        else
            echo "  ✗  is NOT delete-instruction — BLOCK"
            EXIT_CODE=1
        fi
    else
        echo "  ✓ vectoryz.de static: no Set-Cookie"
    fi

    # API POST (will 400 with empty body, but check headers)
    LIVE_API=$(curl -sI --max-time 5 -X POST \
        https://vectoryz.de/api/chat/new \
        -H "Content-Type: application/json" -d '{}' 2>/dev/null \
        | grep -i "set-cookie" || true)
    if [[ -n "$LIVE_API" ]]; then
        echo "  ⚠  /api/chat/new emits Set-Cookie on 400:"
        echo "$LIVE_API" | sed 's/^/    /'
        if echo "$LIVE_API" | grep -q "Max-Age=0"; then
            echo "  ✓  is delete-instruction — OK"
        else
            echo "  ✗  is NOT delete-instruction — BLOCK"
            EXIT_CODE=1
        fi
    else
        echo "  ✓ /api/chat/new: no Set-Cookie on 400"
    fi
    echo
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "=== AUDIT RESULT ==="
if [[ "$EXIT_CODE" == "0" ]]; then
    echo "  ✓ AUDIT PASSED — bröselfrei doctrine intact"
    echo "    All emissions are either NONE or approved (vctz_session DELETE, vctz-theme localStorage)"
else
    echo "  ✗ AUDIT FAILED — unexpected emissions detected"
    echo "    BLOCK deploy. Review hits above + either:"
    echo "      a) update code to match bröselfrei doctrine, OR"
    echo "      b) explicitly approve the new pattern in this script + update datenschutz"
fi

exit $EXIT_CODE
