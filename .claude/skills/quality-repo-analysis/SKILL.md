---
name: quality-repo-analysis
description: Analyzes a repository's quality practices and provides actionable recommendations for improvement
---

# Quality Repository Analysis Skill

Analyzes a repository's quality practices and provides actionable recommendations for improvement.

## Usage

```bash
/quality-repo-analysis [repository-url]
```

## Examples

```bash
/quality-repo-analysis https://github.com/opendatahub-io/kserve
/quality-repo-analysis https://github.com/kubeflow/training-operator
```

## What It Analyzes

This skill performs a comprehensive quality assessment across 8 dimensions:

### 1. Unit Tests (15%)
- Test file detection: `*_test.go`, `*.spec.ts`, `*.test.ts`, `*_test.py`
- Framework detection and usage patterns
- Test-to-code ratio calculation
- Test isolation patterns and best practices

### 2. Integration/E2E Tests (20%)
- `e2e/` and `integration/` directory presence and organization
- Multi-version testing support
- Cluster setup verification (Kind, Minikube, envtest)
- Test scenario coverage and breadth

### 3. Build Integration (15%)
- PR workflow Docker image building
- Konflux build simulation
- Operator manifest validation
- Kustomize overlay verification

### 4. Image Testing (10%)
- Dockerfile/Containerfile analysis and best practices
- Multi-stage build usage
- Base image selection and security
- Runtime validation with Testcontainers
- Multi-architecture support

### 5. Coverage Tracking (10%)
- `.codecov.yml` configuration
- Coverage threshold enforcement
- PR coverage reporting integration
- `--coverprofile` or `pytest-cov` usage in CI
- Coverage gate enforcement

### 6. CI/CD Automation (15%)
- Workflow inventory and trigger mapping
- PR-triggered vs. periodic job analysis
- Concurrency control mechanisms
- Caching strategies and optimization
- Test parallelization patterns

### 7. Static Analysis (10%)
- Linting configuration (golangci-lint, ESLint, ruff, etc.)
- FIPS compatibility checks (crypto imports, build tags, base images)
- Dependency alert configuration (Dependabot, Renovate)
- Pre-commit hooks and enforcement

### 8. Agent Rules (5%)
- `CLAUDE.md` or `AGENTS.md` presence
- `.claude/rules/` directory and rule files
- Test creation rule coverage
- Rule quality assessment (comprehensive, actionable, framework-specific)

## Output

The skill automatically generates a comprehensive report in **two formats**:

### 1. Markdown Report
A detailed markdown document saved as `quality-analysis-{repo}.md` with:

- **YAML Frontmatter** - Structured data for reliable HTML generation (scorecard, gaps, wins, recommendations)
- **Quality Scorecard** - Overall scores across dimensions
- **Critical Gaps** - High-priority issues to address
- **Quick Wins** - Low-effort, high-impact improvements
- **Detailed Findings** - File-by-file analysis
- **Recommendations** - Prioritized action items
- **Comparison** - Benchmarking against gold standards

### 2. HTML Report (Interactive) - **Generated Automatically**
An interactive, visually-rich HTML page saved as `quality-report-{repo}.html` with:

- **Animated score visualization** - Circular progress indicator for overall score
- **Interactive scorecard** - Hover effects and color-coded scores
- **Collapsible sections** - Expand/collapse sections for easy navigation
- **Color-coded severity** - Visual indicators for critical gaps (RED=High, YELLOW=Medium, GREEN=Low)
- **Responsive design** - Works on desktop and mobile devices
- **Zero dependencies** - Pure HTML/CSS/JS, no external libraries required
- **Automatically opened** - Opens in your default browser after generation

Both files are created automatically when you run the skill. No manual steps required!

## Gold Standards

The analysis compares repositories against these gold standards:

- **odh-dashboard**: Multi-layer testing, contract tests, comprehensive CI/CD
- **notebooks**: Image testing best practices, 5-layer validation
- **kserve**: Coverage enforcement, multi-version testing
- **Kubernetes projects**: Industry best practices for operators

## Scoring Criteria

Each dimension is scored 0-10:

- **10**: Gold standard, exceeds expectations
- **8-9**: Strong practices, minor gaps
- **6-7**: Adequate, moderate improvements needed
- **4-5**: Weak, significant gaps
- **0-3**: Critical gaps, major work required

Overall score is weighted average:
- Unit Tests: 15%
- Integration/E2E: 20%
- Build Integration: 15%
- Image Testing: 10%
- Coverage Tracking: 10%
- CI/CD Automation: 15%
- Static Analysis: 10%
- Agent Rules: 5%

## Implementation Details

The skill uses the Agent tool to:

1. Clone and analyze the target repository
2. Examine CI/CD workflows in `.github/workflows/`
3. Analyze test files and frameworks
4. Review build and deployment configurations
5. Check static analysis, FIPS compatibility, and dependency alerts
6. Compare against gold standard practices
7. Generate prioritized recommendations

## Time Estimate

- Quick analysis: 5-10 minutes
- Comprehensive analysis: 15-20 minutes
- With detailed recommendations: 20-30 minutes

## Requirements

- Repository must be publicly accessible
- Works best with Go, TypeScript/JavaScript, Python projects
- Analyzes Kubernetes operators, web applications, and CLI tools
- Python 3.6+ required for HTML report generation

## Files

- `SKILL.md` - This documentation
- `instructions.md` - Detailed analysis instructions for the agent
- `html_generator.py` - Converts markdown reports to interactive HTML
- `sample_report.md` - Example markdown report
- `sample_output.html` - Example HTML visualization
