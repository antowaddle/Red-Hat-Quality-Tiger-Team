#!/usr/bin/env python3
"""HTML generator for individual analyzer reports.

Generates styled HTML versions of risk, test, impact, and crossrepo analyzer outputs.

Usage:
    python3 scripts/analyzer_html_generator.py <type> <pr_number>
    python3 scripts/analyzer_html_generator.py all <pr_number>

Example:
    python3 scripts/analyzer_html_generator.py risk 489
    python3 scripts/analyzer_html_generator.py all 489
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from frontmatter import read


BASE_STYLE = """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }

        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px 40px;
        }

        .header h1 {
            font-size: 2em;
            margin-bottom: 10px;
        }

        .header .meta {
            font-size: 1em;
            opacity: 0.9;
        }

        .content {
            padding: 40px;
        }

        h2 {
            color: #667eea;
            font-size: 1.5em;
            margin: 30px 0 15px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }

        h3 {
            color: #374151;
            font-size: 1.2em;
            margin: 20px 0 10px 0;
        }

        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
            margin-left: 10px;
        }

        .badge.success {
            background: #d1fae5;
            color: #065f46;
        }

        .badge.warning {
            background: #fed7aa;
            color: #92400e;
        }

        .badge.danger {
            background: #fee2e2;
            color: #991b1b;
        }

        .badge.info {
            background: #dbeafe;
            color: #1e40af;
        }

        .card {
            background: #f9fafb;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }

        .risk-item, .finding-item {
            background: #f9fafb;
            border-left: 4px solid;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }

        .risk-item.critical, .finding-item.critical {
            border-color: #ef4444;
            background: #fef2f2;
        }

        .risk-item.high, .finding-item.high {
            border-color: #f59e0b;
            background: #fffbeb;
        }

        .risk-item.medium, .finding-item.medium {
            border-color: #3b82f6;
            background: #eff6ff;
        }

        .risk-item.low, .finding-item.low {
            border-color: #10b981;
            background: #f0fdf4;
        }

        .risk-item h4, .finding-item h4 {
            margin: 0 0 10px 0;
            color: #111827;
        }

        .risk-item p, .finding-item p {
            margin: 5px 0;
            color: #4b5563;
        }

        .file-ref {
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 0.9em;
            background: #f3f4f6;
            padding: 2px 6px;
            border-radius: 3px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }

        table th,
        table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }

        table th {
            background: #f3f4f6;
            font-weight: 600;
            color: #374151;
        }

        table tr:hover {
            background: #f9fafb;
        }

        ul, ol {
            margin: 10px 0 10px 30px;
        }

        li {
            margin: 5px 0;
        }

        code {
            background: #f3f4f6;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 0.9em;
        }

        pre {
            background: #1f2937;
            color: #f9fafb;
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
            margin: 15px 0;
        }

        pre code {
            background: none;
            color: inherit;
            padding: 0;
        }

        .footer {
            background: #f9fafb;
            padding: 20px 40px;
            text-align: center;
            color: #6b7280;
            border-top: 1px solid #e5e7eb;
        }

        .back-link {
            display: inline-block;
            margin-bottom: 20px;
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }

        .back-link:hover {
            text-decoration: underline;
        }

        .stat-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }

        .stat-box {
            background: #f9fafb;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #e5e7eb;
        }

        .stat-box .label {
            font-size: 0.85em;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .stat-box .value {
            font-size: 1.8em;
            font-weight: bold;
            color: #667eea;
            margin: 5px 0;
        }
"""


def generate_risk_html(pr_number: int) -> str:
    """Generate HTML for risk analysis report."""
    fm, body = read(f"artifacts/risk-findings/risk-{pr_number}.md")

    overall_risk = fm.get("overall_risk", 0)
    security_risk = fm.get("security_risk", 0)
    breaking_risk = fm.get("breaking_risk", 0)
    critical_path_risk = fm.get("critical_path_risk", 0)
    top_risks = fm.get("top_risks", [])
    recommendations = fm.get("recommendations", [])
    repo = fm.get("repo", "unknown")

    # Risk level badge
    if overall_risk <= 40:
        risk_badge = '<span class="badge success">Low Risk</span>'
    elif overall_risk <= 70:
        risk_badge = '<span class="badge warning">Medium Risk</span>'
    else:
        risk_badge = '<span class="badge danger">High Risk</span>'

    # Generate risk items HTML
    risks_html = ""
    for risk in top_risks:
        severity = risk.get("severity", "medium").lower()
        title = risk.get("title", "Unknown risk")
        description = risk.get("description", "")
        file = risk.get("file", "")
        lines = risk.get("lines", "")
        risk_score = risk.get("risk_score", 0)

        risks_html += f'''
        <div class="risk-item {severity}">
            <h4>{title} <span class="badge {severity}">{severity.upper()}</span></h4>
            <p>{description}</p>
            <p><strong>Risk Score:</strong> {risk_score}/100</p>
            {f'<p><strong>Location:</strong> <code class="file-ref">{file}:{lines}</code></p>' if file else ''}
        </div>
'''

    # Generate recommendations HTML
    rec_html = "<ul>"
    for rec in recommendations:
        rec_html += f"<li>{rec}</li>"
    rec_html += "</ul>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Risk Analysis - PR #{pr_number}</title>
    <style>
{BASE_STYLE}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Risk Analysis Report</h1>
            <div class="meta">
                <strong>Repository:</strong> {repo}<br>
                <strong>PR #{pr_number}</strong>
            </div>
        </div>

        <div class="content">
            <a href="pr-{pr_number}-analysis.html" class="back-link">← Back to Full Analysis</a>

            <h2>Overview</h2>
            <div class="card">
                <h3>Overall Risk Score: {overall_risk}/100 {risk_badge}</h3>

                <div class="stat-row">
                    <div class="stat-box">
                        <div class="label">Security Risk</div>
                        <div class="value">{security_risk}</div>
                    </div>
                    <div class="stat-box">
                        <div class="label">Breaking Changes</div>
                        <div class="value">{breaking_risk}</div>
                    </div>
                    <div class="stat-box">
                        <div class="label">Critical Paths</div>
                        <div class="value">{critical_path_risk}</div>
                    </div>
                </div>
            </div>

            <h2>Top Risks Identified ({len(top_risks)})</h2>
            {risks_html}

            <h2>Recommendations</h2>
            <div class="card">
                {rec_html}
            </div>
        </div>

        <div class="footer">
            <p><strong>🤖 Generated by Agentic SDLC Quality Framework</strong></p>
            <p>Risk Analysis powered by Claude Sonnet 4.5</p>
        </div>
    </div>
</body>
</html>
"""
    return html


def generate_test_html(pr_number: int) -> str:
    """Generate HTML for test coverage report."""
    fm, body = read(f"artifacts/test-coverage/test-{pr_number}.md")

    coverage = fm.get("coverage_percent", 0)
    functions_changed = fm.get("functions_changed", 0)
    functions_tested = fm.get("functions_tested", 0)
    missing_tests = fm.get("missing_tests", [])
    meets_standards = fm.get("meets_standards", False)
    repo = fm.get("repo", "unknown")

    # Badge
    if meets_standards:
        coverage_badge = '<span class="badge success">Meets Standards</span>'
    else:
        coverage_badge = '<span class="badge danger">Below Standards</span>'

    # Missing tests HTML
    missing_html = ""
    if missing_tests:
        missing_html = "<ul>"
        for test in missing_tests:
            if isinstance(test, dict):
                func = test.get("function", str(test))
                severity = test.get("severity", "medium")
            else:
                func = str(test)
                severity = "medium"
            missing_html += f'<li><code>{func}</code> <span class="badge {severity}">{severity}</span></li>'
        missing_html += "</ul>"
    else:
        missing_html = '<p style="color: #10b981;">✅ All modified functions have tests!</p>'

    # Parse body for detailed sections
    body_html = body.replace("##", "<h2>").replace("\n\n", "</p><p>")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Coverage - PR #{pr_number}</title>
    <style>
{BASE_STYLE}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✅ Test Coverage Analysis</h1>
            <div class="meta">
                <strong>Repository:</strong> {repo}<br>
                <strong>PR #{pr_number}</strong>
            </div>
        </div>

        <div class="content">
            <a href="pr-{pr_number}-analysis.html" class="back-link">← Back to Full Analysis</a>

            <h2>Coverage Summary</h2>
            <div class="card">
                <h3>Coverage: {coverage}% ({functions_tested}/{functions_changed} functions) {coverage_badge}</h3>

                <div class="stat-row">
                    <div class="stat-box">
                        <div class="label">Coverage %</div>
                        <div class="value">{coverage}%</div>
                    </div>
                    <div class="stat-box">
                        <div class="label">Functions Tested</div>
                        <div class="value">{functions_tested}/{functions_changed}</div>
                    </div>
                    <div class="stat-box">
                        <div class="label">Missing Tests</div>
                        <div class="value">{len(missing_tests)}</div>
                    </div>
                </div>
            </div>

            <h2>Functions Missing Tests</h2>
            <div class="card">
                {missing_html}
            </div>

            <h2>Standards</h2>
            <div class="card">
                <ul>
                    <li>Minimum Coverage: <strong>70%</strong></li>
                    <li>Target Coverage: <strong>80%</strong></li>
                    <li>Critical Functions: <strong>100%</strong></li>
                </ul>
                <p style="margin-top: 15px;"><strong>Status:</strong> {'✅ Meets all standards' if meets_standards else '❌ Does not meet minimum requirements'}</p>
            </div>
        </div>

        <div class="footer">
            <p><strong>🤖 Generated by Agentic SDLC Quality Framework</strong></p>
            <p>Test Analysis powered by Claude Sonnet 4.5</p>
        </div>
    </div>
</body>
</html>
"""
    return html


def generate_impact_html(pr_number: int) -> str:
    """Generate HTML for architecture impact report."""
    fm, body = read(f"artifacts/impact-assessments/impact-{pr_number}.md")

    blast_radius = fm.get("blast_radius", "unknown")
    component = fm.get("component", "unknown")
    affected_components = fm.get("affected_components", [])
    breaking_changes = fm.get("breaking_changes", False)
    k8s_renames = fm.get("k8s_resource_renames", [])
    cross_repo_refs = fm.get("cross_repo_references", [])
    repo = fm.get("repo", "unknown")

    # Blast radius badge
    if blast_radius == "low":
        blast_badge = '<span class="badge success">Low</span>'
    elif blast_radius == "medium":
        blast_badge = '<span class="badge warning">Medium</span>'
    else:
        blast_badge = '<span class="badge danger">High</span>'

    # K8s renames alert
    k8s_html = ""
    if k8s_renames:
        k8s_html = '<div class="risk-item critical">'
        k8s_html += '<h4>🚨 KUBERNETES RESOURCE RENAME DETECTED</h4>'
        for rename in k8s_renames:
            res_type = rename.get("resource_type", "resource").upper()
            old_name = rename.get("old_name", "unknown")
            new_name = rename.get("new_name", "unknown")
            k8s_html += f'<p><strong>{res_type}:</strong> <code>{old_name}</code> → <code>{new_name}</code></p>'

        if cross_repo_refs:
            k8s_html += '<p style="margin-top: 10px;"><strong>Cross-Repo References Found:</strong></p><ul>'
            for ref in cross_repo_refs:
                repo_name = ref.get("repo", "unknown")
                count = ref.get("references_found", 0)
                impact = ref.get("impact", "UNKNOWN")
                k8s_html += f'<li>{repo_name}: {count} references ({impact})</li>'
            k8s_html += '</ul>'
        k8s_html += '</div>'

    # Affected components list
    components_html = "<ul>"
    for comp in affected_components:
        components_html += f"<li><code>{comp}</code></li>"
    components_html += "</ul>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Architecture Impact - PR #{pr_number}</title>
    <style>
{BASE_STYLE}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏗️ Architecture Impact Assessment</h1>
            <div class="meta">
                <strong>Repository:</strong> {repo}<br>
                <strong>PR #{pr_number}</strong>
            </div>
        </div>

        <div class="content">
            <a href="pr-{pr_number}-analysis.html" class="back-link">← Back to Full Analysis</a>

            <h2>Impact Summary</h2>
            <div class="card">
                <h3>Component: {component}</h3>
                <div class="stat-row">
                    <div class="stat-box">
                        <div class="label">Blast Radius</div>
                        <div class="value">{blast_radius.title()}</div>
                        {blast_badge}
                    </div>
                    <div class="stat-box">
                        <div class="label">Affected Components</div>
                        <div class="value">{len(affected_components)}</div>
                    </div>
                    <div class="stat-box">
                        <div class="label">Breaking Changes</div>
                        <div class="value">{'Yes' if breaking_changes else 'No'}</div>
                        {'<span class="badge danger">⚠️</span>' if breaking_changes else '<span class="badge success">✓</span>'}
                    </div>
                </div>
            </div>

            {k8s_html}

            <h2>Affected Components ({len(affected_components)})</h2>
            <div class="card">
                {components_html}
            </div>
        </div>

        <div class="footer">
            <p><strong>🤖 Generated by Agentic SDLC Quality Framework</strong></p>
            <p>Impact Analysis powered by Claude Sonnet 4.5</p>
        </div>
    </div>
</body>
</html>
"""
    return html


def generate_crossrepo_html(pr_number: int) -> str:
    """Generate HTML for cross-repo intelligence report."""
    fm, body = read(f"artifacts/crossrepo-intel/crossrepo-{pr_number}.md")

    affected_test_repos = fm.get("affected_test_repos", [])
    breaking_tests = fm.get("breaking_tests", [])
    requires_test_updates = fm.get("requires_test_updates", False)
    repo = fm.get("repo", "unknown")

    # Badge
    if requires_test_updates:
        status_badge = '<span class="badge warning">Updates Required</span>'
    else:
        status_badge = '<span class="badge success">No Updates</span>'

    # Breaking tests HTML
    tests_html = ""
    if breaking_tests:
        tests_html = "<ul>"
        for test in breaking_tests:
            if isinstance(test, dict):
                test_name = test.get("test_suite", str(test))
                probability = test.get("probability", "medium")
            else:
                test_name = str(test)
                probability = "medium"
            tests_html += f'<li><code>{test_name}</code> <span class="badge {probability}">{probability}</span></li>'
        tests_html += "</ul>"
    else:
        tests_html = '<p style="color: #10b981;">✅ No breaking tests detected!</p>'

    # Affected repos
    repos_html = "<ul>"
    for repo_item in affected_test_repos:
        repos_html += f"<li><code>{repo_item}</code></li>"
    repos_html += "</ul>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cross-Repo Intelligence - PR #{pr_number}</title>
    <style>
{BASE_STYLE}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔗 Cross-Repo Intelligence</h1>
            <div class="meta">
                <strong>Repository:</strong> {repo}<br>
                <strong>PR #{pr_number}</strong>
            </div>
        </div>

        <div class="content">
            <a href="pr-{pr_number}-analysis.html" class="back-link">← Back to Full Analysis</a>

            <h2>Cross-Repository Impact</h2>
            <div class="card">
                <div class="stat-row">
                    <div class="stat-box">
                        <div class="label">Test Repos Affected</div>
                        <div class="value">{len(affected_test_repos)}</div>
                    </div>
                    <div class="stat-box">
                        <div class="label">Breaking Tests</div>
                        <div class="value">{len(breaking_tests)}</div>
                        {'<span class="badge warning">⚠️</span>' if requires_test_updates else '<span class="badge success">✓</span>'}
                    </div>
                    <div class="stat-box">
                        <div class="label">Updates Required</div>
                        <div class="value">{'Yes' if requires_test_updates else 'No'}</div>
                        {status_badge}
                    </div>
                </div>
            </div>

            <h2>Affected Test Repositories ({len(affected_test_repos)})</h2>
            <div class="card">
                {repos_html}
            </div>

            <h2>Breaking Tests ({len(breaking_tests)})</h2>
            <div class="card">
                {tests_html}
            </div>
        </div>

        <div class="footer">
            <p><strong>🤖 Generated by Agentic SDLC Quality Framework</strong></p>
            <p>Cross-Repo Analysis powered by Claude Sonnet 4.5</p>
        </div>
    </div>
</body>
</html>
"""
    return html


def main():
    parser = argparse.ArgumentParser(description="Generate HTML for analyzer reports")
    parser.add_argument("type", choices=["risk", "test", "impact", "crossrepo", "all"], help="Report type")
    parser.add_argument("pr_number", type=int, help="PR number")

    args = parser.parse_args()

    generators = {
        "risk": ("artifacts/risk-findings/risk-{}.html", generate_risk_html),
        "test": ("artifacts/test-coverage/test-{}.html", generate_test_html),
        "impact": ("artifacts/impact-assessments/impact-{}.html", generate_impact_html),
        "crossrepo": ("artifacts/crossrepo-intel/crossrepo-{}.html", generate_crossrepo_html),
    }

    try:
        if args.type == "all":
            for report_type, (output_pattern, generator_func) in generators.items():
                output_path = output_pattern.format(args.pr_number)
                html = generator_func(args.pr_number)
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "w") as f:
                    f.write(html)
                print(f"✓ {report_type.title()} HTML written to {output_path}", file=sys.stderr)
        else:
            output_pattern, generator_func = generators[args.type]
            output_path = output_pattern.format(args.pr_number)
            html = generator_func(args.pr_number)
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(html)
            print(f"✓ HTML written to {output_path}", file=sys.stderr)

    except FileNotFoundError as e:
        print(f"Error: Report file not found - {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
