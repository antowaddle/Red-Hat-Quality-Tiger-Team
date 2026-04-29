#!/usr/bin/env python3
"""HTML report generator for PR quality analyses.

Converts markdown analysis reports to styled HTML format.

Usage:
    python3 scripts/html_generator.py <pr_number> [--output <file>]

Example:
    python3 scripts/html_generator.py 489 --output artifacts/pr-analyses/pr-489-analysis.html
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Import frontmatter utilities
sys.path.insert(0, str(Path(__file__).parent))
from frontmatter import read


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quality Analysis - PR #{pr_number}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .header .meta {{
            font-size: 1.1em;
            opacity: 0.9;
        }}

        .decision-badge {{
            display: inline-block;
            padding: 10px 20px;
            background: #f59e0b;
            color: white;
            border-radius: 20px;
            font-weight: bold;
            font-size: 1.2em;
            margin: 20px 0;
        }}

        .decision-badge.approve {{
            background: #10b981;
        }}

        .decision-badge.warn {{
            background: #f59e0b;
        }}

        .risk-score {{
            font-size: 3em;
            font-weight: bold;
            margin: 20px 0;
        }}

        .risk-score.low {{
            color: #10b981;
        }}

        .risk-score.medium {{
            color: #f59e0b;
        }}

        .risk-score.high {{
            color: #ef4444;
        }}

        .content {{
            padding: 40px;
        }}

        .section {{
            margin-bottom: 40px;
        }}

        .section h2 {{
            color: #667eea;
            font-size: 1.8em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}

        .card {{
            background: #f9fafb;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }}

        .card h3 {{
            color: #333;
            margin-bottom: 10px;
        }}

        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}

        .stat-card {{
            background: #f9fafb;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
        }}

        .stat-card .label {{
            font-size: 0.9em;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .stat-card .value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
        }}

        .stat-card .value.high-risk {{
            color: #dc2626;
        }}

        .stat-card .value.medium-risk {{
            color: #f59e0b;
        }}

        .stat-card .value.low-risk {{
            color: #10b981;
        }}

        .stat-card .status {{
            font-size: 0.9em;
            color: #6b7280;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}

        table th,
        table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }}

        table th {{
            background: #f3f4f6;
            font-weight: 600;
            color: #374151;
        }}

        table tr:hover {{
            background: #f9fafb;
        }}

        .recommendation {{
            padding: 15px;
            margin: 10px 0;
            border-radius: 6px;
            border-left: 4px solid;
        }}

        .recommendation.critical {{
            background: #fef2f2;
            border-color: #ef4444;
        }}

        .recommendation.high {{
            background: #fffbeb;
            border-color: #f59e0b;
        }}

        .recommendation.medium {{
            background: #f0fdf4;
            border-color: #10b981;
        }}

        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }}

        .badge.success {{
            background: #d1fae5;
            color: #065f46;
        }}

        .badge.warning {{
            background: #fed7aa;
            color: #92400e;
        }}

        .badge.danger {{
            background: #fee2e2;
            color: #991b1b;
        }}

        .footer {{
            background: #f9fafb;
            padding: 20px 40px;
            text-align: center;
            color: #6b7280;
            border-top: 1px solid #e5e7eb;
        }}

        .link-card {{
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            padding: 15px;
            border-radius: 6px;
            margin: 10px 0;
        }}

        .link-card a {{
            color: #2563eb;
            text-decoration: none;
            font-weight: 500;
        }}

        .link-card a:hover {{
            text-decoration: underline;
        }}

        .alert {{
            background: #fef2f2;
            border: 1px solid #fecaca;
            border-left: 4px solid #ef4444;
            padding: 15px;
            border-radius: 6px;
            margin: 15px 0;
        }}

        .alert.warning {{
            background: #fffbeb;
            border-color: #fed7aa;
            border-left-color: #f59e0b;
        }}

        .alert-title {{
            font-weight: bold;
            margin-bottom: 8px;
            color: #991b1b;
        }}

        .alert.warning .alert-title {{
            color: #92400e;
        }}

        ul {{
            margin: 10px 0 10px 20px;
        }}

        li {{
            margin: 5px 0;
        }}

        code {{
            background: #f3f4f6;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Quality Intelligence Report</h1>
            <div class="meta">
                <strong>Repository:</strong> {repo}<br>
                <strong>PR #{pr_number}</strong>
            </div>
            <div class="decision-badge {decision_class}">{decision_icon} {decision}</div>
            <div class="risk-score {risk_class}">{overall_risk}/100</div>
        </div>

        <div class="content">
            {executive_summary}

            <div class="section">
                <h2>📊 Analysis Overview</h2>
                <div class="stat-grid">
                    {stat_cards}
                </div>
            </div>

            <div class="section">
                <h2>📈 Risk Score Breakdown</h2>
                {risk_breakdown_table}
            </div>

            {recommendations_section}

            {details_sections}

            <div class="section">
                <h2>📋 Full Report</h2>
                <div class="link-card" style="background: #f0fdf4; border-color: #86efac;">
                    <a href="pr-{pr_number}-analysis.md" style="color: #166534;">📄 View complete markdown report →</a>
                </div>
            </div>
        </div>

        <div class="footer">
            <p><strong>🤖 Generated by Agentic SDLC Quality Framework</strong></p>
            <p>Powered by Claude Sonnet 4.5</p>
            <p style="margin-top: 10px;">Analysis completed: {timestamp}</p>
            <p style="margin-top: 20px; font-style: italic;">
                ✨ This is an <strong>advisory report</strong>. You are free to merge without addressing all items,<br>
                but please consider the risks and recommendations above.
            </p>
        </div>
    </div>
</body>
</html>
"""


