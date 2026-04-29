#!/bin/bash
# Load context (architecture, tests, Jira) for analyzers.
#
# Usage:
#     scripts/load_context.sh
#
# Reads PR_NUMBER from state file at tmp/qc-config.yaml

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📚 Loading context (architecture, tests, Jira)..."

PR_NUMBER=$(python3 "$SCRIPT_DIR/state.py" get tmp/qc-config.yaml pr_number)

# Fetch/update context repositories
"$SCRIPT_DIR/fetch-context.sh" > tmp/context-paths.json

if [[ $? -ne 0 ]]; then
  echo "⚠️ Warning: Could not fetch context repositories (continuing with cached)"
fi

# Enrich PR with Jira context (optional - requires JIRA_TOKEN)
if [[ -n "${JIRA_TOKEN:-}" ]]; then
  echo "  Enriching with Jira context..."
  python3 "$SCRIPT_DIR/jira_utils.py" enrich-pr "tmp/pr-${PR_NUMBER}.json" --output "tmp/pr-${PR_NUMBER}-enriched.json"

  if [[ $? -eq 0 ]]; then
    mv "tmp/pr-${PR_NUMBER}-enriched.json" "tmp/pr-${PR_NUMBER}.json"
    echo "  ✓ Jira context added"
  else
    echo "  ⚠️ Jira enrichment failed (continuing without Jira context)"
  fi
else
  echo "  ℹ️ Skipping Jira enrichment (JIRA_TOKEN not set)"
fi

# Load and slice context for analyzers
python3 "$SCRIPT_DIR/context_loader.py" "tmp/pr-${PR_NUMBER}.json" tmp/context-paths.json --output-dir tmp/contexts

if [[ $? -ne 0 ]]; then
  echo "❌ Failed to load context"
  exit 1
fi

echo "✓ Context loaded and sliced for analyzers"
