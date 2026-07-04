#!/usr/bin/env bash
#
# generate-quality-registry.sh
#
# Reads quality-analysis-*.md + quality-report-*.html pairs from a reports
# directory, parses YAML frontmatter, and generates the files needed by the
# rhai-org-pulse system-health module:
#
#   qualityReports.data.js   — Vite-compatible JS registry
#   generated-reports/       — HTML + MD files + index.html landing page
#
# Usage:
#   generate-quality-registry.sh --reports-dir /path/to/reports --target-dir /path/to/client --catalog-dir /path/to/catalog
#   generate-quality-registry.sh --reports-dir /path/to/reports --target-dir /path/to/client --catalog-dir /path/to/catalog --blurb "AI Hub upstream scan"
#
# Requirements: Python 3, uv (for pyyaml)
#
# Environment variables (override flags):
#   CATALOG_DIR   — Path to software catalog references (repo_mappings.json + team_mappings.json)

set -euo pipefail

REPORTS_DIR=""
TARGET_DIR=""
CATALOG_DIR="${CATALOG_DIR:-}"
BLURB=""

usage() {
    cat <<EOF
Usage: $(basename "$0") --reports-dir DIR --target-dir DIR --catalog-dir DIR [OPTIONS]

Parse quality report markdown files and generate org-pulse registry files.

Required:
  --reports-dir DIR   Directory containing quality-analysis-*.md and quality-report-*.html
  --target-dir DIR    Org-pulse client dir (outputs to {target}/generated-reports/ and {target}/qualityReports.data.js)
  --catalog-dir DIR   Software catalog references dir (contains repo_mappings.json + team_mappings.json).
                      Can also be set via CATALOG_DIR env var.

Options:
  --blurb TEXT        Description for the report batch
  -h, --help          Show this help
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --reports-dir)  REPORTS_DIR="$2"; shift 2 ;;
        --target-dir)   TARGET_DIR="$2"; shift 2 ;;
        --catalog-dir)  CATALOG_DIR="$2"; shift 2 ;;
        --blurb)        BLURB="$2"; shift 2 ;;
        -h|--help)     usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

# --- Validate required arguments ---

if [[ -z "$REPORTS_DIR" ]]; then
    echo "Error: --reports-dir is required"
    usage
fi

if [[ ! -d "$REPORTS_DIR" ]]; then
    echo "Error: reports directory not found: $REPORTS_DIR"
    exit 1
fi

if [[ -z "$TARGET_DIR" ]]; then
    echo "Error: --target-dir is required"
    usage
fi

if [[ -z "$CATALOG_DIR" ]]; then
    echo "Error: --catalog-dir is required (or set CATALOG_DIR env var)"
    usage
fi

if [[ ! -d "$CATALOG_DIR" ]]; then
    echo "Error: catalog directory not found: $CATALOG_DIR"
    exit 1
fi

GENERATED_DIR="$TARGET_DIR/generated-reports"
DATA_JS="$TARGET_DIR/qualityReports.data.js"

# --- Count source files ---

MD_FILES=()
while IFS= read -r f; do
    MD_FILES+=("$f")
done < <(find "$REPORTS_DIR" -maxdepth 1 -name 'quality-analysis-*.md' | sort)

