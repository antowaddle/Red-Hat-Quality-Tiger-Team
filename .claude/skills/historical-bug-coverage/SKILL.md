---
name: analyzing-historical-bug-coverage
description: Analyzes historical blocking and critical bugs from Jira, determines what test coverage exists today with deep test inspection and confidence scoring, and generates standalone HTML reports. Use when assessing test gaps for a repository, analyzing bug coverage quality, or generating coverage reports from Jira data.
---

# Historical Bug Test Coverage Analysis

Analyzes historical blocking and critical bugs from Jira, determines what test coverage exists today, and generates a comprehensive HTML report with deep test analysis and confidence scoring.

## Features

**Deep Test Analysis** - Reads test files and extracts actual assertions to understand what tests validate  
**Confidence Scoring** - 0-100% match quality scores for each bug-test mapping  
**Coverage Criteria** - 80%+ confidence required for COVERED status  
**Test File Visibility** - Shows exactly which test covers each bug  
**Granular Test Levels** - Unit, Mock, Component, Integration, E2E (Upstream/Downstream), Contract  
**Team Feedback Loop** - Export mappings for validation and continuous improvement  

## Usage

```bash
/historical-bug-coverage --jql "JQL_QUERY" --repo REPO_PATH [options]
```

### Basic Examples

```bash
# Analyze critical bugs for a component
/historical-bug-coverage \
  --jql "project = MYPROJECT AND component = 'Dashboard' AND priority in (Blocker, Critical)" \
  --repo /path/to/my-repo

# Include external test repository
/historical-bug-coverage \
  --jql "project = MYPROJECT AND component = 'Model Registry'" \
  --repo /path/to/model-registry \
  --external-tests /path/to/e2e-tests/model_registry

# Filter by time range
/historical-bug-coverage \
  --jql "project = MYPROJECT AND priority = Critical AND created >= -90d" \
  --repo /path/to/my-repo

# Multiple bug categories
/historical-bug-coverage \
  --jql "project = MYPROJECT AND (labels = upgrade-issue OR labels = fips)" \
  --repo /path/to/my-repo
```

## How It Works

**Deep Test Analysis** - Reads matched test files, extracts assertions, and calculates 0-100% confidence scores based on entity matches and scenario validation.

**Strict Coverage Thresholds:**
- **COVERED** (≥80%): Test explicitly validates the failure scenario
- **PARTIALLY COVERED** (60-80%): Test covers related aspects
- **GAP** (<60%): No test validates this scenario
- **NOT TESTABLE**: Build/deployment/visual issue (not automatable)

**Test Level Classification** - Assigns earliest feasible level: Unit → Mock → Component → Integration → E2E → Contract

**Auto-Categorization** - Detects upgrade, platform-specific (ARM/Power/s390x), FIPS, performance, security, and disconnected environment issues

## Output

Generates standalone HTML report with:
- **Sortable/filterable table** with bug key, priority, coverage status, test file path, confidence score, test level, categories
- **Color-coded rows** by coverage status with confidence badges (Green/Orange/Red)
- **SVG charts** for coverage distribution and test level breakdown
- **E2E breakdown** categorized by type (Auth, Deployment, Platform, Upgrade)
- **Recommendations** for prioritized test gaps
- **Print-friendly** layout (PDF export)

## Team Feedback

HTML report includes coverage mappings that teams can validate. Future: export to JSON for systematic review and continuous learning.

## Prerequisites

### Python Requirements

- Python 3.8 or higher
- Optional: `openpyxl` (only for `compare_analyses.py` Excel export feature)

### Jira Configuration

Set up environment variables:

```bash
# Create .env file in your home directory or project root
cat > ~/.env <<EOF
JIRA_SERVER=https://yourcompany.atlassian.net
JIRA_USER=your.email@company.com
JIRA_TOKEN=your-api-token
EOF

# Or specify custom location
export JIRA_ENV_FILE=/path/to/your/.env
```

**Environment variable priority:**
1. `$JIRA_ENV_FILE` (if set)
2. `$(pwd)/.env` (current directory)
3. `$HOME/.env` (home directory)
4. `$HOME/.claude/.env` (Claude config directory)

### Repository Access

- Target repository must be accessible (local path or cloneable)
- Git remote origin URL auto-detected for report links
- External test repositories supported via `--external-tests`

## Command Options

| Option | Description | Required |
|--------|-------------|----------|
| `--jql` | JQL query string | Yes (or --filter) |
| `--filter` | Saved Jira filter ID | Yes (or --jql) |
| `--repo` | Target repository path | Yes |
| `--external-tests` | External test repository path | No |
| `--output` | Output HTML file path | No (auto-generated) |

## JQL Query Examples

```jql
# Critical bugs in last 90 days
project = MYPROJECT AND priority = Critical AND created >= -90d

# Specific categories
project = MYPROJECT AND labels in (upgrade-issue, fips, arm, disconnected)
```

## Output Location

Auto-generated in current directory as `{repo-name}-bug-coverage.html`

## Success Metrics

85%+ accuracy for COVERED bugs, <10% false positives, actionable test gap identification.

## Expected Results

Typical: ~10-15% COVERED, ~10-15% PARTIAL, ~70-75% GAP, ~1-5% NOT TESTABLE. Test files visible for all matches with confidence scores for prioritization.

## Time Estimate

- Small repo (<50 bugs): 5-10 minutes
- Medium repo (50-200 bugs): 10-20 minutes
- Large repo (200+ bugs): 20-40 minutes

## References

For detailed implementation guidance:

- **[instructions.md](instructions.md)** - Step-by-step agent execution workflow
- **[coverage_rubric.py](coverage_rubric.py)** - Team feedback and learning system
- **[strict_coverage_analysis.py](strict_coverage_analysis.py)** - Deep test analysis engine
- **[test_analysis.py](test_analysis.py)** - Test file parsing (Jest/Cypress/pytest/Go)
- **[repository_discovery.py](repository_discovery.py)** - Test infrastructure discovery

## Related Skills

- **test-rules-generator** - Generate test creation rules if missing
- **quality-repo-analysis** - Assess overall repository quality

## Support

Report issues at: https://github.com/anthropics/claude-code/issues
