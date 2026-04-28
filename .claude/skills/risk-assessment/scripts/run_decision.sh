#!/bin/bash
# Run decision engine to aggregate analyzer results.
#
# Usage:
#     scripts/run_decision.sh
#
# Reads PR_NUMBER from state file at tmp/qc-config.yaml
# Updates state with decision and overall_risk

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🎯 Aggregating results and calculating decision..."

PR_NUMBER=$(python3 "$SCRIPT_DIR/state.py" get tmp/qc-config.yaml pr_number)

# Run decision engine
python3 "$SCRIPT_DIR/decision_engine.py" "$PR_NUMBER" --output "artifacts/pr-analyses/pr-${PR_NUMBER}-analysis.md"

if [[ $? -ne 0 ]]; then
  echo "❌ Decision engine failed"
  exit 1
fi

# Validate final analysis
python3 "$SCRIPT_DIR/frontmatter.py" validate pr-analysis "artifacts/pr-analyses/pr-${PR_NUMBER}-analysis.md"

if [[ $? -ne 0 ]]; then
  echo "❌ Final analysis validation failed"
  exit 1
fi

# Extract decision for state
DECISION=$(python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); from frontmatter import read; fm, _ = read('artifacts/pr-analyses/pr-${PR_NUMBER}-analysis.md'); print(fm['decision'])")
OVERALL_RISK=$(python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); from frontmatter import read; fm, _ = read('artifacts/pr-analyses/pr-${PR_NUMBER}-analysis.md'); print(fm['overall_risk'])")

# Update state
python3 "$SCRIPT_DIR/state.py" set tmp/qc-config.yaml decision="$DECISION" overall_risk="$OVERALL_RISK"

echo "✓ Decision: $DECISION (Risk: $OVERALL_RISK/100)"
