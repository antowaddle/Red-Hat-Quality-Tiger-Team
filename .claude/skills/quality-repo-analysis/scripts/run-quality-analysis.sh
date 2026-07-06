#!/usr/bin/env bash
#
# run-quality-analysis.sh
#
# Runs /quality-repo-analysis for repos belonging to a team+tier,
# then aggregates the individual reports into an HTML dashboard.
#
# Usage:
#   run-quality-analysis.sh --catalog-dir /path/to/catalog --team "AI Hub" --tier upstream
#   run-quality-analysis.sh --catalog-dir /path/to/catalog --team "Model Serving" --tier midstream --parallel 5
#   run-quality-analysis.sh --catalog-dir /path/to/catalog --team "Runtimes" --tier upstream --dry-run
#   run-quality-analysis.sh --catalog-dir /path/to/catalog --team "AI Hub" --tier upstream --org-pulse --org-pulse-dir /path/to/client
#   run-quality-analysis.sh --catalog-dir /path/to/catalog --list-teams
#
# Requirements:
#   - jq
#   - claude CLI (claude code)
#   - uv (for aggregator's pyyaml dependency)
#
# Environment variables (override flags):
#   CATALOG_DIR      — Path to software catalog references (repo_mappings.json + team_mappings.json)
#   TIGER_TEAM_DIR   — Path to the Red-Hat-Quality-Tiger-Team repo root (auto-detected from script location)

set -euo pipefail

# --- Auto-detect paths from script location ---

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="${TIGER_TEAM_DIR:-$(cd "$SKILL_DIR/../.." && pwd)}"

BUNDLED_CATALOG="$SKILL_DIR/references"
CATALOG_DIR="${CATALOG_DIR:-}"
TEAM=""
TIER=""
OUTPUT_DIR=""
DRY_RUN=false
PARALLEL=1
ORG_PULSE=false
ORG_PULSE_DIR=""

usage() {
    cat <<EOF
Usage: $(basename "$0") --team TEAM --tier TIER [OPTIONS]

Resolve repos for a team+tier from the software catalog, run quality-repo-analysis
on each, then aggregate results into an HTML dashboard.

Required:
  --team TEAM         Team name (from team_mappings.json)
  --tier TIER         One of: upstream, midstream, downstream

Catalog:
  --catalog-dir DIR   Path to software catalog references dir (contains repo_mappings.json + team_mappings.json).
                      Falls back to bundled references/ if not provided.
                      Can also be set via CATALOG_DIR env var.

Options:
  --output-dir DIR      Where to write reports (default: <repo-root>/quality_reports/YYYY-MM-DD/TEAM)
  --parallel N          Run N analyses concurrently (default: 1)
  --org-pulse           After analysis, generate org-pulse registry files
  --org-pulse-dir DIR   Org-pulse client dir (required when --org-pulse is used)
  --dry-run             Print the repo URLs that would be analyzed, then exit
  --list-teams          Print all available team names and exit
  -h, --help            Show this help

Environment variables:
  CATALOG_DIR           Override --catalog-dir
  TIGER_TEAM_DIR        Override auto-detected repo root (default: derived from script location)

Examples:
  $(basename "$0") --catalog-dir /path/to/catalog --team "AI Hub" --tier upstream
  $(basename "$0") --catalog-dir /path/to/catalog --team "Model Serving" --tier midstream --parallel 5 --dry-run
  $(basename "$0") --catalog-dir /path/to/catalog --team "AI Hub" --tier upstream --org-pulse --org-pulse-dir /path/to/client
  $(basename "$0") --catalog-dir /path/to/catalog --list-teams
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --catalog-dir)    CATALOG_DIR="$2"; shift 2 ;;
        --team)           TEAM="$2"; shift 2 ;;
        --tier)           TIER="$2"; shift 2 ;;
        --output-dir)     OUTPUT_DIR="$2"; shift 2 ;;
        --parallel)       PARALLEL="$2"; shift 2 ;;
        --org-pulse)      ORG_PULSE=true; shift ;;
        --org-pulse-dir)  ORG_PULSE_DIR="$2"; shift 2 ;;
        --dry-run)        DRY_RUN=true; shift ;;
        --list-teams)
            if [[ -z "$CATALOG_DIR" ]]; then
                if [[ -d "$BUNDLED_CATALOG" && -f "$BUNDLED_CATALOG/team_mappings.json" ]]; then
                    CATALOG_DIR="$BUNDLED_CATALOG"
                else
                    echo "Error: --catalog-dir (or CATALOG_DIR env var) is required for --list-teams"
                    exit 1
                fi
            fi
            echo "Available teams:"
            jq -r '[.mappings[].team] | unique | .[]' "$CATALOG_DIR/team_mappings.json"
            exit 0
            ;;
        -h|--help)    usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

