#!/usr/bin/env python3
"""
HTML Report Generator for Quality Repository Analysis

Converts markdown analysis output to an interactive HTML page with embedded CSS/JS.
"""

import re
import sys
from datetime import datetime
from html import escape
from typing import Any, Dict, List, Tuple


def extract_executive_summary(content: str) -> Dict[str, Any]:
    """Extract executive summary section"""
    match = re.search(r'## Executive Summary\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
    if not match:
        return {}

    summary_text = match.group(1)
    summary = {}

    # Extract overall score
    score_match = re.search(r'Overall Score:\s*(\d+(?:\.\d+)?)/10', summary_text)
    if score_match:
        summary['overall_score'] = float(score_match.group(1))

    # Extract key strengths
    strengths_match = re.search(r'Key Strengths:\s*(.+?)(?=\n-|\n\n|\Z)', summary_text, re.DOTALL)
    if strengths_match:
        summary['strengths'] = strengths_match.group(1).strip()

    # Extract critical gaps
    gaps_match = re.search(r'Critical Gaps:\s*(.+?)(?=\n-|\n\n|\Z)', summary_text, re.DOTALL)
    if gaps_match:
        summary['gaps'] = gaps_match.group(1).strip()

    return summary


def extract_scorecard(content: str) -> List[Dict[str, str]]:
    """Extract quality scorecard table"""
    # First extract only the Quality Scorecard section (up to next ## heading)
    section_match = re.search(r'## Quality Scorecard\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
    if not section_match:
        return []

    # Then find the pipe table within that bounded section
    section_text = section_match.group(1)
    table_match = re.search(r'((?:\|.*\n)+)', section_text)
    if not table_match:
        return []

    table_text = table_match.group(1)
    lines = [line.strip() for line in table_text.split('\n') if line.strip() and not line.strip().startswith('|---')]

    scorecard = []
    for line in lines[1:]:  # Skip header
        cells = [cell.strip() for cell in line.split('|')[1:-1]]  # Remove empty first/last
        if len(cells) >= 3:
            score_match = re.search(r'(\d+(?:\.\d+)?)/10', cells[1])
            score = float(score_match.group(1)) if score_match else 0
            # Remove markdown bold (**text**)
            dimension = re.sub(r'\*\*(.+?)\*\*', r'\1', cells[0])
            scorecard.append({
                'dimension': dimension,
                'score': score,
                'status': cells[2]
            })

    return scorecard


def extract_sections(content: str, section_title: str) -> List[Dict[str, str]]:
    """Extract list items from a section"""
    pattern = rf'## {re.escape(section_title)}\n(.*?)(?=\n##|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return []

    section_text = match.group(1)
    items = []

    # Match numbered list items
    item_pattern = r'^\d+\.\s+(.+?)(?=\n\d+\.|\Z)'
    for item_match in re.finditer(item_pattern, section_text, re.MULTILINE | re.DOTALL):
        item_text = item_match.group(1).strip()

        # Parse sub-items
        impact_match = re.search(r'Impact:\s*(.+?)(?=\n\s*-|\Z)', item_text, re.DOTALL)
        severity_match = re.search(r'Severity:\s*(HIGH|MEDIUM|LOW)', item_text)
        effort_match = re.search(r'Effort:\s*(.+?)(?=\n\s*-|\Z)', item_text, re.DOTALL)

        # Get main description (first line)
        main_desc = item_text.split('\n')[0].strip()

        items.append({
            'description': main_desc,
            'impact': impact_match.group(1).strip() if impact_match else '',
            'severity': severity_match.group(1) if severity_match else '',
            'effort': effort_match.group(1).strip() if effort_match else ''
        })

    return items


def extract_recommendations(content: str) -> Dict[str, List[str]]:
    """Extract recommendations by priority"""
    recommendations = {'P0': [], 'P1': [], 'P2': []}

    for priority in ['Priority 0 (Critical)', 'Priority 1 (High Value)', 'Priority 2 (Nice-to-Have)']:
        pattern = rf'### {re.escape(priority)}\n(.*?)(?=\n###|\n##|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            items = [line.strip('- ').strip() for line in match.group(1).split('\n') if line.strip().startswith('-')]
            key = 'P0' if 'Priority 0' in priority else 'P1' if 'Priority 1' in priority else 'P2'
            recommendations[key] = items

    return recommendations


def generate_html(markdown_content: str, repo_name: str = "Repository") -> str:
    """Generate complete HTML report"""

    # Extract data from markdown
    summary = extract_executive_summary(markdown_content)
    scorecard = extract_scorecard(markdown_content)
    critical_gaps = extract_sections(markdown_content, 'Critical Gaps')
    quick_wins = extract_sections(markdown_content, 'Quick Wins')
    recommendations = extract_recommendations(markdown_content)

    # Use overall score from summary, fall back to scorecard average if not available
    avg_score = summary.get('overall_score', 0)
    if avg_score == 0 and scorecard:
        avg_score = sum(item['score'] for item in scorecard) / len(scorecard)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quality Analysis: {repo_name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 2rem;
            color: #333;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }}

        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            text-align: center;
        }}

        header h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            font-weight: 700;
        }}

        header .timestamp {{
            opacity: 0.9;
            font-size: 0.9rem;
        }}

        .content {{
            padding: 2rem;
        }}

        .score-overview {{
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 2rem;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            border-radius: 12px;
            margin-bottom: 2rem;
        }}

        .score-circle {{
            position: relative;
            width: 200px;
            height: 200px;
        }}

        .score-circle svg {{
            transform: rotate(-90deg);
        }}

        .score-circle circle {{
            fill: none;
            stroke-width: 12;
        }}

        .score-circle .bg-circle {{
            stroke: #e0e0e0;
        }}

        .score-circle .score-arc {{
            stroke-linecap: round;
            transition: stroke-dashoffset 1s ease;
        }}

        .score-text {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
        }}

        .score-value {{
            font-size: 3rem;
            font-weight: 700;
            color: #333;
        }}

        .score-label {{
            font-size: 0.9rem;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .section {{
            margin-bottom: 2rem;
        }}

        .section-title {{
            font-size: 1.75rem;
            margin-bottom: 1rem;
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 0.5rem;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .section-title:hover {{
            color: #764ba2;
        }}

        .toggle-icon {{
            font-size: 1.2rem;
            transition: transform 0.3s ease;
        }}

        .section-content {{
            padding-top: 1rem;
        }}

        .section-content.collapsed {{
            display: none;
        }}

        .scorecard {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin-bottom: 1rem;
        }}

        .scorecard-item {{
            background: white;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            padding: 1.5rem;
            transition: all 0.3s ease;
        }}

        .scorecard-item:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
            border-color: #667eea;
        }}

        .scorecard-item h3 {{
            font-size: 1rem;
            margin-bottom: 0.5rem;
            color: #666;
            font-weight: 600;
        }}

        .scorecard-score {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}

        .scorecard-status {{
            font-size: 0.9rem;
            color: #666;
        }}

        .items-list {{
            list-style: none;
        }}

        .item-card {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 4px;
            transition: all 0.3s ease;
        }}

        .item-card:hover {{
            background: #e9ecef;
            border-left-width: 6px;
        }}

        .item-card.high {{
            border-left-color: #dc3545;
        }}

        .item-card.medium {{
            border-left-color: #ffc107;
        }}

        .item-card.low {{
            border-left-color: #28a745;
        }}

        .item-description {{
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #333;
        }}

        .item-meta {{
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            margin-top: 0.5rem;
        }}

        .meta-tag {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 600;
        }}

        .severity-high {{
            background: #dc3545;
            color: white;
        }}

        .severity-medium {{
            background: #ffc107;
            color: #333;
        }}

        .severity-low {{
            background: #28a745;
            color: white;
        }}

        .effort-tag {{
            background: #667eea;
            color: white;
        }}

        .recommendations {{
            display: grid;
            gap: 1rem;
        }}

        .rec-priority {{
            background: white;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            padding: 1.5rem;
        }}

        .rec-priority h3 {{
            margin-bottom: 1rem;
            font-size: 1.3rem;
        }}

        .rec-priority.p0 {{
            border-color: #dc3545;
        }}

        .rec-priority.p0 h3 {{
            color: #dc3545;
        }}

        .rec-priority.p1 {{
            border-color: #ffc107;
        }}

        .rec-priority.p1 h3 {{
            color: #f57c00;
        }}

        .rec-priority.p2 {{
            border-color: #28a745;
        }}

        .rec-priority.p2 h3 {{
            color: #28a745;
        }}

        .rec-priority ul {{
            list-style: none;
        }}

        .rec-priority li {{
            padding: 0.5rem 0;
            border-bottom: 1px solid #f0f0f0;
        }}

        .rec-priority li:last-child {{
            border-bottom: none;
        }}

        .rec-priority li:before {{
            content: "→ ";
            font-weight: 700;
            margin-right: 0.5rem;
        }}

        @media (max-width: 768px) {{
            body {{
                padding: 1rem;
            }}

            .content {{
                padding: 1rem;
            }}

            header h1 {{
                font-size: 1.75rem;
            }}

            .scorecard {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Quality Analysis Report</h1>
            <p class="timestamp">Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
            <h2 style="margin-top: 1rem; font-weight: 400;">{escape(repo_name)}</h2>
        </header>

        <div class="content">
            <div class="score-overview">
                <div class="score-circle">
                    <svg width="200" height="200">
                        <circle class="bg-circle" cx="100" cy="100" r="90"></circle>
                        <circle class="score-arc" cx="100" cy="100" r="90"
                                stroke="{get_score_color(avg_score)}"
                                stroke-dasharray="{2 * 3.14159 * 90}"
                                stroke-dashoffset="{2 * 3.14159 * 90 * (1 - avg_score / 10)}"
                                id="scoreArc"></circle>
                    </svg>
                    <div class="score-text">
                        <div class="score-value">{avg_score:.1f}</div>
                        <div class="score-label">Overall Score</div>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2 class="section-title" onclick="toggleSection(this)">
                    Quality Scorecard
                    <span class="toggle-icon">▼</span>
                </h2>
                <div class="section-content">
                    <div class="scorecard">
                        {generate_scorecard_items(scorecard)}
                    </div>
                </div>
            </div>

            {generate_section('Critical Gaps', critical_gaps)}

            {generate_section('Quick Wins', quick_wins)}

            <div class="section">
                <h2 class="section-title" onclick="toggleSection(this)">
                    Recommendations
                    <span class="toggle-icon">▼</span>
                </h2>
                <div class="section-content">
                    <div class="recommendations">
                        {generate_recommendations_section(recommendations)}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function toggleSection(element) {{
            const content = element.nextElementSibling;
            const icon = element.querySelector('.toggle-icon');

            content.classList.toggle('collapsed');
            icon.style.transform = content.classList.contains('collapsed') ? 'rotate(-90deg)' : 'rotate(0deg)';
        }}

        // Animate score circle on load
        window.addEventListener('load', function() {{
            const scoreArc = document.getElementById('scoreArc');
            const targetOffset = scoreArc.getAttribute('stroke-dashoffset');
            const fullCircle = 2 * Math.PI * 90;

            scoreArc.style.strokeDashoffset = fullCircle;

            setTimeout(() => {{
                scoreArc.style.strokeDashoffset = targetOffset;
            }}, 100);
        }});
    </script>
</body>
</html>"""

    return html


def generate_scorecard_items(scorecard: List[Dict[str, str]]) -> str:
    """Generate HTML for scorecard items"""
    items_html = []
    for item in scorecard:
        color = get_score_color(item['score'])
        items_html.append(f"""
                        <div class="scorecard-item">
                            <h3>{escape(item['dimension'])}</h3>
                            <div class="scorecard-score" style="color: {color};">{item['score']:.1f}/10</div>
                            <div class="scorecard-status">{escape(item['status'])}</div>
                        </div>""")
    return ''.join(items_html)


def generate_section(title: str, items: List[Dict[str, str]]) -> str:
    """Generate HTML for a section with items"""
    if not items:
        return ""

    items_html = []
    for item in items:
        severity_class = item['severity'].lower() if item['severity'] else ''
        items_html.append(f"""
                        <li class="item-card {severity_class}">
                            <div class="item-description">{escape(item['description'])}</div>
                            {f'<p>{escape(item["impact"])}</p>' if item['impact'] else ''}
                            <div class="item-meta">
                                {f'<span class="meta-tag severity-{severity_class}">{escape(item["severity"])}</span>' if item['severity'] else ''}
                                {f'<span class="meta-tag effort-tag">{escape(item["effort"])}</span>' if item['effort'] else ''}
                            </div>
                        </li>""")

    return f"""
            <div class="section">
                <h2 class="section-title" onclick="toggleSection(this)">
                    {escape(title)}
                    <span class="toggle-icon">▼</span>
                </h2>
                <div class="section-content">
                    <ul class="items-list">
                        {''.join(items_html)}
                    </ul>
                </div>
            </div>"""


def generate_recommendations_section(recommendations: Dict[str, List[str]]) -> str:
    """Generate HTML for recommendations"""
    sections = []

    priorities = [
        ('P0', 'Priority 0: Critical', 'p0'),
        ('P1', 'Priority 1: High Value', 'p1'),
        ('P2', 'Priority 2: Nice-to-Have', 'p2')
    ]

    for key, title, css_class in priorities:
        if recommendations.get(key):
            items = ''.join(f'<li>{escape(item)}</li>' for item in recommendations[key])
            sections.append(f"""
                        <div class="rec-priority {css_class}">
                            <h3>{escape(title)}</h3>
                            <ul>{items}</ul>
                        </div>""")

    return ''.join(sections)


def get_score_color(score: float) -> str:
    """Get color based on score"""
    if score >= 8:
        return '#28a745'
    elif score >= 6:
        return '#ffc107'
    elif score >= 4:
        return '#fd7e14'
    else:
        return '#dc3545'


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python html_generator.py <markdown_file> [output_html]")
        sys.exit(1)

    markdown_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'quality_report.html'

    # Read markdown content
    with open(markdown_file, 'r') as f:
        markdown_content = f.read()

    # Extract repo name from markdown title
    title_match = re.search(r'# Quality Analysis:\s*(.+)', markdown_content)
    repo_name = title_match.group(1) if title_match else "Repository"

    # Generate HTML
    html_content = generate_html(markdown_content, repo_name)

    # Write output
    with open(output_file, 'w') as f:
        f.write(html_content)

    print(f"HTML report generated: {output_file}")


if __name__ == '__main__':
    main()
