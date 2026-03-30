# Konflux CI Dashboard - Design & Implementation Plan

**Date:** 2026-03-30
**Status:** Design Phase
**Owner:** Quality Tiger Team

---

## Executive Summary

A comprehensive dashboard to monitor Konflux pipeline health, track build failures, and provide visibility into quality metrics across all RHOAI components.

This dashboard addresses the critical gap in proactive monitoring and provides the visibility needed to prevent production failures before they occur.

---

## Problem Statement

### Current State

**Pain Points**:
- Build failures discovered manually
- No centralized view of pipeline health
- No historical trend analysis
- Difficult to identify patterns
- Reactive rather than proactive approach

**Impact**:
- Delayed incident response
- Repeated failures go unnoticed
- No visibility into quality trends
- Manual tracking of issues (time-consuming)
- No correlation between failures and root causes

### The Gap

RHOAI components build in Konflux, but there's no unified view of:
- Which pipelines are failing and why
- How often failures occur
- Whether PR build validation is working
- Quality trends over time
- Security vulnerabilities across components

---

## Solution: Konflux CI Dashboard

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Konflux CI Dashboard                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Pipeline   │  │    Build     │  │   Quality    │  │
│  │    Status    │  │   Failures   │  │   Metrics    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Historical  │  │   PR Build   │  │   Alerting   │  │
│  │    Trends    │  │  Validation  │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
└─────────────────────────────────────────────────────────┘
                          │
                          │ APIs
                          ▼
        ┌──────────────────────────────────────┐
        │         Data Sources                  │
        ├──────────────────────────────────────┤
        │  • Konflux API (pipeline status)     │
        │  • GitHub API (PR status)            │
        │  • JIRA API (issue tracking)         │
        │  • Codecov API (coverage metrics)    │
        └──────────────────────────────────────┘
```

---

## Core Features

### 1. Pipeline Status Dashboard

**Real-Time View**:
```
┌─────────────────────────────────────────────────────────────┐
│  Component            │ Status │ Last Run │ Success Rate     │
├─────────────────────────────────────────────────────────────┤
│  odh-dashboard        │   ✅   │ 5m ago  │ ████████░░ 82%   │
│  notebooks            │   ✅   │ 10m ago │ ██████████ 98%   │
│  kserve               │   ❌   │ 2h ago  │ ██████░░░░ 65%   │
│  training-operator    │   ✅   │ 1h ago  │ █████████░ 91%   │
│  kueue                │   🟡   │ 15m ago │ ████████░░ 85%   │
└─────────────────────────────────────────────────────────────┘

Legend: ✅ Passing | ❌ Failing | 🟡 In Progress
```

**Data Displayed**:
- Current pipeline status (passing/failing/in-progress)
- Last successful run timestamp
- 30-day success rate
- Active failures with links to logs
- Time since last green build

**API Integration**:
```python
# Konflux API endpoint
GET /api/v1/applications/rhoai-v3-4-ea-2/pipelineruns

