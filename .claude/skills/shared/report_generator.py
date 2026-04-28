#!/usr/bin/env python3
"""Standalone HTML report generator for bug coverage analysis.

Generates a single HTML file with:
- Inline CSS (no external stylesheets)
- Inline JavaScript (no CDN dependencies)
- Inline SVG charts (no Chart.js or D3)
- Sortable and filterable table
- Print-friendly styling

Usage:
    from shared.report_generator import generate_bug_coverage_report

    bugs = [
        {
            "key": "RHOAIENG-12345",
            "priority": "Critical",
            "summary": "OCI protocol trimmed",
            "coverage": "GAP",
            "testLevel": "Unit",
            "categories": ["functional"],
            "details": "No tests found",
            "jiraUrl": "https://redhat.atlassian.net/browse/RHOAIENG-12345"
        },
        # ... more bugs
    ]

    metadata = {
        "repoName": "odh-dashboard",
        "repoUrl": "https://github.com/opendatahub-io/odh-dashboard",
        "timestamp": "2026-04-13T12:00:00Z",
        "jql": "project = RHOAIENG AND ...",
        "totalCount": 127
    }

    html = generate_bug_coverage_report(bugs, metadata)
    with open("report.html", "w") as f:
        f.write(html)
"""

import json
import html
from datetime import datetime
from typing import List, Dict, Any


def _escape_html(text: str) -> str:
    """Escape HTML special characters to prevent XSS."""
    if not text:
        return ''
    return html.escape(str(text), quote=True)


def _safe_json_embed(data):
    """Safely embed JSON in HTML script tags.

    Prevents XSS by escaping sequences that could break out of <script> context.
    """
    json_str = json.dumps(data)
    # Escape </script> and <!-- to prevent breaking out of script context
    json_str = json_str.replace('</', '<\\/')
    json_str = json_str.replace('<!--', '<\\!--')
    return json_str


def generate_bug_coverage_report(bugs: List[Dict], metadata: Dict[str, Any]) -> str:
    """Generate standalone HTML report from bug analysis data.

    Args:
        bugs: List of bug dictionaries with keys:
            - key: Jira key (e.g., "RHOAIENG-12345")
            - priority: Priority level
            - summary: Bug summary
            - coverage: Coverage status (COVERED, PARTIALLY COVERED, GAP, NOT TESTABLE)
            - testLevel: Test level (Unit, Mock, E2E, N/A)
            - categories: List of categories (functional, upgrade, etc.)
            - details: Coverage details
            - jiraUrl: Full Jira URL
        metadata: Dictionary with keys:
            - repoName: Repository name
            - repoUrl: Repository URL
            - timestamp: ISO timestamp
            - jql: JQL query used
            - totalCount: Total bug count

    Returns:
        Complete HTML string (standalone, no external dependencies)
    """
    # Calculate statistics
    stats = _calculate_stats(bugs)

    # Generate HTML sections
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bug Coverage Report - {_escape_html(metadata['repoName'])}</title>
    {_generate_css()}
</head>
<body>
    <button id="theme-toggle" aria-label="Toggle dark mode">Dark Mode</button>
    {_generate_header(metadata)}
    {_generate_dashboard(stats)}
    {_generate_filters()}
    {_generate_bug_table()}
    {_generate_e2e_breakdown(stats)}
    {_generate_recommendations(bugs, stats)}
    {_generate_footer()}
    {_generate_javascript(bugs, metadata, stats)}
