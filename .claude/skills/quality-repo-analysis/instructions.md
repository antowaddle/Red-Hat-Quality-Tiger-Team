# Quality Repository Analysis - Instructions

## Task

Analyze a given repository's quality practices and provide actionable recommendations.

## Input

- Repository URL (required)
- Branch name (optional, defaults to main/master)

## Process

### Step 0: Pre-flight Checks

**CRITICAL**: Verify Python dependencies before starting the analysis.

1. **Check PyYAML availability**
   - Run this command to verify PyYAML can be imported:
   ```bash
   uv run --with pyyaml python3 -c "import yaml; print('✅ PyYAML available')"
   ```

2. **If the check fails**, install dependencies:
   ```bash
   uv pip install -r .claude/skills/quality-repo-analysis/requirements.txt
   ```
   Or use `uv run --with pyyaml` to automatically handle dependencies.

3. **Do NOT proceed** with the analysis until PyYAML is confirmed available.
   - Without PyYAML, the HTML generator will fall back to a less reliable parser
   - This can result in missing data in the final report

### Step 1: Repository Discovery

1. Clone or access the repository
2. Identify repository type (operator, web app, CLI, library)
3. Detect primary language(s) (Go, TypeScript, Python, Java, etc.)
4. Identify framework (Kubernetes operator, React app, etc.)

### Step 2: CI/CD Analysis

Analyze `.github/workflows/` or equivalent CI configuration:

1. **Workflow Inventory**
   - List all workflows and their triggers
   - Identify PR-triggered vs. periodic workflows
   - Check for concurrency control
   - Verify caching strategies

2. **Test Automation**
   - What tests run on PRs?
   - What tests are manual/dispatch-only?
   - Are E2E tests automated or manual?
   - Test execution time and parallelization

3. **Build Process**
   - Image build configuration
   - Multi-architecture support
   - Build caching and optimization

### Step 3: Test Coverage Analysis

Examine test files and configuration:

1. **Unit Tests**
   - Count test files (e.g., `*_test.go`, `*.spec.ts`)
   - Identify testing framework
   - Calculate test-to-code ratio
   - Check coverage generation

2. **Integration Tests**
   - Identify integration test suites
   - Check for test isolation
   - Review test data management
   - Assess test fixtures

3. **E2E Tests**
   - Examine E2E test infrastructure
   - Check multi-version testing
   - Review test scenarios coverage
   - Validate cluster setup (Kind, Minikube, etc.)

4. **Coverage Tracking**
   - Check for coverage file generation
   - Verify codecov/coveralls integration
   - Look for coverage thresholds
   - Check PR coverage reporting

### Step 4: Code Quality Assessment

Review linting and quality tools:

1. **Linting Configuration**
   - Go: `.golangci.yaml`, number of enabled linters
   - TypeScript: `eslintrc`, `tsconfig.json` strictness
   - Python: `ruff.toml`, `flake8`, `mypy.ini`

2. **Pre-commit Hooks**
   - Check `.pre-commit-config.yaml`
   - Verify hook enforcement
   - Review configured checks

3. **Static Analysis**
   - SAST tools (CodeQL, gosec, Semgrep)
   - Dependency scanning
   - Secret detection (Gitleaks, TruffleHog)

### Step 5: Build Integration Analysis (CRITICAL)

**NEW - CRITICAL DIMENSION**: Analyze PR-time build validation

1. **PR Build Validation**
   - Does PR workflow build Docker image?
   - Build mode testing (RHOAI vs ODH, etc.)
   - Multi-stage build validation
   - Image startup testing

2. **Integration Testing**
   - Operator manifest application
   - Kustomize overlay validation
   - Kind/Minikube deployment testing
   - Module Federation validation (if applicable)

3. **Manifest Generation**
   - ConfigMap generation validation
   - Kustomize build verification
   - CRD installation testing (operators)
   - Resource manifest validation

4. **Cross-Component Build** (Monorepos)
   - All packages build together
   - Module Federation remotes validated
   - BFF services buildable
   - Integration manifests correct

**Critical Gap**: If PR builds pass but Konflux/production builds fail:
- ❌ No PR-time Konflux simulation
- ❌ No operator integration testing
- ❌ Build issues discovered post-merge

### Step 6: Container Image Testing

Analyze image build and testing:

1. **Build Process**
   - Dockerfile/Containerfile analysis
   - Multi-stage builds
   - Base image selection
   - Platform support

2. **Runtime Testing**
   - Image startup validation
   - Functional testing (Testcontainers, etc.)
   - Deployment testing (Kind, Minikube)

3. **Security Scanning**
   - Trivy/Snyk integration
   - Vulnerability thresholds
   - SBOM generation
   - Image signing/attestation

### Step 7: Agent Rules Analysis

Check for existing Claude Code agent rules and test automation guidance:

