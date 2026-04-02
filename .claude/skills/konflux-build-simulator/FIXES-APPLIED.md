# Konflux Build Simulator - Critical Fixes Applied

## Date: 2026-03-30

This document tracks all critical fixes applied to the konflux-build-simulator skill based on technical review feedback.

---

## Issue #1: Module Federation Validation Was Architecturally Wrong

### Problem
- Current approach tried to `curl http://localhost:8080/_mf/{module}/remoteEntry.js` inside the container
- `/_mf/{name}/*` routes are PROXIES to external Kubernetes services (port 8043), not locally-served files
- Standalone container returns 404 for all `/_mf/*` requests
- This validation would ALWAYS FAIL

### Fix Applied
Changed Module Federation validation to validate the BUILD output instead of runtime proxy endpoints:

**Files Updated:**
- `/Users/acoughli/qualityTigerTeam/quality-tiger-team/.claude/.claude/skills/konflux-build-simulator/instructions.md`
- `/Users/acoughli/qualityTigerTeam/odh-dashboard/.github/workflows/konflux-build-simulator.yml`
- `/Users/acoughli/qualityTigerTeam/odh-dashboard/scripts/validate-konflux-build.sh`

**New Approach:**
```bash
# Instead of curl proxy endpoints, validate the BUILD created the assets
# Check that webpack actually generated the remoteEntry.js files
docker run --rm $IMAGE sh -c '
  for module in gen-ai model-registry maas automl autorag mlflow mlflow-embedded eval-hub observability notebooks; do
    # Check if module has MF config first
    if [ -f "/opt/app-root/src/packages/${module}/package.json" ]; then
      if grep -q "module-federation" "/opt/app-root/src/packages/${module}/package.json"; then
        # Validate remoteEntry.js was generated in dist or build output
        if [ ! -f "/opt/app-root/src/packages/${module}/frontend/dist/remoteEntry.js" ] &&
           [ ! -f "/opt/app-root/src/packages/${module}/dist/remoteEntry.js" ]; then
          echo "ERROR: remoteEntry.js not found for ${module}"
          exit 1
        fi
      fi
    fi
  done
'
```

---

## Issue #2: curl Dependency Problem

### Problem
- `curl` doesn't exist in UBI9 nodejs images by default
- `docker exec test-dashboard curl` would fail

### Fix Applied
Test endpoints from OUTSIDE the container using the mapped port:

**Files Updated:**
- `/Users/acoughli/qualityTigerTeam/quality-tiger-team/.claude/.claude/skills/konflux-build-simulator/instructions.md`
- `/Users/acoughli/qualityTigerTeam/odh-dashboard/.github/workflows/konflux-build-simulator.yml`
- `/Users/acoughli/qualityTigerTeam/odh-dashboard/scripts/validate-konflux-build.sh`

**Before:**
```bash
docker exec test-dashboard curl -f http://localhost:8080/
```

**After:**
```bash
# Health check from HOST (curl doesn't exist in UBI9 nodejs images by default)
curl -f http://localhost:8080/
```

---

## Issue #3: Incorrect Module List

### Problem
- `feature-store` was included but has NO module-federation config
- `mlflow-embedded` was excluded but HAS valid MF config

### Fix Applied
Corrected module list to 10 modules:

**Files Updated:**
- `/Users/acoughli/qualityTigerTeam/odh-dashboard/.github/workflows/konflux-build-simulator.yml`
- `/Users/acoughli/qualityTigerTeam/odh-dashboard/scripts/validate-konflux-build.sh`
- `/Users/acoughli/qualityTigerTeam/quality-tiger-team/.claude/.claude/skills/konflux-build-simulator/odh-dashboard-konflux-sim-report.md`

**Before (11 modules):**
```bash
MF_REMOTES="gen-ai model-registry maas automl autorag mlflow eval-hub observability feature-store notebooks"
```

**After (10 modules):**
```bash
MF_REMOTES="gen-ai model-registry maas automl autorag mlflow mlflow-embedded eval-hub observability notebooks"
# Removed: feature-store (no MF config)
# Added: mlflow-embedded (has valid MF config: mlflowEmbedded)
```

---

## Issue #4: Container Startup Resilience

### Problem
- Backend references K8s service account paths that don't exist outside cluster
- No graceful handling or startup error checks

### Fix Applied
Added graceful handling documentation and test for startup errors:

**Files Updated:**
- `/Users/acoughli/qualityTigerTeam/odh-dashboard/.github/workflows/konflux-build-simulator.yml`
- `/Users/acoughli/qualityTigerTeam/odh-dashboard/scripts/validate-konflux-build.sh`