if [[ ${#MD_FILES[@]} -eq 0 ]]; then
    echo "Error: No quality-analysis-*.md files found in $REPORTS_DIR"
    exit 1
fi

echo "Found ${#MD_FILES[@]} report(s) in $REPORTS_DIR"

# --- Parse frontmatter from all .md files → JSON array ---

REGISTRY_JSON=$(CATALOG_DIR="$CATALOG_DIR" uv run --with pyyaml python3 - "${MD_FILES[@]}" <<'PYEOF'
import sys, json, yaml, os, re

catalog_dir = os.environ.get("CATALOG_DIR", "")
repo_map = {}
team_map = {}

if catalog_dir:
    repo_mappings_path = os.path.join(catalog_dir, "repo_mappings.json")
    team_mappings_path = os.path.join(catalog_dir, "team_mappings.json")
    if os.path.isfile(repo_mappings_path):
        with open(repo_mappings_path) as f:
            for m in json.load(f)["mappings"]:
                repo_map.setdefault(m["repo"], []).append(m)
    if os.path.isfile(team_mappings_path):
        with open(team_mappings_path) as f:
            for m in json.load(f)["mappings"]:
                team_map.setdefault(m["jira_component"], set()).add(m["team"])

def lookup_metadata(repo_slug):
    """Look up tier, component, and teams for a repo slug like 'opendatahub-io/kserve'."""
    entries = repo_map.get(repo_slug, [])
    if not entries:
        # Fallback: derive tier from org
        org = repo_slug.split("/")[0] if "/" in repo_slug else ""
        if org == "opendatahub-io":
            tier = "midstream"
        elif org == "red-hat-data-services":
            tier = "downstream"
        else:
            tier = "upstream"
        return tier, "", []

    entry = entries[0]
    tier = entry.get("tier", "upstream")
    component = entry.get("jira_component", "")
    teams = sorted(team_map.get(component, set()))
    return tier, component, teams

results = []
for path in sys.argv[1:]:
    with open(path) as f:
        content = f.read()

    m = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not m:
        print(f"Warning: no frontmatter in {path}", file=sys.stderr)
        continue

    fm = yaml.safe_load(m.group(1))
    if not isinstance(fm, dict):
        print(f"Warning: invalid frontmatter in {path}", file=sys.stderr)
        continue

    repo = fm.get("repository", "")
    score = fm.get("overall_score", 0)
    gaps_list = fm.get("critical_gaps", [])

    gap_titles = []
    for g in gaps_list[:2]:
        if isinstance(g, dict) and "title" in g:
            gap_titles.append(g["title"])
        elif isinstance(g, str):
            gap_titles.append(g)

    basename = os.path.basename(path)
    file_id = re.sub(r'^quality-analysis-', '', basename)
    file_id = re.sub(r'\.md$', '', file_id)

    html_name = f"quality-report-{file_id}.html"
    html_path = os.path.join(os.path.dirname(path), html_name)
    if not os.path.isfile(html_path):
        print(f"Skipping {file_id}: no matching HTML ({html_name})", file=sys.stderr)
        continue

    github_url = f"https://github.com/{repo}" if "/" in repo else ""

    tier, component, teams = lookup_metadata(repo)

    results.append({
        "id": file_id,
        "label": repo,
        "githubUrl": github_url,
        "score": f"{score}/10",
        "scoreNum": float(score),
        "gaps": ", ".join(gap_titles),
        "tier": tier,
        "component": component,
        "team": teams[0] if teams else "",
        "analyzedDate": fm.get("analyzed_date", ""),
    })

# Deduplicate: if multiple files resolve to the same repo, keep the org-prefixed one
seen = {}
for r in results:
    label = r["label"]
    if label in seen:
        existing = seen[label]
        if r["id"].count("-") > existing["id"].count("-"):
            seen[label] = r
    else:
        seen[label] = r
results = list(seen.values())

results.sort(key=lambda r: r["scoreNum"], reverse=True)
json.dump(results, sys.stdout, indent=2)
PYEOF
)

REPORT_COUNT=$(echo "$REGISTRY_JSON" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")

if [[ "$REPORT_COUNT" -eq 0 ]]; then
    echo "Error: Could not parse any report frontmatter"
    exit 1
fi

echo "Parsed $REPORT_COUNT report(s) successfully"

# --- Clean and populate generated-reports/ ---

echo "Clearing $GENERATED_DIR/"
rm -rf "$GENERATED_DIR"
mkdir -p "$GENERATED_DIR"

# Copy HTML and MD files
for md in "${MD_FILES[@]}"; do
    cp "$md" "$GENERATED_DIR/"
    # Find matching HTML file
    base=$(basename "$md" | sed 's/^quality-analysis-/quality-report-/' | sed 's/\.md$/.html/')
    html="$REPORTS_DIR/$base"
    if [[ -f "$html" ]]; then
        cp "$html" "$GENERATED_DIR/"
    else
        echo "Warning: No matching HTML for $(basename "$md") (expected $base)"
    fi
done

echo "Copied files to $GENERATED_DIR/"

# --- Generate qualityReports.data.js ---

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Compute average score
AVG_SCORE=$(echo "$REGISTRY_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
avg = sum(r['scoreNum'] for r in data) / len(data) if data else 0
print(f'{avg:.1f}/10')
")

if [[ -z "$BLURB" ]]; then
    BLURB="Quality analysis of $REPORT_COUNT repositories."
fi

# Write JSON to temp file (avoids "Argument list too long" with 300+ reports)
REGISTRY_TMP=$(mktemp)
echo "$REGISTRY_JSON" > "$REGISTRY_TMP"
trap "rm -f '$REGISTRY_TMP'" EXIT

# Generate JS file
python3 -c "
import json, re, sys

with open(sys.argv[1]) as f:
    data = json.load(f)
timestamp = sys.argv[2]
avg_score = sys.argv[3]
blurb = sys.argv[4]

lines = [
    '/**',
    ' * Static quality report registry — auto-generated by generate-quality-registry.sh',
    ' * Each reportUrl is resolved by Vite (?url) so the browser loads a full HTML document',
    ' * inside an iframe — no v-html.',
    ' */',
]

# Generate import statements
for r in data:
    # Convert id to camelCase variable name: opendatahub-io-agent-ops → reportOpendatahubIoAgentOps
    # Split on all non-alphanumeric chars (-, ., _) to produce valid JS identifiers
    parts = re.split(r'[-._]+', r['id'])
    var_name = 'report' + ''.join(p.capitalize() for p in parts if p)
    r['_varName'] = var_name
    html_file = f\"quality-report-{r['id']}.html\"
    lines.append(f\"import {var_name} from './generated-reports/{html_file}?url'\")

lines.append('')
lines.append('export const QUALITY_SAMPLE_META = {')
lines.append(f\"  generatedAt: '{timestamp}',\")
lines.append(f\"  averageScore: '{avg_score}',\")
lines.append(f\"  blurb:\")
lines.append(f\"    '{blurb}'\")
lines.append('}')
lines.append('')
lines.append('/** @type {Array<{ id: string, label: string, githubUrl: string, score: string, gaps: string, tier: string, component: string, team: string, reportUrl: string }>} */')
lines.append('export const QUALITY_REPORTS = [')

for r in data:
    lines.append('  {')
    lines.append(f\"    id: '{r['id']}',\")
    lines.append(f\"    label: '{r['label']}',\")
    lines.append(f\"    githubUrl: '{r['githubUrl']}',\")
    lines.append(f\"    score: '{r['score']}',\")
    # Escape single quotes in gaps
    escaped_gaps = r['gaps'].replace(chr(39), chr(92) + chr(39))
    if len(escaped_gaps) <= 60:
        lines.append(f\"    gaps: '{escaped_gaps}',\")
    else:
        lines.append(f\"    gaps:\")
        lines.append(f\"      '{escaped_gaps}',\")
    lines.append(f\"    tier: '{r.get('tier', '')}',\")
    lines.append(f\"    component: '{r.get('component', '')}',\")
    lines.append(f\"    team: '{r.get('team', '')}',\")
    lines.append(f\"    reportUrl: {r['_varName']}\")
    lines.append('  },')

lines.append(']')
lines.append('')

print('\n'.join(lines))
" "$REGISTRY_TMP" "$TIMESTAMP" "$AVG_SCORE" "$BLURB" > "$DATA_JS"

echo "Generated $DATA_JS"

# --- Generate index.html ---

python3 -c "
import json, sys
from html import escape

with open(sys.argv[1]) as f:
    data = json.load(f)
timestamp = sys.argv[2]
avg_score = sys.argv[3]
blurb = sys.argv[4]
count = len(data)

rows = []
for r in data:
    html_file = f\"quality-report-{r['id']}.html\"
    rows.append(f'''
            <tr>
              <td><a href=\"{html_file}\">{escape(r['label'])}</a></td>
              <td><a href=\"{escape(r['githubUrl'])}\" target=\"_blank\">GitHub</a></td>
              <td>{escape(r.get('tier', ''))}</td>
              <td>{escape(r.get('component', ''))}</td>
              <td>{escape(r['score'])}</td>
              <td>{escape(r['gaps'])}</td>
            </tr>''')

html = f'''<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Quality Analysis Reports</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 2rem;
      color: #1f2937;
      background: #f8fafc;
    }}
    .card {{
      background: #ffffff;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      padding: 1.2rem;
      margin-bottom: 1.2rem;
      box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #ffffff;
    }}
    th, td {{
      border: 1px solid #e5e7eb;
      padding: 0.7rem;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #f1f5f9;
    }}
    a {{
      color: #2563eb;
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
  </style>
</head>
<body>
  <div class=\"card\">
    <h1>Quality Analysis ({count} Repos)</h1>
    <p><strong>Generated:</strong> {escape(timestamp)}</p>
    <p><strong>Average score:</strong> {escape(avg_score)}</p>
    <p>{escape(blurb)}</p>
  </div>

  <div class=\"card\">
    <h2>Repository Reports</h2>
    <table>
      <thead>
        <tr>
          <th>Repository (detail page)</th>
          <th>Source</th>
          <th>Tier</th>
          <th>Component</th>
          <th>Overall score</th>
          <th>Top gaps</th>
        </tr>
      </thead>
      <tbody>{''.join(rows)}
      </tbody>
    </table>
  </div>
</body>
</html>
'''

print(html)
" "$REGISTRY_TMP" "$TIMESTAMP" "$AVG_SCORE" "$BLURB" > "$GENERATED_DIR/index.html"

echo "Generated $GENERATED_DIR/index.html"
echo ""
echo "=== Registry generation complete ==="
echo "  Reports:  $GENERATED_DIR/ ($REPORT_COUNT files)"
echo "  Registry: $DATA_JS"
echo "  Landing:  $GENERATED_DIR/index.html"
