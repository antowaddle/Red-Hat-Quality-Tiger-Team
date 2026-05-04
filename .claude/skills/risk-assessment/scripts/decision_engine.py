#!/usr/bin/env python3
"""Decision engine for aggregating analyzer results.

Combines outputs from 4 parallel analyzers (risk, test, impact, crossrepo),
calculates overall risk score, generates APPROVE/WARN decision, and produces
final PR analysis report.

Usage:
    python3 scripts/decision_engine.py <pr_number> [--output <file>]

Example:
    python3 scripts/decision_engine.py 7292 --output artifacts/pr-analyses/pr-7292-analysis.md
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Import frontmatter utilities
sys.path.insert(0, str(Path(__file__).parent))
from frontmatter import read, write


DEFAULT_BLAST_RADIUS = "medium"
BLAST_RADIUS_SCORES = {"low": 20, "medium": 50, "high": 80}


def _has_critical_k8s_renames(impact_data: dict) -> tuple[bool, list]:
    """Pattern from incident RHOAIENG-57824: K8s resource renames that break
    downstream consumers are high-risk and require coordination.
    """
    k8s_renames = impact_data.get("k8s_resource_renames", [])
    cross_repo_refs = impact_data.get("cross_repo_references", [])

    if not (k8s_renames and cross_repo_refs):
        return False, []

    critical_refs = [r for r in cross_repo_refs if r.get("impact") == "CRITICAL"]
    return (True, critical_refs) if critical_refs else (False, [])


def aggregate_risk_score(
    risk_data: dict,
    test_data: dict,
    impact_data: dict,
    crossrepo_data: dict
) -> tuple[int, dict]:
    """
    Calculate overall risk score (0-100).

    Weighting:
    - Risk analyzer: 40% (security, breaking, critical path, deps)
    - Test coverage: 30% (inverse - low coverage = high risk)
    - Impact: 20% (blast radius)
    - Cross-repo: 10% (breaking tests)

    CRITICAL ESCALATION (RHOAIENG-57824):
    If K8s resource renames detected with critical cross-repo references,
    escalate breaking_risk to 90-95 to properly reflect the incident pattern.

    Returns:
        (overall_risk_score, breakdown_dict) where breakdown contains individual scores used
    """
    # Extract risk scores
    risk_score = risk_data.get("overall_risk", 50)
    breaking_risk = risk_data.get("breaking_risk", 50)

    # Test coverage inverse (0% coverage = 100 risk, 100% coverage = 0 risk)
    coverage_percent = test_data.get("coverage_percent", 50)
    test_risk = 100 - coverage_percent

    # Impact blast radius mapping
    blast_radius = (impact_data.get("blast_radius") or DEFAULT_BLAST_RADIUS).lower()
    impact_risk = BLAST_RADIUS_SCORES.get(blast_radius, 50)

    # Cross-repo breaking tests
    requires_test_updates = crossrepo_data.get("requires_test_updates", False)
    breaking_tests_count = len(crossrepo_data.get("breaking_tests", []))
    crossrepo_risk = 70 if requires_test_updates else 30
    if breaking_tests_count > 3:
        crossrepo_risk = 90

    # CRITICAL: Check for K8s resource renames with cross-repo impact (Incident: RHOAIENG-57824)
    k8s_critical_override, critical_refs = _has_critical_k8s_renames(impact_data)

    if k8s_critical_override:
        security_risk = risk_data.get("security_risk", 50)
        critical_path_risk = risk_data.get("critical_path_risk", 50)
        dependency_risk = risk_data.get("dependency_risk", 0)

        breaking_risk = 95

        risk_score = int(
            (security_risk + breaking_risk + critical_path_risk + dependency_risk) / 4
        )

        crossrepo_risk = 90

    # Weighted average
    overall = (
        risk_score * 0.4 +
        test_risk * 0.3 +
        impact_risk * 0.2 +
        crossrepo_risk * 0.1
    )

    # CRITICAL OVERRIDE: If K8s resource rename with critical cross-repo impact,
    # enforce minimum risk floor to prevent dilution from averaging
    if k8s_critical_override:
        # Reference count affects minimum floor
        total_refs = sum(r.get("references_found", 0) for r in impact_data.get("cross_repo_references", []))
        if total_refs >= 10:
            # Many references (like PR #489 with 13 refs) = very high risk
            min_risk_floor = 65
        elif total_refs >= 5:
            # Several references = high risk
            min_risk_floor = 60
        else:
            # Few references = elevated risk
            min_risk_floor = 55

        overall = max(overall, min_risk_floor)

    # Return overall score and breakdown for accurate reporting
    breakdown = {
        "risk_score": risk_score,
        "test_risk": test_risk,
        "impact_risk": impact_risk,
        "crossrepo_risk": crossrepo_risk
    }

    return int(round(overall)), breakdown


def make_decision(
    overall_risk: int,
    impact_data: dict,
    crossrepo_data: dict
) -> str:
    """
    Make APPROVE or WARN decision based on risk score AND qualitative factors.

    Advisory system - never BLOCK. Even high-risk PRs get WARN.

    Rules:
    - Base: 0-40 = APPROVE, 41-100 = WARN
    - Override to WARN if:
      * Blast radius is MEDIUM or HIGH (coordination required)
      * Breaking tests >= 5 (significant cross-repo impact)
      * K8s resource renames with cross-repo references (RHOAIENG-57824 pattern)

    Returns:
        "APPROVE" or "WARN"
    """
    # Base decision on numeric score
    base_decision = "APPROVE" if overall_risk <= 40 else "WARN"

    # Qualitative overrides - escalate to WARN if any of these conditions:
    blast_radius = (impact_data.get("blast_radius") or DEFAULT_BLAST_RADIUS).lower()
    breaking_tests_count = len(crossrepo_data.get("breaking_tests", []))

    # Override: MEDIUM/HIGH blast radius requires coordination
    if blast_radius in ["medium", "high"]:
        return "WARN"

    # Override: 5+ breaking tests requires cross-repo coordination
    if breaking_tests_count >= 5:
        return "WARN"

    # Override: K8s resource renames with cross-repo impact (RHOAIENG-57824)
    has_critical, _ = _has_critical_k8s_renames(impact_data)
    if has_critical:
        return "WARN"

    return base_decision


def generate_pr_analysis(
    pr_number: int,
    repo: str,
    risk_data: dict,
    risk_body: str,
    test_data: dict,
    test_body: str,
    impact_data: dict,
    impact_body: str,
    crossrepo_data: dict,
    crossrepo_body: str
) -> tuple[dict, str]:
    """
    Generate final PR analysis report.

    Returns:
        (frontmatter_dict, body_markdown)
    """
    overall_risk, risk_breakdown = aggregate_risk_score(risk_data, test_data, impact_data, crossrepo_data)
    decision = make_decision(overall_risk, impact_data, crossrepo_data)

    # Extract key findings
    top_risks = risk_data.get("top_risks", [])[:3]  # Top 3
    missing_tests = test_data.get("missing_tests", [])[:5]  # Top 5
    affected_components = impact_data.get("affected_components", [])
    breaking_tests = crossrepo_data.get("breaking_tests", [])

    # Frontmatter
    frontmatter = {
        "pr_number": pr_number,
        "repo": repo,
        "decision": decision,
        "overall_risk": overall_risk,
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "analyzers_complete": True
    }

    # Add jira_epic if available
    # TODO: Extract from Jira context
    # if jira_epic:
    #     frontmatter["jira_epic"] = jira_epic

    # Body markdown
    decision_icon = "✅" if decision == "APPROVE" else "⚠️"
    risk_color = "🟢" if overall_risk <= 40 else "🟡" if overall_risk <= 70 else "🔴"

    body = f"""# 🤖 Quality Intelligence Report