</body>
</html>"""

    return html


def _calculate_stats(bugs: List[Dict]) -> Dict[str, Any]:
    """Calculate statistics from bug data."""
    stats = {
        "total": len(bugs),
        "covered": 0,
        "partialCovered": 0,
        "gap": 0,
        "notTestable": 0,
        "unit": 0,
        "mock": 0,
        "e2e": 0,
        "contract": 0,
        "buildci": 0,
        "na": 0,
        "blocker": 0,
        "critical": 0,
        "categories": {},
        "e2eBreakdown": {
            "auth": [],
            "deployment": [],
            "platform": [],
            "upgrade": [],
            "integration": []
        }
    }

    for bug in bugs:
        # Coverage breakdown
        coverage = bug.get("coverage", "")
        if coverage == "COVERED":
            stats["covered"] += 1
        elif coverage == "PARTIALLY COVERED":
            stats["partialCovered"] += 1
        elif coverage == "GAP":
            stats["gap"] += 1
        elif coverage == "NOT TESTABLE":
            stats["notTestable"] += 1

        # Test level breakdown
        level = bug.get("testLevel", "")
        if level == "Unit":
            stats["unit"] += 1
        elif level == "Mock":
            stats["mock"] += 1
        elif level == "E2E":
            stats["e2e"] += 1
            _categorize_e2e_bug(bug, stats["e2eBreakdown"])
        elif level == "Contract":
            stats["contract"] += 1
        elif level == "Build/CI":
            stats["buildci"] += 1
        elif level == "N/A":
            stats["na"] += 1

        # Priority breakdown
        priority = bug.get("priority", "")
        if priority == "Blocker":
            stats["blocker"] += 1
        elif priority == "Critical":
            stats["critical"] += 1

        # Category breakdown
        for category in bug.get("categories", []):
            stats["categories"][category] = stats["categories"].get(category, 0) + 1

    return stats


def _categorize_e2e_bug(bug: Dict, breakdown: Dict):
    """Categorize E2E bug into subcategories."""
    summary = bug.get("summary", "").lower()
    categories = bug.get("categories", [])

    if "auth" in summary or "rbac" in summary or "permission" in summary:
        breakdown["auth"].append(bug)
    elif "deploy" in summary or "cluster" in summary or "infrastructure" in summary:
        breakdown["deployment"].append(bug)
    elif "upgrade" in categories or "upgrade" in summary:
        breakdown["upgrade"].append(bug)
    elif "platform-specific" in categories or any(p in summary for p in ["arm", "power", "s390x"]):
        breakdown["platform"].append(bug)
    else:
        breakdown["integration"].append(bug)


def _generate_css() -> str:
    """Generate inline CSS styles with dark/light mode toggle."""
    return """<style>
        /* CSS Reset & Base */
        * { margin: 0; padding: 0; box-sizing: border-box; }

        /* CSS Variables for theming */
        :root {
            --bg-primary: #f5f5f5;
            --bg-secondary: #ffffff;
            --bg-tertiary: #f8f9fa;
            --text-primary: #333;
            --text-secondary: #666;
            --border-color: #ddd;
            --border-light: #eee;
            --hover-bg: #f8f9fa;
            --code-bg: #f4f4f4;
            --accent-color: #007bff;
            --accent-hover: #0056b3;
            --shadow: rgba(0,0,0,0.1);
            --th-bg: #007bff;
            --th-hover: #0056b3;
        }

        body.dark-mode {
            --bg-primary: #1a1a1a;
            --bg-secondary: #2a2a2a;
            --bg-tertiary: #333;
            --text-primary: #e0e0e0;
            --text-secondary: #999;
            --border-color: #444;
            --border-light: #555;
            --hover-bg: #3a3a3a;
            --code-bg: #333;
            --accent-color: #4a9eff;
            --accent-hover: #3a8eef;
            --shadow: rgba(0,0,0,0.3);
            --th-bg: #2c5aa0;
            --th-hover: #1e4277;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: var(--text-primary);
            background: var(--bg-primary);
            padding: 20px;
            transition: background 0.3s ease, color 0.3s ease;
        }

        /* Theme toggle button */
        #theme-toggle {
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--accent-color);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 600;
            box-shadow: 0 2px 8px var(--shadow);
            z-index: 1000;
            transition: all 0.3s ease;
        }

        #theme-toggle:hover {
            background: var(--accent-hover);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px var(--shadow);
        }

        #theme-toggle::before {
            content: '🌙 ';
        }

        body.dark-mode #theme-toggle::before {
            content: '☀️ ';
        }

        /* Layout */
        header, section {
            background: var(--bg-secondary);
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px var(--shadow);
            border: 1px solid var(--border-color);
        }

        h1 { font-size: 2rem; margin-bottom: 10px; }
        h2 { font-size: 1.5rem; margin-bottom: 15px; border-bottom: 2px solid var(--accent-color); padding-bottom: 5px; }
        h3 { font-size: 1.2rem; margin: 15px 0 10px; }

        /* Metadata */
        .metadata p { margin: 5px 0; }
        .metadata strong { color: var(--accent-color); }
        .metadata code {
            background: var(--code-bg);
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            color: var(--text-primary);
        }

        /* Dashboard */
        .dashboard { display: grid; grid-template-columns: 1fr; gap: 20px; }
        .charts { display: flex; gap: 20px; flex-wrap: wrap; justify-content: center; }
        .chart { flex: 0 1 auto; min-width: 300px; text-align: center; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-top: 20px; }
        .stat {
            background: var(--bg-tertiary);
            padding: 15px;
            border-radius: 6px;
            text-align: center;
            border-left: 4px solid var(--accent-color);
        }
        .stat .label { display: block; font-size: 0.9em; color: var(--text-secondary); margin-bottom: 5px; }
        .stat .value { display: block; font-size: 2em; font-weight: bold; color: var(--accent-color); }

        /* Filters */
        .filters { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
        .filters h2 { flex: 1 0 100%; }
        .filters input, .filters select {
            padding: 8px 12px;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            font-size: 0.9rem;
            flex: 1;
            min-width: 150px;
            background: var(--bg-secondary);
            color: var(--text-primary);
            transition: all 0.3s ease;
        }
        .filters input { min-width: 250px; }
        .filters input:focus, .filters select:focus {
            outline: none;
            border-color: var(--accent-color);
        }

        /* Table */
        table {
            width: 100%;
            border-collapse: collapse;
            background: var(--bg-secondary);
        }

        th {
            background: var(--th-bg);
            color: white;
            padding: 12px;
            text-align: left;
            cursor: pointer;
            user-select: none;
            position: sticky;
            top: 0;
            z-index: 10;
        }

        th:hover { background: var(--th-hover); }
        th::after { content: ' ↕️'; opacity: 0.5; }
        th.sorted-asc::after { content: ' ↑'; opacity: 1; }
        th.sorted-desc::after { content: ' ↓'; opacity: 1; }

        td {
            padding: 10px 12px;
            border-bottom: 1px solid var(--border-light);
        }

        tr:hover { background: var(--hover-bg); }

        /* Row color coding by coverage - adjusted for dark mode */
        tr[data-coverage="COVERED"] { background-color: #d4edda; }
        tr[data-coverage="PARTIALLY COVERED"] { background-color: #fff3cd; }
        tr[data-coverage="GAP"] { background-color: #f8d7da; }
        tr[data-coverage="NOT TESTABLE"] { background-color: #e2e3e5; }

        body.dark-mode tr[data-coverage="COVERED"] { background-color: #1e4620; color: #90ee90; }
        body.dark-mode tr[data-coverage="PARTIALLY COVERED"] { background-color: #3d3420; color: #ffd700; }
        body.dark-mode tr[data-coverage="GAP"] { background-color: #4a1f1f; color: #ff9999; }
        body.dark-mode tr[data-coverage="NOT TESTABLE"] { background-color: #2a2a2a; color: #aaa; }

        /* Border highlighting for E2E */
        tr[data-level="E2E"] { border-left: 4px solid #ff9800; }

        /* Links */
        a { color: var(--accent-color); text-decoration: none; }
        a:hover { text-decoration: underline; }

        /* Badges */
        .badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
            margin-right: 5px;
        }
        .badge-blocker { background: #dc3545; color: white; }
        .badge-critical { background: #fd7e14; color: white; }
        .badge-unit { background: #28a745; color: white; }
        .badge-mock { background: #17a2b8; color: white; }
        .badge-e2e { background: #ff9800; color: white; }
        .badge-contract { background: #9c27b0; color: white; }
        .badge-buildci { background: #795548; color: white; }
        .badge-na { background: #9e9e9e; color: white; }
        .badge-high { background: #4caf50; color: white; }  /* 80%+ confidence */
        .badge-medium { background: #ff9800; color: white; }  /* 60-80% confidence */
        .badge-low { background: #f44336; color: white; }  /* < 60% confidence */

        /* Test file column */
        .test-file {
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            color: var(--text-secondary);
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        /* Footer */
        footer {
            text-align: center;
            padding: 20px;
            margin-top: 20px;
            background: var(--bg-secondary);
            border-radius: 8px;
        }

        footer button {
            background: var(--accent-color);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 1rem;
            margin-bottom: 10px;
        }

        footer button:hover { background: var(--accent-hover); }

        /* Print styles */
        @media print {
            body { background: white; padding: 0; }
            .filters, footer button, #theme-toggle { display: none; }
            section { box-shadow: none; page-break-inside: avoid; }
            tr { page-break-inside: avoid; }
            th { position: static; }
        }

        /* Responsive */
        @media (max-width: 768px) {
            .dashboard { grid-template-columns: 1fr; }
            .charts { flex-direction: column; }
            .filters { flex-direction: column; }
            .filters input, .filters select { width: 100%; min-width: auto; }
            #theme-toggle { top: 10px; right: 10px; padding: 8px 16px; font-size: 0.85rem; }
        }
    </style>"""


def _generate_header(metadata: Dict) -> str:
    """Generate header section with metadata."""
    timestamp = datetime.fromisoformat(metadata['timestamp'].replace('Z', '+00:00'))
    formatted_time = timestamp.strftime("%Y-%m-%d %H:%M UTC")

    return f"""<header>
        <h1>🐛 Historical Bug Test Coverage Analysis</h1>
        <div class="metadata">
            <p><strong>Component:</strong> {_escape_html(metadata['repoName'])}</p>
            <p><strong>Repository:</strong> <a href="{_escape_html(metadata['repoUrl'])}" target="_blank">{_escape_html(metadata['repoUrl'])}</a></p>
            <p><strong>Generated:</strong> {_escape_html(formatted_time)}</p>
            <p><strong>JQL:</strong> <code>{_escape_html(metadata['jql'])}</code></p>
            <p><strong>Total Bugs Analyzed:</strong> {_escape_html(str(metadata['totalCount']))}</p>
        </div>
    </header>"""


def _generate_dashboard(stats: Dict) -> str:
    """Generate summary dashboard with charts."""
    return f"""<section class="dashboard">
        <h2>Summary Dashboard</h2>
        <div class="charts">
            <div class="chart">
                <h3>Test Level Distribution</h3>
                <svg id="test-level-chart" width="300" height="400"></svg>
            </div>
            <div class="chart">
                <h3>Coverage Status</h3>
                <svg id="coverage-chart" width="300" height="400"></svg>
            </div>
        </div>
        <div class="stats">
            <div class="stat">
                <span class="label">Total Bugs</span>
                <span class="value">{stats['total']}</span>
            </div>
            <div class="stat">
                <span class="label">Already Covered</span>
                <span class="value">{stats['covered']}</span>
            </div>
            <div class="stat">
                <span class="label">True Gaps</span>
                <span class="value">{stats['gap']}</span>
            </div>
            <div class="stat">
                <span class="label">E2E Needed</span>
                <span class="value">{stats['e2e']}</span>
            </div>
            <div class="stat">
                <span class="label">Blocker/Critical</span>
                <span class="value">{stats['blocker'] + stats['critical']}</span>
            </div>
        </div>
    </section>"""


def _generate_filters() -> str:
    """Generate filter controls."""
    return """<section class="filters">
        <h2>🔍 Filters</h2>
        <input type="text" id="search" placeholder="Search across all columns...">
        <select id="filter-priority">
            <option value="">All Priorities</option>
            <option value="Blocker">Blocker</option>
            <option value="Critical">Critical</option>
            <option value="Major">Major</option>
        </select>
        <select id="filter-coverage">
            <option value="">All Coverage</option>
            <option value="COVERED">Covered</option>
            <option value="PARTIALLY COVERED">Partially Covered</option>
            <option value="GAP">Gap</option>
            <option value="NOT TESTABLE">Not Testable</option>
        </select>
        <select id="filter-level">
            <option value="">All Test Levels</option>
            <option value="Unit">Unit</option>
            <option value="Mock">Mock/Integration</option>
            <option value="E2E">E2E</option>
            <option value="N/A">N/A</option>
        </select>
        <select id="filter-category">
            <option value="">All Categories</option>
            <option value="functional">Functional</option>
            <option value="upgrade">Upgrade</option>
            <option value="platform-specific">Platform-Specific</option>
            <option value="fips">FIPS</option>
            <option value="disconnected">Disconnected</option>
            <option value="performance">Performance</option>
            <option value="security">Security</option>
        </select>
    </section>"""


def _generate_bug_table() -> str:
    """Generate bug analysis table (populated by JavaScript)."""
    return """<section class="bug-table">
        <h2>📊 Bug Analysis Table</h2>
        <table id="bugs">
            <thead>
                <tr>
                    <th data-sort="key">Key</th>
                    <th data-sort="priority">Priority</th>
                    <th data-sort="summary">Summary</th>
                    <th data-sort="coverage">Coverage</th>
                    <th data-sort="testFile">Test File</th>
                    <th data-sort="confidence">Confidence</th>
                    <th data-sort="testLevel">Test Level</th>
                    <th data-sort="categories">Categories</th>
                    <th data-sort="details">Details</th>
                </tr>
            </thead>
            <tbody>
                <!-- Populated by JavaScript -->
            </tbody>
        </table>
    </section>"""


def _generate_e2e_breakdown(stats: Dict) -> str:
    """Generate E2E test breakdown section."""
    e2e = stats["e2eBreakdown"]

    rows = ""
    for category, bugs in e2e.items():
        if bugs:
            examples = ", ".join([b["key"] for b in bugs[:3]])
            if len(bugs) > 3:
                examples += f", ... +{len(bugs) - 3} more"
            rows += f"""<tr>
                <td>{category.replace('_', ' ').title()}</td>
                <td>{len(bugs)}</td>
                <td>{examples}</td>
            </tr>"""

    if not rows:
        rows = '<tr><td colspan="3">No E2E bugs identified</td></tr>'

    return f"""<section class="e2e-breakdown">
        <h2>🚀 E2E Test Breakdown</h2>
        <table>
            <thead>
                <tr>
                    <th>Category</th>
                    <th>Count</th>
                    <th>Examples</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    </section>"""


def _generate_recommendations(bugs: List[Dict], stats: Dict) -> str:
    """Generate recommendations section."""
    # Find critical gaps (Blocker/Critical with GAP coverage)
    critical_gaps = [
        b for b in bugs
        if b.get("priority") in ["Blocker", "Critical"] and b.get("coverage") == "GAP"
    ]

    critical_gap_items = ""
    for bug in critical_gaps[:10]:  # Top 10
        critical_gap_items += f'<li><a href="{_escape_html(bug["jiraUrl"])}" target="_blank">{_escape_html(bug["key"])}</a>: {_escape_html(bug["summary"])} (Recommend: {_escape_html(bug["testLevel"])} test)</li>\n'

    if not critical_gap_items:
        critical_gap_items = "<li>✅ No critical gaps found! All blocker/critical bugs have test coverage.</li>"

    # Category gaps
    category_stats = stats["categories"]
    category_items = ""
    for category, count in category_stats.items():
        if category != "functional":
            gap_count = len([b for b in bugs if category in b.get("categories", []) and b.get("coverage") == "GAP"])
            if gap_count > 0:
                category_items += f"<li><strong>{_escape_html(category.title())}:</strong> {gap_count} of {count} bugs lack coverage</li>\n"

    if not category_items:
        category_items = "<li>✅ Good coverage across all non-functional categories</li>"

    return f"""<section class="recommendations">
        <h2>💡 Recommendations</h2>

        <h3>Critical Gaps (Blocker/Critical with no coverage)</h3>
        <ul>
            {critical_gap_items}
        </ul>

        <h3>Non-Functional Coverage Gaps</h3>
        <ul>
            {category_items}
        </ul>

        <h3>Test Creation Guidance</h3>
        <p>✅ Use existing test rules: <code>.claude/rules/</code></p>
        <p>⚙️ Or generate new rules: <code>/test-rules-generator {_escape_html(bugs[0].get('jiraUrl', '').split('/browse/')[0].replace('/rest/api/3', '')) if bugs else 'JIRA_SERVER'}</code></p>
        <p>📚 Follow the test pyramid: Unit &gt; Mock &gt; E2E</p>
    </section>"""


def _generate_footer() -> str:
    """Generate footer section."""
    return """<footer>
        <button onclick="window.print()">📥 Export to PDF</button>
        <p>Generated by <strong>Quality Tiger Team</strong> - Historical Bug Coverage Analysis</p>
        <p style="font-size: 0.9em; color: #666; margin-top: 10px;">
            This report is self-contained and can be shared directly. All data is embedded inline.
        </p>
    </footer>"""


def _generate_javascript(bugs: List[Dict], metadata: Dict, stats: Dict) -> str:
    """Generate inline JavaScript for interactivity."""
    bugs_json = _safe_json_embed(bugs)
    stats_json = _safe_json_embed(stats)
    metadata_json = _safe_json_embed(metadata)

    return f"""<script>
        // Embedded data (XSS-safe)
        const DATA = {{
            bugs: {bugs_json},
            metadata: {metadata_json},
            stats: {stats_json}
        }};

        // Chart rendering
        function createDonutChart(data, elementId) {{
            const svg = document.getElementById(elementId);
            const centerX = 150;
            const centerY = 150;
            const radius = 100;
            const innerRadius = 60;

            let currentAngle = -90;
            const total = data.reduce((sum, d) => sum + d.value, 0);

            data.forEach((item, i) => {{
                if (item.value === 0) return;

                const angle = (item.value / total) * 360;
                const startAngle = currentAngle * Math.PI / 180;
                const endAngle = (currentAngle + angle) * Math.PI / 180;

                const x1 = centerX + radius * Math.cos(startAngle);
                const y1 = centerY + radius * Math.sin(startAngle);
                const x2 = centerX + radius * Math.cos(endAngle);
                const y2 = centerY + radius * Math.sin(endAngle);
                const x3 = centerX + innerRadius * Math.cos(endAngle);
                const y3 = centerY + innerRadius * Math.sin(endAngle);
                const x4 = centerX + innerRadius * Math.cos(startAngle);
                const y4 = centerY + innerRadius * Math.sin(startAngle);

                const largeArcFlag = angle > 180 ? 1 : 0;

                const pathData = [
                    `M ${{x1}} ${{y1}}`,
                    `A ${{radius}} ${{radius}} 0 ${{largeArcFlag}} 1 ${{x2}} ${{y2}}`,
                    `L ${{x3}} ${{y3}}`,
                    `A ${{innerRadius}} ${{innerRadius}} 0 ${{largeArcFlag}} 0 ${{x4}} ${{y4}}`,
                    'Z'
                ].join(' ');

                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('d', pathData);
                path.setAttribute('fill', item.color);
                path.setAttribute('stroke', 'white');
                path.setAttribute('stroke-width', '2');

                const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
                title.textContent = `${{item.label}}: ${{item.value}} (${{Math.round(item.value / total * 100)}}%)`;
                path.appendChild(title);

                svg.appendChild(path);
                currentAngle += angle;
            }});

            // Create legend below chart instead of labels on the chart
            const legendY = 310;
            const legendX = 30;
            const lineHeight = 20;

            data.forEach((item, i) => {{
                if (item.value === 0) return;

                const y = legendY + (i * lineHeight);

                // Color box
                const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                rect.setAttribute('x', legendX);
                rect.setAttribute('y', y - 12);
                rect.setAttribute('width', '15');
                rect.setAttribute('height', '15');
                rect.setAttribute('fill', item.color);
                svg.appendChild(rect);

                // Label text
                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('x', legendX + 20);
                text.setAttribute('y', y);
                text.setAttribute('font-size', '14');
                text.setAttribute('fill', 'var(--text-primary)');
                const percentage = Math.round(item.value / total * 100);
                text.textContent = `${{item.label}}: ${{item.value}} (${{percentage}}%)`;
                svg.appendChild(text);
            }});
        }}

        // Render charts
        function renderCharts() {{
            const testLevelData = [
                {{ label: 'Unit', value: DATA.stats.unit, color: '#28a745' }},
                {{ label: 'Mock', value: DATA.stats.mock, color: '#17a2b8' }},
                {{ label: 'E2E', value: DATA.stats.e2e, color: '#ff9800' }},
                {{ label: 'Contract', value: DATA.stats.contract, color: '#9c27b0' }},
                {{ label: 'Build/CI', value: DATA.stats.buildci, color: '#795548' }},
                {{ label: 'N/A', value: DATA.stats.na, color: '#9e9e9e' }}
            ];

            const coverageData = [
                {{ label: 'Covered', value: DATA.stats.covered, color: '#28a745' }},
                {{ label: 'Partial', value: DATA.stats.partialCovered, color: '#ffc107' }},
                {{ label: 'Gap', value: DATA.stats.gap, color: '#dc3545' }},
                {{ label: 'Not Testable', value: DATA.stats.notTestable, color: '#6c757d' }}
            ];

            createDonutChart(testLevelData, 'test-level-chart');
            createDonutChart(coverageData, 'coverage-chart');
        }}

        // Table rendering
        function renderTable() {{
            const tbody = document.querySelector('#bugs tbody');
            tbody.innerHTML = '';

            DATA.bugs.forEach(bug => {{
                const row = document.createElement('tr');
                row.dataset.key = bug.key;
                row.dataset.priority = bug.priority;
                row.dataset.summary = bug.summary;
                row.dataset.coverage = bug.coverage;
                row.dataset.testLevel = bug.testLevel;
                row.dataset.categories = bug.categories.join(',');
                row.dataset.details = bug.details;

                const priorityBadge = bug.priority === 'Blocker' ? 'badge-blocker' :
                                      bug.priority === 'Critical' ? 'badge-critical' : '';
                const levelBadge = bug.testLevel === 'Unit' ? 'badge-unit' :
                                   bug.testLevel === 'Mock' ? 'badge-mock' :
                                   bug.testLevel === 'E2E' ? 'badge-e2e' :
                                   bug.testLevel === 'Contract' ? 'badge-contract' :
                                   bug.testLevel === 'Build/CI' ? 'badge-buildci' : 'badge-na';

                // Distinguish E2E upstream vs downstream
                let testLevelDisplay = bug.testLevel;
                if (bug.testLevel === 'E2E' && bug.testFile) {{
                    if (bug.testFile.includes('opendatahub-tests') || bug.testFile.includes('e2e-tests')) {{
                        testLevelDisplay = 'E2E (Downstream)';
                    }} else {{
                        testLevelDisplay = 'E2E (Upstream)';
                    }}
                }}

                // Confidence badge color
                const confidenceBadge = bug.confidence >= 80 ? 'badge-high' :
                                       bug.confidence >= 60 ? 'badge-medium' :
                                       bug.confidence > 0 ? 'badge-low' : '';

                // Escape HTML to prevent XSS
                const escapeHtml = (text) => {{
                    const div = document.createElement('div');
                    div.textContent = text || '';
                    return div.innerHTML;
                }};

                row.innerHTML = `
                    <td><a href="${{escapeHtml(bug.jiraUrl)}}" target="_blank">${{escapeHtml(bug.key)}}</a></td>
                    <td><span class="badge ${{priorityBadge}}">${{escapeHtml(bug.priority)}}</span></td>
                    <td>${{escapeHtml(bug.summary)}}</td>
                    <td>${{escapeHtml(bug.coverage)}}</td>
                    <td class="test-file">${{escapeHtml(bug.testFile || 'N/A')}}</td>
                    <td>${{bug.confidence > 0 ? '<span class="badge ' + confidenceBadge + '">' + bug.confidence + '%</span>' : 'N/A'}}</td>
                    <td><span class="badge ${{levelBadge}}">${{escapeHtml(testLevelDisplay)}}</span></td>
                    <td>${{bug.categories.map(c => escapeHtml(c)).join(', ')}}</td>
                    <td>${{escapeHtml(bug.details)}}</td>
                `;

                tbody.appendChild(row);
            }});
        }}

        // Sorting
        let sortColumn = null;
        let sortDirection = 'asc';

        function sortTable(column) {{
            const tbody = document.querySelector('#bugs tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));

            if (sortColumn === column) {{
                sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
            }} else {{
                sortColumn = column;
                sortDirection = 'asc';
            }}

            rows.sort((a, b) => {{
                const aVal = a.dataset[column] || '';
                const bVal = b.dataset[column] || '';
                return sortDirection === 'asc' ?
                    aVal.localeCompare(bVal) :
                    bVal.localeCompare(aVal);
            }});

            rows.forEach(row => tbody.appendChild(row));

            // Update header
            document.querySelectorAll('th').forEach(th => {{
                th.classList.remove('sorted-asc', 'sorted-desc');
            }});
            const header = document.querySelector(`th[data-sort="${{column}}"]`);
            header.classList.add(`sorted-${{sortDirection}}`);
        }}

        // Filtering
        function filterTable() {{
            const searchTerm = document.getElementById('search').value.toLowerCase();
            const priorityFilter = document.getElementById('filter-priority').value;
            const coverageFilter = document.getElementById('filter-coverage').value;
            const levelFilter = document.getElementById('filter-level').value;
            const categoryFilter = document.getElementById('filter-category').value;

            const rows = document.querySelectorAll('#bugs tbody tr');
            let visibleCount = 0;

            rows.forEach(row => {{
                const matchesSearch = !searchTerm ||
                    Object.values(row.dataset).some(val => val.toLowerCase().includes(searchTerm));
                const matchesPriority = !priorityFilter || row.dataset.priority === priorityFilter;
                const matchesCoverage = !coverageFilter || row.dataset.coverage === coverageFilter;
                const matchesLevel = !levelFilter || row.dataset.testLevel === levelFilter;
                const matchesCategory = !categoryFilter ||
                    row.dataset.categories.split(',').includes(categoryFilter);

                const visible = matchesSearch && matchesPriority && matchesCoverage &&
                                matchesLevel && matchesCategory;
                row.style.display = visible ? '' : 'none';
                if (visible) visibleCount++;
            }});

            console.log(`Showing ${{visibleCount}} of ${{DATA.bugs.length}} bugs`);
        }}

        // Event listeners
        function attachEventListeners() {{
            // Sorting
            document.querySelectorAll('th[data-sort]').forEach(th => {{
                th.addEventListener('click', () => sortTable(th.dataset.sort));
            }});

            // Filtering
            document.getElementById('search').addEventListener('input', filterTable);
            document.getElementById('filter-priority').addEventListener('change', filterTable);
            document.getElementById('filter-coverage').addEventListener('change', filterTable);
            document.getElementById('filter-level').addEventListener('change', filterTable);
            document.getElementById('filter-category').addEventListener('change', filterTable);
        }}

        // Theme toggle functionality
        function initThemeToggle() {{
            const toggleBtn = document.getElementById('theme-toggle');
            const body = document.body;

            // Check for saved theme preference or default to light mode
            const savedTheme = localStorage.getItem('theme') || 'light';
            if (savedTheme === 'dark') {{
                body.classList.add('dark-mode');
                toggleBtn.textContent = 'Light Mode';
            }} else {{
                toggleBtn.textContent = 'Dark Mode';
            }}

            // Toggle theme on button click
            toggleBtn.addEventListener('click', () => {{
                body.classList.toggle('dark-mode');
                const isDark = body.classList.contains('dark-mode');
                toggleBtn.textContent = isDark ? 'Light Mode' : 'Dark Mode';
                localStorage.setItem('theme', isDark ? 'dark' : 'light');
            }});
        }}

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {{
            initThemeToggle();
            renderCharts();
            renderTable();
            attachEventListeners();
            console.log('Bug Coverage Report initialized');
            console.log(`Total bugs: ${{DATA.bugs.length}}`);
        }});
    </script>"""