1. **Check for Agent Rules**
   - Look for `CLAUDE.md` or `AGENTS.md` in root
   - Check for `.claude/` directory
   - Examine `.claude/rules/` for test creation rules
   - Review `.claude/skills/` for custom skills

2. **Analyze Test Automation Guidance**
   - Test creation rules (unit-tests.md, e2e-tests.md, etc.)
   - Testing standards documentation
   - Contract test guidelines
   - Mock test patterns

3. **Evaluate Rule Completeness**
   - Are rules comprehensive? (cover all test types)
   - Are rules up-to-date? (match current test patterns)
   - Are rules actionable? (specific patterns, examples, checklists)
   - Are rules framework-specific? (Jest, Cypress, Go testing, etc.)

4. **Gap Identification**
   - Missing test type rules
   - Outdated patterns
   - Lack of examples
   - No quality gates/checklists

### Step 8: Gap Analysis

Compare findings against gold standards:

1. **odh-dashboard comparison**
   - Multi-layer testing
   - Contract testing
   - Comprehensive CI/CD
   - Coverage enforcement
   - Comprehensive agent rules

2. **notebooks comparison**
   - Image testing strategy
   - Multi-architecture support
   - Security scanning

3. **Kubernetes best practices**
   - Operator testing patterns
   - CRD validation
   - Webhook testing

### Step 9: Generate Report

Create structured report with:

1. **Executive Summary**
   - Overall quality score (0-10)
   - Critical gaps
   - Top 3 recommendations

2. **Detailed Scorecard**
   - Score per dimension
   - Comparison table
   - Trend indicators

3. **Critical Gaps**
   - Missing coverage enforcement
   - No image scanning
   - E2E not automated
   - Security vulnerabilities

4. **Quick Wins** (High ROI, Low Effort)
   - Add codecov integration (2-4 hours)
   - Add Trivy scanning (1-2 hours)
   - Enable pre-commit hooks (1-2 hours)

5. **Prioritized Recommendations**
   - P0: Critical gaps (coverage, security)
   - P1: High-value improvements (E2E, contracts)
   - P2: Nice-to-have (performance tests, etc.)

6. **Implementation Guidance**
   - Example code snippets
   - Workflow templates
   - Configuration examples

## Step 10: Generate Reports (Markdown + HTML)

After completing the analysis, generate both markdown and HTML reports:

1. **Save the Markdown Report**
   - Write the complete markdown analysis to a file: `quality-analysis-{repo}.md`
   - **CRITICAL**: Include YAML frontmatter at the top with all structured data
   - Include detailed markdown content after the frontmatter

2. **Automatically Generate HTML Report**
   - Run the HTML generator using uv to ensure dependencies are available:
   ```bash
   uv run --with pyyaml python3 .claude/skills/quality-repo-analysis/html_generator.py quality-analysis-{repo}.md quality-report-{repo}.html
   ```
   - This creates an interactive HTML page with:
     - Animated score circles
     - Color-coded severity indicators  
     - Collapsible sections
     - Responsive design
   - Note: `uv run --with pyyaml` ensures PyYAML is installed without requiring global installation

3. **Open the HTML Report**
   - Open the generated HTML file in the default browser:
   ```bash
   open quality-report-{repo}.html  # macOS
   ```

4. **Provide Summary**
   - Inform the user that both reports have been generated:
     - `quality-analysis-{repo}.md` - Detailed markdown for archiving
     - `quality-report-{repo}.html` - Interactive visualization for sharing
   - Provide the file paths so they can easily find the reports

## Output Format

**IMPORTANT**: Reports MUST include YAML frontmatter for structured data extraction. This enables reliable HTML report generation.

