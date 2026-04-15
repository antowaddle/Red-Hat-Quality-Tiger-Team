#!/usr/bin/env python3
"""Repository test framework discovery.

Discovers test frameworks, types, and capabilities BEFORE analyzing bugs.
This ensures we only classify bugs for test types that actually exist in the repo.
"""

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Set
from pathlib import Path


@dataclass
class TestFile:
    """Represents a discovered test file."""
    path: str
    framework: str  # jest, cypress, go-testing, pytest, etc.
    test_type: str  # unit, mock, e2e, contract, integration
    patterns: Set[str]  # What this test file tests (classes, functions, components)


@dataclass
class TestPattern:
    """Represents a testing pattern observed in the repo."""
    code_area: str  # ui, api, operator, utils, etc.
    framework: str  # cypress, jest, ginkgo, go-testing, etc.
    test_type: str  # unit, mock, integration, e2e
    location_pattern: str  # cypress/tests/mocked/, __tests__/, etc.
    example_files: List[str]  # Example test files following this pattern
    count: int  # Number of tests following this pattern


@dataclass
class TestCapabilities:
    """Repository's test capabilities."""
    frameworks: Dict[str, int]  # framework -> count
    test_types: Dict[str, int]  # test_type -> count
    test_files: List[TestFile]
    patterns: List[TestPattern]  # Observed testing patterns
    has_unit: bool
    has_mock: bool
    has_e2e: bool
    has_contract: bool
    has_integration: bool


def discover_test_framework(file_path: str, content: str) -> str:
    """Identify the test framework used in a file."""

    # BDD frameworks
    if file_path.endswith('.feature'):
        return "cucumber/behave"
    elif file_path.endswith('.robot'):
        return "robot-framework"

    # TypeScript/JavaScript frameworks
    if "from '@testing-library/react'" in content or "import { render" in content:
        return "react-testing-library"
    elif "describe(" in content and ("jest" in content.lower() or ".spec.ts" in file_path or "__tests__" in file_path):
        return "jest"
    elif "cy." in content or ".cy.ts" in file_path or ".cy.js" in file_path:
        return "cypress"
    elif file_path.endswith(('.ts', '.tsx', '.js', '.jsx')) and "describe(" in content:
        return "jest"  # Generic JS/TS test with describe blocks

    # Go testing
    elif file_path.endswith("_test.go") or (file_path.endswith('.go') and 'func Test' in content):
        if "ginkgo" in content.lower():
            return "ginkgo"
        else:
            return "go-testing"

    # Python testing - expanded detection
    elif file_path.endswith('.py'):
        # Check for pytest (look in first 50 lines, not just beginning)
        lines = content.split('\n')[:50]
        content_start = '\n'.join(lines)

        if "import pytest" in content_start or "from pytest" in content_start:
            return "pytest"
        elif "@pytest." in content_start or "pytest.mark" in content_start:
            return "pytest"  # Pytest decorators present
        elif "def test_" in content:
            return "pytest"  # pytest-style test functions (pytest is default Python test runner)
        elif "import unittest" in content_start:
            return "unittest"
        elif "class Test" in content and "unittest.TestCase" in content:
            return "unittest"
        # If none of the above but has test/assert patterns, likely pytest
        elif any(p in content for p in ['assert ', 'pytest.', '@pytest']):
            return "pytest"

    return "unknown"


def classify_test_type(file_path: str, content: str, repo_root: str) -> str:
    """Classify test as unit, mock, e2e, contract, or integration."""

    rel_path = os.path.relpath(file_path, repo_root).lower()

    # External E2E test repos (like opendatahub-tests) - check FIRST
    # These contain system-level tests that need real infrastructure
    e2e_repo_markers = [
        'opendatahub-tests/', 'odh-tests/', 'e2e-tests/',
        'rbac/', 'upgrade/', 'security/', 'negative_tests/',
        'cluster_health/', 'model_serving/', 'workbenches/'
    ]
    if any(marker in rel_path for marker in e2e_repo_markers):
        # Except for pure unit utility tests
        if 'utils.py' in file_path or 'conftest.py' in file_path:
            return "unit"  # Helper files, not actual tests
        return "e2e"

    # E2E tests - explicit directories or Cypress tests
    if any(marker in rel_path for marker in ['e2e/', 'tests/e2e/', 'cypress/tests/e2e/']):
        return "e2e"

    # Contract tests - explicit directories
    if 'contract' in rel_path or 'contract-tests' in rel_path:
        return "contract"

    # Integration tests - explicit directories
    if 'integration' in rel_path or 'tests/integration/' in rel_path:
        return "integration"

    # Cypress mock/component tests
    if '.cy.ts' in file_path or '.cy.js' in file_path:
        if 'mocked' in rel_path or 'mock' in rel_path:
            return "mock"
        elif 'component' in rel_path:
            return "mock"  # Cypress component tests are mock-level
        else:
            return "e2e"  # Default Cypress to E2E unless explicitly mock

    # Unit tests - small, focused tests
    # Heuristics:
    # - In __tests__ adjacent to source
    # - Tests for utils, helpers, hooks
    # - No API mocking or component rendering
    if '__tests__' in rel_path:
        # Check content for unit test signals
        if 'cy.intercept' not in content and 'render(' not in content:
            # No API mocking, no rendering -> likely unit
            return "unit"

    # Mock/Component tests - render components with mocked APIs
    if 'render(' in content or 'cy.intercept' in content:
        return "mock"

    # Default based on framework
    if '.spec.ts' in file_path or '.test.ts' in file_path:
        if 'render(' in content:
            return "mock"
        else:
            return "unit"

    return "unit"  # Conservative default


