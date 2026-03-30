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

The skill generates a comprehensive report including:

1. **Quality Scorecard** - Overall scores across dimensions
2. **Critical Gaps** - High-priority issues to address
3. **Quick Wins** - Low-effort, high-impact improvements
4. **Detailed Findings** - File-by-file analysis
5. **Recommendations** - Prioritized action items
6. **Comparison** - Benchmarking against gold standards

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
