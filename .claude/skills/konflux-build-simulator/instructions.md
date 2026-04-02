# PR Build Validation - Implementation Instructions

## Task

Analyze a repository and generate comprehensive PR build validation workflows that catch build failures before they reach Konflux/production.

## Input

- Repository URL (required)
- Optional: Build modes to test (RHOAI, ODH, etc.)
- Optional: Platforms to target (if multi-arch)

## Output

Generate GitHub Actions workflows and supporting files for PR build validation.

## Process

### Phase 1: Repository Analysis

#### Step 1.1: Detect Repository Type

```bash
# Clone repository
git clone <repo-url> /tmp/pr-build-repo
cd /tmp/pr-build-repo

# Identify type
if [ -f "Dockerfile" ] || [ -f "Containerfile" ]; then
  echo "✅ Container-based repository"
fi

if [ -d "manifests" ] || [ -d "config" ]; then
  echo "✅ Operator repository"
fi

if [ -d "packages" ] && [ -f "turbo.json" ]; then
  echo "✅ Monorepo"
fi
```

#### Step 1.2: Analyze Dockerfile/Containerfile

Extract critical information:

```bash
# Check for build args
grep "ARG BUILD_MODE" Dockerfile
grep "ARG BASE_IMAGE" Dockerfile

# Check for multi-stage build
grep "FROM .* as " Dockerfile

# Identify COPY commands (potential failure points)
grep "^COPY" Dockerfile

# Check CMD/ENTRYPOINT
grep "^CMD\|^ENTRYPOINT" Dockerfile
```

#### Step 1.3: Detect Module Federation (if monorepo)

```bash
# Check for Module Federation
find . -name "moduleFederation.js" -o -name "webpack*.js"

# Check for remotes configuration
grep -r "remoteEntry" . --include="*.json" --include="*.js"

# Identify packages
ls -d packages/*/
```

#### Step 1.4: Analyze Manifests (if operator)

```bash
# Find manifest directories
find . -type d -name "manifests" -o -name "config"

# Check for Kustomize
find . -name "kustomization.yaml"

# Identify CRDs
find . -name "*_crd.yaml" -o -name "*crd.yaml"

# Find overlays
find manifests -type d -name "overlays"
```

### Phase 2: Generate Build Validation Workflow

#### Step 2.1: Create Base Workflow Template

```yaml
name: PR Build Validation

on:
  pull_request:
    branches: [main, v*, release-*]
    paths:
      - 'Dockerfile'
      - 'Containerfile'
      - 'src/**'
      - 'packages/**'
      - 'manifests/**'
      - '.github/workflows/pr-build-validation.yml'

# Allow skipping via [skip konflux-sim] in PR title or commit message

env:
  # Extracted from Dockerfile ARG defaults
  BUILD_MODE: RHOAI  # Or detected from Konflux config
  IMAGE_NAME: ${{ github.repository }}:pr-${{ github.event.pull_request.number }}

jobs:
  build-validation:
    name: Validate Build
    runs-on: ubuntu-latest
    timeout-minutes: 30
    # Skip if [skip konflux-sim] is in PR title or commit message
    if: |
      !contains(github.event.pull_request.title, '[skip konflux-sim]') &&
      !contains(github.event.head_commit.message, '[skip konflux-sim]')

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      # Phase 1: Docker Build
      - name: Build Docker Image
        id: build
        run: |
          docker build \
            --build-arg BUILD_MODE=${{ env.BUILD_MODE }} \
            --tag ${{ env.IMAGE_NAME }} \
            -f Dockerfile \
            .

      # Phase 2: Runtime Validation
      - name: Test Container Startup
        run: |
          # Start container
          # Backend may reference K8s service account paths that don't exist outside cluster
          # Container should handle this gracefully and not crash on startup
          docker run -d \
            --name test-container \
            -p 8080:8080 \
            ${{ env.IMAGE_NAME }}

          # Wait for container to be running
          echo "Waiting for container to start..."
          sleep 5

          # Check if container is still running (didn't crash on startup)
          if ! docker ps | grep -q test-container; then
            echo "❌ Container failed to start or crashed immediately"
            echo "Container logs:"
            docker logs test-container || true
            docker ps -a
            exit 1
          fi

          # Wait for health check
          timeout 60 bash -c 'until docker ps | grep test-container | grep -q "Up"; do sleep 2; done' || {
            echo "❌ Container failed health check"
            docker logs test-container
            exit 1
          }

          # Give it a moment to fully initialize
          sleep 10

      - name: Validate Endpoints
        run: |
          # Health check from HOST (curl doesn't exist in UBI9 nodejs images by default)
          # Use host-side curl with mapped port instead of docker exec
          curl -f http://localhost:8080/ || {
            echo "Health check failed"
            docker logs test-container
            exit 1
          }

          echo "✅ Health check passed"

      # Collect logs on failure
      - name: Debug Logs
        if: failure()
        run: |
          echo "=== Container Logs ==="
          docker logs test-container || true

          echo "=== Container Status ==="
          docker ps -a

          echo "=== Docker Inspect ==="
          docker inspect test-container || true
```

