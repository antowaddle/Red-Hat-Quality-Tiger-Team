# RHOAI Quality Assessment - All Components (rhoai-3.4)

## Executive Summary

- Overall Platform Score: **7/10**
- Components Analyzed: **45**
- Key Strengths: **Konflux/Tekton is the primary build and release path across RHOAI; several teams ship rich automated tests (notably `odh-dashboard` Jest + Cypress, `notebooks` pytest + Playwright + Trivy, `kuberay` extensive Go e2e); Red Hat–curated architecture docs consistently cite `Dockerfile.konflux`, FIPS-oriented Go builds, and supply-chain tasks (SBOM/OpenVex where present). Agent guidance is strongest in `odh-dashboard` (root `AGENTS.md` + `.claude/rules/`) and `notebooks` (`AGENTS.md`).**
- Critical Gaps: `**kueue` in this workspace has almost no GitHub Actions test automation (only `krew-release.yml`, `sbom.yaml`, `openvex.yaml`, `sync-dependabot.yaml`) despite a very large `*_test.go` tree—CI appears to live in Kubernetes project automation outside this clone; `odh-model-controller` e2e workflow is manual-only (`workflow_dispatch`); `codeflare-operator` has very few Go unit tests; several components rely on platform Konflux for SAST rather than repo-local CodeQL/Trivy in GitHub Actions.**
- Agent Rules Status: **Present and mature for `odh-dashboard` and `notebooks`; absent (`AGENTS.md` / `.claude/`) for `odh-model-controller`, `kuberay`, `kueue`, and `codeflare-operator` in the analyzed trees.**

## Quality Scorecard - Locally Analyzed Components

### odh-dashboard


| Dimension         | Score    | Status                                                                                                                                                                                                                                                                                                                         |
| ----------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Unit Tests        | 9/10     | **~604** `*.test.*` / `*.spec.*` files (monorepo); **Jest** via `@odh-dashboard/jest-config`, Turbo orchestration; broad package coverage (frontend, BFF-adjacent packages, plugins).                                                                                                                                          |
| Integration/E2E   | 9/10     | **Cypress** (shared `packages/cypress`, many package-level suites); `**.github/workflows/cypress-e2e-test.yml`** with cluster failover, tag/label-based selection, BFF coverage; additional workflows (`mlflow-bff-tests`, `maas-bff-tests`, `eval-hub-*`, `autorag`, `automl`, `gen-ai-*`, `modular-arch-quality-gates.yml`). |
| Build Integration | 9/10     | `**.github/workflows/test.yml**` (push/PR): lockfile validation, type-check, lint, test matrix, **Codecov upload**; Konflux: `**.tekton/`** PipelineRuns (`odh-dashboard-push.yaml`, modular-arch components) referencing `**odh-konflux-central**` `pipeline/multi-arch-container-build.yaml`.                                |
| Image Testing     | 8/10     | **24** `Dockerfile*` / `Containerfile*` at shallow depth; image build path exercised via Konflux; no Trivy/CodeQL strings in `.github/` (reliance on central pipeline).                                                                                                                                                        |
| Coverage Tracking | 8/10     | `**.codecov.yml`** (informational project/patch gates); `**codecov/codecov-action**` in `test.yml`.                                                                                                                                                                                                                            |
| CI/CD Automation  | 9/10     | **18** workflow YAMLs under `.github/workflows/` including Konflux simulator, kustomize validation, releases, stale bot, PR image expiry.                                                                                                                                                                                      |
| Agent Rules       | 10/10    | `**AGENTS.md`**, `**CLAUDE.md**`, `**.claude/rules/**` (architecture, BFF, Cypress, security, testing, etc.), `**.claude/skills/**`; package-level `**AGENTS.md**` under `packages/{eval-hub,maas,mlflow,autorag,automl}`.                                                                                                     |
| **Overall**       | **9/10** | **Strong end-to-end engineering quality** for an exec narrative: measurable test volume, explicit coverage gates, deep agent enablement.                                                                                                                                                                                       |


### odh-model-controller


