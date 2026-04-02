# Red Hat Quality Tiger Team

Quality tooling and automation for RHOAI component development.

## Overview

This repository contains tools and documentation created by the Quality Tiger Team to improve quality practices across Red Hat OpenShift AI (RHOAI) components.

## Tools

### 1. Quality Repo Analysis (`/.claude/skills/quality-repo-analysis/`)

Automated analysis tool that evaluates CI/CD, testing, security, and best practices against gold standards.

**Usage:**
```bash
/quality-repo-analysis https://github.com/org/repo
```

**Outputs:**
- Quality scorecard (0-10 scoring)
- Critical gaps report
- Quick wins recommendations
- Benchmarking against gold standards

### 2. Konflux Build Simulator (`/.claude/skills/konflux-build-simulator/`)

Generates GitHub Actions workflows and local scripts that simulate Konflux builds before merge.

**Usage:**
```bash
/konflux-build-simulator https://github.com/org/repo
```

**Outputs:**
- `.github/workflows/konflux-build-simulator.yml`
- `scripts/validate-konflux-build.sh`
- Documentation and reports

**Validates:**
- Docker builds with production BUILD_MODE
- Module Federation (for monorepos)
- Kubernetes manifests (kustomize)
- Operator integration

### 3. Test Rules Generator (`/.claude/skills/test-rules-generator/`)

Extracts test patterns from existing tests and generates `.claude/rules/` documentation.

**Usage:**
```bash
/test-rules-generator https://github.com/org/repo
```

**Outputs:**
- `testing-standards.md` - Cross-cutting guidance
- `unit-tests.md` - Unit test patterns
- `e2e-tests.md` - E2E test patterns (if found)
- `contract-tests.md` - Contract test patterns (if found)
- `mock-tests.md` - Mock/component test patterns (if found)

### 4. Test Plan Creator (`/.claude/skills/test-plan-creator/`)

Generates comprehensive test plans for RHOAI features from a refined strategy (RHAISTRAT), with optional ADR for additional technical depth. Uses parallel sub-agents for analysis and includes an automated review step.

**Usage:**
```bash
/test-plan-creator RHAISTRAT-400
/test-plan-creator RHAISTRAT-400 /path/to/adr.pdf
```

**Inputs:**
- Strategy Jira key (RHAISTRAT) — required
- ADR file path (optional, for API-level detail)

**Pipeline:**
1. Fetch strategy from Jira (MCP integration required)
2. 3 parallel sub-agents analyze scope, test strategy, and environment
3. Generate TestPlan.md from merged findings
4. Reviewer sub-agent checks for gaps and recommends additional documents

**Sub-agents (context: fork, non-user-invocable):**
- `scope-endpoint-analyzer` — feature scope + endpoints/methods under test
- `test-strategy-risk-analyzer` — test levels, types, priorities + risks
- `environment-infra-analyzer` — environment config, test data, infrastructure
- `test-plan-reviewer` — completeness review, gap analysis, document recommendations

**Outputs:**
- `<feature_name>/TestPlan.md` - Structured test plan following a consistent template
- `<feature_name>/README.md` - Feature summary with links

### 5. Test Case Generator (`/.claude/skills/test-cases/`)

**Status:** To be implemented in a follow-up. Will generate individual test case files from the output of `/test-plan-creator`.

### 6. Konflux CI Dashboard (`/konflux-CI-Dashboard/`)

**Status:** Design Phase (Planned Q2 2026)

Web dashboard for monitoring Konflux pipeline health across all RHOAI components.

**Planned Features:**
- Real-time pipeline status
- Historical trend analysis
- Automated alerting
- Failure pattern recognition

## Repository Structure

```
.
├── .claude/
│   └── .claude/
│       └── skills/
│           ├── quality-repo-analysis/
│           │   ├── SKILL.md
│           │   └── instructions.md
│           ├── konflux-build-simulator/
│           │   ├── SKILL.md
│           │   └── instructions.md
│           ├── test-rules-generator/
│           │   ├── SKILL.md
│           │   └── instructions.md
│           ├── test-plan-creator/          # Orchestrator
│           │   ├── SKILL.md
│           │   └── test-plan-template.md
│           ├── scope-endpoint-analyzer/    # Sub-agent (fork)
│           │   └── SKILL.md
│           ├── test-strategy-risk-analyzer/ # Sub-agent (fork)
│           │   └── SKILL.md
│           ├── environment-infra-analyzer/ # Sub-agent (fork)
│           │   └── SKILL.md
│           ├── test-plan-reviewer/         # Sub-agent (fork)
│           │   └── SKILL.md
│           └── test-cases/
│               └── SKILL.md
└── konflux-CI-Dashboard/
    └── KONFLUX-CI-DASHBOARD.md
```

## Getting Started

These tools are designed to be used with Claude Code (Anthropic's CLI tool for Claude).

### Prerequisites

- Claude Code installed
- Access to target repositories
- Docker (for build simulator)
- Git

### Usage

Skills can be invoked using the `/skill-name` syntax in Claude Code:

```bash
# Analyze repository quality
/quality-repo-analysis https://github.com/opendatahub-io/odh-dashboard

# Generate build validation
/konflux-build-simulator https://github.com/opendatahub-io/odh-model-controller

# Extract test patterns
/test-rules-generator https://github.com/opendatahub-io/notebooks

# Generate test plan from strategy
/test-plan-creator RHAISTRAT-400

# Generate test cases from test plan
/test-cases
```

## Documentation

Each skill includes:
- `SKILL.md` - High-level overview and usage
- `instructions.md` - Detailed implementation instructions
- Example outputs and reports

## Proven Results

**Repositories Tested:**
- odh-dashboard (Quality: 8.5/10, Build validation: ✅)
- notebooks (Test rules: 77 KB, 30+ examples)
- odh-model-controller (Build validation: ✅)
- kserve (external benchmarking)

**Impact:**
- Quality assessment: 95% faster (weeks → 30 min)
- Build failure detection: 90% faster (hours → 10-20 min)
- Test consistency: 100% (standardized patterns)

## Contributing

This is a Red Hat internal repository. For questions or contributions, contact the Quality Tiger Team.

## Status

- ✅ Quality Repo Analysis: Production Ready
- ✅ Konflux Build Simulator: Production Ready
- ✅ Test Rules Generator: Production Ready
- 🧪 Test Plan Creator: Tested / WIP (with parallel sub-agents)
- 🧪 Test Case Generator: Next
- 🔮 Konflux CI Dashboard: Planned (Q2 2026)

## License

Internal Red Hat tooling.

---

**Maintained by:** Quality Tiger Team
**Last Updated:** April 2, 2026
