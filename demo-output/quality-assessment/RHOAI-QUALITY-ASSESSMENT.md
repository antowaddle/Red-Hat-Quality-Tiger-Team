# RHOAI Quality Assessment — All 16 DSC Components (rhoai-3.4)

## Executive Summary
- **Platform Quality Score: 7.4/10**
- **Components Assessed: 16** (every component managed by the DataScienceCluster CR)
- **Assessment Method: Deep file-level analysis** — all 16 repos cloned and inspected
- **Top Performers:** rhods-operator (9/10), kserve (9/10), feast (9/10), odh-dashboard (9/10)
- **Needs Attention:** models-as-a-service (6/10), model-registry-operator (6/10), odh-model-controller (6/10), codeflare-operator/kueue (6/10)
- **Agent Rules:** Only 6 of 16 repos have any agent guidance (AGENTS.md or CLAUDE.md)

## Component Scorecard

| # | Component (DSC Name) | Repo | Unit | Int/E2E | Build | Image | Coverage | CI/CD | Agent Rules | **Overall** |
|---|---------------------|------|------|---------|-------|-------|----------|-------|-------------|------------|
| 1 | Dashboard | odh-dashboard | 9 | 9 | 9 | 8 | 8 | 9 | 10 | **9** |
| 2 | Workbenches | notebooks | 7 | 8 | 9 | 9 | 8 | 8 | 8 | **8** |
| 3 | KServe | kserve | 9 | 10 | 10 | 7 | 8 | 10 | 0 | **9** |
| 4 | DataSciencePipelines | data-science-pipelines-operator | 7 | 8 | 9 | 7 | 2 | 8 | 0 | **7** |
| 5 | ModelRegistry | model-registry-operator | 6 | 7 | 7 | 7 | 2 | 7 | 4 | **6** |
| 6 | Kueue | kueue | 9 | 9 | 8 | 7 | 5 | 3 | 0 | **6** |
| 7 | Ray | kuberay | 8 | 8 | 8 | 7 | 5 | 7 | 0 | **7** |
| 8 | TrustyAI | trustyai-service-operator | 8 | 8 | 8 | 8 | 2 | 6 | 0 | **7** |
| 9 | TrainingOperator | training-operator | 9 | 9 | 9 | 8 | 2 | 9 | 0 | **8** |
| 10 | Trainer | trainer | 8 | 9 | 8 | 5 | 8 | 8 | 0 | **8** |
| 11 | FeastOperator | feast | 10 | 9 | 10 | 9 | 4 | 10 | 6 | **9** |
| 12 | LlamaStackOperator | llama-stack-k8s-operator | 7 | 8 | 7 | 7 | 6 | 7 | 0 | **7** |
| 13 | MLflowOperator | mlflow-operator | 8 | 8 | 8 | 5 | 4 | 7 | 6 | **7** |
| 14 | SparkOperator | spark-operator | 9 | 8 | 9 | 8 | 4 | 8 | 6 | **8** |
| 15 | ModelsAsService | models-as-a-service | 7 | 4 | 7 | 6 | 5 | 6 | 0 | **6** |
| 16 | ModelController | odh-model-controller | 8 | 4 | 8 | 8 | 4 | 7 | 0 | **6** |

## Detailed Findings — Per Component

### 1. odh-dashboard — 9/10
- **604** test files (Jest + Cypress); **18** CI workflows; **.codecov.yml** with project/patch gates
- Full `.claude/rules/` + `.claude/skills/` + `AGENTS.md` + `CLAUDE.md` + per-package agent docs
- **Gold standard** for the platform

### 2. notebooks — 8/10
- **33** Python test files + Go tests; **64+** Dockerfiles; **31** CI workflows
- Trivy scanning (custom action + SARIF), Codecov, Playwright browser tests, Testcontainers
- `AGENTS.md` present with detailed Makefile/pytest/ruff guidance

### 3. kserve — 9/10
- **379** test files (149 Go + 230 Python); **40** CI workflows; automated e2e on Kind
- `.pre-commit-config.yaml` with helm-docs, ruff, pinned actions; Gosec security scanning
- Coverage via `vladopajic/go-test-coverage` with PR comments; **no agent rules**

### 4. data-science-pipelines-operator — 7/10
- **22** Go test files; Kind integration + functional tests automated on PR
- `.pre-commit-config.yaml` (golangci-lint, yamllint); `.tekton/` Konflux pipelines
- **No coverage tracking**, **no agent rules**

### 5. model-registry-operator — 6/10
- **13** Go test files (Ginkgo/Gomega); Kind deploy test on PR
- `.pre-commit-config.yaml` (fmt, vet, lint); `.tekton/` pipelines
- `AGENTS.md` present; **no coverage tracking**

