---
pr_number: 489
repo: opendatahub-io/model-registry-operator
overall_risk: 30
security_risk: 15
breaking_risk: 45
critical_path_risk: 55
dependency_risk: 0
patterns_matched:
  - pattern: controller
    file: internal/controller/modelcatalog_controller.go
    line: 144-157
    severity: medium
  - pattern: rbac.*configmaps
    file: internal/controller/kubebuilder.go
    line: 11
    severity: low
top_risks:
  - title: ConfigMap deletion timing may cause brief service disruption
    severity: medium
    description: Migration logic deletes old ConfigMap (model-catalog-default-sources) during reconciliation. If pods are still mounting the old ConfigMap name, there could be a brief disruption until reconciliation completes and deployment is updated.
    file: internal/controller/modelcatalog_controller.go
    lines: 147-157
    risk_score: 25
  - title: RBAC permission expansion adds delete capability
    severity: low
    description: Kubebuilder RBAC annotation now includes 'delete' verb for configmaps. This expands the operator's permissions, though only for ConfigMap resources which are low-sensitivity.
    file: internal/controller/kubebuilder.go
    lines: 11
    risk_score: 10
  - title: Migration code may remain indefinitely
    severity: low
    description: Comment states 'Remove once old clusters have had enough time to reconcile' but provides no specific timeline or version. Migration code could accumulate over time.
    file: internal/controller/modelcatalog_controller.go
    lines: 147-149
    risk_score: 5
recommendations:
  - Add explicit version/timeline for removing migration code (e.g., 'Remove in v2.0.0 or after 2026-07-01')
  - Consider using owner references or finalizers to ensure graceful ConfigMap migration
  - Verify that the deployment rollout completes before old ConfigMap deletion in reconciliation order
  - Add metrics/logging to track successful migration in production clusters
---

# Risk Analysis Report - PR #489

**PR Title:** feat(catalog): rename default sources ConfigMap to default-catalog-sources  
**Author:** pboyd  
**Repository:** opendatahub-io/model-registry-operator  
**Overall Risk Score:** 30/100 (LOW-MEDIUM)

---

## Executive Summary

This PR renames the default catalog sources ConfigMap from `model-catalog-default-sources` to `default-catalog-sources` for consistency with naming conventions. The change includes migration logic to automatically delete the old ConfigMap and comprehensive test coverage. The overall risk is **LOW-MEDIUM** due to proper handling of the breaking change, though care should be taken around deployment timing.

---

## Risk Assessment Details

### 1. Security Risk: 15/100 (LOW)

**Analysis:**
- No authentication, authorization, or credential handling changes
- No SQL queries, user input handling, or injection risks
- RBAC change adds `delete` verb to configmaps permission (minor expansion)
- No secrets, tokens, or sensitive data exposed in diff
- No cryptographic or TLS changes

**Security Pattern Matches:**
- None (no auth, password, credential, SQL patterns matched)

**Conclusion:** Minimal security risk. The RBAC permission expansion is limited to ConfigMap resources which are low-sensitivity infrastructure objects.

---

### 2. Breaking Change Risk: 45/100 (MEDIUM)

**Analysis:**
This is a **breaking change** in resource naming, but it is well-handled:

**Breaking aspects:**
- ConfigMap resource name changes from `model-catalog-default-sources` to `default-catalog-sources`
- Deployment volume mount reference updated to new ConfigMap name
- External tooling or scripts referencing the old name will break

**Mitigation factors:**
- Migration code automatically deletes old ConfigMap with operator-managed label check
- Template changes ensure new ConfigMap is created before old one is deleted (reconciliation order)
- Comprehensive test coverage including specific migration test case
- Tests verify both old ConfigMap deletion and new ConfigMap creation

**Files affected:**
- `internal/controller/config/templates/catalog/catalog-default-configmap.yaml.tmpl` (line 4)
- `internal/controller/config/templates/catalog/catalog-deployment.yaml.tmpl` (line 44)
- `internal/controller/modelcatalog_controller.go` (lines 147-157: migration logic)
- All test references updated (5 locations in test file)

