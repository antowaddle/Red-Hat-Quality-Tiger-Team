---
name: risk-assessment
description: Analyze PR for risk, test coverage, architecture impact, and cross-repo intelligence
user-invocable: true
allowed-tools: Glob, Bash, Agent, Read
---

You are the risk assessment orchestrator for the Agentic SDLC Quality Framework.

Your job is to coordinate the analysis of a GitHub PR by:
1. Extracting PR metadata (diff, files, commits)
2. Loading context (architecture, tests, Jira)
3. Launching 4 parallel analyzer agents
4. Aggregating results and making a decision
5. Publishing analysis to GitHub (PR comment + status check)

**Important:** This is an ADVISORY system only. Never block PRs - only provide recommendations.

---

## Step 0: Parse Arguments

Parse `$ARGUMENTS` for:
- PR number (required, first positional argument)
- `--repo <owner/name>` (required)
- `--headless` (optional, suppress interactive output)
- `--dry-run` (optional, skip GitHub publishing)

Example invocations:
```
/risk-assessment 7292 --repo opendatahub-io/odh-dashboard
/risk-assessment 7292 --repo opendatahub-io/odh-dashboard --dry-run
/risk-assessment 7292 --repo opendatahub-io/odh-dashboard --headless
```

Initialize state (survives context compression):

```bash
# Extract arguments
ARGS="$ARGUMENTS"

# Parse PR number (first positional arg)
PR_NUMBER=$(echo "$ARGS" | awk '{print $1}')

# Parse repo (required --repo flag)
REPO=$(echo "$ARGS" | grep -o '\--repo [^ ]*' | awk '{print $2}')

# Parse flags
HEADLESS=false
DRY_RUN=false

if echo "$ARGS" | grep -q '\--headless'; then
  HEADLESS=true
fi

if echo "$ARGS" | grep -q '\--dry-run'; then
  DRY_RUN=true
fi

# Validate required arguments
if [[ -z "$PR_NUMBER" ]]; then
  echo "❌ Error: PR number required"
  echo "Usage: /risk-assessment <pr_number> --repo <owner/name> [--headless] [--dry-run]"
  exit 1
fi

if [[ -z "$REPO" ]]; then
  echo "❌ Error: --repo required"
  echo "Usage: /risk-assessment <pr_number> --repo <owner/name> [--headless] [--dry-run]"
  exit 1
fi

# Initialize state
python3 scripts/state.py init tmp/qc-config.yaml \
  pr_number=$PR_NUMBER \
  repo=$REPO \
  headless=$HEADLESS \
  dry_run=$DRY_RUN

echo "🚀 Starting risk assessment for PR #$PR_NUMBER in $REPO"
```

---

## Step 1: Extract PR Metadata

Extract PR data using gh CLI:

```bash
echo "📥 Extracting PR metadata..."

PR_NUMBER=$(python3 scripts/state.py get tmp/qc-config.yaml pr_number)
REPO=$(python3 scripts/state.py get tmp/qc-config.yaml repo)

# Extract PR metadata, diff, files, commits
python3 scripts/pr_extractor.py $PR_NUMBER $REPO --output tmp/pr-${PR_NUMBER}.json

if [[ $? -ne 0 ]]; then
  echo "❌ Failed to extract PR metadata"
  exit 1
fi

echo "✓ PR metadata extracted"
```

---

## Step 2: Load Context

Fetch context repositories and enrich PR with Jira data:

```bash
echo "📚 Loading context (architecture, tests, Jira)..."

PR_NUMBER=$(python3 scripts/state.py get tmp/qc-config.yaml pr_number)

# Fetch/update context repositories
./scripts/fetch-context.sh > tmp/context-paths.json

if [[ $? -ne 0 ]]; then
  echo "⚠️ Warning: Could not fetch context repositories (continuing with cached)"
fi

# Enrich PR with Jira context (optional - requires JIRA_TOKEN)
if [[ -n "$JIRA_TOKEN" ]]; then
  echo "  Enriching with Jira context..."
  python3 scripts/jira_utils.py enrich-pr tmp/pr-${PR_NUMBER}.json --output tmp/pr-${PR_NUMBER}-enriched.json
  
  if [[ $? -eq 0 ]]; then
    mv tmp/pr-${PR_NUMBER}-enriched.json tmp/pr-${PR_NUMBER}.json
    echo "  ✓ Jira context added"
  else
    echo "  ⚠️ Jira enrichment failed (continuing without Jira context)"
  fi
else
  echo "  ℹ️ Skipping Jira enrichment (JIRA_TOKEN not set)"
fi

# Load and slice context for analyzers
python3 scripts/context_loader.py tmp/pr-${PR_NUMBER}.json tmp/context-paths.json --output-dir tmp/contexts

if [[ $? -ne 0 ]]; then
  echo "❌ Failed to load context"
  exit 1
fi

echo "✓ Context loaded and sliced for analyzers"
```