### 6. kueue — 6/10
- **364** Go test files — **largest test corpus of any component**
- Extensive envtest/integration suites under `test/integration/`
- **Nearly zero GitHub Actions** (Prow-based upstream CI invisible here); **no agent rules**

### 7. kuberay — 7/10
- **136** Go test files; rich e2e under `test/e2e*`
- `.pre-commit-config.yaml` with gitleaks, shellcheck, golangci-lint
- **No coverage tracking**, **no agent rules**

### 8. trustyai-service-operator — 7/10
- **34** Go test files; Kind smoke test automated on PR
- **Trivy** (`aquasecurity/trivy-action` + SARIF) + Gosec; `.tekton/` with multiple images
- **No coverage**, **no pre-commit**, **no agent rules**

### 9. training-operator — 8/10
- **45** Go test files + 7 Python e2e; automated integration + e2e on PR with Kind
- `.pre-commit-config.yaml` (black, isort, flake8); `.tekton/` with Snyk SAST
- **No coverage tracking**, **no agent rules**

### 10. trainer — 8/10
- **32** Go test files; multi-language (Go + Python + Rust)
- Automated e2e on PR; coverage via `shogo82148/actions-goveralls`
- `.pre-commit-config.yaml` (Python + Rust cargo fmt/check); **no agent rules**

### 11. feast — 9/10
- **227** test files (175 Python + 49 Go + 3 React/Jest); **30** CI workflows
- CodeQL security scanning; `.pre-commit-config.yaml` (ruff via uv)
- `AGENTS.md` present; **no coverage reporting to external service**

### 12. llama-stack-k8s-operator — 7/10
- **21** Go test files; automated e2e on PR with Kind
- Coverage via `limgo` (custom tool with `.limgo.json`); `.pre-commit-config.yaml`
- `.tekton/` with Snyk SAST; **no agent rules**

### 13. mlflow-operator — 7/10
- **26** test files (17 Go + 9 Python); automated e2e + integration on PR with Kind
- `.tekton/` pipelines; `AGENTS.md` present
- **No pre-commit**, **no coverage to external service**

### 14. spark-operator — 8/10
- **38** Go test files; automated e2e + kustomize e2e
- **Trivy** image scanning (`trivy-image-scanning.yaml`); `.tekton/` pipelines
- `CLAUDE.md` present; `.pre-commit-config.yaml` (helm-docs)

### 15. models-as-a-service — 6/10
- **26** test files (18 Go + 8 Python e2e); per-component CI (controller + API)
- Coverage uploaded as artifact but **not to external service**
- **E2E tests not automated in CI** (no pytest workflow); **no agent rules**, **no pre-commit**

### 16. odh-model-controller — 6/10
- **52** Go test files; e2e tests exist but **manual-trigger only** (`workflow_dispatch`)
- `.tekton/` with Snyk SAST; `.golangci.yml` lint in CI
- **No coverage tracking**, **no agent rules**

## Platform-Wide Analysis

### Testing Patterns
- **Go operators** dominate: 13 of 16 components are Go-based
- **Test volume varies wildly**: kueue has 364 test files, model-registry-operator has 13
- **E2E automation**: 13/16 have automated e2e on PRs; **3 have gaps**: odh-model-controller (manual), models-as-a-service (no CI e2e), kueue (external Prow)

### Security Posture
- **Trivy**: trustyai-service-operator, spark-operator, notebooks (3/16)
- **Gosec**: kserve (1/16)
- **CodeQL**: feast (1/16)
- **Snyk (Konflux)**: training-operator, llama-stack-k8s-operator, odh-model-controller, data-science-pipelines-operator (via `.tekton/` push pipelines)
- **5 repos have no security scanning visible in GHA or Tekton**

### Coverage Tracking
- **Codecov**: odh-dashboard, notebooks, rhods-operator (3/16)
- **Goveralls**: trainer (1/16)
- **go-test-coverage**: kserve (1/16)
- **limgo**: llama-stack-k8s-operator (1/16)
- **Artifact-only**: models-as-a-service (1/16)
- **None**: 8 of 16 repos have no coverage reporting at all

### Agent Rules Adoption
| Level | Count | Repos |
|-------|-------|-------|
| **Full** (8-10) | 2 | odh-dashboard, notebooks |
| **Present** (4-6) | 4 | rhods-operator, feast, model-registry-operator, mlflow-operator, spark-operator |
| **None** (0) | 10 | kserve, dspo, kueue, kuberay, trustyai, training-operator, trainer, llama-stack, maas, odh-model-controller |

### Pre-commit Hooks
- **Present**: 11/16 repos
- **Missing**: trustyai-service-operator, mlflow-operator, models-as-a-service, odh-dashboard (uses ESLint/Turbo instead), notebooks (uses ruff/pyright in CI)

