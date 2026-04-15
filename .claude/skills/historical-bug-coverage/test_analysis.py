#!/usr/bin/env python3
"""Deep test analysis - reads test files and extracts what they actually test.

Instead of just keyword matching, this module:
1. Reads matched test files
2. Extracts test cases, descriptions, and assertions
3. Determines what scenario the test validates
4. Compares to the bug's actual failure scenario
"""

import re
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass


@dataclass
class TestAssertion:
    """Represents what a test actually validates."""
    test_name: str
    description: str
    assertions: List[str]  # What's being checked (expect, assert, should)
    validates: Set[str]  # Inferred validations (error handling, permissions, state changes)
    confidence: str  # low/medium/high


def extract_test_cases(file_path: str, content: str, framework: str) -> List[TestAssertion]:
    """Extract test cases and their assertions from a test file.

    Returns list of TestAssertion objects with:
    - test_name: The test case name
    - description: What the test describes
    - assertions: Actual assertion statements
    - validates: What scenario it validates
    """
    test_cases = []

    if framework in ['jest', 'cypress', 'react-testing-library']:
        test_cases = _extract_js_test_cases(content)
    elif framework in ['pytest', 'unittest']:
        test_cases = _extract_python_test_cases(content)
    elif framework in ['go-testing', 'ginkgo']:
        test_cases = _extract_go_test_cases(content)

    return test_cases


def _extract_js_test_cases(content: str) -> List[TestAssertion]:
    """Extract Jest/Cypress test cases."""
    test_cases = []

    # Find all it() / test() blocks with their descriptions
    # Matches: it('should do something', () => { ... })
    test_blocks = re.finditer(
        r"(?:it|test)\s*\(\s*['\"`]([^'\"]+)['\"`]\s*,\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{(.*?)\n\s*\}",
        content,
        re.DOTALL | re.MULTILINE
    )

    for match in test_blocks:
        description = match.group(1)
        test_body = match.group(2)

        # Extract assertions
        assertions = _extract_js_assertions(test_body)

        # Infer what's being validated
        validates = _infer_validations(description, assertions, test_body)

        # Calculate confidence
        confidence = _calculate_confidence(description, assertions, validates)

        test_cases.append(TestAssertion(
            test_name=description,
            description=description,
            assertions=assertions,
            validates=validates,
            confidence=confidence
        ))

    return test_cases


def _extract_js_assertions(test_body: str) -> List[str]:
    """Extract assertion statements from JS test body."""
    assertions = []

    # expect() statements
    expect_patterns = [
        r'expect\([^)]+\)\.([^\(;]+)',  # expect(x).toBe...
        r'cy\.([^(]+)\([^)]*\)',  # cy.should, cy.contains, etc.
    ]

    for pattern in expect_patterns:
        matches = re.findall(pattern, test_body)
        assertions.extend(matches)

    return assertions


def _extract_python_test_cases(content: str) -> List[TestAssertion]:
    """Extract pytest/unittest test cases."""
    test_cases = []

    # Find test functions: def test_something():
    test_funcs = re.finditer(
        r'def (test_\w+)\([^)]*\):\s*"""?([^"]*?)"""?\s*(.*?)(?=\ndef |\nclass |\Z)',
        content,
        re.DOTALL
    )

    for match in test_funcs:
        test_name = match.group(1)
        docstring = match.group(2).strip()
        test_body = match.group(3)

        description = docstring if docstring else test_name.replace('_', ' ')

        # Extract assertions
        assertions = _extract_python_assertions(test_body)

        # Infer validations
        validates = _infer_validations(description, assertions, test_body)

        confidence = _calculate_confidence(description, assertions, validates)

        test_cases.append(TestAssertion(
            test_name=test_name,
            description=description,
            assertions=assertions,
            validates=validates,
            confidence=confidence
        ))

    return test_cases


def _extract_python_assertions(test_body: str) -> List[str]:
    """Extract assertion statements from Python test body."""
    assertions = []

    # assert statements
    assert_matches = re.findall(r'assert ([^#\n]+)', test_body)
    assertions.extend(assert_matches)

    # pytest.raises
    raises_matches = re.findall(r'pytest\.raises\((\w+)', test_body)
    assertions.extend([f"raises {e}" for e in raises_matches])

    return assertions


def _extract_go_test_cases(content: str) -> List[TestAssertion]:
    """Extract Go test cases."""
    test_cases = []

    # Find test functions: func TestSomething(t *testing.T)
    test_funcs = re.finditer(
        r'func (Test\w+)\(t \*testing\.T\)\s*\{(.*?)^\}',
        content,
        re.DOTALL | re.MULTILINE
    )

    for match in test_funcs:
        test_name = match.group(1)
        test_body = match.group(2)

        description = test_name.replace('Test', '').replace('_', ' ')

        # Extract assertions
        assertions = _extract_go_assertions(test_body)

        validates = _infer_validations(description, assertions, test_body)
        confidence = _calculate_confidence(description, assertions, validates)

        test_cases.append(TestAssertion(
            test_name=test_name,
            description=description,
            assertions=assertions,
            validates=validates,
            confidence=confidence
        ))

    return test_cases


