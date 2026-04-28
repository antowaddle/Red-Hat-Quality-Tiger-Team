#!/usr/bin/env python3
"""Coverage analysis rubric and feedback system.

Allows teams to:
1. Review bug-test mappings
2. Provide feedback (correct/incorrect/partial)
3. Learn from corrections to improve matching
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class CoverageMapping:
    """Represents a bug-to-test mapping with confidence score."""
    bug_key: str
    bug_summary: str
    coverage_status: str  # COVERED, PARTIALLY COVERED, GAP, NOT TESTABLE
    matched_test_file: Optional[str]
    match_confidence: float  # 0-100
    match_reason: str
    entities_matched: List[str]
    scenarios_matched: List[str]
    validations_found: List[str]
    test_assertions: List[str]

    # Feedback fields
    human_validated: bool = False
    validation_status: Optional[str] = None  # correct/incorrect/partial
    validation_notes: Optional[str] = None
    validated_by: Optional[str] = None
    validated_at: Optional[str] = None


@dataclass
class FeedbackRubric:
    """Rubric for evaluating coverage analysis quality."""

    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD = 80  # 80%+ match score
    MEDIUM_CONFIDENCE_THRESHOLD = 60  # 60-80% match score
    LOW_CONFIDENCE_THRESHOLD = 40  # 40-60% match score

    # Coverage criteria
    COVERED_CRITERIA = """
    A bug should be marked COVERED if:
    1. Test file explicitly tests the failure scenario described in the bug
    2. Test assertions validate the specific error/behavior mentioned in the bug
    3. Test covers the same entities (components, functions, endpoints) as the bug
    4. Test validates the same conditions (permissions, state, inputs) as the bug
    5. Match confidence >= 80%

    Example:
    - Bug: "User with editor role gets 'Permission denied' error when deleting project"
    - Test: it('should show permission error for editor trying to delete project')
          expect(deleteProject).toThrow('Permission denied')
    - Status: ✅ COVERED (validates exact scenario + error message)
    """

    PARTIALLY_COVERED_CRITERIA = """
    A bug should be marked PARTIALLY COVERED if:
    1. Test covers some but not all aspects of the bug
    2. Test validates related entities but not the exact failure scenario
    3. Test checks error handling but not the specific error mentioned
    4. Match confidence 60-80%

    Example:
    - Bug: "User with editor role gets 'Permission denied' error when deleting project"
    - Test: it('should handle errors when deleting project')
          expect(deleteProject).toThrow()
    - Status: ⚠️ PARTIALLY COVERED (checks error but not permission-specific)
    """

    GAP_CRITERIA = """
    A bug should be marked GAP if:
    1. No test validates the specific failure scenario
    2. Tests exist for related entities but don't test this specific bug
    3. Match confidence < 60%

    Example:
    - Bug: "User with editor role gets 'Permission denied' error when deleting project"
    - Tests found: test_project_creation.py, test_project_list.py
    - Status: ❌ GAP (no deletion or permission tests found)
    """

    NOT_TESTABLE_CRITERIA = """
    A bug should be marked NOT TESTABLE if:
    1. Feature request / recommendation (not a bug)
    2. Documentation only
    3. Build/deployment infrastructure issue (suggest konflux-build-simulator)
    4. Visual styling only
    5. Manual process / one-off migration
    """


def export_coverage_mappings(
    mappings: List[CoverageMapping],
    output_file: str,
    include_rubric: bool = True
) -> None:
    """Export coverage mappings to JSON for team review."""

    data = {
        "export_date": datetime.now().isoformat(),
        "total_bugs": len(mappings),
        "rubric": asdict(FeedbackRubric()) if include_rubric else None,
        "mappings": [asdict(m) for m in mappings]
    }

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n✅ Exported {len(mappings)} coverage mappings to: {output_file}")
    print(f"\nTeams can review and provide feedback using this JSON file.")
    print(f"Update 'validation_status' field to: correct | incorrect | partial")


def import_validated_mappings(feedback_file: str) -> List[CoverageMapping]:
    """Import team feedback from JSON file."""

    with open(feedback_file, 'r') as f:
        data = json.load(f)

    mappings = []
    for m_dict in data.get('mappings', []):
        mappings.append(CoverageMapping(**m_dict))

    return mappings


def learn_from_feedback(
    validated_mappings: List[CoverageMapping],
    learning_output: str
) -> Dict[str, any]:
    """Analyze validated feedback to improve future matching.

    Learns:
    - Which entity combinations reliably indicate coverage
    - Which scenario keywords are most predictive
    - Confidence threshold adjustments
    - Common false positives/negatives
    """

    learning_data = {
        "analyzed_at": datetime.now().isoformat(),
        "total_validated": len(validated_mappings),
        "accuracy_metrics": {},
        "improvements": []
    }

    # Separate by validation status
    correct = [m for m in validated_mappings if m.validation_status == 'correct']
    incorrect = [m for m in validated_mappings if m.validation_status == 'incorrect']
    partial = [m for m in validated_mappings if m.validation_status == 'partial']

    # Calculate accuracy
    if validated_mappings:
        learning_data["accuracy_metrics"] = {
            "correct_predictions": len(correct),
            "incorrect_predictions": len(incorrect),
            "partial_predictions": len(partial),
            "accuracy_rate": len(correct) / len(validated_mappings) * 100
        }

    # Analyze false positives (marked COVERED but actually GAP)
    false_positives = [
        m for m in incorrect
        if m.coverage_status == 'COVERED' and 'should be GAP' in (m.validation_notes or '')
    ]

    if false_positives:
        avg_confidence = sum(m.match_confidence for m in false_positives) / len(false_positives)
        learning_data["improvements"].append({
            "issue": "False positives (incorrect COVERED status)",
            "count": len(false_positives),
            "avg_confidence": avg_confidence,
            "recommendation": f"Increase confidence threshold from 60 to {int(avg_confidence + 10)}"
        })

    # Analyze false negatives (marked GAP but actually COVERED)
    false_negatives = [
        m for m in incorrect
        if m.coverage_status == 'GAP' and 'should be COVERED' in (m.validation_notes or '')
    ]

    if false_negatives:
        common_entities = {}
        for m in false_negatives:
            for entity in m.entities_matched:
                common_entities[entity] = common_entities.get(entity, 0) + 1

        learning_data["improvements"].append({
            "issue": "False negatives (missed COVERED tests)",
            "count": len(false_negatives),
            "missing_entities": dict(sorted(common_entities.items(), key=lambda x: -x[1])[:5]),
            "recommendation": "Add these entities to domain_nouns list"
        })

    # Save learning data
    with open(learning_output, 'w') as f:
        json.dump(learning_data, f, indent=2)

    print(f"\n✅ Learning data saved to: {learning_output}")
    print(f"\n📊 Accuracy Metrics:")
    print(f"   Correct: {len(correct)}/{len(validated_mappings)} ({len(correct)/len(validated_mappings)*100:.1f}%)")
    print(f"   Incorrect: {len(incorrect)}/{len(validated_mappings)}")
    print(f"   Partial: {len(partial)}/{len(validated_mappings)}")

    if learning_data["improvements"]:
        print(f"\n💡 Suggested Improvements:")
        for imp in learning_data["improvements"]:
            print(f"   - {imp['issue']}: {imp['recommendation']}")

    return learning_data


def generate_review_template(mappings: List[CoverageMapping], output_file: str) -> None:
    """Generate a review template for teams to fill out."""

    review_data = {
        "instructions": """
        Review each bug-test mapping and update the validation fields:

        validation_status options:
          - "correct"   : The mapping is accurate (test does cover this bug)
          - "incorrect" : The mapping is wrong (test doesn't cover this bug)
          - "partial"   : The mapping is partially correct (test covers some aspects)

        validation_notes:
          - Add your reasoning for the validation status
          - Suggest improvements if needed

        validated_by:
          - Your name or team identifier
        """,
        "rubric_summary": {
            "COVERED": "Test explicitly validates the failure scenario (confidence >= 80%)",
            "PARTIALLY_COVERED": "Test validates related aspects (confidence 60-80%)",
            "GAP": "No test validates this scenario (confidence < 60%)",
            "NOT TESTABLE": "Not automatable (feature request, docs, build issue)"
        },
        "mappings_to_review": []
    }

    # Focus on high-priority items to review first
    high_priority = sorted(
        [m for m in mappings if m.coverage_status in ['COVERED', 'PARTIALLY COVERED']],
        key=lambda m: m.match_confidence,
        reverse=False  # Review lowest confidence first
    )[:50]  # Top 50 to review

    for mapping in high_priority:
        review_data["mappings_to_review"].append({
            "bug_key": mapping.bug_key,
            "bug_summary": mapping.bug_summary,
            "coverage_status": mapping.coverage_status,
            "matched_test_file": mapping.matched_test_file,
            "match_confidence": mapping.match_confidence,
            "match_reason": mapping.match_reason,
            "validation_status": "",  # Team fills this in
            "validation_notes": "",   # Team fills this in
            "validated_by": ""        # Team fills this in
        })

    with open(output_file, 'w') as f:
        json.dump(review_data, f, indent=2)

    print(f"\n✅ Generated review template: {output_file}")
    print(f"   {len(high_priority)} high-priority mappings to review")
    print(f"\nNext steps:")
    print(f"1. Team reviews and updates validation_status for each mapping")
    print(f"2. Run: python coverage_rubric.py --learn-from <review_file>")
    print(f"3. System improves matching based on feedback")
