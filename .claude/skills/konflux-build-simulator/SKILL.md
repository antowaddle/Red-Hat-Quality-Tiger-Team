---
name: konflux-build-simulator
description: Simulates Konflux build environment on PRs to catch build failures before they reach production
---

# Konflux Build Simulator Skill

Simulates Konflux build environment on PRs to catch build failures before they reach production.

## Usage

```bash
/konflux-build-simulator [repository-url]
```

## Examples

```bash
/konflux-build-simulator https://github.com/opendatahub-io/odh-dashboard
/konflux-build-simulator https://github.com/opendatahub-io/kserve
/konflux-build-simulator https://github.com/kubeflow/training-operator
```

## What It Does

This skill analyzes a repository and generates GitHub Actions workflows to validate builds at PR time, catching failures that would otherwise only be discovered in Konflux or production.

### Generated Artifacts

1. **`.github/workflows/pr-build-validation.yml`** - Main build validation workflow
2. **`scripts/validate-build.sh`** - Reusable validation scripts
3. **`manifests/pr-testing/`** - Test-specific manifests (if operator)
4. **Documentation** - Setup guide and troubleshooting

### What Gets Validated

#### Phase 0: Early Static Checks
- ✅ **Hermetic lockfile validation** - Validates package-lock.json for Hermeto/Cachi2 compatibility
  - Detects unsupported dependency protocols (git+, github:, file:)
  - Ensures all dependencies have resolved URLs
  - Verifies go.sum exists for all go.mod files
  - Runs go mod verify if Go is available
- ✅ **Workspace dependency validation** - Ensures Dockerfiles COPY all referenced packages
  - Dynamically detects workspace scope from package.json
  - Cross-references workspace imports with COPY commands in Dockerfiles
  - Prevents "package not found" build failures
  - Works with any workspace monorepo structure
- ✅ **FIPS compliance validation** - Checks FIPS requirements for RHOAI builds
  - Verifies esbuild removal from node_modules
  - Ensures Go binaries use -tags strictfipsruntime
  - Warns about FIPS violations that block product release
- ✅ **Hermetic build preflight** - Proves the build survives with no network
  - Node: populate a pnpm store, then install from it
  - Go: populate an isolated module cache, then compile with `GOPROXY=off`
  - Python: build a local wheelhouse, then resolve with `pip --no-index`
  - Catches missing prefetch inputs in minutes instead of in Konflux

#### Phase 1: Docker Build Validation
- ✅ Builds Docker image with production build mode (RHOAI, etc.)
- ✅ Tests multi-stage build (builder + runtime)
- ✅ Validates COPY commands and file paths
- ✅ Catches BUILD_MODE environment differences

#### Phase 2: Runtime Validation
- ✅ Starts container
- ✅ Scans logs for crashloop indicators (fastify errors, uncaught exceptions)
- ✅ Detects delayed crashes after initialization
- ✅ Tests non-root user runtime (catches permission issues)
- ✅ Waits for health check
- ✅ Validates endpoints
- ✅ **Tests critical API endpoints** - Catches fastify v5 regressions
  - Tests PATCH with `application/merge-patch+json` (415 error in Fastify 5)
  - Tests PATCH with `application/json-patch+json` (breaks 28+ operations)
  - Prevents PR #6727 style regressions
- ✅ **Tests WebSocket compatibility** - Catches connection crashes
  - Validates WebSocket endpoints don't crash the pod
  - Catches @fastify/websocket v11 regression (SocketStream removal)
  - Prevents non-admin user crashes (exit 1/OOMKill 137)
- ✅ Monitors container stability

#### Phase 3: Module Federation Validation (if applicable)
- ✅ Validates remoteEntry.js build output in dist/
- ✅ **Checks remoteEntry.js file size** - Catches empty/corrupted manifests
- ✅ **Checks for missing webpack chunks** - Catches ChunkLoadError issues
  - Verifies all .bundle.js files are present
  - Prevents "chunk 8419 failed" runtime errors (RHOAIENG-59862)
  - Detects suspiciously large chunks (>1MB) that slow page load
  - Reports total dist size per module
- ✅ **Tests Module Federation load performance**
  - Measures endpoint response times
  - Flags slow endpoints (>2s) that cause Cypress timeouts
  - Catches issues that cause "dashboard takes too long to load" (RHOAIENG-59861)
