# PR Build Validation - Implementation Instructions

## Task

Analyze a repository and generate comprehensive PR build validation workflows that catch build failures before they reach Konflux/production.

## Input

- Repository URL (required)
- Optional: Build modes to test (RHOAI, ODH, etc.)
- Optional: Platforms to target (if multi-arch)

## Output

Generate GitHub Actions workflows and supporting files for PR build validation.

## Security Hardening Requirements

**CRITICAL:** ALL generated workflows MUST include these security hardening patterns. See `LEARNINGS.md` for detailed rationale.

### Required Security Patterns

1. **Pin GitHub Actions by Commit SHA**
   - ✅ `uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.2.2`
   - ❌ `uses: actions/checkout@v4`

2. **Least-Privilege Permissions**
   ```yaml
   permissions:
     contents: read
     actions: write  # Only when needed for artifacts
   ```

3. **Strict Shell Error Handling**
   ```yaml
   run: |
     set -euo pipefail  # FIRST line of every bash script
     # ... commands
   ```

4. **Checksum Verification for Downloaded Binaries** ⚠️ **NOT RECOMMENDED**
   
   **Status:** Attempted but removed due to CI failures with checksum mismatches.
   
   **Why it failed:**
   - Checksums must be manually verified and updated
   - GitHub Actions runners may have caching/proxy issues
   - Difficult to debug checksum mismatches in CI
   - Adds complexity and potential for breakage
   
   **Alternative approach:**
   - Use official installation scripts when available
   - Download from trusted sources (github.com releases)
   - Rely on HTTPS for transport security
   - Pin specific versions in URLs when possible
   - **Primary supply chain protection comes from pinned GitHub Actions (SHA)**
   
   See `LEARNINGS.md` for detailed explanation.

5. **Improved Skip Conditions**
   ```yaml
   if: "!contains(github.event.pull_request.title, '[skip konflux-sim]') && !contains(github.event.pull_request.labels.*.name, 'skip-konflux-sim')"
   ```

6. **Optional Tool Dependencies with Fallback**
   ```bash
   if command -v jq &> /dev/null; then
     # ... jq commands
   else
     echo "⚠️  WARNING: jq not installed, skipping validation"
   fi
   ```

7. **Proper Timeout Handling**
   ```bash
   READY=false
   for i in {1..30}; do
     if check_condition; then
       READY=true
       break
     fi
     sleep 2
   done
   
   if [ "$READY" = "false" ]; then
     echo "❌ FAIL: Timeout waiting for condition"
     exit 1
   fi
   ```

8. **Proper Variable Quoting**
   ```bash
   # Always quote variables
   echo "Processing ${VARIABLE}..."
   if [ -n "$VARIABLE" ]; then
     # ... commands
   fi
   ```

9. **No Credential Persistence in Checkouts**
   ```yaml
   - uses: actions/checkout@<sha> # vX.Y.Z
     with:
       persist-credentials: false
   ```
   Validation workflows only need to read the repo; leaving the token in
   `.git/config` gives later steps (and any compromised dependency) push access.

10. **Single Skip Gate, Safe Summary Job, No PR-Text Interpolation**
    Evaluate the skip condition once in a `check-skip` job and let every other
    job consume `needs.check-skip.outputs.should-skip`. Duplicating the
    expression per job lets the title and label rules drift apart.

    Pass PR text through `env:`, never interpolate `${{ github.event.pull_request.title }}`
    directly into `run:` — a PR title is attacker-controlled input.

    A skip gate is only correct if all five of these hold. Omitting any one of
    them produces a workflow that reports success without validating anything:

    1. the `check-skip` job **declares `outputs:`** — without it
       `needs.check-skip.outputs.should-skip` is the empty string, and
       `'' != 'true'` makes every consumer run while looking guarded;
    2. every validation job has **`if: needs.check-skip.outputs.should-skip != 'true'`**;
    3. `workflow_dispatch` is handled — `github.event.pull_request` is `null`
       there, so the title/label test matches nothing and the run proceeds;
    4. the summary can distinguish "skipped on purpose" from "never ran";
    5. you re-run on edits, because `edited`/`labeled`/`unlabeled` change the
       skip inputs and the `gh` CLI's `--add-label` path emits `labeled`.

    ```yaml
    on:
      pull_request:
        types: [opened, synchronize, reopened, edited, labeled, unlabeled]
      workflow_dispatch:

    concurrency:
      # A new push supersedes the old run; edits and label events must NOT
      # cancel, or the summary check flips to "cancelled" mid-review.
      group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
      cancel-in-progress: ${{ github.event.action == 'synchronize' }}

    jobs:
      check-skip:
        runs-on: ubuntu-latest
        outputs:
          should-skip: ${{ steps.decide.outputs.should-skip }}
        steps:
          - id: decide
            env:
              PR_TITLE: ${{ github.event.pull_request.title }}
              PR_LABELS: ${{ join(github.event.pull_request.labels.*.name, ',') }}
              EVENT_NAME: ${{ github.event_name }}
            run: |
              set -euo pipefail
              # workflow_dispatch carries no pull_request payload; never skip a
              # manual run, or the job silently validates nothing.
              if [ "$EVENT_NAME" != "pull_request" ]; then
                echo "should-skip=false" >> "$GITHUB_OUTPUT"
                exit 0
              fi
              if [[ "$PR_TITLE" == *"[skip konflux-sim]"* ]] || \
                 [[ ",${PR_LABELS}," == *",skip-konflux-sim,"* ]]; then
                echo "should-skip=true" >> "$GITHUB_OUTPUT"
              else
                echo "should-skip=false" >> "$GITHUB_OUTPUT"
              fi

      static-checks:
        needs: check-skip
        if: needs.check-skip.outputs.should-skip != 'true'
        runs-on: ubuntu-latest
        # ...

      summary:
        if: always()
        needs: [check-skip, static-checks]   # every validation job
        runs-on: ubuntu-latest
        steps:
          - env:
              NEEDS: ${{ toJSON(needs) }}
            run: |
              set -euo pipefail
              echo "$NEEDS"
              # check-skip must itself succeed, or the gate told us nothing.
              gate=$(jq -r '."check-skip".result' <<< "$NEEDS")
              if [ "$gate" != "success" ]; then
                echo "❌ check-skip result was '$gate'"
                exit 1
              fi
              skip=$(jq -r '."check-skip".outputs."should-skip"' <<< "$NEEDS")
              if [ "$skip" = "true" ]; then
                # Off by request. 'skipped' is the only acceptable result, and
                # anything else means the gate leaked into a job that still ran.
                bad=$(jq -r 'to_entries[]
                  | select(.key != "check-skip" and .key != "summary")
                  | select(.value.result != "skipped")
                  | "\(.key)=\(.value.result)"' <<< "$NEEDS")
              else
                # Not skipped, so 'skipped' is a failure here. GitHub counts a
                # skipped job as a passing required check, which lets a broken
                # `if:` report green.
                bad=$(jq -r 'to_entries[]
                  | select(.key != "check-skip" and .key != "summary")
                  | select(.value.result != "success")
                  | "\(.key)=\(.value.result)"' <<< "$NEEDS")
              fi
              if [ -n "$bad" ]; then
                echo "❌ unexpected job results:"
                echo "$bad"
                exit 1
              fi
              echo "✅ all validation jobs accounted for (skip=$skip)"
    ```

    Make `summary` the only required status check. It cannot be bypassed by a
    job that never ran, which is the whole point of keeping it outside any
    path filter.

    Do not combine `!` with a pipeline under `set -o pipefail` when deciding
    whether a PR touched relevant files. `grep -q` exits at the first match, so
    `git diff` can take `SIGPIPE` and fail; the negation then reads that as
    "no relevant changes" and the run skips validation while reporting success.
    Capture first, then match:

    ```bash
    set -euo pipefail
    changed_files="$(git diff --name-only "origin/${BASE_REF}...HEAD")" || exit 1
    if ! grep -Eq "$RELEVANT" <<< "$changed_files"; then
      echo "should-skip=true" >> "$GITHUB_OUTPUT"
    else
      echo "should-skip=false" >> "$GITHUB_OUTPUT"
    fi
    ```

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

**Then answer the question that actually decides operator integration: who consumes these
images?** Repo layout cannot tell you this. An operator in another repository may
ship everything you build here, and skipping operator integration then leaves that path
untested.

```bash
# Does another repo's operator reference this image?
gh search code "<image-name>" --filename=manifests-config.yaml --limit 10
gh search code "RELATED_IMAGE_" --repo <org>/<candidate-operator> --limit 10

# Does this repo already assume a platform operator exists?
rg -n "DataScienceCluster|datasciencecluster|managementState" .
```

Three outcomes:

| Outcome | Operator integration |
|---------|---------|
| This repo owns the operator | Run it as written |
| Another repo's operator ships these images | Run it against that operator, at a pinned commit |
| Only the RHOAI platform operator ships it | Out of scope — say so explicitly, do not fake it |

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

#### Step 1.2b: Enumerate the Build Variants (ODH, RHOAI, downstream)

A simulator that builds one artifact proves one artifact. ODH components
usually ship at least two: the upstream/ODH build and the downstream/RHOAI
build. Find out how they differ **before** writing jobs, or the simulator
silently covers half the product.

Three mechanisms produce the difference. Check all three:

```bash
# 1. A build-arg that changes the bytes in the image
rg -n "ARG (BUILD_MODE|PLATFORM|DISTRIBUTION|[A-Z_]*_MODE)" -g '*ockerfile*' -g 'Containerfile*'
rg -n "BUILD_MODE|BUILD_PLATFORM" .github .tekton 2>/dev/null

# 2. A Makefile or script variable that selects the inputs
rg -n "ODH_PLATFORM_TYPE|PLATFORM_TYPE|DOWNSTREAM|IS_RHOAI" Makefile hack/ scripts/ 2>/dev/null

# 3. A separate downstream repository that is the real build input
rg -n "red-hat-data-services|quay.io/rhoai|registry.redhat.io" hack/ scripts/ Makefile .tekton 2>/dev/null
```

| Mechanism | What changes | Simulator requirement |
|-----------|--------------|-----------------------|
| `ARG BUILD_MODE=RHOAI` in the Containerfile | The bytes in the image: branding, route bundles, feature flags | Build **both** variants and assert cross-contamination (the ODH build must not carry RHOAI branding, and vice versa) |
| Platform selector such as `ODH_PLATFORM_TYPE` | Which manifests/overlays get rendered, which platform-type value is injected at runtime | Run the operator/e2e phase once per value — not once in total |
| Downstream repo (`red-hat-data-services/<component>`) | The pinned manifest commit and the `RELATED_IMAGE_*` registry set | Pin and validate the downstream commit; say so explicitly if you cannot build it |

Record the answer in the PR description as a table of variants and which job
covers each. A variant with no job is a coverage gap to name, not something to
leave implied.

Do not assume the dashboard's shape. `odh-dashboard` needs two docker builds
because `BUILD_MODE` is a compile-time input. `feast-module-operator` has no
build-arg at all and still has two variants: `ODH_PLATFORM_TYPE=odh|rhoai`
selects a different overlay — namespace, `RELATED_IMAGE_CRON_JOB`
(`registry.k8s.io/kubectl` vs `registry.redhat.io/openshift4/ose-cli`),
`odh-kube-rbac-proxy` vs `rhoai/odh-kube-rbac-proxy-rhel9`, and `rhoai` adds
`../../prometheus` plus a `ServiceMonitor`. Same image, different deployed
resource set, and only one of them was ever deployed.

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

#### Step 1.5b: Resolve How Konflux Actually Builds

**Context:** `.tekton/*pull-request.yaml` often delegates to a shared pipeline in another repository (for example `odh-konflux-central`). The resolved pipeline's parameter defaults decide the platform set, hermetic mode, and prefetch inputs. Do not infer any of that from the PipelineRun filename.

