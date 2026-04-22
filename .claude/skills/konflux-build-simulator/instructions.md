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

#### Step 1.5: Analyze Lockfiles for Hermetic Build Compatibility

**Context:** Downstream RHOAI builds use Hermeto/Cachi2 for hermetic builds (no network access during build). Package lockfiles must be compatible with pre-fetching.

```bash
# Check for npm lockfiles
LOCKFILES=$(find . -name "package-lock.json")

for lockfile in $LOCKFILES; do
  echo "Analyzing $lockfile for Hermeto compatibility..."
  
  # Check for unsupported dependency protocols
  # git+, github:, file: protocols break Hermeto prefetch
  if grep -q '"resolved".*\(git+\|github:\|file:\)' "$lockfile"; then
    echo "⚠️  Found unsupported dependency protocol in $lockfile"
    echo "   Hermeto/Cachi2 cannot prefetch git+, github:, or file: dependencies"
    grep '"resolved".*\(git+\|github:\|file:\)' "$lockfile" | head -5
  fi
  
  # Check for missing resolved URLs
  # All dependencies must have resolved field for prefetch
  if grep -q '"version":' "$lockfile" && ! grep -q '"resolved":' "$lockfile"; then
    echo "⚠️  Missing resolved URLs in $lockfile"
  fi
done

# Check for Go modules
if [ -f "go.mod" ]; then
  echo "✅ Found go.mod"
  
  # Verify go.sum exists
  if [ ! -f "go.sum" ]; then
    echo "❌ go.mod exists but go.sum is missing"
    echo "   Required for hermetic builds"
  else
    echo "✅ go.sum present"
  fi
  
  # Check for multiple go.mod files (monorepo BFFs)
  GO_MODS=$(find packages -name "go.mod" 2>/dev/null || true)
  for gomod in $GO_MODS; do
    gosum="${gomod%%.mod}.sum"
    if [ ! -f "$gosum" ]; then
      echo "❌ $gomod exists but $gosum is missing"
    else
      echo "✅ $gomod has corresponding go.sum"
    fi
  done
fi
```

#### Step 1.6: Analyze Workspace Dependencies (Monorepo Only)

**Context:** Monorepo modules often import workspace packages. The Dockerfile must COPY all referenced workspace packages or the build fails.

