# Red Hat Quality Tiger Team

Quality tooling and automation for RHOAI component development.

[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-blue)](https://claude.ai/code)
[![Version](https://img.shields.io/badge/version-0.1.0-green)](./pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-orange)](./LICENSE)

## Overview

This repository contains tools and documentation created by the Quality Tiger Team to improve quality practices across Red Hat OpenShift AI (RHOAI) components.


## Tools

### 1. Risk Assessment (`/.claude/skills/risk-assessment/`)

Analyzes PRs for risk, test coverage, architecture impact, and cross-repo intelligence using parallel analyzer agents.

**Usage:**
```bash
/risk-assessment --pr PR_NUMBER [--repo REPO_PATH] [--headless] [--dry-run]
```

**Features:**
- Parallel analysis with 4 specialized agents
- Cross-repo intelligence integration
- Architecture impact assessment
- Test coverage verification
- Advisory-only system (never blocks PRs)

**Outputs:**
- PR comment with risk analysis
- Status check (informational)
- Detailed analysis reports

### 2. Historical Bug Coverage (`/.claude/skills/historical-bug-coverage/`)

Analyzes historical blocking and critical bugs from Jira, determines test coverage with deep inspection and confidence scoring.

**Usage:**
```bash
/historical-bug-coverage --jql "JQL_QUERY" --repo REPO_PATH [--external-tests PATH]
```

**Features:**
- Deep test analysis with assertion extraction
- 0-100% confidence scoring
- 80%+ confidence required for COVERED status
- Granular test levels (Unit, Mock, Component, Integration, E2E, Contract)
- Team feedback loop with mapping exports

**Outputs:**
- Interactive HTML report
- Bug-to-test mappings
- Coverage gap analysis

### 3. Quality Repo Analysis (`/.claude/skills/quality-repo-analysis/`)

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

### 4. Konflux Build Simulator (`/.claude/skills/konflux-build-simulator/`)

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

### 5. Test Rules Generator (`/.claude/skills/test-rules-generator/`)

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

### 6. Workflow Diagram Generator (`/.claude/skills/workflow-diagram-generator/`)

Generates Mermaid diagrams visualizing software development workflows and processes.

**Usage:**
```bash
/workflow-diagram-generator
```

**Outputs:**
- Mermaid diagram definitions (.mmd files)
- PNG renderings of diagrams
- Documentation of workflow processes

### 7. Quality Report Aggregator (`/aggregate_quality_reports.py`)

Aggregates quality analysis reports across multiple repositories and generates combined reports with statistics.

**Usage:**
```bash
# Generate analysis commands for all configured repos
python aggregate_quality_reports.py --generate-commands

# Process existing reports and create combined report
python aggregate_quality_reports.py --reports-dir ./quality_reports \
  --output-md combined_report.md \
  --output-json summary.json
```

**Outputs:**
- Combined markdown report with cross-repo statistics
- JSON export for programmatic analysis
- Analysis command lists for batch processing

**Features:**
- Analyzes 20+ RHOAI component repositories
- Supports Upstream (opendatahub-io), Downstream (RHODS), and External repos
- Identifies common gaps and quick wins
- Tracks quality trends across repository groups

See [AGGREGATOR_README.md](./AGGREGATOR_README.md) for detailed documentation.

## Repository Structure

```
.
├── .claude/
│   └── skills/
│       ├── risk-assessment/          # PR risk analysis
│       │   ├── SKILL.md
│       │   └── scripts/
│       ├── historical-bug-coverage/  # Bug test coverage analysis
│       │   ├── SKILL.md
│       │   └── *.py
│       ├── quality-repo-analysis/    # Repository quality assessment
│       │   ├── SKILL.md
│       │   └── instructions.md
│       ├── konflux-build-simulator/  # Build validation
│       │   ├── SKILL.md
│       │   └── instructions.md
│       ├── test-rules-generator/     # Test pattern extraction
│       │   ├── SKILL.md
│       │   └── instructions.md
│       ├── workflow-diagram-generator/ # Mermaid diagrams
│       │   └── SKILL.md
│       └── shared/                   # Shared utilities
│           ├── fingerprint_utils.py
│           ├── jira_utils.py
│           └── report_generator.py
├── .claude-plugin/
│   └── plugin.json                   # Plugin metadata & autocomplete
├── docs/
│   └── diagrams/
├── pyproject.toml                    # Python package definition
├── aggregate_quality_reports.py     # Report aggregation tool
├── repos_config.yaml                 # Repository configuration
├── run_batch_analysis.sh            # Batch analysis helper
├── AGGREGATOR_README.md             # Aggregator documentation
├── WORKFLOW.md                      # Analysis workflow guide
└── README.md
```

## Installation

### As a Claude Code Plugin

This repository is packaged as a formal Claude Code plugin with autocomplete support.

**Option 1: Clone and Use Locally**
```bash
git clone https://github.com/antowaddle/Red-Hat-Quality-Tiger-Team.git
cd Red-Hat-Quality-Tiger-Team
```

**Option 2: Install Dependencies**
```bash
# Using uv (recommended)
uv pip install -r requirements.txt

# Using pip
pip install -r requirements.txt
```

The plugin structure includes:
- `.claude-plugin/plugin.json` - Plugin metadata and autocomplete configuration
- `pyproject.toml` - Python package definition and dependencies
- `.claude/skills/` - All skill implementations

### Prerequisites

- Claude Code installed
- Python 3.10 or higher
- Access to target repositories
- Docker (for build simulator)
- Git

### Plugin Features

✅ **Autocomplete Support** - All skills show up with autocomplete in Claude Code  
✅ **Structured Metadata** - Consistent skill frontmatter for better discovery  
✅ **Dependency Management** - Automatic Python dependency resolution  
✅ **Version Control** - Semantic versioning via pyproject.toml  
✅ **Categorization** - Skills organized by category (evaluation, testing, quality)  

## Getting Started

### Usage

Skills can be invoked using the `/skill-name` syntax in Claude Code. **Autocomplete is enabled** - just type `/` to see all available skills:

```bash
# Analyze PR risk (parallel agents)
/risk-assessment --pr 123 --repo ./odh-dashboard

# Analyze historical bug coverage
/historical-bug-coverage --jql "project = RHOAIENG AND priority = Critical" --repo ./odh-dashboard

# Analyze repository quality
/quality-repo-analysis https://github.com/opendatahub-io/odh-dashboard

# Generate build validation
/konflux-build-simulator https://github.com/opendatahub-io/odh-model-controller

# Extract test patterns
/test-rules-generator https://github.com/opendatahub-io/notebooks

# Generate workflow diagrams
/workflow-diagram-generator
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

- ✅ **Plugin Structure**: Production Ready (v0.1.0)
- ✅ Risk Assessment: Production Ready
- ✅ Historical Bug Coverage: Production Ready
- ✅ Quality Repo Analysis: Production Ready
- ✅ Konflux Build Simulator: Production Ready
- ✅ Test Rules Generator: Production Ready
- ✅ Workflow Diagram Generator: Production Ready
- ✅ Quality Report Aggregator: Production Ready

## License

Internal Red Hat tooling.

---

**Maintained by:** Quality Tiger Team
**Last Updated:** April 8, 2026