def load_analyzer_data(pr_number: int) -> dict[str, tuple[dict, str]]:
    """Load all analyzer outputs for a PR.

    Returns:
        Dictionary mapping analyzer name to (frontmatter, body) tuple
    """
    analyzers = {
        "risk": f"artifacts/risk-findings/risk-{pr_number}.md",
        "test": f"artifacts/test-coverage/test-{pr_number}.md",
        "impact": f"artifacts/impact-assessments/impact-{pr_number}.md",
        "crossrepo": f"artifacts/crossrepo-intel/crossrepo-{pr_number}.md"
    }

    data = {}
    for name, path in analyzers.items():
        try:
            fm, body = read(path)
            data[name] = (fm, body)
        except FileNotFoundError:
            print(f"Warning: {path} not found", file=sys.stderr)
            data[name] = ({}, "")

    return data


def generate_stat_cards(risk_fm: dict, test_fm: dict, impact_fm: dict, crossrepo_fm: dict) -> str:
    """Generate the stat cards section."""
    # Risk card
    risk_score = risk_fm.get("overall_risk", 0)
    if risk_score <= 40:
        risk_label = "✅ Low Risk"
    elif risk_score <= 70:
        risk_label = "⚠️ Medium Risk"
    else:
        risk_label = "🔴 High Risk"

    # Test coverage card
    coverage = test_fm.get("coverage_percent", 0)
    tested = test_fm.get("functions_tested", 0)
    changed = test_fm.get("functions_changed", 0)
    meets_standards = test_fm.get("meets_standards", False)

    if meets_standards:
        test_label = "✅ Meets Standard"
    else:
        test_label = "❌ Below Standard (70% min)"

    # Blast radius card
    blast_radius = impact_fm.get("blast_radius", "unknown")
    affected = len(impact_fm.get("affected_components", []))

    # Determine blast radius color class
    blast_radius_lower = blast_radius.lower()
    if blast_radius_lower == "high":
        blast_radius_class = "high-risk"
    elif blast_radius_lower == "medium":
        blast_radius_class = "medium-risk"
    elif blast_radius_lower == "low":
        blast_radius_class = "low-risk"
    else:
        blast_radius_class = ""

    # Breaking tests card
    breaking_tests = len(crossrepo_fm.get("breaking_tests", []))
    requires_updates = crossrepo_fm.get("requires_test_updates", False)

    if requires_updates:
        breaking_label = "⚠️ Updates Required"
    else:
        breaking_label = "✅ No Updates Needed"

    return f"""
                    <div class="stat-card">
                        <div class="label">Security & Risk</div>
                        <div class="value">{risk_score}/100</div>
                        <div class="status">{risk_label}</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Test Coverage</div>
                        <div class="value">{coverage}%</div>
                        <div class="status">{test_label}</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Blast Radius</div>
                        <div class="value {blast_radius_class}">{blast_radius.title()}</div>
                        <div class="status">{affected} components affected</div>
                    </div>
                    <div class="stat-card">
                        <div class="label">Breaking Tests</div>
                        <div class="value">{breaking_tests}</div>
                        <div class="status">{breaking_label}</div>
                    </div>
"""