```bash
# Images Konflux builds from PRs (ignore early-gate CI pipelines)
rg -l "kind: PipelineRun" .tekton/*pull-request.yaml

# Build inputs per component
rg -nE "name: (output-image|dockerfile|path-context|build-platforms|hermetic|prefetch-input)" \
  .tekton/*pull-request.yaml

# Resolve an external pipelineRef and read its parameter defaults
PIPELINE_URL=$(yq '.spec.pipelineRef.params[] | select(.name=="url") | .value' .tekton/<file>.yaml)
PIPELINE_PATH=$(yq '.spec.pipelineRef.params[] | select(.name=="pathInRepo") | .value' .tekton/<file>.yaml)
curl -fsSL "${PIPELINE_URL/github.com/raw.githubusercontent.com}/main/${PIPELINE_PATH}" | \
  grep -A6 -E "name: (build-platforms|hermetic|prefetch-input)"
```

**Rules:**

- Only simulate images the repository's `.tekton` PR PipelineRuns build. Do not add controller, CSI, or test images Konflux does not build here, and do not duplicate coverage that existing workflows already provide (Kind/operator deployment, unit tests).
- A pipeline named `multi-arch-*` is not automatically multi-arch: `odh-konflux-central` defaults `build-platforms` to `linux/x86_64`. Compare against the exact value the pipeline resolves, or normalize the `x86_64`/`amd64` spellings before comparing; do not assume the two strings are interchangeable.
- If `hermetic` or `prefetch-input` is set, the build depends on Hermeto prefetch; add the offline preflight from Step 2.1b.

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

#### Step 1.8: Mine Historical Breakages for This Component

Do this before deciding which checks to generate. A simulator that only runs
generic checks measures nothing; a simulator that is aimed at failures that
actually escaped is worth something. The output of this step is the coverage
target list that Step 2.6 has to prove against.

**Find the right Jira component first.** It is frequently *not* the repository
name, and picking the obvious one returns an empty result that looks like "no
history". For model-registry, the `Model Registry` component is empty while all
the work sits under `AI Hub`. Search for the repo name, the operator's component
key from Step 2.5, and the product-facing name, then keep whichever component
actually returns issues:

```bash
# Use whatever Jira client is configured. Detect rather than assume:
for tool in acli jira; do command -v "$tool" >/dev/null 2>&1 && echo "found: $tool"; done

# acli (Atlassian CLI)
acli jira workitem search --jql 'project = RHOAIENG AND component = "AI Hub"' --limit 200

# jira-cli (ankitpokhrel)
jira issue list -q 'project = RHOAIENG AND component = "AI Hub"' --plain
```

If no client is installed or configured, stop and ask for the ticket list (or a
saved JQL export). Do **not** invent ticket keys, and do not silently skip this
step — an unsupported "no history found" claim in the PR description is worse
than an explicit gap.

**Search by QE test name, not just by words.** Failed-test names are the
highest-signal key in the tracker, because they name the assertion that broke.
The model-registry DSC tickets were clustered by `test_mr_condition_in_dsc`,
`test_mr_management_state`, `test_mr_pods_health`, and
`test_data_science_cluster_healthy`:

```bash
jira issue list -q 'project = RHOAIENG AND text ~ "test_mr_condition_in_dsc"' --plain
jira issue list -q 'project = RHOAIENG AND (summary ~ "DataScienceCluster" OR summary ~ "DSC")' --plain
```

**Classify every hit honestly.** Only the first two classes are this skill's
job; claiming the others is how a green check gets mistaken for coverage.

| Class | Tell-tale in the ticket | Where it can be caught |
|---|---|---|
| Build-time, in-repo | `hermetic`, `go.sum`, `lockfile`, `ModuleNotFoundError` / `No module named` during image build | This repo — hermetic preflight, lockfile checks |
| Packaging / render | manifest path mismatch, missing overlay dir, `RELATED_IMAGE_*` ignored, wrong `sourcePath` | This repo — manifest validation and the operator phase |
| Reconcile / conditions | `DataScienceCluster` condition `False`, `managementState`, component pods unhealthy | Operator repo e2e only — hand off via Step 2.5 |
| Infra / capacity / flake | quota, image pull throttling, CSI, provisioning | Neither. Say so; do not claim it |

Write the result down as you go. Each row needs the ticket, the QE test that
failed, the observed symptom, and the class:

```markdown
| Ticket | Failing test | Symptom | Class |
|---|---|---|---|
| RHOAIENG-103141 | `test_mr_condition_in_dsc` | `ModelRegistryReady` False | Reconcile |
| RHOAIENG-63943 | async-upload smoke | build green, job dies on `No module named 'model_signing'` | Build-time |
```

### Phase 2: Generate Build Validation Workflow

## Critical Learnings from ODH Dashboard Implementation

**Read `LEARNINGS.md` for detailed explanations of all issues and solutions.**

### 1. Hermetic Build Validation

**❌ DO NOT use `docker run --network=none npm ci`**
- Consistently crashes npm with "Exit handler never called" error
- npm tries network operations even with `--ignore-scripts`
- Not representative of how Hermeto/Cachi2 actually work (they pre-fetch tarballs)

**✅ DO use grep/jq lockfile validation:**
```bash
# Check for unsupported protocols
grep -E '"resolved":\s*"(git\+|github:|file:)' package-lock.json

# Check only node_modules packages for resolved URLs (skip workspace packages!)
jq -r '.packages | to_entries[] | select(.key | startswith("node_modules/")) | select(.value.resolved == null)'
```

### 2. Workspace Packages in package-lock.json

**Monorepo workspace packages DO NOT have `resolved` URLs** - this is normal!

Only check packages in `node_modules/`:
- ✅ `"node_modules/@foo/bar"` - Real dependency (needs resolved URL)
- ❌ `""` - Root package (skip)
- ❌ `"backend"`, `"frontend"`, `"packages/*"` - Workspace packages (skip)

### 3. Module Federation - Host vs Remote

**Host frontend `remoteEntry.js` is OPTIONAL:**
- Generated only if `mfConfig.length > 0` (federated modules detected)
- Host has empty `exposes: {}` - doesn't expose modules
- Not critical for runtime

**✅ Check `app.bundle.js` instead** - always present in main frontend build.

**Remote packages** (gen-ai, model-registry) **DO require** `remoteEntry.js` to expose modules.

### 4. Operator Integration in Vanilla Kind

**Vanilla Kind is NOT OpenShift** - many resources will fail:
- Missing: Routes, certificate injection, CA bundles, ConsoleLinks
- ClusterRoleBindings may have validation errors (missing namespace fields)
- Pods cannot reach Ready state without OpenShift platform resources

**Strategy: Mock Secrets + Container Runtime Validation**

Simulate what Konflux actually does - **run containers** to validate builds:

1. **Create mock secrets** for volume mounts (TLS, CA bundles)
2. **Reduce resources** to fit Kind's ~2Gi memory (128Mi/50m CPU per container)
3. **Scale to 1 replica** to avoid resource exhaustion
4. **Wait for image pulls** and container startup (60s)
5. **Validate container lifecycle** - check that images pulled and containers started

This validates:
- ✅ Images load into Kind successfully
- ✅ Container specs are valid (args, env, probes)
- ✅ Volume mounts work (with mock secrets)
- ✅ Containers actually start

Much stronger than just checking YAML syntax!

**Be lenient on manifest *application*, never on manifest *validation*.** When
applying to a Kind cluster, `kubectl apply` may legitimately fail on resources
the cluster cannot admit (CRDs not yet established, ClusterRoleBinding
escalation). That is a reason to keep applying and report, not a reason to
swallow validator output. `kustomize build`, `kubeconform`, and the contract
checks must fail closed; only the apply step may continue past an error.

### 5. Security Hardening

**✅ ALWAYS do:**
- Pin GitHub Actions by commit SHA with version comment
- Least-privilege permissions (contents: read, actions: write only when needed)
- `set -euo pipefail` at start of every bash script
- Proper variable quoting
- Skip conditions for both PR title and labels

**❌ DO NOT do:**
- Download a tarball over HTTPS and `sudo install` it without a digest check.
  A version in a URL is a name, not an integrity guarantee (CWE-494, CWE-829).

**Verify every downloaded tool.** Add the digest next to the version and check it
before extraction, so a swapped artifact fails closed:

```yaml
env:
  SIM_KUSTOMIZE_VERSION: 'v5.8.1'
  SIM_KUSTOMIZE_SHA256: '<sha256 of kustomize_v5.8.1_linux_amd64.tar.gz>'
run: |
  set -euo pipefail
  url="https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2F${SIM_KUSTOMIZE_VERSION}/kustomize_${SIM_KUSTOMIZE_VERSION}_linux_amd64.tar.gz"
  curl -fsSL -o /tmp/kustomize.tar.gz "$url"
  printf '%s  %s\n' "$SIM_KUSTOMIZE_SHA256" /tmp/kustomize.tar.gz | sha256sum --check --strict
  tar -xzf /tmp/kustomize.tar.gz -C /tmp
```

Name the variables `SIM_*` when the repository's Makefile defines the same
version variable; see the Makefile-shadowing note in Step 2.4d.

Take the digest from the project's published checksum file where one exists
(Helm publishes `helm-vX.Y.Z-linux-amd64.tar.gz.sha256sum`, kubeconform ships
`CHECKSUMS`), otherwise compute it once from a known-good download and commit
it. Never invent one, and never derive it from the artifact you are about to
install. Prefer a SHA-pinned action (`astral-sh/setup-uv`, `actions/setup-go`)
over a `curl | sh` bootstrap — a pipe to a shell cannot be verified at all.

Pinned GitHub Actions remain the first line of supply chain protection; digests
cover the tools the workflow fetches itself.

### 6. Dashboard-Specific: Multi-Container Deployments

ODH Dashboard has **9 containers** in one pod:
- odh-dashboard, kube-rbac-proxy, model-registry-ui, gen-ai-ui, maas-ui, mlflow-ui, eval-hub-ui, automl-ui, autorag-ui

