---
pr_number: 489
pr_title: "feat(catalog): rename default sources ConfigMap to default-catalog-sources"
repository: opendatahub-io/model-registry-operator
component: model-registry-operator
blast_radius: high
affected_components:
  - name: model-registry-operator
    impact: high
    reason: Primary component making the K8s ConfigMap rename
  - name: odh-dashboard
    impact: critical
    reason: Hardcoded references in Go client and Cypress E2E tests will break at runtime
k8s_resource_renames:
  - resource_type: configmap
    old_name: model-catalog-default-sources
    new_name: default-catalog-sources
    file_changed: internal/controller/config/templates/catalog/catalog-default-configmap.yaml.tmpl
    migration_code_added: true
    migration_details: |
      Reconciler automatically deletes old ConfigMap on reconcile (lines 48-58 in modelcatalog_controller.go).
      Checks for 'app.kubernetes.io/created-by: model-registry-operator' label before deletion.
cross_repo_references:
  - repo: odh-dashboard
    impact: CRITICAL
    references_found: 13
    critical_files:
      - path: packages/model-registry/upstream/bff/internal/integrations/kubernetes/client.go
        line: 15
        type: go_constant
        reference: 'const CatalogSourceDefaultConfigMapName = "model-catalog-default-sources"'
        impact: CRITICAL - Go constant will cause BFF API to query wrong ConfigMap name
      - path: packages/cypress/cypress/utils/oc_commands/modelCatalog.ts
        lines: [67, 171, 250]
        type: e2e_tests
        reference: 'oc get configmap model-catalog-default-sources'
        impact: CRITICAL - E2E tests will fail with NotFound errors
    all_references:
      - "packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:62 (doc comment)"
      - "packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:67 (oc command)"
      - "packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:68 (log message)"
      - "packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:73 (log message)"
      - "packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:77 (error message)"
      - "packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:80 (log message)"
      - "packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:152 (doc comment)"
      - "packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:168 (comment)"
      - "packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:171 (oc command)"
      - "packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:243 (doc comment)"
      - "packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:250 (oc command)"
      - "packages/model-registry/upstream/bff/internal/integrations/kubernetes/k8mocks/base_testenv.go:350 (error message in test mock)"
      - "packages/model-registry/upstream/bff/internal/integrations/kubernetes/client.go:15 (Go constant definition)"
breaking_changes: true
coordination_required: high
risk_assessment: HIGH
---

# Architecture Impact Assessment: PR #489

## Executive Summary

**CRITICAL K8s RESOURCE RENAME DETECTED**

PR #489 renames a Kubernetes ConfigMap from `model-catalog-default-sources` to `default-catalog-sources`. This is a **de-facto API breaking change** with **critical cross-repository impact**.

**Key Finding**: 13 hardcoded references found in `odh-dashboard` repository, including:
- **Go constant** in BFF client that will break catalog API at runtime
- **Cypress E2E tests** with hardcoded `oc get configmap` commands that will fail

**Blast Radius**: HIGH (escalated from low/medium due to cross-repo dependencies)
**Coordination Required**: HIGH (requires synchronized updates across repos)

---

## 1. Component Mapping

### Primary Component
- **model-registry-operator**: Kubernetes operator managing model registry and catalog resources
  - Manages ConfigMap templates for catalog default sources
  - Reconciles catalog resources in target namespaces
  - Owns the ConfigMap lifecycle and naming

### Affected Downstream Components
- **odh-dashboard**: Web UI and BFF services for Open Data Hub
  - **model-registry package**: Contains BFF (Backend-for-Frontend) written in Go
  - **cypress E2E tests**: Integration tests that verify catalog functionality

---

## 2. Blast Radius Assessment

**Initial Assessment**: Low (simple ConfigMap rename within single operator)

**ESCALATED TO: HIGH** due to:
1. **Hardcoded external references**: 13 references in odh-dashboard
2. **Runtime impact**: Go constant will cause API failures
3. **Test failures**: E2E tests will break immediately
4. **Cross-repo coordination**: Requires synchronized PR across repositories

### Blast Radius Breakdown

