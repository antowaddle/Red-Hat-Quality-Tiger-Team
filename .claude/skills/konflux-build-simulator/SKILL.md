---
name: konflux-build-simulator
description: Simulates Konflux build environment on PRs to catch build failures before they reach production - validates Docker builds, Module Federation, operator integration, and FIPS compliance
user-invocable: true
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
- ✅ **Hermetic build preflight** - Tests lockfile integrity without full build
  - Runs docker build --network=none with npm ci --ignore-scripts
  - Catches lockfile-out-of-sync issues in <1 minute
  - Validates both root and module lockfiles

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

#### Phase 5: Manifest Validation (if applicable)
- ✅ Kustomize build validation
- ✅ ConfigMap generation
- ✅ Overlay testing
- ✅ Resource validation

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
- **Fast Feedback**: Runs in 10-20 minutes on PRs
- **Comprehensive**: Catches most common build failures before merge
- **Automated**: No manual intervention needed
- **Documented**: Clear failure messages and logs
- **Skippable**: Add `[skip konflux-sim]` to PR title to skip

## Repository Type Detection

The skill automatically detects repository type and generates appropriate validation:

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