def extract_test_patterns(file_path: str, content: str) -> Set[str]:
    """Extract what this test file is testing (component names, function names, etc.)."""

    patterns = set()

    # Extract from describe blocks
    describe_matches = re.findall(r'describe\([\'"`]([^\'"]+)[\'"`]', content)
    patterns.update(describe_matches)

    # Extract from file name
    base_name = os.path.basename(file_path)
    # Remove test suffixes
    test_name = re.sub(r'\.(spec|test|cy)\.(ts|tsx|js|jsx|go|py)$', '', base_name)
    test_name = re.sub(r'_(test|spec)$', '', test_name)
    patterns.add(test_name)

    # Extract imports (what's being tested)
    import_matches = re.findall(r'from [\'"]\.\.?/([\w/]+)[\'"]', content)
    for imp in import_matches:
        # Get the last part (likely the file being tested)
        parts = imp.split('/')
        if parts:
            patterns.add(parts[-1])

    return patterns


def identify_code_area(file_path: str, repo_root: str) -> str:
    """Identify what area of code this test covers."""
    rel_path = os.path.relpath(file_path, repo_root).lower()

    # UI/Frontend tests
    if any(marker in rel_path for marker in ['frontend/', 'ui/', 'client/', 'web/', 'components/', 'pages/']):
        return 'ui'

    # API/Backend tests
    if any(marker in rel_path for marker in ['api/', 'backend/', 'server/', 'handlers/', 'controllers/']):
        return 'api'

    # Operator/Controller tests
    if any(marker in rel_path for marker in ['operator/', 'controller/', 'reconciler/', 'webhook/']):
        return 'operator'

    # CLI tests
    if 'cli/' in rel_path or 'cmd/' in rel_path:
        return 'cli'

    # Utils/Helpers
    if any(marker in rel_path for marker in ['util/', 'helper/', 'common/', 'shared/']):
        return 'utils'

    # Model/Data layer
    if any(marker in rel_path for marker in ['model/', 'schema/', 'database/', 'db/']):
        return 'data'

    return 'general'


def build_test_patterns(test_files: List[TestFile], repo_root: str) -> List[TestPattern]:
    """Analyze test files to identify testing patterns."""
    # Group tests by (code_area, framework, test_type, location_pattern)
    pattern_map = {}

    for test_file in test_files:
        code_area = identify_code_area(test_file.path, repo_root)

        # Extract location pattern (directory structure)
        rel_path = os.path.relpath(test_file.path, repo_root)
        # Get directory path up to the test file
        dir_path = os.path.dirname(rel_path)
        # Simplify to general pattern
        location_pattern = dir_path.replace(os.sep, '/')

        # Create pattern key
        key = (code_area, test_file.framework, test_file.test_type, location_pattern)

        if key not in pattern_map:
            pattern_map[key] = {
                'examples': [],
                'count': 0
            }

        pattern_map[key]['examples'].append(test_file.path)
        pattern_map[key]['count'] += 1

    # Convert to TestPattern objects
    patterns = []
    for (code_area, framework, test_type, location_pattern), data in pattern_map.items():
        # Only include patterns with at least 2 examples (established pattern)
        if data['count'] >= 2:
            patterns.append(TestPattern(
                code_area=code_area,
                framework=framework,
                test_type=test_type,
                location_pattern=location_pattern,
                example_files=data['examples'][:3],  # Keep first 3 examples
                count=data['count']
            ))

    # Sort by count (most common patterns first)
    patterns.sort(key=lambda p: p.count, reverse=True)

    return patterns