Most components will be simpler (1-2 containers). Adjust resource patching accordingly.

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
            # IMPORTANT: Only check node_modules packages, not workspace packages
            # Workspace packages (backend, frontend, packages/*) don't have resolved URLs
            # If using jq: '.packages | to_entries[] | select(.key | startswith("node_modules/"))'
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
          
          # Detect workspace scope dynamically
          WORKSPACE_SCOPE=""
          if [ -f "package.json" ]; then
            WORKSPACE_SCOPE=$(grep -o '"name"[[:space:]]*:[[:space:]]*"@[^/]*' package.json | sed 's/.*"@/@/' || true)
          fi
          
          # If no scope at root, detect from first workspace package
          if [ -z "$WORKSPACE_SCOPE" ]; then
            for pkg in packages/*/package.json; do
              if [ -f "$pkg" ]; then
                WORKSPACE_SCOPE=$(grep -o '"name"[[:space:]]*:[[:space:]]*"@[^/]*' "$pkg" | sed 's/.*"@/@/' | head -1 || true)
                [ -n "$WORKSPACE_SCOPE" ] && break
              fi
            done
          fi
          
          echo "Detected workspace scope: ${WORKSPACE_SCOPE:-<none>}"
          
          for dockerfile in $(find packages -name "Dockerfile.workspace" -o -name "Dockerfile" | grep -v node_modules); do
            MODULE=$(dirname "$dockerfile")
            echo "Checking $dockerfile..."
            
            # Extract packages that are COPY'd
            COPIED=$(grep "^COPY.*packages/" "$dockerfile" | sed 's/.*COPY.*\(packages\/[^\/]*\).*/\1/' | sort -u || true)
            
            # Check package.json for workspace deps
            PKG_JSON="$MODULE/package.json"
            if [ -f "$PKG_JSON" ] && [ -n "$WORKSPACE_SCOPE" ]; then
              # Find workspace dependencies using detected scope
              DEPS=$(grep -o "\"$WORKSPACE_SCOPE/[^\"]*\"" "$PKG_JSON" | tr -d '"' | sed "s|$WORKSPACE_SCOPE/|packages/|" | sort -u || true)
              
              # Cross-reference - check only runtime dependencies
              for dep in $DEPS; do
                pkg_name=$(basename "$dep")
                
                # Check if it's a runtime dependency (not devDependency)
                if grep -A 50 '"dependencies"' "$PKG_JSON" | grep -q "\"$WORKSPACE_SCOPE/$pkg_name\""; then
                  if ! echo "$COPIED" | grep -q "^$dep$"; then
                    echo "⚠️  $dockerfile imports $dep (runtime dependency) but does not COPY it"
                    echo "   This will cause Docker build to fail"
                    echo "   Add: COPY --chown=default:root $dep/ ./$dep/"
                    ISSUES=$((ISSUES + 1))
                  fi
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

  # NOTE: DO NOT add hermetic npm install test with --network=none
  # It is unreliable and crashes npm. See LEARNINGS.md for details.
  # The validation-checks job already validates lockfile compatibility.

  build-validation:
    name: Validate Build
    runs-on: ubuntu-latest
    timeout-minutes: 30
    needs: validation-checks
    if: |
      always() &&
      !contains(github.event.pull_request.title, '[skip konflux-sim]') &&
      needs.validation-checks.result == 'success'

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      # Docker build
      - name: Build Docker Image
        id: build
        run: |
          docker build \
            --build-arg BUILD_MODE=${{ env.BUILD_MODE }} \
            --tag ${{ env.IMAGE_NAME }} \
            -f Dockerfile \
            .

      # Runtime validation
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

          # Scan logs for critical errors (catches fastify/dependency issues)
          echo "Scanning logs for errors..."
          LOGS=$(docker logs test-container 2>&1)
          
          # Check for crashloop indicators
          if echo "$LOGS" | grep -qi "error.*fastify\|uncaught.*exception\|segmentation fault\|killed"; then
            echo "⚠️  Detected potential errors in startup logs:"
            echo "$LOGS" | grep -i "error\|exception\|killed" | tail -10
            echo ""
            echo "Continuing validation but flagging for review..."
          fi

          # Wait for health check
          timeout 60 bash -c 'until docker ps | grep test-container | grep -q "Up"; do sleep 2; done' || {
            echo "❌ Container failed health check"
            docker logs test-container
            exit 1
          }

          # Give it a moment to fully initialize and watch for crashes
          echo "Monitoring container stability..."
          sleep 10
          
          # Re-check container is still running after initialization
          if ! docker ps | grep -q test-container; then
            echo "❌ Container crashed after startup (delayed crash)"
            echo "This can indicate dependency compatibility issues (e.g., fastify v4→v5)"
            echo "Container logs:"
            docker logs test-container || true
            exit 1
          fi

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
      
      - name: Test Critical API Endpoints
        run: |
          # Test endpoints that broke in fastify v4→v5 upgrade (PR #7387)
          echo "Testing critical API endpoint compatibility..."
          
          # Test 1: PATCH with application/merge-patch+json (broke in Fastify 5)
          # Fastify 5 rejects this content-type with 415 FST_ERR_CTP_INVALID_MEDIA_TYPE
          echo "Testing PATCH with merge-patch+json content-type..."
          HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            -X PATCH \
            -H "Content-Type: application/merge-patch+json" \
            -d '{"test": true}' \
            http://localhost:8080/api/config 2>/dev/null || echo "000")
          
          # We expect 401/403 (auth required) or 404 (endpoint doesn't exist)
          # We do NOT expect 415 (unsupported media type)
          if [ "$HTTP_CODE" = "415" ]; then
            echo "❌ PATCH with merge-patch+json returned 415 Unsupported Media Type"
            echo "   This indicates Fastify 5 content-type regression (PR #6727)"
            echo "   Breaks 28+ operations: notebooks, model serving, pipelines, RBAC"
            exit 1
          else
            echo "✅ PATCH with merge-patch+json: $HTTP_CODE (not 415)"
          fi
          
          # Test 2: PATCH with application/json-patch+json
          echo "Testing PATCH with json-patch+json content-type..."
          HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            -X PATCH \
            -H "Content-Type: application/json-patch+json" \
            -d '[{"op": "add", "path": "/test", "value": true}]' \
            http://localhost:8080/api/config 2>/dev/null || echo "000")
          
          if [ "$HTTP_CODE" = "415" ]; then
            echo "❌ PATCH with json-patch+json returned 415 Unsupported Media Type"
            echo "   This indicates Fastify 5 content-type regression (PR #6727)"
            exit 1
          else
            echo "✅ PATCH with json-patch+json: $HTTP_CODE (not 415)"
          fi
          
          echo ""
          echo "✅ Critical API endpoint validation passed"
      
      - name: Test WebSocket Compatibility
        run: |
          # Test WebSocket connections (broke in @fastify/websocket v8→v11, PR #6727)
          # v11 removed SocketStream, causing connection.socket to return undefined
          # Non-admin users trigger 403 on WS upgrade → unhandled error → pod crash
          echo "Testing WebSocket endpoint compatibility..."
          
          # Install websocat if not available (for WS testing)
          if ! command -v websocat &> /dev/null; then
            echo "Installing websocat for WebSocket testing..."
            # Use wscat via npx as fallback
            if ! command -v npx &> /dev/null; then
              echo "⚠️  Cannot test WebSocket (no websocat or npx available)"
              echo "   Skipping WebSocket validation"
              exit 0
            fi
            WS_CLIENT="npx -y wscat"
          else
            WS_CLIENT="websocat"
          fi
          
          # Check if container is still running before WS test
          if ! docker ps | grep -q test-container; then
            echo "❌ Container not running before WebSocket test"
            echo "   Container may have crashed from earlier tests"
            docker logs test-container
            exit 1
          fi
          
          # Attempt WebSocket connection
          # We expect connection attempt (may fail auth, but shouldn't crash pod)
          echo "Attempting WebSocket connection..."
          timeout 5 $WS_CLIENT ws://localhost:8080/api/terminal 2>&1 | head -10 || true
          
          # Wait a moment for any crash to occur
          sleep 3
          
          # Check if container is still running after WS attempt
          if ! docker ps | grep -q test-container; then
            echo "❌ Container CRASHED after WebSocket connection attempt"
            echo "   This indicates @fastify/websocket v11 regression (PR #6727)"
            echo "   Issue: SocketStream removed, connection.socket returns undefined"
            echo "   Impact: Non-admin users cause pod crash (exit 1 or OOMKill 137)"
            echo ""
            echo "Container logs:"
            docker logs test-container | tail -50
            exit 1
          fi
          
          echo "✅ WebSocket test passed (container did not crash)"
      
      - name: Test Non-Root User Runtime
        run: |
          # Test running as non-root user (catches permission issues like fastify v4→v5 regression)
          echo "Testing container with non-root user..."
          
          # Stop the default container
          docker stop test-container || true
          docker rm test-container || true
          
          # Start with explicit non-root user
          # Note: UBI images typically use UID 1001
          docker run -d \
            --name test-container-nonroot \
            --user 1001:0 \
            -p 8081:8080 \
            ${{ env.IMAGE_NAME }}
          
          sleep 10
          
          # Check if container is still running (catches "killed when run with regular users")
          if ! docker ps | grep -q test-container-nonroot; then
            echo "❌ Container crashed when running as non-root user"
            echo "This indicates a permission or dependency compatibility issue"
            echo "Container logs:"
            docker logs test-container-nonroot || true
            docker ps -a | grep nonroot
            exit 1
          fi
          
          # Verify health endpoint still works
          if curl -f http://localhost:8081/ 2>/dev/null; then
            echo "✅ Non-root user runtime test passed"
          else
            echo "⚠️  Health check failed with non-root user"
            echo "Container logs:"
            docker logs test-container-nonroot
            # Don't fail - this might be expected in some environments
          fi
          
          # Cleanup
          docker stop test-container-nonroot || true
          docker rm test-container-nonroot || true
          
          # Restart default container for remaining tests
          docker run -d \
            --name test-container \
            -p 8080:8080 \
            ${{ env.IMAGE_NAME }}
          
          sleep 5

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

#### Step 2.1b: Hermetic Preflight for Go and Python Repositories

Node repos use the two-stage pnpm store pattern above. Go and Python need the same shape of proof: populate a cache with network access, then build or resolve with the network disabled by configuration. That catches the failure Hermeto exposes — a dependency that was never prefetched.

Both functions open with `(` rather than `{`. A `trap ... EXIT` registered
inside a function body belongs to the *shell*, not to the function: when the
function returns, the trap fires at the end of the whole job, by which point
its `local` variables are out of scope and the cleanup dies on
`workdir: unbound variable` under `set -u` — leaking `mktemp -d` directories
and turning a clean failure into a confusing one. A subshell gives the trap its
own scope and its own lifetime. `exit 1` still propagates: the subshell's status
becomes the function's status, so the caller's `set -e` aborts as expected.

```bash
hermetic_go_preflight() (
  local workdir modcache
  workdir="$(mktemp -d)"
  # Go marks module cache files read-only; chmod before rm or the cleanup fails.
  trap 'chmod -R u+w "$workdir" 2>/dev/null || true; rm -rf "$workdir"' EXIT
  modcache="$workdir/gomodcache"

  # GOTOOLCHAIN is explicit in BOTH phases. `go.mod` may request a newer
  # toolchain than the runner ships; the network phase then downloads it into
  # GOMODCACHE/golang.org/toolchain, and the offline phase must find that same
  # copy instead of trying to fetch it again (which GOPROXY=off would reject).
  # Setting it explicitly also stops an inherited GOTOOLCHAIN from changing
  # behaviour between local runs and CI.
  GOTOOLCHAIN=auto GOMODCACHE="$modcache" GOFLAGS="-mod=readonly" \
    go mod download

  # Offline phase: GOPROXY=off turns a missing module into a hard failure
  GOTOOLCHAIN=auto GOMODCACHE="$modcache" GOPROXY=off GOFLAGS="-mod=readonly" \
    CGO_ENABLED=0 GOOS=linux go build -buildvcs=false -o "$workdir/app" .
)

hermetic_python_preflight() (
  local workdir
  workdir="$(mktemp -d)"
  trap 'rm -rf "$workdir"' EXIT

  # One requirements file per job, not a hardcoded path: a repo may ship
  # several (one per Konflux component) and only some are in scope.
  local requirements_file="${REQUIREMENTS_FILE:?set REQUIREMENTS_FILE to the job requirements file}"
  local python_version="${PYTHON_VERSION:-3.12}"
  # Resolve for the BUILD platform, not the runner's. A wheel that exists for
  # macosx_arm64 says nothing about the manylinux build Konflux runs.
  local python_platform="${PYTHON_PLATFORM:-x86_64-manylinux_2_34}"

  # Network phase 1: resolve the full closure. Use uv, not pip. pip's
  # backtracking gives up on real dependency graphs ("resolution-too-deep")
  # and falls back to building sdists that need system toolchains (psycopg-c
  # wants pg_config). uv resolves the same graph the image installs from.
  uv pip compile "$requirements_file" \
    --python-version "$python_version" \
    --python-platform "$python_platform" \
    --quiet \
    --output-file "$workdir/lock.txt"
  echo "resolved $(grep -c '==' "$workdir/lock.txt") pinned distributions"

  # The offline proof is only meaningful where the target platform can be
  # installed. On a macOS runner the cache is keyed for darwin, so skip it
  # rather than report a pass that proves nothing.
  if [ "$(uname -s)" != "Linux" ]; then
    echo "skipping offline install on $(uname -s); resolution check only"
    return 0
  fi

  # Network phase 2: populate an ISOLATED cache, then delete the venv so the
  # next install cannot reuse installed packages and must come from the cache.
  export UV_CACHE_DIR="$workdir/uv-cache"
  uv venv "$workdir/v1" --python "$python_version" --quiet
  uv pip install --python "$workdir/v1/bin/python" \
    --requirement "$requirements_file" --quiet

  # Offline phase: --offline forbids all network, so a missing prefetch fails here
  rm -rf "$workdir/v1"
  uv venv "$workdir/v2" --python "$python_version" --quiet
  uv pip install --offline --python "$workdir/v2/bin/python" \
    --requirement "$requirements_file" --quiet
)
```

