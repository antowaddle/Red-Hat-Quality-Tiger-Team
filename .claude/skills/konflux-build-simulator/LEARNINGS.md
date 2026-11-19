# Konflux Build Simulator - Critical Learnings

## Issue: Hermetic npm install test with --network=none is unreliable

### Problem

The generated workflow includes this test:
```bash
docker run --rm \
  --network=none \
  -v "$(pwd)":/workspace \
  -w /workspace \
  node:22 \
  npm ci --ignore-scripts
```

This **consistently fails** with npm crash:
```
npm error Exit handler never called!
npm error This is an error with npm itself.
```

### Root Cause

`npm ci` performs validation and integrity checks that may attempt network operations even with `--ignore-scripts`. When `--network=none` is set, npm crashes instead of gracefully failing.

This is a known npm issue when running in completely isolated network environments.

### Why This Test is Flawed

1. **Docker image pull requires network**: The workflow pulls `node:22` image WITH network access, then runs npm with network disabled
2. **npm internals**: npm may try to contact registry for integrity checks even with `--ignore-scripts`
3. **Not representative**: Real hermetic builds (Hermeto/Cachi2) don't use `--network=none` - they pre-fetch tarballs
4. **Unreliable**: Crashes instead of providing useful validation

### What Actually Matters for Hermetic Builds

Hermeto/Cachi2 hermetic builds care about:
1. ✅ **No git+/github:/file: protocols** - Already validated with grep/jq
2. ✅ **All dependencies have resolved URLs** - Already validated with jq
3. ✅ **package-lock.json is in sync** - Can be validated differently

The `--network=none` test adds no additional value beyond what the lockfile validation already provides.

### Solution

**Remove the hermetic npm install test entirely.**

The workflow should only validate:
1. Lockfile compatibility (grep for unsupported protocols)
2. Resolved URLs presence (jq query)
3. Actual Docker build (which will catch real hermetic issues)

### Alternative: Lockfile Sync Validation

If you want to validate lockfile sync, use:
```bash
# Generate a fresh lockfile and compare
npm install --package-lock-only --ignore-scripts
if ! git diff --quiet package-lock.json; then
  echo "❌ package-lock.json is out of sync"
  exit 1
fi
```

This is more reliable than `--network=none`.

## Learning: Workspace Packages in package-lock.json

### Problem

