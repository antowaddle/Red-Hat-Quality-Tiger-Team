# Risk Assessment Skill

**Agentic PR analysis for risk assessment, test coverage, architecture impact, and cross-repository intelligence**

---

## Overview

The Risk Assessment skill is a multi-agent system that analyzes GitHub pull requests to provide intelligent, context-aware quality gates. It combines 4 specialized AI analyzers with weighted risk scoring to catch high-risk changes before they reach production.

**Key Feature:** Automatically detects Kubernetes resource renames that could break downstream services (see [demo example](examples/pr-489-demo/)).

---

## Quick Start

```bash
# Analyze any GitHub PR
/risk-assessment <pr_number> --repo <owner/name> --dry-run

# Example
/risk-assessment 489 --repo opendatahub-io/model-registry-operator --dry-run
```

---

## What It Analyzes

### 1. 📊 Risk Assessment
- Security vulnerabilities (SQL injection, XSS, secret exposure)
- Breaking changes in APIs and critical paths
- Dependency risks
- Historical incident patterns

### 2. ✅ Test Coverage
- Unit test coverage for modified functions
- Integration test validation
- E2E test impact
- Test gap identification

### 3. 🏗️ Architecture Impact
- Component blast radius
- Cross-component dependencies
- **Kubernetes resource renames** (ConfigMaps, Secrets, CRDs)
- Breaking change detection

### 4. 🔗 Cross-Repository Intelligence
- Hardcoded references in other repos
- Breaking test identification
- Version compatibility
- Coordination requirements

---

## Output

The skill generates comprehensive reports in both HTML and Markdown:

- **Main Analysis:** Overall risk score (0-100), decision (APPROVE/WARN), executive summary
- **Risk Details:** Security findings, breaking changes, critical path analysis
- **Test Report:** Coverage metrics, missing tests, recommendations
- **Impact Assessment:** Affected components, blast radius, K8s alerts
- **Cross-Repo Intel:** Affected repositories, breaking tests, coordination needs

**Decision Thresholds:**
- `0-40`: ✅ APPROVE (low risk)
- `41-100`: ⚠️ WARN (medium/high risk - requires review)

*This is an advisory system - it never blocks PRs, only provides recommendations.*

---

## Real-World Example

See [`examples/pr-489-demo/`](examples/pr-489-demo/) for a complete analysis that caught an incident pattern:

**Scenario:** PR #489 renamed a ConfigMap in model-registry-operator
**Risk:** Would break odh-dashboard (13 hardcoded references)
**Detection:** K8s rename detector + cross-repo search
**Result:** Risk score escalated from 19 → 65, decision changed from APPROVE → WARN
**Outcome:** Incident prevented through coordinated PR strategy

---

## How It Works

```
1. Extract PR metadata (gh CLI)
   ↓
2. Load context (architecture, tests, related repos)
   ↓
3. Launch 4 parallel analyzer agents
   ├─ Risk Analyzer
   ├─ Test Validator
   ├─ Impact Analyzer (with K8s detection)
   └─ Cross-Repo Analyzer
   ↓
4. Decision Engine aggregates results
   ├─ Calculate weighted risk score
   ├─ Apply critical overrides (K8s renames, etc.)
   └─ Generate decision
   ↓
5. Generate HTML + Markdown reports
```

### Risk Scoring Algorithm

```python
Overall Risk = (
    Risk Analysis × 40% +
    Test Coverage (inverse) × 30% +
    Architecture Impact × 20% +
    Cross-Repo Impact × 10%
)

# Critical Override: K8s resource rename with cross-repo refs
if k8s_rename and critical_references:
    breaking_risk = 95  # Escalate
    min_risk_floor = 65  # Apply minimum
```

---

## File Structure