**Repository:** {repo}
**PR:** #{pr_number}
**Decision:** {decision_icon} **{decision}**
**Overall Risk Score:** {risk_color} **{overall_risk}/100**

---

## Executive Summary

{_generate_executive_summary(overall_risk, decision, risk_data, test_data, impact_data, crossrepo_data)}

---

## 📊 Risk Assessment

{_format_risk_summary(risk_data, risk_body)}

---

## ✅ Test Coverage

{_format_test_summary(test_data, test_body)}

---

## 🏗️ Architecture Impact

{_format_impact_summary(impact_data, impact_body)}

---

## 🔗 Cross-Repo Intelligence

{_format_crossrepo_summary(crossrepo_data, crossrepo_body)}

---

## 💡 Top Recommendations

{_generate_recommendations(risk_data, test_data, impact_data, crossrepo_data)}

---

## 📈 Risk Score Breakdown

| Category | Score | Weight | Contribution |
|----------|-------|--------|--------------|
| Security & Risk | {risk_breakdown['risk_score']}/100 | 40% | {risk_breakdown['risk_score'] * 0.4:.1f} |
| Test Coverage | {risk_breakdown['test_risk']}/100 (inverse) | 30% | {risk_breakdown['test_risk'] * 0.3:.1f} |
| Architecture Impact | {risk_breakdown['impact_risk']}/100 | 20% | {risk_breakdown['impact_risk'] * 0.2:.1f} |
| Cross-Repo Impact | {risk_breakdown['crossrepo_risk']}/100 | 10% | {risk_breakdown['crossrepo_risk'] * 0.1:.1f} |
| **Overall** | **{overall_risk}/100** | **100%** | **{overall_risk:.1f}** |