Set `REQUIREMENTS_FILE` per invocation rather than editing the function, so one
job can cover several components:

```bash
for req in jobs/*/requirements.txt; do
  REQUIREMENTS_FILE="$req" hermetic_python_preflight
done
```

**Rules:**

- Build the same package target with the same flags as the Dockerfile (`CGO_ENABLED`, `GOOS`, `-tags`, entry package). Building a different target does not prove the shipped binary links.
- Set `GOOS=linux` even on macOS so local runs catch platform-specific files.
- Use `GOPROXY=off` instead of `--network=none` inside a build that must also populate its cache; the npm limitation documented in `LEARNINGS.md` applies to any package manager that resolves during the build.
- **Use `uv` for the Python preflight, not `pip`.** `pip download` / `pip install --no-index` is the obvious recipe and it does not survive contact with a real dependency graph: pip aborts with `resolution-too-deep`, and its sdist fallback needs system toolchains the runner lacks. If the image already installs with `uv`, resolve with `uv` too — otherwise the preflight is validating a different resolution than the one that ships.
- Pin `--python-version` and `--python-platform` to the Konflux build target (`x86_64-manylinux_2_34` for a linux/x86_64 pipeline). Resolving on the runner platform proves nothing about the build.
- Warm an isolated `UV_CACHE_DIR` and **delete the venv** before the `--offline` install. If the venv survives, the second install can satisfy itself from installed packages and the check passes without proving the prefetch is sufficient.
- Run the Python resolution in a venv: PEP 668 externally-managed environments (Homebrew, Debian) reject `pip install --dry-run`.
- Keep this in a separate fast preflight job and make image builds depend on it.

#### Step 2.1c: Add the Build-Variant Matrix (when Step 1.2b found more than one)

**Compile-time variants** (`ARG BUILD_MODE`) get one build job per value, plus a
cross-contamination assertion:

```yaml
  docker-build-odh:
    steps:
      - run: docker build --build-arg BUILD_MODE=ODH -t "$IMAGE_ODH" .

  docker-build-rhoai:
    steps:
      - run: docker build --build-arg BUILD_MODE=RHOAI -t "$IMAGE_RHOAI" .
```

Assert the branding rather than stopping at a green build. A build-arg that
stops being plumbed still builds successfully — it just builds the wrong
artifact. Grep the built image for the other variant's markers and fail when
they are present.

**Runtime variants** (platform selector) get a matrix leg on the deploy/e2e
job, not a second image build:

```yaml
  operator-e2e:
    strategy:
      fail-fast: false
      matrix:
        platform: [odh, rhoai]
    steps:
      # $IMAGE is the operator image built by this PR's build job.
      - run: make test-e2e ODH_PLATFORM_TYPE=${{ matrix.platform }} IMG="$IMAGE"
```

Name the legs after the platform (`Operator e2e (odh)`, `Operator e2e (rhoai)`)
so a red leg says which platform broke. `fail-fast: false` is required: the
first leg failing must not hide whether the other platform was also broken.

If a variant genuinely cannot run in CI — no entitlement-protected registry
access, no OpenShift APIs on Kind — say that in the PR description and file the
follow-up. Do not let the matrix quietly shrink to the variant that happens to
work.

#### Step 2.2: Add Module Federation Validation (if detected)

```yaml
      # Module Federation validation
      - name: Validate Module Federation Build Output
        if: ${{ env.IS_MONOREPO == 'true' }}
        run: |
          # Validate that webpack actually generated the remoteEntry.js files
          # NOTE: /_mf/{name}/* routes are PROXIES to K8s services (port 8043), not local files
          # Standalone container returns 404 for all /_mf/* requests
          # This validates the BUILD created the assets, not runtime proxy endpoints

          docker run --rm ${{ env.IMAGE_NAME }} sh -c '
            ISSUES=0
            
            for module in {DETECTED_MODULES}; do
              # Check if module has MF config first
              if [ -f "/opt/app-root/src/packages/${module}/package.json" ]; then
                if grep -q "module-federation" "/opt/app-root/src/packages/${module}/package.json"; then
                  echo "Validating $module Module Federation output..."
                  
                  # Find dist directory
                  DIST_DIR=""
                  if [ -d "/opt/app-root/src/packages/${module}/frontend/dist" ]; then
                    DIST_DIR="/opt/app-root/src/packages/${module}/frontend/dist"
                  elif [ -d "/opt/app-root/src/packages/${module}/dist" ]; then
                    DIST_DIR="/opt/app-root/src/packages/${module}/dist"
                  elif [ -d "/static" ]; then
                    # Module sidecar pattern (e.g., gen-ai-ui container)
                    DIST_DIR="/static"
                  fi
                  
                  if [ -z "$DIST_DIR" ]; then
                    echo "❌ $module: No dist directory found"
                    ISSUES=$((ISSUES + 1))
                    continue
                  fi
                  
                  # Validate remoteEntry.js exists
                  if [ ! -f "$DIST_DIR/remoteEntry.js" ]; then
                    echo "❌ $module: remoteEntry.js not found"
                    ISSUES=$((ISSUES + 1))
                    continue
                  fi
                  
                  echo "✅ $module: remoteEntry.js exists"
                  
                  # Check remoteEntry.js size (catches empty/corrupted files)
                  ENTRY_SIZE=$(stat -f%z "$DIST_DIR/remoteEntry.js" 2>/dev/null || stat -c%s "$DIST_DIR/remoteEntry.js" 2>/dev/null)
                  if [ "$ENTRY_SIZE" -lt 1000 ]; then
                    echo "⚠️  $module: remoteEntry.js is suspiciously small ($ENTRY_SIZE bytes)"
                    echo "   This may cause Module Federation to fail"
                    ISSUES=$((ISSUES + 1))
                  fi
                  
                  # Enhanced: Check for webpack chunks
                  # This catches ChunkLoadError issues (missing bundle files)
                  CHUNK_COUNT=$(find "$DIST_DIR" -name "*.bundle.js" | wc -l | tr -d " ")
                  
                  if [ "$CHUNK_COUNT" -eq 0 ]; then
                    echo "⚠️  $module: No webpack chunks found (may cause ChunkLoadError at runtime)"
                    echo "   Expected: *.bundle.js files"
                    echo "   Issue: RHOAIENG-59862 - Dashboard loads slowly, Cypress timeouts"
                    ISSUES=$((ISSUES + 1))
                  else
                    echo "✅ $module: Found $CHUNK_COUNT webpack chunks"
                    
                    # List sample chunks for verification
                    echo "   Sample chunks:"
                    find "$DIST_DIR" -name "*.bundle.js" | head -3 | while read chunk; do
                      echo "     - $(basename $chunk) ($(stat -f%z "$chunk" 2>/dev/null || stat -c%s "$chunk" 2>/dev/null) bytes)"
                    done
                    
                    # Check for suspiciously large chunks (slow to load)
                    LARGE_CHUNKS=$(find "$DIST_DIR" -name "*.bundle.js" -size +1M | wc -l | tr -d " ")
                    if [ "$LARGE_CHUNKS" -gt 0 ]; then
                      echo "   ⚠️  Found $LARGE_CHUNKS chunks larger than 1MB (may slow page load)"
                      find "$DIST_DIR" -name "*.bundle.js" -size +1M -exec ls -lh {} \; | head -3
                    fi
                  fi
                  
                  # Validate critical assets exist
                  TOTAL_SIZE=$(du -sh "$DIST_DIR" 2>/dev/null | cut -f1)
                  echo "   Total dist size: $TOTAL_SIZE"
                fi
              fi
            done
            
            if [ $ISSUES -gt 0 ]; then
              echo ""
              echo "❌ Module Federation validation failed with $ISSUES issue(s)"
              echo ""
              echo "These issues can cause:"
              echo "  - Dashboard slow to load (RHOAIENG-59861)"
              echo "  - ChunkLoadError in browser (RHOAIENG-59862)"
              echo "  - Cypress tests timeout waiting for #page-sidebar"
              exit 1
            fi
            
            echo ""
            echo "✅ All Module Federation remotes built successfully"
          ' || {
            echo "❌ Module Federation build validation failed"
            exit 1
          }
      
      - name: Test Module Federation Load Performance
        if: ${{ env.IS_MONOREPO == 'true' }}
        run: |
          # Test that Module Federation endpoints respond quickly
          # Slow remoteEntry.js loading causes dashboard timeouts
          
          echo "Starting test container for MF performance testing..."
          docker run -d \
            --name mf-perf-test \
            -p 8090:8080 \
            ${{ env.IMAGE_NAME }}
          
          sleep 5
          
          echo ""
          echo "Testing Module Federation endpoint response times..."
          echo "(Dashboard slow load issue: RHOAIENG-59861, RHOAIENG-59862)"
          echo ""
          
          SLOW_ENDPOINTS=0
          FAILED_ENDPOINTS=0
          
          # Test main dashboard endpoint
          START=$(date +%s%N)
          if curl -f -s --max-time 5 http://localhost:8090/ > /dev/null; then
            END=$(date +%s%N)
            DURATION=$((($END - $START) / 1000000))
            if [ $DURATION -gt 2000 ]; then
              echo "⚠️  Main dashboard: ${DURATION}ms (slow - >2s)"
              SLOW_ENDPOINTS=$((SLOW_ENDPOINTS + 1))
            else
              echo "✅ Main dashboard: ${DURATION}ms"
            fi
          else
            echo "❌ Main dashboard: FAILED to respond"
            FAILED_ENDPOINTS=$((FAILED_ENDPOINTS + 1))
          fi
          
          # Note: Module endpoints (/_mf/*) require K8s environment
          # In standalone Docker, we can only test build artifacts
          
          # Cleanup
          docker stop mf-perf-test || true
          docker rm mf-perf-test || true
          
          if [ $SLOW_ENDPOINTS -gt 0 ]; then
            echo ""
            echo "⚠️  $SLOW_ENDPOINTS endpoint(s) responded slowly (>2s)"
            echo "   This may cause Cypress timeouts and slow dashboard loads"
          fi
          
          if [ $FAILED_ENDPOINTS -gt 0 ]; then
            echo ""
            echo "❌ $FAILED_ENDPOINTS endpoint(s) failed to respond"
            exit 1
          fi
          
          echo ""
          echo "✅ Module Federation performance test complete"
```

#### Step 2.3: Add Operator Integration Testing (if detected)

**CRITICAL UNDERSTANDING: Vanilla Kind Limitations**

Vanilla Kind (Kubernetes in Docker) is **NOT** OpenShift. It lacks:
- OpenShift Routes, Ingress controllers
- OpenShift certificate management (service CA injection)
- OpenShift trusted CA bundle injection  
- ConsoleLinks, OdhQuickStarts, OdhDocuments (OpenShift CRDs)
- Many platform-level resources that manifests expect

**What Can Be Validated in Kind:**
- ✅ Manifest structural validity (YAML syntax, API versions)
- ✅ Deployment/Pod resource creation
- ✅ **Container runtime lifecycle** (images pull, containers start)
- ✅ Volume mount specifications (with mock secrets)
- ✅ Container args, env vars, probes
- ❌ Full application readiness (requires OpenShift platform)

