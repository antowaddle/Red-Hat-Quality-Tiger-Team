#!/bin/bash
# Parse and validate arguments for risk-assessment skill.
#
# Usage:
#     source scripts/parse_args.sh "$ARGUMENTS"
#
# Sets these variables in the calling shell:
#     PR_NUMBER, REPO, HEADLESS, DRY_RUN
#
# Exits with error if validation fails.

set -euo pipefail

# Check if dependencies are installed
python3 -c "import yaml; import requests" 2>/dev/null

if [[ $? -ne 0 ]]; then
  echo "❌ Error: Missing Python dependencies"
  echo "Install with: pip3 install -r .claude/skills/risk-assessment/requirements.txt"
  exit 1
fi

# Extract arguments
ARGS="$1"

# Parse PR number (first positional arg)
PR_NUMBER=$(echo "$ARGS" | awk '{print $1}')

# Parse repo (required --repo flag)
REPO=$(echo "$ARGS" | grep -o '\--repo [^ ]*' | awk '{print $2}')

# Parse flags
HEADLESS=false
DRY_RUN=false

if echo "$ARGS" | grep -q '\--headless'; then
  HEADLESS=true
fi

if echo "$ARGS" | grep -q '\--dry-run'; then
  DRY_RUN=true
fi

# Validate required arguments
if [[ -z "$PR_NUMBER" ]]; then
  echo "❌ Error: PR number required"
  echo "Usage: /risk-assessment <pr_number> --repo <owner/name> [--headless] [--dry-run]"
  exit 1
fi

if [[ -z "$REPO" ]]; then
  echo "❌ Error: --repo required"
  echo "Usage: /risk-assessment <pr_number> --repo <owner/name> [--headless] [--dry-run]"
  exit 1
fi

# Initialize state
python3 scripts/state.py init tmp/qc-config.yaml \
  pr_number="$PR_NUMBER" \
  repo="$REPO" \
  headless="$HEADLESS" \
  dry_run="$DRY_RUN"

echo "🚀 Starting risk assessment for PR #$PR_NUMBER in $REPO"
