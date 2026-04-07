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

### 4. Test Plan Creator (`/.claude/skills/tplan.create/`)

Generates comprehensive test plans for RHOAI features from a refined strategy (RHAISTRAT), with optional ADR for additional technical depth. Uses parallel sub-agents for analysis and includes an automated review step.

**Usage:**
```bash
/tplan.create RHAISTRAT-400
/tplan.create RHAISTRAT-400 /path/to/adr.pdf
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
- `tplan.analyze.endpoints` — feature scope + endpoints/methods under test
- `tplan.analyze.risks` — test levels, types, priorities + risks
- `tplan.analyze.infra` — environment config, test data, infrastructure
- `tplan.review` — completeness review, gap analysis, document recommendations

**Outputs:**
- `<feature_name>/TestPlan.md` - Structured test plan following a consistent template
- `<feature_name>/README.md` - Feature summary with links

### 5. Test Case Generator (`/.claude/skills/tcases.create/`)

Generates individual test case specification files from an existing test plan. Designed to run after `/tplan.create`.

**Usage:**
```bash
/tcases.create
/tcases.create mcp_catalog
```

**Inputs:**
- Auto-detects feature directory if run after `/tplan.create` in the same session
- Otherwise accepts a feature directory path or asks interactively

**Outputs:**
- `<feature_dir>/test_cases/TC-<CATEGORY>-<NUMBER>.md` — Individual test case files
- `<feature_dir>/test_cases/INDEX.md` — Test case index with stats
- Updates TestPlan.md Sections 5, 5.1, 8.1, 8.2

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
│   └── skills/
│       ├── quality-repo-analysis/
│       │   ├── SKILL.md
│       │   └── instructions.md
│       ├── konflux-build-simulator/
│       │   ├── SKILL.md
│       │   └── instructions.md
│       ├── test-rules-generator/
│       │   ├── SKILL.md
│       │   └── instructions.md
│       ├── tplan.create/               # Orchestrator
│       │   ├── SKILL.md
│       │   └── test-plan-template.md
│       ├── tplan.analyze.endpoints/    # Sub-agent (fork)
│       │   └── SKILL.md
│       ├── tplan.analyze.risks/        # Sub-agent (fork)
│       │   └── SKILL.md
│       ├── tplan.analyze.infra/        # Sub-agent (fork)
│       │   └── SKILL.md
│       ├── tplan.review/               # Sub-agent (fork)
│       │   └── SKILL.md
│       └── tcases.create/
│           ├── SKILL.md
│           └── test-case-template.md
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
/tplan.create RHAISTRAT-400

# Generate test cases from test plan
/tcases.create
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
- 🧪 Test Case Generator: Tested / WIP
- 🔮 Konflux CI Dashboard: Planned (Q2 2026)

## License

Internal Red Hat tooling.

---

**Maintained by:** Quality Tiger Team
**Last Updated:** April 2, 2026