---

*🤖 Generated by Agentic SDLC Quality Framework*
*Powered by Claude Sonnet 4.5*
*Analysis completed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC*

---

**Note:** This is an **advisory report**. You are free to merge without addressing all items, but please consider the risks and recommendations above.
"""

    return frontmatter, body


def _generate_executive_summary(
    overall_risk: int,
    decision: str,
    risk_data: dict,
    test_data: dict,
    impact_data: dict,
    crossrepo_data: dict
) -> str:
    """Generate executive summary paragraph."""
    risk_level = "low" if overall_risk <= 40 else "medium" if overall_risk <= 70 else "high"

    summary_parts = []

    # Overall assessment
    if decision == "APPROVE":
        summary_parts.append(f"This PR presents **{risk_level} risk** ({overall_risk}/100) and is recommended for approval.")
    else:
        summary_parts.append(f"This PR presents **{risk_level} risk** ({overall_risk}/100) with some concerns to address.")

    # Key findings
    top_concerns = []

    if test_data.get("coverage_percent", 100) < 70:
        top_concerns.append(f"test coverage is below standards ({test_data.get('coverage_percent')}%)")

    if risk_data.get("security_risk", 0) > 60:
        top_concerns.append("security-sensitive changes detected")

    if impact_data.get("blast_radius") == "high":
        top_concerns.append("high blast radius across multiple components")

    if crossrepo_data.get("requires_test_updates"):
        top_concerns.append("cross-repo test updates required")

    if top_concerns:
        summary_parts.append(f"Primary concerns: {', '.join(top_concerns)}.")

    return " ".join(summary_parts)


def _format_risk_summary(risk_data: dict, risk_body: str) -> str:
    """Format risk analysis summary."""
    overall = risk_data.get("overall_risk", 50)
    security = risk_data.get("security_risk", 50)
    breaking = risk_data.get("breaking_risk", 50)
    critical_path = risk_data.get("critical_path_risk", 50)

    summary = f"""**Overall Risk:** {overall}/100

**Risk Breakdown:**
- Security: {security}/100
- Breaking Changes: {breaking}/100
- Critical Paths: {critical_path}/100

**Top Risks Found:** {len(risk_data.get('top_risks', []))}

