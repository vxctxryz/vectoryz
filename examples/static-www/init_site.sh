#!/usr/bin/env bash
# init_site.sh — fill the {{PLACEHOLDERS}} with YOUR values, get a deployable
# static-www-site out. Per [[smartfaul]]: one script, one input file, done.
#
# Usage:
#   1. Copy site.config.example → site.config
#   2. Edit site.config with your values
#   3. Run: ./init_site.sh
#   4. Output: ./_output/  — ready to rsync to your web-root
#
# {{YOUR_PROJECT_NAME}} static-site init — plug-and-play

set -euo pipefail

CONFIG="${1:-site.config}"
OUTPUT="${OUTPUT:-./_output}"

if [[ ! -f "$CONFIG" ]]; then
    echo "✗ Config not found: $CONFIG"
    echo "  Copy site.config.example → site.config first."
    exit 1
fi

# Load config (simple KEY=VALUE format)
declare -A SUBS
while IFS='=' read -r key value; do
    [[ "$key" =~ ^[[:space:]]*# || -z "$key" ]] && continue
    # Strip surrounding quotes from value if present
    value="${value%\"}"
    value="${value#\"}"
    SUBS["{{${key}}}"]="$value"
done < "$CONFIG"

# Build sed-expression chain
sed_expr=""
for placeholder in "${!SUBS[@]}"; do
    # Escape for sed: backslash, slash, ampersand
    escaped=$(printf '%s\n' "${SUBS[$placeholder]}" | sed 's|[\\/&]|\\&|g')
    sed_expr+=" -e 's|${placeholder}|${escaped}|g'"
done

# Process each HTML file
rm -rf "$OUTPUT"
mkdir -p "$OUTPUT"
for f in *.html; do
    [[ -f "$f" ]] || continue
    eval "sed $sed_expr '$f' > '$OUTPUT/$f'"
    echo "  ✓ $f → $OUTPUT/$f"
done

# Detect remaining unsubstituted placeholders
echo
echo "→ Checking for unsubstituted placeholders..."
remaining=$(grep -rho '{{[A-Z_]*}}' "$OUTPUT" 2>/dev/null | sort -u || true)
if [[ -n "$remaining" ]]; then
    echo "⚠ Unsubstituted placeholders found (add to your $CONFIG):"
    echo "$remaining"
else
    echo "  ✓ All placeholders substituted."
fi
echo
echo "→ Output ready at: $OUTPUT"
echo "  Next: rsync -avz $OUTPUT/ user@yourserver:/var/www/yoursite/"
