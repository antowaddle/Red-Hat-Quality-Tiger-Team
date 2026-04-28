#!/bin/bash
# Report final results to user (unless headless mode).
#
# Usage:
#     scripts/report_results.sh
#
# Reads HEADLESS and PR_NUMBER from state file at tmp/qc-config.yaml

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

HEADLESS=$(python3 "$SCRIPT_DIR/state.py" get tmp/qc-config.yaml headless)

if [[ "$HEADLESS" != "True" ]]; then
  PR_NUMBER=$(python3 "$SCRIPT_DIR/state.py" get tmp/qc-config.yaml pr_number)

  echo ""
  echo "✅ Risk assessment complete for PR #$PR_NUMBER"
  echo ""
  echo "Results available at:"
  echo "  artifacts/pr-analyses/pr-${PR_NUMBER}-analysis.md"
fi
