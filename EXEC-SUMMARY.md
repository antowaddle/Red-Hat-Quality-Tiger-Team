# Quality Tiger Team — Executive Summary

**Date:** April 10, 2026 | **Scope:** RHOAI 3.4 core components | **Tools Run:** 3

---

## What We Did

We ran three agentic quality tools from the Quality Tiger Team toolkit against real RHOAI component repositories:

| Tool | Target | What It Does |
|------|--------|--------------|
| **Quality Repo Analysis** | 6 core RHOAI component repos (deep analysis) | Scores each component across 7 quality dimensions — tests, CI/CD, security, coverage, agent rules |
| **Konflux Build Simulator** | odh-dashboard | Analyzes the production Dockerfile and Konflux pipeline, generates a PR build validation workflow that catches failures before they hit production |
| **Test Rules Generator** | notebooks | Extracts existing test patterns and generates agent-consumable rules so AI can write tests that match the team's conventions |

---

## Key Findings

### Platform Quality: Who's Leading, Who's Lagging

| Component | Score | Verdict |
|-----------|-------|---------|
| **odh-dashboard** | **9/10** | **Gold standard.** 604 test files, Cypress E2E, Codecov, 18 CI workflows, full `.claude/rules/` agent guidance. Every other team should aspire to this. |
| **notebooks** | **8/10** | **Image testing best-in-class.** 64+ Dockerfiles, Trivy scanning, Testcontainers + Playwright, Codecov. The layered validation approach is genuinely innovative. |
| **kuberay** | **7/10** | **Strong Go depth.** 136 test files, gitleaks secret scanning, solid e2e. Missing coverage reporting and agent rules. |
| **odh-model-controller** | **6/10** | **Silent regression risk.** 52 Go test files — solid. But e2e tests are **manual-trigger only** (`workflow_dispatch`). Not gated on PRs. Coverage not tracked. No agent rules. |
| **kueue** | **6/10** | **Hidden giant.** 364 test files — the largest corpus of any component. But nearly zero GitHub Actions visible. CI lives in upstream Kubernetes Prow, invisible to RHOAI auditing. |
| **codeflare-operator** | **6/10** | **Under-tested for its criticality.** Only 7 unit test files for a component that orchestrates distributed workloads. |

**The gap between the best (odh-dashboard at 9/10) and the worst (multiple at 6/10) is significant.** The top teams have invested in CI/CD, coverage tracking, and agent rules. The bottom teams have test code but lack the automation and visibility to prove it.

---

### Konflux Build Simulator: Preventing the 111-Bug Problem

**Context:** [111 bugs have been logged in RHOAIENG](https://redhat.atlassian.net/issues?filter=-4&jql=project%20%3D%20RHOAIENG%20AND%20type%20%3D%20Bug%20and%20description%20~%20crash) where crashes caused the DSC (DataScienceCluster) to go **NotReady**. When the DSC goes NotReady, Konflux pipelines fail, teams are blocked, and the blast radius spreads across the entire platform. Many of these originate from build failures that weren't caught at PR time.

**What the simulator found on odh-dashboard (first run):**
- **Module Federation path mismatch** — the existing simulator checks `/opt/app-root/src/packages/...` but the Dockerfile actually uses `/usr/src/app`. This means the current check is giving **false confidence** — it could pass even when the build is broken.
- **Health endpoint unusable standalone** — `/api/health` requires a Kube context and 503s outside a cluster. Smoke tests pointed at it are unreliable.
- **Manifest validation inconsistency** — two different workflows validate different sets of kustomize roots. No single source of truth.

**What it generated:** A corrected GitHub Actions workflow and local validation script, ready to drop into the repo. Same `BUILD_MODE=RHOAI` as the real Konflux pipeline, correct filesystem paths, proper smoke test endpoints.

**This is the kind of tool that, if deployed across all RHOAI components, would have prevented a significant portion of those 111 DSC-breaking bugs.** It catches build failures at PR time — minutes instead of hours/days.

---

### Test Rules Generator: Closing the Biggest Gap

**The problem:** Most RHOAI component repos have **zero agent rules**. When developers or AI agents need to write tests, there's no codified guide for "how we test here." Every new contributor — human or AI — has to reverse-engineer the patterns from existing code.

**What it extracted from notebooks:**
- 4 complete rule files covering unit tests, image/container tests, E2E/browser tests, and cross-cutting standards
- The full testing DNA: pytest markers, Testcontainers patterns, Podman CI quirks, multi-layer image validation, papermill notebook execution
- Framework-specific conventions that would take a new contributor days to discover

**Why this matters at scale:** Only 2 of the 6 deeply analyzed repos have any agent rules. The repos with agent rules (odh-dashboard, notebooks) score **8-9/10**. The repos without them score **6/10**. That's not a coincidence — agent rules are living documentation. They benefit every contributor, not just AI. Running this tool across all RHOAI components would immediately raise the quality floor.

---

## Critical Actions

| # | Action | Effort | Impact |
|---|--------|--------|--------|
| 1 | Deploy Konflux Build Simulator across high-risk components | Medium | Prevents DSC-breaking build failures at PR time — directly addresses the 111-bug pattern |
| 2 | Re-enable `odh-model-controller` e2e on PRs | Low | Catches integration regressions before merge |
| 3 | Run Test Rules Generator on all component repos | Low | Instant agent rules — closes the biggest quality gap across the platform |
| 4 | Add `AGENTS.md` to Go operator repos | Low | Enables AI-assisted development and faster onboarding |

---

## The Tools in 30 Seconds

**Quality Repo Analysis** — "Here's your quality report card across all RHOAI components. Here's where you're strong, here's where you're exposed."

**Konflux Build Simulator** — "Here's exactly how your production build works, what can break, and a ready-to-use workflow that catches it on PRs. 111 DSC-breaking bugs say this matters."

**Test Rules Generator** — "Here's your team's testing DNA extracted into rules that any developer or AI agent can follow to write tests that match your conventions. It's the biggest gap we found — and the easiest to close."

All three run against real code, produce actionable output, and took minutes — not sprints.