#### Step 2.2: Add Module Federation Validation (if detected)

```yaml
      # Phase 3: Module Federation Validation
      - name: Validate Module Federation Build Output
        if: ${{ env.IS_MONOREPO == 'true' }}
        run: |
          # Validate that webpack actually generated the remoteEntry.js files
          # NOTE: /_mf/{name}/* routes are PROXIES to K8s services (port 8043), not local files
          # Standalone container returns 404 for all /_mf/* requests
          # This validates the BUILD created the assets, not runtime proxy endpoints

          docker run --rm ${{ env.IMAGE_NAME }} sh -c '
            for module in {DETECTED_MODULES}; do
              # Check if module has MF config first
              if [ -f "/opt/app-root/src/packages/${module}/package.json" ]; then
                if grep -q "module-federation" "/opt/app-root/src/packages/${module}/package.json"; then
                  # Validate remoteEntry.js was generated in dist or build output
                  if [ ! -f "/opt/app-root/src/packages/${module}/frontend/dist/remoteEntry.js" ] &&
                     [ ! -f "/opt/app-root/src/packages/${module}/dist/remoteEntry.js" ]; then
                    echo "ERROR: remoteEntry.js not found for ${module}"
                    exit 1
                  else
                    echo "✅ $module: remoteEntry.js generated successfully"
                  fi
                fi
              fi
            done
            echo "✅ All Module Federation remotes built successfully"
          ' || {
            echo "❌ Module Federation build validation failed"
            exit 1
          }
```

#### Step 2.3: Add Operator Integration Testing (if detected)

```yaml
  operator-integration:
    name: Operator Integration Test
    needs: build-validation
    runs-on: ubuntu-latest
    if: ${{ env.IS_OPERATOR == 'true' }}

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Kind Cluster
        uses: helm/kind-action@v1
        with:
          node_image: kindest/node:v1.35.0
          config: |
            kind: Cluster
            apiVersion: kind.x-k8s.io/v1alpha4
            nodes:
            - role: control-plane

      - name: Build and Load Image
        run: |
          # Build image
          docker build \
            --build-arg BUILD_MODE=${{ env.BUILD_MODE }} \
            --tag localhost:5000/${{ env.IMAGE_NAME }} \
            -f Dockerfile \
            .

          # Load to Kind
          kind load docker-image localhost:5000/${{ env.IMAGE_NAME }}

      - name: Install CRDs
        run: |
          # Apply CRDs (find location dynamically)
          if [ -d "config/crd" ]; then
            kubectl apply -k config/crd
          elif [ -d "manifests/crd" ]; then
            kubectl apply -f manifests/crd/
          else
            echo "No CRD directory found, skipping"
          fi

      - name: Apply Manifests
        run: |
          # Determine manifest location
          if [ -f "config/default/kustomization.yaml" ]; then
            MANIFEST_DIR="config/default"
          elif [ -f "manifests/base/kustomization.yaml" ]; then
            MANIFEST_DIR="manifests/base"
          else
            echo "❌ No manifest directory found"
            exit 1
          fi

          # Patch image
          cd $MANIFEST_DIR
          kustomize edit set image controller=localhost:5000/${{ env.IMAGE_NAME }}

          # Apply
          kubectl apply -k .

      - name: Wait for Deployment
        run: |
          # Find deployment name
          DEPLOYMENT=$(kubectl get deployment -o name | head -n1)

          if [ -z "$DEPLOYMENT" ]; then
            echo "❌ No deployment found"
            kubectl get all
            exit 1
          fi

          echo "Waiting for $DEPLOYMENT to be ready..."
          kubectl wait --for=condition=available $DEPLOYMENT --timeout=5m || {
            echo "❌ Deployment failed"
            kubectl get pods
            kubectl describe $DEPLOYMENT
            kubectl logs -l control-plane=controller-manager --tail=100 || true
            exit 1
          }

          echo "✅ Deployment successful"

      - name: Validate Operator
        run: |
          # Get pods
          kubectl get pods

          # Check logs for errors
          kubectl logs -l control-plane=controller-manager --tail=50 || true

          # Verify operator is running
          POD=$(kubectl get pod -l control-plane=controller-manager -o name | head -n1)
          kubectl exec $POD -- curl -f http://localhost:8080/metrics || echo "No metrics endpoint"

      - name: Debug on Failure
        if: failure()
        run: |
          echo "=== Pods ==="
          kubectl get pods -A

          echo "=== Deployments ==="
          kubectl get deployments -A

          echo "=== Events ==="
          kubectl get events --sort-by='.lastTimestamp'

          echo "=== Logs ==="
          kubectl logs -l control-plane=controller-manager --tail=200 || true
```

