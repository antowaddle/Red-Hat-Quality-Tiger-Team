---
pr_number: 489
repo: opendatahub-io/model-registry-operator
incident_jira: RHOAIENG-57824
incident_severity: P2
reported_risk: 19
actual_risk: 80
decision: APPROVE
actual_outcome: caused_incident
incident_date: 2026-04-09
analysis_date: 2026-04-20
false_negative: true
pattern_type: kubernetes_resource_rename
---

# Incident Analysis: PR #489 - ConfigMap Rename Breaking Dashboard

## Summary

**PR #489** renamed a ConfigMap from `model-catalog-default-sources` to `default-catalog-sources` in the model-registry-operator. Our analysis scored it as **19/100 (APPROVE)**, but it caused a **P2 incident** when the odh-dashboard failed due to hardcoded references to the old ConfigMap name.

This is a **false negative** - we approved a PR that broke production.

---

## Timeline

- **2026-04-07:** PR #489 opened (ConfigMap rename)
- **2026-04-09:** PR #489 merged
- **2026-04-09:** Dashboard BFF crashes, E2E tests fail
- **2026-04-09:** Incident RHOAIENG-57824 filed
- **2026-04-20:** Retrospective analysis conducted

---

## Root Cause

The model-registry-operator renamed a Kubernetes ConfigMap, but the odh-dashboard had hardcoded references in:

### 1. BFF Backend Code
```go
// packages/model-registry/upstream/bff/internal/integrations/kubernetes/client.go
const CatalogSourceDefaultConfigMapName = "model-catalog-default-sources" ❌
```

### 2. Cypress E2E Tests (6 references)
```typescript
// packages/cypress/cypress/utils/oc_commands/modelCatalog.ts
const command = `oc get configmap model-catalog-default-sources -n ${namespace}`; ❌
```

### 3. Test Mocks
```go
// packages/model-registry/upstream/bff/internal/integrations/kubernetes/k8mocks/base_testenv.go
return fmt.Errorf("failed to create model-catalog-default-sources configmap: %w", err) ❌
```

**Total:** 12+ hardcoded references across dashboard codebase

---

## What Our Analysis Missed

### ✅ What We Got Right
1. Identified "Breaking Changes: Yes"
2. Noted 2 affected components (operator, dashboard)
3. Recommended cross-repo coordination

### ❌ What We Got Wrong

#### 1. Impact Severely Underestimated
- **Scored:** odh-dashboard impact as "LOW"
- **Should be:** CRITICAL (BFF code + E2E tests broken)

#### 2. No Cross-Repo Code Search
- Analyzed only the operator's codebase
- Never searched dashboard for hardcoded ConfigMap name
- **Gap:** No automated cross-repo grep

#### 3. Missing Detection Pattern
- Did not recognize "Kubernetes resource rename" as critical pattern
- ConfigMap/Secret/CRD name changes = de-facto API breaking changes
- **Gap:** No K8s resource rename detector

#### 4. Test Coverage Blind Spot
- Validated operator's tests (100% coverage ✅)
- Did not check if *other repos'* tests reference this resource
- **Gap:** Cross-repo test dependency analysis missing

#### 5. Impact Analysis Gap
- Identified dashboard as affected component
- Did not validate *how* it's affected:
  - Import/library dependency? ✗
  - API consumer? ✗
  - **Kubernetes resource consumer?** ✓ ← Missed this
- **Gap:** No detection of K8s resource coupling

---

## Corrected Risk Score

| Category | Original | Corrected | Reason |
|----------|----------|-----------|--------|
| Security | 15/100 | 15/100 | (unchanged) |
| **Breaking Changes** | **45/100** | **95/100** | K8s resource rename with cross-repo hardcoded refs |
| **Critical Path** | **55/100** | **70/100** | Dashboard BFF + E2E tests broken |
| Dependency | 0/100 | 0/100 | (unchanged) |
| **OVERALL** | **19/100** | **~80/100** | **APPROVE → WARN (High Priority)** |

**Decision Should Have Been:** ⚠️ WARN with requirement for coordinated PRs

---

## Lessons Learned

### 1. Backend Changes Break Frontend
Even in microservices architectures, backend K8s resource renames break frontend code that consumes those resources.

### 2. Kubernetes Resource Names Are APIs
ConfigMap/Secret/Service names are effectively part of your API surface. Renaming them is a breaking change.

### 3. Test References Create Coupling
E2E tests that hardcode `oc get configmap X` create tight coupling. These are integration points.

### 4. Cross-Repo Search Is Critical
Cannot analyze an operator in isolation. Must search all related repos for hardcoded references.

### 5. Migration Logic ≠ Consumer Migration
The operator adding cleanup logic to delete the old ConfigMap doesn't help the dashboard - its code still breaks.

---

## Improvements Implemented

### 1. K8s Resource Rename Detector
**File:** `scripts/k8s_resource_detector.py`