| Dimension         | Score    | Status                                                                                                                                                                                              |
| ----------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Unit Tests        | 8/10     | **52** `*_test.go` files: controller, webhook, gateway, comparator coverage; `**make test`** in `**.github/workflows/test.yml**`.                                                                   |
| Integration/E2E   | 4/10     | `**test/e2e/**` and `**server/test/e2e/**` exist, but `**.github/workflows/test-e2e.yml**` has `**on: workflow_dispatch` only** (push/PR commented)—e2e not gated on every PR in this config.       |
| Build Integration | 8/10     | `**test.yml`** + `**lint.yml**` (golangci-lint-action v2.11.3); `**validate-manifests.yml**`, `**konflux-build-simulator.yml**`, version/metadata update workflows.                                 |
| Image Testing     | 8/10     | `**Containerfile**`, `**Containerfile.server**`, `**dev_tools/Containerfile.devspace**`; Konflux push pipeline includes `**sast-snyk-check**` task in `**.tekton/odh-model-controller-push.yaml**`. |
| Coverage Tracking | 4/10     | **No** `.codecov.yml` or Codecov usage found in-repo; coverage not surfaced in CI metadata reviewed.                                                                                                |
| CI/CD Automation  | 7/10     | Solid unit + lint automation; **e2e gap** as above; Konflux SAST (Snyk) on push path.                                                                                                               |
| Agent Rules       | 2/10     | **No** `AGENTS.md` or `**.claude/`** in this repository snapshot.                                                                                                                                   |
| **Overall**       | **6/10** | **Solid Go/unit/lint**; **regression risk** from **non-automated e2e** in GitHub Actions and **no published coverage discipline** in-repo.                                                          |


### notebooks


| Dimension         | Score    | Status                                                                                                                                                                                                                                            |
| ----------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Unit Tests        | 7/10     | **33** Python files under `tests/` (per `find`); `**pytest`** + `**pyproject.toml`/`pytest.ini**`; `**make test**` in `**.github/workflows/code-quality.yaml**`; scope skews toward **static/config/container** validation vs. classic unit-only. |
| Integration/E2E   | 8/10     | `**tests/containers/`** (testcontainers), `**tests/browser/**` (Playwright), `**build-browser-tests.yaml**`, `**test-playwright-action.yaml**`; integration-heavy.                                                                                |
| Build Integration | 9/10     | **31** workflows: `**build-notebooks-pr.yaml`**, `**build-notebooks-push.yaml**`, `**code-quality.yaml**`, `**notebooks-release.yaml**`, template-driven `**build-notebooks-TEMPLATE.yaml**`.                                                     |
| Image Testing     | 9/10     | **64+** Dockerfiles (multi-flavor Jupyter, runtimes, ROCm/CUDA bases); `**build-notebooks-TEMPLATE.yaml`** integrates **Trivy** (with CentOS Stream caveats documented).                                                                          |
| Coverage Tracking | 8/10     | `**.codecov.yml`** present; `**codecov/codecov-action**` + `**codecov/test-results-action**` in `**code-quality.yaml**` (`coverage.xml`, token-based).                                                                                            |
| CI/CD Automation  | 8/10     | `**security.yaml**`: Trivy filesystem scan + `**github/codeql-action/upload-sarif**`; `**sec-scan.yml**` for periodic report updates; `**test-trivy-scan-action.yaml**` validates custom action.                                                  |
| Agent Rules       | 8/10     | `**AGENTS.md**` (detailed: Makefile/KONFLUX, pytest layout, ruff/pyright). **No** `.claude/` directory.                                                                                                                                           |
| **Overall**       | **8/10** | **Image-centric quality is a standout** (Trivy, large Dockerfile matrix, pytest/Playwright); **AGENTS.md** supports consistent contributions.                                                                                                     |


### kuberay


| Dimension         | Score    | Status                                                                                                                                                                                                         |
| ----------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Unit Tests        | 8/10     | **~136** `*_test.go` files (ray-operator, kubectl-plugin, podpool); broad controller and utility tests.                                                                                                        |
| Integration/E2E   | 8/10     | Rich `**test/e2e*`** packages (RayJob, RayService, autoscaler, upgrade paths, etc.).                                                                                                                           |
| Build Integration | 8/10     | `**.github/workflows/test-job.yaml**`: **pre-commit**, multi-part Go build/test (apiserver, ray-operator, kubectl-plugin); additional `**consistency-check.yaml`**, `**helm.yaml**`, `**image-release.yaml**`. |
| Image Testing     | 7/10     | **14** Dockerfiles (operator, test helpers); build/test in CI, not a separate "image contract test" layer beyond integration tests.                                                                            |
| Coverage Tracking | 5/10     | **No** Codecov config in-repo; coverage not visible in CI files reviewed.                                                                                                                                      |
| CI/CD Automation  | 7/10     | Meaningful `**test-job.yaml`**; `**.pre-commit-config.yaml**` includes **gitleaks**, **shellcheck**, **golangci-lint** hooks.                                                                                  |
| Agent Rules       | 2/10     | **No** `AGENTS.md` or `.claude/` found.                                                                                                                                                                        |
| **Overall**       | **7/10** | **Strong Go test depth**; **secret scanning in pre-commit** is a plus; **no codecov** and **no agent rules**.                                                                                                  |


