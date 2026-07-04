# Quality Analysis Pipeline Scripts

Automated tooling for running quality analysis across RHOAI software catalog
repos and generating registry artifacts for the Org Pulse dashboard.

## Prerequisites

- `claude` CLI (Claude Code) with `/quality-repo-analysis` skill available
- `jq` for JSON processing
- `uv` (Python package manager) for pyyaml dependency
- Python 3.8+
- A software catalog directory containing `repo_mappings.json` and `team_mappings.json`

## Scripts

### run-quality-analysis.sh

Batch runner that resolves team → Jira components → repos from the software
catalog, runs `/quality-repo-analysis` on each repo via `claude -p`, aggregates
results into an HTML dashboard, and optionally generates Org Pulse registry files.

**Usage:**

```bash
run-quality-analysis.sh --catalog-dir DIR --team TEAM --tier TIER [OPTIONS]
```

**Required flags:**

| Flag | Description |
|------|-------------|
| `--catalog-dir DIR` | Path to software catalog references directory |
| `--team TEAM` | Team name as listed in `team_mappings.json` |
| `--tier TIER` | One of: `upstream`, `midstream`, `downstream` |

**Optional flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--output-dir DIR` | `<repo-root>/quality_reports/YYYY-MM-DD/TEAM` | Where to write report files |
| `--parallel N` | `1` | Run N analyses concurrently |
| `--org-pulse` | off | Generate Org Pulse registry after analysis |
| `--org-pulse-dir DIR` | (none, required with `--org-pulse`) | Path to org-pulse `modules/system-health/client` |
| `--dry-run` | off | Print resolved repos and exit without running |
| `--list-teams` | — | Print all team names from catalog and exit |

**Environment variables:**

| Variable | Description |
|----------|-------------|
| `CATALOG_DIR` | Alternative to `--catalog-dir` flag |
| `TIGER_TEAM_DIR` | Override auto-detected repo root |

**Examples:**

```bash
# List all available teams
run-quality-analysis.sh --catalog-dir /path/to/catalog --list-teams

# Preview which repos would be analyzed
run-quality-analysis.sh \
  --catalog-dir /path/to/catalog \
  --team "Model Serving" --tier upstream \
  --dry-run

# Run analysis with 5 parallel workers
run-quality-analysis.sh \
  --catalog-dir /path/to/catalog \
  --team "Model Serving" --tier midstream \
  --parallel 5

# Run analysis and generate Org Pulse registry
run-quality-analysis.sh \
  --catalog-dir /path/to/catalog \
  --team "AI Hub" --tier upstream \
  --parallel 5 \
  --org-pulse \
  --org-pulse-dir /path/to/rhai-org-pulse/modules/system-health/client
```

**Output structure:**

```
quality_reports/2026-07-04/model-serving/
├── quality-analysis-kserve-kserve.md
├── quality-report-kserve-kserve.html
├── quality-analysis-opendatahub-io-modelmesh.md
├── quality-report-opendatahub-io-modelmesh.html
├── ...
├── combined_report.md
├── summary.json
└── dashboard.html
```

Filenames are org-prefixed (`{org}-{repo}`) to avoid collisions when the same
repo name exists across tiers.

---

### generate-quality-registry.sh

Standalone registry generator for the Org Pulse System Health module. Parses
YAML frontmatter from quality report markdown files, enriches each entry with
tier/component/team metadata from the software catalog, and produces:

- `qualityReports.data.js` — ES module with Vite `?url` imports and `QUALITY_REPORTS` array
- `generated-reports/*.html` + `*.md` — copied report files
- `generated-reports/index.html` — standalone HTML landing page with filterable table

**Usage:**

```bash
generate-quality-registry.sh --reports-dir DIR --target-dir DIR --catalog-dir DIR [OPTIONS]
```

**Required flags:**

| Flag | Description |
|------|-------------|
| `--reports-dir DIR` | Directory containing `quality-analysis-*.md` and `quality-report-*.html` pairs |
| `--target-dir DIR` | Org Pulse client directory (writes to `{target}/generated-reports/` and `{target}/qualityReports.data.js`) |
| `--catalog-dir DIR` | Path to software catalog references directory |

**Optional flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--blurb TEXT` | `"Quality analysis of N repositories."` | Description shown in the registry metadata |

**Environment variables:**

| Variable | Description |
|----------|-------------|
| `CATALOG_DIR` | Alternative to `--catalog-dir` flag |

**Examples:**

```bash
# Generate registry from a reports directory
generate-quality-registry.sh \
  --reports-dir /path/to/reports \
  --target-dir /path/to/rhai-org-pulse/modules/system-health/client \
  --catalog-dir /path/to/catalog

# With custom blurb
generate-quality-registry.sh \
  --reports-dir /path/to/reports \
  --target-dir /path/to/rhai-org-pulse/modules/system-health/client \
  --catalog-dir /path/to/catalog \
  --blurb "Model Serving (upstream) — 30 repositories"
```

**Important:** `--reports-dir` and `--target-dir` must be different directories.
The script clears `generated-reports/` inside `--target-dir` before populating
it. If they point to the same location, the source files will be deleted before
they can be copied.

---

## How the pipeline fits together

```
repo_mappings.json ──┐
                     ├── run-quality-analysis.sh ──→ quality-analysis-{org}-{repo}.md
team_mappings.json ──┘       │                       quality-report-{org}-{repo}.html
                             │
                             ├── aggregate_quality_reports.py ──→ dashboard.html
                             │                                    combined_report.md
                             │                                    summary.json
                             │
                             └── (--org-pulse) ──→ generate-quality-registry.sh
                                                       │
                                                       ├── qualityReports.data.js
                                                       ├── generated-reports/*.html
                                                       └── generated-reports/index.html
```

The `qualityReports.data.js` file is consumed by the Org Pulse frontend
(`QualityAnalysisView.vue`) which renders the quality dashboard with
tier/component filter dropdowns.