- ✅ Checks webpack generated federation artifacts
- ✅ Verifies module-federation config in package.json
- ⚠️  Does NOT test runtime proxy endpoints (/_mf/* routes proxy to K8s services)

#### Phase 4: Operator Integration (if applicable)
- ✅ Creates Kind cluster
- ✅ Loads image to cluster
- ✅ Applies CRDs and manifests
- ✅ Validates deployment
- ✅ Tests operator functionality
- ✅ **Operator reconcile smoke test** (controller-runtime operators)
  - Runs the operator from checked-in sim manifests (not workflow heredocs)
  - Creates a CR and asserts reconcile evidence: finalizer set, `status.observedGeneration` advanced, 0 operator restarts
  - Dumps describe/logs/`--previous`/events **inline** on rollout failure (not a later `if: failure()` step)
  - Preserves the "test the PR image" invariant by pinning the operator's image-resolution env to the loaded PR tag (SSA reverts workload image patches)
  - Adds a free-disk-space step for jobs that load multiple images
- ✅ **External operator variant** (this repo builds an image that an operator in
  *another* repo ships)
  - Applies `<operator-repo>/config/default?ref=<pinned-sha>`, never a moving branch
  - Sets the operator's `RELATED_IMAGE_*` variable, not the workload Deployment
    spec: operators re-render the workload from that variable, so patching the
    Deployment looks correct and silently reverts
  - Asserts the rendered workload's `spec.template.spec.containers[].image`
    equals the PR tag — the only proof the PR image is under test
  - Greps the operator source for the constant it actually reads instead of
    guessing the variable name

#### Phase 4b: Platform Operator Handoff (always emit, never implement here)

Some components are shipped by a platform operator (`DataScienceCluster` /
RHOAI) rather than by their own controller or an external module operator. That
layer cannot be simulated in the component repo: it needs the operator's CRDs,
DSC reconcile loop, RBAC, and platform bootstrap.

The skill still has to be useful there. Detect it and emit a follow-up instead
of silently stopping:

- ✅ **Detects** whether a platform operator ships this component, using the
  same evidence as the external-operator check
- ✅ **Checks whether the coverage already exists** before proposing new tests:
  is there an E2E suite for the component, and is it in the operator's Kind
  target? A registered-but-filtered suite is a two-line fix, not a new suite
- ✅ **Emits a ready-to-file follow-up** in the PR description with exact file
  paths and the one-line diff
- ❌ Does not add platform-operator tests to this repo, and does not claim
  `DataScienceCluster` coverage in the simulator

The common outcome is that the assertions already exist upstream and only the
Kind component filter excludes them. Emit the diff; do not reimplement them.

#### Phase 5: Manifest Validation (if applicable)
- ✅ Kustomize build validation
- ✅ ConfigMap generation
- ✅ Overlay testing
- ✅ Resource validation
- ✅ **Operator-derived overlay coverage** - validates every overlay the operator renders at runtime, with dynamic module discovery (not just `find`-able kustomizations)
- ✅ **kubeconform typo guard** - fails when a Kubernetes built-in kind is skipped for a missing schema (catches `Deploymnet`-style typos that `-ignore-missing-schemas` silently passes)

#### Not Covered (state this explicitly)
- ❌ Platform-operator reconciliation (`DataScienceCluster`): component
  conditions, Managed vs Unmanaged state, and operator-rendered manifest paths
  (e.g. model-registry RHOAIENG-103141, RHOAIENG-103140, RHOAIENG-99568).
  Phase 4 covers the component's own operator, or an external one it names
  explicitly; the RHOAI platform operator needs that operator repo's E2E suite,
  not this one.
- ❌ Cluster RBAC/SCC, networking, storage, and upgrade paths
- ❌ Broken wheels only if the image is actually run and modules imported —
  always add import/healthcheck smoke tests for Python and Go entrypoints

## Key Features

- **Hermetic Build Validation**: Validates lockfiles for downstream RHOAI hermetic builds
  - Catches Hermeto/Cachi2 incompatibilities early (git+, github:, file: protocols)
  - Verifies Go module checksums
  - Tests hermetic npm install with --network=none
  - Runs in <1 minute before Docker build
- **Workspace Dependency Validation**: Prevents missing COPY failures in monorepos
  - Dynamically detects workspace scope and directories
  - Cross-references package imports with Dockerfile COPY commands
  - Detects missing workspace packages before build
  - Works with any monorepo structure (not hardcoded)
- **FIPS Compliance Validation**: Checks FIPS requirements for RHOAI
  - Validates esbuild removal
  - Verifies strictfipsruntime build tags for Go binaries
  - Warns about violations that block product release
- **Konflux-Like Environment**: Simulates production build environment
- **Workflow Scaffolding**: One skip gate for all jobs, per-job least-privilege
  permissions, `persist-credentials: false`, and a summary job that is safe as
  the only required status check
- **Fast Feedback**: Runs in 10-20 minutes on PRs
- **Comprehensive**: Catches most common build failures before merge
- **Automated**: No manual intervention needed
- **Documented**: Clear failure messages and logs
- **Skippable**: Add `[skip konflux-sim]` to PR title to skip

## Artifact Consumption Detection

Repo layout is a poor proxy for what needs validating. The question is not
"does this repo contain a controller?" but "what consumes the artifacts this
repo builds?". A service repo can be shipped entirely by an operator that lives
somewhere else; treating "no controller here" as "skip Phase 4" leaves the
whole shipping path untested.

Ask in this order:

1. **Does this repo own the operator?** (`dashboard-operator/`, `controllers/`,
   `config/crd/`) → Phase 4 as written.
2. **Does another repo's operator ship these images?** Look for a component
   entry in an operator's `manifests-config.yaml`, a `RELATED_IMAGE_*` variable
   naming the image, or a deploy script that creates a CR. → Phase 4 against
   that external operator, at a pinned commit.
3. **Does only the platform operator ship it?** (`DataScienceCluster`,
   RHOAI-managed components) → run Phase 4b: emit the handoff, do not claim
   coverage.

### Monorepo (e.g., odh-dashboard)
- Docker build validation
- Module Federation testing
- Cross-component build validation
- Operator integration (Kind)
- Manifest validation

### Kubernetes Operator (e.g., kserve, training-operator)
- Docker build validation
- CRD installation testing
- Operator deployment (Kind)
- Webhook validation
- RBAC testing

### Service or job consumed by an external operator (e.g., model-registry)
- Konflux target discovery from `.tekton/*pull-request.yaml`, including
  parameter defaults from external `pipelineRef` pipelines
- Hermetic preflight: `GOPROXY=off` compile and Python wheelhouse resolution
- Container build, health/API runtime checks, and manifest validation
- **Phase 4 against the external operator**: deploy it at a pinned commit, pin
  its `RELATED_IMAGE_*` variable to the PR image, create a CR, and assert the
  rendered workload uses that image with zero restarts
- Cross-repo contract check: the operator's component entry (repo, ref,
  `sourcePath`) must point at a real directory, and the manifest directory name
  must match what the controller reads

### Standalone service or job (no operator consumer)
- Konflux target discovery from `.tekton/*pull-request.yaml`
- Hermetic preflight: `GOPROXY=off` compile and Python wheelhouse resolution
- Container build, health/API runtime checks, and manifest validation

### Component/Library
- Docker build validation (if Dockerfile exists)
- Runtime testing
- Integration validation

## Benefits

### Prevents Build Failures
- ✅ Catches failures BEFORE merge
- ✅ No broken main branch
- ✅ No Konflux production failures
- ✅ Faster development cycle

### Comprehensive Coverage
- ✅ **Hermetic build failures** - Catches issues before downstream RHOAI builds
- ✅ **Workspace dependency issues** - Prevents missing package errors
- ✅ **FIPS compliance violations** - Warns about release blockers
- ✅ **Dependency regressions** - Detects crashloops from breaking changes (e.g., fastify v4→v5)
- ✅ **WebSocket crashes** - Catches @fastify/websocket v11 pod crashes (PR #6727, #7387)
- ✅ **API content-type rejections** - Detects 415 errors on PATCH operations (PR #6727, #7387)
- ✅ **Permission issues** - Tests non-root user runtime
- ✅ Docker build failures (any stage)
- ✅ Module Federation issues (including missing chunks, slow loads)
- ✅ Operator packaging problems
- ✅ Manifest generation errors
- ✅ Runtime crashes (immediate and delayed)

### Developer Experience
- ✅ Fast feedback (10-20 min)
- ✅ Clear error messages
- ✅ Automated validation
- ✅ No manual setup

## Time Estimate

- Quick setup (basic Docker build): 30-45 minutes
- Standard setup (with operator integration): 1-2 hours
- Comprehensive (with all validations): 2-3 hours

## Requirements

- Repository with Dockerfile
- GitHub Actions enabled
- Public or accessible repository
