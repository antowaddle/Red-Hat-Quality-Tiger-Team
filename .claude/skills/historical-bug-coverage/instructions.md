# Historical Bug Test Coverage Analysis - Agent Instructions

## Table of Contents

- [Objective](#objective)
- [Inputs](#inputs)
- [Key Principles](#key-principles)
- [Execution Workflow](#execution-workflow)
  - [Step 1: Repository Test Discovery](#step-1-repository-test-discovery)
  - [Step 2: Environment Validation](#step-2-environment-validation)
  - [Step 3: Fetch Bugs from Jira](#step-3-fetch-bugs-from-jira)
  - [Step 4: Strict Coverage Analysis](#step-4-strict-coverage-analysis-with-deep-test-analysis)
  - [Step 5: Test Level Classification](#step-5-test-level-classification)
  - [Step 6: Generate HTML Report](#step-6-generate-html-report)
- [Deep Test Analysis](#deep-test-analysis)
- [Security](#security)
- [Output](#output)
- [Error Handling](#error-handling)
- [Example Output](#example-output)
- [Quality Checks](#quality-checks)
- [Performance](#performance)
- [Success Criteria](#success-criteria)

## Objective

Analyze historical blocking and critical bugs from Jira, assess test coverage with deep test analysis, and generate a comprehensive HTML report with confidence scores.

## Inputs

- `--jql` OR `--filter`: JQL query or saved filter ID
- `--repo`: Target repository path (required)
- `--external-tests`: External test repository path (optional)
- `--output`: Output HTML file path (optional, auto-generated)

## Key Principles

**CRITICAL**: This skill uses **strict coverage analysis with deep test inspection**, not keyword matching.

1. **Read actual test files** to understand what they validate
2. **Calculate confidence scores** (0-100%) for each bug-test match
3. **Require 80%+ confidence** for COVERED status
4. **Show test file paths** so teams can verify matches
5. **Distinguish E2E upstream vs downstream** tests

## Execution Workflow

Copy this checklist and track your progress:
- [ ] Step 1: Repository test discovery
- [ ] Step 2: Environment validation
- [ ] Step 3: Fetch bugs from Jira
- [ ] Step 4: Strict coverage analysis
- [ ] Step 5: Test level classification
- [ ] Step 6: Generate HTML report

### Step 1: Repository Test Discovery

Discover all test infrastructure before analyzing bugs:

```python
from repository_discovery import discover_repository_tests

test_capabilities = discover_repository_tests(repo_path, external_tests_path)
```

**Output**: Test frameworks, test types, available test levels

### Step 2: Environment Validation

```python
from shared.jira_utils import require_env

server, user, token = require_env()
# Validates JIRA_SERVER, JIRA_USER, JIRA_TOKEN
```

### Step 3: Fetch Bugs from Jira

```python
from shared.jira_utils import api_call

# Use cursor-based pagination
body = {
    "jql": jql_query,
    "fields": ["key", "summary", "status", "priority", "components", "labels"],
    "maxResults": 100
}

bugs = []
is_last = False
next_page_token = None

while not is_last:
    if next_page_token:
        body["nextPageToken"] = next_page_token
    
    result = api_call(server, "/search/jql", user, token, body=body, method="POST")
    bugs.extend(result.get("issues", []))
    is_last = result.get("isLast", True)
    next_page_token = result.get("nextPageToken")
```

### Step 4: Strict Coverage Analysis (with Deep Test Analysis)

For each bug, use `strict_coverage_search()`:

```python
from strict_coverage_analysis import strict_coverage_search

coverage_status, test_file_path, confidence_score, details = strict_coverage_search(
    bug_key=bug_key,
    bug_summary=bug_summary,
    bug_labels=bug_labels,
    test_capabilities=test_capabilities,
    test_files=test_files
)
```

**This function**:
1. Extracts entities (components, functions, APIs) from bug summary
2. Extracts scenario keywords (failure conditions)
3. Searches for test files matching those entities
4. **Reads matched test files** and extracts assertions
5. **Calculates confidence score** based on:
   - Entity matches (30 points)
   - Scenario matches (30 points)
   - Assertion validation (40 points)
6. Returns coverage status, test file path, confidence, and details

**Coverage Thresholds**:
- **COVERED**: ≥80% confidence
- **PARTIALLY COVERED**: 60-80% confidence
- **GAP**: <60% confidence
- **NOT TESTABLE**: Build/deployment/visual issues

### Step 5: Test Level Classification

```python
from strict_coverage_analysis import classify_test_level_strict

test_level, rationale = classify_test_level_strict(
    bug_summary=bug_summary,
    bug_labels=bug_labels,
    test_capabilities=test_capabilities
)
```

**Test Pyramid** (earliest feasible level):
- **Unit** - Pure logic bugs
- **Mock** - Component behavior with mocked APIs
- **Component** - Python component tests
- **Integration** - Multi-component interactions
- **E2E (Upstream)** - End-to-end in same repo
- **E2E (Downstream)** - External test repo
- **Contract** - API contract validation

### Step 6: Generate HTML Report

```python
from shared.report_generator import generate_bug_coverage_report

html = generate_bug_coverage_report(bugs, metadata)

with open(output_file, 'w') as f:
    f.write(html)
```

**Bug data structure**:
```python
{
    'key': 'MYPROJECT-12345',
    'priority': 'Critical',
    'summary': 'User gets error...',
    'coverage': 'COVERED',
    'testFile': 'frontend/src/__tests__/Component.spec.tsx',
    'confidence': 85.0,  # 0-100 match score
    'testLevel': 'Mock',
    'categories': ['functional'],
    'details': 'Test validates...',
    'jiraUrl': 'https://jira.company.com/browse/MYPROJECT-12345'
}
```

## Deep Test Analysis

The `test_analysis.py` module provides:

```python
from test_analysis import extract_test_cases, match_test_to_bug_scenario

# Extract test assertions from file
test_assertions = extract_test_cases(file_path, content, framework)

# Match test to bug scenario
is_match, confidence, reason = match_test_to_bug_scenario(
    bug_summary,
    test_assertion,
    bug_entities,
    bug_scenarios
)
```

**Supported frameworks**: Jest, Cypress, pytest, Go testing, Ginkgo

## Security

All user-controlled data is escaped to prevent XSS:
- HTML escaping via `html.escape()`
- JSON embedding via `_safe_json_embed()`
- See `SECURITY_AUDIT.md` for details

## Output

Generates standalone HTML report at:
- Default: `{repo-name}-bug-coverage.html` in current directory
- Custom: Specified via `--output`

**Report features**:
- Sortable/filterable table
- Test File column
- Confidence score badges
- E2E upstream/downstream distinction
- SVG charts (no external dependencies)
- Print-friendly (PDF export)

## Error Handling

**Missing .env file**:
```
Error: .env file not found
Searched locations:
  - $JIRA_ENV_FILE (if set)
  - $(pwd)/.env
  - $HOME/.env
  - $HOME/.claude/.env
```

**No tests found**:
```
⚠️  No test files discovered
📊 Coverage: GAP (100%)
💡 Recommend running: /test-rules-generator
```

**Jira API errors**: Auto-retry with exponential backoff (handled in `jira_utils.py`)

## Example Output

```
============================================================
STRICT Historical Bug Coverage Analysis
============================================================

✅ Discovered 341 test files
   pytest: 90, jest: 40, cypress: 37, go-testing: 105

✅ Fetched 65 bugs

📊 Coverage Status:
   COVERED                5 ( 7%)  ← Realistic, high-confidence
   PARTIALLY COVERED      7 (10%)
   GAP                   50 (76%)
   NOT TESTABLE           3 ( 4%)

🎯 Test Level Classification:
   Unit                  52 (80%)
   Mock                   8 (12%)
   E2E                    4 ( 6%)

✅ Report generated: model-registry-bug-coverage.html
   File size: 81,519 bytes
   Open: file:///path/to/model-registry-bug-coverage.html
```

## Quality Checks

Before finalizing:
- [ ] All bugs have coverage status
- [ ] All bugs have test level classification
- [ ] Confidence scores calculated for matches
- [ ] Test file paths shown for COVERED/PARTIAL bugs
- [ ] E2E upstream/downstream correctly distinguished
- [ ] HTML report self-contained (no CDN links)
- [ ] XSS protections in place
- [ ] Charts render correctly
- [ ] Filters and sorting work

## Performance

- Use repository discovery once (cache results)
- Batch Jira API calls (cursor pagination)
- Read test files only when needed (for deep analysis)
- Typical runtime: 10-30 minutes for 200-400 bugs

## Success Criteria

- ✅ Accuracy: 85%+ of COVERED bugs are correct
- ✅ False positives: <10%
- ✅ Test files visible for verification
- ✅ Confidence scores help prioritize review
- ✅ Teams can validate and provide feedback