# Response includes:
{
  "component": "odh-dashboard",
  "status": "Succeeded",
  "startTime": "2026-03-30T10:00:00Z",
  "completionTime": "2026-03-30T10:15:32Z",
  "conditions": [...],
  "logs_url": "https://konflux-ui.apps..."
}
```

---

### 2. Build Failure Tracking

**Failure Analysis**:
```
┌─────────────────────────────────────────────────────────────┐
│  Recent Failures (Last 7 Days)                              │
├─────────────────────────────────────────────────────────────┤
│  Component         │ Failure Type        │ Count │ JIRA    │
├─────────────────────────────────────────────────────────────┤
│  odh-dashboard     │ Docker build        │   3   │ ENG-XXX │
│  kserve            │ Manifest validation │   5   │ ENG-YYY │
│  notebooks         │ Multi-arch build    │   2   │ ENG-ZZZ │
└─────────────────────────────────────────────────────────────┘
```

**Failure Categories**:

1. **Docker Build Failures**
   - Build arg issues
   - COPY command failures
   - Multi-stage build problems
   - Dependency issues

2. **Manifest/Operator Failures**
   - Kustomize errors
   - CRD validation failures
   - ConfigMap generation issues
   - RBAC problems

3. **Image/Runtime Failures**
   - Container startup crashes
   - Missing files
   - Port binding issues
   - Health check failures

4. **Test Failures**
   - Unit test failures
   - E2E test failures
   - Integration test failures

**Failure Detail View**:
```
Failure: odh-dashboard-v3-4-ea-2-on-push-7kfcc
├── Type: Docker build (BUILD_MODE mismatch)
├── Branch: main
├── Commit: abc123 (Update Module Federation config)
├── Time: 2026-03-30 14:23:15 UTC
├── Duration: 8m 32s
├── Error:
│   COPY failed: /opt/app-root/src/dist/_mf/genAi/remoteEntry.js
│   not found
├── Root Cause: BUILD_MODE=ODH on PR, BUILD_MODE=RHOAI in Konflux
├── JIRA: RHOAIENG-55730
├── Logs: [View Full Logs]
└── Fix: PR build validation (prevents 90% of these)
```

---

### 3. PR Build Validation Status

**Integration with GitHub PRs**:
```
┌─────────────────────────────────────────────────────────────┐
│  PR Build Validation Coverage                               │
├─────────────────────────────────────────────────────────────┤
│  Component            │ Enabled │ PRs Tested │ Failures     │
├─────────────────────────────────────────────────────────────┤
│  odh-dashboard        │   ❌    │    0/45    │    N/A       │
│  notebooks            │   ❌    │    0/32    │    N/A       │
│  kserve               │   ❌    │    0/28    │    N/A       │
│  training-operator    │   ❌    │    0/19    │    N/A       │
└─────────────────────────────────────────────────────────────┘

⚠️  0/13 components have PR build validation enabled
📊  Target: 13/13 by Q2 2026
```

**After Implementation**:
```
┌─────────────────────────────────────────────────────────────┐
│  PR Build Validation Coverage                               │
├─────────────────────────────────────────────────────────────┤
│  Component            │ Enabled │ PRs Tested │ Caught       │
├─────────────────────────────────────────────────────────────┤
│  odh-dashboard        │   ✅    │   45/45    │ 8 failures   │
│  notebooks            │   ✅    │   32/32    │ 3 failures   │
│  kserve               │   ✅    │   28/28    │ 5 failures   │
│  training-operator    │   ✅    │   19/19    │ 2 failures   │
└─────────────────────────────────────────────────────────────┘

✅  13/13 components have PR build validation enabled
📈  18 failures caught at PR time (prevented Konflux failures)
```

---

### 4. Historical Trends

**Success Rate Over Time**:
```
Success Rate (Last 30 Days)

100% ┼─────────────────────────────────────────────────
  90% ┤           ╭╮    ╭─╮
  80% ┤         ╭─╯╰────╯ ╰╮        ╭────
  70% ┤    ╭────╯          ╰╮      ╭╯
  60% ┤────╯                ╰──────╯
     └┴────┴────┴────┴────┴────┴────┴────┴
      Week1   Week2   Week3   Week4

Current: 85% | Previous: 72% | Trend: ↗️ +13%
```

**Metrics Tracked**:
- Build success rate (overall & per component)
- Mean time to detect (MTTD) failures
- Mean time to resolve (MTTR) failures
- PR build validation adoption rate
- Test coverage trends
- Image vulnerability trends

**Correlation Analysis**:
```
┌─────────────────────────────────────────────────────────────┐
│  Build Success vs PR Build Validation Adoption              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  100%┤                                    ●────●────●        │
│      │                              ●────●                   │
│   80%┤                        ●────●                         │
│      │                  ●────●                               │
│   60%┤────●────●────●                                        │
│      │                                                       │
│      └┴────┴────┴────┴────┴────┴────┴────┴────┴             │
│       0/13  2/13  4/13  6/13  8/13 10/13 12/13 13/13       │
│                  Components with PR Validation              │
│                                                              │
│  Insight: Each component adds ~4% to overall success rate   │
└─────────────────────────────────────────────────────────────┘
```

---

### 5. Quality Metrics

**Coverage Tracking**:
```
┌─────────────────────────────────────────────────────────────┐
│  Code Coverage (by component)                               │
├─────────────────────────────────────────────────────────────┤
│  odh-dashboard       ████████████████░░ 82% (✅ enforced)   │
│  notebooks           ████████████░░░░░░ 65% (🟡 not enforced)│
│  kserve              ████████████████░░ 80% (✅ enforced)   │
│  training-operator   ██████████████░░░░ 72% (🟡 badge only) │
│  kueue               ████████████░░░░░░ 63% (❌ not tracked)│
└─────────────────────────────────────────────────────────────┘