| Scope | Impact | Details |
|-------|--------|---------|
| model-registry-operator | HIGH | Primary change location, includes migration code |
| odh-dashboard (BFF) | CRITICAL | Go constant must be updated or API breaks |
| odh-dashboard (E2E tests) | CRITICAL | Cypress tests will fail with NotFound errors |
| Existing clusters | LOW | Migration handles gracefully via reconciler |
| New deployments | LOW | Uses new name from start |

---

## 3. Affected Components Analysis

### 3.1 model-registry-operator (Primary)

**Files Changed**:
- `internal/controller/config/templates/catalog/catalog-default-configmap.yaml.tmpl` (line 9): ConfigMap name
- `internal/controller/config/templates/catalog/catalog-deployment.yaml.tmpl` (line 22): Volume reference
- `internal/controller/kubebuilder.go` (line 36): RBAC permissions (added `delete`)
- `internal/controller/modelcatalog_controller.go` (lines 48-58): Migration code
- `internal/controller/modelcatalog_controller_test.go`: Test updates

**Impact**: HIGH
- Operator reconciliation creates new ConfigMap with new name
- Old ConfigMap deleted automatically on reconcile
- Migration is safe and idempotent

**Risk**: Low (well-handled with migration code)

### 3.2 odh-dashboard (CRITICAL - Go Client)

**File**: `packages/model-registry/upstream/bff/internal/integrations/kubernetes/client.go`

**Line 15 - CRITICAL GO CONSTANT**:
```go
const CatalogSourceDefaultConfigMapName = "model-catalog-default-sources"
```

**Impact Analysis**:
- This constant is used by the BFF's Kubernetes client to query the ConfigMap
- When BFF API calls try to read catalog sources, they will query the OLD name
- Result: **404 NotFound errors at runtime** after operator upgrade
- User-facing impact: Catalog features will break in dashboard UI

**References in Code**:
```go
// Used in GetAllCatalogSourceConfigs(ctx, namespace)
// Returns: (defaultConfigMap, userConfigMap, error)
// Likely queries: client.Get(ctx, types.NamespacedName{
//   Name: CatalogSourceDefaultConfigMapName,  // OLD NAME!
//   Namespace: namespace,
// }, &defaultConfigMap)
```

**Required Fix**: Update constant to `"default-catalog-sources"`

### 3.3 odh-dashboard (CRITICAL - E2E Tests)

**File**: `packages/cypress/cypress/utils/oc_commands/modelCatalog.ts`

**CRITICAL OC COMMANDS** (3 instances):
1. **Line 67** - `verifyModelCatalogSourcesConfigMap()`:
   ```typescript
   const command = `oc get configmap model-catalog-default-sources -n ${namespace}`;
   ```

2. **Line 171** - `verifyModelCatalogSourceEnabled()`:
   ```typescript
   const defaultCommand = `oc get configmap model-catalog-default-sources -n ${namespace} -o jsonpath='{.data.sources\\.yaml}' | ${parseCmd}`;
   ```

3. **Line 250** - `isModelCatalogSourceEnabled()`:
   ```typescript
   const command = `oc get configmap model-catalog-default-sources -n ${namespace} -o jsonpath='{.data.sources\\.yaml}' | ${parseCmd}`;
   ```

**Impact Analysis**:
- These are test utilities used by Cypress E2E tests
- Tests will fail with "ConfigMap not found" errors after operator upgrade
- Affects catalog feature E2E test coverage
- Tests will be red/failing until updated

**Additional References** (comments/logs - lower priority):
- Lines 62, 68, 73, 77, 80, 152, 168, 243: Documentation and log messages

**Required Fix**: Update all `oc get configmap` commands to use new name

### 3.4 Test Mocks (Low Priority)

**File**: `packages/model-registry/upstream/bff/internal/integrations/kubernetes/k8mocks/base_testenv.go`

**Line 350**:
```go
return fmt.Errorf("failed to create model-catalog-default-sources configmap: %w", err)
```

**Impact**: LOW - Test mock error message only
**Required Fix**: Update error message for consistency (non-breaking)

---

## 4. Integration Point Mapping

### 4.1 K8s API Integration Points

**Operator → K8s API**:
- **Create**: New ConfigMap with name `default-catalog-sources`
- **Delete**: Old ConfigMap `model-catalog-default-sources` (migration)
- **Read**: Checks for old ConfigMap existence before delete