**Strategy: Simulate Konflux's Container Runtime Validation**

Konflux actually **runs containers** to test builds. We should do the same in Kind by:
1. Creating mock secrets/configmaps for volume mounts
2. Reducing resource requests to fit Kind's ~2Gi memory limit
3. Validating containers actually start and images pull successfully

This is **much stronger validation** than just checking YAML syntax.

```yaml
  operator-integration:
    name: "Operator Integration (Kind)"
    needs: [docker-build-odh, docker-build-rhoai]  # Or whatever your build jobs are named
    runs-on: ubuntu-latest
    permissions:
      contents: read
    if: "!contains(github.event.pull_request.title, '[skip konflux-sim]') && !contains(github.event.pull_request.labels.*.name, 'skip-konflux-sim')"

    steps:
      - name: Checkout code
        uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.2.2

      - name: Install Kind
        run: |
          set -euo pipefail
          curl -Lo kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
          chmod +x kind
          sudo mv kind /usr/local/bin/

      - name: Create Kind cluster
        run: |
          set -euo pipefail
          kind create cluster --name test-cluster --wait 300s

      - name: Download built image
        uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4.2.1
        with:
          name: your-image-artifact
          path: /tmp

      - name: Load image into Kind
        run: |
          set -euo pipefail
          docker load < /tmp/your-image.tar.gz
          kind load docker-image your-image:tag --name test-cluster

      - name: Create target namespace
        run: |
          kubectl create namespace your-namespace

      - name: Create mock OpenShift secrets (if manifests need them)
        run: |
          set -euo pipefail
          # CRITICAL: Many manifests expect OpenShift-injected secrets
          # Create mock TLS secret for volume mounts
          openssl req -x509 -newkey rsa:2048 -nodes \
            -keyout /tmp/tls.key -out /tmp/tls.crt \
            -days 1 -subj "/CN=test" 2>/dev/null

          kubectl create secret tls your-tls-secret \
            --cert=/tmp/tls.crt --key=/tmp/tls.key \
            -n your-namespace

          rm /tmp/tls.key /tmp/tls.crt

          # Create mock CA bundle configmaps (if needed)
          kubectl create configmap ca-bundle \
            --from-literal=ca-bundle.crt="# Mock CA for Kind testing" \
            -n your-namespace

          echo "✅ Created mock OpenShift secrets and configmaps"

      - name: Apply manifests
        run: |
          # Be LENIENT - pre-existing manifest issues may exist
          # Some resources may fail validation (e.g., ClusterRoleBinding missing namespace)
          # This is expected in vanilla Kind
          kubectl apply -k manifests/your-overlay -n your-namespace || \
          kubectl apply -k manifests/base -n your-namespace || true

          echo "Manifest application completed (some resources may have failed due to pre-existing issues)"

      - name: Patch deployment for Kind resource constraints
        run: |
          set -euo pipefail
          # Kind has limited memory (~2Gi total by default)
          # Reduce resource requests to fit multiple containers
          
          # EXAMPLE: For multi-container deployments like ODH Dashboard
          kubectl patch deployment your-deployment -n your-namespace --type=json -p='[
            {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "128Mi"},
            {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "50m"},
            {"op": "replace", "path": "/spec/template/spec/containers/1/resources/requests/memory", "value": "64Mi"},
            {"op": "replace", "path": "/spec/template/spec/containers/1/resources/requests/cpu", "value": "50m"}
          ]' || true

          # Reduce to 1 replica for resource constraints
          kubectl scale deployment your-deployment --replicas=1 -n your-namespace

          echo "✅ Patched deployment for Kind constraints"

      - name: Wait for pods to attempt starting
        run: |
          set -euo pipefail
          echo "Waiting for pods to be created and attempt starting..."

          # Wait up to 2 minutes for pod creation
          for i in {1..24}; do
            POD_COUNT=$(kubectl get pods -n your-namespace -l app=your-app --no-headers 2>/dev/null | wc -l)
            if [ "$POD_COUNT" -gt 0 ]; then
              echo "✅ Pod(s) created"
              break
            fi
            echo "Waiting for pods... ($i/24)"
            sleep 5
          done

          # Give pods time to pull images and start containers
          echo "Waiting 60s for image pull and container startup..."
          sleep 60

      - name: Check container status and validate
        run: |
          set -euo pipefail
          echo "::group::Pod status"
          kubectl get pods -n your-namespace -o wide
          echo "::endgroup::"

          echo "::group::Deployment status"
          kubectl describe deployment your-deployment -n your-namespace
          echo "::endgroup::"

          # Get pod details
          echo "::group::Pod events and status"
          POD=$(kubectl get pods -n your-namespace -l app=your-app -o name | head -1)
          if [ -n "$POD" ]; then
            kubectl describe -n your-namespace "$POD"
          fi
          echo "::endgroup::"

          # Check if containers started (even if they fail later)
          echo "Validating container lifecycle..."
          CONTAINER_STATUSES=$(kubectl get pods -n your-namespace -l app=your-app -o jsonpath='{.items[0].status.containerStatuses[*].state}' 2>/dev/null || echo "")

          if [ -z "$CONTAINER_STATUSES" ]; then
            echo "❌ FAIL: No container statuses found - pods may not have started"
            exit 1
          fi

          # Check for successful image pulls
          IMAGES_PULLED=$(kubectl get pods -n your-namespace -l app=your-app -o jsonpath='{.items[0].status.containerStatuses[*].imageID}' 2>/dev/null | wc -w)

          if [ "$IMAGES_PULLED" -eq 0 ]; then
            echo "❌ FAIL: No images were pulled successfully"
            exit 1
          fi

          echo "✅ PASS: Containers attempted to start, $IMAGES_PULLED image(s) pulled"
          echo "Container states: $CONTAINER_STATUSES"

          # Show logs from main container (even if it failed)
          echo "::group::Container logs"
          kubectl logs -n your-namespace "$POD" -c your-main-container --tail=100 || echo "No logs available"
          echo "::endgroup::"

      - name: Cleanup
        if: always()
        run: kind delete cluster --name test-cluster

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

##### Step 2.3b: Operator Reconciliation Smoke Test (controller-runtime operators)

The "run the containers" strategy above validates the **workload** manifests. If the
repo also ships a **controller-runtime operator** that reconciles a CRD into those
manifests (e.g. odh-dashboard's `dashboard-operator` reconciling a `Dashboard` CR),
add a second, stronger check: actually run the operator and prove it reconciles a CR.
This catches RBAC gaps, scheme/registration panics, and broken render paths that pure
`kubectl apply` never exercises.

**Five rules learned the hard way (odh-dashboard PR #9658 review):**

1. **Extract inline manifests to checked-in files — never heredoc them in the workflow.**
   A `kubectl apply -f - <<EOF ... EOF` operator Deployment/RBAC block is unreviewable,
   unlintable, and untestable. Put the sim-only operator `Deployment`, `ServiceAccount`,
   and `ClusterRoleBinding` in a dedicated dir — e.g. `.github/pr-build-simulation/` —
   **not** under `manifests/` (so kustomize/overlay validation never picks them up or
   ships them) and `kubectl apply -f` them. Bind the operator's **real** ClusterRole
   (from `config/rbac/role.yaml`) so the smoke test exercises the shipped RBAC, not a
   hand-copied subset that drifts.

2. **Dump diagnostics inline on rollout failure — a later `if: failure()` step is too late.**
   `kubectl rollout status deployment/<operator> --timeout=120s` under `set -e` aborts the
   step on timeout, and the exact failure this phase exists to catch (controller panic,
   scheme/registration error) surfaces as a bare `timed out waiting for the condition`.
   Wrap it so the diagnostics run in the **same** step:

   ```yaml
   - name: Deploy operator
     run: |
       set -euo pipefail
       kubectl apply -f .github/pr-build-simulation/operator-deployment.yaml
       if ! kubectl rollout status deployment/dashboard-operator -n opendatahub --timeout=120s; then
         echo "::group::Operator rollout failed — diagnostics"
         kubectl describe deployment/dashboard-operator -n opendatahub || true
         kubectl get pods -n opendatahub -o wide || true
         kubectl logs deployment/dashboard-operator -n opendatahub --tail=200 || true
         kubectl logs deployment/dashboard-operator -n opendatahub --previous --tail=200 || true
         kubectl get events -n opendatahub --sort-by=.lastTimestamp | tail -30 || true
         echo "::endgroup::"
         exit 1
       fi
   ```

3. **Preserve the "we test the PR image" invariant — point the operator at the PR image,
   don't patch the workload.** When the operator reconciles, it server-side-applies its
   base manifests as field owner `dashboard-operator`. The merge strategy typically
   preserves only `spec.replicas` and `containers[].resources` — **not** `image` or
   `imagePullPolicy`. So any pre-patch of the dashboard Deployment to the loaded PR tag /
   `Never` is silently reverted on the next reconcile, and the node starts pulling the
   baked-in upstream default (`quay.io/opendatahub/odh-dashboard:main`) mid-poll. Patching
   `imagePullPolicy` is futile for the same reason. Instead, set the operator's image
   resolution env to the already-loaded PR tag so the operator itself applies it:

   ```yaml
   # in .github/pr-build-simulation/operator-deployment.yaml
   env:
     - name: RELATED_IMAGE_ODH_DASHBOARD_IMAGE   # the env the operator resolves the image from
       value: odh-dashboard:odh-test              # the tag already loaded into Kind
   ```

   The reconciled dashboard pod may then show a benign `ErrImagePull` on the local-only
   tag (there is no registry copy) — that's fine: this phase asserts on **operator
   reconcile evidence** (finalizer present, `status.observedGeneration` advanced), not on
   the dashboard pod becoming Ready. Document that in a comment on the CR step.

4. **Add a `free-disk-space` step to any job that loads more than one image.** The
   operator-integration job loads *both* the app image and the operator image into Kind;
   without freeing disk (as the docker-build jobs already do) the runner can fill up and
   the image loads or `:main` pull fail with confusing ENOSPC errors:

   ```yaml
   - name: Free disk space
     uses: ./.github/actions/free-disk-space   # or easimon/maximize-build-space, etc.
   ```

5. **Assert on reconcile evidence, not pod readiness.** After creating the CR, poll for
   the operator's finalizer on the CR and for `status.observedGeneration` catching up to
   `metadata.generation`, and assert the operator pod has `0` restarts. That proves the
   controller ran a full reconcile loop without crashing — the thing this phase exists to
   verify — in a vanilla Kind cluster that can never make the app pod Ready.

   ```yaml
   - name: Create Dashboard CR and verify reconcile
     run: |
       set -euo pipefail
       # NOTE: the operator SSA-applies the PR image tag (odh-test), NOT :main, so no
       # large upstream pull happens here. The dashboard pod may sit in ErrImagePull on
       # the local-only tag — benign; we assert only on operator reconcile evidence below.
       kubectl apply -f .github/pr-build-simulation/dashboard-cr.yaml
       for i in $(seq 1 30); do
         gen=$(kubectl get dashboard default -o jsonpath='{.metadata.generation}' 2>/dev/null || echo "")
         obs=$(kubectl get dashboard default -o jsonpath='{.status.observedGeneration}' 2>/dev/null || echo "")
         fin=$(kubectl get dashboard default -o jsonpath='{.metadata.finalizers}' 2>/dev/null || echo "")
         if [ -n "$obs" ] && [ "$obs" = "$gen" ] && [ -n "$fin" ]; then
           echo "✅ Reconciled: observedGeneration=$obs, finalizer=$fin"
           break
         fi
         echo "waiting for reconcile... ($i/30) gen=$gen obs=$obs"
         sleep 5
       done
       restarts=$(kubectl get pods -n opendatahub -l app.kubernetes.io/name=dashboard-operator \
         -o jsonpath='{.items[0].status.containerStatuses[0].restartCount}')
       [ "$restarts" = "0" ] || { echo "❌ operator restarted $restarts time(s)"; exit 1; }
   ```

**Certs in Kind:** the real `config/manager/manager.yaml` usually mounts webhook/metrics
cert secrets (cert-manager) that don't exist in Kind. In the sim-only Deployment, run the
manager with the webhook disabled (its default) and metrics over HTTP
(`--secure-metrics=false`) so no certs are required — enough to prove the controller
starts and reconciles.

**External operator variant (the operator lives in another repo)**

model-registry is the canonical case: it has no controller of its own, and
`opendatahub-operator` maps component `aihub` to
`opendatahub-io/model-registry-operator@<ref>`. That operator's
`RELATED_IMAGE_ODH_MODEL_REGISTRY_IMAGE` decides which server image lands in the
cluster. Detecting "no controller in this repo" and skipping operator integration there would
leave the entire shipping path untested — which is exactly what happened.

Apply the operator from a pinned commit and let it render the workload:

```bash
CTX="kind-${CLUSTER_NAME}"
kubectl --context "$CTX" apply -k \
  "https://github.com/<org>/<operator>.git//config/default?ref=<sha>"