```markdown
---
repository: "owner/repo-name"
overall_score: 7.8
scorecard:
  - dimension: "Unit Tests"
    score: 8.0
    status: "Strong test coverage with Go testing framework"
  - dimension: "Integration/E2E"
    score: 9.0
    status: "Comprehensive E2E suite with multi-version testing"
  - dimension: "Build Integration"
    score: 4.0
    status: "No PR-time Konflux simulation or image validation"
  - dimension: "Image Testing"
    score: 6.0
    status: "Basic image builds but limited runtime validation"
  - dimension: "Coverage Tracking"
    score: 8.0
    status: "Codecov integration with enforcement"
  - dimension: "CI/CD Automation"
    score: 9.0
    status: "Well-organized workflows with caching"
  - dimension: "Agent Rules"
    score: 2.0
    status: "No test automation guidance for AI agents"
critical_gaps:
  - title: "Missing PR-time build integration testing"
    impact: "Build failures discovered only after merge in Konflux"
    severity: "HIGH"
    effort: "8-12 hours"
  - title: "No container image runtime validation"
    impact: "Image startup issues not caught until deployment"
    severity: "HIGH"
    effort: "4-6 hours"
quick_wins:
  - title: "Add Trivy scanning to PR workflow"
    effort: "1-2 hours"
    impact: "Early detection of security vulnerabilities in dependencies"
  - title: "Create basic agent rules for unit test patterns"
    effort: "2-3 hours"
    impact: "Improve AI-generated test quality and consistency"
recommendations:
  priority_0:
    - "Implement PR-time Konflux build simulation to catch build issues before merge"
    - "Add container runtime validation tests for all built images"
  priority_1:
    - "Add contract tests for API boundaries between components"
    - "Create comprehensive agent rules for test automation (.claude/rules/)"
  priority_2:
    - "Add performance regression testing for prediction endpoints"
    - "Implement chaos engineering tests for resilience"
---

# Quality Analysis: [Repository Name]

## Executive Summary
- Overall Score: X/10
- Key Strengths: ...
- Critical Gaps: ...
- Agent Rules Status: [Present/Missing/Incomplete]

## Quality Scorecard
| Dimension | Score | Status |
|-----------|-------|--------|
| Unit Tests | X/10 | ... |
| Integration/E2E | X/10 | ... |
| **Build Integration** | **X/10** | **...** |
| Image Testing | X/10 | ... |
| Coverage Tracking | X/10 | ... |
| CI/CD Automation | X/10 | ... |
| Agent Rules | X/10 | ... |

## Critical Gaps
1. [Gap description]
   - Impact: ...
   - Severity: HIGH/MEDIUM/LOW
   - Effort: X hours

## Quick Wins
1. [Improvement description]
   - Effort: X hours
   - Impact: [description]
   - Implementation: [code example]

## Detailed Findings
### CI/CD Pipeline
[Analysis...]

### Test Coverage
[Analysis...]

### Code Quality
[Analysis...]

### Container Images
[Analysis...]

### Security
[Analysis...]

### Agent Rules (Agentic Flow Quality)
[Analysis of existing agent rules]
- **Status**: Present/Missing/Incomplete
- **Coverage**: Which test types have rules?
- **Quality**: Are rules comprehensive, up-to-date, actionable?
- **Gaps**: What's missing?
- **Recommendation**: Generate missing rules with /test-rules-generator

## Recommendations

### Priority 0 (Critical)
[Items...]

### Priority 1 (High Value)
[Items...]

### Priority 2 (Nice-to-Have)
[Items...]

## Comparison to Gold Standards
[Table comparing to odh-dashboard, notebooks, etc.]

## File Paths Reference
[Key configuration files analyzed]
```

## Key Files to Examine

### CI/CD
- `.github/workflows/*.yml`
- `.github/workflows/*.yaml`
- `Makefile` (test targets)
- `.gitlab-ci.yml` (if GitLab)
- `Jenkinsfile` (if Jenkins)

### Testing
- `*_test.go`, `*_test.py`, `*.spec.ts`, `*.test.ts`
- `test/`, `tests/` directories
- `e2e/`, `integration/` directories
- `pytest.ini`, `go.mod` (test dependencies)

### Code Quality
- `.golangci.yaml`, `.golangci.yml`
- `.eslintrc.js`, `eslintrc.json`
- `ruff.toml`, `.flake8`, `mypy.ini`
- `.pre-commit-config.yaml`

### Container Images
- `Dockerfile`, `Containerfile`
- `docker-compose.yml`
- `.dockerignore`

### Coverage
- `.codecov.yml`, `codecov.yml`
- `.coveragerc`

### Security
- `.github/workflows/codeql.yml`
- `.gitleaks.toml`
- `.trivyignore`

### Agent Rules
- `CLAUDE.md`, `AGENTS.md` (root documentation)
- `.claude/` directory
- `.claude/rules/*.md` (test creation rules)
- `.claude/skills/` (custom skills)
- `docs/` (testing documentation)

## Special Considerations

### For Kubernetes Operators

- Check for envtest usage
- Verify CRD testing
- Review webhook validation tests
- Assess RBAC test coverage
- Check for multi-namespace testing

### For Web Applications

- Frontend test coverage
- API contract testing
- BFF (Backend for Frontend) tests
- Accessibility testing
- Performance testing

### For CLI Tools

- Command testing
- Integration tests
- Cross-platform testing
- Installation testing

## Error Handling

If repository is:
- **Private**: Request user to provide access or run locally
- **Very large**: Focus on key directories (`.github`, `test`, root configs)
- **Polyglot**: Analyze each language separately
- **Monorepo**: Analyze each component or aggregate

## Time Management

- Quick scan: 5-10 minutes (high-level only)
- Standard analysis: 15-20 minutes (detailed)
- Comprehensive: 20-30 minutes (with examples)

Adjust depth based on repository size and complexity.
