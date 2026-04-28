#!/usr/bin/env python3
"""Strict historical bug coverage analysis with repository discovery.

Correct workflow (per user feedback):
1. Repository Discovery - Learn what test frameworks/types exist
2. Architecture Context - Understand component boundaries
3. Jira Fetch - Get bugs based on JQL
4. Strict Coverage - Conservative matching (not keyword-based)
5. Deep Test Analysis - READ test files and understand assertions
6. Test Pyramid - Classify based on discovered capabilities
7. Interactive Feedback - User can provide corrections as rubric
8. Report - Generate comprehensive HTML output with rubric data
"""

import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Tuple, Set, Optional
from pathlib import Path

# Import deep test analysis module
try:
    from test_analysis import extract_test_cases, match_test_to_bug_scenario
    from coverage_rubric import CoverageMapping, export_coverage_mappings, generate_review_template
    DEEP_ANALYSIS_AVAILABLE = True
except ImportError:
    DEEP_ANALYSIS_AVAILABLE = False
    print("⚠️  Deep test analysis module not available - using keyword matching only")

# Add shared utilities to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

from jira_utils import require_env, search_jql
from report_generator import generate_bug_coverage_report
from repository_discovery import (
    discover_repository_tests,
    get_available_test_levels,
    identify_code_area,
    TestCapabilities,
    TestFile,
    TestPattern
)


def load_architecture_context(repo_path: str) -> Dict[str, any]:
    """Load architecture context from architecture-context directory if available."""
    arch_context_path = os.path.join(os.path.dirname(repo_path), "architecture-context")

    if not os.path.exists(arch_context_path):
        print(f"ℹ️  No architecture context found at {arch_context_path}")
        return {}

    print(f"\n📐 Loading architecture context from {arch_context_path}...")

    context = {
        'components': [],
        'services': [],
        'apis': []
    }

    # Look for GENERATED_ARCHITECTURE.md files
    for root, dirs, files in os.walk(arch_context_path):
        for file in files:
            if file == "GENERATED_ARCHITECTURE.md":
                context['components'].append(os.path.join(root, file))

    if context['components']:
        print(f"   Found {len(context['components'])} architecture documents")

    return context


