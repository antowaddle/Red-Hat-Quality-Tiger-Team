#!/bin/bash
# Extract PR metadata using gh CLI.
#
# Usage:
#     scripts/extract_pr.sh
#
# Reads PR_NUMBER and REPO from state file at tmp/qc-config.yaml

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📥 Extracting PR metadata..."

PR_NUMBER=$(python3 "$SCRIPT_DIR/state.py" get tmp/qc-config.yaml pr_number)
REPO=$(python3 "$SCRIPT_DIR/state.py" get tmp/qc-config.yaml repo)

# Extract PR metadata, diff, files, commits
python3 "$SCRIPT_DIR/pr_extractor.py" "$PR_NUMBER" "$REPO" --output "tmp/pr-${PR_NUMBER}.json"

if [[ $? -ne 0 ]]; then
  echo "❌ Failed to extract PR metadata"
  exit 1
fi

echo "✓ PR metadata extracted"