kubectl --context "$CTX" -n <operator-ns> set env deployment/<operator-deploy> \
  RELATED_IMAGE_<COMPONENT>_IMAGE="$SERVER_IMAGE"
kubectl --context "$CTX" -n <operator-ns> rollout status \
  deployment/<operator-deploy> --timeout=300s
kubectl --context "$CTX" apply -k \
  "https://github.com/<org>/<operator>.git//config/samples/<sample>?ref=<sha>"
kubectl --context "$CTX" wait --for=condition=Available <crd>/<name> --timeout=300s
```

`//` separates the repository from the path *inside* it; kustomize documents
that form. Current `kubectl` also resolves the single-slash form for a
`.git`-suffixed URL — both were verified against the same pinned ref while
writing this — so this is about matching the documented grammar rather than
fixing a live breakage. Prefer `//` anyway: without it the boundary between
repository and path is inferred, and the grammar does not oblige a future
kustomize to keep inferring it.

`?ref=<sha>` makes kustomize clone shallowly at that ref. A full 40-character
commit is reachable that way, but a branch name can resolve to different
content later and a short SHA may fail to fetch at all. Always pin the full
commit. If the clone fails behind a proxy, pass
`--load-restrictor LoadRestrictionsNone` only after confirming the failure is
a path-restriction error and not a network error.

Pass `--context` on **every** `kubectl` call in this phase, including any
diagnostic dump. When the cluster was reused rather than created, the current
context still points wherever it did before, and an unqualified command
installs the operator — and then deletes things — in an unrelated cluster.

Then assert, in order:

1. The rendered workload image equals the PR tag. This is the only proof the PR
   image is under test; without it the job passes while exercising whatever
   `:latest` points at. `<workload>` is usually named after the CR, not the
   component — select by the label the operator template sets and fail if it
   matches nothing:

   ```bash
   set -euo pipefail
   workload=$(kubectl --context "$CTX" -n <ns> get deployment \
     -l component=<component> -o jsonpath='{.items[0].metadata.name}')
   # Fail loudly on no match. `kubectl get deployment ""` exits non-zero with an
   # unhelpful message, and a later `[ "$rendered" = "$SERVER_IMAGE" ]` on two
   # empty strings passes -- the assertion must never be satisfiable by absence.
   if [ -z "$workload" ]; then
     echo "❌ no workload matched -l component=<component> in namespace <ns>"
     exit 1
   fi
   rendered=$(kubectl --context "$CTX" -n <ns> get deployment "$workload" \
     -o jsonpath='{.spec.template.spec.containers[0].image}')
   if [ -z "$rendered" ]; then
     echo "❌ deployment/$workload has no image in the pod template"
     exit 1
   fi
   if [ "$rendered" != "$SERVER_IMAGE" ]; then
     echo "❌ rendered image '$rendered' != PR image '$SERVER_IMAGE'"
     exit 1
   fi
   ```

   Assert against the **running** container, not just the deployment spec: after
   `set env`, the old ReplicaSet can still satisfy `Available` while the new pod
   is stuck. Wait on `rollout status` first, then compare
   `.status.containerStatuses[0].image` on the pod, and fail if the pod UID is
   unchanged from before the env edit.
2. The CR carries the operator's finalizer.
3. The workload pods report `restartCount == 0`, keyed by pod UID and container
   name. Summing counts across pods hides a restart: two restarts on pod A and
   one on its replacement B total `1`, which reads as "healthy". Snapshot the
   per-identity counts, then fail on any increase, on any new or missing pod,
   and on an empty pod list.

**The failure this catches:** model-registry's existing `build-image-pr.yml` set
`REST_IMAGE`, an env var the operator never read, so the workflow tested
`quay.io/opendatahub/model-registry:latest` on every PR while appearing to test
the build. Grep the operator source for the constant it actually reads
(`internal/controller/config/defaults.go` in that repo) rather than inferring the
variable name from the workflow that came before.

Pin the operator commit. A moving branch makes the phase fail for reasons
unrelated to the PR, and a pin lets you bump it deliberately.

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

##### Step 2.4b: Validate the overlays the operator actually renders (not just the obvious ones)

`find manifests -name kustomization.yaml` misses two failure classes:

1. **Overlays the operator renders at runtime but that live outside the obvious tree.**
   If a controller-runtime operator kustomize-renders specific paths, enumerate *those*
   paths from the operator source — don't guess. For odh-dashboard the operator renders
   (from `dashboard-operator/internal/controller/*.go`):
   `manifests/base`, `manifests/odh`, `manifests/rhoai`,
   `manifests/observability/{odh,rhoai}`,
   `manifests/maas-consumer-portal-consolelink/rhoai`, and **every**
   `manifests/modules/<slug>/` that has a `kustomization.yaml`. A broken `resources:` path
   in `manifests/modules/<slug>/kustomization.yaml` otherwise passes the job named
   "Manifest Validation" and fails only on a live cluster. **Discover modules dynamically**
   so new ones are covered automatically:

   ```yaml
   - name: Validate operator-rendered overlays
     run: |
       set -euo pipefail
       OVERLAYS=(
         manifests/base manifests/odh manifests/rhoai
         manifests/observability/odh manifests/observability/rhoai
         manifests/maas-consumer-portal-consolelink/rhoai
       )
       # dynamic module discovery — future-proof for new modules
       while IFS= read -r kfile; do OVERLAYS+=("$(dirname "$kfile")"); done \
         < <(find manifests/modules -mindepth 2 -maxdepth 2 -name kustomization.yaml | sort)
       for o in "${OVERLAYS[@]}"; do
         echo "== $o =="
         kustomize build "$o" > "/tmp/$(echo "$o" | tr / _).yaml"
       done
   ```

   > Verify these paths against the operator's Go source for the repo you're onboarding —
   > they drift. (odh-dashboard note: `manifests/distributions/maas-consumer-portal` is a
   > **stale** path; the operator renders `manifests/maas-consumer-portal-consolelink/rhoai`.)

2. **Schema-level typos hidden by `-ignore-missing-schemas`.** kubeconform with
   `-ignore-missing-schemas` turns a misspelled kind into a silent pass: `kind: Deploymnet`
   is just counted as "no schema found," exit 0. Overlays that are never `kubectl apply`-ed
   anywhere ship the typo undetected. Don't assert on a raw skip *count* (churns with every
   CRD added) — instead run `-output json` and **fail if any skipped resource is a
   Kubernetes built-in** (core group `""`, `*.k8s.io`, or `apps`/`batch`/`policy`/
   `autoscaling`/`extensions`), which is exactly what a typo in a built-in kind produces.
   CRD-backed kinds (Dashboard, ConsoleLink, …) are still allowed to skip.

   ```yaml
   - name: kubeconform schema validation (typo guard)
     run: |
       set -euo pipefail
       for f in /tmp/*.yaml; do
         set +e
         kubeconform -strict -ignore-missing-schemas -verbose \
           -kubernetes-version 1.31.0 -output json "$f" > /tmp/kc.json 2> /tmp/kc.err
         status=$?
         set -e
         # Any non-zero exit is a failure: invalid or errored resources, but
         # also a malformed input or a crashed binary. Never key off the JSON
         # alone — a partial report can omit both status strings.
         if [ "$status" -ne 0 ]; then
           cat /tmp/kc.err /tmp/kc.json >&2
           echo "❌ kubeconform failed on $f (exit $status)"; exit 1
         fi
         if [ ! -s /tmp/kc.json ]; then
           cat /tmp/kc.err >&2
           echo "❌ kubeconform produced no report for $f"; exit 1
         fi
         # -verbose is required for statusSkipped records. It also records the
         # CRDs themselves, which have no standalone schema — allow that exact
         # (apiVersion, kind) pair, never a whole group. Compare the fields, not
         # the whole object: skipped records also carry a status field.
         BAD=$(jq -r '
           .resources[] | select(.status=="statusSkipped")
           | select((.version == "apiextensions.k8s.io/v1" and .kind == "CustomResourceDefinition") | not)
           | . as $r
           | (if ($r.version|contains("/")) then ($r.version|split("/")[0]) else "" end) as $g
           | select($g=="" or ($g|endswith(".k8s.io")) or ($g|IN("apps","batch","policy","autoscaling","extensions")))
           | "  \($r.kind) (\($r.version))"' /tmp/kc.json)
         if [ -n "$BAD" ]; then
           echo "❌ built-in kind(s) skipped — likely an apiVersion/kind typo:"; echo "$BAD"; exit 1
         fi
       done
   ```

   `|| true` on the kubeconform call is the single most common way this check
   ends up decorative: it discards the non-zero exit, so `statusInvalid` and
   `statusError` never reach the summary and the job stays green. Fail on the
   exit status alone and use the JSON report only for the `statusSkipped`
   allow-list; a partial report with neither status string must not pass.

   Pin `kubeconform` and `kubernetes-version` (e.g. 1.31.0) so results are reproducible.

##### Step 2.4c: Validate the rendered manifest against the binary it starts

Rendering an overlay only proves it is valid YAML. It does not prove the
container it describes can start. Two failure classes survive `kustomize build`
and `kubeconform` completely:

1. **The Deployment passes a flag the binary does not define.** The container
   exits during flag parsing and never reconciles. RHOAIENG-100779: the RHOAI
   overlay passed `--metrics-cert-path`, the operand image did not define it,
   `feast-operator-controller-manager` crash-looped and `default-feastoperator`
   stayed `Not Ready`. Nothing in either repository compared the two.
2. **A container declares the same env var name twice.** The API server keeps
   only the last entry, so the rendered overlay and the effective configuration
   silently disagree. RHOAIENG-57579: duplicate `RELATED_IMAGE_CRON_JOB` on the
   controller-manager Deployment.

Both are cheap to check and neither needs a cluster.

**Duplicate env vars** — no extra tooling beyond PyYAML:

```python
for _, doc in yaml.safe_load_all(handle):
    if doc.get("kind") not in {"Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"}:
        continue
    for container in doc["spec"]["template"]["spec"].get("containers", []):
        names = [e["name"] for e in container.get("env", []) if "name" in e]
        duplicates = {n for n in names if names.count(n) > 1}
```

**Flag contract** — build the operator image, read its flag set, compare:

```yaml
- name: Build the operator and verify its flag contract
  run: |
    set -euo pipefail
    # flags the overlays actually pass
    python3 scripts/manifest_contract.py manager-flags out/rhoai.yaml out/odh.yaml \
      | sort -u > used.txt
    # flags the binary actually defines
    docker build -f infra/feast-operator/Dockerfile -t operator:pr infra/feast-operator
    docker run --rm operator:pr --help > help.txt 2>&1 || true
    python3 scripts/manifest_contract.py help-flags help.txt | sort -u > known.txt
    missing="$(comm -23 used.txt known.txt)"
    [ -z "$missing" ] || { echo "undefined flag(s): $missing"; exit 1; }
```

`manager-flags` should read only the `controller-manager` Deployment and only
concatenate `command` + `args` of its containers — otherwise flags belonging to
operand containers produce false failures.

**Rules:**

- Compare flag *names* only, never values. A value mismatch is a config bug the
  overlay intentionally parameterises; a missing name is a crash.
- Skip the comparison when the rendered manifest has no flags, and fail closed
  if `--help` produced no output — an empty `known.txt` would otherwise make
  every comparison pass.
- This check is only meaningful when the operator binary and the overlays are
  built from the same commit. In a repo that ships both (like feast) it catches
  "overlay edited, `cmd/main.go` not updated". It cannot catch a new overlay
  shipped against an older published operand image — that is the cross-repo
  case, and it is why Step 2.5 exists.
- Negative-test it before trusting it: add a bogus flag to the overlay and a
  duplicated env var to a fixture, confirm both fail, then revert.

##### Step 2.4d: Check generated artifacts, RBAC identity, and the manifest path contract

Three more failure classes survive every check above. All three are cheap and
none needs a cluster.

**1. A generated artifact that CI never regenerates.**

When a repo generates something it ships — a Helm chart (`make helm`), an OLM
bundle (`make bundle`), a manifest bundle — and nothing in CI regenerates and
diffs it, the artifact silently stops matching its source. For
`feast-module-operator`, `config/chart` is generated from `config/default` by
`make helm` and consumed by `opendatahub-operator` through
`manifests-config.yaml` (`sourcePath: config/chart`). `ci.yaml` runs
`make manifests generate` in `Verify Generated Files`, which covers CRDs and
deepcopy code but **not** the chart. RHOAIENG-96436 ("odh-feast-operator —
manifests are out of sync") was an RC blocker for exactly this reason.

Detect the seam before writing the check:

```bash
# a Makefile target whose name suggests generation, writing into a tracked dir
grep -nE '^[a-zA-Z0-9_-]+:' Makefile | grep -iE 'helm|bundle|manifests|generate'
# who consumes that directory?
gh search code "sourcePath: <dir>" --filename=manifests-config.yaml --limit 10
```

Set `BASE_REF` to the PR base commit (in the workflow, pass
`${{ github.event.pull_request.base.sha }}`). The check fetches it when the
checkout is shallow. Regenerate both `HEAD` and the base, compare what each
expects to generate, and only warn for drift already present on the base:

```bash
set -euo pipefail
tmp="$(mktemp -d)"
trap "rm -rf '$tmp'" EXIT
base_ref="${BASE_REF:?set BASE_REF to the PR base commit}"

# actions/checkout defaults to fetch-depth: 1, so the base commit is usually
# absent even though the PR event carries its SHA.
if ! git rev-parse --verify "$base_ref^{commit}" >/dev/null 2>&1; then
  git fetch --no-tags --depth=1 origin "$base_ref"
  base_ref="$(git rev-parse FETCH_HEAD^{commit})"
fi
if ! git rev-parse --verify "$base_ref^{commit}" >/dev/null 2>&1; then
  echo "::error::base ref $base_ref is unavailable after fetch" >&2
  exit 1
fi

for ref in HEAD "$base_ref"; do
  label=head
  [ "$ref" = "$base_ref" ] && label=base
  mkdir -p "$tmp/$label" "$tmp/$label-committed"
  git archive "$ref" | tar -x -C "$tmp/$label"
  if [ -d "$tmp/$label/config/chart" ]; then
    cp -R "$tmp/$label/config/chart/." "$tmp/$label-committed/"
  fi
  if ! ( cd "$tmp/$label" && make helm >"$tmp/make-$label.log" 2>&1 ); then
    cat "$tmp/make-$label.log" >&2
    echo "::error::make helm failed on $ref; the chart cannot be verified" >&2
    exit 1
  fi
  if [ ! -d "$tmp/$label/config/chart" ]; then
    echo "::error::$ref generated no config/chart" >&2
    exit 1
  fi

  # Record "path<TAB>generated digest" for every stale file. Keying on the
  # content the ref generates, not just the path, catches a PR that changes
  # what a file should contain while it stays committed stale. Walk files with
  # find: config/chart nests templates/*.yaml, which a top-level glob misses.
  : > "$tmp/$label.files"
  {
    ( cd "$tmp/$label-committed" && find . -type f -print )
    ( cd "$tmp/$label/config/chart" && find . -type f -print )
  } | sed 's|^\./||' | LC_ALL=C sort -u | while IFS= read -r rel; do
    committed="$tmp/$label-committed/$rel"
    generated="$tmp/$label/config/chart/$rel"
    if cmp -s "$committed" "$generated"; then
      continue
    fi
    # sha256sum, not cksum: this is content identity, not an integrity check,
    # and the generated file may have been deleted by this ref.
    if [ -f "$generated" ]; then
      digest="$(sha256sum "$generated" | cut -d' ' -f1)"
    else
      digest="deleted"
    fi
    printf '%s\t%s\n' "$rel" "$digest" >> "$tmp/$label.files"
  done
  LC_ALL=C sort -o "$tmp/$label.files" "$tmp/$label.files"
  diff -ru "$tmp/$label-committed" "$tmp/$label/config/chart" > "$tmp/$label.diff" 2>&1 || true
done

new_drift="$(LC_ALL=C comm -23 "$tmp/head.files" "$tmp/base.files")"
if [ -n "$new_drift" ]; then
  cat "$tmp/head.diff" >&2
  echo "::error::config/chart drift introduced by this PR:" >&2
  printf '%s\n' "$new_drift" | cut -f1 >&2
  exit 1
fi
if [ -s "$tmp/head.files" ]; then
  echo "::warning::config/chart is already drifted on $base_ref: $(cut -f1 "$tmp/head.files" | paste -sd, -)"
  cat "$tmp/head.diff"
fi
```

Pass the repository's prebuilt tool overrides (for example `KUSTOMIZE=...` or
`HELM=...`) to `make` when it supports them, so the job does not depend on a
network-backed `go run`.

Rules:

- **Warn, do not fail, on pre-existing drift.** If `main` is already drifted, a
  hard failure blocks every PR on day one and the check gets removed. Compare
  the base and head drift sets: warn for files that are already stale on the
  base, and fail when the PR changes what a file should generate while it stays
  committed stale.
- **A failed generator is a failure, not a skip.** If `make helm` cannot run,
  exit non-zero; a green job that never generated the artifact is worse than a
  red one.
- Print *which files* drift. "chart is out of sync" is not actionable;
  `values.yaml`, the NetworkPolicy template, and a template that `make helm` no
  longer produces are.
- Regenerate from `git archive <ref>` for both `HEAD` and the base, not the
  working tree, so the check compares what is committed.
- A generation target that also regenerates CRDs and deepcopy code (`helm:
  manifests generate`) is fine — only diff the artifact directory.
- **Fetch the base commit inside the check.** `actions/checkout` defaults to
  `fetch-depth: 1`, so a workflow that assumes the base is present fails before
  it compares anything. Fetch the SHA the PR event provides.

**2. RBAC bindings that name an identity the manifests never create.**

A kustomize `namePrefix` is applied by the kustomization that declares it.
Kustomize's name-reference transformer updates a `RoleBinding` or
`ClusterRoleBinding` subject when the referenced `ServiceAccount` is part of the
same rendered set; a binding rendered without that `ServiceAccount` keeps the
literal name. In `feast-module-operator`, rendering `overlays/openshift` alone
leaves `controller-manager`; rendering `overlays/rhoai` with `../../default`
produces `feast-operator-controller-manager`. The failure is a binding rendered
or applied without the prefixed `ServiceAccount`, not `namePrefix` ignoring
subjects in general. RHOAIENG-100514 / RHOAIENG-100515:
`tls_clusterrolebinding.yaml` still bound `controller-manager` while the
deployed `ServiceAccount` was `feast-operator-controller-manager`; the operator
could not read `apiservers.config.openshift.io`, `default-feastoperator` stayed
`Not Ready`, and the `DataScienceCluster` was never Ready (RHOAIENG-99631 is the
same outage from the platform side).

```python
# docs is the union of every rendered manifest applied to the cluster together.
service_accounts = set()
for d in docs:
    if d.get("kind") != "ServiceAccount":
        continue
    meta = d.get("metadata") or {}
    if meta.get("name"):
        service_accounts.add((meta.get("namespace") or "", meta["name"]))

def resolves(namespace, name):
    # A ServiceAccount rendered without metadata.namespace is applied into the
    # overlay's target namespace, which the union does not record. Match it by
    # name; render explicit namespaces if you need cross-namespace precision.
    return (namespace, name) in service_accounts or ("", name) in service_accounts

for d in docs:
    kind = d.get("kind")
    meta = d.get("metadata") or {}
    namespace = meta.get("namespace") or ""
    if kind in {"RoleBinding", "ClusterRoleBinding"}:
        for s in d.get("subjects") or []:
            if s.get("kind") != "ServiceAccount":
                continue
            name = s.get("name")
            if kind == "ClusterRoleBinding":
                # Cluster-scoped bindings have no namespace to inherit: an
                # omitted subject namespace is invalid, not defaulted.
                if not s.get("namespace"):
                    fail(f"{kind}/{meta.get('name')} binds {name} with no subject namespace")
                    continue
                account_ns = s["namespace"]
            else:
                # A RoleBinding subject with no namespace defaults to the
                # binding's namespace (Kubernetes API semantics).
                account_ns = s.get("namespace") or namespace
            if not resolves(account_ns, name):
                fail(f"{kind}/{meta.get('name')} binds {account_ns}/{name}")

    spec = d.get("spec") or {}
    pod_spec = None
    if kind in {"Deployment", "StatefulSet", "DaemonSet", "Job"}:
        pod_spec = (spec.get("template") or {}).get("spec")
    elif kind == "CronJob":
        job = (spec.get("jobTemplate") or {}).get("spec") or {}
        pod_spec = (job.get("template") or {}).get("spec")
    if pod_spec:
        sa = pod_spec.get("serviceAccountName")
        if sa and not resolves(namespace, sa):
            fail(f"{kind}/{meta.get('name')} runs as {sa}")
```

Load every rendered manifest that is applied together into one `docs` list and
run the check on that union. Do not run it once per overlay: `openshift` alone
has the binding but no `ServiceAccount`, while `default` has the
`ServiceAccount` but no binding. Raw kustomize directories do not apply
`namePrefix`, so the mismatch is invisible there. Skip the whole check only
when the union contains no `ServiceAccount`; do not skip an individual overlay
that has a binding but no `ServiceAccount`. Render explicit `metadata.namespace`
values when you can: the name-only fallback for an unqualified `ServiceAccount`
cannot distinguish two same-named accounts in different namespaces.

**3. The manifest path contract between image, chart, and binary.**

Three files that never reference each other have to agree:

| File | Statement |
|---|---|
| `Containerfile` | `COPY --from=builder /workspace/config/manifests/ /manifests/` |
| chart `initContainer` | `cp -r /manifests/. /opt/manifests/` |
| Deployment `env` | `ODH_MODULE_OPERATOR_MANIFESTS_PATH=/opt/manifests` |

Change one and the operator starts with no operand overlays. Parse all three and
compare; this is the generalised form of the model-registry manifest-path
handoff. Fixtures: RHOAIENG-99568 (model-registry shipped to
`/opt/manifests/modelregistry`, operator read `/opt/manifests/aihub`) and the
`feast-module-operator` equivalent, which passes today.

