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

## What It Analyzes

### 1. Deep Test Analysis

Instead of simple keyword matching, the skill:
- **Reads matched test files** and extracts test cases
- **Parses assertions** (expect, assert, should statements)
- **Infers what tests validate** (error handling, permissions, state transitions, etc.)
- **Calculates confidence scores** (0-100%) based on entity matches, scenario validation, and assertion specificity

### 2. Strict Coverage Assessment

Each bug is classified with strict criteria:

| Status | Criteria | Confidence Threshold |
|--------|----------|---------------------|
| **COVERED** | Test explicitly validates the failure scenario | ≥ 80% |
| **PARTIALLY COVERED** | Test covers related aspects but not the exact scenario | 60-80% |
| **GAP** | No test validates this scenario | < 60% |
| **NOT TESTABLE** | Build/deployment/visual issue, not automatable | N/A |

### 3. Granular Test Level Classification

Assigns the **earliest feasible test level** using the test pyramid:

| Level | When to Use | Example |
|-------|-------------|---------|
| **Unit** | Pure logic bug | Validation, parsing, calculation errors |
| **Mock** | Component behavior bug | UI rendering, form validation with mocked APIs |
| **Component** | Python upstream component tests | Component tests with mocked dependencies |
| **Integration** | Multi-component interactions | Service-to-service communication |
| **E2E (Upstream)** | End-to-end in same repo | Full workflow in main repository |
| **E2E (Downstream)** | External test repo | Tests in separate e2e-tests repository |
| **Contract** | API contract validation | BFF/API schema validation |

### 4. Non-Functional Bug Detection

Automatically categorizes:
- **Upgrade Issues** - Version migration bugs
- **Platform-Specific** - ARM, Power, s390x architecture issues
- **FIPS** - FIPS compliance issues
- **Performance** - Performance degradation, resource issues
- **Security** - CVEs, auth issues, RBAC problems
- **Disconnected** - Air-gap environment issues

## Output

Generates a **standalone HTML report** with:

### Interactive Features

- **Sortable table** - Click column headers to sort
- **Real-time filtering** - Search and filter by priority, coverage, test level
- **Color-coded rows** - Visual distinction between coverage statuses
- **Confidence badges** - Green (80%+), Orange (60-80%), Red (<60%)
- **Test file links** - See exactly which test covers each bug
- **SVG charts** - Coverage distribution and test level breakdown
- **PDF export** - Print-friendly layout

### Report Sections

1. **Summary Dashboard** - Coverage stats and test level distribution
2. **Bug Table** - Sortable, filterable table with:
   - Key (linked to Jira)
   - Priority
   - Summary
   - Coverage Status
   - Test File
   - Confidence Score
   - Test Level
   - Categories
   - Match Details
3. **E2E Breakdown** - E2E tests categorized by type (Auth, Deployment, Platform, etc.)
4. **Recommendations** - Prioritized test gaps to fill

### Table Columns

| Column | Description |
|--------|-------------|
| **Key** | Jira issue key (clickable link) |
| **Priority** | Blocker/Critical badge |
| **Summary** | Bug description |
| **Coverage** | COVERED/PARTIAL/GAP/NOT TESTABLE |
| **Test File** | Path to test that covers this bug (monospace font) |
| **Confidence** | 0-100% match quality (color-coded badge) |
| **Test Level** | Unit/Mock/E2E-Upstream/E2E-Downstream/etc. |
| **Categories** | functional, upgrade, security, etc. |
| **Details** | Match reason and recommendation |

### Example Output

```
MYPROJECT-12345 | Critical | User gets error when deleting | COVERED | 
  frontend/src/__tests__/Permissions.spec.tsx | 85% | Mock | 
  Test validates permission error on delete

MYPROJECT-12346 | Critical | Deployment gets stuck in pending | GAP |
  N/A | 0% | E2E | No tests found for deployment lifecycle
```

## Team Feedback Loop

Export coverage mappings for team validation:

```bash
# Analysis generates mappings automatically
# Teams can review and validate in the HTML report

# Future: Export to JSON for systematic review
# Click "Export Mappings" button in report
# Team fills in validation_status: correct/incorrect/partial
# System learns and improves future matching
```

## Prerequisites

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
# All blocker/critical bugs
project = MYPROJECT AND priority in (Blocker, Critical)

# Recent critical bugs
project = MYPROJECT AND priority = Critical AND created >= -90d

# Upgrade issues
project = MYPROJECT AND labels = upgrade-issue

# FIPS compliance issues
project = MYPROJECT AND labels = fips

# Platform-specific (ARM, Power, s390x)
project = MYPROJECT AND (labels in (arm, power, s390x) OR summary ~ "ARM")

# Security issues
project = MYPROJECT AND (labels = security OR summary ~ "CVE")

# Multiple categories
project = MYPROJECT AND (labels = upgrade-issue OR labels = fips OR labels = disconnected)
```

## Output Location

Reports are generated in the current working directory:

```bash
# Auto-generated filename
{repo-name}-bug-coverage.html

# Examples
odh-dashboard-bug-coverage.html
model-registry-bug-coverage.html
kserve-bug-coverage.html
```

## Success Metrics

- **Accuracy**: 85%+ of COVERED bugs should be correct
- **False Positives**: < 10% (marking GAP as COVERED)
- **Usefulness**: Teams can identify real test gaps to fill
- **Feedback Loop**: Teams validate → system learns → improves

## Expected Results

Typical coverage results:
- **COVERED**: ~10-15% (high-confidence matches)
- **PARTIALLY COVERED**: ~10-15% (related tests exist)
- **GAP**: ~70-75% (no automated tests found)
- **NOT TESTABLE**: ~1-5% (build/deployment/visual issues)

Test files are visible for each match, and confidence scores help prioritize review.

## Security

All user input is properly escaped to prevent XSS attacks:
- HTML output properly escaped
- JSON embedding XSS-safe
- No command injection risks
- Safe file operations

## Time Estimate

- Small repo (<50 bugs): 5-10 minutes
- Medium repo (50-200 bugs): 10-20 minutes
- Large repo (200+ bugs): 20-40 minutes

## Related Skills

- **test-rules-generator** - Generate test creation rules if missing
- **quality-repo-analysis** - Assess overall repository quality

## Support

Report issues at: https://github.com/anthropics/claude-code/issues