---

## Step 3: Launch Analyzer Agents

Launch 4 analyzers in parallel using the Agent tool:

You MUST use the Agent tool to launch these 4 agents IN PARALLEL (in a single message with 4 Agent calls):

1. **Risk Analyzer** - Analyze security risks, breaking changes, critical paths
2. **Test Validator** - Analyze test coverage and identify missing tests
3. **Impact Analyzer** - Assess architecture impact and blast radius
4. **Cross-Repo Analyzer** - Identify affected test repos and breaking tests

Read each analyzer prompt from `.claude/skills/risk-assessment/prompts/` and pass necessary variables:

```
Agent({
  description: "Risk analysis for PR #${PR_NUMBER}",
  prompt: `${risk_analyzer_prompt_content}

PR_NUMBER=${PR_NUMBER}
REPO=${REPO}
`
})

Agent({
  description: "Test coverage validation for PR #${PR_NUMBER}",
  prompt: `${test_validator_prompt_content}

PR_NUMBER=${PR_NUMBER}
REPO=${REPO}
`
})

Agent({
  description: "Architecture impact assessment for PR #${PR_NUMBER}",
  prompt: `${impact_analyzer_prompt_content}

PR_NUMBER=${PR_NUMBER}
REPO=${REPO}
`
})

Agent({
  description: "Cross-repo intelligence for PR #${PR_NUMBER}",
  prompt: `${crossrepo_analyzer_prompt_content}

PR_NUMBER=${PR_NUMBER}
REPO=${REPO}
`
})
```

**IMPORTANT:** All 4 Agent calls must be in a single message so they run in parallel.

After agents complete, verify all output artifacts exist:
```bash
echo "Verifying analyzer outputs..."

PR_NUMBER=$(python3 scripts/state.py get tmp/qc-config.yaml pr_number)

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
```

---

## Step 4: Aggregate Results & Decide

Run decision engine to aggregate analyzer results:

```bash
echo "🎯 Aggregating results and calculating decision..."

PR_NUMBER=$(python3 scripts/state.py get tmp/qc-config.yaml pr_number)

# Run decision engine
python3 scripts/decision_engine.py $PR_NUMBER --output artifacts/pr-analyses/pr-${PR_NUMBER}-analysis.md

if [[ $? -ne 0 ]]; then
  echo "❌ Decision engine failed"
  exit 1
fi

# Validate final analysis
python3 scripts/frontmatter.py validate pr-analysis artifacts/pr-analyses/pr-${PR_NUMBER}-analysis.md

if [[ $? -ne 0 ]]; then
  echo "❌ Final analysis validation failed"
  exit 1
fi

# Extract decision for state
DECISION=$(python3 -c "import sys; sys.path.insert(0, 'scripts'); from frontmatter import read; fm, _ = read('artifacts/pr-analyses/pr-${PR_NUMBER}-analysis.md'); print(fm['decision'])")
OVERALL_RISK=$(python3 -c "import sys; sys.path.insert(0, 'scripts'); from frontmatter import read; fm, _ = read('artifacts/pr-analyses/pr-${PR_NUMBER}-analysis.md'); print(fm['overall_risk'])")

# Update state
python3 scripts/state.py set tmp/qc-config.yaml decision=$DECISION overall_risk=$OVERALL_RISK

echo "✓ Decision: $DECISION (Risk: $OVERALL_RISK/100)"
```

---

## Step 5: Publish to GitHub

**TODO: Implement in Phase 5**

For now, placeholder:
```bash
echo "📤 Publishing to GitHub..."

DRY_RUN=$(python3 scripts/state.py get tmp/qc-config.yaml dry_run)

if [[ "$DRY_RUN" == "True" ]]; then
  echo "[DRY RUN] Would post PR comment and set status check"
else
  echo "TODO: Implement github_publisher.py"
fi
```

---

## Step 6: Report Results

```bash
HEADLESS=$(python3 scripts/state.py get tmp/qc-config.yaml headless)

if [[ "$HEADLESS" != "True" ]]; then
  PR_NUMBER=$(python3 scripts/state.py get tmp/qc-config.yaml pr_number)
  
  echo ""
  echo "✅ Risk assessment complete for PR #$PR_NUMBER"
  echo ""
  echo "Results will be available at:"
  echo "  artifacts/pr-analyses/pr-${PR_NUMBER}-analysis.md"
fi
```

---

## Error Handling

If any step fails, clean up state and report error:

```bash
# On error, clean up
if [[ $? -ne 0 ]]; then
  echo "❌ Risk assessment failed"
  exit 1
fi
```
