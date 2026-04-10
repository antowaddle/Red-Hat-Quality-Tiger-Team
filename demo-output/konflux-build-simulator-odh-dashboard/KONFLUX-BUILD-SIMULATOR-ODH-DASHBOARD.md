# Konflux Build Simulator Analysis: odh-dashboard

## Repository Profile

- **Type:** Monorepo (npm workspaces + Turbo task orchestration; not a Kubernetes operator repository).
- **Primary deliverable:** Container image for the main dashboard (`Dockerfile` at repo root) plus **separate Konflux pipelines** for Modular Architecture UI/BFF components (e.g. `packages/gen-ai/Dockerfile.workspace`).
- **Language:** TypeScript/JavaScript (frontend, backend), Go (BFFs under select `packages/*/bff/`), YAML (manifests, Tekton).
- **Framework:** React 18, Fastify backend, Webpack with `@module-federation/enhanced`.
- **Build system:** `npm` (package manager `npm@10.9.2`, Node `>=22`), `turbo` for parallel tasks, `npm-run-all` for root scripts; root `npm run build` runs `build:backend` (app-config + backend) and `build:frontend` in parallel.
- **Base image (main Dockerfile):** `registry.access.redhat.com/ubi9/nodejs-22:latest` (overridable via `BASE_IMAGE`).

## Dockerfile Analysis

**Primary file:** `Dockerfile` (multi-stage; main production image for Konflux `odh-dashboard-*` pipelines).

### Build Stages

| Stage | Purpose |
|--------|---------|
| `builder` (`FROM ${BASE_IMAGE} as builder`) | Install dependencies, run full `npm run build`, prune to production `node_modules`, strip esbuild binaries for FIPS posture. |
| `runtime` (`FROM ${BASE_IMAGE} as runtime`) | Minimal runtime filesystem: static frontend assets, compiled backend, production `node_modules`, config/data. `WORKDIR` ends at `/usr/src/app/backend`; `CMD` starts the Node server. |

### Build Arguments

| Argument | Default | Role |
|----------|---------|------|
| `SOURCE_CODE` | `.` | Context copied into `/usr/src/app`. |
| `BUILD_MODE` | `ODH` | Selects branding/env script before `npm run build`. Konflux sets **`BUILD_MODE=RHOAI`** in `.tekton/odh-dashboard-*.yaml`. |
| `BASE_IMAGE` | `registry.access.redhat.com/ubi9/nodejs-22:latest` | Builder and runtime base. |

### Critical COPY Commands

- **Builder:** `COPY --chown=default:root ${SOURCE_CODE} /usr/src/app` — entire repo context (Konflux `path-context: .`).
- **Runtime (from builder):** Static UI `frontend/public`; `backend` `package.json`, `node_modules`, `dist`; `packages/app-config` `package.json` and `dist`; root `package.json`, `package-lock.json`, root `node_modules`, `.npmrc`, `.env`, `data/`.
- **Not copied:** Full `packages/*` source trees (only `app-config` dist), so **federated remote packages are not present as source in the runtime image**—they are consumed at runtime via Kubernetes proxies (see Module Federation section).

### CMD / ENTRYPOINT

- **`WORKDIR`:** `/usr/src/app/backend` (final `WORKDIR` before `CMD`).
- **`CMD`:** `["npm", "run", "start"]` — production backend process; serves `frontend/public` and API routes.

### Potential Failure Points

1. **`npm ci --ignore-scripts`** then **`npm run build`:** Any workspace resolution, TypeScript, or Webpack failure fails the image build (large surface: entire monorepo build).
2. **`BUILD_MODE` branching:** RHOAI path writes `/tmp/env.sh` with product branding vars; ODH path writes an empty env script—mis-set `BUILD_MODE` changes assets but both should build if sources are consistent.
3. **`prepare-production-manifest.js` + `npm install --omit=dev`:** Custom production manifest logic; failure here breaks the slim runtime `node_modules`.
4. **FIPS-related `rm -rf` of esbuild:** If paths change, could mask or surface install layout issues.
5. **Runtime assumptions:** Backend expects compiled assets at `path.join(__dirname, '../../frontend/public')` relative to `backend/dist` — mismatch between build output dir and copy paths would yield broken UI.
6. **`.env` copied into image:** Build-time/env coupling; ensure secrets are not embedded inappropriately for a given environment (review contents for pipeline demos).

## Existing CI/CD Analysis

### Current Workflows (representative)