Overall: 72% | Target: 80% | Components enforcing: 3/13
```

**Image Security**:
```
┌─────────────────────────────────────────────────────────────┐
│  Vulnerability Scanning Status                              │
├─────────────────────────────────────────────────────────────┤
│  Component         │ Critical │ High │ Medium │ Trivy       │
├─────────────────────────────────────────────────────────────┤
│  odh-dashboard     │    0     │  0   │   2    │ ✅ enabled  │
│  notebooks         │    0     │  0   │   1    │ ✅ enabled  │
│  kserve            │    0     │  3   │   5    │ ❌ not enabled│
│  training-operator │    1     │  2   │   7    │ ❌ not enabled│
└─────────────────────────────────────────────────────────────┘

⚠️  1 CRITICAL vulnerability requires immediate attention
📊  Components scanning: 2/13 (target: 13/13)
```

**Agent Rules Coverage**:
```
┌─────────────────────────────────────────────────────────────┐
│  Agent Test Creation Rules                                  │
├─────────────────────────────────────────────────────────────┤
│  Component            │ Rules │ Unit │ Mock │ E2E │ Contract│
├─────────────────────────────────────────────────────────────┤
│  odh-dashboard        │  ✅   │  ✅  │  ✅  │ ✅  │   ✅    │
│  notebooks            │  ❌   │  ❌  │  ❌  │ ❌  │   ❌    │
│  kserve               │  ❌   │  ❌  │  ❌  │ ❌  │   ❌    │
│  training-operator    │  ❌   │  ❌  │  ❌  │ ❌  │   ❌    │
└─────────────────────────────────────────────────────────────┘

Coverage: 1/13 components | Target: 13/13 by Q2 2026
```

---

### 6. Alerting & Notifications

**Alert Rules**:

#### 1. Build Failure Alert (Immediate)
```
Trigger: Pipeline fails in Konflux
Channel: Slack #rhoai-builds
Severity: HIGH
Message: "🔴 Build failed: odh-dashboard-v3-4-ea-2
         Branch: main
         Commit: abc123
         Error: Docker build failure (BUILD_MODE)
         Logs: [link]
         Assigned: @team-dashboard"
```

#### 2. Repeated Failure Alert (3+ failures in 24h)
```
Trigger: Same component fails 3+ times in 24h
Channel: Slack #rhoai-quality
Severity: CRITICAL
Message: "🚨 Repeated failures: kserve (5 failures in 18h)
         Common error: Manifest validation
         JIRA: RHOAIENG-YYY
         Action: Investigate root cause immediately"
```

#### 3. Coverage Drop Alert
```
Trigger: Coverage drops > 5% on PR
Channel: PR comment + Slack
Severity: MEDIUM
Message: "⚠️  Coverage dropped from 82% to 76% (-6%)
         Files affected: controller.go, webhook.go
         Action: Add tests or justify in PR description"
```

#### 4. Security Alert
```
Trigger: CRITICAL or HIGH CVE detected
Channel: Slack #rhoai-security + JIRA auto-create
Severity: CRITICAL
Message: "🔒 Security vulnerability: CVE-2026-12345 (CRITICAL)
         Component: training-operator
         Package: golang.org/x/crypto
         Fix available: v0.15.0
         JIRA: RHOAIENG-ZZZ (auto-created)"
```

#### 5. Success Rate Alert (trending down)
```
Trigger: Success rate < 80% for 7 days
Channel: Slack #rhoai-quality
Severity: HIGH
Message: "📉 Success rate trending down: 75% (7-day avg)
         Components affected: kserve, modelmesh-serving
         Recommendation: Enable PR build validation
         Dashboard: [link]"
```

**Alert Destinations**:
- Slack channels (builds, quality, security)
- Email (maintainers, oncall)
- PagerDuty (CRITICAL only)
- JIRA (auto-create tickets)
- GitHub PR comments (PR-specific)

---

## Data Sources & APIs

### 1. Konflux API
```python
# Pipeline runs
GET /api/v1/applications/{app}/pipelineruns
GET /api/v1/pipelineruns/{id}
GET /api/v1/pipelineruns/{id}/logs

# Webhooks for real-time updates
POST /webhook/konflux (pipeline status changes)
```

### 2. GitHub API
```python
# PR status
GET /repos/{owner}/{repo}/pulls
GET /repos/{owner}/{repo}/pulls/{number}/checks