Monorepo workspace packages (backend, frontend, packages/*) appear in `.packages` without `resolved` URLs:
```json
{
  "packages": {
    "": { ... },                    // Root package
    "backend": { ... },             // Workspace package (no resolved)
    "frontend": { ... },            // Workspace package (no resolved)
    "node_modules/@foo/bar": { ... } // Real dependency (has resolved)
  }
}
```

### Solution

Only check packages in `node_modules/`:
```bash
jq '.packages | to_entries[] | select(.key | startswith("node_modules/"))'
```

This excludes:
- Root package (key = "")
- Workspace packages (don't start with "node_modules/")

## Updated Workflow Template

### Hermetic Build Preflight (Recommended)

```yaml
- name: Validate lockfile for Hermeto/Cachi2 compatibility
  run: |
    echo "::group::Checking package-lock.json for unsupported protocols"
    # Check for protocols that Hermeto/Cachi2 cannot resolve
    UNSUPPORTED=$(grep -E '"resolved":\s*"(git\+|github:|file:)' package-lock.json || true)
    if [ -n "$UNSUPPORTED" ]; then
      echo "❌ FAIL: Found unsupported dependency protocols for hermetic builds:"
      echo "$UNSUPPORTED"
      echo ""
      echo "Hermeto/Cachi2 requires all dependencies to have HTTP/HTTPS URLs."
      echo "Replace git+, github:, and file: protocols with registry versions."
      exit 1
    fi
    echo "✅ PASS: No unsupported protocols found"
    echo "::endgroup::"

    echo "::group::Verifying all dependencies have resolved URLs"
    # Check only node_modules dependencies (skip workspace packages)
    MISSING_RESOLVED=$(jq -r '.packages | to_entries[] | select(.key | startswith("node_modules/")) | select(.value.resolved == null or .value.resolved == "") | .key' package-lock.json || true)
    if [ -n "$MISSING_RESOLVED" ]; then
      echo "❌ FAIL: Found dependencies without resolved URLs"
      echo "$MISSING_RESOLVED"
      exit 1
    fi
    echo "✅ PASS: All dependencies have resolved URLs"
    echo "::endgroup::"

# DO NOT include hermetic npm install test with --network=none
# It is unreliable and provides no additional value
```

## Issue: Module Federation remoteEntry.js validation for host frontend

### Problem

The workflow was checking for `remoteEntry.js` in the main frontend build output:
```bash
docker cp odh-dashboard-test:/usr/src/app/frontend/public ./dist-check

if [ ! -f "dist-check/remoteEntry.js" ]; then
  echo "❌ FAIL: remoteEntry.js not found"
  exit 1
fi
```

This **incorrectly assumes** that the host frontend always generates a `remoteEntry.js` file.

### Root Cause

In Module Federation architecture:
- **Remote packages** (like gen-ai, model-registry) generate `remoteEntry.js` to expose their modules
- **Host application** (main frontend) may or may not generate `remoteEntry.js` depending on configuration

Looking at `frontend/config/moduleFederation.js`:
```javascript
moduleFederationPlugins: mfConfig.length > 0
  ? [
      new ModuleFederationPlugin({
        name: 'host',
        filename: 'remoteEntry.js',
        exposes: {},  // Host doesn't expose anything
        // ...
      }),
    ]
  : [],
```

The ModuleFederationPlugin is **only added if `mfConfig.length > 0`** (i.e., if federated modules are discovered from workspace packages).

If no federated modules are detected (e.g., packages don't have `module-federation` in package.json), the plugin isn't loaded and no `remoteEntry.js` is generated.

### Why This Matters

The host frontend's `remoteEntry.js`:
- Is **optional** - only exists when federated modules are configured
- Has **empty `exposes: {}`** - the host doesn't expose modules
- Is **not critical for runtime** - the host consumes remotes, it doesn't serve as one

### Solution

**Make remoteEntry.js check optional, check for main bundle instead:**

```yaml
- name: Validate Module Federation artifacts
  run: |
    # Copy dist from container
    docker cp odh-dashboard-test:/usr/src/app/frontend/public ./dist-check

    # Check for main app bundle (always required)
    if [ ! -f "dist-check/app.bundle.js" ]; then
      echo "❌ FAIL: app.bundle.js not found - build did not complete"
      exit 1
    fi

    echo "✅ PASS: Main app bundle present"

    # Check for remoteEntry.js (optional - only generated if federated modules exist)
    if [ -f "dist-check/remoteEntry.js" ]; then
      SIZE=$(stat -f%z dist-check/remoteEntry.js 2>/dev/null || stat -c%s dist-check/remoteEntry.js)
      if [ "$SIZE" -lt 100 ]; then
        echo "❌ FAIL: remoteEntry.js is suspiciously small ($SIZE bytes)"
        exit 1
      fi

      echo "✅ PASS: remoteEntry.js present and valid ($SIZE bytes)"

      # Check for missing webpack chunks (only if remoteEntry exists)
      CHUNK_REFS=$(grep -o 'chunk[0-9]\+' dist-check/remoteEntry.js || true)
      # ... chunk validation ...
    else
      echo "ℹ️  INFO: No remoteEntry.js found (no federated modules configured)"
    fi
```

### Distinction: Host vs Remote Validation

- **Host frontend** (main dashboard):
  - `app.bundle.js` is **required** (main application code)
  - `remoteEntry.js` is **optional** (only if MF configured)
  
- **Remote packages** (gen-ai, model-registry):
  - `remoteEntry.js` is **required** (exposes modules to host)
  - Should be checked in package-specific validation

The skill's module validation code is correct - it checks remoteEntry.js for **remote packages**, which should have it.

The PR workflow was wrong - it checked remoteEntry.js for the **host**, which may not have it.

## Key Takeaways

1. **Don't use `docker run --network=none` for npm validation** - It crashes npm
2. **Lockfile validation with grep/jq is sufficient** - Catches the actual hermetic build issues
3. **Only check node_modules packages for resolved URLs** - Workspace packages don't have them
4. **Real validation happens in Docker build phase** - That's where actual hermetic issues surface
5. **Keep the preflight fast and reliable** - It should fail-fast on obvious issues, not test theoretical scenarios
6. **Host frontend remoteEntry.js is optional** - Only remote packages require it
7. **Check app.bundle.js instead** - This is always generated by the main frontend build

## Security Hardening Best Practices

The following security hardening patterns were implemented in the PR #7425 workflow after CodeRabbit AI review. These should be applied to all generated workflows.

### 1. Pin All GitHub Actions by Commit SHA

**Why:** Tags can be moved to point to different commits (CWE-494, CWE-829), allowing supply chain attacks.

**Pattern:**

```yaml
# Bad - uses mutable tag
- uses: actions/checkout@v4

# Good - pinned by commit SHA with comment
- uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.2.2
```

**Applied to:**
- `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5` # v4.2.2
- `actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020` # v4.2.0
- `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02` # v4.6.0
- `actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093` # v4.2.1

### 2. Least-Privilege Permissions Model

**Why:** Reduces blast radius if workflow is compromised. Never grant unnecessary permissions.

**Pattern:**

```yaml
jobs:
  my-job:
    permissions:
      contents: read        # Read-only access to repo
      actions: write        # Only for upload/download artifacts
    runs-on: ubuntu-latest
```

**Applied to all jobs:**
- `hermetic-preflight`: `contents: read`
- `docker-build-odh`: `contents: read, actions: write`
- `docker-build-rhoai`: `contents: read, actions: write`
- `runtime-validation-odh`: `contents: read, actions: read`
- `runtime-validation-rhoai`: `contents: read, actions: read`
- `operator-integration`: `contents: read, actions: read`
- `manifest-validation`: `contents: read`
- `summary`: `contents: read`

### 3. Strict Shell Error Handling

**Why:** Prevents silent failures, catches errors early, prevents use of undefined variables.

**Pattern:**

```yaml
- name: My step
  run: |
    set -euo pipefail  # ALWAYS first line
    # -e: exit on any error
    # -u: error on undefined variable
    # -o pipefail: pipe failures propagate
    
    # Your commands...
```

**Applied to all bash scripts in:**
- hermetic-preflight job (all steps)
- docker-build jobs (all steps)
- runtime-validation jobs (all steps)
- operator-integration job (all steps)
- manifest-validation job (all steps)
- summary job

### 4. Checksum Verification for Downloaded Binaries (Attempted but Removed)

**Why:** Prevents execution of tampered or corrupted binaries (supply chain security).

**Status:** ⚠️ **NOT IMPLEMENTED** - Attempted but caused CI failures with checksum mismatches.

**Lessons Learned:**
- Checksum verification is excellent security practice in theory
- In practice, it adds complexity and potential for breakage:
  * Checksums must be manually verified and updated
  * GitHub Actions runners may have caching/proxy issues
  * Difficult to debug checksum mismatches in CI
- For this workflow, the security benefits of pinned GitHub Actions provide the primary supply chain protection
- Binary downloads (websocat, Kind, kustomize) revert to simple curl + install

**Alternative Approach (if needed in future):**
- Use official installation scripts when available (e.g., kustomize install script)
- Download from trusted sources (github.com releases)
- Rely on HTTPS for transport security
- Pin specific versions in URLs when possible

**What was attempted:**
- websocat v1.12.0: SHA256 verification (failed in CI)
- Kind v0.20.0: SHA256 verification (failed in CI)
- Kustomize v5.3.0: SHA256 verification (never enabled)

**Final implementation:**
```yaml
# Simple approach - works reliably
- name: Install Kind
  run: |
    set -euo pipefail
    curl -Lo kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
    chmod +x kind
    sudo mv kind /usr/local/bin/
```

### 5. Improved Skip Conditions

**Why:** Allows both PR title and label-based skipping for better workflow control.

**Pattern:**

```yaml
if: "!contains(github.event.pull_request.title, '[skip konflux-sim]') && !contains(github.event.pull_request.labels.*.name, 'skip-konflux-sim')"
```

**Applied to all main jobs**

### 6. Optional Tool Dependencies with Fallback

**Why:** Makes workflows more resilient to environment differences, provides clear warnings.

**Pattern:**

```yaml
if command -v jq &> /dev/null; then
  # jq commands with proper validation
  MISSING=$(jq -r '.packages | ...' package-lock.json || true)
  if [ -n "$MISSING" ]; then
    echo "❌ FAIL: Validation failed"
    exit 1
  fi
else
  echo "⚠️  WARNING: jq not installed, skipping detailed validation"
fi
```

**Applied to:**
- jq dependency in hermetic-preflight job
- Workspace validation checks

### 7. Proper Timeout Handling and Readiness Probes

**Why:** Prevents infinite waits, detects failures early, provides useful debugging output.

**Pattern:**

```yaml
- name: Wait for service
  run: |
    set -euo pipefail
    READY=false
    for i in {1..30}; do
      if curl -f http://localhost:8080/api/health 2>/dev/null; then
        READY=true
        echo "✅ Health check passed after ${i} attempts"
        break
      fi
      sleep 2
    done
    
    if [ "$READY" = "false" ]; then
      echo "❌ FAIL: Service health check never succeeded"
      docker logs service-container 2>&1 || true
      exit 1
    fi
```

**Applied to:**
- Container startup validation
- API endpoint health checks
- Kubernetes deployment readiness

### 8. Proper Variable Quoting and Error Messages

**Why:** Prevents word splitting issues, improves debugging, provides actionable error messages.

**Pattern:**

```bash
# Always quote variables
if [ -n "$VARIABLE" ]; then
  echo "Processing ${VARIABLE}..."
fi

# Provide context in error messages
if ! some_command; then
  echo "❌ FAIL: Command failed at step X"
  echo "Expected: <expected state>"
  echo "Actual: <actual state>"
  exit 1
fi
```

**Applied throughout all bash scripts**

### 9. Correct API Endpoint Testing

**Why:** Test against real endpoints, not mock/placeholder paths.

**Pattern:**

```yaml
# Bad - test endpoint doesn't exist
curl -X PATCH http://localhost:8080/api/test-endpoint

# Good - test real endpoint
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X PATCH \
  -H "Content-Type: application/merge-patch+json" \
  -d '{}' \
  http://localhost:8080/api/config 2>/dev/null || echo "000")

if [ "$STATUS" = "200" ] || [ "$STATUS" = "204" ]; then
  echo "✅ PASS: API accepts merge-patch requests"
fi
```

**Applied to:**
- Merge-patch regression test

### Security Hardening Checklist for Generated Workflows

When generating new Konflux build simulation workflows, ensure:

- [ ] All GitHub Actions pinned by commit SHA with version comment
- [ ] Least-privilege permissions defined for each job
- [ ] `set -euo pipefail` in all bash scripts
- [ ] Skip conditions check both PR title and labels
- [ ] Optional tools have fallback messages
- [ ] Readiness probes with proper timeouts
- [ ] All variables quoted in bash scripts
- [ ] Error messages provide context and debugging info
- [ ] API tests use real endpoints, not placeholders
- [ ] Webpack chunk validation uses correct file patterns

**Note:** Checksum verification for downloaded binaries was attempted but removed due to CI failures. For supply chain security, rely on pinned GitHub Actions and HTTPS downloads from trusted sources.

## Issue: Operator-Integration in Vanilla Kind — Pods Cannot Become Ready

### Problem

The operator-integration workflow was attempting to wait for pods to become Ready after applying manifests to a vanilla Kind cluster:

```yaml
- name: Wait for deployment
  run: |
    set -euo pipefail
    kubectl wait --for=condition=Available \
      --timeout=300s \
      deployment/odh-dashboard \
      -n opendatahub
```

This step **always times out** because pods require OpenShift-specific resources that don't exist in vanilla Kind.

### Root Cause

Tested locally with Kind cluster to understand actual behavior:

1. **Deployment DOES get created** ✅
   - `kubectl apply -k manifests/odh -n opendatahub` succeeds
   - Deployment resource is created
   - Pods are created

2. **Pods CANNOT become Ready** ❌
   - Missing required secrets:
     * `dashboard-proxy-tls` (created by OpenShift Routes or cert-manager)
     * `odh-ca-cert` (injected by OpenShift CA bundle injector)
     * `odh-trusted-ca-cert` (injected by OpenShift)
   - Pod events show: `MountVolume.SetUp failed for volume "proxy-tls" : secret "dashboard-proxy-tls" not found`

3. **Resource constraints** ⚠️
   - Default Kind cluster has ~2Gi total memory
   - Deployment spec requests 2 replicas × 1Gi memory each
   - Result: One pod fails to schedule with `FailedScheduling: 0/1 nodes are available: 1 Insufficient memory`

### What Actually Works in Vanilla Kind

| Operation | Result |
|-----------|--------|
| Create namespace | ✅ Works |
| Apply CRDs | ✅ Works |
| Apply ConfigMaps | ✅ Works |
| Create Deployment | ✅ Works |
| Create Pods | ✅ Pods get created |
| Mount OpenShift secrets | ❌ Fails - secrets don't exist |
| Pods become Ready | ❌ Never happens |
| Wait for deployment Available | ❌ Times out |

### What the Workflow Should Validate

The operator-integration phase should verify that manifests are **structurally valid**, not that the full application becomes operational:

**✅ DO validate:**
- Namespace creation succeeds
- Manifests apply without errors
- Deployment resource is created
- CRDs are accepted by Kubernetes API
- No YAML syntax errors or invalid resource definitions

**❌ DO NOT validate:**
- Pods becoming Ready (requires OpenShift resources)
- Deployment becoming Available (requires Ready pods)
- Application functionality (requires full OpenShift platform)

### Solution

**Mock OpenShift resources and run containers with minimal resources:**

This approach simulates what Konflux actually does - it tries to run the containers.

```yaml
- name: Create mock OpenShift secrets
  run: |
    # Create dummy TLS secret (so volumes can mount)
    kubectl create secret tls dashboard-proxy-tls ...
    
    # Create dummy CA bundle configmaps
    kubectl create configmap odh-ca-cert ...
    kubectl create configmap odh-trusted-ca-cert ...

- name: Apply manifests
  run: |
    kubectl apply -k manifests/odh -n opendatahub

- name: Patch deployment for Kind resource constraints
  run: |
    # Reduce resource requests to fit in Kind's limited memory
    kubectl patch deployment odh-dashboard -n opendatahub --type=json -p='[
      {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "128Mi"},
      ...
    ]'
    
    # Reduce to 1 replica
    kubectl scale deployment odh-dashboard --replicas=1 -n opendatahub

- name: Wait for pods and validate container lifecycle
  run: |
    # Wait for pod creation and image pulls
    sleep 60
    
    # Check if containers started (even if they fail later)
    IMAGES_PULLED=$(kubectl get pods ... -o jsonpath='{.items[0].status.containerStatuses[*].imageID}')
    
    if [ "$IMAGES_PULLED" -eq 0 ]; then
      echo "❌ FAIL: No images were pulled"
      exit 1
    fi
    
    echo "✅ PASS: Containers attempted to start, images pulled successfully"
```

**Why this approach:**
- ✅ **Validates images load into Kind** - Catches image pull errors, invalid image specs
- ✅ **Validates container specs** - Catches invalid args, missing env vars, bad probes
- ✅ **Validates volume mounts** - Mock secrets allow containers to at least attempt mounting
- ✅ **Simulates Konflux behavior** - Konflux actually runs containers, not just applies YAML
- ✅ **Works with Kind's constraints** - Reduced resources fit in limited memory
- ⚠️  Containers may crash (missing OpenShift APIs), but that's expected - we validated the important parts

**What this catches that YAML-only validation misses:**
- Invalid container image references
- Bad entrypoint/command configurations
- Missing required environment variables
- Invalid volume mount configurations
- Resource specification errors
- Init container failures

**Dashboard-specific note:**
ODH Dashboard has many containers (odh-dashboard, kube-rbac-proxy, model-registry-ui, gen-ai-ui, etc.), so resource patching is critical. Most components will have simpler deployments and may not need as aggressive resource reduction.

### Test Results

**Without mock secrets (initial test):**
- ✅ Namespace creation: Success
- ✅ Manifest application: Success
- ✅ Deployment created: Success
- ✅ Pods created: Success
- ❌ Pod Ready state: Failed (missing secrets, insufficient memory)
- ❌ Deployment Available: Never achieved

**With mock secrets and reduced resources (final solution):**
- ✅ Namespace creation: Success
- ✅ Manifest application: Success
- ✅ Mock TLS secret created: Success
- ✅ Mock CA configmaps created: Success
- ✅ Deployment patched for reduced resources: Success (128Mi per container, 1 replica)
- ✅ Pod scheduled: Success (after old pod deleted)
- ✅ **All 9 containers running: Success**
  * odh-dashboard (main frontend)
  * kube-rbac-proxy
  * model-registry-ui
  * gen-ai-ui
  * maas-ui
  * mlflow-ui
  * eval-hub-ui
  * automl-ui
  * autorag-ui
- ✅ **All 9 images pulled successfully**: Success
- ✅ Containers started and stay running: Success
- ⚠️  Application readiness probes may fail (missing OpenShift APIs) - but containers are running

### Key Takeaway

**Vanilla Kind can validate manifest structure, NOT application readiness.**

The operator-integration phase is about catching **manifest errors** (invalid YAML, wrong API versions, malformed specs), not about validating that the full ODH Dashboard application runs. Full runtime validation requires an actual OpenShift cluster with all platform components.

## Issue: Operator reconcile smoke test — image clobber, silent rollout failures, and missing overlays

Source: odh-dashboard PR #9658 review (reviewer @antowaddle). The workflow was extended
with an operator build, a `Dashboard` CR reconcile smoke test, and kubeconform validation.
Six issues surfaced that generalize to any controller-runtime operator repo.

### 1. Server-side apply reverts your pre-patched image — pin it on the operator instead

When the operator reconciles a CR, it **server-side-applies** its base manifests as a
named field owner. The typical merge strategy preserves only `spec.replicas` and
`containers[].resources` — **not** `image` or `imagePullPolicy`. So the common trick of
pre-patching the workload Deployment to the loaded PR tag / `imagePullPolicy: Never` is
silently reverted on the very next reconcile, and the node begins pulling the operator's
baked-in default image (e.g. `quay.io/opendatahub/odh-dashboard:main`) mid-poll.

**Fix:** don't patch the workload — point the *operator* at the already-loaded PR image via
its image-resolution env (odh-dashboard: `RELATED_IMAGE_ODH_DASHBOARD_IMAGE=odh-dashboard:odh-test`).
Then the operator itself SSA-applies the PR tag, the "we're testing the PR image" invariant
holds, and no `:main` network pull happens. The reconciled pod may sit in `ErrImagePull` on
the local-only tag — benign, because this phase asserts on reconcile evidence, not pod
readiness (see #4).

### 2. Rollout failures must dump diagnostics inline

`kubectl rollout status ... --timeout=Ns` under `set -e` aborts the step on timeout; any
`::group::logs` dump in a *later* step never runs. Controller panics and scheme/registration
errors then surface as a bare `timed out waiting for the condition`. Wrap the rollout in
`if ! kubectl rollout status ...; then <describe + get pods + logs + logs --previous +
events>; exit 1; fi` so it's diagnosable in the same step. (Same lesson as
"Proper Timeout Handling" above, applied to the operator Deployment.)

### 3. Extract inline manifests to checked-in files

Operator `Deployment` / `ServiceAccount` / `ClusterRoleBinding` heredocs
(`kubectl apply -f - <<EOF`) are unreviewable, unlintable, and untestable. Move sim-only
specs to a dedicated dir **outside** `manifests/` (e.g. `.github/pr-build-simulation/`) so
overlay validation never picks them up or ships them, and `kubectl apply -f` them. Bind the
operator's **real** ClusterRole (`config/rbac/role.yaml`) rather than a hand-copied subset,
so the smoke test exercises shipped RBAC.

### 4. Assert on reconcile evidence, not pod readiness

Extends the "Vanilla Kind can't make pods Ready" learning above. For a controller-runtime
operator, the *right* assertion is that the controller completed a reconcile loop without
crashing: poll the CR for the operator's finalizer and for
`status.observedGeneration == metadata.generation`, and assert the operator pod has `0`
restarts. That works in vanilla Kind even though the app pod never becomes Ready.

### 5. Free disk space when loading multiple images

The operator-integration job loads *two* images (app + operator) into Kind. Without a
`free-disk-space` step (which the docker-build jobs already have) the runner can hit ENOSPC
during image load or pull, producing confusing failures. Add
`uses: ./.github/actions/free-disk-space` to any multi-image job.

### 6. `-ignore-missing-schemas` masks kind typos; validate the overlays the operator renders

- **Typo masking:** `kubeconform -ignore-missing-schemas` counts a misspelled built-in kind
  (`Deploymnet`) as "no schema found," exit 0. Instead of asserting a raw skip *count*
  (churns as CRDs are added), run `-output json` and **fail if any skipped resource is a
  Kubernetes built-in** — group `""` (core), `*.k8s.io`, or `apps`/`batch`/`policy`/
  `autoscaling`/`extensions`. CRD-backed kinds stay allowed to skip.
- **Overlay coverage:** `find manifests -name kustomization.yaml` misses paths the operator
  renders at runtime. Enumerate them from the operator's Go source and add **dynamic module
  discovery** (`find manifests/modules -mindepth 2 -maxdepth 2 -name kustomization.yaml`) so
  new modules are covered automatically. A broken `resources:` path in a module overlay
  otherwise passes "Manifest Validation" and fails only on a live cluster. (odh-dashboard:
  the operator renders `manifests/{base,odh,rhoai}`, `manifests/observability/{odh,rhoai}`,
  `manifests/maas-consumer-portal-consolelink/rhoai`, and each `manifests/modules/<slug>` —
  note `manifests/distributions/maas-consumer-portal` is a stale path that does not exist.)

### Key Takeaway

For controller-runtime operators, the reconcile smoke test must (a) let the *operator* own
the image via its resolution env, (b) fail loud with inline diagnostics, (c) keep sim
manifests in reviewable files, (d) assert on reconcile evidence, and (e) validate every
overlay the operator actually renders — with schema checks that don't let typos slip through.

## Issue: Porting the simulator to a Go + Python repo (model-registry)

Onboarding `opendatahub-io/model-registry` exposed several places where the skill
was Node-shaped. These are the generalized fixes; all were validated by running
the generated simulator end to end.

### 1. `--network=none` cannot populate the cache it needs

The npm lesson generalizes to every package manager: a single build with the
network disabled cannot fetch the dependency set it is supposed to use. For Go
and Python, split the work into two phases on the host:

1. Network phase: `GOMODCACHE=<tmp> go mod download`, or
   `pip download -r requirements.txt -d <wheelhouse>`.
2. Offline phase: `GOPROXY=off ... go build`, or
   `pip install --dry-run --no-index --find-links <wheelhouse>`.

The offline phase is the actual hermetic proof: a dependency that Hermeto would
not prefetch fails immediately instead of in Konflux.

### 2. Go module cache files are read-only

`rm -rf` on the temporary `GOMODCACHE` fails on macOS with
`rm: ... Permission denied` because the module cache is written read-only. The
cleanup trap must chmod first:

```bash
trap 'chmod -R u+w "$workdir" 2>/dev/null || true; rm -rf "$workdir"' EXIT
```

### 3. `GOTOOLCHAIN=auto` downloads the toolchain into `GOMODCACHE`

When `go.mod` requires a newer Go than the host has, `go mod download` fetches
the toolchain into the isolated module cache. That is desirable: the offline
phase then succeeds only because the toolchain was prefetched, which mirrors the
hermetic build. Keep `GOTOOLCHAIN=auto` and populate the cache before going
offline.

### 4. PEP 668 blocks `pip install --dry-run`

Homebrew and Debian mark their Python as externally managed, so even a dry run
fails with `externally-managed-environment`. Run the offline resolution with a
venv's pip:

```bash
python3 -m venv "$workdir/venv"
"$workdir/venv/bin/python" -m pip install --dry-run --no-index \
  --find-links "$wheelhouse" -r requirements.txt
```

### 5. Prove the shipped target, not `./...`

Go entry points and flags in the Dockerfile are the contract. Build the same
package with the same `CGO_ENABLED`, `GOOS`, and tags (for example
`CGO_ENABLED=0 GOOS=linux go build -buildvcs=false -o app .`). Building `./...`
does not prove the binary links, and omitting `GOOS=linux` hides
platform-specific files when the simulator runs on macOS.

### 6. A pipeline named `multi-arch-*` is not automatically multi-arch

model-registry's PipelineRun resolves
`odh-konflux-central/pipeline/multi-arch-container-build.yaml`. That pipeline
defaults `build-platforms` to `linux/x86_64`, `hermetic` to `false`, and
`prefetch-input` to empty because the PipelineRun does not override them. Resolve
the `pipelineRef` and read its defaults before choosing the CI platform or
claiming a build is hermetic.

### 7. Simulate only what Konflux builds from PRs

The repo contains controller, CSI, testops, and UI Dockerfiles, but only two
images are built by `.tekton/*pull-request.yaml`. Adding the rest duplicates
coverage that other workflows already provide (Kind deployment, unit tests) and
creates jobs that can drift from what Konflux actually validates. Derive the
target list from the PipelineRuns, not from `find . -name Dockerfile`.

### 8. Interpolating PR titles into `run:` is a script-injection vector

`${{ github.event.pull_request.title }}` is attacker-controlled. Pass it through
`env:` and test it in bash. Evaluate the skip rule once in a `check-skip` job so
every job cannot drift, and include `workflow_dispatch` as an explicit override.

### 9. Make the summary job the only required check

A `summary` job with `if: always()` that fails unless every dependency is
`success` or `skipped` gives branch protection one stable check name. GitHub
treats a skipped required check as passing, so an intentional
`[skip konflux-sim]` run does not block merge.

## Issue: Detecting the operator consumer, not the operator repo

Onboarding `opendatahub-io/model-registry` produced a simulator with every phase
except operator integration, and it looked deliberate: the repo has no `controllers/` and no
`config/crd/`, so "Go service / Python job" seemed right. It was not. The image
is shipped entirely by an operator in another repository, so the shipping path
was untested end to end.

### The detection bug

The skill keyed operator integration on repo layout — "does this repo contain a controller?".
That is a proxy for the real question, which is "what consumes the artifacts this
repo builds?". The two disagree whenever a service is deployed by an external
operator, which is the normal shape for component repos in ODH:

- `opendatahub-operator/manifests-config.yaml` maps component `aihub` →
  `opendatahub-io/model-registry-operator@<ref>`, `sourcePath: config`.
- That operator resolves the server image from
  `RELATED_IMAGE_ODH_MODEL_REGISTRY_IMAGE`
  (`internal/controller/config/defaults.go`), not from the Deployment spec.

Detection that works:

```bash
gh search code "<image-name>" --filename=manifests-config.yaml --limit 10
gh search code "RELATED_IMAGE_" --repo <org>/<candidate-operator> --limit 10
```

If any operator names the image, operator integration applies — against that operator, pinned
to a commit.

### The bug this would have caught

`model-registry/.github/workflows/build-image-pr.yml` did deploy
`model-registry-operator` into Kind on every PR, and it looked like operator
coverage. It ran:

```bash
kubectl set env -n model-registry-operator-system \
  deployment/model-registry-operator-controller-manager REST_IMAGE="${IMG}"
```

`REST_IMAGE` is not read anywhere in the operator. The real variable is
`RELATED_IMAGE_ODH_MODEL_REGISTRY_IMAGE`. So for as long as that workflow has
existed it has been testing `quay.io/opendatahub/model-registry:latest`, not the
image it just built — and passing.

Two lessons:

1. **Never infer the image-override variable name.** Grep the operator source for
   the constant it reads. A wrong name fails silently, because the operator falls
   back to its embedded default.
2. **Assert the rendered image.** `kubectl get deployment/<workload> -o jsonpath='{.spec.template.spec.containers[0].image}'`
   must equal the PR tag before any other assertion runs. Without it, "operator
   integration passed" means nothing.

An existing operator workflow is also not evidence that the right thing is being
tested. Read what it pins.

### External-operator phase shape

```bash
kubectl apply -k "https://github.com/<org>/<operator>.git/config/default?ref=<sha>"
kubectl -n <operator-ns> set env deployment/<operator-deploy> \
  RELATED_IMAGE_<COMPONENT>_IMAGE="$SERVER_IMAGE"
kubectl -n <operator-ns> rollout status deployment/<operator-deploy> --timeout=300s
kubectl apply -k "https://github.com/<org>/<operator>.git/config/samples/<sample>?ref=<sha>"
kubectl wait --for=condition=Available <crd>/<name> --timeout=300s
```

Assert: rendered image equals the PR tag, finalizer present, `restartCount == 0`.
Reuse the image built by the container phase (artifact upload/download) instead
of rebuilding, so the operator reconciles the bytes that were just tested.

### Select the rendered workload by label, not by name

Operators usually name the workload after the CR (`modelregistry-sample`), not
after the component (`model-registry`). A hardcoded
`kubectl get deployment/model-registry` therefore fails *after* a successful
reconcile, which reads like a reconcile failure and sends you debugging the
operator.

Select by a label the operator's template actually sets, and use the same
selector for the restart count so it cannot quietly match zero pods:

```bash
kubectl get deployment -l component=model-registry \
  -o jsonpath='{.items[0].spec.template.spec.containers[0].image}'
kubectl wait --for=condition=Available deployment -l component=model-registry
kubectl get pods -l component=model-registry \
  -o jsonpath='{range .items[*]}{range .status.containerStatuses[*]}{.restartCount}{"\n"}{end}{end}'
```

Check the template for the label instead of assuming the pod and Deployment
share every key: `deployment.yaml.tmpl` in model-registry-operator puts
`component: model-registry` on both, but only the Deployment carries
`app.kubernetes.io/component`.

### Where this still stops

An external-operator phase proves the component's operator can ship the image. It
does **not** reach the RHOAI platform operator, so `DataScienceCluster` component
conditions, `Managed`/`Unmanaged` transitions, and operator-rendered manifest
paths (RHOAIENG-103141, 103140, 99568) remain out of scope. Those assertions
already exist in `opendatahub-operator/tests/e2e/aihub_test.go`; the gap is that
they are excluded from the Kind E2E (`E2E_TEST_COMPONENT="kserve"` is hardcoded
in `make e2e-test-xks`) and only run in the OpenShift suite.

## Issue: Coverage that exists but is never invoked

Before writing platform-operator tests from scratch, check whether they already
exist upstream and are only filtered out.

For model-registry, `opendatahub-operator/tests/e2e/aihub_test.go` already
asserts exactly the `DataScienceCluster` behaviour the Jira tickets describe:

- `spec.components.modelregistry.managementState` Removed → Managed
- `status.components.modelregistry.registriesNamespace`
- `status.conditions[] | select(.type == "ModelRegistryReady") | .status == "True"`

The suite is registered in the `Components` TestGroup
(`tests/e2e/controller_test.go`, `componentApi.AIHubModuleName`), and `--tag`
defaults to `All`, so it is not tier-skipped. It never runs on Kind because
`make e2e-test-xks` hardcodes:

```make
-e E2E_TEST_COMPONENT="kserve"
```

Enabling it is two edits, not a new test suite:

1. `Makefile` → `E2E_TEST_COMPONENT="kserve,aihub"`
2. `.github/workflows/test-kind-odh-e2e.yaml` → add the component's paths to
   `paths:` (`internal/controller/modules/aihub/**`,
   `api/components/v1alpha1/aihub_types.go`, `tests/e2e/aihub_test.go`,
   `config/overlays/aihub/**`)

Nothing else is needed. The operator image already bundles `opt/manifests/aihub`
because `Dockerfiles/Dockerfile` runs `manifest-tools download` for every entry
in `manifests-config.yaml`, and the aihub handler renders
`aihub-controller-manager` from `overlays/aihub`.

### Generalize: ask three questions in order

1. Does the platform operator already have a suite for this component?
2. Is that suite registered in the component `TestGroup`?
3. Does the Kind target include the component in `E2E_TEST_COMPONENT`?

New coverage work is only needed when (1) is false. When (3) is false, the fix
is one Makefile line plus path filters — and it is worth more than any amount of
component-repo simulation, because it exercises the actual DSC reconcile loop.

## Issue: Workflow correctness lessons from the model-registry onboarding review

These came from CodeRabbit review of the generated workflow and from CI runs.
Each one is a silent green check if left unfixed.

### 1. Workflow-level `paths:` can strand a required status check

If an administrator makes the summary job required, a workflow-level `paths:`
filter prevents the workflow from starting for out-of-scope PRs, so the
required check stays **pending** and the PR cannot merge. Remove `paths:` from
the trigger and evaluate changed files inside the gate job, then let the
summary report an explicit out-of-scope success.

### 2. A summary job must not treat skipped validations as success

When the gate job fails before writing its output, every dependent job becomes
`skipped`, and `if: always()` lets the summary run. Accepting `skipped` then
reports success without running anything. Require `needs.check-skip.result ==
'success'`, and only accept skipped validation jobs when the gate explicitly
set `skip=true`.

### 3. Metadata triggers plus `cancel-in-progress` cancel real builds

Adding `edited`, `labeled`, and `unlabeled` lets the skip decision re-evaluate,
but with `cancel-in-progress: true` every bot-applied label aborts an in-flight
image build and the summary correctly reports `cancelled`. Cancel only on new
commits:

```yaml
cancel-in-progress: ${{ github.event.action == 'synchronize' }}
```

### 4. kubeconform `statusError` is fail-open

kubeconform v0.7.0 emits `statusError` when schema retrieval fails. Filtering
only `statusInvalid` and swallowing the exit status reports success when
validation never ran. Treat `statusError` and unparseable JSON as failures.

### 5. EXIT traps cannot see function-local variables

`trap cleanup EXIT` inside a function keeps running after the function
returns, when `local` variables are out of scope; under `set -u` cleanup dies
with `unbound variable` and leaves containers behind. Define the validation
function with a subshell body so the trap fires before the subshell exits:

```bash
validate_server() (
  local name="..."
  trap 'docker rm -f "$name"' EXIT
  ...
)
```

### 6. Generate disposable credentials instead of hardcoding them

Even a throwaway Postgres password trips secret scanners and the shell rule
against hardcoded credentials. Generate one per run and use it for both
`POSTGRES_PASSWORD` and the DSN.

### 7. Resolve remote `replace` directives before checking `go.sum`

`replace example.org/lib => example.org/fork v1.1.0` makes Go record the
fork's checksum, not the original module's. A naïve require/go.sum check then
rejects a valid dependency update. Resolve remote replacements first; skip
local replacements and verify the target path instead.

## Why image-level checks matter: Jira evidence from model-registry

- **RHOAIENG-63943**: the async-upload image crashed at startup because the
  `model_signing` package was missing, while the build itself was green. An
  image-level `import job.entrypoint` check catches exactly this class of
  broken wheel.
- **RHOAIENG-64763**: asked for early detection of async-upload hermetic build
  issues, local/CI triggering before merge, and sanity imports of Python
  packages. Closed as Won't Do; a PR-time simulator is the practical
  implementation of the first two asks.
- **RHOAIENG-66101 / 66102**: Conforma `hermetic_task.hermetic` exception for
  `odh-model-registry-job-async-upload-v3-4`, showing dependency prefetch
  completeness needs a PR-time check.

### Scope boundary: build simulation does not catch DSC/operator issues

The model-registry DSC backlog is dominated by operator-level failures:
`test_mr_condition_in_dsc` (ModelRegistry condition False), `test_mr_management_state`,
`test_data_science_cluster_healthy`, and operator manifest path mismatches
(RHOAIENG-99568). A build simulator that runs the container standalone cannot
reproduce DSC reconciliation, RBAC/SCC, or operator-rendered manifests. State
that limitation explicitly; operator integration needs the Kind phase, not a
bigger Docker run.

## Learning: A green check that never ran is worse than no check

Four separate ways the generated workflow reported success without validating
anything, all found in review of the model-registry PR. They are cheap to get
wrong and expensive to notice, because the failure mode is *green*.

### 1. `!` on a pipeline under `pipefail` inverts the wrong failure

```bash
# Wrong
if ! git diff --name-only "origin/${BASE_REF}...HEAD" | grep -Eq "$RELEVANT"; then
  echo "should-skip=true" >> "$GITHUB_OUTPUT"
fi
```

`grep -q` exits at its first match and closes the pipe. `git diff` then dies on
`SIGPIPE`, `pipefail` reports the pipeline as failed, and `!` turns that into
"no relevant files changed". The run skips every validation job and the summary
passes. Capture first, match second:

```bash
changed_files="$(git diff --name-only "origin/${BASE_REF}...HEAD")" || exit 1
grep -Eq "$RELEVANT" <<< "$changed_files" || echo "should-skip=true" >> "$GITHUB_OUTPUT"
```

### 2. A skip gate without declared `outputs:` guards nothing

`needs.check-skip.outputs.should-skip` expands to the empty string unless the
job declares `outputs:`. `'' != 'true'` is true, so every consumer job runs
while *looking* guarded. The declaration is easy to drop when you copy the job
into a new workflow.

### 3. `skipped` counts as success for a required check

GitHub treats a skipped job as passing. So `if: ${{ env.HAS_MANIFESTS == 'true' }}`
on a job where the env var is never set produces a green required check that
never executes. The summary has to know which results are legitimate: when
`should-skip` is `false`, require `success`; when it is `true`, require
`skipped`. Checking only for `failure` misses this entirely.

### 4. `workflow_dispatch` has no `pull_request` payload

`github.event.pull_request.title` is `null` on a manual run. Any guard built
from it matches nothing, so either the run proceeds without the skip logic or
the expression errors. Branch on `github.event_name` first.

## Learning: Cluster ownership and context in the operator phase

The Kind phase is written to be run locally as well as in CI, and the two
environments differ in the ways that matter.

- **Never delete a cluster you did not create.** `KIND_CLUSTER_NAME` lets a
  developer point the script at an existing cluster. If the reuse branch accepts
  it and the `EXIT` trap calls `kind delete` unconditionally, a failed run wipes
  their working environment. Set `created_cluster=true` only after a successful
  `kind create`, and gate the delete on it.
- **Pass `--context` on every `kubectl` call.** Reuse does not switch context.
  The operator then installs into whatever cluster the developer was last using
  — and the diagnostics that dump state read the wrong cluster too, so the
  failure is misdiagnosed. In CI this is invisible, because the context already
  happens to be `kind-<name>`.
- **`Available` does not mean your pod is running.** After `kubectl set env` the
  old ReplicaSet still satisfies `Available` while the new pod is stuck. A
  workflow that waits on `Available` and then asserts the *deployment spec*
  image will pass while testing the old image. `rollout status` first, then
  compare the running container image and confirm the pod UID changed.
- **`Available` can also precede the operator's own rollover.** When the
  operator starts on `:latest` and switches to the PR image once
  `RELATED_IMAGE_*` reaches it, the workload Deployment rolls over *after* it
  reports `Available`. A stability snapshot taken at that point legitimately
  sees the old pod disappear and reports it as instability:

  ```
  ❌ Model Registry changed after becoming Available:
  pod fd732b58-... container rest-container disappeared
  ```

  Wait on `rollout status` for the workload before snapshotting, and exclude
  pods carrying a `deletionTimestamp` so a superseded ReplicaSet cannot read
  as a restart or a disappearance. The check is right to be strict; it just has
  to observe the steady state rather than the transition.
- **Do not sum restart counts across pods.** Two restarts on pod A and one on
  its replacement B total `1`, which reads as healthy. `END {print total + 0}`
  also makes an empty pod list read as `0`. Key counts by pod UID and container
  name, fail on any increase, and fail on an empty list.

## Learning: `//` in kustomize remote URLs is required grammar, not a live bug

A review comment insisted `kubectl apply -k` fails without the double slash:

```
https://github.com/<org>/<repo>.git/config/default?ref=<sha>    # single
https://github.com/<org>/<repo>.git//config/default?ref=<sha>   # double
```

Tested both against a pinned ref while addressing the review:

```
OK   []   config/default      -> 12 objects
OK   [//] config/default      -> 12 objects
OK   []   config/samples/mysql -> 5 objects
OK   [//] config/samples/mysql -> 5 objects
```

Current `kubectl` accepts both, and the model-registry workflow had already been
passing in CI using the single-slash form. Use `//` anyway: it is the documented
separator between repository and in-repo path, and it states the boundary
explicitly instead of relying on inference that the grammar does not require.
State the evidence when you change it, so the next reader does not "fix" it
back after seeing a green run.

## Learning: Find the Jira component before claiming there is no history

Searching Jira for `component = "Model Registry"` returns nothing. The
model-registry work lives under `AI Hub`. An empty result is much more likely to
mean the wrong component than a component with no failures, so search the repo
name, the operator's component key, and the product-facing name, and keep the
one that returns issues.

QE test names are the highest-signal search key, because they name the assertion
that broke: `test_mr_condition_in_dsc`, `test_mr_management_state`,
`test_mr_pods_health`, `test_data_science_cluster_healthy`. Searching by those
recovers tickets that share no vocabulary with the repository.

### Worked example: what the model-registry tickets actually split into

| Ticket | Failing test | Class | Catchable by this skill |
|---|---|---|---|
| RHOAIENG-63943 | async-upload smoke | Build-time | Yes — Python `--no-index` resolve |
| RHOAIENG-64763 | (prevention request) | Build-time | Yes — this is the skill's premise |
| RHOAIENG-66101 / 66102 | Conforma `hermetic_task.hermetic` | Build-time | Yes — wheelhouse completeness |
| RHOAIENG-99568 | DSC never Ready | Packaging / render | Yes — manifest path contract check |
| RHOAIENG-103141 | `test_mr_condition_in_dsc` | Reconcile | No — operator e2e |
| RHOAIENG-103140 | `test_mr_management_state` | Reconcile | No — operator e2e |
| RHOAIENG-103668 / 103521 | `test_mr_pods_health` | Reconcile | No — operator e2e |
| RHOAIENG-103763 / 103636 / 103313 | `test_data_science_cluster_healthy` | Reconcile | No — operator e2e |

The lower half is the reason the operator handoff exists. A container that
starts cleanly says nothing about whether the operator can render it, and the
first model-registry onboarding looked complete while every one of those was
still failing.

## Learning: Fault injection is the only evidence a check works

"This assertion would have caught it" is a hypothesis. Break the thing on a
throwaway branch and watch the assertion fail; that is evidence. Then revert and
confirm it passes, which proves the positive path too. Quote the actual failing
line in the PR — a reviewer cannot distinguish a real red test from a claim
without it, and a check that has never been seen to fail has never been tested.

Keep the injection out of the PR, and do not generalise: one injection proves
that assertion fires for that failure mode, not that the stage covers the class.

## Learning: `pip` cannot prove a Python hermetic build, `uv` can

The model-registry onboarding used `pip download` into a wheelhouse and then
`pip install --no-index --find-links`. That worked for a small graph and does not
generalise. On feast's feature-server requirements pip aborts with
`resolution-too-deep`; its fallback then tries to build `psycopg-c` from source,
which needs `pg_config` that the runner does not have. `ast-serialize==0.13.1`
also publishes no `cp312` manylinux wheel, so an `--only-binary` pass finds
nothing.

`uv pip compile` resolves the same file to 186 pinned distributions in seconds,
for `x86_64-manylinux_2_34` / Python 3.12. Two details make the proof real:

- Resolve for the **build** platform (`--python-version`, `--python-platform`),
  never the runner's.
- Delete the venv between the warm install and the `--offline` install. If the
  venv survives, the offline pass can satisfy itself from installed packages and
  the check is vacuous.

If the Dockerfile installs with `uv`, the preflight must too — otherwise it
validates a different resolution than the one that ships.

## Learning: a rendered manifest is not a runnable container

Feast's recurring downstream failure was not a bad overlay and not a bad image;
it was the seam between them. RHOAIENG-100779 shipped a RHOAI overlay passing
`--metrics-cert-path` to an operand image that did not define the flag. The
container exited during flag parsing, `default-feastoperator` stayed `Not
Ready`, and both `kustomize build` and `kubeconform` were perfectly happy.
RHOAIENG-57579 was the same seam: a duplicated `RELATED_IMAGE_CRON_JOB` env var,
where the API server silently keeps the last value.

Neither needs a cluster to detect:

- render the overlays the operator ships;
- for the controller-manager Deployment, collect `command` + `args` flag *names*
  (never values, and never flags from operand containers);
- build the operator image and diff against `--help`;
- reject any container that repeats an env var name.

Fail closed when `--help` is empty, or every comparison passes trivially.

This only works when the binary and the overlay come from the same commit. A new
overlay shipped against an older published operand image is the cross-repo case
and belongs in the platform handoff, not here.

## Worked example: feast (three Konflux targets, one repo)

`opendatahub-io/feast` builds three images from `.tekton/*pull-request.yaml`:
`feature-server`, `feast-operator` (context `infra/feast-operator`), and
`odh-feast-mcp`. Each needed a different check, which is the point — "the repo
is a Python repo" was not a useful level of analysis.

The highest-value assertion was the cheapest: the feature-server Dockerfile
`COPY`s `sdk/python/feast` over the installed package. If that overlay regresses,
the image silently ships PyPI feast instead of the PR's code. That is not
hypothetical — RHOAIENG-81940 / 81941 / 81942 are the same bug on three
branches.

**Jira mining paid for itself, but the raw count misleads.** `text ~ feast`
returned 564 bugs; 252 of them (45%) are Snyk CVE tickets against kserve sample
Dockerfiles that merely mention feast. Filter by mechanism, not by count.
Seventeen tickets had a mechanism this simulator reproduces; the rest were
reconciliation, bundle, or NetworkPolicy failures that need a cluster.

**The operator was the missing phase.** The repo's own operator e2e builds
from source, so the published operator image was untested; see "a source-built
operator suite cannot test the image under test" below.

**Fork PRs cannot run Konflux.** The three Konflux status checks fail in ~1 second
on a fork PR — that is admission denial when the PipelineRun is created, not a
build failure, and it is not related to the change. Say so in the PR so a
reviewer does not go looking for a code problem.

**PR title lint.** feast runs commitlint with `subject-case: sentence-case`;
`ci: add ...` fails, `ci: Add ...` passes.

**Tell your failures from theirs.** The feast unit suite failed on exactly one
test in each of two runs, a different one each time
(`test_wait_for_index_ready_timeout`, then
`test_apply_stream_source_from_repo`), with 4,553 and 4,564 passing. The same
commit passed on the other matrix legs. A single unrelated failure that moves
between runs is flake, not regression — compare the same suite on a sibling
matrix leg before spending time on it, and say so in the PR. External
contributors cannot re-run jobs, so a maintainer has to clear it.

## Learning: a source-built operator suite cannot test the image under test

feast ships an operator e2e suite that deploys a real operator into a real Kind
cluster, which reads like full operator coverage. It calls
`utils.DeployOperatorFromCode(...)`, which runs `make docker-build` in the test
and loads that image. The PipelineRun's Containerfile is never involved, so a
broken entrypoint, a missing binary, or a bad environment contract in the
published image is invisible to it.

The suite was also label-gated (`ok-to-test` / `approved` / `lgtm`) and filtered
to `paths: infra/**`, so it did not run on most PRs even to do the source-built
version.

### The phase that closes it

1. Build both images from PipelineRun inputs — operator `Dockerfile` with
   context `infra/feast-operator`, operand Dockerfile with context `.` — and
   `kind load docker-image` each one, so nothing is pulled from a registry.
2. `make install`, then `make deploy IMG=<operator> FS_IMG=<operand>`; the
   Makefile's `related-image-fs` target is what carries the operand image into
   the operator's env.
3. `kubectl wait --for=condition=Available deployment/<name>`. "Created" is not
   "runnable": a crash-looping container satisfies the object existing.
4. Assert the running Deployment's image equals the one you built. This catches
   a stale tag or a default that overrode your flag.
5. Apply a minimal CR, wait for the operand, then assert an operand pod runs the
   built image — that is what proves reconcile happened *and* used the PR image.
6. Dump operator logs, operand pods and events before deleting the cluster.

### `kubectl wait --all` errors on an empty set

`kubectl wait --for=condition=Available deployment --all -n <ns>` returns
`error: no matching resources found` when nothing matches — which is exactly the
state right after applying a CR, before the operator has reconciled. The first
run of the feast phase failed here after reconciling correctly, and the error
reads like a reconcile failure if you only read the last line.

Poll until `kubectl get deployment -o name` is non-empty, then wait:

```bash
while [ -z "$(kubectl -n "$NS" get deployment -o name)" ]; do sleep 5; done
kubectl -n "$NS" wait --for=condition=Available deployment --all --timeout=10m
```

### Ungating a suite surfaces its unpaid flakes

Removing the label gate is one line, but budget for the suite being red. The
first unlabelled feast run passed `Should be able to deploy and run a
TestSimpleFeastCR` and failed `TestRemoteRegistryFeastCR` — the remote-setup
Deployment never became Available in three minutes — on a PR that changed no
operator code. A suite that only runs when a maintainer asks for it has never
had its timing assumptions tested against a loaded runner. Report it as a
finding, do not "fix" it by re-adding the gate.

## Worked example: feast-module-operator (generated chart and RBAC identity)

`feast-module-operator` builds one image and ships the operand manifests inside
it. It is the smallest repo this skill has been run against, and it still had
two contract failures that no compiler, linter, or `go test` can see.

### The generated chart is not verified anywhere

`config/chart` is generated by `make helm` from `config/default`, and it is the
path `opendatahub-operator` consumes through `manifests-config.yaml`
(`sourcePath: config/chart`). `ci.yaml` runs four jobs plus `docker-build`;
`Verify Generated Files` runs `make manifests generate`, which covers CRDs and
deepcopy code and nothing else. **No job runs `make helm`.**

Running it on a clean `git archive HEAD` of `main` changes three files:

- `config/chart/values.yaml` — committed
  `quay.io/opendatahub/odh-feast-module-operator:odh-stable`, regenerated
  `ttl.sh/opendatahub-feast-operator:latest` (from
  `config/manager/kustomization.yaml`)
- `config/chart/templates/networking.k8s.io_v1_networkpolicy.yaml` — committed
  `opendatahub-feast-allow-egress` / `{{ .Values.namespace }}`, regenerated
  `allow-egress` / `{{ default .Release.Namespace .Values.namespace }}`
- `config/chart/templates/upgrade-gates.yaml` — committed, but not produced by
  `make helm` at all

That is the shape of RHOAIENG-96436 (`odh-feast-operator — manifests are out of
sync`, an RC1 blocker for 3.6-EA2). The ticket's own mechanism was the
downstream `red-hat-data-services` fork sync, which this check does not cover;
the in-repo half — "the shipped chart is not what the source generates" — is
what it does cover, and it was true on `main` the day the skill ran.

Because the drift already exists, the check has to **warn**. A hard failure
would block every PR in the repo on its first run and be removed within a day.
The warning names the files and says the check can be promoted once the
committed chart is regenerated.

### RBAC identity: the check that reproduces RHOAIENG-100514

The Data module outage in October 2026 was a kustomize rename, not a code bug.
`namePrefix: feast-operator-` rewrote the `ServiceAccount` but not the
`subjects` of `tls_clusterrolebinding.yaml`, so the operator ran as
`feast-operator-controller-manager` while its binding granted permissions to
`controller-manager`. It started, failed to read
`apiservers.config.openshift.io`, crash-looped, `default-feastoperator` stayed
`Not Ready`, and the `DataScienceCluster` was never Ready
(RHOAIENG-100514, RHOAIENG-100515, RHOAIENG-99631).

The check is twenty lines: collect the rendered `ServiceAccount` names, then
assert every RBAC subject and every pod `serviceAccountName` is in that set.
Fault-injected by rewriting the rendered chart's subjects back to
`controller-manager`:

```
ClusterRoleBinding/opendatahub-feast-manager-rolebinding binds to
ServiceAccount validation/controller-manager, which the chart does not create
```

It has to run on **rendered** output. `namePrefix` is a kustomize transform, so
the raw overlay and the raw chart template both look correct.

### Two false positives worth pre-empting

- `COPY --from=builder /workspace/bin/manager .` is not a build-context path.
  A naive "every COPY source must exist" walk fails on every multi-stage
  Dockerfile. Skip `COPY` lines containing `--from=`.
- `cp -r /manifests/. /opt/manifests/` reaches the parser as separate argv
  tokens. Filter tokens starting with `-` and treat the last token as the
  destination.

### The green job that skipped its own check

The first CI run of the drift check passed in 2m21s. It had not checked
anything: `make helm` failed in the clean export, the script printed a warning
and returned 0, and the job went green. The failure only surfaced when the log
was read line by line — which nobody does for a passing job.

Two separate bugs, both worth carrying forward:

1. **A skipped assertion must not be a pass.** Capture the generator output and
   exit non-zero when generation fails. *Drift* may warn (it pre-exists);
   *inability to generate* must fail.
2. **Workflow `env:` overrides Makefile `?=` variables.** The workflow exported
   `KUSTOMIZE_VERSION: '5.8.1'`. `KUSTOMIZE_VERSION ?= v5.8.1` does not apply
   when the variable is already set, so `make helm` ran
   `go run ...kustomize/v5@5.8.1` and died with `invalid version: unknown
   revision 5.8.1`. The `v` was in the Makefile default and not in the
   workflow. Prefix every simulator variable (`SIM_*`) so it cannot collide.

### Environment: the `go run` fallback is not free

`make helm` and the skill's helm/kustomize fallbacks use `go run <module>@<ver>`.
That needs a writable `GOCACHE` and a reachable module proxy. On a locked-down
laptop it fails with `operation not permitted` on
`~/Library/Caches/go-build`, or `dial tcp: lookup proxy.golang.org`. Add
`HELM_BIN` / `KUSTOMIZE_BIN` / `KUBECONFORM_BIN` overrides, and install real
binaries in CI.

Two related Go notes:

- `GOTOOLCHAIN=local` belongs in the CI hermetic job. With `auto`, a `go.mod`
  bump past the builder image silently downloads a toolchain mid-build — the one
  thing the Konflux builder cannot do. (On a laptop, `auto` plus an isolated
  `GOMODCACHE` is still the right call; see the note above.)
- **`go-version-file: go.mod` is the wrong toolchain.** It installs whatever
  `go.mod` asks for, so the preflight passes on a Go the builder image does not
  have. Parse the `golang:<ver>` tag out of the Containerfile, pass that to
  `actions/setup-go`, and compare `go env GOVERSION` against it before building.
- Do not hardcode `docker`. `CONTAINER_TOOL=docker|podman` costs three lines and
  is the difference between the image check running and being skipped.

### What the review of the simulator itself found

A second pass over the generated workflow found six more traps, all of them in
the simulator rather than the component:

1. **`-verbose` is not optional.** kubeconform's `-output json` omits
   `statusSkipped` records unless `-verbose` is set. Without it a `Deploymnet`
   typo disappears from the report and the built-in-kind guard never fires.
2. **`-verbose` also surfaces every CRD.** kubeconform ships no schema for
   `CustomResourceDefinition`, so each one arrives as `statusSkipped`. Allow
   exactly `(apiextensions.k8s.io/v1, CustomResourceDefinition)`; anything else
   in a built-in group is a typo or an API version that no longer exists. Do not
   allowlist the whole `apiextensions.k8s.io` group — that hides `v1beta1`.
3. **A version in a URL is not integrity.** Pin the SHA-256 of every release
   archive (`helm`, `kustomize`, `kubeconform`) in the workflow and run
   `sha256sum --check --strict` before extracting. Same for installers:
   `curl ... | sh` for `uv` becomes the SHA-pinned `astral-sh/setup-uv`.
4. **The PipelineRun's dockerfile and context must travel.** Reading
   `dockerfile` / `path-context` only to check they exist, then building
   `Containerfile` with context `.`, lets a PR pass the simulator and break the
   build Konflux actually runs. Resolve the target once and pass it to every
   downstream check, including `COPY` source existence.
5. **`.dockerignore` is a build input.** A PR that only edits it can break the
   image build; it belongs in the relevant-path filter next to the Containerfile.
6. **A lock is not an install.** `uv pip compile --python-platform
   x86_64-manylinux_2_34` on an arm64 host proves the closure *resolves*. Gate
   the offline install on `uname -m` matching the lock target and pass
   `--python-platform` to both installs, or say plainly that only resolution ran.
   For Go, `GOPROXY=off` alone still permits a direct VCS fetch for modules
   matching `GONOPROXY`; add `GONOPROXY=none`.

### Evidence table

| Issue | Caught | By |
|---|---|---|
| RHOAIENG-100514 / 100515 — Data module NotReady, RBAC subject mismatch | Yes | `rbac-subjects` on the rendered chart |
| RHOAIENG-99631 — DSC never Ready, rhods-operator renders the feast chart | Partly | Chart render + RBAC; platform consumption is out of scope |
| RHOAIENG-57579 — duplicate `RELATED_IMAGE_CRON_JOB` | Yes | `duplicate-env` |
| RHOAIENG-96436 — manifests out of sync | Partly | In-repo chart drift; downstream fork sync is separate |
| RHOAIENG-83128 — `get-manifests.sh` pins an old feast commit | No | Needs a cluster |
| RHOAIENG-101993 — reconciler crashes on `is not a WithReleases` | No | Needs `make test-e2e` |
| RHOAIENG-79767 — ppc64le `ImagePullBackOff` | Warn | `build-platforms` absent from the PipelineRun |

## Learning: the skill shipped the defects it was meant to catch

Reviewing the two onboarding PRs side by side showed the same two findings in
both. Neither came from the component repos — both were copied verbatim out of
this skill's own recipes.

**`kubeconform ... || true`.** Step 2.4b taught the typo guard with the exit
status discarded. The guard then cannot fire: `statusInvalid` and `statusError`
are exactly the states it exists to catch, and `|| true` drops both. CodeRabbit
raised it independently on `feast#310` and `feast-module-operator#55`.

**"DO NOT do binary checksum verification."** The security section said this
explicitly, on the grounds that it was "too fragile in CI", and recommended
HTTPS plus a pinned version instead. Both generated workflows therefore
downloaded Helm, Kustomize, and kubeconform and `sudo install`ed them without a
digest. Both PRs got CWE-494 / CWE-829 findings for it.

Two things follow.

1. **A skill snippet is a template, not an example.** Whatever it contains ends
   up in every repo that onboards, so a defect in the recipe scales with
   adoption. Review the recipes with the same suspicion as generated code —
   ideally by fault-injecting them, the same rule the skill applies to checks.
2. **Fix the fragility, don't abandon the control.** Checksum verification was
   dropped because the first attempt was flaky, and the fix recorded was "don't
   do it". The right fix is to pin the digest next to the version and read it
   from the project's published checksum file, which is neither fragile nor
   optional.

The general rule already appears in this document — *a check that cannot fail is
worse than no check* — and that is precisely what a `|| true` on a validator, or
an unverified download-then-execute, produces. Apply it to the templates too.

## Learning: one build variant is not the product

The odh-dashboard simulator builds twice (`BUILD_MODE=ODH` and `=RHOAI`) and
asserts the artifacts do not contaminate each other. That looked like
dashboard-specific complexity, so the feast-module-operator onboarding copied
the single-build shape. It was wrong, and the reason is visible in the
repository rather than in the workflow.

`feast-module-operator` has no `ARG BUILD_MODE`. It still has two products.
`ODH_PLATFORM_TYPE=odh|rhoai` selects a different overlay at runtime:
`opendatahub` vs `redhat-ods-applications`, `registry.k8s.io/kubectl` vs
`registry.redhat.io/openshift4/ose-cli`, `odh-kube-rbac-proxy` vs
`rhoai/odh-kube-rbac-proxy-rhel9`, and `rhoai` adds `../../prometheus` plus a
`ServiceMonitor`. Only the ODH overlay had ever been deployed by CI. A
`RELATED_IMAGE_*` value, a namespace, or a bundled monitoring object that only
exists on one side is invisible to a single-variant simulator, and those are
exactly the inputs to "component NotReady" tickets.

The generalisation: a variant is anything that changes the artifact or the
deployed resource set. Compile-time build-args, runtime platform selectors, and
a separate `red-hat-data-services/*` repository are all variants. Enumerate
them from the repo (Step 1.2b) before designing jobs; the workflow should have
one leg per variant, named after it, with `fail-fast: false` so one red leg
does not hide the other.

## References

- npm issue with --network=none: https://github.com/npm/cli/issues
- Hermeto documentation: (add link)
- odh-dashboard PR #9658 (operator reconcile smoke test + kubeconform hardening): https://github.com/opendatahub-io/odh-dashboard/pull/9658
- Cachi2 documentation: (add link)
- CWE-494: Download of Code Without Integrity Check
- CWE-829: Inclusion of Functionality from Untrusted Control Sphere
