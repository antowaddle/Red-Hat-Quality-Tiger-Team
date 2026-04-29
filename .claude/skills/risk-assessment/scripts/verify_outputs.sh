#!/bin/bash
# Verify all 4 analyzer outputs exist.
#
# Usage:
#     scripts/verify_outputs.sh <pr_number>
#
# Exits with error if any outputs are missing.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <pr_number>" >&2
  exit 1
fi

PR_NUMBER=$1

echo "Verifying analyzer outputs..."

# Check all 4 analyzer outputs exist
if [[ ! -f "artifacts/risk-findings/risk-${PR_NUMBER}.md" ]]; then
  echo "❌ Risk analyzer failed"
  exit 1
fi

if [[ ! -f "artifacts/test-coverage/test-${PR_NUMBER}.md" ]]; then
  echo "❌ Test validator failed"
  exit 1
fi

if [[ ! -f "artifacts/impact-assessments/impact-${PR_NUMBER}.md" ]]; then
  echo "❌ Impact analyzer failed"
  exit 1
fi

if [[ ! -f "artifacts/crossrepo-intel/crossrepo-${PR_NUMBER}.md" ]]; then
  echo "❌ Cross-repo analyzer failed"
  exit 1
fi

echo "✓ All analyzers completed successfully"
