#!/usr/bin/env python3
"""Full end-to-end test: Historical bug coverage analysis for ODH Dashboard.

Fetches real bugs from Jira, analyzes test coverage in odh-dashboard codebase,
and generates a comprehensive HTML report.
"""

import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Tuple

# Add shared utilities to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

from jira_utils import require_env, search_jql
from report_generator import generate_bug_coverage_report


# Configuration - can be overridden via environment variables
REPO_PATH = os.environ.get('REPO_PATH', './odh-dashboard')
JQL_QUERY = os.environ.get('JQL_QUERY', 'project = MYPROJECT AND component = "Dashboard" AND issuetype = Bug AND priority in (Blocker, Critical) AND created >= -90d')


def find_test_files(repo_path: str) -> List[str]:
    """Find all test files in the repository."""
    test_files = []
    test_patterns = [
        '*.spec.ts', '*.spec.tsx', '*.test.ts', '*.test.tsx',  # Unit/mock tests
        '*.cy.ts', '*.cy.js',  # Cypress tests
        '*_test.go', '*_test.py'  # Go/Python tests
    ]

    print("📁 Discovering test files...")

    for root, dirs, files in os.walk(repo_path):
        # Skip node_modules, .git, etc.
        dirs[:] = [d for d in dirs if d not in ['node_modules', '.git', 'dist', 'build', '.next']]

        for file in files:
            if any(file.endswith(pattern.replace('*', '')) or
                   re.match(pattern.replace('*', '.*'), file) for pattern in test_patterns):
                test_files.append(os.path.join(root, file))

    print(f"✅ Found {len(test_files)} test files")
    return test_files


def derive_search_keywords(bug_summary: str) -> List[str]:
    """Derive 2-3 keyword search patterns from bug summary.

    Examples:
    - "OCI protocol trimmed" → ["oci", "protocol", "trim"]
    - "Project selector dropdown broken" → ["project", "selector", "dropdown"]
    - "GPU allocation fails on ARM" → ["gpu", "allocation", "arm"]
    """
    # Remove common words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                  'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been'}

    # Tokenize and clean
    words = re.findall(r'\b[a-zA-Z]{3,}\b', bug_summary.lower())
    keywords = [w for w in words if w not in stop_words]

    # Return top 3 most relevant (longer words first, then first occurrence)
    keywords.sort(key=lambda w: (-len(w), words.index(w)))
    return keywords[:3]


def search_test_coverage(bug_summary: str, test_files: List[str]) -> Tuple[str, str]:
    """Search test files for coverage of a bug.

    Returns:
        Tuple of (coverage_status, details)
        - coverage_status: COVERED, PARTIALLY COVERED, GAP, NOT TESTABLE
        - details: Description of findings
    """
    # Check for not testable signals
    not_testable_signals = [
        'build process', 'release', 'migration', 'one-off',
        'visual', 'styling', 'appearance', 'UI polish',
        'documentation', 'README', 'ci/cd', 'pipeline'
    ]

    summary_lower = bug_summary.lower()
    if any(signal in summary_lower for signal in not_testable_signals):
        return ("NOT TESTABLE", "Build/process/visual issue, not automatable in code tests")

    # Derive keywords
    keywords = derive_search_keywords(bug_summary)

    if not keywords:
        return ("GAP", "No searchable keywords derived from summary")

    # Search test files
    matches = []
    for test_file in test_files:
        try:
            with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()

                # Check if any keywords appear
                keyword_matches = [kw for kw in keywords if kw in content]

                if keyword_matches:
                    # Count occurrences
                    occurrences = sum(content.count(kw) for kw in keyword_matches)
                    matches.append((test_file, keyword_matches, occurrences))
        except Exception:
            continue

    if not matches:
        return ("GAP", f"No tests found for keywords: {', '.join(keywords)}")

    # Sort by relevance (more keyword matches + more occurrences)
    matches.sort(key=lambda m: (len(m[1]), m[2]), reverse=True)

    # Determine coverage level
    top_match = matches[0]
    matched_keywords = top_match[1]
    test_file_name = os.path.basename(top_match[0])

    # If all keywords matched in same file, likely covered
    if len(matched_keywords) >= 2:
        return ("COVERED", f"Test exists: {test_file_name} (keywords: {', '.join(matched_keywords)})")
    else:
        return ("PARTIALLY COVERED", f"Related tests in {test_file_name}, but specific scenario may be missing")