#### Step 2.4: Add Manifest Validation (if detected)

```yaml
  manifest-validation:
    name: Validate Manifests
    runs-on: ubuntu-latest
    if: ${{ env.HAS_MANIFESTS == 'true' }}

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      # Kustomize is pre-installed on ubuntu-latest runners
      # No installation needed

      - name: Validate Kustomize Builds
        run: |
          # Find all kustomization.yaml files
          KUSTOMIZATIONS=$(find manifests config -name "kustomization.yaml" -o -name "kustomization.yml")

          for kust in $KUSTOMIZATIONS; do
            DIR=$(dirname $kust)
            echo "Building $DIR..."

            kustomize build $DIR > /tmp/$(basename $DIR).yaml || {
              echo "❌ Kustomize build failed for $DIR"
              exit 1
            }

            echo "✅ $DIR validated"
          done

      - name: Validate Generated Resources
        run: |
          for file in /tmp/*.yaml; do
            echo "Checking $file..."

            # Validate required resource types
            grep -q "kind: Deployment" $file || echo "⚠️  No Deployment in $file"
            grep -q "kind: Service" $file || echo "⚠️  No Service in $file"

            # Check for common issues
            grep "image: .*latest" $file && echo "⚠️  Warning: 'latest' tag found in $file"
          done
```

### Phase 3: Generate Helper Scripts

#### Step 3.1: Create `scripts/validate-build.sh`

```bash
#!/bin/bash
set -e

echo "=== PR Build Validation Script ==="

# Configuration
IMAGE_NAME=${1:-"test-image:pr"}
BUILD_MODE=${2:-"RHOAI"}
DOCKERFILE=${3:-"Dockerfile"}

# Build
echo "Building Docker image with BUILD_MODE=$BUILD_MODE..."
docker build \
  --build-arg BUILD_MODE=$BUILD_MODE \
  --tag $IMAGE_NAME \
  -f $DOCKERFILE \
  .

# Test startup
echo "Testing container startup..."
docker run -d --name test-build -p 8080:8080 $IMAGE_NAME

# Wait for health
echo "Waiting for health check..."
timeout 60 bash -c 'until curl -sf http://localhost:8080; do sleep 2; done' || {
  echo "❌ Container failed health check"
  docker logs test-build
  docker rm -f test-build
  exit 1
}

# Validate
echo "Container started successfully"
docker logs test-build | tail -20

# Cleanup
docker rm -f test-build

echo "✅ Build validation passed"
```

### Phase 4: Generate Documentation

#### Step 4.1: Create `docs/pr-build-validation.md`