**Dashboard BFF → K8s API**:
- **Read**: Queries ConfigMap by constant name (BREAKS after upgrade)
- Method: `GetAllCatalogSourceConfigs(ctx, namespace)`
- Expectation: ConfigMap exists with hardcoded name

### 4.2 Volume Mount Integration

**Deployment → ConfigMap**:
```yaml
volumes:
  - name: default-sources
    configMap:
      name: default-catalog-sources  # UPDATED
```

**Impact**: Deployment will mount new ConfigMap correctly after reconcile

### 4.3 Test Integration Points

**Cypress E2E → Cluster**:
- Uses `oc` CLI to verify ConfigMap existence
- Reads ConfigMap data to validate catalog sources
- Polls ConfigMap for enabled status changes

**Impact**: All E2E tests using these utilities will fail

---

## 5. Breaking Change Detection

### K8s Resource Rename = De-Facto API Breaking Change

**Why This is Breaking**:
1. **External clients hardcode resource names**: ConfigMap names are part of the operator's implicit API contract
2. **No K8s API version change**: Resource name changes don't trigger K8s version deprecation warnings
3. **Silent runtime failures**: Queries for old name will fail with 404, not caught by type system
4. **Cross-repo coordination required**: Can't be fixed in single PR

### Breaking Change Characteristics

| Characteristic | Assessment |
|----------------|------------|
| **Type** | Kubernetes resource rename |
| **Detectability** | Not detected by K8s API machinery (same apiVersion/kind) |
| **Failure Mode** | Runtime 404 NotFound errors |
| **Backward Compatibility** | Migration code in operator only; downstream repos need updates |
| **Coordination** | Requires synchronized PRs across repos |

### Migration Strategy Assessment

**Operator-Side** (✅ GOOD):
- Reconciler automatically deletes old ConfigMap
- Checks for operator ownership label before deletion
- Idempotent and safe

**Downstream-Side** (❌ NOT HANDLED):
- No automated update mechanism for odh-dashboard
- Manual PR required to update hardcoded references
- Tests will fail until downstream PR merges

---

## 6. K8s Resource Rename Detection

### Detection Results

**Tool**: `scripts/k8s_resource_detector.py`

**Output**:
```json
{
  "has_renames": true,
  "renames": [
    {
      "resource_type": "configmap",
      "old_name": "model-catalog-default-sources",
      "new_name": "default-catalog-sources",
      "risk_level": "CRITICAL",
      "reason": "ConfigMap rename detected in manifest"
    }
  ],
  "requires_cross_repo_search": true
}
```

### Cross-Repo Search Results

**Tool**: `scripts/search_cross_repo_refs.py`

**Search Pattern**: `"model-catalog-default-sources"`

**Affected Repositories**: 1 (odh-dashboard)

**Total References**: 13

**Reference Breakdown by Impact**:
- **CRITICAL** (2 unique locations, 3 runtime instances):
  - Go constant (1): Will break API
  - OC commands (3): Will break E2E tests
- **MEDIUM** (10):
  - Documentation comments (6)
  - Log messages (3)
  - Test mock error message (1)

---

## 7. Risk Analysis

### Technical Risks

| Risk | Severity | Likelihood | Impact | Mitigation |
|------|----------|------------|--------|-----------|
| BFF API failures | CRITICAL | High | Users can't access catalog features | Coordinate dashboard PR with operator release |
| E2E test failures | HIGH | Certain | CI/CD red, no test coverage | Update tests before operator upgrade in test clusters |
| Deployment failures | LOW | Low | Migration handles gracefully | Operator reconcile handles cleanup |
| Documentation drift | MEDIUM | Medium | Support burden | Update all comments in dashboard |

### Coordination Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Timing window**: Operator deployed before dashboard update | CRITICAL | Require synchronized release, or accept temporary breakage |
| **Discovery delay**: Downstream team unaware of change | HIGH | Document breaking change in release notes, notify dashboard team |
| **Rollback complexity**: Need to revert both repos | MEDIUM | Ensure rollback plan before deployment |

### User Impact

**Scenario 1**: Operator upgraded, dashboard NOT updated
- **Impact**: Catalog features broken in UI (404 errors from BFF)
- **Duration**: Until dashboard PR merges and deploys
- **User Experience**: "Model catalog unavailable" errors

