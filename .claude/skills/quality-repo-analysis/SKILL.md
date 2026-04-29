---
name: quality-repo-analysis
description: Analyzes a repository's quality practices and provides actionable recommendations for improvement - assesses CI/CD, test coverage, code quality, security, and generates interactive HTML reports
user-invocable: true
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

This skill performs a comprehensive quality assessment across multiple dimensions:

### 1. CI/CD Pipeline Analysis
- What tests run on PRs vs. periodic jobs
- Workflow organization and efficiency
- Concurrency control and caching
- Build automation

### 2. Test Coverage Assessment
- Unit test coverage and frameworks
- Integration test infrastructure
- E2E test coverage and execution
- Test-to-code ratio
- Coverage tracking and enforcement

### 3. Code Quality Tools
- Linting configuration (golangci-lint, ESLint, etc.)
- Pre-commit hooks
- Static analysis tools
- Code formatters

### 4. Container Image Testing
- Image build process
- Runtime validation
- Vulnerability scanning
- Multi-architecture support
- SBOM generation

### 5. Security Practices
- Container scanning (Trivy, Snyk)
- SAST/CodeQL integration
- Dependency scanning
- Secret detection

### 6. Agent Rules Assessment (NEW)
- Checks for `.claude/rules/` directory
- Evaluates rule completeness (all test types covered)
- Assesses rule quality (comprehensive, actionable)
- Identifies gaps and missing test type rules

### 7. Testing Frameworks
- Unit testing frameworks
- Integration testing tools
- E2E testing infrastructure
- Mocking strategies

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
- Unit Tests: 20%
- Integration/E2E: 25%
- Image Testing: 20%
- Coverage Tracking: 15%
- CI/CD Automation: 20%

## Implementation Details

The skill uses the Agent tool to:

1. Clone and analyze the target repository
2. Examine CI/CD workflows in `.github/workflows/`
3. Analyze test files and frameworks
4. Review build and deployment configurations
5. Check for security scanning integration
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
