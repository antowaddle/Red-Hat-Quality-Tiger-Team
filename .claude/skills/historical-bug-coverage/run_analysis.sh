#!/bin/bash
# Wrapper script to run historical bug coverage analysis with .env credentials

set -e

# Load credentials from .env
# Check multiple locations in priority order
if [ -n "$JIRA_ENV_FILE" ] && [ -f "$JIRA_ENV_FILE" ]; then
    ENV_FILE="$JIRA_ENV_FILE"
elif [ -f "$(pwd)/.env" ]; then
    ENV_FILE="$(pwd)/.env"
elif [ -f "$HOME/.env" ]; then
    ENV_FILE="$HOME/.env"
elif [ -f "$HOME/.claude/.env" ]; then
    ENV_FILE="$HOME/.claude/.env"
else
    echo "Error: .env file not found"
    echo "Searched locations:"
    echo "  - \$JIRA_ENV_FILE (if set)"
    echo "  - $(pwd)/.env"
    echo "  - $HOME/.env"
    echo "  - $HOME/.claude/.env"
    exit 1
fi

echo "Using .env file: $ENV_FILE"

# Source and map variables
source "$ENV_FILE"

# Map to expected variable names
export JIRA_SERVER="${JIRA_BASE_URL}"
export JIRA_USER="${JIRA_USERNAME}"
export JIRA_TOKEN="${JIRA_TOKEN}"

# Validate credentials are set
if [ -z "$JIRA_SERVER" ] || [ -z "$JIRA_USER" ] || [ -z "$JIRA_TOKEN" ]; then
    echo "Error: Missing Jira credentials in .env file"
    echo "  JIRA_BASE_URL (maps to JIRA_SERVER): ${JIRA_SERVER:-NOT SET}"
    echo "  JIRA_USERNAME (maps to JIRA_USER): ${JIRA_USER:-NOT SET}"
    echo "  JIRA_TOKEN: ${JIRA_TOKEN:+SET}"
    exit 1
fi

# Parse command-line arguments (supports both --flag and positional formats)
REPO=""
JQL=""
EXTERNAL_TESTS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --repo)
            REPO="$2"
            shift 2
            ;;
        --jql)
            JQL="$2"
            shift 2
            ;;
        --external-tests)
            EXTERNAL_TESTS="$2"
            shift 2
            ;;
        --output)
            # Ignored - script has hardcoded output path
            shift 2
            ;;
        *)
            # Assume positional: first=repo, second=jql
            if [ -z "$REPO" ]; then
                REPO="$1"
            elif [ -z "$JQL" ]; then
                JQL="$1"
            fi
            shift
            ;;
    esac
done

if [ -z "$REPO" ] || [ -z "$JQL" ]; then
    echo "Usage: $0 --repo <repo_path> --jql <jql_query> [--external-tests <path>]"
    echo "   or: $0 <repo_path> <jql_query>"
    exit 1
fi

# Auto-detect opendatahub-tests if not explicitly provided
if [ -z "$EXTERNAL_TESTS" ]; then
    # Get repo name from path
    REPO_NAME=$(basename "$REPO")

    # Check for opendatahub-tests in common locations
    for location in \
        "$(dirname "$REPO")/opendatahub-tests/tests/${REPO_NAME//-/_}" \
        "$(dirname "$REPO")/opendatahub-tests/tests/${REPO_NAME}" \
        "$HOME/opendatahub-tests/tests/${REPO_NAME//-/_}" \
        "$HOME/opendatahub-tests/tests/${REPO_NAME}" \
        "./opendatahub-tests/tests/${REPO_NAME//-/_}" \
        "./opendatahub-tests/tests/${REPO_NAME}"; do

        if [ -d "$location" ]; then
            echo "✅ Auto-detected external tests: $location"
            EXTERNAL_TESTS="$location"
            break
        fi
    done

    if [ -z "$EXTERNAL_TESTS" ]; then
        echo "ℹ️  No external tests found (checked opendatahub-tests). Use --external-tests to specify."
    fi
fi

# Run the Python script with positional arguments
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -n "$EXTERNAL_TESTS" ]; then
    exec python3 "$SCRIPT_DIR/strict_coverage_analysis.py" "$REPO" "$JQL" --external-tests "$EXTERNAL_TESTS"
else
    exec python3 "$SCRIPT_DIR/strict_coverage_analysis.py" "$REPO" "$JQL"
fi
