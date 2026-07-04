# Quality Assessment Workflow

## End-to-End Workflow for Analyzing All RHOAI Repositories

### Step 1: Generate Analysis Commands

```bash
cd quality-tiger-team
python aggregate_quality_reports.py --generate-commands --commands-output analysis_todo.txt
```

This creates a file with 20 `/quality-repo-analysis` commands.

### Step 2: Run Quality Analysis on All Repos

In Claude Code, run each command from the generated list:

```bash
/quality-repo-analysis https://github.com/opendatahub-io/odh-dashboard
/quality-repo-analysis https://github.com/opendatahub-io/model-registry
# ... continue for all 20 repos
```

Save each generated report with the repository name in the filename.

### Step 3: Collect Reports

```bash
mkdir -p quality_reports/$(date +%Y-%m-%d)
# Move or copy all generated *_quality_report.md files to this directory
```

### Step 4: Generate Combined Report

```bash
python aggregate_quality_reports.py \
  --reports-dir quality_reports/2026-04-16 \
  --output-md quality_reports/2026-04-16/combined_report.md \
  --output-json quality_reports/2026-04-16/summary.json
```

### Step 5: Review Results

```bash
# View the combined report
cat quality_reports/2026-04-16/combined_report.md

# Query JSON data
jq '.average_score' quality_reports/2026-04-16/summary.json
jq '.repositories[] | select(.overall_score < 6) | .name' quality_reports/2026-04-16/summary.json
```

## Alternative: Use Helper Script

```bash
./run_batch_analysis.sh quality_reports/2026-04-16
```

This script guides you through all steps interactively.

## Repository Groups

- **Upstream (6)**: opendatahub-io repositories
- **Downstream (12)**: red-hat-data-services repositories  
- **External (2)**: ray-project/kuberay, kubernetes-sigs/kueue

## Tips

- Run analyses in batches (e.g., all upstream, then all downstream)
- Use consistent naming: `{repo-name}_quality_report.md`
- Archive reports by date for historical tracking
- Compare reports over time to track improvements

---

## Catalog-Driven Batch Workflow

The `scripts/` directory contains automated tooling that reads the software
catalog (`repo_mappings.json` + `team_mappings.json`) and runs batch analysis
across all repos for a given team and tier.

### Prerequisites

- `claude` CLI (Claude Code)
- `jq`
- `uv` (Python package manager, for pyyaml)
- Software catalog directory containing `repo_mappings.json` and `team_mappings.json`

### scripts/run-quality-analysis.sh

Batch runner that resolves team → Jira components → repos from the catalog,
runs `/quality-repo-analysis` on each, aggregates results, and optionally
generates org-pulse registry files.

```bash
# List available teams
scripts/run-quality-analysis.sh \
  --catalog-dir /path/to/catalog \
  --list-teams

# Dry run — see which repos would be analyzed
scripts/run-quality-analysis.sh \
  --catalog-dir /path/to/catalog \
  --team "Model Serving" --tier upstream \
  --dry-run

# Run analysis with 5 parallel workers
scripts/run-quality-analysis.sh \
  --catalog-dir /path/to/catalog \
  --team "Model Serving" --tier midstream \
  --parallel 5

# Run analysis and generate org-pulse registry
scripts/run-quality-analysis.sh \
  --catalog-dir /path/to/catalog \
  --team "AI Hub" --tier upstream \
  --parallel 5 \
  --org-pulse --org-pulse-dir /path/to/rhai-org-pulse/modules/system-health/client
```

Output files are written to `quality_reports/YYYY-MM-DD/TEAM/` by default.
Use `--output-dir` to override.

Filenames are org-prefixed (`quality-analysis-{org}-{repo}.md`) to avoid
collisions when the same repo name exists across tiers.

### scripts/generate-quality-registry.sh

Standalone registry generator for the org-pulse System Health module. Parses
YAML frontmatter from quality reports, enriches with catalog metadata
(tier, component, team), and produces:

- `qualityReports.data.js` — ES module with Vite `?url` imports
- `generated-reports/` — HTML + MD report files
- `generated-reports/index.html` — standalone landing page

```bash
# Generate registry from a reports directory
scripts/generate-quality-registry.sh \
  --reports-dir /path/to/reports \
  --target-dir /path/to/rhai-org-pulse/modules/system-health/client \
  --catalog-dir /path/to/catalog

# With custom blurb
scripts/generate-quality-registry.sh \
  --reports-dir /path/to/reports \
  --target-dir /path/to/rhai-org-pulse/modules/system-health/client \
  --catalog-dir /path/to/catalog \
  --blurb "Model Serving (upstream) — 30 repositories"
```

Both scripts accept a `CATALOG_DIR` environment variable as an alternative to
`--catalog-dir`.
