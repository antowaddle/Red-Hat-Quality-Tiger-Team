#!/bin/bash
# Fetch or update context repositories for analyzer context.
#
# This script clones/updates the architecture-context and odh-test-context
# repositories that provide context for quality analysis.
#
# Usage:
#     ./scripts/fetch-context.sh [--force]
#
# Options:
#     --force    Force re-clone even if repos exist
#
# Environment:
#     CONTEXT_DIR    Directory for context repos (default: context-repos)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONTEXT_DIR="${CONTEXT_DIR:-$PROJECT_ROOT/context-repos}"

ARCHITECTURE_REPO="https://github.com/opendatahub-io/architecture-context.git"
TEST_CONTEXT_REPO="https://github.com/opendatahub-io/odh-test-context.git"

FORCE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE=true
            shift
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 [--force]" >&2
            exit 1
            ;;
    esac
done

echo "Context directory: $CONTEXT_DIR" >&2

# Create context directory if it doesn't exist
mkdir -p "$CONTEXT_DIR"

# Function to clone or update a repository
fetch_repo() {
    local repo_url=$1
    local repo_name=$2
    local repo_path="$CONTEXT_DIR/$repo_name"

    echo "---" >&2
    echo "Repository: $repo_name" >&2

    if [ -d "$repo_path/.git" ]; then
        if [ "$FORCE" = true ]; then
            echo "Force mode: removing existing repository..." >&2
            rm -rf "$repo_path"
        else
            echo "Repository exists, updating..." >&2
            cd "$repo_path"

            # Fetch latest changes
            if git fetch origin main >/dev/null 2>&1; then
                # Reset to latest main
                git reset --hard origin/main >/dev/null 2>&1
                echo "✓ Updated to latest main branch" >&2
            else
                echo "⚠ Warning: Could not update repository (continuing with cached version)" >&2
            fi

            cd - >/dev/null
            return 0
        fi
    fi

    # Clone if not exists or force mode
    if [ ! -d "$repo_path/.git" ]; then
        echo "Cloning repository..." >&2
        if git clone --depth 1 --branch main "$repo_url" "$repo_path" >/dev/null 2>&1; then
            echo "✓ Cloned successfully" >&2
        else
            echo "✗ Error: Failed to clone $repo_name" >&2
            return 1
        fi
    fi
}

# Fetch architecture-context
fetch_repo "$ARCHITECTURE_REPO" "architecture-context"

# Fetch odh-test-context
fetch_repo "$TEST_CONTEXT_REPO" "odh-test-context"

echo "---" >&2
echo "✓ Context repositories ready" >&2
echo "" >&2

# Output paths for consumption by other scripts
cat <<EOF
{
  "context_dir": "$CONTEXT_DIR",
  "architecture_context": "$CONTEXT_DIR/architecture-context",
  "test_context": "$CONTEXT_DIR/odh-test-context"
}
EOF