def classify_test_level(bug_summary: str, bug_labels: List[str]) -> Tuple[str, str]:
    """Classify the earliest feasible test level for a bug.

    Returns:
        Tuple of (test_level, rationale)
        - test_level: Unit, Mock, E2E, N/A
        - rationale: Explanation
    """
    summary_lower = bug_summary.lower()
    labels_lower = [label.lower() for label in bug_labels]

    # N/A signals
    na_signals = ['build', 'release', 'ci/cd', 'migration', 'visual', 'styling', 'documentation']
    if any(signal in summary_lower for signal in na_signals):
        return ("N/A", "Build/process/visual issue, not testable in code")

    # E2E signals
    e2e_signals = [
        'rbac', 'auth', 'permission', 'cluster', 'deployment',
        'upgrade', 'arm', 'power', 's390x', 'fips', 'disconnected',
        'operator', 'reconcile', 'crd', 'webhook', 'namespace', 'project creation'
    ]
    if any(signal in summary_lower for signal in e2e_signals):
        return ("E2E", "Requires real infrastructure, auth, or platform-specific testing")

    # Unit signals
    unit_signals = [
        'validation', 'parse', 'parsing', 'format', 'calculate', 'utility',
        'helper', 'default', 'config value', 'data transformation', 'trim', 'protocol'
    ]
    if any(signal in summary_lower for signal in unit_signals):
        return ("Unit", "Pure logic bug, testable in isolation")

    # Mock signals (component behavior)
    mock_signals = [
        'component', 'dropdown', 'form', 'button', 'modal', 'dialog',
        'render', 'display', 'show', 'hide', 'toggle', 'error message',
        'selector', 'input', 'checkbox', 'radio'
    ]
    if any(signal in summary_lower for signal in mock_signals):
        return ("Mock", "Component behavior, testable with mocked dependencies")

    # Default to Mock (safer than E2E)
    return ("Mock", "Unclear from summary, defaulting to Mock/Integration test")


def categorize_bug(bug_summary: str, bug_labels: List[str]) -> List[str]:
    """Categorize bug into functional and non-functional types."""
    categories = []

    summary_lower = bug_summary.lower()
    labels_lower = [label.lower() for label in bug_labels]

    # Upgrade issues (including 2.25 -> 3.3 migration)
    if any(label in labels_lower for label in ['upgrade-issue', 'upgrade', 'rhoai-3.3_migration']):
        categories.append('upgrade')
    elif any(word in summary_lower for word in ['upgrade', 'migration', '2.25', '3.3', '2.25 to 3.3']):
        categories.append('upgrade')

    # Disconnected/air-gap
    if 'disconnected' in labels_lower or 'airgap' in labels_lower:
        categories.append('disconnected')
    elif any(word in summary_lower for word in ['disconnected', 'air-gap', 'offline']):
        categories.append('disconnected')

    # FIPS
    if 'fips' in labels_lower or 'fips' in summary_lower:
        categories.append('fips')

    # Performance
    if 'performance' in labels_lower or 'perf' in labels_lower:
        categories.append('performance')
    elif any(word in summary_lower for word in ['slow', 'timeout', 'performance', 'latency', 'memory leak']):
        categories.append('performance')

    # Platform-specific
    platform_labels = ['arm', 'power', 's390x', 'ppc64le', 'aarch64']
    if any(pl in labels_lower for pl in platform_labels):
        categories.append('platform-specific')
    elif any(word in summary_lower for word in ['arm', 'power', 's390x', 'aarch64']):
        categories.append('platform-specific')

    # Security
    if 'security' in labels_lower or 'cve' in labels_lower:
        categories.append('security')
    elif any(word in summary_lower for word in ['cve', 'security', 'vulnerability', 'auth', 'rbac']):
        categories.append('security')

    # Default to functional
    if not categories:
        categories.append('functional')

    return categories


def analyze_bugs(bugs: List[Dict], test_files: List[str], jira_server: str) -> List[Dict]:
    """Analyze each bug for test coverage and classification."""
    analyzed_bugs = []
    total = len(bugs)

    print(f"\n🔍 Analyzing {total} bugs for test coverage...")

    for i, bug in enumerate(bugs, 1):
        if i % 10 == 0:
            print(f"   Progress: {i}/{total} ({int(i/total*100)}%)")

        fields = bug.get('fields', {})
        key = bug['key']
        summary = fields.get('summary', '')
        priority = fields.get('priority', {}).get('name', 'Unknown')
        status = fields.get('status', {}).get('name', 'Unknown')
        labels = fields.get('labels', [])

        # Analyze coverage
        coverage_status, coverage_details = search_test_coverage(summary, test_files)

        # Classify test level
        test_level, test_rationale = classify_test_level(summary, labels)

        # Categorize
        categories = categorize_bug(summary, labels)

        analyzed_bugs.append({
            'key': key,
            'priority': priority,
            'summary': summary,
            'status': status,
            'coverage': coverage_status,
            'testLevel': test_level,
            'categories': categories,
            'details': f"{coverage_details} | {test_rationale}",
            'jiraUrl': f"{jira_server}/browse/{key}"
        })

    print(f"✅ Analysis complete: {total} bugs processed")
    return analyzed_bugs


