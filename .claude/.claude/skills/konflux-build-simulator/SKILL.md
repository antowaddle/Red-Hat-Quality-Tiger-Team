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

#### Phase 1: Docker Build Validation
- ✅ Builds Docker image with production build mode (RHOAI, etc.)
- ✅ Tests multi-stage build (builder + runtime)
- ✅ Validates COPY commands and file paths
- ✅ Catches BUILD_MODE environment differences

#### Phase 2: Runtime Validation
- ✅ Starts container
- ✅ Waits for health check
- ✅ Validates endpoints
- ✅ Checks logs for errors

#### Phase 3: Module Federation Validation (if applicable)
- ✅ Validates remoteEntry.js build output in dist/
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

- **Konflux-Like Environment**: Simulates production build environment
- **Fast Feedback**: Runs in 10-20 minutes on PRs
- **Comprehensive**: Catches most common build failures before merge
- **Automated**: No manual intervention needed
- **Documented**: Clear failure messages and logs
- **Skippable**: Add `[skip konflux-sim]` to PR title or commit message to skip

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
- ✅ Docker build failures (any stage)
- ✅ Module Federation issues
- ✅ Operator packaging problems
- ✅ Manifest generation errors
- ✅ Runtime crashes

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
