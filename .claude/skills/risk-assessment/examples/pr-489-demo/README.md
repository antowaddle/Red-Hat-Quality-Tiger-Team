# Executive Demo: PR #489 Analysis

**Real-world example of the Agentic Quality Framework catching a production incident pattern**

---

## 🎯 Overview

This directory contains a complete analysis of **PR #489** from the model-registry-operator repository, demonstrating how the framework detects high-risk Kubernetes resource renames that could break downstream services.

**PR Details:**
- **Repository:** opendatahub-io/model-registry-operator
- **PR:** #489 - "feat(catalog): rename default sources ConfigMap"
- **Change:** Renamed ConfigMap from `model-catalog-default-sources` → `default-catalog-sources`
- **Incident:** RHOAIENG-57824 (Dashboard crash due to hardcoded references)

---

## 📊 Analysis Results

### Risk Score: **65/100 (WARN)**

The framework correctly identified this as a **high-risk change** requiring coordination:

| Analyzer | Score | Key Finding |
|----------|-------|-------------|
| **Risk** | 30/100 | Breaking changes detected in controller |
| **Test Coverage** | 100% | All modified functions tested ✅ |
| **Impact** | HIGH | Blast radius across 2+ components |
| **Cross-Repo** | CRITICAL | **13 hardcoded references** in odh-dashboard |

---

## 🚨 What Was Detected

### K8s Resource Rename Pattern
```yaml
# ConfigMap name changed
- model-catalog-default-sources
+ default-catalog-sources
```

### Cross-Repository Impact
**odh-dashboard had 13 hardcoded references:**
- Go constant: `CatalogSourceDefaultConfigMapName = "model-catalog-default-sources"`
- Cypress E2E tests: `oc get configmap model-catalog-default-sources` (6 files)
- Test mocks and fixtures

**Without coordination, this breaks:**
- Dashboard BFF (backend-for-frontend)
- E2E test suite
- Integration tests

---

## 📁 Files in This Demo

### Analysis Reports (HTML + Markdown)

**Main Report:**
- `pr-489-analysis.html` - Executive summary with all 4 analyzers
- `pr-489-analysis.md` - Markdown version

**Detailed Analyzer Reports:**
- `risk-489.html` / `risk-489.md` - Risk assessment details
- `test-489.html` / `test-489.md` - Test coverage analysis
- `impact-489.html` / `impact-489.md` - Architecture impact + K8s rename detection
- `crossrepo-489.html` / `crossrepo-489.md` - Cross-repo intelligence

**Documentation:**
- `IMPROVEMENTS-PR-489.md` - Detection tools built to catch this pattern
- `pr-489-RHOAIENG-57824.md` - Incident analysis and lessons learned

---

## 🎨 View the Demo

### Option 1: Open HTML Reports
```bash
open pr-489-analysis.html
```

Click through the detailed analyzer reports via the links in the main report.

### Option 2: Read Markdown
```bash
cat pr-489-analysis.md
```

---

## 💡 Key Insights

### What Made This High-Risk?

1. **Kubernetes Resource Rename** - Changes the de-facto API contract
2. **Cross-Repo References** - Other repos hardcoded the ConfigMap name
3. **No Coordination** - Dashboard team wasn't aware of the change
4. **Production Impact** - Would break deployed systems immediately

### How the Framework Caught It

1. **K8s Rename Detector** (`scripts/k8s_resource_detector.py`)
   - Detected ConfigMap name change in YAML templates
   - Flagged for cross-repo search

2. **Cross-Repo Search** (`scripts/search_cross_repo_refs.py`)
   - Searched odh-dashboard for `model-catalog-default-sources`
   - Found 13 references in code and tests
   - Categorized as CRITICAL impact

3. **Risk Score Escalation** (`scripts/decision_engine.py`)
   - Breaking risk: 45 → 95 (due to K8s rename + critical refs)
   - Overall risk: 19 → 65 (minimum floor applied)
   - Decision: APPROVE → WARN

### Recommended Actions

The framework generated specific recommendations:

1. **CRITICAL:** Create coordinated PR in odh-dashboard
2. **CRITICAL:** Merge dashboard PR FIRST, then operator PR
3. **HIGH:** Add backward-compatibility period (support both names for 1 release)
4. **MEDIUM:** Use feature flag for gradual rollout

---

## 🔧 How to Reproduce This Analysis

```bash
# From repo root
/risk-assessment 489 --repo opendatahub-io/model-registry-operator --dry-run
```

The framework will:
1. Fetch PR diff and metadata
2. Load context repositories
3. Run 4 parallel analyzers
4. Generate HTML + Markdown reports
5. Calculate risk score and decision

---

## 📖 Learning Resources

**Incident Pattern:** Kubernetes Resource Rename
- **What:** Backend service renames a ConfigMap, Secret, CRD, or Service
- **Risk:** Breaks hardcoded references in other repos
- **Detection:** YAML diff analysis + cross-repo grep
- **Mitigation:** Coordinated PRs, backward compatibility, feature flags

**Detection Tools Built:**
- `scripts/k8s_resource_detector.py` - Find K8s renames in diffs
- `scripts/search_cross_repo_refs.py` - Search for hardcoded references
- Enhanced impact analyzer prompt with K8s section

**Incident Documentation:**
- `pr-489-RHOAIENG-57824.md` - Full incident analysis
- `IMPROVEMENTS-PR-489.md` - Detection improvements implemented

---

## 🎯 Use This Demo For

- **Executive presentations:** Show HTML reports (click through the analysis)
- **Team onboarding:** Walk through the incident pattern and detection
- **Process improvement:** Demonstrate automated coordination requirements
- **Sales/partnerships:** Real-world evidence of incident prevention

---

## 🚀 Next Steps

After reviewing this demo:

1. **Try it on another PR:**
   ```bash
   /risk-assessment <pr_number> --repo <owner/name>
   ```

2. **Customize for your repos:**
   - Add to `context-repos/` in `scripts/fetch-context.sh`
   - Define repository-specific test patterns

3. **Integrate into CI/CD:**
   - GitHub Actions workflow
   - Post PR comments automatically
   - Set status checks (APPROVE/WARN)

---

**Generated by:** Agentic SDLC Quality Framework  
**Powered by:** Claude Sonnet 4.5  
**Analysis Date:** 2026-04-21