# Workflow runs
GET /repos/{owner}/{repo}/actions/runs
GET /repos/{owner}/{repo}/actions/workflows/{id}/runs
```

### 3. Codecov API
```python
# Coverage data
GET /api/v2/github/{owner}/repos/{repo}/commits/{sha}/totals
GET /api/v2/github/{owner}/repos/{repo}/commits/{sha}/file_report/{path}
```

### 4. JIRA API
```python
# Issue tracking
GET /rest/api/3/search?jql=project=RHOAIENG AND labels=build-failure
POST /rest/api/3/issue (auto-create tickets)
GET /rest/api/3/issue/{key}
```

---

## Technology Stack

**Frontend**:
- React + TypeScript
- PatternFly UI components (consistent with odh-dashboard)
- Recharts for data visualization
- Real-time updates via WebSocket

**Backend**:
- Go API server (consistent with RHOAI ecosystem)
- PostgreSQL for historical data
- Redis for caching
- Prometheus for metrics

**Infrastructure**:
- Deploy on OpenShift (same as RHOAI)
- Konflux for CI/CD
- OAuth integration with GitHub

---

## Implementation Plan

### Phase 1: Foundation (2-3 weeks)
```
Week 1-2: Core infrastructure
├── API server (Go)
├── Database schema
├── Konflux API integration
└── GitHub API integration

Week 2-3: Basic dashboard
├── Pipeline status view
├── Build failure tracking
└── Simple alerting
```

### Phase 2: Enhanced Features (3-4 weeks)
```
Week 4-5: Advanced dashboards
├── Historical trends
├── Quality metrics
├── PR build validation tracking
└── Correlation analysis

Week 5-6: Alerting & integrations
├── Slack integration
├── JIRA auto-creation
├── Email notifications
└── PagerDuty integration
```

### Phase 3: Analytics & Optimization (2-3 weeks)
```
Week 7-8: Advanced analytics
├── Failure pattern detection
├── Predictive analytics
├── Root cause analysis
└── Recommendation engine

Week 8-9: Polish & deployment
├── Performance optimization
├── Documentation
├── Runbooks
└── Production deployment
```

**Total Effort**: 7-10 weeks (1-2 engineers)

---

## Success Metrics

### After Implementation

| Metric | Baseline | Target | Timeline |
|--------|----------|--------|----------|
| Build success rate | 72% | 95%+ | Q3 2026 |
| MTTD (mean time to detect) | Hours/days | <15 min | Q2 2026 |
| MTTR (mean time to resolve) | Days | <4 hours | Q3 2026 |
| PR build validation adoption | 0/13 | 13/13 | Q2 2026 |
| Repeated failures | Common | Rare | Q3 2026 |
| Manual monitoring effort | Hours/day | Minutes/day | Q2 2026 |

---

## Dashboard Access

**URL**: `https://konflux-quality.rhoai.redhat.com` (proposed)

**Authentication**: GitHub OAuth (RHOAI org membership)

**Permissions**:
- **Viewers**: All RHOAI contributors
- **Maintainers**: Component maintainers (can acknowledge alerts)
- **Admins**: Quality team (can configure alerts, modify thresholds)

---

## Next Steps

### Immediate (Week 1)
1. Gather requirements from stakeholders
2. Design database schema
3. Set up development environment
4. Spike Konflux API integration

### Short Term (Weeks 2-4)
1. Build core infrastructure
2. Implement basic dashboard
3. Set up alerting framework
4. Deploy to staging

### Medium Term (Weeks 5-8)
1. Add advanced features
2. Integrate all data sources
3. Implement alerting rules
4. User acceptance testing

### Long Term (Weeks 9-10)
1. Production deployment
2. Documentation and training
3. Runbook creation
4. Continuous improvement

---

## Conclusion

The Konflux CI Dashboard provides the critical visibility and proactive monitoring needed to shift from reactive incident response to proactive quality management.

**Key Benefits**:
- ✅ Centralized visibility across all 13 components
- ✅ Proactive alerting prevents incidents
- ✅ Historical trends inform quality improvements
- ✅ Correlation analysis identifies patterns
- ✅ Automated JIRA ticket creation reduces manual work

**This dashboard, combined with PR build validation, will reduce Konflux failures by 90%+ and enable continuous quality improvement across RHOAI.**