**Risks:**
1. If external systems reference `model-catalog-default-sources` by name, they will fail
2. Timing window between old ConfigMap deletion and pod restart could cause brief disruption
3. No version gate or feature flag for gradual rollout

**Recommendation:** Document the breaking change in release notes and migration guide.

---

### 3. Critical Path Risk: 55/100 (MEDIUM)

**Analysis:**
This PR touches **controller code**, which is a critical path component in Kubernetes operators:

**Critical path components affected:**
- `modelcatalog_controller.go` - Core reconciliation logic (12 lines added)
- Catalog deployment template - Pod configuration for running service
- Default sources ConfigMap - Runtime configuration for catalog

**Impact scope:**
- Changes affect `ensureCatalogResources()` function in reconciliation loop
- Deployment template changes affect pod specification
- ConfigMap is mounted into catalog container at `/etc/default-sources`

**Mitigation factors:**
- Migration logic uses `client.IgnoreNotFound()` for graceful error handling
- Label check ensures only operator-managed ConfigMaps are deleted (`app.kubernetes.io/created-by: model-registry-operator`)
- Test coverage includes edge cases (old ConfigMap deletion, new ConfigMap creation, concurrent operations)
- No changes to core business logic or data processing

**Failure scenarios:**
1. If reconciliation fails mid-migration, old ConfigMap may persist (low impact - will be cleaned up on next reconcile)
2. If deployment rollout is delayed, pods may restart during migration window (brief disruption possible)

**Recommendation:** Monitor reconciliation metrics post-deployment and ensure rollout completes successfully in staging before production.

---

### 4. Dependency Risk: 0/100 (NONE)

**Analysis:**
- No changes to `go.mod`, `go.sum`, or any dependency files
- No new external libraries added
- No version bumps of existing dependencies

**Conclusion:** Zero dependency risk.

---

## Pattern Matching Results

### Critical Path Patterns Matched:
1. **controller** - File path contains `controller` (critical component)
   - `internal/controller/modelcatalog_controller.go`
   - `internal/controller/modelcatalog_controller_test.go`
   - `internal/controller/kubebuilder.go`

### Breaking Change Patterns Matched:
None - No API signatures, schemas, or handler changes detected in diff patterns.

### Security Patterns Matched:
None - No auth, token, password, credential, SQL, or XSS patterns detected.

---

## Detailed Findings

### Finding 1: ConfigMap Deletion Timing Risk (MEDIUM - 25 points)

**Location:** `internal/controller/modelcatalog_controller.go:147-157`

**Description:**  
The migration logic deletes the old ConfigMap during reconciliation. If the deployment hasn't fully rolled out to use the new ConfigMap name, pods may briefly reference a non-existent ConfigMap.

**Code:**
```go
// Delete the old-named default sources ConfigMap (renamed 2026-04, was "model-catalog-default-sources").
// Remove once old clusters have had enough time to reconcile.
var oldDefaultCM corev1.ConfigMap
err = r.Get(ctx, types.NamespacedName{Name: "model-catalog-default-sources", Namespace: r.TargetNamespace}, &oldDefaultCM)
if client.IgnoreNotFound(err) != nil {
    log.Error(err, "failed to get legacy default sources ConfigMap")
} else if err == nil && oldDefaultCM.Labels["app.kubernetes.io/created-by"] == "model-registry-operator" {
    if delErr := r.Delete(ctx, &oldDefaultCM); client.IgnoreNotFound(delErr) != nil {
        log.Error(delErr, "failed to delete legacy default sources ConfigMap")
    }
}
```

