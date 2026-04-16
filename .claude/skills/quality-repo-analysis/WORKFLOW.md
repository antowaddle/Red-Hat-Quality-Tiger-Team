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