### kueue


| Dimension         | Score    | Status                                                                                                                                                                                                                                                                   |
| ----------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Unit Tests        | 9/10     | **~364** `*_test.go` files under `test/integration`, `test/performance`, `apis`, etc.—**very large** automated test corpus for scheduler/webhook/integration behavior.                                                                                                   |
| Integration/E2E   | 9/10     | Extensive **envtest/integration** style tests under `test/integration/singlecluster/`.                                                                                                                                                                                   |
| Build Integration | 8/10     | `**Makefile`** targets, `**cloudbuild.yaml**` (image-push to staging registry—Kubernetes-style release), `**.golangci.yaml**` + `**.golangci-kal.yaml**`.                                                                                                                |
| Image Testing     | 7/10     | **14** Dockerfiles under `hack/` and main tree; distroless-style operator packaging documented in `Makefile`.                                                                                                                                                            |
| Coverage Tracking | 5/10     | No project-root `**.codecov.yml`** (only vendored deps); no Codecov in `**.github/workflows**`.                                                                                                                                                                          |
| CI/CD Automation  | 3/10     | **Observed** workflows: `**krew-release.yml`**, `**sbom.yaml**`, `**openvex.yaml**`, `**sync-dependabot.yaml**` only—**no `go test` or integration-test workflow in this clone** (upstream Kubernetes projects typically use **Prow/test-infra**; not represented here). |
| Agent Rules       | 2/10     | **No** `AGENTS.md` or `.claude/`.                                                                                                                                                                                                                                        |
| **Overall**       | **6/10** | **Codebase test richness is elite; observable GitHub Actions automation in this workspace is thin**—score reflects **local CI reality**, not upstream Kubernetes test infrastructure.                                                                                    |


### codeflare-operator


| Dimension         | Score    | Status                                                                                                                                                          |
| ----------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Unit Tests        | 5/10     | Only **7** `*_test.go` files (`pkg/controllers/*_test.go`); `**make test-unit`** in `**.github/workflows/unit_tests.yml**` (pre-commit-go-toolchain container). |
| Integration/E2E   | 6/10     | `**test/e2e/**` (MNIST RayJob, AppWrapper scenarios); not all paths verified as PR-gated without reading `Makefile` targets in depth.                           |
| Build Integration | 7/10     | `**precommit.yml**`, `**unit_tests.yml**`, `**verify_generated_files.yml**`, `**operator-image.yml**`, `**tag-and-build.yml**`, `**odh-release.yml**`.          |
| Image Testing     | 7/10     | **1** top-level operator Dockerfile pattern; `**.tekton/odh-codeflare-operator-push.yaml`** includes `**sast-snyk-check**` (Konflux).                           |
| Coverage Tracking | 4/10     | No `**.codecov.yml**` found; coverage not surfaced in workflows reviewed.                                                                                       |
| CI/CD Automation  | 7/10     | `**.pre-commit-config.yaml**`: fmt, **golangci-lint**, go-mod-tidy, yamllint; containerized pre-commit in CI.                                                   |
| Agent Rules       | 2/10     | **No** `AGENTS.md` or `.claude/`.                                                                                                                               |
| **Overall**       | **6/10** | **Thin unit-test surface** relative to operator criticality; **Konflux Snyk** helps **supply-chain** posture.                                                   |


## Platform-Wide Analysis

### CI/CD Patterns

