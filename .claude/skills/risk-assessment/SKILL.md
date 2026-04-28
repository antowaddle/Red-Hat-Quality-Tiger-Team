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

## Step 0: Verify Dependencies & Parse Arguments

Verify Python dependencies, parse arguments, and initialize state:

```bash
source scripts/parse_args.sh "$ARGUMENTS"
```

This sets: `PR_NUMBER`, `REPO`, `HEADLESS`, `DRY_RUN` and initializes `tmp/qc-config.yaml`

---

## Step 1: Extract PR Metadata

Extract PR data using gh CLI:

```bash
scripts/extract_pr.sh
```

---

## Step 2: Load Context

Fetch context repositories and enrich PR with Jira data:

```bash
scripts/load_context.sh
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
PR_NUMBER=$(python3 scripts/state.py get tmp/qc-config.yaml pr_number)
scripts/verify_outputs.sh $PR_NUMBER
```

---

## Step 4: Aggregate Results & Decide

Run decision engine to aggregate analyzer results:

```bash
scripts/run_decision.sh
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
scripts/report_results.sh
```

---

## Error Handling

All utility scripts use `set -euo pipefail` and exit with error codes on failure. The orchestrator will stop on any step failure.