**Risk Assessment:**
- Reconciliation order ensures templates are applied before migration code runs
- Label check prevents accidental deletion of user-managed ConfigMaps
- Error handling is graceful (logs errors but doesn't fail reconciliation)

**Mitigation:**
The reconciliation loop will create the new ConfigMap before deleting the old one, reducing risk. However, in-flight pods may experience a brief disruption if they're restarted during the migration window.

**Recommendation:**
- Add a condition check to ensure deployment has updated before deleting old ConfigMap
- Or use a two-phase migration: Phase 1 creates new ConfigMap, Phase 2 (next version) deletes old one

---

### Finding 2: RBAC Permission Expansion (LOW - 10 points)

**Location:** `internal/controller/kubebuilder.go:11`

**Description:**  
The kubebuilder RBAC annotation now includes `delete` verb for `configmaps` resource.

**Change:**
```diff
-// +kubebuilder:rbac:groups=core,resources=configmaps,verbs=create;get;list;watch;patch;update
+// +kubebuilder:rbac:groups=core,resources=configmaps,verbs=create;get;list;watch;patch;update;delete
```

**Risk Assessment:**
- ConfigMaps are low-sensitivity infrastructure resources
- Operator already has create/update/patch permissions (can effectively delete by overwriting)
- Delete permission is necessary for migration cleanup
- Scoped to operator's ServiceAccount (not cluster-wide)

**Recommendation:**
No action required. This is appropriate for the migration use case.

---

### Finding 3: Indefinite Migration Code (LOW - 5 points)

**Location:** `internal/controller/modelcatalog_controller.go:147-149`

**Description:**  
The migration code includes a comment "Remove once old clusters have had enough time to reconcile" but provides no specific version number or date.

**Comment:**
```go
// Delete the old-named default sources ConfigMap (renamed 2026-04, was "model-catalog-default-sources").
// Remove once old clusters have had enough time to reconcile.
```

**Risk Assessment:**
- Technical debt accumulation if migration code isn't removed
- No functional risk (code is safe to leave indefinitely)
- Could confuse future maintainers

**Recommendation:**
Add explicit removal timeline:
```go
// TODO(2026-07): Remove this migration code after v2.0.0 release or 2026-07-01, whichever is later
```

---

## Test Coverage Analysis

**Test Coverage: EXCELLENT**

The PR includes comprehensive test coverage for the migration:

1. **New migration test** (`Should delete the old-named default sources ConfigMap on reconcile`):
   - Creates old-named ConfigMap with operator label
   - Runs reconciliation
   - Verifies old ConfigMap is deleted
   - Verifies new ConfigMap exists

2. **Updated existing tests** (5 test cases updated):
   - All references to old ConfigMap name updated to new name
   - Deployment volume mount assertions updated
   - ConfigMap existence checks updated

3. **Edge cases covered**:
   - Old ConfigMap with operator label → deleted
   - Old ConfigMap without operator label → not touched (safe)
   - New ConfigMap creation → verified
   - Concurrent reconciliation → handled gracefully

**Conclusion:** Test coverage effectively validates the migration logic and reduces deployment risk.

---

## Recommendations Summary

### High Priority:
None (no high-severity risks identified)

### Medium Priority:
1. **Add explicit version/timeline for removing migration code**  
   Suggested: `TODO(2026-07): Remove after v2.0.0 or 2026-07-01`

2. **Document breaking change in release notes**  
   External systems referencing `model-catalog-default-sources` by name will need updates

3. **Verify deployment rollout order in reconciliation**  
   Ensure new ConfigMap is created and mounted before old one is deleted

### Low Priority:
4. **Add migration metrics/logging**  
   Track successful migration in production: `log.Info("migrated legacy ConfigMap", "old", "model-catalog-default-sources", "new", "default-catalog-sources")`

5. **Consider two-phase migration for extra safety**  
   Phase 1 (current version): Create new ConfigMap alongside old  
   Phase 2 (next version): Delete old ConfigMap

---

## Conclusion

**Overall Risk Score: 30/100 (LOW-MEDIUM)**

This is a well-executed breaking change with appropriate migration logic and comprehensive test coverage. The primary risks are:

1. Brief service disruption if deployment rollout timing is unfavorable (mitigated by reconciliation order)
2. RBAC permission expansion (minimal security impact)
3. Indefinite migration code (technical debt, not functional risk)

The PR demonstrates good engineering practices:
- Migration code with safety checks (label verification)
- Graceful error handling (`client.IgnoreNotFound()`)
- Comprehensive test coverage including migration scenarios
- Clear comments explaining the change and intent

**Recommendation: APPROVE** with minor suggestions for improvement (explicit migration removal timeline and release notes documentation).