- **Konflux-centric builds**: Architecture docs (`PLATFORM.md`, per-component `*.md`) repeatedly reference `**Dockerfile.konflux`**, **Tekton PipelineRuns** (e.g. `.tekton/*-push.yaml`), and `**odh-konflux-central`**-style shared pipelines for `**odh-dashboard**`, `**odh-model-controller**`, `**codeflare-operator**`.
- **GitHub Actions diversity**: `**odh-dashboard`** and `**notebooks**` have the **broadest** GHA footprints (multi-workflow, BFF, browser, security). `**kuberay`** runs substantial `**test-job.yaml**`. `**kueue**` in this tree shows **supply-chain/artifact** workflows more than **test** workflows.
- **Downstream automation**: `**odh-model-controller` e2e** is **opt-in/manual** in the checked-in workflow file—a **process gap** for continuous regression detection.

### Testing Patterns

- **Frontend/monorepo**: Jest + Cypress + Turbo (`**odh-dashboard`**).
- **Python images**: pytest + testcontainers + Playwright (`**notebooks`**).
- **Go operators**: table-driven + envtest + kind/e2e (`**odh-model-controller`**, `**kuberay**`, `**kueue**`, `**codeflare-operator**`); `**kueue**` has the **largest** in-repo test tree observed.
- **Cross-stack**: Architecture doc for `**distributed-workloads`** describes a **Go e2e suite** validating Training Operator, Trainer, KubeRay, Kueue, JobSet on OpenShift—**platform-level integration testing** beyond any single repo.

### Security Posture

- **Trivy + SARIF**: `**notebooks`** (`security.yaml`, custom `**trivy-scan-action**`).
- **Snyk (Konflux)**: `**odh-model-controller`**, `**codeflare-operator**` `.tekton` push pipelines reference `**sast-snyk-check**`.
- **Secrets**: `**kuberay`** pre-commit **gitleaks**.
- **SBOM / OpenVex**: `**kueue`** workflows `**sbom.yaml**`, `**openvex.yaml**`.
- **Architecture baseline**: `**RHOAI-Build-Config.md`** and `**PLATFORM.md**` describe **FIPS-oriented Go**, **disconnected** installs, and **86** shipped images—**enterprise hardening** is a **design constraint**, not always visible as CodeQL in every GitHub repo.

### Agent Rules Adoption

- **High**: `**odh-dashboard`** (`AGENTS.md`, `.claude/rules`, skills); `**notebooks**` (`AGENTS.md`).
- **Low / none**: `**odh-model-controller`**, `**kuberay**`, `**kueue**`, `**codeflare-operator**` (no `AGENTS.md` or `.claude/` in these paths).

## Critical Gaps

1. `**kueue` GitHub Actions vs. test volume** — **Impact**: Misleading "green" repo if only GHA is considered; **Severity**: High for orgs auditing **GitHub-only** CI; **Effort**: Medium (document upstream Prow jobs or add mirror workflow).
2. `**odh-model-controller` e2e not on PR path** — **Impact**: Late discovery of integration regressions; **Severity**: High; **Effort**: Low (re-enable `push`/`pull_request` on `test-e2e.yml` or add nightly).
3. `**codeflare-operator` sparse unit tests** — **Impact**: Controller logic changes under-tested before e2e; **Severity**: Medium; **Effort**: Medium (expand table tests + envtest).
4. **Inconsistent coverage reporting (Go services)** — **Impact**: Hard to track debt; **Severity**: Medium; **Effort**: Medium (Codecov or cov upload in `make test`).
5. **Security scanning fragmented** (Trivy in one repo, Snyk in Konflux, no CodeQL in dashboard GHA) — **Impact**: Dashboard varies by audit lens; **Severity**: Medium; **Effort**: High (standardize at Konflux central pipeline level).

## Quick Wins

1. **Re-enable automated `odh-model-controller` e2e triggers** — **Effort**: Low; **Impact**: High.
2. **Add root `AGENTS.md` to Go operators** (start with `**odh-model-controller`**, `**codeflare-operator**`) — **Effort**: Low; **Impact**: Medium (AI/human onboarding).
3. `**kueue` README note** on **where CI runs** (Prow vs GHA) — **Effort**: Low; **Impact**: Medium (audit clarity).
4. **Unify Codecov for Go operators** using existing patterns from `**notebooks`**/`**odh-dashboard**` — **Effort**: Medium; **Impact**: Medium.

## Recommendations

### Priority 0 (Critical)

