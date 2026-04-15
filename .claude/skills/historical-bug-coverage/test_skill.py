#!/usr/bin/env python3
"""Test script for historical bug coverage analysis skill.

Tests:
1. Jira connection and search
2. Mock bug coverage analysis
3. HTML report generation
"""

import os
import sys
from datetime import datetime

# Add shared utilities to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

from jira_utils import require_env, search_jql
from report_generator import generate_bug_coverage_report


def test_jira_connection():
    """Test Jira API connection and JQL search."""
    print("=" * 60)
    print("TEST 1: Jira Connection and JQL Search")
    print("=" * 60)

    server, user, token = require_env()

    if not all([server, user, token]):
        print("❌ Jira credentials not configured")
        print("\nSet environment variables:")
        print("  export JIRA_SERVER=https://redhat.atlassian.net")
        print("  export JIRA_USER=your-email@redhat.com")
        print("  export JIRA_TOKEN=your-api-token")
        return False

    print(f"✅ Jira server: {server}")
    print(f"✅ Jira user: {user}")
    print(f"✅ Token configured: {token[:20]}...")

    # Test JQL search - fetch recent ODH Dashboard critical bugs
    jql = 'project = RHOAIENG AND component = "AI Core Dashboard" AND priority = Critical AND created >= -90d'

    print(f"\n🔍 Testing JQL query:")
    print(f"   {jql}")

    try:
        bugs = search_jql(
            server, user, token,
            jql=jql,
            fields=['key', 'summary', 'status', 'priority', 'labels', 'created'],
            max_results=10
        )

        print(f"\n✅ Successfully fetched {len(bugs)} bugs")

        if bugs:
            print("\n📋 Sample bugs:")
            for i, bug in enumerate(bugs[:3], 1):
                fields = bug.get('fields', {})
                print(f"\n{i}. {bug['key']}: {fields.get('summary', 'N/A')}")
                print(f"   Priority: {fields.get('priority', {}).get('name', 'N/A')}")
                print(f"   Status: {fields.get('status', {}).get('name', 'N/A')}")
                labels = fields.get('labels', [])
                if labels:
                    print(f"   Labels: {', '.join(labels[:5])}")

        return True

    except Exception as e:
        print(f"\n❌ JQL search failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_report_generation():
    """Test HTML report generation with mock data."""
    print("\n" + "=" * 60)
    print("TEST 2: HTML Report Generation")
    print("=" * 60)

    # Mock bug data
    mock_bugs = [
        {
            "key": "RHOAIENG-12345",
            "priority": "Critical",
            "summary": "OCI protocol trimmed causing image pull failures",
            "coverage": "GAP",
            "testLevel": "Unit",
            "categories": ["functional"],
            "details": "No tests found for OCI protocol handling. Should add unit tests for URL parsing logic.",
            "jiraUrl": "https://redhat.atlassian.net/browse/RHOAIENG-12345"
        },
        {
            "key": "RHOAIENG-12346",
            "priority": "Blocker",
            "summary": "RBAC check fails for non-admin users in project creation",
            "coverage": "PARTIALLY COVERED",
            "testLevel": "E2E",
            "categories": ["functional", "security"],
            "details": "E2E tests exist for admin users, but non-admin scenarios are missing.",
            "jiraUrl": "https://redhat.atlassian.net/browse/RHOAIENG-12346"
        },
        {
            "key": "RHOAIENG-12347",
            "priority": "Critical",
            "summary": "Dropdown selector doesn't show selected value",
            "coverage": "COVERED",
            "testLevel": "Mock",
            "categories": ["functional"],
            "details": "Covered by mock tests in __tests__/components/ProjectSelector.spec.tsx",
            "jiraUrl": "https://redhat.atlassian.net/browse/RHOAIENG-12347"
        },
        {
            "key": "RHOAIENG-12348",
            "priority": "Critical",
            "summary": "Upgrade from 2.25 to 3.3 fails on FIPS clusters",
            "coverage": "GAP",
            "testLevel": "E2E",
            "categories": ["upgrade", "fips", "platform-specific"],
            "details": "No upgrade tests for FIPS environments. Needs E2E test with real cluster.",
            "jiraUrl": "https://redhat.atlassian.net/browse/RHOAIENG-12348"
        },
        {
            "key": "RHOAIENG-12349",
            "priority": "Critical",
            "summary": "GPU allocation fails on ARM architecture",
            "coverage": "GAP",
            "testLevel": "E2E",
            "categories": ["platform-specific"],
            "details": "No ARM-specific tests. Needs E2E testing on ARM cluster.",
            "jiraUrl": "https://redhat.atlassian.net/browse/RHOAIENG-12349"
        },
    ]

    metadata = {
        "repoName": "odh-dashboard",
        "repoUrl": "https://github.com/opendatahub-io/odh-dashboard",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "jql": 'project = RHOAIENG AND component = "AI Core Dashboard" AND priority in (Blocker, Critical)',
        "totalCount": len(mock_bugs)
    }

    print(f"\n📊 Generating report with {len(mock_bugs)} mock bugs...")

    try:
        html = generate_bug_coverage_report(mock_bugs, metadata)

        # Validate HTML structure
        assert '<!DOCTYPE html>' in html, "Missing DOCTYPE"
        assert '<html lang="en">' in html, "Missing html tag"
        assert 'Historical Bug Test Coverage Analysis' in html, "Missing title"
        assert 'odh-dashboard' in html, "Missing repo name"
        assert 'RHOAIENG-12345' in html, "Missing bug key"

        # Write to file
        output_file = "/Users/acoughli/qualityTigerTeam/test-bug-coverage-report.html"
        with open(output_file, 'w') as f:
            f.write(html)

        file_size = len(html)
        print(f"✅ Report generated successfully")
        print(f"   File size: {file_size:,} bytes")
        print(f"   Output: {output_file}")

        # Validate key sections exist
        print("\n✅ Report validation:")
        checks = [
            ('Summary Dashboard', 'Summary Dashboard' in html),
            ('Bug Analysis Table', 'Bug Analysis Table' in html),
            ('E2E Breakdown', 'E2E Test Breakdown' in html),
            ('Recommendations', 'Recommendations' in html),
            ('Inline CSS', '<style>' in html and '</style>' in html),
            ('Inline JavaScript', '<script>' in html and '</script>' in html),
            ('SVG Charts', 'id="test-level-chart"' in html),
        ]

        for check_name, passed in checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}")

        all_passed = all(passed for _, passed in checks)

        if all_passed:
            print(f"\n🎉 All validations passed!")
            print(f"\n📂 Open report in browser:")
            print(f"   file://{output_file}")

        return all_passed

    except Exception as e:
        print(f"\n❌ Report generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n🧪 Historical Bug Coverage Skill - Component Tests\n")

    results = []

    # Test 1: Jira connection
    results.append(("Jira Connection", test_jira_connection()))

    # Test 2: Report generation
    results.append(("Report Generation", test_report_generation()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(passed for _, passed in results)

    if all_passed:
        print("\n🎉 All tests passed! Skill components are working correctly.")
        print("\n📝 Next steps:")
        print("   1. Review generated report: test-bug-coverage-report.html")
        print("   2. Skill is ready for integration with full implementation")
    else:
        print("\n⚠️  Some tests failed. Review errors above.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