For detailed analysis, see `artifacts/risk-findings/risk-{risk_data.get('pr_number')}.md`
"""
    return summary


def _format_test_summary(test_data: dict, test_body: str) -> str:
    """Format test coverage summary."""
    coverage = test_data.get("coverage_percent", 0)
    changed = test_data.get("functions_changed", 0)
    tested = test_data.get("functions_tested", 0)
    meets_standards = test_data.get("meets_standards", False)

    icon = "✅" if meets_standards else "❌"

    summary = f"""**Coverage:** {coverage}% ({tested}/{changed} functions tested) {icon}

**Standards:** {'Meets' if meets_standards else 'Does not meet'} minimum requirements

**Functions Missing Tests:** {len(test_data.get('missing_tests', []))}

For detailed analysis, see `artifacts/test-coverage/test-{test_data.get('pr_number')}.md`
"""
    return summary


def _format_impact_summary(impact_data: dict, impact_body: str) -> str:
    """Format architecture impact summary."""
    blast_radius = impact_data.get("blast_radius", "unknown")
    component = impact_data.get("component", "unknown")
    affected = len(impact_data.get("affected_components", []))
    breaking = impact_data.get("breaking_changes", False)

    icon = "🟢" if blast_radius == "low" else "🟡" if blast_radius == "medium" else "🔴"

    summary = f"""**Component:** {component}
**Blast Radius:** {icon} {blast_radius.title()}

**Affected Components:** {affected}
**Breaking Changes:** {'Yes ⚠️' if breaking else 'No ✅'}

For detailed analysis, see `artifacts/impact-assessments/impact-{impact_data.get('pr_number')}.md`
"""
    return summary


def _format_crossrepo_summary(crossrepo_data: dict, crossrepo_body: str) -> str:
    """Format cross-repo intelligence summary."""
    affected_repos = len(crossrepo_data.get("affected_test_repos", []))
    breaking_tests = len(crossrepo_data.get("breaking_tests", []))
    requires_updates = crossrepo_data.get("requires_test_updates", False)

    icon = "⚠️" if requires_updates else "✅"

    summary = f"""**Test Repositories Affected:** {affected_repos}
**Breaking Tests:** {breaking_tests} {icon}

**Requires Test Updates:** {'Yes ⚠️' if requires_updates else 'No ✅'}