- **Make `odh-model-controller` e2e part of the default quality gate** (scheduled + PR, or nightly with Slack/alerting).
- **Document and verify `kueue` CI**: either add a `**go test`** workflow mirroring upstream minimum or explicitly map to **Kubernetes test-infra** jobs for auditors.

### Priority 1 (High Value)

- **Raise unit-test density** on `**codeflare-operator`** controller paths.
- **Standardize coverage** for Go components (`**odh-model-controller`**, `**kuberay**`, `**kueue**`, `**codeflare-operator**`).
- **Extend agent guidance** (`AGENTS.md`) to high-churn Go repos without copying full `.claude/` trees.

### Priority 2 (Nice-to-Have)

- **Optional CodeQL** on JavaScript monorepos if not fully redundant with Konflux SAST catalog.
- **Cross-link** architecture doc "quality" hints (e.g. `**vllm-orchestrator-gateway`** Tier 1 testing note) into component READMEs.

## Component Comparison Matrix


| Component                           | Unit | Int/E2E | Build | Image | Coverage | CI/CD | Agent Rules | Overall |
| ----------------------------------- | ---- | ------- | ----- | ----- | -------- | ----- | ----------- | ------- |
| MLServer                            | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| NeMo-Guardrails                     | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| argo-workflows                      | 7    | 7       | 8     | 8     | 6        | 7     | 3           | **7**   |
| batch-gateway                       | 6    | 5       | 8     | 8     | 5        | 7     | 3           | **6**   |
| data-science-pipelines              | 7    | 7       | 8     | 8     | 6        | 7     | 3           | **7**   |
| data-science-pipelines-operator     | 7    | 7       | 8     | 8     | 6        | 7     | 3           | **7**   |
| distributed-workloads               | 6    | 9       | 8     | 8     | 5        | 7     | 3           | **7**   |
| eval-hub                            | 7    | 7       | 8     | 8     | 6        | 7     | 5           | **7**   |
| feast                               | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| fms-guardrails-orchestrator         | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| guardrails-detectors                | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| guardrails-regex-detector           | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| kserve                              | 8    | 8       | 8     | 8     | 6        | 7     | 3           | **7**   |
| kube-auth-proxy                     | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| kubeflow                            | 6    | 6       | 7     | 7     | 5        | 6     | 3           | **6**   |
| kuberay                             | 8    | 8       | 8     | 7     | 5        | 7     | 2           | **7**   |
| llama-stack-distribution            | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| llama-stack-k8s-operator            | 7    | 7       | 8     | 8     | 5        | 7     | 3           | **7**   |
| llama-stack-provider-ragas          | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| llama-stack-provider-trustyai-garak | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| llm-d-inference-scheduler           | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| llm-d-kv-cache                      | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| lm-evaluation-harness               | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| ml-metadata                         | 6    | 6       | 7     | 7     | 5        | 6     | 3           | **6**   |
| mlflow                              | 7    | 6       | 8     | 8     | 6        | 7     | 3           | **7**   |
| mlflow-operator                     | 7    | 7       | 8     | 8     | 5        | 7     | 3           | **7**   |
| model-metadata-collection           | 5    | 5       | 7     | 7     | 4        | 7     | 3           | **6**   |
| model-registry                      | 7    | 7       | 8     | 8     | 6        | 7     | 3           | **7**   |
| model-registry-operator             | 7    | 7       | 8     | 8     | 5        | 7     | 3           | **7**   |
| models-as-a-service                 | 7    | 7       | 8     | 8     | 5        | 7     | 5           | **7**   |
| notebooks                           | 7    | 8       | 9     | 9     | 8        | 8     | 8           | **8**   |
| odh-dashboard                       | 9    | 9       | 9     | 8     | 8        | 9     | 10          | **9**   |
| odh-model-controller                | 8    | 4       | 8     | 8     | 4        | 7     | 2           | **6**   |
| openvino_model_server               | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| pipelines-components                | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| rhods-operator                      | 7    | 7       | 8     | 8     | 5        | 7     | 3           | **7**   |
| spark-operator                      | 7    | 7       | 8     | 8     | 5        | 7     | 3           | **7**   |
| trainer                             | 7    | 7       | 8     | 8     | 6        | 7     | 3           | **7**   |
| training-operator                   | 7    | 7       | 8     | 8     | 6        | 7     | 3           | **7**   |
| trustyai-explainability             | 7    | 6       | 8     | 8     | 5        | 6     | 3           | **6**   |
| trustyai-service-operator           | 7    | 7       | 8     | 8     | 5        | 7     | 3           | **7**   |
| vllm-cpu                            | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| vllm-gaudi                          | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| vllm-orchestrator-gateway           | 7    | 7       | 8     | 8     | 6        | 7     | 3           | **7**   |
| workload-variant-autoscaler         | 6    | 6       | 8     | 8     | 5        | 7     | 3           | **6**   |
| kueue                               | 9    | 9       | 8     | 7     | 5        | 3     | 2           | **6**   |
| codeflare-operator                  | 5    | 6       | 7     | 7     | 4        | 7     | 2           | **6**   |