def generate_risk_breakdown_table(pr_analysis_fm: dict, risk_fm: dict, test_fm: dict, impact_fm: dict, crossrepo_fm: dict) -> str:
    """Generate risk score breakdown table."""
    overall_risk = pr_analysis_fm.get("overall_risk", 0)

    # Extract scores
    risk_score = risk_fm.get("overall_risk", 50)
    test_risk = 100 - test_fm.get("coverage_percent", 50)

    blast_radius = impact_fm.get("blast_radius", "medium")
    impact_score_map = {"low": 20, "medium": 50, "high": 80}
    impact_score = impact_score_map.get(blast_radius, 50)

    requires_updates = crossrepo_fm.get("requires_test_updates", False)
    crossrepo_score = 70 if requires_updates else 30

    # Calculate contributions
    risk_contrib = risk_score * 0.4
    test_contrib = test_risk * 0.3
    impact_contrib = impact_score * 0.2
    crossrepo_contrib = crossrepo_score * 0.1

    return f"""
                <table>
                    <thead>
                        <tr>
                            <th>Category</th>
                            <th>Score</th>
                            <th>Weight</th>
                            <th>Contribution</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Security & Risk</td>
                            <td>{risk_score}/100</td>
                            <td>40%</td>
                            <td>{risk_contrib:.1f}</td>
                        </tr>
                        <tr>
                            <td>Test Coverage (inverse)</td>
                            <td>{test_risk:.0f}/100</td>
                            <td>30%</td>
                            <td><strong>{test_contrib:.1f}</strong></td>
                        </tr>
                        <tr>
                            <td>Architecture Impact</td>
                            <td>{impact_score}/100</td>
                            <td>20%</td>
                            <td>{impact_contrib:.1f}</td>
                        </tr>
                        <tr>
                            <td>Cross-Repo Impact</td>
                            <td>{crossrepo_score}/100</td>
                            <td>10%</td>
                            <td>{crossrepo_contrib:.1f}</td>
                        </tr>
                        <tr style="background: #f3f4f6; font-weight: bold;">
                            <td><strong>Overall</strong></td>
                            <td><strong>{overall_risk}/100</strong></td>
                            <td><strong>100%</strong></td>
                            <td><strong>{overall_risk:.1f}</strong></td>
                        </tr>
                    </tbody>
                </table>
"""