For detailed analysis, see `artifacts/crossrepo-intel/crossrepo-{crossrepo_data.get('pr_number')}.md`
"""
    return summary


def _generate_recommendations(
    risk_data: dict,
    test_data: dict,
    impact_data: dict,
    crossrepo_data: dict
) -> str:
    """Generate prioritized recommendations."""
    recommendations = []

    # Critical: Missing tests for security functions
    missing_tests = test_data.get("missing_tests", [])
    critical_missing_tests = []

    # Handle both dict and string formats
    for t in missing_tests:
        if isinstance(t, dict):
            if t.get("severity") == "critical":
                critical_missing_tests.append(t)
        elif isinstance(t, str) and "critical:" in t.lower():
            critical_missing_tests.append({"function": t, "severity": "critical"})

    if critical_missing_tests:
        # Extract function names (handle both dict and string formats)
        func_names = []
        for t in critical_missing_tests[:3]:
            if isinstance(t, dict):
                func_names.append(t.get("function", str(t)))
            else:
                func_names.append(str(t))

        recommendations.append({
            "priority": "🔴 Critical",
            "action": f"Add tests for {len(critical_missing_tests)} critical function(s)",
            "details": ", ".join(func_names)
        })

    # High: Breaking tests
    breaking_tests = crossrepo_data.get("breaking_tests", [])
    if breaking_tests:
        # Handle both dict and string formats
        first_test = breaking_tests[0]
        if isinstance(first_test, dict):
            details = first_test.get("test_suite", "See cross-repo report")
        else:
            details = str(first_test) if first_test else "See cross-repo report"

        recommendations.append({
            "priority": "🟡 High",
            "action": f"Update {len(breaking_tests)} breaking test suite(s)",
            "details": details
        })

    # High: Security risks
    top_risks = risk_data.get("top_risks", [])
    high_security_risks = []

    # Handle both dict and string formats
    for r in top_risks:
        if isinstance(r, dict):
            if r.get("severity") == "high":
                high_security_risks.append(r)
        elif isinstance(r, str) and "high:" in r.lower():
            high_security_risks.append({"title": r, "severity": "high"})

    if high_security_risks:
        recs = risk_data.get("recommendations", ["Review security implications"])
        rec = recs[0] if recs else "Review security implications"

        # Extract title (handle both dict and string formats)
        first_risk = high_security_risks[0]
        if isinstance(first_risk, dict):
            details = first_risk.get("title", "")
        else:
            details = str(first_risk)

        recommendations.append({
            "priority": "🟡 High",
            "action": rec if isinstance(rec, str) else str(rec),
            "details": details
        })

    # Medium: Coordinate with affected teams
    if len(impact_data.get("affected_components", [])) > 2:
        recommendations.append({
            "priority": "🟢 Medium",
            "action": "Coordinate with affected teams before merge",
            "details": f"{len(impact_data.get('affected_components', []))} components impacted"
        })

    if not recommendations:
        return "No critical issues found. ✅"

    # Format recommendations
    output = []
    for i, rec in enumerate(recommendations, 1):
        output.append(f"{i}. **{rec['priority']}:** {rec['action']}")
        if rec["details"]:
            output.append(f"   - {rec['details']}")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(description="Decision engine for PR quality analysis")
    parser.add_argument("pr_number", type=int, help="PR number")
    parser.add_argument("--output", help="Output file path")

    args = parser.parse_args()

    try:
        pr_number = args.pr_number

        # Read all analyzer outputs
        print(f"Aggregating results for PR #{pr_number}...", file=sys.stderr)

        risk_frontmatter, risk_body = read(f"artifacts/risk-findings/risk-{pr_number}.md")
        test_frontmatter, test_body = read(f"artifacts/test-coverage/test-{pr_number}.md")
        impact_frontmatter, impact_body = read(f"artifacts/impact-assessments/impact-{pr_number}.md")
        crossrepo_frontmatter, crossrepo_body = read(f"artifacts/crossrepo-intel/crossrepo-{pr_number}.md")

        # Get repo from any of the frontmatter
        repo = risk_frontmatter.get("repo") or test_frontmatter.get("repo") or "unknown"

        # Generate final analysis
        final_frontmatter, final_body = generate_pr_analysis(
            pr_number, repo,
            risk_frontmatter, risk_body,
            test_frontmatter, test_body,
            impact_frontmatter, impact_body,
            crossrepo_frontmatter, crossrepo_body
        )

        # Write markdown output
        output_path = args.output or f"artifacts/pr-analyses/pr-{pr_number}-analysis.md"
        write(output_path, final_frontmatter, final_body)

        print(f"✓ Final analysis written to {output_path}", file=sys.stderr)

        # Generate HTML outputs
        try:
            from pathlib import Path
            import subprocess

            # Generate main PR analysis HTML
            html_output = output_path.replace('.md', '.html')
            result = subprocess.run(
                ['python3', 'scripts/html_generator.py', str(pr_number), '--output', html_output],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print(f"✓ HTML report written to {html_output}", file=sys.stderr)
            else:
                print(f"⚠️ Warning: HTML generation failed: {result.stderr}", file=sys.stderr)

            # Generate analyzer HTML reports (risk, test, impact, crossrepo)
            result = subprocess.run(
                ['python3', 'scripts/analyzer_html_generator.py', 'all', str(pr_number)],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                print(f"✓ Analyzer HTML reports generated", file=sys.stderr)
            else:
                print(f"⚠️ Warning: Analyzer HTML generation failed: {result.stderr}", file=sys.stderr)

        except Exception as e:
            print(f"⚠️ Warning: HTML generation failed: {e}", file=sys.stderr)

        print(f"Decision: {final_frontmatter['decision']}", file=sys.stderr)
        print(f"Overall Risk: {final_frontmatter['overall_risk']}/100", file=sys.stderr)

    except FileNotFoundError as e:
        print(f"Error: Analyzer output missing - {e}", file=sys.stderr)
        print("Ensure all 4 analyzers completed successfully", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