def _extract_go_assertions(test_body: str) -> List[str]:
    """Extract assertion statements from Go test body."""
    assertions = []

    # t.Error, assert.Equal, etc.
    assert_patterns = [
        r't\.Error[f]?\(([^)]+)\)',
        r'assert\.(\w+)\(',
        r'require\.(\w+)\(',
    ]

    for pattern in assert_patterns:
        matches = re.findall(pattern, test_body)
        assertions.extend(matches)

    return assertions


def _infer_validations(description: str, assertions: List[str], test_body: str) -> Set[str]:
    """Infer what the test actually validates based on description and assertions."""
    validates = set()

    combined = f"{description} {' '.join(assertions)} {test_body}".lower()

    # Error handling validation
    if any(kw in combined for kw in ['error', 'fail', 'throw', 'reject', 'raises', 'exception']):
        validates.add('error_handling')

    # Permission/auth validation
    if any(kw in combined for kw in ['permission', 'auth', 'rbac', 'role', 'editor', 'viewer', 'admin']):
        validates.add('permissions')

    # State transition validation
    if any(kw in combined for kw in ['state', 'status', 'pending', 'running', 'complete', 'failed']):
        validates.add('state_transitions')

    # Data validation
    if any(kw in combined for kw in ['valid', 'invalid', 'format', 'parse', 'serialize']):
        validates.add('data_validation')

    # UI rendering validation
    if any(kw in combined for kw in ['render', 'display', 'shown', 'visible', 'hidden']):
        validates.add('ui_rendering')

    # API/Network validation
    if any(kw in combined for kw in ['api', 'request', 'response', 'fetch', 'call']):
        validates.add('api_calls')

    # Specific error message validation
    if re.search(r'["\']([^"\']*error[^"\']*)["\']', test_body, re.IGNORECASE):
        validates.add('specific_error_message')

    return validates


def _calculate_confidence(description: str, assertions: List[str], validates: Set[str]) -> str:
    """Calculate confidence that this test actually validates a scenario.

    low: Just basic existence checks
    medium: Has assertions and some validation
    high: Specific error messages, edge cases, multiple validations
    """
    score = 0

    # Has meaningful description
    if len(description) > 10 and not description.startswith('test_'):
        score += 20

    # Has assertions
    score += min(len(assertions) * 15, 30)

    # Validates multiple aspects
    score += len(validates) * 10

    # Specific validations (high value)
    if 'specific_error_message' in validates:
        score += 20
    if 'permissions' in validates:
        score += 15
    if 'error_handling' in validates:
        score += 15

    if score >= 70:
        return 'high'
    elif score >= 40:
        return 'medium'
    else:
        return 'low'


def match_test_to_bug_scenario(
    bug_summary: str,
    test_assertion: TestAssertion,
    bug_entities: List[str],
    bug_scenarios: List[str]
) -> Tuple[bool, float, str]:
    """Determine if a test actually validates the bug scenario.

    Returns:
        (is_match, confidence_score, reason)
    """
    description_lower = test_assertion.description.lower()
    assertions_str = ' '.join(test_assertion.assertions).lower()

    # Count entity matches
    entity_matches = sum(1 for e in bug_entities if e.lower() in description_lower)

    # Count scenario matches
    scenario_matches = sum(1 for s in bug_scenarios if s.lower() in description_lower or s.lower() in assertions_str)

    # Check validation types
    bug_lower = bug_summary.lower()
    required_validations = set()

    if 'error' in bug_lower or 'fail' in bug_lower:
        required_validations.add('error_handling')
    if 'permission' in bug_lower or 'editor' in bug_lower or 'rbac' in bug_lower:
        required_validations.add('permissions')
    if 'pending' in bug_lower or 'stuck' in bug_lower or 'state' in bug_lower:
        required_validations.add('state_transitions')

    validation_match = len(required_validations & test_assertion.validates)

    # Calculate match score
    score = 0.0
    reason_parts = []

    # Entities (30 points max)
    if entity_matches >= 3:
        score += 30
        reason_parts.append(f"{entity_matches} entities match")
    elif entity_matches >= 2:
        score += 20
        reason_parts.append(f"{entity_matches} entities match")
    elif entity_matches >= 1:
        score += 10
        reason_parts.append(f"{entity_matches} entity matches")

    # Scenarios (30 points max)
    if scenario_matches >= 2:
        score += 30
        reason_parts.append(f"{scenario_matches} scenarios match")
    elif scenario_matches >= 1:
        score += 15
        reason_parts.append(f"{scenario_matches} scenario matches")

    # Validations (40 points max)
    if validation_match == len(required_validations) and validation_match > 0:
        score += 40
        reason_parts.append(f"validates {', '.join(required_validations)}")
    elif validation_match > 0:
        score += 20
        reason_parts.append(f"partially validates {', '.join(test_assertion.validates & required_validations)}")

    # Confidence boost for high-confidence tests
    if test_assertion.confidence == 'high':
        score *= 1.1
        reason_parts.append("high-quality test")

    is_match = score >= 60  # Require 60% match
    reason = "; ".join(reason_parts) if reason_parts else "weak match"

    return (is_match, min(score, 100), reason)