```bash
# Detect workspace configuration from root package.json
WORKSPACE_SCOPE=""
WORKSPACE_DIRS=()

if [ -f "package.json" ]; then
  # Detect workspace scope from package name (e.g., @odh-dashboard/foo -> @odh-dashboard)
  WORKSPACE_SCOPE=$(grep -o '"name"[[:space:]]*:[[:space:]]*"@[^/]*' package.json | sed 's/.*"@/@/' || true)
  
  # Detect workspace directories from workspaces field
  # Common patterns: packages/*, apps/*, libs/*
  if grep -q '"workspaces"' package.json; then
    WORKSPACE_PATTERNS=$(grep -A 10 '"workspaces"' package.json | grep -o '"[^"]*\/\*"' | tr -d '"' | sed 's/\/\*//' || true)
    
    for pattern in $WORKSPACE_PATTERNS; do
      if [ -d "$pattern" ]; then
        WORKSPACE_DIRS+=("$pattern")
      fi
    done
  fi
  
  # Fallback: check common workspace directories
  if [ ${#WORKSPACE_DIRS[@]} -eq 0 ]; then
    for dir in packages apps libs modules components; do
      if [ -d "$dir" ]; then
        WORKSPACE_DIRS+=("$dir")
      fi
    done
  fi
fi

if [ ${#WORKSPACE_DIRS[@]} -eq 0 ]; then
  echo "Not a workspace monorepo, skipping workspace validation"
else
  echo "Analyzing workspace dependencies..."
  echo "Workspace scope: ${WORKSPACE_SCOPE:-<none>}"
  echo "Workspace directories: ${WORKSPACE_DIRS[@]}"
  
  # Find all Dockerfile.workspace files in workspace directories
  WORKSPACE_DOCKERFILES=""
  for wsdir in "${WORKSPACE_DIRS[@]}"; do
    WORKSPACE_DOCKERFILES+=$(find "$wsdir" -name "Dockerfile.workspace" -o -name "Dockerfile" 2>/dev/null || true)
    WORKSPACE_DOCKERFILES+=$'\n'
  done
  
  for dockerfile in $WORKSPACE_DOCKERFILES; do
    [ -z "$dockerfile" ] && continue
    
    module=$(dirname "$dockerfile")
    echo "Checking $dockerfile..."
    
    # Extract COPY commands that reference workspace directories
    COPIED_PACKAGES=""
    for wsdir in "${WORKSPACE_DIRS[@]}"; do
      COPIED=$(grep "^COPY.*$wsdir/" "$dockerfile" | sed "s/.*COPY.*\($wsdir\/[^\/]*\).*/\1/" | sort -u || true)
      COPIED_PACKAGES+="$COPIED"$'\n'
    done
    COPIED_PACKAGES=$(echo "$COPIED_PACKAGES" | sort -u | grep -v "^$")
    
    # Find package.json for this module
    PKG_JSON="$module/package.json"
    if [ ! -f "$PKG_JSON" ]; then
      echo "  No package.json found, skipping"
      continue
    fi
    
    # Extract workspace dependencies
    WORKSPACE_DEPS=""
    
    # Pattern 1: Scoped packages (@scope/*)
    if [ -n "$WORKSPACE_SCOPE" ]; then
      SCOPED_DEPS=$(grep -o "\"$WORKSPACE_SCOPE/[^\"]*\"" "$PKG_JSON" | tr -d '"' || true)
      for dep in $SCOPED_DEPS; do
        # Convert @scope/name to workspace/name
        pkg_name=${dep#$WORKSPACE_SCOPE/}
        for wsdir in "${WORKSPACE_DIRS[@]}"; do
          if [ -d "$wsdir/$pkg_name" ]; then
            WORKSPACE_DEPS+="$wsdir/$pkg_name"$'\n'
            break
          fi
        done
      done
    fi
    
    # Pattern 2: workspace:* protocol
    WORKSPACE_PROTOCOL_DEPS=$(grep -o '"workspace:[^"]*"' "$PKG_JSON" || true)
    # These are harder to resolve without parsing, just warn about them
    
    # Pattern 3: Check source code for imports if scope is known
    if [ -n "$WORKSPACE_SCOPE" ]; then
      SRC_IMPORTS=$(find "$module" -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" 2>/dev/null | \
        xargs grep -h "from '$WORKSPACE_SCOPE/" 2>/dev/null | \
        sed "s/.*from '$WORKSPACE_SCOPE\/\([^'\"]*\).*/\1/" | \
        sort -u || true)
      
      for imp in $SRC_IMPORTS; do
        for wsdir in "${WORKSPACE_DIRS[@]}"; do
          if [ -d "$wsdir/$imp" ]; then
            WORKSPACE_DEPS+="$wsdir/$imp"$'\n'
            break
          fi
        done
      done
    fi
    
    WORKSPACE_DEPS=$(echo "$WORKSPACE_DEPS" | sort -u | grep -v "^$")
    
    # Cross-reference dependencies vs COPY commands
    for dep in $WORKSPACE_DEPS; do
      if ! echo "$COPIED_PACKAGES" | grep -q "^$dep$"; then
        # Check if it's a runtime dependency (not devDependency)
        dep_name=$(basename "$dep")
        if grep -A 50 '"dependencies"' "$PKG_JSON" | grep -q "\"$dep_name\""; then
          echo "⚠️  $dockerfile: imports $dep (runtime dependency) but does not COPY it"
          echo "   Add: COPY $dep/ /path/to/destination/"
        else
          echo "ℹ️  $dockerfile: references $dep (devDependency, may not need COPY)"
        fi
      fi
    done
  done
fi
```

#### Step 1.7: Analyze FIPS Compliance (RHOAI Specific)

**Context:** RHOAI downstream builds require FIPS-compatible cryptography. This means esbuild (which contains non-FIPS crypto) must be removed, and Go binaries must use FIPS-validated crypto libraries.