def strict_coverage_search(
    bug_key: str,
    bug_summary: str,
    bug_labels: List[str],
    test_capabilities: TestCapabilities,
    test_files: List[TestFile]
) -> Tuple[str, Optional[str], float, str]:
    """Strict coverage matching with DEEP TEST ANALYSIS.

    Reads test files, extracts assertions, compares to bug scenario.

    Conservative approach:
    - COVERED: Test validates bug scenario with 80%+ confidence
    - PARTIALLY COVERED: Test partially covers scenario (60-80% confidence)
    - GAP: No relevant test found or confidence < 60%
    - NOT TESTABLE: Build/process/feature request

    Returns:
        Tuple of (coverage_status, test_file_path, confidence_score, details)
    """
    summary_lower = bug_summary.lower()
    labels_lower = [label.lower() for label in bug_labels]

    # Check for feature requests / recommendations (NOT bugs to be tested)
    feature_request_signals = [
        'follow up -', 'follow-up -', 'recommendation:', 'recommend:',
        'should we', 'consider adding', 'nice to have', 'enhancement:',
        'feature request:', 'fr:', 'rfe:'
    ]
    if any(signal in summary_lower for signal in feature_request_signals):
        return ("NOT TESTABLE", None, 0, "Feature request/recommendation, not a bug to test")

    # WARNING: Labels can be incorrect - validate rather than auto-trust
    # cypress_found_bug label should mean test exists, but verify
    has_cypress_found_bug = 'cypress_found_bug' in labels_lower
    # Don't auto-return COVERED - let entity matching validate it

    # Check for NOT TESTABLE signals
    # IMPORTANT: Don't include UI bugs here - they are testable!
    # Only include true infrastructure/build/deployment issues
    not_testable_signals = [
        'release pipeline', 'ci/cd pipeline', 'build pipeline',
        'documentation only', 'readme only', 'docs update',
        'visual styling only', 'ui polish', 'cosmetic',
        'migration script', 'one-off script', 'manual migration'
    ]

    # Build/deployment issues - recommend konflux-build-simulator
    # Only true infrastructure issues (OOM, crashes) - NOT deployment bugs
    build_deployment_signals = [
        'oomkilled', 'oom killed', 'out of memory',
        'pod crash', 'pod restart', 'crashloopbackoff',
        'resource limit exceeded', 'memory limit exceeded'
    ]

    # Check if it's truly NOT TESTABLE (exclude UI bugs which ARE testable)
    has_ui_context = any(word in summary_lower for word in [
        'in the ui', 'ui shows', 'ui display', 'entered in', 'shown in ui'
    ])

    if not has_ui_context and any(signal in summary_lower for signal in not_testable_signals):
        return ("NOT TESTABLE", None, 0, "Build/process/documentation issue, not automatable in code tests")

    if not has_ui_context and any(signal in summary_lower for signal in build_deployment_signals):
        return ("NOT TESTABLE", None, 0, "Build/deployment issue - recommend testing with konflux-build-simulator skill")

    # Extract key entities from bug summary
    # Look for specific component names, function names, API endpoints, etc.
    entities = extract_entities(bug_summary)

    if not entities:
        return ("GAP", None, 0, "No testable entities identified in bug summary")

    # Search for explicit test coverage with DEEP ANALYSIS
    # Read test files, extract assertions, compare to bug scenario
    scenario_keywords = extract_scenario_keywords(bug_summary)

    # Store matches with confidence scores
    matches_with_confidence = []  # (test_file, confidence, reason, matched_entities)

    for test_file in test_files:
        try:
            with open(test_file.path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                content_lower = content.lower()

            # Quick entity check first (avoid deep analysis on unrelated tests)
            test_filename_lower = os.path.basename(test_file.path).lower()
            matched_entities = []
            for e in entities:
                e_lower = e.lower()
                if e_lower in content_lower or e_lower in test_filename_lower:
                    matched_entities.append(e)

            if not matched_entities:
                continue  # No entities matched, skip

            # DEEP ANALYSIS: Read test file and extract assertions
            if DEEP_ANALYSIS_AVAILABLE:
                test_assertions = extract_test_cases(test_file.path, content, test_file.framework)

                # Match each test case to the bug scenario
                best_match_score = 0
                best_match_reason = ""

                for assertion in test_assertions:
                    is_match, score, reason = match_test_to_bug_scenario(
                        bug_summary,
                        assertion,
                        matched_entities,
                        scenario_keywords
                    )

                    if score > best_match_score:
                        best_match_score = score
                        best_match_reason = reason

                if best_match_score > 0:
                    matches_with_confidence.append((
                        test_file,
                        best_match_score,
                        best_match_reason,
                        matched_entities
                    ))
            else:
                # Fallback to keyword matching (original logic)
                has_negative_test = any(pattern in content_lower for pattern in [
                    'should not', 'fails', 'error', 'invalid', 'incorrect',
                    'missing', 'throws', 'rejects', 'exception', 'forbidden'
                ])
                has_scenario = any(kw in content_lower for kw in scenario_keywords)
                filename_match_count = sum(1 for e in matched_entities if e.lower() in test_filename_lower)

                # Calculate simple confidence score
                score = 0
                if len(matched_entities) >= 4 and filename_match_count >= 2:
                    score = 85
                elif len(matched_entities) >= 3 and has_negative_test and has_scenario:
                    score = 75
                elif len(matched_entities) >= 2 and has_scenario:
                    score = 50
                elif matched_entities:
                    score = 30

                if score > 0:
                    matches_with_confidence.append((
                        test_file,
                        score,
                        f"{len(matched_entities)} entities match",
                        matched_entities
                    ))

        except Exception as e:
            continue

    # Determine coverage status based on confidence scores
    # STRICT THRESHOLDS:
    # - COVERED: 80%+ confidence
    # - PARTIALLY COVERED: 60-80% confidence
    # - GAP: < 60% confidence

    if not matches_with_confidence:
        return ("GAP", None, 0, f"No tests found for: {', '.join(entities[:3])}")

    # Sort by confidence score (highest first)
    matches_with_confidence.sort(key=lambda m: m[1], reverse=True)

    best_match = matches_with_confidence[0]
    test_file, confidence, reason, matched_entities = best_match

    test_name = os.path.basename(test_file.path)
    test_path = test_file.path
    entities_str = ", ".join(matched_entities[:3])

    if confidence >= 80:
        return (
            "COVERED",
            test_path,
            confidence,
            f"Test: {test_name} validates {entities_str} | {reason} | Confidence: {confidence:.0f}%"
        )
    elif confidence >= 60:
        return (
            "PARTIALLY COVERED",
            test_path,
            confidence,
            f"Test: {test_name} partially covers {entities_str} | {reason} | Confidence: {confidence:.0f}%"
        )
    else:
        return (
            "GAP",
            test_path,
            confidence,
            f"Tests for entities exist in {test_name}, but confidence too low ({confidence:.0f}%)"
        )


def extract_entities(bug_summary: str) -> List[str]:
    """Extract testable entities from bug summary.

    Entities:
    - Component names: ProjectSelector, ModelRegistry, PipelineEditor
    - Function names: validateConfig, parseOCI, trimProtocol
    - API endpoints: /api/projects, /models/list
    - File names: config.yaml, deployment.spec
    - Technical terms: OCI protocol, RBAC, GPU allocation
    - Domain nouns: artifact, model, pipeline, notebook, sorting, filtering
    """
    entities = []

    # Extract camelCase/PascalCase identifiers (likely component/function names)
    camel_case = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b', bug_summary)
    entities.extend(camel_case)

    # Extract API paths
    api_paths = re.findall(r'/[\w/-]+', bug_summary)
    entities.extend(api_paths)

    # Extract technical terms (2-3 word phrases with capital letters or acronyms)
    technical = re.findall(r'\b(?:[A-Z]{2,}|[A-Z][a-z]+)\s+\w+\b', bug_summary)
    entities.extend(technical)

    # Extract file names
    files = re.findall(r'\b\w+\.\w{2,4}\b', bug_summary)
    entities.extend(files)

    # Extract quoted strings (often component/feature names)
    quoted = re.findall(r'"([^"]+)"', bug_summary)
    entities.extend(quoted)

    # NEW: Extract domain-specific nouns (common in bug descriptions)
    # These are key technical terms that appear in test file names
    domain_nouns = [
        'artifact', 'model', 'pipeline', 'notebook', 'workbench', 'project',
        'deployment', 'inferenceservice', 'servingruntime', 'experiment',
        'registry', 'catalog', 'metadata', 'version', 'endpoint', 'api',
        'sorting', 'filtering', 'validation', 'authentication', 'authorization',
        'rbac', 'permission', 'role', 'user', 'group', 'namespace',
        'connection', 'secret', 'configmap', 'volume', 'storage',
        'training', 'serving', 'inference', 'explainability', 'monitoring',
        'upload', 'download', 'import', 'export', 'migration', 'upgrade',
        'database', 'postgres', 'mysql', 'minio', 's3', 'oci',
        'property', 'custom', 'label', 'annotation', 'status', 'state',
        'dashboard', 'ui', 'frontend', 'backend', 'bff', 'controller',
        'operator', 'webhook', 'editor', 'yaml', 'json', 'form',
        'modal', 'dialog', 'dropdown', 'button', 'table', 'list',
        'page', 'route', 'component', 'service', 'pod', 'container'
    ]

    summary_lower = bug_summary.lower()
    for noun in domain_nouns:
        # Match whole words only
        if re.search(r'\b' + re.escape(noun) + r'\b', summary_lower):
            entities.append(noun)

    # Deduplicate and clean
    entities = list(set([e.strip() for e in entities if len(e.strip()) > 2]))

    return entities


def extract_scenario_keywords(bug_summary: str) -> List[str]:
    """Extract scenario-specific keywords from bug summary.

    Scenarios:
    - "trimmed" → ["trim", "trimmed", "trimming"]
    - "dropdown broken" → ["dropdown", "broken", "select"]
    - "fails on ARM" → ["fail", "arm", "aarch64"]
    """
    summary_lower = bug_summary.lower()
    keywords = set()

    # Action verbs and their variations
    action_patterns = {
        'trim': ['trim', 'trimmed', 'trimming'],
        'fail': ['fail', 'failed', 'fails', 'failure'],
        'break': ['break', 'broken', 'breaks'],
        'missing': ['missing', 'miss', 'missed'],
        'invalid': ['invalid', 'invalidate', 'invalidated'],
        'error': ['error', 'errors', 'errored'],
        'reject': ['reject', 'rejected', 'rejects'],
        'prevent': ['prevent', 'prevented', 'prevents'],
        'sort': ['sort', 'sorted', 'sorting', 'sorts'],
        'filter': ['filter', 'filtered', 'filtering', 'filters'],
        'search': ['search', 'searched', 'searching', 'searches'],
        'upload': ['upload', 'uploaded', 'uploading', 'uploads'],
        'download': ['download', 'downloaded', 'downloading', 'downloads'],
        'create': ['create', 'created', 'creating', 'creates', 'creation'],
        'delete': ['delete', 'deleted', 'deleting', 'deletes', 'deletion'],
        'update': ['update', 'updated', 'updating', 'updates'],
    }

    for base, variations in action_patterns.items():
        if base in summary_lower:
            keywords.update(variations)

    # Platform-specific
    platform_map = {
        'arm': ['arm', 'aarch64', 'arm64'],
        'power': ['power', 'ppc64le'],
        's390x': ['s390x', 's390'],
    }

    for platform, variations in platform_map.items():
        if platform in summary_lower:
            keywords.update(variations)

    return list(keywords)


def identify_bug_code_area(bug_summary: str, bug_labels: List[str]) -> str:
    """Identify what code area this bug affects.

    Be more specific to match actual testing patterns:
    - 'ui' for frontend component/display bugs (Cypress territory)
    - 'api' for backend API/endpoint bugs (Go/Ginkgo territory)
    - 'operator' for K8s operator bugs
    - 'data' for database/persistence bugs
    - 'utils' for utility/helper functions
    - 'general' for everything else
    """
    summary_lower = bug_summary.lower()
    labels_lower = [label.lower() for label in bug_labels]

    # Operator/Controller bugs (check FIRST - more specific than API)
    operator_signals = [
        'operator', 'controller', 'reconcile', 'webhook', 'crd',
        'custom resource', 'namespace', 'pod', 'deployment',
        'inferenceservice'
    ]
    if any(signal in summary_lower for signal in operator_signals):
        return 'operator'

    # API/Backend bugs (BFF, REST endpoints)
    api_signals = [
        'api', 'endpoint', 'rest', 'graphql', '/api/', 'get /', 'post /',
        'backend', 'server', 'handler', 'bff', '404', '500', 'http'
    ]
    if any(signal in summary_lower for signal in api_signals):
        return 'api'

    # Frontend UI component bugs (what users SEE)
    # These are Cypress mock test territory
    frontend_ui_signals = [
        'in the ui', 'on the ui', 'ui shows', 'ui displays', 'displayed in',
        'shown in', 'rendered', 'modal', 'dialog', 'dropdown', 'button',
        'form', 'table', 'component', 'page', 'tab', 'dashboard shows',
        'dashboard displays', 'catalog page', 'registry page', 'frontend'
    ]
    if any(signal in summary_lower for signal in frontend_ui_signals):
        return 'ui'

    # Database/persistence bugs
    data_signals = [
        'database', 'db', 'storage', 'persist', 'query', 'migration',
        'schema', 'sql', 'postgres', 'mysql'
    ]
    if any(signal in summary_lower for signal in data_signals):
        return 'data'

    # CLI bugs
    if 'cli' in summary_lower or 'command line' in summary_lower:
        return 'cli'

    # Utils/helpers (pure logic)
    util_signals = [
        'validation', 'validate', 'parse', 'parsing', 'format', 'formatting',
        'utility', 'helper', 'transform', 'convert', 'calculation',
        'sort', 'filter', 'sanitize', 'normalize'
    ]
    if any(signal in summary_lower for signal in util_signals):
        return 'utils'

    return 'general'


def determine_appropriate_test_type(bug_summary: str, bug_labels: List[str]) -> str:
    """Determine what test type is appropriate based on bug characteristics.

    Returns: 'unit', 'mock', 'integration', 'e2e', or 'contract'
    """
    summary_lower = bug_summary.lower()

    # E2E signals (needs real infrastructure)
    e2e_signals = [
        'rbac', 'auth', 'permission', 'deployment', 'upgrade',
        'arm', 'power', 's390x', 'fips', 'disconnected',
        'reconcile', 'crd', 'webhook', 'end-to-end'
    ]
    if any(signal in summary_lower for signal in e2e_signals):
        return 'e2e'

    # Integration signals (crosses boundaries but mockable)
    integration_signals = [
        'kubernetes', 'k8s', 'cluster', 'namespace', 'pod',
        'integration', 'cross-component'
    ]
    if any(signal in summary_lower for signal in integration_signals):
        return 'integration'

    # Contract signals (API contracts)
    contract_signals = [
        'api contract', 'contract', 'schema', 'openapi', 'swagger'
    ]
    if any(signal in summary_lower for signal in contract_signals):
        return 'contract'

    # Mock signals (component behavior with mocked deps)
    mock_signals = [
        'in the ui', 'ui shows', 'ui displays', 'displayed', 'shown',
        'modal', 'dialog', 'dropdown', 'button', 'form', 'table',
        'component', 'render', 'page', 'tab', 'dashboard'
    ]
    if any(signal in summary_lower for signal in mock_signals):
        return 'mock'

    # Unit signals (pure logic) - default
    return 'unit'


def recommend_test_from_patterns(
    bug_summary: str,
    bug_labels: List[str],
    patterns: List[TestPattern]
) -> Tuple[str, str, str]:
    """Recommend test type based on observed repo patterns.

    Strategy:
    1. Identify bug's code area (ui, api, operator, etc.)
    2. Determine appropriate test type (unit, mock, integration, e2e)
    3. Find pattern matching BOTH code area AND test type
    4. If no exact match, fall back to most common pattern for that code area

    Returns:
        Tuple of (test_level, framework, rationale)
    """
    if not patterns:
        return ("", "", "No patterns available")

    # Identify bug code area and appropriate test type
    code_area = identify_bug_code_area(bug_summary, bug_labels)
    desired_test_type = determine_appropriate_test_type(bug_summary, bug_labels)

    # Try to find pattern matching BOTH code area AND desired test type
    exact_matches = [
        p for p in patterns
        if p.code_area == code_area and p.test_type == desired_test_type
    ]

    if exact_matches:
        # Use the most common exact match
        best_pattern = exact_matches[0]

        # Map test_type to test_level
        level_map = {
            'unit': 'Unit',
            'mock': 'Mock',
            'integration': 'Integration',
            'e2e': 'E2E',
            'contract': 'Contract'
        }
        test_level = level_map.get(best_pattern.test_type, best_pattern.test_type.title())

        rationale = (
            f"Repo pattern for {code_area} {best_pattern.test_type} tests: "
            f"{best_pattern.framework} ({best_pattern.count} examples in {best_pattern.location_pattern})"
        )

        return (test_level, best_pattern.framework, rationale)

    # Fallback: find any pattern for this code area
    code_area_matches = [p for p in patterns if p.code_area == code_area]

    if not code_area_matches:
        # Try general patterns
        code_area_matches = [p for p in patterns if p.code_area == 'general']

    if code_area_matches:
        # Use most common pattern for this code area
        best_pattern = code_area_matches[0]

        level_map = {
            'unit': 'Unit',
            'mock': 'Mock',
            'integration': 'Integration',
            'e2e': 'E2E',
            'contract': 'Contract'
        }
        test_level = level_map.get(best_pattern.test_type, best_pattern.test_type.title())

        rationale = (
            f"Repo pattern for {code_area} bugs: {best_pattern.framework} {best_pattern.test_type} tests "
            f"({best_pattern.count} examples in {best_pattern.location_pattern}). "
            f"Note: Desired {desired_test_type} not available for this area."
        )

        return (test_level, best_pattern.framework, rationale)

    return ("", "", f"No pattern found for {code_area} bugs")


def classify_test_level_strict(
    bug_summary: str,
    bug_labels: List[str],
    test_capabilities: TestCapabilities
) -> Tuple[str, str]:
    """Classify test level based on bug characteristics AND available test infrastructure.

    Only recommends test levels that EXIST in the repository.
    Uses test pyramid: Unit > Mock > Integration > E2E

    Returns:
        Tuple of (test_level, rationale)
    """
    summary_lower = bug_summary.lower()
    labels_lower = [label.lower() for label in bug_labels]

    # Build/CI testing signals (infrastructure, resource, deployment issues)
    build_ci_signals = [
        'oomkilled', 'oom killed', 'out of memory', 'memory limit',
        'pod crash', 'pod restart', 'crashloopbackoff',
        'resource limit', 'cpu limit', 'memory exceeded',
        'image pull', 'container fail', 'container crash',
        'deployment fail', 'pod fails to start'
    ]
    if any(signal in summary_lower for signal in build_ci_signals):
        return ("Build/CI", "Build/deployment/resource issue, testable in CI pipeline")

    # N/A signals (truly not testable - visual, docs, release process)
    na_signals = [
        'release process', 'release workflow', 'release notes',
        'visual styling only', 'cosmetic only', 'ui polish',
        'documentation only', 'readme update', 'docs update',
        'manual process', 'manual migration', 'one-off script'
    ]
    if any(signal in summary_lower for signal in na_signals):
        return ("N/A", "Process/visual/documentation issue, not automatable")

    # E2E signals (requires real infrastructure or end-to-end user flows)
    e2e_signals = [
        'rbac', 'auth', 'permission', 'cluster', 'deployment', 'operator',
        'upgrade', 'arm', 'power', 's390x', 'fips', 'disconnected',
        'reconcile', 'crd', 'webhook', 'namespace',
        'create project', 'create new project', 'project creation',
        'create experiment', 'create pipeline', 'create run',
        'cross-component', 'integration between', 'end-to-end',
        'user flow', 'user journey', 'workflow',
        'fails to be ready', 'fails to start', 'not ready', 'startup fail',
        'full deployment', 'deployed to cluster', 'cluster deployment',
        'getting stuck', 'gets stuck', 'stuck in pending'
    ]
    if any(signal in summary_lower for signal in e2e_signals):
        if test_capabilities.has_e2e:
            return ("E2E", "Requires real infrastructure/auth/platform-specific testing")
        elif test_capabilities.has_integration:
            return ("Integration", "Infrastructure needed but E2E not available, use integration tests")
        else:
            return ("E2E", "Requires E2E testing (gap: no E2E tests exist yet)")

    # Unit signals (pure logic) - CHECK FIRST for logic bugs
    unit_signals = [
        'validation', 'validate', 'parse', 'parsing', 'format', 'formatting',
        'calculate', 'calculation', 'utility', 'helper', 'utils',
        'default value', 'config value', 'configuration',
        'data transformation', 'transform', 'convert', 'conversion',
        'trim', 'protocol', 'algorithm', 'computation',
        'sort', 'filter', 'map', 'reduce',
        'sanitize', 'normalize', 'encode', 'decode',
        'serialize', 'deserialize', 'json', 'yaml',
        'regex', 'pattern matching', 'string manipulation'
    ]
    if any(signal in summary_lower for signal in unit_signals):
        if test_capabilities.has_unit:
            return ("Unit", "Pure logic bug, testable in isolation")
        else:
            return ("Unit", "Should be unit test (gap: no unit tests exist yet)")

    # Contract signals (API contracts) - CHECK BEFORE Mock
    contract_signals = [
        'api contract', 'contract', 'schema', 'interface', 'bff',
        'api endpoint', 'rest api', 'graphql', 'openapi', 'swagger',
        'api response', 'api request', 'api call',
        'backend integration', 'service integration',
        'data model', 'entity', 'dto'
    ]
    if any(signal in summary_lower for signal in contract_signals):
        if test_capabilities.has_contract:
            return ("Contract", "API contract validation needed")
        elif test_capabilities.has_integration:
            return ("Integration", "Contract test ideal but not available, use integration")
        else:
            return ("Contract", "Should be contract test (gap: no contract tests exist yet)")

    # Mock/Component signals (component behavior with mocked deps)
    # BE MORE SPECIFIC - only clear UI component interaction bugs

    # UI context indicators - if bug mentions UI, it's likely Mock not Unit
    ui_context_signals = [
        'in the ui', 'on the ui', 'ui shows', 'ui displays', 'ui does not',
        'entered in the ui', 'displayed in ui', 'shown in ui',
        'state in the ui', 'rendered in ui', 'appears in ui',
        'visible in ui', 'hidden in ui',
        'component state', 'component does not', 'component fails to',
        'frontend', 'user interface', 'dashboard shows', 'dashboard displays'
    ]

    has_ui_context = any(signal in summary_lower for signal in ui_context_signals)

    mock_signals = [
        'component render', 'component display', 'component behavior',
        'dropdown select', 'dropdown option', 'dropdown menu',
        'form submit', 'form validation', 'form field',
        'button click', 'button state', 'button disabled',
        'modal open', 'modal close', 'modal dialog',
        'dialog box', 'dialog window',
        'user interaction', 'user click', 'user input', 'entered in',
        'checkbox select', 'radio button', 'toggle switch',
        'table row', 'table column', 'table cell',
        'list item', 'list view',
        'page load', 'page navigation', 'route',
        'state change', 'status change', 'does not change to',
        'completed state', 'finished state', 'running state',
        'yaml editor', 'code editor', 'text editor', 'json editor',
        'deployed as', 'displayed as', 'shown as', 'appears as',
        'editor shows', 'field shows', 'field displays'
    ]

    # Check for multi-word phrases first (more specific)
    if any(signal in summary_lower for signal in mock_signals) or has_ui_context:
        if test_capabilities.has_mock:
            return ("Mock", "UI component/state behavior, testable with mocked dependencies")
        elif test_capabilities.has_unit:
            return ("Unit", "Component bug but no mock tests, fallback to unit tests")
        else:
            return ("Mock", "Should be mock test (gap: no mock tests exist yet)")

    # Single-word component signals (less specific, use cautiously)
    single_word_ui = ['dropdown', 'modal', 'dialog', 'form', 'button', 'input field']
    if any(word in summary_lower for word in single_word_ui):
        # Check if it's NOT about logic/data
        if not any(logic in summary_lower for logic in ['validate', 'parse', 'transform', 'calculate']):
            if test_capabilities.has_mock:
                return ("Mock", "UI component bug, testable with mocked dependencies")

    # Default: analyze bug summary for best guess
    # If it mentions "error", "fail", "incorrect" without UI context → likely Unit
    if any(word in summary_lower for word in ['error', 'fail', 'incorrect', 'wrong', 'invalid']):
        # No clear UI component → likely logic bug
        if test_capabilities.has_unit:
            return ("Unit", "Error/validation bug, likely testable as unit test")

    # Final default based on available infrastructure
    if test_capabilities.has_unit:
        return ("Unit", "Unclear from summary, defaulting to Unit test (lowest test pyramid level)")
    elif test_capabilities.has_mock:
        return ("Mock", "Unclear from summary, defaulting to Mock test")
    else:
        return ("Unit", "Should be Unit test (gap: no tests exist yet)")


def categorize_bug(bug_summary: str, bug_labels: List[str]) -> List[str]:
    """Categorize bug into functional and non-functional types."""
    categories = []

    summary_lower = bug_summary.lower()
    labels_lower = [label.lower() for label in bug_labels]

    # Build-time/deployment issues
    build_signals = [
        'oomkilled', 'oom killed', 'out of memory', 'memory limit',
        'pod crash', 'pod fails', 'pod restart', 'crashloopbackoff',
        'image pull', 'container fail', 'resource limit', 'cpu limit',
        'build fail', 'build error', 'compilation error',
        'dockerfile', 'containerfile', 'deployment fail'
    ]
    if any(signal in summary_lower for signal in build_signals):
        categories.append('build-time')

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


def analyze_bugs_strict(
    bugs: List[Dict],
    test_capabilities: TestCapabilities,
    jira_server: str,
    repo_path: str = ""
) -> List[Dict]:
    """Analyze bugs with strict coverage matching.

    Args:
        bugs: List of bug dictionaries from Jira
        test_capabilities: Repository test capabilities
        jira_server: Jira server URL (e.g., https://mycompany.atlassian.net)
        repo_path: Repository root path (for relative test file paths)
    """
    analyzed_bugs = []
    total = len(bugs)

    print(f"\n🔍 Analyzing {total} bugs with STRICT coverage matching...")
    print(f"   (Conservative approach - requires evidence, not keywords)")

    for i, bug in enumerate(bugs, 1):
        if i % 10 == 0:
            print(f"   Progress: {i}/{total} ({int(i/total*100)}%)")

        fields = bug.get('fields', {})
        key = bug['key']
        summary = fields.get('summary', '')
        priority = fields.get('priority', {}).get('name', 'Unknown')
        status = fields.get('status', {}).get('name', 'Unknown')
        labels = fields.get('labels', [])

        # Strict coverage analysis with deep test analysis
        coverage_status, test_file_path, confidence_score, coverage_details = strict_coverage_search(
            key, summary, labels, test_capabilities, test_capabilities.test_files
        )

        # Try pattern-based recommendation first (uses repo's actual testing patterns)
        test_level, framework, test_rationale = recommend_test_from_patterns(
            summary, labels, test_capabilities.patterns
        )

        # Fall back to signal-based classification if no pattern found
        if not test_level:
            test_level, test_rationale = classify_test_level_strict(
                summary, labels, test_capabilities
            )
            framework = ""

        # Categorize
        categories = categorize_bug(summary, labels)

        # Build details with framework recommendation if available
        if framework:
            test_recommendation = f"{test_level} ({framework})"
        else:
            test_recommendation = test_level

        # Prepare test file display (relative path or basename)
        test_file_display = None
        if test_file_path:
            test_file_display = os.path.relpath(test_file_path, repo_path) if repo_path else os.path.basename(test_file_path)

        analyzed_bugs.append({
            'key': key,
            'priority': priority,
            'summary': summary,
            'status': status,
            'coverage': coverage_status,
            'testFile': test_file_display,  # NEW: Show which test covers this bug
            'confidence': round(confidence_score, 1),  # NEW: Confidence score 0-100
            'testLevel': test_level,
            'framework': framework,
            'categories': categories,
            'details': f"{coverage_details} | Recommend: {test_recommendation} - {test_rationale}",
            'jiraUrl': f"{jira_server}/browse/{key}"
        })

    print(f"✅ Strict analysis complete: {total} bugs processed")
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
    print("STRICT ANALYSIS STATISTICS")
    print("=" * 60)

    print(f"\n📊 Coverage Status:")
    for status in ['COVERED', 'PARTIALLY COVERED', 'GAP', 'NOT TESTABLE']:
        count = coverage_counts.get(status, 0)
        pct = int(count/total*100) if total > 0 else 0
        print(f"   {status:20} {count:3} ({pct:2}%)")

    print(f"\n🎯 Test Level Classification:")
    for level in ['Unit', 'Mock', 'Integration', 'E2E', 'Contract', 'N/A']:
        count = level_counts.get(level, 0)
        if count > 0:
            pct = int(count/total*100)
            print(f"   {level:20} {count:3} ({pct:2}%)")

    print(f"\n🏷️  Bug Categories:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        pct = int(count/total*100)
        print(f"   {cat:20} {count:3} ({pct:2}%)")


def main():
    """Run strict end-to-end analysis with repository discovery."""
    if len(sys.argv) < 3:
        print("Usage: strict_coverage_analysis.py <repo_path> <jql_query> [--external-tests <path>]")
        print("\nExample:")
        print('  strict_coverage_analysis.py /path/to/repo \\')
        print('    "project = MYPROJECT AND component = Dashboard AND priority in (Blocker, Critical)"')
        print('\n  # With external E2E tests:')
        print('  strict_coverage_analysis.py /path/to/model-registry \\')
        print('    "project = MYPROJECT AND component = Registry" \\')
        print('    --external-tests /path/to/opendatahub-tests/tests/model_registry')
        return 1

    repo_path = sys.argv[1]
    jql_query = sys.argv[2]

    # Parse optional --external-tests argument
    external_test_repos = []
    if len(sys.argv) > 3 and sys.argv[3] == '--external-tests':
        if len(sys.argv) > 4:
            external_test_repos = [sys.argv[4]]
        else:
            print("❌ --external-tests requires a path argument")
            return 1

    print("\n" + "=" * 60)
    print("STRICT Historical Bug Coverage Analysis")
    print("=" * 60)
    print("\nWorkflow:")
    print("  1. Repository Discovery")
    print("  2. Architecture Context")
    print("  3. Jira Fetch")
    print("  4. Strict Coverage Matching")
    print("  5. Test Pyramid Classification")
    print("  6. Report Generation")

    # Step 1: Validate environment
    print("\n" + "=" * 60)
    print("STEP 1: Environment Validation")
    print("=" * 60)

    server, user, token = require_env()
    if not all([server, user, token]):
        print("❌ Jira credentials not configured")
        print("   Set: JIRA_SERVER, JIRA_USER, JIRA_TOKEN")
        return 1

    if not os.path.exists(repo_path):
        print(f"❌ Repository not found: {repo_path}")
        return 1

    print(f"✅ Jira: {server}")
    print(f"✅ Repository: {repo_path}")

    # Step 2: Repository Discovery
    print("\n" + "=" * 60)
    print("STEP 2: Repository Test Discovery")
    print("=" * 60)

    test_capabilities = discover_repository_tests(repo_path, external_test_repos)

    available_levels = get_available_test_levels(test_capabilities)
    print(f"\n✅ Test infrastructure discovered")
    print(f"   Available test levels: {', '.join(available_levels)}")

    # Step 3: Architecture Context
    print("\n" + "=" * 60)
    print("STEP 3: Architecture Context Loading")
    print("=" * 60)

    arch_context = load_architecture_context(repo_path)

    # Step 4: Fetch bugs from Jira
    print("\n" + "=" * 60)
    print("STEP 4: Jira Bug Fetch")
    print("=" * 60)
    print(f"\n📋 JQL: {jql_query}")

    try:
        bugs = search_jql(
            server, user, token,
            jql=jql_query,
            fields=['key', 'summary', 'status', 'priority', 'labels', 'created'],
            max_results=100
        )
        print(f"\n✅ Fetched {len(bugs)} bugs")
    except Exception as e:
        print(f"❌ Failed to fetch bugs: {e}")
        return 1

    if not bugs:
        print("⚠️  No bugs returned from JQL query")
        return 1

    # Step 5: Strict coverage analysis
    print("\n" + "=" * 60)
    print("STEP 5: Strict Coverage Analysis")
    print("=" * 60)

    analyzed_bugs = analyze_bugs_strict(bugs, test_capabilities, server, repo_path)

    # Step 6: Print statistics
    print_statistics(analyzed_bugs)

    # Step 7: Generate HTML report
    print("\n" + "=" * 60)
    print("STEP 6: HTML Report Generation")
    print("=" * 60)

    repo_name = os.path.basename(repo_path)

    # Try to detect repo URL from git remote
    repo_url = ""
    try:
        import subprocess
        result = subprocess.run(
            ['git', '-C', repo_path, 'config', '--get', 'remote.origin.url'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            repo_url = result.stdout.strip()
            # Convert SSH to HTTPS if needed
            if repo_url.startswith('git@'):
                repo_url = repo_url.replace(':', '/').replace('git@', 'https://')
            if repo_url.endswith('.git'):
                repo_url = repo_url[:-4]
    except:
        pass

    if not repo_url:
        repo_url = f"<repository-url>/{repo_name}"

    metadata = {
        "repoName": repo_name,
        "repoUrl": repo_url,
        "timestamp": datetime.now().isoformat() + "Z",
        "jql": jql_query,
        "totalCount": len(analyzed_bugs),
        "analysisMode": "STRICT (Evidence-based, Conservative)",
        "testCapabilities": {
            "unit": test_capabilities.has_unit,
            "mock": test_capabilities.has_mock,
            "e2e": test_capabilities.has_e2e,
            "contract": test_capabilities.has_contract,
            "integration": test_capabilities.has_integration
        }
    }

    try:
        html = generate_bug_coverage_report(analyzed_bugs, metadata)

        # Use current directory for output
        output_file = os.path.join(os.getcwd(), f"{repo_name}-bug-coverage.html")
        with open(output_file, 'w') as f:
            f.write(html)

        print(f"\n✅ Report generated: {output_file}")
        print(f"   File size: {len(html):,} bytes")
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