def parse_recommendations(body: str) -> str:
    """Parse recommendations from markdown body."""
    lines = body.split("\n")
    in_recommendations = False
    recs = []

    for line in lines:
        if "## 💡 Top Recommendations" in line:
            in_recommendations = True
            continue
        if in_recommendations:
            if line.startswith("##"):
                break
            if line.strip().startswith("1.") or line.strip().startswith("2.") or line.strip().startswith("3."):
                # Parse recommendation
                if "🔴 Critical" in line:
                    priority_class = "critical"
                    priority_text = "🔴 Critical Priority"
                elif "🟡 High" in line:
                    priority_class = "high"
                    priority_text = "🟡 High Priority"
                else:
                    priority_class = "medium"
                    priority_text = "🟢 Medium Priority"

                # Extract action text
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    action = parts[2].strip()
                elif len(parts) == 2:
                    action = parts[1].strip()
                else:
                    action = line.strip()

                recs.append((priority_class, priority_text, action))
            elif line.strip().startswith("-"):
                # Detail line
                if recs:
                    last_rec = recs[-1]
                    detail = line.strip()[1:].strip()
                    recs[-1] = (last_rec[0], last_rec[1], last_rec[2], detail)

    if not recs:
        return '<div class="card"><p>No critical issues found. ✅</p></div>'

    html = ""
    for rec in recs:
        priority_class = rec[0]
        priority_text = rec[1]
        action = rec[2]
        detail = rec[3] if len(rec) > 3 else None

        html += f'<div class="recommendation {priority_class}">\n'
        html += f'    <strong>{priority_text}:</strong> {action}\n'
        if detail:
            html += f'    <p style="margin-top: 5px; color: #6b7280;">{detail}</p>\n'
        html += '</div>\n'

    return html