| Workflow | Role |
|----------|------|
| `.github/workflows/test.yml` | Main CI: lockfile check, `npm install`, `validate:ports`, `type-check`, `lint`, unit coverage, contract tests (Go 1.25), Cypress mock matrix, coverage merge, Codecov. |
| `.github/workflows/validate-kustomize.yml` | `kustomize build` for **`manifests/rhoai/addon`**, **`manifests/rhoai/onprem`**, **`manifests/odh`** (kustomize v5.4.1). |
| `.github/workflows/modular-arch-quality-gates.yml` | On PR open under `packages/**`: module detection, per-module testing maturity reporting (informational). |
| `.github/workflows/konflux-build-simulator.yml` | **Konflux-oriented PR simulation:** `docker build` with `BUILD_MODE=RHOAI`, container smoke test on port 8080, kustomize loop over all `manifests/**/kustomization.yaml`, summary job. |
| `.github/workflows/release-odh-dashboard.yml` | Manual release tagging against Quay images (podman), not a PR builder. |
| Package-scoped workflows | e.g. `gen-ai-bff-build.yml`, `eval-hub-frontend-tests.yml`, `cypress-e2e-test.yml`, etc. |

### Existing Build Validation

- **No `docker build` in the main `test.yml`** — validation is npm-centric (lint, test, type-check, Cypress).
- **`konflux-build-simulator.yml`** is the explicit **Docker + manifest** rehearsal aligned with Konflux parameters.
- **Kustomize:** Official validation is **three curated roots**; the simulator **iterates every** `kustomization.yaml` under `manifests/` (stricter / different scope).

### Gaps in Current CI

1. **Main CI does not build the production `Dockerfile`** — regressions that only appear in `npm ci` + full build + prune path can slip until Konflux or the simulator runs.
2. **Modular Architecture images:** Separate Dockerfiles under `packages/*` (e.g. `Dockerfile.workspace`) are built by **other** Konflux `PipelineRun` files; a PR that only touches those may need path filters beyond the root `Dockerfile` (partially addressed by per-module `.tekton` CEL expressions).
3. **`konflux-build-simulator.yml` Module Federation step:** It inspects paths under **`/opt/app-root/src/packages/...`**, while the **root `Dockerfile` uses `/usr/src/app`** and **does not ship** full `packages/<module>/frontend/dist` for remotes. **As written, that step does not match the actual layout or architecture** of the main image (see Module Federation Analysis). Root-cause risk: false failures or false confidence depending on behavior.
4. **`/api/health` is not a reliable standalone smoke check:** `backend/src/routes/api/health/healthUtils.ts` requires a **Kube context**; without a cluster this route can **503**. The simulator correctly uses **`GET /`** (SPA) for basic responsiveness.
5. **Manifest validation duplication/inconsistency:** Curated three-way `validate-kustomize.yml` vs. "build every kustomization" in the simulator — teams should agree on which is authoritative for PRs.

## Konflux/Tekton Pipeline Analysis

### Current Konflux Configuration

**Location:** `.tekton/`