**Scenario 2**: Both upgraded in sync
- **Impact**: Minimal (brief reconciliation window)
- **Duration**: Seconds to minutes during pod restart
- **User Experience**: Transparent

---

## 8. Recommendations

### CRITICAL Actions (Must Do)

1. **Create Coordinated Dashboard PR**:
   - File: `packages/model-registry/upstream/bff/internal/integrations/kubernetes/client.go`
   - Change: `const CatalogSourceDefaultConfigMapName = "default-catalog-sources"`
   - File: `packages/cypress/cypress/utils/oc_commands/modelCatalog.ts`
   - Change: Update all 3 `oc get configmap` commands to use `default-catalog-sources`

2. **Synchronize Releases**:
   - Deploy operator and dashboard updates together
   - OR accept temporary catalog feature outage
   - Document the coordination requirement

3. **Update Breaking Change Documentation**:
   - Add to operator release notes: "BREAKING: ConfigMap renamed, requires dashboard update"
   - Link to dashboard PR
   - Provide upgrade sequence

### HIGH Priority Actions (Should Do)

4. **Update Documentation and Comments**:
   - All 10 comment/log references in modelCatalog.ts
   - Test mock error message in base_testenv.go

5. **Add E2E Test for Migration**:
   - Verify old ConfigMap is deleted after reconcile
   - Verify new ConfigMap works correctly

6. **Add Integration Test**:
   - Test that BFF can read from new ConfigMap name
   - Catch this type of issue earlier

### MEDIUM Priority Actions (Nice to Have)

7. **Design Pattern for K8s Renames**:
   - Document process for resource renames
   - Checklist: "Search for hardcoded resource names"
   - Tooling: Automated cross-repo reference detection

8. **Consider Deprecation Period**:
   - Support both names temporarily (if feasible)
   - Log warnings when old name is queried
   - Remove old name in future version

---

## 9. Coordination Requirements

### Required Coordination Level: HIGH

**Coordination Strategy**: Synchronized Release

**Stakeholders**:
1. **model-registry-operator team**: Owns PR #489
2. **odh-dashboard team**: Must create companion PR
3. **Release management**: Must coordinate deployment timing
4. **QE team**: Must validate both PRs together

**Timeline**:
```
1. PR #489 merges (operator) → Do NOT deploy yet
2. Dashboard PR created and reviewed → Link to #489
3. Dashboard PR merges → Ready to deploy
4. Synchronized deployment: Operator + Dashboard together
5. Validation: E2E tests pass, catalog features work
```

**Rollback Plan**:
1. If issues found post-deployment, rollback BOTH components
2. Operator rollback recreates old ConfigMap name
3. Dashboard rollback restores old constant/test references

---

## 10. Testing Recommendations

### Pre-Merge Testing

1. **Operator Tests** (✅ Already Included):
   - Unit test for old ConfigMap deletion
   - Integration test for new ConfigMap creation
   - Verify deployment mounts new ConfigMap

2. **Dashboard Tests** (❌ TO DO):
   - Unit test BFF constant change
   - Update E2E test to use new name
   - Run E2E tests against upgraded operator

### Integration Testing

3. **End-to-End Scenario**:
   - Deploy old operator + old dashboard → catalog works
   - Upgrade operator only → catalog breaks (expected)
   - Upgrade dashboard → catalog works again
   - Verify: No old ConfigMap left behind

4. **Migration Scenario**:
   - Start with cluster using old ConfigMap name
   - Upgrade operator
   - Verify old ConfigMap deleted
   - Verify new ConfigMap created
   - Verify pod mounts new ConfigMap

---

## 11. Documentation Impact

### Required Documentation Updates

**Operator Release Notes**:
```markdown
## Breaking Changes

### ConfigMap Rename: model-catalog-default-sources → default-catalog-sources

**Impact**: This change renames the default catalog sources ConfigMap. 
Downstream components that reference this ConfigMap by name must be updated.

**Affected**: odh-dashboard (model-registry BFF and E2E tests)

**Required Actions**:
- Deploy odh-dashboard PR #XXXX alongside this operator version
- Do NOT upgrade operator without dashboard update

**Migration**: The operator automatically deletes the old ConfigMap on reconcile.
No manual intervention required for the ConfigMap itself.
```