```bash
# Check main Dockerfile for esbuild removal
if [ -f "Dockerfile" ]; then
  echo "Checking FIPS compliance in Dockerfile..."
  
  # Verify esbuild is removed (required for FIPS)
  if ! grep -q "rm -rf.*node_modules/esbuild" Dockerfile; then
    echo "⚠️  Dockerfile does not remove node_modules/esbuild"
    echo "   RHOAI FIPS builds require: RUN rm -rf node_modules/esbuild"
    echo "   This blocks product release for FIPS compliance"
  else
    echo "✅ esbuild removal found (FIPS compliant)"
  fi
fi

# Check Dockerfile.workspace files for Go FIPS build tags
WORKSPACE_DOCKERFILES=$(find . -name "Dockerfile.workspace" 2>/dev/null || true)

for dockerfile in $WORKSPACE_DOCKERFILES; do
  echo "Checking $dockerfile for FIPS compliance..."
  
  # Check if this Dockerfile builds a Go binary (has bff-builder stage)
  if grep -q "FROM.*bff-builder" "$dockerfile" || grep -q "go build" "$dockerfile"; then
    # Verify -tags strictfipsruntime is used
    if ! grep -q "\-tags.*strictfipsruntime" "$dockerfile"; then
      echo "⚠️  $dockerfile builds Go binary without -tags strictfipsruntime"
      echo "   RHOAI FIPS builds require: go build -tags strictfipsruntime"
      echo "   Add to go build command in bff-builder stage"
    else
      echo "✅ strictfipsruntime tag found (FIPS compliant)"
    fi
  fi
done
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
  # Early validation checks (run in <30s before Docker build)
  validation-checks:
    name: Static Validation Checks
    runs-on: ubuntu-latest
    timeout-minutes: 5
    if: |
      !contains(github.event.pull_request.title, '[skip konflux-sim]')
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Validate NPM Lockfiles
        run: |
          # Check all package-lock.json files for Hermeto/Cachi2 compatibility
          LOCKFILES=$(find . -name "package-lock.json")
          ISSUES=0
          
          for lockfile in $LOCKFILES; do
            echo "Checking $lockfile..."
            
            # Check for unsupported protocols (git+, github:, file:)
            if grep -q '"resolved".*\(git+\|github:\|file:\)' "$lockfile"; then
              echo "❌ $lockfile contains unsupported dependency protocols"
              echo "   Hermeto/Cachi2 cannot prefetch git+, github:, or file: dependencies"
              echo "   Affected dependencies:"
              grep '"resolved".*\(git+\|github:\|file:\)' "$lockfile" | head -5
              ISSUES=$((ISSUES + 1))
            fi
            
            # Check for missing resolved URLs
            PKG_COUNT=$(grep -c '"version":' "$lockfile" || true)
            RESOLVED_COUNT=$(grep -c '"resolved":' "$lockfile" || true)
            
            if [ $PKG_COUNT -gt 0 ] && [ $RESOLVED_COUNT -eq 0 ]; then
              echo "⚠️  $lockfile is missing resolved URLs"
              echo "   This may cause issues with hermetic builds"
              ISSUES=$((ISSUES + 1))
            fi
          done
          
          if [ $ISSUES -gt 0 ]; then
            echo ""
            echo "❌ Lockfile validation failed with $ISSUES issue(s)"
            echo "   Downstream hermetic builds (RHOAI) will fail"
            echo ""
            echo "How to fix:"
            echo "  1. Run 'npm install' to regenerate package-lock.json"
            echo "  2. Replace git+/github:/file: dependencies with npm registry versions"
            echo "  3. Ensure all dependencies have 'resolved' URLs"
            exit 1
          else
            echo "✅ All lockfiles are hermetic build compatible"
          fi
      
      - name: Validate Go Modules
        if: hashFiles('go.mod') != ''
        run: |
          ISSUES=0
          
          # Check root go.mod
          if [ -f "go.mod" ]; then
            if [ ! -f "go.sum" ]; then
              echo "❌ go.mod exists but go.sum is missing"
              ISSUES=$((ISSUES + 1))
            else
              echo "✅ Root go.mod/go.sum present"
              
              # Verify checksums if Go is available
              if command -v go &> /dev/null; then
                echo "Verifying Go module checksums..."
                go mod verify || {
                  echo "❌ go mod verify failed"
                  ISSUES=$((ISSUES + 1))
                }
              fi
            fi
          fi
          
          # Check for BFF go.mod files in packages/*/bff
          for gomod in $(find packages -name "go.mod" 2>/dev/null || true); do
            gosum="${gomod%%.mod}.sum"
            if [ ! -f "$gosum" ]; then
              echo "❌ $gomod exists but $gosum is missing"
              ISSUES=$((ISSUES + 1))
            else
              echo "✅ $gomod has corresponding go.sum"
              
              # Verify if Go is available
              if command -v go &> /dev/null; then
                DIR=$(dirname "$gomod")
                (cd "$DIR" && go mod verify) || {
                  echo "❌ go mod verify failed for $gomod"
                  ISSUES=$((ISSUES + 1))
                }
              fi
            fi
          done
          
          if [ $ISSUES -gt 0 ]; then
            echo ""
            echo "❌ Go module validation failed"
            echo ""
            echo "How to fix:"
            echo "  1. Run 'go mod tidy' in directories with go.mod"
            echo "  2. Commit the updated go.sum file"
            exit 1
          else
            echo "✅ All Go modules validated"
          fi
      
      - name: Validate Workspace Dependencies
        if: hashFiles('packages/*/package.json') != ''
        run: |
          # Workspace COPY cross-reference for monorepos
          ISSUES=0
          
          for dockerfile in $(find packages -name "Dockerfile.workspace" -o -name "Dockerfile" | grep -v node_modules); do
            MODULE=$(dirname "$dockerfile")
            echo "Checking $dockerfile..."
            
            # Extract packages that are COPY'd
            COPIED=$(grep "^COPY.*packages/" "$dockerfile" | sed 's/.*COPY.*\(packages\/[^\/]*\).*/\1/' | sort -u || true)
            
            # Check package.json for workspace deps
            PKG_JSON="$MODULE/package.json"
            if [ -f "$PKG_JSON" ]; then
              # Find @odh-dashboard/* dependencies
              DEPS=$(grep -o '"@odh-dashboard/[^"]*"' "$PKG_JSON" | tr -d '"' | sed 's/@odh-dashboard\//packages\//' | sort -u || true)
              
              # Cross-reference
              for dep in $DEPS; do
                if ! echo "$COPIED" | grep -q "^$dep$"; then
                  echo "⚠️  $dockerfile imports $dep but does not COPY it"
                  echo "   This will cause Docker build to fail"
                  echo "   Add: COPY $dep/ /path/to/destination/"
                  ISSUES=$((ISSUES + 1))
                fi
              done
              
              if [ $ISSUES -eq 0 ]; then
                echo "✅ All workspace dependencies are COPY'd"
              fi
            fi
          done
          
          if [ $ISSUES -gt 0 ]; then
            echo ""
            echo "❌ Workspace dependency validation found $ISSUES issue(s)"
            exit 1
          fi
      
      - name: Validate FIPS Compliance
        run: |
          # FIPS compliance checks for RHOAI downstream builds
          ISSUES=0
          
          # Check main Dockerfile for esbuild removal
          if [ -f "Dockerfile" ]; then
            if ! grep -q "rm -rf.*node_modules/esbuild" Dockerfile; then
              echo "⚠️  Dockerfile does not remove node_modules/esbuild"
              echo "   RHOAI FIPS builds require: RUN rm -rf node_modules/esbuild"
              echo "   This blocks product release for FIPS compliance"
              ISSUES=$((ISSUES + 1))
            else
              echo "✅ esbuild removal found in Dockerfile (FIPS compliant)"
            fi
          fi
          
          # Check Dockerfile.workspace files for Go FIPS build tags
          for dockerfile in $(find . -name "Dockerfile.workspace" 2>/dev/null || true); do
            # Check if this Dockerfile builds a Go binary (has bff-builder stage)
            if grep -q "FROM.*bff-builder" "$dockerfile" || grep -q "go build" "$dockerfile"; then
              # Verify -tags strictfipsruntime is used
              if ! grep -q "\-tags.*strictfipsruntime" "$dockerfile"; then
                echo "⚠️  $dockerfile builds Go binary without -tags strictfipsruntime"
                echo "   RHOAI FIPS builds require: go build -tags strictfipsruntime"
                ISSUES=$((ISSUES + 1))
              else
                echo "✅ $dockerfile has strictfipsruntime tag (FIPS compliant)"
              fi
            fi
          done
          
          if [ $ISSUES -gt 0 ]; then
            echo ""
            echo "⚠️  FIPS compliance validation found $ISSUES issue(s)"
            echo "   These are warnings for RHOAI downstream builds"
            echo "   They will block product release if not fixed"
            # Don't exit 1 - these are warnings, not hard failures
          else
            echo "✅ All FIPS compliance checks passed"
          fi

  hermetic-preflight:
    name: Hermetic Build Preflight
    runs-on: ubuntu-latest
    timeout-minutes: 10
    needs: validation-checks
    if: |
      !contains(github.event.pull_request.title, '[skip konflux-sim]') &&
      hashFiles('package-lock.json') != ''
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Test Hermetic NPM Install (Root)
        run: |
          # Simulate hermetic build - no network access
          # This tests if package-lock.json is in sync without building full image
          
          # Create minimal Dockerfile for npm ci test
          cat > Dockerfile.hermetic-test <<'EOF'
          FROM registry.access.redhat.com/ubi9/nodejs-20:latest
          WORKDIR /test
          COPY package.json package-lock.json ./
          RUN npm ci --ignore-scripts
          EOF
          
          echo "Testing hermetic npm install (--network=none)..."
          if docker build --network=none -f Dockerfile.hermetic-test -t hermetic-test:root . 2>&1 | tee /tmp/hermetic-build.log; then
            echo "✅ Root package-lock.json is hermetic build compatible"
          else
            echo "❌ Hermetic build failed for root package-lock.json"
            echo ""
            echo "This means the lockfile is out of sync or has dependencies"
            echo "that cannot be resolved without network access."
            echo ""
            echo "How to fix:"
            echo "  1. Run 'npm install' to regenerate package-lock.json"
            echo "  2. Ensure no git+, github:, or file: dependencies"
            echo "  3. Commit the updated lockfile"
            exit 1
          fi
      
      - name: Test Hermetic NPM Install (Modules)
        if: hashFiles('packages/*/frontend/package-lock.json') != ''
        run: |
          # Test each module's lockfile
          FAILED_MODULES=""
          
          for module_dir in packages/*/frontend; do
            if [ -f "$module_dir/package-lock.json" ]; then
              module_name=$(basename $(dirname "$module_dir"))
              echo ""
              echo "Testing $module_name hermetic build..."
              
              # Create test Dockerfile for this module
              cat > Dockerfile.hermetic-test-module <<EOF
          FROM registry.access.redhat.com/ubi9/nodejs-20:latest
          WORKDIR /test
          COPY $module_dir/package.json $module_dir/package-lock.json ./
          RUN npm ci --ignore-scripts
          EOF
              
              if docker build --network=none -f Dockerfile.hermetic-test-module -t hermetic-test:$module_name . 2>&1; then
                echo "✅ $module_name: hermetic build compatible"
              else
                echo "❌ $module_name: hermetic build failed"
                FAILED_MODULES="$FAILED_MODULES $module_name"
              fi
            fi
          done
          
          if [ -n "$FAILED_MODULES" ]; then
            echo ""
            echo "❌ Hermetic build failed for modules:$FAILED_MODULES"
            echo ""
            echo "Run 'npm install' in each failed module's frontend directory"
            echo "and commit the updated package-lock.json files"
            exit 1
          else
            echo ""
            echo "✅ All module lockfiles are hermetic build compatible"
          fi

  build-validation:
    name: Validate Build
    runs-on: ubuntu-latest
    timeout-minutes: 30
    needs: [validation-checks, hermetic-preflight]
    if: |
      always() &&
      !contains(github.event.pull_request.title, '[skip konflux-sim]') &&
      needs.validation-checks.result == 'success' &&
      (needs.hermetic-preflight.result == 'success' || needs.hermetic-preflight.result == 'skipped')

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

# P0: Hermetic lockfile validation function
validate_lockfiles() {
  echo ""
  echo "=== Validating Lockfiles for Hermetic Build ==="
  
  local issues=0
  
  # Check NPM lockfiles
  while IFS= read -r lockfile; do
    [ -z "$lockfile" ] && continue
    echo "Checking $lockfile..."
    
    # Check for unsupported protocols
    if grep -q '"resolved".*\(git+\|github:\|file:\)' "$lockfile"; then
      echo "❌ $lockfile contains unsupported dependency protocols"
      echo "   Hermeto/Cachi2 cannot prefetch git+, github:, or file: dependencies"
      grep '"resolved".*\(git+\|github:\|file:\)' "$lockfile" | head -5
      issues=$((issues + 1))
    fi
    
    # Check for missing resolved URLs
    pkg_count=$(grep -c '"version":' "$lockfile" || true)
    resolved_count=$(grep -c '"resolved":' "$lockfile" || true)
    
    if [ $pkg_count -gt 0 ] && [ $resolved_count -eq 0 ]; then
      echo "⚠️  $lockfile is missing resolved URLs"
      issues=$((issues + 1))
    fi
  done < <(find . -name "package-lock.json")
  
  # Check Go modules
  if [ -f "go.mod" ]; then
    if [ ! -f "go.sum" ]; then
      echo "❌ go.mod exists but go.sum is missing"
      issues=$((issues + 1))
    else
      echo "✅ Root go.mod/go.sum present"
      if command -v go &> /dev/null; then
        go mod verify || issues=$((issues + 1))
      fi
    fi
  fi
  
  # Check BFF modules
  while IFS= read -r gomod; do
    [ -z "$gomod" ] && continue
    gosum="${gomod%%.mod}.sum"
    if [ ! -f "$gosum" ]; then
      echo "❌ $gomod exists but $gosum is missing"
      issues=$((issues + 1))
    else
      echo "✅ $gomod has corresponding go.sum"
      if command -v go &> /dev/null; then
        (cd "$(dirname "$gomod")" && go mod verify) || issues=$((issues + 1))
      fi
    fi
  done < <(find packages -name "go.mod" 2>/dev/null || true)
  
  if [ $issues -gt 0 ]; then
    echo "❌ Lockfile validation failed with $issues issue(s)"
    return 1
  fi
  
  echo "✅ All lockfiles validated"
  return 0
}

# P0: Workspace COPY cross-reference validation function
validate_workspace_copies() {
  echo ""
  echo "=== Validating Workspace Dependencies ==="
  
  # Detect workspace configuration
  local workspace_scope=""
  local workspace_dirs=()
  
  if [ -f "package.json" ]; then
    # Detect workspace scope from package name
    workspace_scope=$(grep -o '"name"[[:space:]]*:[[:space:]]*"@[^/]*' package.json | sed 's/.*"@/@/' || true)
    
    # Detect workspace directories from workspaces field
    if grep -q '"workspaces"' package.json; then
      local patterns=$(grep -A 10 '"workspaces"' package.json | grep -o '"[^"]*\/\*"' | tr -d '"' | sed 's/\/\*//' || true)
      for pattern in $patterns; do
        [ -d "$pattern" ] && workspace_dirs+=("$pattern")
      done
    fi
    
    # Fallback: check common workspace directories
    if [ ${#workspace_dirs[@]} -eq 0 ]; then
      for dir in packages apps libs modules components; do
        [ -d "$dir" ] && workspace_dirs+=("$dir")
      done
    fi
  fi
  
  if [ ${#workspace_dirs[@]} -eq 0 ]; then
    echo "Not a workspace monorepo, skipping"
    return 0
  fi
  
  echo "Workspace scope: ${workspace_scope:-<none>}"
  echo "Workspace directories: ${workspace_dirs[*]}"
  
  local issues=0
  
  # Find all Dockerfile.workspace files
  for wsdir in "${workspace_dirs[@]}"; do
    while IFS= read -r dockerfile; do
      [ -z "$dockerfile" ] && continue
      
      local module=$(dirname "$dockerfile")
      echo "Checking $dockerfile..."
      
      # Extract COPY'd workspace packages
      local copied=""
      for ws in "${workspace_dirs[@]}"; do
        local pkg=$(grep "^COPY.*$ws/" "$dockerfile" | sed "s/.*COPY.*\($ws\/[^\/]*\).*/\1/" | sort -u || true)
        copied+="$pkg"$'\n'
      done
      copied=$(echo "$copied" | sort -u | grep -v "^$")
      
      # Check package.json
      local pkg_json="$module/package.json"
      [ ! -f "$pkg_json" ] && continue
      
      # Extract workspace dependencies
      local deps=""
      
      # Pattern 1: Scoped packages
      if [ -n "$workspace_scope" ]; then
        local scoped=$(grep -o "\"$workspace_scope/[^\"]*\"" "$pkg_json" | tr -d '"' || true)
        for dep in $scoped; do
          local pkg_name=${dep#$workspace_scope/}
          for ws in "${workspace_dirs[@]}"; do
            if [ -d "$ws/$pkg_name" ]; then
              deps+="$ws/$pkg_name"$'\n'
              break
            fi
          done
        done
      fi
      
      # Pattern 2: Check source for imports
      if [ -n "$workspace_scope" ]; then
        local imports=$(find "$module" -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" 2>/dev/null | \
          xargs grep -h "from '$workspace_scope/" 2>/dev/null | \
          sed "s/.*from '$workspace_scope\/\([^'\"]*\).*/\1/" | sort -u || true)
        
        for imp in $imports; do
          for ws in "${workspace_dirs[@]}"; do
            if [ -d "$ws/$imp" ]; then
              deps+="$ws/$imp"$'\n'
              break
            fi
          done
        done
      fi
      
      deps=$(echo "$deps" | sort -u | grep -v "^$")
      
      # Cross-reference
      for dep in $deps; do
        if ! echo "$copied" | grep -q "^$dep$"; then
          # Check if it's a runtime dependency
          local dep_name=$(basename "$dep")
          if grep -A 50 '"dependencies"' "$pkg_json" | grep -q "\"$dep_name\""; then
            echo "⚠️  $dockerfile imports $dep (runtime) but does not COPY it"
            echo "   Add: COPY $dep/ /path/to/destination/"
            issues=$((issues + 1))
          fi
        fi
      done
    done < <(find "$wsdir" -name "Dockerfile.workspace" -o -name "Dockerfile" | grep -v node_modules || true)
  done
  
  if [ $issues -gt 0 ]; then
    echo "❌ Workspace validation found $issues issue(s)"
    return 1
  fi
  
  echo "✅ All workspace dependencies validated"
  return 0
}

# P0: Run early validations
validate_lockfiles
validate_workspace_copies

# Build
echo ""
echo "=== Building Docker Image ==="
echo "Building with BUILD_MODE=$BUILD_MODE..."
docker build \
  --build-arg BUILD_MODE=$BUILD_MODE \
  --tag $IMAGE_NAME \
  -f $DOCKERFILE \
  .

# Test startup
echo ""
echo "=== Testing Container Startup ==="
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

echo ""
echo "✅ Build validation passed"
```

### Phase 4: Generate Documentation

#### Step 4.1: Create `docs/pr-build-validation.md`

```markdown
# PR Build Validation

This repository uses automated PR build validation to catch build failures before merge.

## What's Validated

- ✅ **Hermetic lockfile compatibility** (P0) - Validates package-lock.json and go.sum for downstream RHOAI builds
- ✅ **Workspace dependencies** (P0) - Ensures Dockerfiles COPY all referenced workspace packages
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

### Lockfile Validation Fails (P0)

**Error:** Unsupported dependency protocols (git+, github:, file:)

**Fix:**
1. Run `npm install` to regenerate package-lock.json
2. Replace git+/github:/file: dependencies with npm registry versions
3. Update package.json to use published packages instead of git references

**Error:** Missing go.sum file

**Fix:**
1. Run `go mod tidy` in the directory with go.mod
2. Commit the generated go.sum file

### Workspace Dependency Validation Fails (P0)

**Error:** Dockerfile imports package but does not COPY it

**Fix:**
1. Identify which workspace package is imported (e.g., @odh-dashboard/kserve)
2. Add COPY command to Dockerfile: `COPY packages/kserve/ /path/to/kserve/`
3. Ensure COPY happens before the build step that needs it

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