**Main dashboard (this report's primary Konflux target):**

- `odh-dashboard-pull-request.yaml` — PRs to `main`; image `quay.io/opendatahub/odh-dashboard:odh-pr` + tag `odh-pr-{{revision}}`; **`build-args`: `BUILD_MODE=RHOAI`**; `dockerfile: Dockerfile`, `path-context: .`.
- `odh-dashboard-push.yaml` — push to `main`; image `quay.io/opendatahub/odh-dashboard:odh-stable`; same build args and Dockerfile.

**Pipeline reference:** Both resolve `https://github.com/opendatahub-io/odh-konflux-central.git` @ `main`, path `pipeline/multi-arch-container-build.yaml` (shared multi-arch container pipeline).

**Modular Architecture / component pipelines (same repo, different Dockerfile/path-context), examples:**

- `odh-mod-arch-gen-ai-*.yaml` — `packages/gen-ai/Dockerfile.workspace`, CEL on `packages/gen-ai/**`, etc.
- Similar patterns for `mlflow`, `eval-hub`, `maas`, `automl`, `autorag`, `modular-architecture`.

**Service account:** `build-pipeline-odh-dashboard` (main) vs e.g. `build-pipeline-genai-poc` for some components — tenant-specific.

### Build Parameters (main `odh-dashboard` PipelineRun)

| Parameter | Value |
|-----------|--------|
| `dockerfile` | `Dockerfile` |
| `path-context` | `.` |
| `build-args` | `BUILD_MODE=RHOAI` |
| `output-image` | Quay coordinates per event (PR vs push) |

## Module Federation Analysis

### Detected Modules

**Configuration pattern:** Workspace `package.json` entries with a `"module-federation"` key; aggregated by `frontend/config/moduleFederation.js` via `npm query .workspace`.

**Representative files present in repo:**

- `frontend/config/moduleFederation.js` (host: `ModuleFederationPlugin`, `filename: 'remoteEntry.js'`, remotes in dev / type-update flows).
- Per-package configs including: `packages/gen-ai`, `packages/model-registry`, `packages/mlflow`, `packages/maas`, `packages/eval-hub`, `packages/automl`, `packages/autorag`, `packages/notebooks/upstream/workspaces/frontend`, etc.

### Federation Configuration

- **Host** webpack config exposes/consumes remotes per environment; production remotes are not defined the same way as dev (`remotes` conditional on `MF_UPDATE_TYPES` / dev tooling in `moduleFederation.js`).
- **Backend integration:** `backend/src/routes/module-federation.ts` registers proxies under `/_mf/<name>` to Kubernetes services; a catch-all `/_mf/*` returns **404** when unhandled — **standalone containers do not serve remote bundles locally**; they proxy to cluster services when configured via app-config / ConfigMaps.
- **Port uniqueness:** `scripts/validate-module-ports.js` validates dev ports and production ports from `manifests/modular-architecture/federation-configmap.yaml` and `manifests/rhoai/shared/base/federation-configmap.yaml` — CI runs `npm run validate:ports` in `test.yml` Setup.

### Validation Requirements

| Layer | What to validate | Notes |
|-------|------------------|-------|
| **CI (current)** | `npm run validate:ports` | Catches port collisions before merge. |
| **Webpack / build** | Host `frontend/public` output | Host `remoteEntry.js` is emitted to the frontend dist dir (`ModuleFederationPlugin` `filename: 'remoteEntry.js'`). In the **runtime image**, path is **`/usr/src/app/frontend/public/remoteEntry.js`** (not under `/opt/app-root/...`). |
| **Remote modules** | Separate images / Konflux pipelines | Remotes for modular features are built and deployed as **separate containers** (see `manifests/modular-architecture/` image params); validating them belongs to **component** `PipelineRun` definitions, not only the root `Dockerfile`. |
| **Runtime (cluster)** | `/_mf/*` proxies | Smoke tests outside a cluster cannot fully validate federated loading; use integration/E2E against a real OpenShift deployment. |

## Manifest Analysis

### Kustomize Structure (high level)

- **`manifests/odh/`** — ODH dashboard assembly: pulls `../common`, `../modular-architecture`, `../core-bases/consolelink`, `./apps`; ConfigMap-driven image and params (`params.env`).
- **`manifests/modular-architecture/`** — Federation ConfigMap, network policy, patches to `Deployment`/`Service` for modular workloads; references **per-feature UI images** (gen-ai, model-registry, maas, mlflow, eval-hub, automl, autorag, etc.).
- **`manifests/rhoai/`** — RHOAI-specific overlays: `addon`, `onprem`, `shared` (including app-specific trees under `shared/apps/`).
- **`manifests/common/`** — Shared bases: CRDs (`odhdashboardconfigs`, `odhapplications`, `odhdocuments`, `odhquickstarts`, etc.), connection types, Jupyter/MLflow app bundles.
- **`manifests/core-bases/base/`** — Core RBAC, Deployment, Service, HTTPRoute, kube-rbac-proxy config, etc.
- **`manifests/overlays/dev/`** — Dev overlay.
- **Upstream-embedded manifests** under some `packages/notebooks/upstream/...` trees (not in the three canonical CI kustomize roots).

### Overlay Configuration

- **RHOAI vs ODH:** Distinct trees under `manifests/rhoai` vs `manifests/odh` with different operator/add-on assumptions.
- **Params:** `params.env` + `params.yaml` kustomize configurations for image references and substitutions.

### Validation Requirements

1. **Minimum PR gate (aligned with existing `validate-kustomize.yml`):** `kustomize build` on `manifests/rhoai/addon`, `manifests/rhoai/onprem`, `manifests/odh`.
2. **Extended / Konflux simulator:** Full-tree `kustomize build` per directory containing `kustomization.yaml` — catches local overlay mistakes but may include directories not meant as standalone roots (document policy).
3. **CRDs:** Validate presence and compatibility when changing dashboard APIs (`manifests/common/crd/`).
4. **Federation ConfigMap JSON:** Must stay consistent with `scripts/validate-module-ports.js` expectations when service ports change.

## Generated PR Build Validation Workflow

Below is a **single consolidated GitHub Actions workflow** suitable for executive demo and engineering use. It mirrors Konflux (`BUILD_MODE=RHOAI`), fixes **image paths** for artifact checks, avoids **`/api/health`** for standalone smoke tests, and aligns kustomize validation with the **three official roots** (optional full scan as a separate job).

```yaml
name: Konflux Build Simulator (odh-dashboard)

on:
  pull_request:
    branches: [main, v*, release-*, f/*]
    paths:
      - 'Dockerfile'
      - 'frontend/**'
      - 'backend/**'
      - 'packages/**'
      - 'manifests/**'
      - '.github/workflows/konflux-build-simulator-odh-dashboard.yml'

env:
  BUILD_MODE: RHOAI
  IMAGE_NAME: odh-dashboard:pr-${{ github.event.pull_request.number }}
  NODE_VERSION: '22'

jobs:
  docker-build-smoke:
    name: Docker build + runtime smoke (Konflux-aligned)
    runs-on: ubuntu-latest
    timeout-minutes: 45
    steps:
      - uses: actions/checkout@v4

      - uses: docker/setup-buildx-action@v3

      - name: Docker build (same args as Konflux main pipeline)
        run: |
          docker build \
            --build-arg BUILD_MODE=${{ env.BUILD_MODE }} \
            --tag "${{ env.IMAGE_NAME }}" \
            -f Dockerfile \
            --progress=plain \
            .

      - name: Inspect host Module Federation artifact (main image)
        run: |
          docker run --rm "${{ env.IMAGE_NAME }}" \
            test -f /usr/src/app/frontend/public/remoteEntry.js
          echo "Host remoteEntry.js present"

      - name: Run container (smoke)
        run: |
          docker run -d --name odh-smoke -p 8080:8080 \
            -e NODE_ENV=production \
            "${{ env.IMAGE_NAME }}"
          for i in $(seq 1 30); do
            docker ps --filter name=odh-smoke --filter status=running | grep -q odh-smoke && break
            sleep 2
          done
          docker ps --filter name=odh-smoke --filter status=running | grep -q odh-smoke

      - name: HTTP smoke (root SPA — not /api/health)
        run: |
          curl -fsS -o /dev/null --retry 5 --retry-delay 2 http://localhost:8080/

      - name: Cleanup
        if: always()
        run: docker rm -f odh-smoke 2>/dev/null || true

  kustomize-official:
    name: Kustomize (canonical roots)
    runs-on: ubuntu-latest
    env:
      KUSTOMIZE_VERSION: v5.4.1
    strategy:
      fail-fast: false
      matrix:
        include:
          - name: RHOAI Add-on
            path: manifests/rhoai/addon
          - name: RHOAI On-Prem
            path: manifests/rhoai/onprem
          - name: ODH
            path: manifests/odh
    steps:
      - uses: actions/checkout@v4
      - name: Install kustomize
        run: |
          curl -fsSL -o /tmp/kustomize.tar.gz \
            "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize/${KUSTOMIZE_VERSION}/kustomize_${KUSTOMIZE_VERSION}_linux_amd64.tar.gz"
          sudo tar -xzf /tmp/kustomize.tar.gz -C /usr/local/bin kustomize
      - run: kustomize build "${{ matrix.path }}" > /dev/null

  summary:
    name: Summary
    runs-on: ubuntu-latest
    needs: [docker-build-smoke, kustomize-official]
    if: always()
    steps:
      - run: |
          echo "docker-build-smoke: ${{ needs.docker-build-smoke.result }}"
          echo "kustomize-official: ${{ needs.kustomize-official.result }}"
          test "${{ needs.docker-build-smoke.result }}" = "success" \
            && test "${{ needs.kustomize-official.result }}" = "success"
```

## Generated Validation Script

Bash script suitable for local or CI use: **Konflux-aligned Docker build**, **host `remoteEntry.js` check**, **curl smoke**, **official kustomize roots**.

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BUILD_MODE="${BUILD_MODE:-RHOAI}"
IMAGE_TAG="${IMAGE_TAG:-odh-dashboard:local-konflux-sim}"
DOCKERFILE="${DOCKERFILE:-Dockerfile}"
KUSTOMIZE_VERSION="${KUSTOMIZE_VERSION:-v5.4.1}"

echo "==> Docker build (BUILD_MODE=${BUILD_MODE})"
docker build \
  --build-arg "BUILD_MODE=${BUILD_MODE}" \
  -t "${IMAGE_TAG}" \
  -f "${DOCKERFILE}" \
  --progress=plain \
  .

echo "==> Verify host Module Federation output in image"
docker run --rm "${IMAGE_TAG}" test -f /usr/src/app/frontend/public/remoteEntry.js

echo "==> Runtime smoke (container)"
docker rm -f odh-konflux-smoke 2>/dev/null || true
docker run -d --name odh-konflux-smoke -p 8080:8080 -e NODE_ENV=production "${IMAGE_TAG}"
cleanup() { docker rm -f odh-konflux-smoke 2>/dev/null || true; }
trap cleanup EXIT

for _ in $(seq 1 30); do
  docker ps --filter name=odh-konflux-smoke --filter status=running | grep -q odh-konflux-smoke && break
  sleep 2
done
docker ps --filter name=odh-konflux-smoke --filter status=running | grep -q odh-konflux-smoke

echo "==> HTTP GET / (SPA)"
curl -fsS -o /dev/null --retry 5 --retry-delay 2 "http://localhost:8080/"

echo "==> Kustomize build (canonical roots)"
if ! command -v kustomize >/dev/null 2>&1; then
  echo "Installing kustomize ${KUSTOMIZE_VERSION} to /tmp/kustomize"
  curl -fsSL -o /tmp/kustomize.tar.gz \
    "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize/${KUSTOMIZE_VERSION}/kustomize_${KUSTOMIZE_VERSION}_linux_amd64.tar.gz"
  tar -xzf /tmp/kustomize.tar.gz -C /tmp
  export PATH="/tmp:${PATH}"
fi

for p in manifests/rhoai/addon manifests/rhoai/onprem manifests/odh; do
  echo "  - kustomize build $p"
  kustomize build "$p" > /dev/null
done

echo "==> All checks passed"
```

## Risk Assessment

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Root `Dockerfile` build fails on `npm run build` while CI passes lint/tests | High | Medium | Run Konflux simulator (`docker build` + kustomize) on PRs touching build paths; cache npm in pipeline. |
| **MF validation script uses wrong filesystem paths** (`/opt/app-root/...` vs `/usr/src/app`, expects package `dist` in main image) | High | High (if using current simulator step as-is) | Validate **`/usr/src/app/frontend/public/remoteEntry.js`** for host; validate remotes via **component** images / their Tekton pipelines. |
| **`/api/health` fails outside cluster** (no kube context) | Medium | High | Smoke test **`GET /`**, not health API, for standalone Docker. |
| Kustomize: full-tree `find` vs three canonical roots | Medium | Medium | Document authoritative set; align `validate-kustomize.yml` and simulator. |
| **FIPS / esbuild** removal assumes known paths | Low | Low | Keep Dockerfile comments in sync with dependency graph when upgrading MF toolchain. |
| Modular Architecture drift (ConfigMap ports vs packages) | Medium | Medium | Keep `npm run validate:ports` in required checks; review `federation-configmap.yaml` on MF changes. |

## Implementation Roadmap

### Phase 1: Basic Docker Build (Week 1)

- Enforce **`docker build` with `BUILD_MODE=RHOAI`** on PRs touching `Dockerfile`, root lockfile, or `frontend`/`backend`/`packages` as appropriate.
- Add **host** `remoteEntry.js` presence check at **`/usr/src/app/frontend/public/remoteEntry.js`**.
- Align Tekton parameter documentation (`build-args`, `path-context`) with onboarding docs for teams.

### Phase 2: Runtime Validation (Week 2)

- Container smoke: **`GET /`** on port **8080**; optional log scrape for fatal startup errors.
- Document that **full MF runtime** validation requires cluster networking and sidecars.
- Optional: add targeted checks for **component** images when `packages/<module>` changes (matrix of Dockerfiles used in `.tekton`).

### Phase 3: Full Integration (Week 3-4)

- End-to-end validation on OpenShift (Routes, `/_mf/*` proxies, ConfigMaps).
- Tie **Konflux Application/Component** health in Konflux UI to pipeline success rates.
- Expand contract tests / Cypress where they cover deployment-critical paths (already partially in `test.yml`).

## Success Metrics

| Metric | Before | After |
|--------|--------|-------|
| **PR feedback on Konflux-only failures** (Docker build vs unit tests) | Failure discovered late on Konflux | **Early** `docker build` signal on PR |
| **False negatives/positives on MF checks** | Risk of misleading checks if paths wrong | **Deterministic** host artifact check + documented remote scope |
| **Manifest regression detection** | RHOAI/ODH roots validated | Same roots **always** built; optional extended matrix documented |
| **Mean time to detect broken static/prod prune path** | Variable | Reduced by **prepare-production-manifest** + full image build in CI |
| **Exec demo clarity** | Ad hoc | Single story: **same build-args as `.tekton/odh-dashboard-*.yaml`**, smoke **GET /**, kustomize **canonical** trees |