**New Checks:**
```bash
# Start container and capture logs
docker run -d --name test-dashboard -p 8080:8080 $IMAGE
sleep 5

# Check if container is still running (didn't crash on startup)
if ! docker ps | grep -q test-dashboard; then
  echo "Container failed to start"
  docker logs test-dashboard
  exit 1
fi
```

---

## Issue #5: [skip konflux-sim] Implementation

### Problem
- No way to skip the workflow when needed

### Fix Applied
Added workflow condition:

**Files Updated:**
- `/Users/acoughli/qualityTigerTeam/quality-tiger-team/.claude/.claude/skills/konflux-build-simulator/instructions.md`
- `/Users/acoughli/qualityTigerTeam/odh-dashboard/.github/workflows/konflux-build-simulator.yml`

**Implementation:**
```yaml
jobs:
  build-validation:
    # Skip if [skip konflux-sim] is in PR title or commit message
    if: |
      !contains(github.event.pull_request.title, '[skip konflux-sim]') &&
      !contains(github.event.head_commit.message, '[skip konflux-sim]')
```

---

## Issue #6: Kustomize Installation

### Problem
- Fragile curl install script
- ubuntu-latest already has kustomize pre-installed

### Fix Applied
Use pre-installed kustomize:

**Files Updated:**
- `/Users/acoughli/qualityTigerTeam/quality-tiger-team/.claude/.claude/skills/konflux-build-simulator/instructions.md`
- `/Users/acoughli/qualityTigerTeam/odh-dashboard/.github/workflows/konflux-build-simulator.yml`

**Before:**
```yaml
- name: Setup Kustomize
  run: |
    curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash
    sudo mv kustomize /usr/local/bin/
```

**After:**
```yaml
# Kustomize is pre-installed on ubuntu-latest runners
- name: Verify Kustomize
  run: |
    kustomize version
```

---

## Documentation Updates

### Files Updated:
1. `/Users/acoughli/qualityTigerTeam/quality-tiger-team/.claude/.claude/skills/konflux-build-simulator/SKILL.md`
   - Updated Phase 3 description to reflect filesystem validation, not runtime proxy testing
   - Removed "90%+ of build failures" claim (too optimistic)
   - Updated module count to 10 (not 11)
   - Added [skip konflux-sim] feature

2. `/Users/acoughli/qualityTigerTeam/quality-tiger-team/.claude/.claude/skills/konflux-build-simulator/odh-dashboard-konflux-sim-report.md`
   - Updated module count from 11 to 10
   - Updated Module Federation validation description
   - Removed overly optimistic "90%+" claims
   - Updated to "Most common issues" and "Improved" metrics

3. `/Users/acoughli/qualityTigerTeam/quality-tiger-team/.claude/.claude/skills/konflux-build-simulator/instructions.md`
   - Updated all template workflows with corrected MF validation logic
   - Updated to use host-side curl
   - Added [skip konflux-sim] check
   - Updated to use pre-installed kustomize
   - Added container startup resilience checks

---

## Summary of Changes

### Critical Architecture Fixes
- ✅ Module Federation validation now checks BUILD output, not runtime proxies
- ✅ curl runs from host, not inside container
- ✅ Module list corrected to 10 modules (removed feature-store, added mlflow-embedded)
- ✅ Container startup resilience improved
- ✅ [skip konflux-sim] flag implemented
- ✅ Pre-installed kustomize used instead of fragile install script

### Documentation Improvements
- ✅ Removed overly optimistic "90%+" claims
- ✅ Updated module count to 10 throughout
- ✅ Clarified what Module Federation validation actually tests
- ✅ Added notes about K8s service account path graceful handling

### Files Modified
1. `.github/workflows/konflux-build-simulator.yml` - Production workflow
2. `scripts/validate-konflux-build.sh` - Local validation script
3. `.claude/skills/konflux-build-simulator/instructions.md` - Skill instructions
4. `.claude/skills/konflux-build-simulator/SKILL.md` - Skill documentation
5. `.claude/skills/konflux-build-simulator/odh-dashboard-konflux-sim-report.md` - Report template

---

## Next Steps

The updated skill has been applied to:
- `/Users/acoughli/qualityTigerTeam/quality-tiger-team/.claude/.claude/skills/konflux-build-simulator/`
- `/Users/acoughli/qualityTigerTeam/odh-dashboard/` (workflow and script files)

All critical issues identified in the technical review have been addressed.
