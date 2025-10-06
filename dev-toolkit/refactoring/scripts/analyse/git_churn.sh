#!/usr/bin/env bash
# Git churn analysis for hotspot detection
# Usage: ./git_churn.sh [time-period] [output-file]
# Example: ./git_churn.sh "12 months ago" churn.txt

set -euo pipefail

# Configuration
SINCE="${1:-12 months ago}"
OUTPUT="${2:-dev-toolkit/refactoring/output/churn.txt}"

# Ensure output directory exists
mkdir -p "$(dirname "$OUTPUT")"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository" >&2
    exit 1
fi

echo "Analyzing git churn since: $SINCE"
echo "Output: $OUTPUT"

# Generate churn report
# Format: <count> <file>
git log --since="$SINCE" --name-only --pretty=format: \
    | awk 'NF' \
    | sort \
    | uniq -c \
    | sort -nr \
    > "$OUTPUT"

# Summary
TOTAL_FILES=$(wc -l < "$OUTPUT")
echo "Found $TOTAL_FILES files with changes"

if [ "$TOTAL_FILES" -gt 0 ]; then
    echo ""
    echo "Top 10 most changed files:"
    head -10 "$OUTPUT"
fi

echo ""
echo "✅ Churn analysis complete: $OUTPUT"