# --- Validate required arguments ---

if [[ -z "$CATALOG_DIR" ]]; then
    if [[ -d "$BUNDLED_CATALOG" && -f "$BUNDLED_CATALOG/repo_mappings.json" ]]; then
        CATALOG_DIR="$BUNDLED_CATALOG"
        echo "Using bundled catalog: $CATALOG_DIR"
    else
        echo "Error: --catalog-dir is required (or set CATALOG_DIR env var)"
        echo ""
        usage
    fi
fi

if [[ ! -d "$CATALOG_DIR" ]]; then
    echo "Error: catalog directory not found: $CATALOG_DIR"
    exit 1
fi

TEAM_MAPPINGS="$CATALOG_DIR/team_mappings.json"
REPO_MAPPINGS="$CATALOG_DIR/repo_mappings.json"

if [[ ! -f "$TEAM_MAPPINGS" ]]; then
    echo "Error: team_mappings.json not found in $CATALOG_DIR"
    exit 1
fi

if [[ ! -f "$REPO_MAPPINGS" ]]; then
    echo "Error: repo_mappings.json not found in $CATALOG_DIR"
    exit 1
fi

if [[ -z "$TEAM" || -z "$TIER" ]]; then
    echo "Error: --team and --tier are required"
    echo ""
    usage
fi

if [[ ! "$TIER" =~ ^(upstream|midstream|downstream)$ ]]; then
    echo "Error: --tier must be one of: upstream, midstream, downstream"
    exit 1
fi

if $ORG_PULSE && [[ -z "$ORG_PULSE_DIR" ]]; then
    echo "Error: --org-pulse-dir is required when --org-pulse is used"
    exit 1
fi

# --- Resolve repos ---

# Step 1: team -> jira_components
COMPONENTS=$(jq -r --arg team "$TEAM" \
    '[.mappings[] | select(.team == $team) | .jira_component] | unique | .[]' \
    "$TEAM_MAPPINGS")

if [[ -z "$COMPONENTS" ]]; then
    echo "Error: No components found for team '$TEAM'"
    echo ""
    echo "Did you mean one of these?"
    jq -r '[.mappings[].team] | unique | .[]' "$TEAM_MAPPINGS" | grep -i "${TEAM%% *}" || true
    exit 1
fi

echo "Team '$TEAM' maps to components:"
echo "$COMPONENTS" | sed 's/^/  - /'
echo ""

# Step 2: jira_components + tier -> repo URLs
REPO_URLS=""
while IFS= read -r comp; do
    urls=$(jq -r --arg comp "$comp" --arg tier "$TIER" \
        '.mappings[] | select(.jira_component == $comp and .tier == $tier) | "https://github.com/" + .repo' \
        "$REPO_MAPPINGS")
    if [[ -n "$urls" ]]; then
        REPO_URLS+="$urls"$'\n'
    fi
done <<< "$COMPONENTS"

REPO_URLS=$(echo "$REPO_URLS" | sort -u | sed '/^$/d')

if [[ -z "$REPO_URLS" ]]; then
    echo "No repos found for team '$TEAM' at tier '$TIER'"
    exit 0
fi

REPO_COUNT=$(echo "$REPO_URLS" | wc -l)
echo "Found $REPO_COUNT repo(s) at tier '$TIER':"
echo "$REPO_URLS" | sed 's/^/  /'
echo ""

if $DRY_RUN; then
    echo "(dry-run) Would analyze the above repos."
    exit 0
fi

# --- Set up output directory ---

TEAM_SLUG=$(echo "$TEAM" | tr '[:upper:] ' '[:lower:]-' | tr -cd 'a-z0-9-')
if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="$REPO_ROOT/quality_reports/$(date +%Y-%m-%d)/$TEAM_SLUG"
fi
mkdir -p "$OUTPUT_DIR"
echo "Output directory: $OUTPUT_DIR"
echo ""