```bash
# Automatically detect ConfigMap/Secret/CRD renames in diff
python3 scripts/k8s_resource_detector.py tmp/pr-489.diff

# Output:
{
  "has_renames": true,
  "renames": [
    {
      "resource_type": "configmap",
      "old_name": "model-catalog-default-sources",
      "likely_new_names": ["default-catalog-sources"],
      "risk_level": "CRITICAL"
    }
  ]
}
```

### 2. Cross-Repo Reference Search
**File:** `scripts/search_cross_repo_refs.py`

```bash
# Search all context repos for hardcoded references
python3 scripts/search_cross_repo_refs.py "model-catalog-default-sources"

# Output:
{
  "affected_repos": [
    {
      "repo": "odh-dashboard",
      "impact": "CRITICAL",
      "match_count": 12,
      "matches": [
        {
          "file": "packages/.../client.go",
          "line": "47",
          "content": "const CatalogSourceDefaultConfigMapName = \"model-catalog-default-sources\""
        },
        ...
      ]
    }
  ]
}
```

### 3. Updated Impact Analyzer Prompt
**File:** `.claude/skills/risk-assessment/prompts/impact-analyzer.md`

Added section 6: **CRITICAL: Detect Kubernetes Resource Renames**

- Run k8s_resource_detector.py on diff
- If renames detected, run search_cross_repo_refs.py
- Flag as CRITICAL if code/test references found
- Escalate blast_radius to HIGH
- Require coordinated PRs

### 4. Enhanced Frontmatter Schema
Added fields to impact-assessment output:
```yaml
k8s_resource_renames:
  - resource_type: "configmap"
    old_name: "model-catalog-default-sources"
    new_name: "default-catalog-sources"
    cross_repo_search_performed: true
cross_repo_references:
  - repo: "odh-dashboard"
    references_found: 12
    impact: "CRITICAL"
```

---

## How Future Analysis Would Differ

### With These Improvements

**PR #489 Analysis (Enhanced):**

```yaml
Decision: ⚠️ WARN (Risk: 80/100)

k8s_resource_renames:
  - resource_type: configmap
    old_name: model-catalog-default-sources
    new_name: default-catalog-sources

cross_repo_references:
  - repo: odh-dashboard
    impact: CRITICAL
    references_found: 12
    files:
      - packages/.../client.go (Go constant)
      - packages/cypress/.../modelCatalog.ts (6 E2E test refs)
      - packages/.../base_testenv.go (test mock)

breaking_changes: true
blast_radius: high
coordination_required: high

recommendations:
  - CRITICAL: Create coordinated PR for odh-dashboard to update all 12 references
  - CRITICAL: Merge dashboard PR FIRST, then operator PR
  - HIGH: Add backward-compat period (support both names for 1 release)
  - MEDIUM: Use feature flag or phased rollout
```

---

## Testing This Improvement

### Validate on PR #489
```bash
# Test the new detectors on PR #489
cd /Users/acoughli/agentic-quality-framework

# 1. Extract diff
gh pr diff 489 --repo opendatahub-io/model-registry-operator > tmp/pr-489-test.diff

# 2. Detect K8s renames
python3 scripts/k8s_resource_detector.py tmp/pr-489-test.diff

# Expected output: ConfigMap rename detected

# 3. Search cross-repo refs
python3 scripts/search_cross_repo_refs.py "model-catalog-default-sources"

# Expected output: 12+ references in odh-dashboard

# 4. Re-run risk-assessment with enhanced analyzers
# Should now score 75-85/100 (WARN) instead of 19/100 (APPROVE)
```

---

## Future Rubric Enhancement

When rubric system is implemented, add this criteria:

```yaml
# rubrics/v1.1.0/breaking-rubric.yaml
categories:
  kubernetes_resource_changes:
    weight: 0.35  # High weight due to RHOAIENG-57824 incident
    criteria:
      - name: "ConfigMap/Secret Name Changes"
        scoring:
          critical: [81-100]
            indicators:
              - "ConfigMap name changed in YAML templates"
              - "Secret name changed in manifests"
              - "CRD name/kind modified"
            why_it_matters: |
              Incident RHOAIENG-57824: Dashboard crashed when operator renamed ConfigMap.
              Other repos hardcode resource names in code, tests, RBAC policies.
            detection:
              - "Run scripts/k8s_resource_detector.py"
              - "Search context repos for old resource name"
            required_actions:
              - "Create coordinated PRs for ALL affected repos"
              - "Merge downstream PRs FIRST, then operator"
              - "Consider backward-compat period (support both names)"
```

---

## Related Issues

- **RHOAIENG-57824:** Dashboard BFF failure due to ConfigMap rename
- **PR #489:** model-registry-operator ConfigMap rename (merged)
- **PR #???:** odh-dashboard fix for ConfigMap references (follow-up)

---

## Tags

`false-negative` `kubernetes` `configmap` `cross-repo` `breaking-change` `incident` `P2`