def discover_repository_tests(repo_path: str, external_test_repos: List[str] = None) -> TestCapabilities:
    """Discover all test files and categorize them.

    Args:
        repo_path: Primary repository path to scan
        external_test_repos: Optional list of external test repository paths to include
                            (e.g., opendatahub-tests for E2E tests)

    Returns:
        TestCapabilities with discovered tests from all repositories
    """

    print("=" * 60)
    print("STEP 1: Repository Test Discovery")
    print("=" * 60)

    test_files = []
    frameworks = {}
    test_types = {}

    # Scan primary repository
    print(f"\n📁 Scanning primary repository: {repo_path}")

    for root, dirs, files in os.walk(repo_path):
        # Skip common non-test directories
        dirs[:] = [d for d in dirs if d not in [
            'node_modules', '.git', 'dist', 'build', '.next', 'coverage',
            '__pycache__', '.pytest_cache', 'vendor'
        ]]

        for file in files:
            file_path = os.path.join(root, file)

            # Identify test files by multiple signals
            # 1. Standard naming patterns
            is_test_by_name = (
                file.endswith(('.spec.ts', '.spec.tsx', '.test.ts', '.test.tsx')) or
                file.endswith(('.cy.ts', '.cy.js')) or
                file.endswith('_test.go') or
                file.endswith('_test.py') or
                os.path.basename(file_path).startswith('test_') and file.endswith('.py') or
                file.startswith('test') and file.endswith('.py')  # unittest: test*.py
            )

            # 2. Directory-based detection (files in test directories)
            rel_path = os.path.relpath(file_path, repo_path)
            is_in_test_dir = any(part in ['tests', '__tests__', 'test', 'testing', 'e2e', 'integration']
                                 for part in Path(rel_path).parts)

            # Only check content if in test directory and has code extension
            has_code_ext = file.endswith(('.py', '.ts', '.tsx', '.js', '.jsx', '.go'))

            is_test_by_directory = (
                is_in_test_dir and
                has_code_ext and
                not file.endswith(('conftest.py', '__init__.py', 'setup.py'))  # Exclude helper files
            )

            # 3. BDD/Framework-specific files
            is_bdd_test = file.endswith(('.feature', '.robot'))

            is_test = is_test_by_name or is_test_by_directory or is_bdd_test

            if not is_test:
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Discover framework
                framework = discover_test_framework(file_path, content)

                # If detected by directory only, validate it's actually a test file
                if is_test_by_directory and not is_test_by_name:
                    # Content-based validation: must have test-related code
                    has_test_code = any(pattern in content for pattern in [
                        'def test_', 'class Test', 'describe(', 'it(', 'test(',
                        'assert', 'expect(', '@Test', 'func Test', 'pytest.mark'
                    ])
                    if not has_test_code and framework == 'unknown':
                        continue  # Not actually a test file, skip it

                frameworks[framework] = frameworks.get(framework, 0) + 1

                # Classify test type
                test_type = classify_test_type(file_path, content, repo_path)
                test_types[test_type] = test_types.get(test_type, 0) + 1

                # Extract patterns
                patterns = extract_test_patterns(file_path, content)

                test_files.append(TestFile(
                    path=file_path,
                    framework=framework,
                    test_type=test_type,
                    patterns=patterns
                ))

            except Exception as e:
                print(f"⚠️  Error processing {file_path}: {e}")
                continue

    # Scan external test repositories if provided
    if external_test_repos:
        for ext_repo in external_test_repos:
            if not os.path.exists(ext_repo):
                print(f"\n⚠️  External test repo not found: {ext_repo}")
                continue

            print(f"\n📁 Scanning external test repository: {ext_repo}")

            for root, dirs, files in os.walk(ext_repo):
                # Skip common non-test directories
                dirs[:] = [d for d in dirs if d not in [
                    'node_modules', '.git', 'dist', 'build', '.next', 'coverage',
                    '__pycache__', '.pytest_cache', 'vendor', '.venv', 'venv'
                ]]

                for file in files:
                    file_path = os.path.join(root, file)

                    # Identify test files
                    is_test = (
                        file.endswith(('.spec.ts', '.spec.tsx', '.test.ts', '.test.tsx')) or
                        file.endswith(('.cy.ts', '.cy.js')) or
                        file.endswith('_test.go') or
                        file.endswith('_test.py') or
                        file.startswith('test_') and file.endswith('.py')
                    )

                    if not is_test:
                        continue

                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()

                        # Discover framework
                        framework = discover_test_framework(file_path, content)
                        frameworks[framework] = frameworks.get(framework, 0) + 1

                        # External repos typically contain E2E tests
                        # But still classify to be sure
                        test_type = classify_test_type(file_path, content, ext_repo)
                        test_types[test_type] = test_types.get(test_type, 0) + 1

                        # Extract patterns
                        patterns = extract_test_patterns(file_path, content)

                        test_files.append(TestFile(
                            path=file_path,
                            framework=framework,
                            test_type=test_type,
                            patterns=patterns
                        ))

                    except Exception as e:
                        print(f"⚠️  Error processing {file_path}: {e}")
                        continue

            print(f"   Found {sum(1 for f in test_files if ext_repo in f.path)} tests in {os.path.basename(ext_repo)}")

    # Build test patterns
    patterns = build_test_patterns(test_files, repo_path)

    # Build capabilities object
    capabilities = TestCapabilities(
        frameworks=frameworks,
        test_types=test_types,
        test_files=test_files,
        patterns=patterns,
        has_unit=test_types.get('unit', 0) > 0,
        has_mock=test_types.get('mock', 0) > 0,
        has_e2e=test_types.get('e2e', 0) > 0,
        has_contract=test_types.get('contract', 0) > 0,
        has_integration=test_types.get('integration', 0) > 0
    )

    # Print summary
    print(f"\n✅ Discovered {len(test_files)} test files")

    print(f"\n📊 Test Frameworks Found:")
    for framework, count in sorted(frameworks.items(), key=lambda x: -x[1]):
        print(f"   {framework:30} {count:4} files")

    print(f"\n🎯 Test Types Found:")
    for test_type, count in sorted(test_types.items(), key=lambda x: -x[1]):
        print(f"   {test_type:30} {count:4} files")

    print(f"\n🔍 Test Capabilities:")
    print(f"   Unit Tests:         {'✅ Available' if capabilities.has_unit else '❌ Not found'}")
    print(f"   Mock Tests:         {'✅ Available' if capabilities.has_mock else '❌ Not found'}")
    print(f"   E2E Tests:          {'✅ Available' if capabilities.has_e2e else '❌ Not found'}")
    print(f"   Contract Tests:     {'✅ Available' if capabilities.has_contract else '❌ Not found'}")
    print(f"   Integration Tests:  {'✅ Available' if capabilities.has_integration else '❌ Not found'}")

    # Print discovered patterns
    if patterns:
        print(f"\n🎯 Testing Patterns Discovered ({len(patterns)} patterns):")
        # Show top 10 most common patterns
        for pattern in patterns[:10]:
            print(f"   {pattern.code_area:12} → {pattern.framework:20} ({pattern.test_type:12}) - {pattern.count:3} tests")
            print(f"      📁 {pattern.location_pattern}")

    return capabilities