```python
import os, posixpath, shlex

def normalize(path):
    return posixpath.normpath(path.rstrip("/")) or "/"

def where(owner):
    meta = owner.get("metadata") or {}
    return f"{owner.get('kind')}/{meta.get('name')}"

def pod_specs(docs):
    for d in docs:
        kind, spec = d.get("kind"), d.get("spec") or {}
        if kind in {"Deployment", "StatefulSet", "DaemonSet", "Job"}:
            yield d, (spec.get("template") or {}).get("spec") or {}
        elif kind == "CronJob":
            job = (spec.get("jobTemplate") or {}).get("spec") or {}
            yield d, (job.get("template") or {}).get("spec") or {}

# 1. Containerfile: the COPY --from that stages the operand manifests.
image_dir = None
for line in open("Containerfile", encoding="utf-8"):
    line = line.strip()
    if not line.upper().startswith("COPY "):
        continue
    argv = shlex.split(line, comments=True)
    if not any(a.startswith("--from=") for a in argv):
        continue  # build-context COPY: the image build verifies it, not this check
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) >= 2 and "manifests" in args[0]:
        image_dir = normalize(args[-1])
if image_dir is None:
    fail("Containerfile has no COPY --from of the operand manifests")

# 2. Chart initContainer: cp <staged tree> <shared volume>.
chart_source = chart_dest = None
for owner, pod in pod_specs(docs):
    for container in pod.get("initContainers") or []:
        argv = list(container.get("command") or []) + list(container.get("args") or [])
        if not argv:
            continue
        shell_flags = [a for a in argv[1:] if a.startswith("-") and not a.startswith("--")]
        if os.path.basename(argv[0]) in {"sh", "bash"} and any("c" in a[1:] for a in shell_flags):
            fail(f"{where(owner)}: cp behind a shell string cannot be verified")
        if os.path.basename(argv[0]) != "cp":
            continue  # command: [echo] with cp in args copies nothing
        target_dir = any(
            a.startswith("--target-directory")
            or (a.startswith("-") and not a.startswith("--") and "t" in a[1:])
            for a in argv
        )
        if target_dir:
            fail(f"{where(owner)}: cp -t is not handled; use cp SRC DEST")
        rest = [a for a in argv[1:] if not a.startswith("-")]
        if len(rest) != 2:
            fail(f"{where(owner)}: expected cp SRC DEST, got {argv}")
        chart_source, chart_dest = rest
if chart_source is None:
    fail("chart has no initContainer cp of the operand manifests")
if normalize(chart_source) != image_dir:
    fail(f"chart copies {chart_source}, image stages {image_dir}")

# 3. Deployment env: the path the binary reads.
env_path = None
for owner, pod in pod_specs(docs):
    for container in pod.get("containers") or []:
        for env in container.get("env") or []:
            if str(env.get("name", "")).endswith("MANIFESTS_PATH"):
                env_path = env.get("value")
if env_path is None:
    fail("no *MANIFESTS_PATH env var on the Deployment")
if normalize(chart_dest) != normalize(env_path):
    fail(f"chart copies to {chart_dest}, binary reads {env_path}")
```

**Two false positives to avoid:**

- `COPY --from=<stage> <path> <dest>` references an earlier build stage, not the
  build context. If you also check that build-context sources exist, skip every
  `COPY` line containing `--from=`, or the checker fails on any multi-stage
  Dockerfile.
- Parse argv, not strings. The copier must have `cp` as its executable
  (`os.path.basename(argv[0]) == "cp"`); an init container with `command: [echo]`
  and `cp` in its arguments copies nothing. The snippet filters flag tokens,
  handles `cp -r SRC DEST`, and fails loudly on `cp -t DIR SRC` and
  `sh -c "cp ..."` rather than silently skipping them.

**Do not export environment variables that the repo's Makefile defines.**
`KUSTOMIZE_VERSION ?= v5.8.1` does **not** apply when the environment already
sets `KUSTOMIZE_VERSION`; `?=` only fills an unset value. A workflow that
exported the simulator's tool version as `KUSTOMIZE_VERSION: '5.8.1'` (no `v`)
made the repo's own `make helm` run `go run
sigs.k8s.io/kustomize/kustomize/v5@5.8.1` and fail with `unknown revision`.
Prefix simulator variables (`SIM_KUSTOMIZE_VERSION`, `SIM_HELM_VERSION`, …) so
they cannot shadow anything the Makefile reads.

**A generation step that fails is a failure, not a skip.** The first version of
the drift check warned and returned 0 when `make helm` failed, so the job went
green while its main assertion never ran. Capture the generator output, print
it, and exit non-zero. The distinction is: *drift* warns because it pre-exists,
*inability to generate* fails because there is no evidence either way.

**Also warn when `.tekton/*pull-request.yaml` does not set `build-platforms`.**
The shared pipeline then defaults to `linux/x86_64` only, and a single-arch
manifest list surfaces as `ImagePullBackOff` on ppc64le/arm64
(RHOAIENG-79767). Warn rather than fail: the fix is a PipelineRun change, not
something a PR can infer.

#### Step 2.5: Emit the Platform Operator Handoff (always)

Run this even when the repo has no controller. The output goes into the
simulator PR description; it never becomes new test code in this repo.

**1. Find the consuming operator and its component key**

```bash
gh search code "<image-name-without-tag>" --filename=manifests-config.yaml --limit 10
```

The YAML key above the matching `repo:` is the component key. Example:
`aihub` maps to `opendatahub-io/model-registry-operator` with
`sourcePath: config`.

**2. Check whether the operator already tests this component**

```bash
rg -n "<component-key>" tests/e2e/controller_test.go
rg -n "func <component>TestSuite" tests/e2e/
```

If the suite is registered in the `Components` TestGroup, the assertions already
exist. Do not write them again.

**3. Check whether the Kind target actually runs it**

```bash
rg -n "E2E_TEST_COMPONENT" Makefile
rg -n "paths:" -A30 .github/workflows/test-kind-odh-e2e.yaml | head -40
```

`make e2e-test-xks` usually hardcodes `E2E_TEST_COMPONENT="kserve"`. A
registered suite that is absent from that list never runs on Kind.

The list is **space**-separated, not comma-separated: it is read from the
environment and split with `strings.Fields`, so `"kserve,aihub"` collapses into
a single malformed name and validation fails before any test runs. Check for a
regression test that pins the format before you edit it.

**4. Emit the follow-up**

| Suite registered | In Kind target | Follow-up |
|---|---|---|
| no | — | File a coverage ticket against the operator; the simulator cannot substitute |
| yes | yes | None |
| yes | no | Two-line diff: add the component to `E2E_TEST_COMPONENT`, add its paths to the Kind workflow `paths:` |

```markdown
## Platform operator coverage (not in this PR)

`<component>` is reconciled by `<operator>`, so `DataScienceCluster`
conditions cannot be asserted from this repository.

- Suite: `tests/e2e/<component>_test.go` — <registered|missing>
- Kind target: `make e2e-test-xks` — <included|excluded by E2E_TEST_COMPONENT>
- Required change: add the component to `E2E_TEST_COMPONENT` in the
  `e2e-test-xks` target of `Makefile`, and add its paths to the Kind
  workflow's `paths:` filter.
```

Do not report `DataScienceCluster` coverage in the simulator summary.

#### Step 2.5c: Check the repo's own operator e2e (if it has one)

A repository that ships an operator usually has a Kind/operator e2e suite.
Two questions decide whether that suite gives you image coverage at all:

```bash
# 1. Does it deploy the operator from source, or from a prebuilt image?
rg -n "DeployOperatorFromCode|make deploy|IMG=|FS_IMG=" infra/*/test .github/workflows

# 2. Is it gated behind a label, or a path filter that excludes the operand?
rg -n "labels\.|ok-to-test|lgtm|approved|paths:" .github/workflows/*operator*e2e*.yml
```

- **Source-built** (`DeployOperatorFromCode`, `make docker-build` inside the
  test) proves the code compiles and reconciles. It never runs the image the
  PipelineRun publishes, so add an operator-image phase.
- **Label-gated** means the suite is not part of standard CI. Removing the gate
  is in scope — it is the only coverage that exercises a real cluster.
- **Path-gated to the operator directory alone** misses changes to the operand
  images the operator renders. Add those paths.

Expect an unlabelled suite to be red for reasons unrelated to your diff the
first time it runs: it has never run on every PR, so its flakes have never been
paid down. Compare against a sibling matrix leg or spec, and say so in the PR
rather than chasing it.

#### Step 2.6: Prove the Checks Catch Them (always)

A check you have never seen fail is a check you have not tested. Every row from
Step 1.8 that you classified as catchable here needs a demonstration that the
generated check actually goes red on that failure. Reading the code and
concluding "this would have caught it" is not evidence, and reviewers are right
to reject it.

**Fault-inject each check on a scratch branch, then revert.** One mutation per
row, sized so that only the intended assertion can fire:

| Ticket class | Injection | Assertion that must fail |
|---|---|---|
| Build-time, Go | add an `import` of a module absent from `go.sum` | offline `GOPROXY=off` build |
| Build-time, Python | add a package to `requirements.txt` that the wheelhouse cannot supply | `--no-index` resolve |
| Lockfile | delete a `resolved` / `integrity` field from a `package-lock.json` entry | lockfile validator |
| Workspace COPY | delete one `COPY packages/<x>` line from the Dockerfile | workspace dependency check |
| Manifest path | rename the directory the operator's `sourcePath` points at | cross-repo contract check |
| Rendered image | set the `RELATED_IMAGE_*` variable to `:latest` while asserting the PR tag | rendered-image assertion |
| Reconcile | not catchable here — must appear under the operator handoff | operator repo e2e |

Record the failing output verbatim. "It failed with the expected message" is
not proof; the message is:

```
❌ rendered image 'quay.io/opendatahub/model-registry:latest' != PR image 'quay.io/...@sha256:...'
```

Three rules keep this honest:

- **Revert the injection.** It must not be part of the PR. If the check passes
  after the revert, that is the positive path working. If it passed *with* the
  injection, you proved nothing and the check itself needs fixing.
- **Never inject into the default branch or a shared fork.** Use a throwaway
  branch and delete it afterwards.
- **Do not upgrade a red-test into a claim about coverage.** One injection
  proves that assertion fires for that failure mode, not that the stage covers
  the whole class.

**Put the result in the PR description.** Reviewers need to see, per ticket,
that the gap is closed rather than asserted. This table is the deliverable:

```markdown
## Historical failures this catches

Source: Jira component `AI Hub` (the `Model Registry` component is empty),
searched by QE test name. Classified per Step 1.8.

| Ticket | Failing test | Symptom | Covered by | Proof |
|---|---|---|---|---|
| RHOAIENG-63943 | async-upload smoke | build green, job died on `No module named 'model_signing'` | `Hermetic Build Preflight` (Python `--no-index`) | injected the import; preflight failed with `ERROR: No matching distribution found for model-signing` |

## Historical failures this does not catch

| Ticket | Failing test | Why not | Follow-up |
|---|---|---|---|
| RHOAIENG-103141 | `test_mr_condition_in_dsc` | needs DSC reconciliation, not a standalone container | opendatahub-operator#<n> |
```

The second table is not optional. Listing only what you catch is how a
simulator gets credit for failures it would have sailed past — the model-registry
DSC conditions (`ModelRegistryReady` False, `managementState`, unhealthy
component pods) are exactly that case: the container ran fine, so nothing in
this repo could observe them.

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
    # IMPORTANT: Only check node_modules packages, not workspace packages
    # Workspace packages (backend, frontend, packages/*) don't have resolved URLs
    # If using jq: '.packages | to_entries[] | select(.key | startswith("node_modules/"))'
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