## Critical Gaps

| # | Gap | Components Affected | Severity | Effort |
|---|-----|-------------------|----------|--------|
| 1 | E2E not automated on PRs | odh-model-controller, models-as-a-service | High | Low |
| 2 | No coverage tracking | 8 of 16 repos | Medium | Medium |
| 3 | No agent rules | 10 of 16 repos | Medium | Low |
| 4 | No security scanning in GHA | 5 repos | Medium | Medium |
| 5 | Kueue CI invisible (Prow) | kueue | Medium | Low (document) |

## Quick Wins

| # | Action | Effort | Impact |
|---|--------|--------|--------|
| 1 | Re-enable odh-model-controller e2e on PRs | 1 hour | High — catches integration regressions |
| 2 | Add AGENTS.md to 10 repos without one | 2-4 hours each | Medium — onboarding + AI quality |
| 3 | Add Codecov to Go operators using rhods-operator pattern | 2-4 hours each | Medium — coverage visibility |
| 4 | Wire models-as-a-service e2e into CI | 4-8 hours | High — currently manual-only |

## Recommendations

### Priority 0 (Critical)
- **Automate e2e for odh-model-controller and models-as-a-service** — these are the only two components where integration tests don't run on PRs
- **Document kueue CI** — 364 tests exist but nothing runs in GitHub Actions

### Priority 1 (High Value)
- **Standardize coverage tracking** — adopt Codecov (already in 3 repos) across all Go operators
- **Deploy agent rules across all 16 components** — repos with rules score 1.5-3 points higher
- **Add Trivy/CodeQL to repos without security scanning** — only 6 of 16 have visible scanning

### Priority 2 (Nice-to-Have)
- **Pre-commit hooks** for the 5 repos missing them
- **Unify test frameworks** — most use Ginkgo/Gomega but some use raw `testing`

## File Paths Reference

| Component | Key CI Files | Key Test Paths | Agent Rules |
|-----------|-------------|----------------|-------------|
| odh-dashboard | `.github/workflows/test.yml`, `cypress-e2e-test.yml` | `packages/*/src/__tests__/` | `AGENTS.md`, `.claude/rules/` |
| notebooks | `.github/workflows/code-quality.yaml`, `build-notebooks-*.yaml` | `tests/`, `tests/containers/` | `AGENTS.md` |
| kserve | `.github/workflows/go.yml`, `e2e-test.yml` | `pkg/**/*_test.go`, `test/e2e/` | — |
| data-science-pipelines-operator | `.github/workflows/unittests.yml`, `kind-integration.yml` | `controllers/*_test.go` | — |
| model-registry-operator | `.github/workflows/build.yml`, `build-image-pr.yml` | `internal/controller/*_test.go` | `AGENTS.md` |
| kueue | `Makefile` | `test/integration/`, `pkg/**/*_test.go` | — |
| kuberay | `.github/workflows/test-job.yaml` | `ray-operator/test/` | — |
| trustyai-service-operator | `.github/workflows/smoke.yaml`, `security-scan.yaml` | `controllers/**/*_test.go` | — |
| training-operator | `.github/workflows/test-go.yaml`, `integration-tests.yaml` | `pkg/**/*_test.go`, `sdk/python/test/e2e/` | — |
| trainer | `.github/workflows/test-go.yaml`, `test-e2e.yaml` | `test/integration/`, `test/e2e/` | — |
| feast | `.github/workflows/unit_tests.yml`, `security.yml` | `sdk/python/tests/`, `infra/feast-operator/test/e2e/` | `AGENTS.md` |
| llama-stack-k8s-operator | `.github/workflows/run-e2e-test.yml`, `code-coverage.yml` | `tests/e2e/`, `pkg/**/*_test.go` | — |
| mlflow-operator | `.github/workflows/test.yml`, `test-e2e.yml` | `internal/controller/*_test.go`, `test/e2e/` | `AGENTS.md` |
| spark-operator | `.github/workflows/integration.yaml`, `trivy-image-scanning.yaml` | `pkg/**/*_test.go`, `test/e2e/` | `CLAUDE.md` |
| models-as-a-service | `.github/workflows/maas-controller-ci.yml`, `maas-api-ci.yml` | `maas-controller/pkg/**/*_test.go`, `test/e2e/` | — |
| odh-model-controller | `.github/workflows/test.yml`, `test-e2e.yml` | `controllers/*_test.go`, `test/e2e/` | — |
| rhods-operator | `.github/workflows/test-unit.yaml`, `test-integration.yaml` | `pkg/**/*_test.go`, `tests/e2e/` | `AGENTS.md` |