# --- Run analyses ---

run_analysis() {
    local url="$1"
    local repo_name
    repo_name=$(echo "$url" | sed 's|.*/||')
    local org_name
    org_name=$(echo "$url" | sed 's|https://github.com/||; s|/.*||')

    echo "[START] $org_name/$repo_name"
    (
        cd "$REPO_ROOT"
        claude -p --permission-mode bypassPermissions \
            "/quality-repo-analysis $url" \
            2>&1
    )

    # Move generated files to output directory, normalizing filenames to
    # include org so repos with the same name across tiers don't collide.
    local canonical_md="quality-analysis-${org_name}-${repo_name}.md"
    local canonical_html="quality-report-${org_name}-${repo_name}.html"

    local found_md=""
    for f in "$REPO_ROOT"/quality-analysis-"$org_name"-"$repo_name".md \
             "$REPO_ROOT"/quality-analysis-"$repo_name".md; do
        if [[ -f "$f" ]]; then
            found_md="$f"
            break
        fi
    done
    if [[ -n "$found_md" ]]; then
        mv "$found_md" "$OUTPUT_DIR/$canonical_md"
        echo "[DONE]  $org_name/$repo_name -> $canonical_md"
    fi

    local found_html=""
    for f in "$REPO_ROOT"/quality-report-"$org_name"-"$repo_name".html \
             "$REPO_ROOT"/quality-report-"$repo_name".html; do
        if [[ -f "$f" ]]; then
            found_html="$f"
            break
        fi
    done
    if [[ -n "$found_html" ]]; then
        mv "$found_html" "$OUTPUT_DIR/$canonical_html"
    fi
}

export -f run_analysis
export REPO_ROOT OUTPUT_DIR

if [[ "$PARALLEL" -gt 1 ]]; then
    echo "Running $REPO_COUNT analyses ($PARALLEL at a time)..."
    echo "$REPO_URLS" | xargs -P "$PARALLEL" -I {} bash -c 'run_analysis "$@"' _ {}
else
    echo "Running $REPO_COUNT analyses sequentially..."
    while IFS= read -r url; do
        run_analysis "$url"
        echo ""
    done <<< "$REPO_URLS"
fi

echo ""
echo "=== Individual analyses complete ==="
echo ""

# --- Aggregate into dashboard ---

MD_COUNT=$(find "$OUTPUT_DIR" -name '*.md' -not -name 'combined_*' | wc -l)

if [[ "$MD_COUNT" -eq 0 ]]; then
    echo "Warning: No markdown reports found in $OUTPUT_DIR to aggregate"
    echo "Reports may have been saved with unexpected filenames."
    echo "Check $REPO_ROOT for quality-analysis-*.md files."
    exit 1
fi

echo "Aggregating $MD_COUNT report(s) into dashboard..."

AGGREGATOR="$SKILL_DIR/aggregate_quality_reports.py"
DASHBOARD="$OUTPUT_DIR/dashboard.html"

uv run --with pyyaml python3 "$AGGREGATOR" \
    --reports-dir "$OUTPUT_DIR" \
    --output-md "$OUTPUT_DIR/combined_report.md" \
    --output-json "$OUTPUT_DIR/summary.json" \
    --output-html "$DASHBOARD"

echo ""
echo "=== Aggregation complete ==="
echo "Reports:   $OUTPUT_DIR/"
echo "Dashboard: $DASHBOARD"
echo ""

# --- Optionally generate org-pulse registry ---

if $ORG_PULSE; then
    echo "Generating org-pulse registry..."
    "$SCRIPT_DIR/generate-quality-registry.sh" \
        --reports-dir "$OUTPUT_DIR" \
        --target-dir "$ORG_PULSE_DIR" \
        --catalog-dir "$CATALOG_DIR" \
        --blurb "$TEAM ($TIER) — $REPO_COUNT repositories"
    echo ""
fi

echo "=== Done ==="

# Try to open the dashboard
if command -v xdg-open &>/dev/null; then
    xdg-open "$DASHBOARD" 2>/dev/null &
elif command -v open &>/dev/null; then
    open "$DASHBOARD"
fi