def generate_details_sections(pr_number: int, risk_fm: dict, test_fm: dict, impact_fm: dict, crossrepo_fm: dict) -> str:
    """Generate detailed sections for each analyzer."""
    html = ""

    # Risk section
    risk_score = risk_fm.get("overall_risk", 0)
    security_risk = risk_fm.get("security_risk", 0)
    breaking_risk = risk_fm.get("breaking_risk", 0)
    critical_path_risk = risk_fm.get("critical_path_risk", 0)
    top_risks_count = len(risk_fm.get("top_risks", []))

    if risk_score <= 40:
        risk_badge = '<span class="badge success">Low</span>'
    elif risk_score <= 70:
        risk_badge = '<span class="badge warning">Medium</span>'
    else:
        risk_badge = '<span class="badge danger">High</span>'

    html += f"""
            <div class="section">
                <h2>📊 Risk Assessment Details</h2>
                <div class="card">
                    <h3>Overall Risk: {risk_score}/100 {risk_badge}</h3>
                    <p><strong>Risk Breakdown:</strong></p>
                    <ul style="margin-left: 20px; margin-top: 10px;">
                        <li>Security: {security_risk}/100</li>
                        <li>Breaking Changes: {breaking_risk}/100</li>
                        <li>Critical Paths: {critical_path_risk}/100</li>
                    </ul>
                    <p style="margin-top: 15px;"><strong>Top Risks Found:</strong> {top_risks_count}</p>
                    <div class="link-card">
                        <a href="../risk-findings/risk-{pr_number}.html">📄 View detailed risk analysis →</a>
                    </div>
                </div>
            </div>
"""

    # Test section
    coverage = test_fm.get("coverage_percent", 0)
    tested = test_fm.get("functions_tested", 0)
    changed = test_fm.get("functions_changed", 0)
    meets_standards = test_fm.get("meets_standards", False)
    missing_tests = test_fm.get("missing_tests", [])

    if meets_standards:
        test_badge = '<span class="badge success">Meets Standards</span>'
    else:
        test_badge = '<span class="badge danger">Below Standard</span>'

    html += f"""
            <div class="section">
                <h2>✅ Test Coverage</h2>
                <div class="card">
                    <h3>Coverage: {coverage}% ({tested}/{changed} functions tested) {test_badge}</h3>
                    <p><strong>Standards:</strong> {'Meets' if meets_standards else 'Does not meet'} minimum requirements (70% minimum, 80% target)</p>
"""

    if missing_tests:
        html += f'                    <p style="margin-top: 10px;"><strong>Functions Missing Tests:</strong> {len(missing_tests)}</p>\n'
        html += '                    <ul style="margin-left: 20px; margin-top: 10px;">\n'
        for test in missing_tests[:5]:  # Show top 5
            if isinstance(test, dict):
                func = test.get("function", str(test))
            else:
                func = str(test)
            html += f'                        <li>{func}</li>\n'
        html += '                    </ul>\n'

    html += f"""                    <div class="link-card">
                        <a href="../test-coverage/test-{pr_number}.html">📄 View detailed test coverage report →</a>
                    </div>
                </div>
            </div>
"""

    # Impact section
    blast_radius = impact_fm.get("blast_radius", "unknown")
    component = impact_fm.get("component", "unknown")
    affected = len(impact_fm.get("affected_components", []))
    breaking = impact_fm.get("breaking_changes", False)
    k8s_renames = impact_fm.get("k8s_resource_renames", [])
    cross_repo_refs = impact_fm.get("cross_repo_references", [])

    if blast_radius == "low":
        blast_badge = '<span class="badge success">Low Blast Radius</span>'
    elif blast_radius == "medium":
        blast_badge = '<span class="badge warning">Medium Blast Radius</span>'
    else:
        blast_badge = '<span class="badge danger">High Blast Radius</span>'

    html += f"""
            <div class="section">
                <h2>🏗️ Architecture Impact</h2>
                <div class="card">
                    <h3>Component: {component} {blast_badge}</h3>
                    <p><strong>Affected Components:</strong> {affected}</p>
                    <p><strong>Breaking Changes:</strong> {'Yes ⚠️' if breaking else 'No ✅'}</p>
"""

    # K8s renames alert
    if k8s_renames:
        html += '                    <div class="alert warning">\n'
        html += '                        <div class="alert-title">🚨 KUBERNETES RESOURCE RENAME DETECTED</div>\n'
        for rename in k8s_renames:
            res_type = rename.get("resource_type", "resource").upper()
            old_name = rename.get("old_name", "unknown")
            new_name = rename.get("new_name", "unknown")
            html += f'                        <p><strong>{res_type}:</strong> <code>{old_name}</code> → <code>{new_name}</code></p>\n'

        if cross_repo_refs:
            html += '                        <p style="margin-top: 10px;"><strong>Cross-Repo References Found:</strong></p>\n'
            html += '                        <ul>\n'
            for ref in cross_repo_refs:
                repo = ref.get("repo", "unknown")
                count = ref.get("references_found", 0)
                impact = ref.get("impact", "UNKNOWN")
                html += f'                            <li>{repo}: {count} references ({impact})</li>\n'
            html += '                        </ul>\n'

        html += '                    </div>\n'

    html += f"""                    <div class="link-card">
                        <a href="../impact-assessments/impact-{pr_number}.html">📄 View detailed architecture impact →</a>
                    </div>
                </div>
            </div>
"""

    # Cross-repo section
    affected_repos = len(crossrepo_fm.get("affected_test_repos", []))
    breaking_tests = len(crossrepo_fm.get("breaking_tests", []))
    requires_updates = crossrepo_fm.get("requires_test_updates", False)

    html += f"""
            <div class="section">
                <h2>🔗 Cross-Repo Intelligence</h2>
                <div class="card">
                    <h3>Test Repositories Affected: {affected_repos} {'<span class="badge warning">Updates Required</span>' if requires_updates else '<span class="badge success">No Updates</span>'}</h3>
                    <p><strong>Breaking Tests:</strong> {breaking_tests} {'⚠️' if requires_updates else '✅'}</p>
                    <p><strong>Requires Test Updates:</strong> {'Yes ⚠️' if requires_updates else 'No ✅'}</p>
"""

    if crossrepo_fm.get("breaking_tests"):
        html += '                    <ul style="margin-left: 20px; margin-top: 10px;">\n'
        for test in crossrepo_fm.get("breaking_tests", [])[:5]:
            if isinstance(test, dict):
                test_name = test.get("test_suite", str(test))
            else:
                test_name = str(test)
            html += f'                        <li>{test_name}</li>\n'
        html += '                    </ul>\n'

    html += f"""                    <div class="link-card">
                        <a href="../crossrepo-intel/crossrepo-{pr_number}.html">📄 View detailed cross-repo analysis →</a>
                    </div>
                </div>
            </div>
"""

    return html