def print_statistics(bugs: List[Dict]):
    """Print analysis statistics."""
    total = len(bugs)

    # Coverage breakdown
    coverage_counts = {}
    for bug in bugs:
        status = bug['coverage']
        coverage_counts[status] = coverage_counts.get(status, 0) + 1

    # Test level breakdown
    level_counts = {}
    for bug in bugs:
        level = bug['testLevel']
        level_counts[level] = level_counts.get(level, 0) + 1

    # Category breakdown
    category_counts = {}
    for bug in bugs:
        for cat in bug['categories']:
            category_counts[cat] = category_counts.get(cat, 0) + 1

    print("\n" + "=" * 60)
    print("ANALYSIS STATISTICS")
    print("=" * 60)

    print(f"\n📊 Coverage Status:")
    for status, count in sorted(coverage_counts.items()):
        pct = int(count/total*100)
        print(f"   {status:20} {count:3} ({pct:2}%)")

    print(f"\n🎯 Test Level Classification:")
    for level, count in sorted(level_counts.items()):
        pct = int(count/total*100)
        print(f"   {level:20} {count:3} ({pct:2}%)")

    print(f"\n🏷️  Bug Categories:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        pct = int(count/total*100)
        print(f"   {cat:20} {count:3} ({pct:2}%)")


def main():
    """Run full end-to-end analysis."""
    print("\n" + "=" * 60)
    print("ODH Dashboard - Historical Bug Coverage Analysis")
    print("=" * 60)

    # Step 1: Validate environment
    print("\n1️⃣  Validating environment...")

    server, user, token = require_env()
    if not all([server, user, token]):
        print("❌ Jira credentials not configured")
        return 1

    if not os.path.exists(REPO_PATH):
        print(f"❌ Repository not found: {REPO_PATH}")
        return 1

    print(f"✅ Jira: {server}")
    print(f"✅ Repository: {REPO_PATH}")

    # Step 2: Find test files
    print("\n2️⃣  Discovering test infrastructure...")
    test_files = find_test_files(REPO_PATH)

    if not test_files:
        print("⚠️  No test files found in repository")
        return 1

    # Step 3: Fetch bugs from Jira
    print("\n3️⃣  Fetching bugs from Jira...")
    print(f"   JQL: {JQL_QUERY}")

    try:
        bugs = search_jql(
            server, user, token,
            jql=JQL_QUERY,
            fields=['key', 'summary', 'status', 'priority', 'labels', 'created'],
            max_results=100
        )

        print(f"✅ Fetched {len(bugs)} bugs")

    except Exception as e:
        print(f"❌ Failed to fetch bugs: {e}")
        return 1

    if not bugs:
        print("⚠️  No bugs returned from JQL query")
        return 1

    # Step 4: Analyze bugs
    print("\n4️⃣  Analyzing bug coverage...")
    analyzed_bugs = analyze_bugs(bugs, test_files, server)

    # Step 5: Print statistics
    print_statistics(analyzed_bugs)

    # Step 6: Generate HTML report
    print("\n5️⃣  Generating HTML report...")

    # Detect repo URL from git remote
    repo_url = ""
    try:
        import subprocess
        result = subprocess.run(
            ['git', '-C', REPO_PATH, 'config', '--get', 'remote.origin.url'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            repo_url = result.stdout.strip()
            if repo_url.startswith('git@'):
                repo_url = repo_url.replace(':', '/').replace('git@', 'https://')
            if repo_url.endswith('.git'):
                repo_url = repo_url[:-4]
    except:
        pass

    if not repo_url:
        repo_url = "<repository-url>"

    metadata = {
        "repoName": os.path.basename(REPO_PATH),
        "repoUrl": repo_url,
        "timestamp": datetime.now().isoformat() + "Z",
        "jql": JQL_QUERY,
        "totalCount": len(analyzed_bugs)
    }

    try:
        html = generate_bug_coverage_report(analyzed_bugs, metadata)

        output_file = os.path.join(os.getcwd(), f"{os.path.basename(REPO_PATH)}-bug-coverage-report.html")
        with open(output_file, 'w') as f:
            f.write(html)

        file_size = len(html)
        print(f"✅ Report generated: {output_file}")
        print(f"   File size: {file_size:,} bytes")
        print(f"   Bugs analyzed: {len(analyzed_bugs)}")

        print("\n" + "=" * 60)
        print("🎉 ANALYSIS COMPLETE!")
        print("=" * 60)
        print(f"\n📂 Open report in browser:")
        print(f"   file://{output_file}")

        return 0

    except Exception as e:
        print(f"❌ Report generation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