```
risk-assessment/
├── SKILL.md                    ← Main skill orchestrator
├── prompts/
│   ├── risk-analyzer.md        ← Security, breaking changes, patterns
│   ├── test-validator.md       ← Test coverage analysis
│   ├── impact-analyzer.md      ← Architecture + K8s detection
│   └── crossrepo-analyzer.md   ← Cross-repo intelligence
├── scripts/
│   ├── decision_engine.py      ← Aggregates analyzer results
│   ├── frontmatter.py          ← YAML frontmatter utilities
│   ├── k8s_resource_detector.py ← Detects K8s renames
│   ├── search_cross_repo_refs.py ← Searches for hardcoded refs
│   ├── html_generator.py       ← Main report HTML
│   ├── analyzer_html_generator.py ← Analyzer report HTML
│   └── ... (other utilities)
├── examples/
│   └── pr-489-demo/            ← Real incident detection example
└── README.md                   ← This file
```

---

## Dependencies

### Required
- Python 3.9+
- GitHub CLI (`gh`)
- Git

### Optional
- JIRA_TOKEN env var (for Jira epic/story context)

### Python Packages
No external packages required - uses Python standard library only.

---

## Usage Examples

### Basic Analysis
```bash
/risk-assessment 3329 --repo opendatahub-io/odh-dashboard --dry-run
```

### With Jira Context
```bash
export JIRA_TOKEN="your-token"
/risk-assessment 7292 --repo opendatahub-io/odh-dashboard --dry-run
```

### Headless Mode (CI/CD)
```bash
/risk-assessment 489 --repo opendatahub-io/model-registry-operator --headless --dry-run
```

---

## Configuration

The skill works out-of-the-box, but you can customize context repositories in `scripts/fetch-context.sh`:

```bash
CONTEXT_REPOS=(
    "opendatahub-io/odh-dashboard"
    "opendatahub-io/kserve"
    "opendatahub-io/notebooks"
    # Add your repos here
)
```

---

## Incident Detection Capabilities

### Kubernetes Resource Renames
Automatically detects when ConfigMaps, Secrets, CRDs, or Services are renamed and searches for hardcoded references in related repositories.

**Example Pattern Caught:**
```yaml
# Before
- model-catalog-default-sources

# After
+ default-catalog-sources
```

**Action:** Searches related repos for `model-catalog-default-sources`, finds 13 references in dashboard code/tests, escalates risk to 65/100.

### Other Patterns
- Authentication/authorization changes
- Database migration without rollback
- API signature modifications
- Critical path changes without tests

---

## Output Artifacts

```
artifacts/
├── pr-analyses/
│   ├── pr-{number}-analysis.html    ← Main report (HTML)
│   └── pr-{number}-analysis.md      ← Main report (Markdown)
├── risk-findings/
│   ├── risk-{number}.html
│   └── risk-{number}.md
├── test-coverage/
│   ├── test-{number}.html
│   └── test-{number}.md
├── impact-assessments/
│   ├── impact-{number}.html
│   └── impact-{number}.md
└── crossrepo-intel/
    ├── crossrepo-{number}.html
    └── crossrepo-{number}.md
```

---

## Integration

### GitHub Actions (Future)
```yaml
- name: PR Quality Check
  run: |
    /risk-assessment ${{ github.event.pull_request.number }} \
      --repo ${{ github.repository }} \
      --headless
```

### CI/CD Pipeline
Run as part of your PR validation pipeline to get automated quality gates.

---

## Troubleshooting

**"PR metadata extraction failed"**
- Ensure `gh` CLI is authenticated: `gh auth status`
- Check PR number and repo are correct

**"Context repositories not found"**
- Context repos are optional - skill works without them
- Check network access if using private repos

**"No analyzer outputs"**
- Check Python 3.9+ is available
- Verify scripts have execute permissions

---

## Learn More

- **Architecture:** See main SKILL.md for detailed orchestration flow
- **Demo:** Explore `examples/pr-489-demo/` for real-world analysis
- **Customization:** Edit prompts in `prompts/` to adjust analyzer behavior

---

**Part of the Red Hat Quality Tiger Team**