def generate_html(pr_number: int) -> str:
    """Generate HTML report for a PR analysis.

    Args:
        pr_number: PR number

    Returns:
        HTML content as string
    """
    # Load PR analysis
    pr_analysis_fm, pr_analysis_body = read(f"artifacts/pr-analyses/pr-{pr_number}-analysis.md")

    # Load all analyzer data
    analyzer_data = load_analyzer_data(pr_number)
    risk_fm, _ = analyzer_data["risk"]
    test_fm, _ = analyzer_data["test"]
    impact_fm, _ = analyzer_data["impact"]
    crossrepo_fm, _ = analyzer_data["crossrepo"]

    # Extract frontmatter
    decision = pr_analysis_fm.get("decision", "UNKNOWN")
    overall_risk = pr_analysis_fm.get("overall_risk", 0)
    repo = pr_analysis_fm.get("repo", "unknown")
    timestamp = pr_analysis_fm.get("timestamp", "")

    # Format timestamp
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        except:
            timestamp_str = timestamp
    else:
        timestamp_str = "Unknown"

    # Decision styling
    decision_class = "approve" if decision == "APPROVE" else "warn"
    decision_icon = "✅" if decision == "APPROVE" else "⚠️"

    # Risk styling - if WARN decision, show at least "medium" (orange) color
    if decision == "WARN":
        # WARN decision: use minimum "medium" color even for low numeric scores
        if overall_risk <= 40:
            risk_class = "medium"  # Override: show orange for WARN even with low score
        elif overall_risk <= 70:
            risk_class = "medium"
        else:
            risk_class = "high"
    else:
        # APPROVE decision: use score-based coloring
        if overall_risk <= 40:
            risk_class = "low"
        elif overall_risk <= 70:
            risk_class = "medium"
        else:
            risk_class = "high"

    # Extract executive summary
    lines = pr_analysis_body.split("\n")
    exec_summary = ""
    in_summary = False
    for line in lines:
        if "## Executive Summary" in line:
            in_summary = True
            continue
        if in_summary:
            if line.startswith("##"):
                break
            if line.strip():
                exec_summary += line.strip() + " "

    exec_summary_html = f"""
            <div class="section">
                <h2>Executive Summary</h2>
                <div class="card">
                    <p>{exec_summary.strip()}</p>
                </div>
            </div>
"""

    # Generate components
    stat_cards = generate_stat_cards(risk_fm, test_fm, impact_fm, crossrepo_fm)
    risk_breakdown_table = generate_risk_breakdown_table(pr_analysis_fm, risk_fm, test_fm, impact_fm, crossrepo_fm)
    recommendations_html = parse_recommendations(pr_analysis_body)
    details_sections = generate_details_sections(pr_number, risk_fm, test_fm, impact_fm, crossrepo_fm)

    recommendations_section = f"""
            <div class="section">
                <h2>💡 Top Recommendations</h2>
                {recommendations_html}
            </div>
"""

    # Fill template
    html = HTML_TEMPLATE.format(
        pr_number=pr_number,
        repo=repo,
        decision=decision,
        decision_class=decision_class,
        decision_icon=decision_icon,
        overall_risk=overall_risk,
        risk_class=risk_class,
        executive_summary=exec_summary_html,
        stat_cards=stat_cards,
        risk_breakdown_table=risk_breakdown_table,
        recommendations_section=recommendations_section,
        details_sections=details_sections,
        timestamp=timestamp_str
    )

    return html


def main():
    parser = argparse.ArgumentParser(description="Generate HTML report for PR analysis")
    parser.add_argument("pr_number", type=int, help="PR number")
    parser.add_argument("--output", help="Output file path")

    args = parser.parse_args()

    try:
        pr_number = args.pr_number

        print(f"Generating HTML report for PR #{pr_number}...", file=sys.stderr)

        html = generate_html(pr_number)

        # Write output
        output_path = args.output or f"artifacts/pr-analyses/pr-{pr_number}-analysis.html"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(html)

        print(f"✓ HTML report written to {output_path}", file=sys.stderr)

    except FileNotFoundError as e:
        print(f"Error: Analysis file missing - {e}", file=sys.stderr)
        print(f"Ensure PR #{args.pr_number} analysis exists", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