*Non-local scores are **architecture-informed estimates** (Konflux-first builds, typical operator/runtime patterns in `architecture-context/architecture/rhoai-3.4/*.md`); **local repos** use **file-backed** metrics.*

## File Paths Reference

### odh-dashboard

- `odh-dashboard/.github/workflows/` — CI (e.g. `test.yml`, `cypress-e2e-test.yml`, `modular-arch-quality-gates.yml`, Konflux simulators).
- `odh-dashboard/.tekton/` — Konflux PipelineRuns (`odh-dashboard-push.yaml`, modular-arch pipelines).
- `odh-dashboard/.codecov.yml` — Codecov configuration.
- `odh-dashboard/AGENTS.md`, `odh-dashboard/.claude/rules/` — Agent rules.
- `odh-dashboard/.eslintrc.js`, package-level `.eslintrc.js` — ESLint.

### odh-model-controller

- `odh-model-controller/.github/workflows/test.yml`, `lint.yml`, `test-e2e.yml` — Tests and lint; e2e trigger configuration.
- `odh-model-controller/.tekton/odh-model-controller-push.yaml` — Konflux (includes `sast-snyk-check`).
- `odh-model-controller/.golangci.yml` — Go linting.
- `odh-model-controller/Containerfile`, `Containerfile.server` — Container builds.

### notebooks

- `notebooks/.github/workflows/code-quality.yaml`, `security.yaml`, `build-notebooks-*.yaml` — Tests, Trivy, builds.
- `notebooks/.github/actions/trivy-scan-action/action.yml` — Custom Trivy action.
- `notebooks/.codecov.yml`, `notebooks/pyproject.toml`, `notebooks/pytest.ini` — Coverage and pytest.
- `notebooks/.pre-commit-config.yaml` — ruff, pyright, uv lock.
- `notebooks/AGENTS.md` — Agent documentation.

### kuberay

- `kuberay/.github/workflows/test-job.yaml` — Primary build/test workflow.
- `kuberay/.pre-commit-config.yaml` — gitleaks, shellcheck, golangci-lint.
- `kuberay/.golangci.yml` — Go linting.
- `kuberay/ray-operator/test/` — Large e2e/unit test tree.

### kueue

- `kueue/.github/workflows/krew-release.yml`, `sbom.yaml`, `openvex.yaml`, `sync-dependabot.yaml` — Observed automation scope.
- `kueue/cloudbuild.yaml` — Staging image push (Kubernetes-style).
- `kueue/Makefile` — Build/test entrypoints.
- `kueue/.golangci.yaml`, `kueue/.golangci-kal.yaml` — Lint configs.
- `kueue/test/integration/` — Extensive integration tests.

### codeflare-operator

- `codeflare-operator/.github/workflows/unit_tests.yml`, `precommit.yml` — Unit tests and pre-commit.
- `codeflare-operator/.pre-commit-config.yaml` — golangci-lint via pre-commit-go.
- `codeflare-operator/.golangci.yaml` — Go linting.
- `codeflare-operator/.tekton/odh-codeflare-operator-push.yaml` — Konflux Snyk task reference.

### Architecture corpus (all 45 components)

- `architecture-context/architecture/rhoai-3.4/PLATFORM.md` — Platform-wide inventory and Konflux/FIPS context.
- `architecture-context/architecture/rhoai-3.4/<component>.md` — Per-component repository URLs, `Dockerfile.konflux` references, build notes, and change history (quality-relevant signals).
- `architecture-context/architecture/rhoai-3.4/RHOAI-Build-Config.md` — Build configuration narrative for the release.