```markdown
# PR Build Validation

This repository uses automated PR build validation to catch build failures before merge.

## What's Validated

- ✅ Docker build with production configuration
- ✅ Container startup and health checks
- ✅ Module Federation (if applicable)
- ✅ Operator integration (if applicable)
- ✅ Manifest generation (if applicable)

## Workflow

1. PR created
2. GitHub Actions runs build validation
3. Build, test, and validate (10-20 minutes)
4. Feedback on PR

## Troubleshooting

### Build Fails

Check the workflow logs for the exact error. Common issues:

- **Missing build arg**: Check BUILD_MODE matches Konflux
- **COPY failure**: Build output path changed
- **Module Federation**: Remote entry not generated

### Container Won't Start

Check `docker logs` in the workflow output. Common issues:

- **Missing env var**: Add to Dockerfile or deployment
- **Port binding**: Ensure correct port (default 8080)
- **Crash on startup**: Check application logs

### Operator Integration Fails

Check Kind cluster logs. Common issues:

- **CRD not applied**: Ensure CRDs in correct location
- **Image pull failure**: Verify image tag correct
- **RBAC issues**: Check service account permissions

## Local Testing

Run locally before pushing:

\`\`\`bash
./scripts/validate-build.sh
\`\`\`

## Configuration

Edit `.github/workflows/pr-build-validation.yml` to adjust:

- Build arguments
- Timeout values
- Platforms to test
```

### Phase 5: Output and Validation

#### Step 5.1: Generate File Structure

```text
.github/
  workflows/
    pr-build-validation.yml      # Main workflow

scripts/
  validate-build.sh              # Helper script

docs/
  pr-build-validation.md         # Documentation

manifests/
  pr-testing/                    # PR-specific manifests (if needed)
    kustomization.yaml
```

#### Step 5.2: Validation Checklist

- [ ] Workflow syntax is valid
- [ ] Build args match Konflux configuration
- [ ] Module Federation modules detected correctly
- [ ] Manifest paths are correct
- [ ] Documentation is clear
- [ ] Scripts are executable

### Phase 6: Integration with Existing Workflows

#### Step 6.1: Update PR Template (if exists)

Add to `.github/pull_request_template.md`:

```markdown
## Build Validation

- [ ] PR build validation workflow passed
- [ ] No build errors in logs
- [ ] Container starts successfully
- [ ] All remotes load (if Module Federation)
```

#### Step 6.2: Add Status Check Requirement

Suggest adding to repository settings:
- Require "Validate Build" status check before merge

## Success Metrics

### Before Implementation

| Metric | Current |
|--------|---------|
| Build failures caught on PR | 0% |
| Build failures in Konflux | Unknown |
| Time to detect | Hours/days |

### After Implementation

| Metric | Target |
|--------|--------|
| Build failures caught on PR | 90%+ |
| Build failures in Konflux | <5% |
| Time to detect | 10-20 min |

## Error Handling

### Common Issues

1. **Repository has no Dockerfile**: Skip Docker build validation, focus on other checks
2. **Multiple Dockerfiles**: Ask user which to validate or validate all
3. **Complex build args**: Extract from `.tekton` files if available
4. **No manifests**: Skip operator integration

### Fallback Strategies

- If Module Federation detection fails: Skip MF validation
- If Kind cluster fails: Warn but don't fail
- If validation script fails: Provide detailed error message

## Time Estimates

- Analysis: 5-10 minutes
- Workflow generation: 10-15 minutes
- Script creation: 5-10 minutes
- Documentation: 5-10 minutes
- **Total**: 30-45 minutes per repository

## Key Files to Examine

### Build Configuration
- `Dockerfile`, `Containerfile`
- `.tekton/*.yaml` (Konflux config)
- `package.json` (build scripts)

### Manifests
- `manifests/`, `config/`
- `kustomization.yaml` files
- CRD definitions

### Module Federation
- `**/moduleFederation.js`
- `webpack*.config.js`
- `package.json` (module-federation field)

## Output Validation

Generated workflow should:
- ✅ Build Docker image
- ✅ Test container startup
- ✅ Validate critical endpoints
- ✅ Provide clear error messages
- ✅ Complete in < 20 minutes