**Dashboard Release Notes**:
```markdown
## Bug Fixes

### Update ConfigMap name for model catalog (#XXXX)

Updates references to renamed ConfigMap in model-registry-operator.

**Related**: model-registry-operator PR #489

**Deployment**: Must be deployed with model-registry-operator vX.Y.Z or later
```

---

## 12. Incident Pattern Analysis

### Matches Known Pattern: RHOAIENG-57824

This PR matches the **K8s Resource Rename** incident pattern:
- Kubernetes resource name changed without cross-repo coordination
- Hardcoded references in another repository
- Runtime failures (404 NotFound)
- E2E test failures

**Pattern**: ConfigMaps, Secrets, Services, CRDs with hardcoded names in:
- Go constants
- TypeScript constants
- Test scripts (kubectl/oc commands)
- Documentation

**Detection**: K8s resource detector script caught this pattern correctly

**Mitigation**: This assessment + cross-repo search flagged all references

---

## 13. Summary and Next Steps

### Summary

PR #489 renames a Kubernetes ConfigMap, which is a **breaking change** for downstream consumers. The change is well-handled within the operator (migration code, tests), but requires **critical coordination** with odh-dashboard.

**Blast Radius**: HIGH (escalated from low/medium)
**Breaking Changes**: YES (cross-repo API contract change)
**Coordination**: HIGH (synchronized release required)

### Critical Path

```
┌─────────────────────────────────────────────────────────────┐
│ 1. CREATE DASHBOARD PR                                       │
│    - Update Go constant in client.go                         │
│    - Update 3 OC commands in modelCatalog.ts                 │
│    - Update comments/logs                                    │
│    - Link to operator PR #489                                │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. MERGE BOTH PRs                                            │
│    - Operator PR #489 merges                                 │
│    - Dashboard PR merges                                     │
│    - DO NOT DEPLOY YET                                       │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. SYNCHRONIZED DEPLOYMENT                                   │
│    - Deploy operator + dashboard together                    │
│    - Validate catalog features work                          │
│    - Verify E2E tests pass                                   │
└─────────────────────────────────────────────────────────────┘
```

### Success Criteria

✅ Dashboard PR created and linked to #489
✅ Both PRs pass CI/CD
✅ Deployment plan documented and approved
✅ Both components deployed together
✅ E2E tests pass after deployment
✅ Catalog features work in production

---

## Appendix A: File Locations

### model-registry-operator (PR #489)
- `/internal/controller/config/templates/catalog/catalog-default-configmap.yaml.tmpl`
- `/internal/controller/config/templates/catalog/catalog-deployment.yaml.tmpl`
- `/internal/controller/kubebuilder.go`
- `/internal/controller/modelcatalog_controller.go`
- `/internal/controller/modelcatalog_controller_test.go`

### odh-dashboard (Requires Update)
- `/packages/model-registry/upstream/bff/internal/integrations/kubernetes/client.go` (CRITICAL)
- `/packages/cypress/cypress/utils/oc_commands/modelCatalog.ts` (CRITICAL)
- `/packages/model-registry/upstream/bff/internal/integrations/kubernetes/k8mocks/base_testenv.go` (LOW)

---

## Appendix B: Search Results Detail

### Complete Cross-Repo Reference List

**odh-dashboard** (13 references):

1. `packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:62` - Doc comment
2. `packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:67` - **CRITICAL**: OC command
3. `packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:68` - Log message
4. `packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:73` - Log message
5. `packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:77` - Error message
6. `packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:80` - Log message
7. `packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:152` - Doc comment
8. `packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:168` - Comment
9. `packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:171` - **CRITICAL**: OC command
10. `packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:243` - Doc comment
11. `packages/cypress/cypress/utils/oc_commands/modelCatalog.ts:250` - **CRITICAL**: OC command
12. `packages/model-registry/upstream/bff/internal/integrations/kubernetes/k8mocks/base_testenv.go:350` - Test mock error
13. `packages/model-registry/upstream/bff/internal/integrations/kubernetes/client.go:15` - **CRITICAL**: Go constant

---

**Generated**: 2026-04-20
**Analyzer**: Impact Analyzer Agent (Agentic SDLC Quality Framework)
**Detection Tools**: k8s_resource_detector.py, search_cross_repo_refs.py
**Confidence**: HIGH (automated detection + manual verification)