def get_available_test_levels(capabilities: TestCapabilities) -> List[str]:
    """Get list of test levels available in this repo (in pyramid order)."""
    available = []

    if capabilities.has_unit:
        available.append("Unit")
    if capabilities.has_mock or capabilities.has_integration:
        available.append("Mock")
    if capabilities.has_e2e:
        available.append("E2E")
    if capabilities.has_contract:
        available.append("Contract")

    return available


def recommend_missing_test_types(capabilities: TestCapabilities) -> List[str]:
    """Recommend test types that should be added to the repo."""
    recommendations = []

    if not capabilities.has_unit:
        recommendations.append("⚠️  No unit tests found - Consider adding unit tests for utility functions and business logic")

    if not capabilities.has_mock:
        recommendations.append("⚠️  No mock/component tests found - Consider adding component tests with mocked APIs")

    if not capabilities.has_e2e:
        recommendations.append("⚠️  No E2E tests found - Consider adding end-to-end tests for critical user journeys")

    if not capabilities.has_contract:
        recommendations.append("ℹ️  No contract tests found - Consider adding contract tests if you have BFF/API services")

    return recommendations


if __name__ == "__main__":
    # Test mode - provide repo path as command line argument
    import sys
    if len(sys.argv) < 2:
        print("Usage: repository_discovery.py <repo_path>")
        print("Example: repository_discovery.py ./my-repo")
        sys.exit(1)

    repo_path = sys.argv[1]
    capabilities = discover_repository_tests(repo_path)

    print(f"\n{'=' * 60}")
    print("Available Test Levels (Test Pyramid Order)")
    print("=" * 60)
    levels = get_available_test_levels(capabilities)
    for level in levels:
        print(f"   ✅ {level}")

    print(f"\n{'=' * 60}")
    print("Recommendations")
    print("=" * 60)
    recommendations = recommend_missing_test_types(capabilities)
    if recommendations:
        for rec in recommendations:
            print(f"   {rec}")
    else:
        print("   ✅ All test types present - well-rounded test suite!")
