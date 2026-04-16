#!/usr/bin/env python3
"""
Quality Analysis Report Aggregator

This script aggregates quality analysis reports from multiple repositories
and generates combined reports with statistics and comparisons.

Usage:
    # Process existing reports from a directory
    python aggregate_quality_reports.py --reports-dir ./quality_reports

    # Generate analysis commands for all repos from architecture-context
    python aggregate_quality_reports.py --generate-commands

    # Process reports and generate HTML
    python aggregate_quality_reports.py --reports-dir ./quality_reports --output-html combined.html
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import subprocess
import sys


@dataclass
class QualityScore:
    """Quality score for a specific dimension"""
    dimension: str
    score: float
    status: str
    notes: str = ""


@dataclass
class RepositoryQuality:
    """Complete quality analysis for a repository"""
    name: str
    url: str
    org: str
    source_type: str  # upstream, downstream, external
    overall_score: float
    scores: List[QualityScore]
    critical_gaps: List[str]
    quick_wins: List[str]
    recommendations: Dict[str, List[str]]
    analyzed_date: Optional[str] = None
    report_file: Optional[str] = None


class QualityReportParser:
    """Parser for markdown quality analysis reports"""

    def __init__(self):
        self.score_pattern = re.compile(r'\|\s*(.+?)\s*\|\s*(\d+(?:\.\d+)?)/10\s*\|\s*(.+?)\s*\|')
        self.overall_score_pattern = re.compile(r'Overall Score:\s*(\d+(?:\.\d+)?)/10')

    def parse_report(self, report_path: Path, repo_name: str, repo_url: str,
                     org: str, source_type: str) -> Optional[RepositoryQuality]:
        """Parse a markdown quality report"""
        try:
            content = report_path.read_text()

            # Extract overall score
            overall_match = self.overall_score_pattern.search(content)
            overall_score = float(overall_match.group(1)) if overall_match else 0.0

            # Extract dimension scores
            scores = []
            for match in self.score_pattern.finditer(content):
                dimension = match.group(1).strip()
                score = float(match.group(2))
                status = match.group(3).strip()
                scores.append(QualityScore(dimension, score, status))

            # Extract critical gaps
            critical_gaps = self._extract_section(content, "## Critical Gaps")

            # Extract quick wins
            quick_wins = self._extract_section(content, "## Quick Wins")

            # Extract recommendations by priority
            recommendations = {
                'P0': self._extract_section(content, "### Priority 0"),
                'P1': self._extract_section(content, "### Priority 1"),
                'P2': self._extract_section(content, "### Priority 2"),
            }

            return RepositoryQuality(
                name=repo_name,
                url=repo_url,
                org=org,
                source_type=source_type,
                overall_score=overall_score,
                scores=scores,
                critical_gaps=critical_gaps,
                quick_wins=quick_wins,
                recommendations=recommendations,
                analyzed_date=datetime.now().isoformat(),
                report_file=str(report_path)
            )

        except Exception as e:
            print(f"Error parsing report {report_path}: {e}")
            return None

    def _extract_section(self, content: str, header: str) -> List[str]:
        """Extract bulleted items from a markdown section"""
        items = []
        in_section = False
        lines = content.split('\n')

        for line in lines:
            if line.startswith(header):
                in_section = True
                continue
            if in_section:
                if line.startswith('##') or line.startswith('###'):
                    if not line.startswith(header):
                        break
                # Match numbered lists (1., 2., etc.) or bullet points (-, *, +)
                if re.match(r'^\d+\.|\s*[-*+]\s+', line):
                    items.append(line.strip())

        return items


class ArchitectureContextLoader:
    """Loads repository information from architecture-context directory"""

    def __init__(self, arch_context_dir: Path):
        self.arch_context_dir = arch_context_dir

    def get_repositories(self) -> List[Dict[str, str]]:
        """Extract repository information from architecture context files"""
        repos = []

        # Use 'newest' symlink to get latest version, fall back to sorting if not available
        newest_link = self.arch_context_dir / "architecture" / "newest"
        if newest_link.exists():
            latest_version = newest_link.resolve()
            print(f"Loading repositories from {latest_version.name} (via 'newest' link)")
        else:
            # Fallback: Find latest RHOAI version directory by sorting
            version_dirs = sorted(
                [d for d in (self.arch_context_dir / "architecture").glob("rhoai-*") if d.is_dir()],
                reverse=True
            )
            if not version_dirs:
                print(f"Warning: No RHOAI version directories found in {self.arch_context_dir}/architecture")
                return []
            latest_version = version_dirs[0]
            print(f"Loading repositories from {latest_version.name}")

        # Read component markdown files
        for md_file in latest_version.glob("*.md"):
            if md_file.name in ['PLATFORM.md', 'README.md']:
                continue

            content = md_file.read_text()
            repo_info = self._extract_repo_info(content, md_file.stem)

            if repo_info:
                repos.append(repo_info)

        return repos

    def _extract_repo_info(self, content: str, component_name: str) -> Optional[Dict[str, str]]:
        """Extract repository information from component markdown"""
        # Look for GitHub URL
        github_patterns = [
            r'https://github\.com/([^/\s]+)/([^/\s\)]+)',
            r'\*\*Repository\*\*:\s*https://github\.com/([^/\s]+)/([^/\s\)]+)',
            r'Source:\s*https://github\.com/([^/\s]+)/([^/\s\)]+)',
        ]

        for pattern in github_patterns:
            match = re.search(pattern, content)
            if match:
                org = match.group(1)
                repo = match.group(2).rstrip('.,;)').replace('.git', '')

                # Determine source type
                if org == 'opendatahub-io':
                    source_type = 'upstream'
                elif org == 'red-hat-data-services':
                    source_type = 'downstream'
                else:
                    source_type = 'external'

                return {
                    'name': repo,
                    'url': f"https://github.com/{org}/{repo}",
                    'org': org,
                    'source_type': source_type,
                    'component': component_name
                }

        return None


class QualityReportAggregator:
    """Aggregates quality reports across multiple repositories"""

    def __init__(self, arch_context_dir: Path = None):
        # Default to repo root's architecture-context (script is in .claude/skills/quality-repo-analysis/)
        self.arch_context_dir = arch_context_dir or Path(__file__).parent.parent.parent.parent / "architecture-context"
        self.loader = ArchitectureContextLoader(self.arch_context_dir)
        self.parser = QualityReportParser()

    def get_all_repositories(self) -> List[Dict[str, str]]:
        """Get list of all repositories from architecture context"""
        return self.loader.get_repositories()

    def process_reports(self, reports_dir: Path) -> List[RepositoryQuality]:
        """Process all reports in a directory"""
        results = []
        repos = self.get_all_repositories()

        for repo in repos:
            # Look for report file (assuming pattern: {repo_name}_quality_report.md)
            report_files = list(reports_dir.glob(f"{repo['name']}*.md"))
            if not report_files:
                report_files = list(reports_dir.glob(f"*{repo['name']}*.md"))

            if report_files:
                report_file = report_files[0]  # Use first match
                result = self.parser.parse_report(
                    report_file,
                    repo['name'],
                    repo['url'],
                    repo['org'],
                    repo['source_type']
                )
                if result:
                    results.append(result)
            else:
                print(f"Warning: No report found for {repo['name']}")

        return results

    def generate_combined_report(self, results: List[RepositoryQuality],
                                  output_path: Path) -> None:
        """Generate combined markdown report"""
        report_lines = [
            "# Quality Analysis - Combined Report",
            f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"\nTotal Repositories Analyzed: {len(results)}",
            "\n---\n",
            "## Executive Summary\n"
        ]

        # Calculate statistics
        avg_score = sum(r.overall_score for r in results) / len(results) if results else 0
        max_score_repo = max(results, key=lambda r: r.overall_score) if results else None
        min_score_repo = min(results, key=lambda r: r.overall_score) if results else None

        report_lines.extend([
            f"- **Average Quality Score**: {avg_score:.2f}/10",
            f"- **Highest Score**: {max_score_repo.name} ({max_score_repo.overall_score:.1f}/10)" if max_score_repo else "",
            f"- **Lowest Score**: {min_score_repo.name} ({min_score_repo.overall_score:.1f}/10)" if min_score_repo else "",
            "\n## Quality Scorecard by Repository\n",
            "| Repository | Source | Overall Score | Unit Tests | Integration/E2E | Image Testing | Coverage | CI/CD |",
            "|------------|--------|---------------|------------|-----------------|---------------|----------|-------|"
        ])

        # Add repository scores
        for result in sorted(results, key=lambda r: r.overall_score, reverse=True):
            scores_dict = {s.dimension: s.score for s in result.scores}
            row = f"| [{result.name}]({result.url}) | {result.source_type.title()} | {result.overall_score:.1f}/10 |"

            # Add common dimensions (handle missing gracefully)
            for dim in ["Unit Tests", "Integration/E2E", "Image Testing", "Coverage Tracking", "CI/CD Automation"]:
                score = scores_dict.get(dim, 0)
                row += f" {score:.1f}/10 |"

            report_lines.append(row)

        # Statistics by source type
        report_lines.extend([
            "\n## Statistics by Source Type\n"
        ])

        for source_type in ['upstream', 'downstream', 'external']:
            type_results = [r for r in results if r.source_type == source_type]
            if type_results:
                type_avg = sum(r.overall_score for r in type_results) / len(type_results)
                report_lines.extend([
                    f"\n### {source_type.title()}",
                    f"- **Count**: {len(type_results)} repositories",
                    f"- **Average Score**: {type_avg:.2f}/10",
                    f"- **Range**: {min(r.overall_score for r in type_results):.1f} - {max(r.overall_score for r in type_results):.1f}",
                ])

        # Write report
        output_path.write_text('\n'.join(report_lines))
        print(f"\nCombined report written to: {output_path}")

    def export_json(self, results: List[RepositoryQuality], output_path: Path) -> None:
        """Export results as JSON"""
        data = {
            'generated': datetime.now().isoformat(),
            'total_repositories': len(results),
            'average_score': sum(r.overall_score for r in results) / len(results) if results else 0,
            'repositories': [
                {
                    'name': r.name,
                    'url': r.url,
                    'org': r.org,
                    'source_type': r.source_type,
                    'overall_score': r.overall_score,
                    'scores': [asdict(s) for s in r.scores],
                    'critical_gaps': r.critical_gaps,
                    'quick_wins': r.quick_wins,
                    'recommendations': r.recommendations,
                    'report_file': r.report_file
                }
                for r in results
            ]
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"JSON export written to: {output_path}")

    def generate_html(self, results: List[RepositoryQuality], output_path: Path) -> None:
        """Generate custom HTML dashboard for aggregated results"""
        if not results:
            print("No results to generate HTML")
            return

        # Calculate statistics
        avg_score = sum(r.overall_score for r in results) / len(results)
        max_repo = max(results, key=lambda r: r.overall_score)
        min_repo = min(results, key=lambda r: r.overall_score)

        # Sort by score
        sorted_results = sorted(results, key=lambda r: r.overall_score, reverse=True)

        # Generate HTML
        html = self._generate_aggregated_html(sorted_results, avg_score, max_repo, min_repo)
        output_path.write_text(html)
        print(f"HTML report written to: {output_path}")

    def _generate_aggregated_html(self, results: List[RepositoryQuality],
                                   avg_score: float, max_repo: RepositoryQuality,
                                   min_repo: RepositoryQuality) -> str:
        """Generate HTML for aggregated quality report"""

        # Calculate color based on average score
        score_color = self._get_score_color(avg_score)

        # Group by source type
        by_source = {}
        for r in results:
            by_source.setdefault(r.source_type, []).append(r)

        timestamp = datetime.now().strftime('%B %d, %Y at %I:%M %p')

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quality Analysis - Combined Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 2rem;
            color: #333;
        }}

        .container {{
            max-width: 1400px;
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

        .timestamp {{
            opacity: 0.9;
            font-size: 0.9rem;
        }}

        .content {{
            padding: 2rem;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .stat-card {{
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
        }}

        .stat-value {{
            font-size: 3rem;
            font-weight: 700;
            color: {score_color};
            margin-bottom: 0.5rem;
        }}

        .stat-label {{
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
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1rem;
        }}

        th, td {{
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }}

        th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #667eea;
        }}

        tr:hover {{
            background: #f8f9fa;
        }}

        .score-badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-weight: 600;
            font-size: 0.9rem;
        }}

        .score-excellent {{ background: #28a745; color: white; }}
        .score-good {{ background: #ffc107; color: #333; }}
        .score-fair {{ background: #fd7e14; color: white; }}
        .score-poor {{ background: #dc3545; color: white; }}

        .repo-link {{
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
        }}

        .repo-link:hover {{
            text-decoration: underline;
        }}

        .source-badge {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: 600;
            background: #e9ecef;
            color: #495057;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Quality Analysis - Combined Dashboard</h1>
            <div class="timestamp">Generated on {timestamp}</div>
            <div class="timestamp">{len(results)} Repositories Analyzed</div>
        </header>

        <div class="content">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{avg_score:.1f}/10</div>
                    <div class="stat-label">Average Score</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: {self._get_score_color(max_repo.overall_score)};">{max_repo.overall_score:.1f}/10</div>
                    <div class="stat-label">Highest Score</div>
                    <div style="margin-top: 0.5rem; font-size: 0.9rem;">{max_repo.name}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: {self._get_score_color(min_repo.overall_score)};">{min_repo.overall_score:.1f}/10</div>
                    <div class="stat-label">Lowest Score</div>
                    <div style="margin-top: 0.5rem; font-size: 0.9rem;">{min_repo.name}</div>
                </div>
            </div>

            <div class="section">
                <h2 class="section-title">Quality Scorecard by Repository</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Repository</th>
                            <th>Source</th>
                            <th>Overall</th>
                            <th>Unit Tests</th>
                            <th>Integration/E2E</th>
                            <th>Coverage</th>
                            <th>CI/CD</th>
                        </tr>
                    </thead>
                    <tbody>
                        {self._generate_table_rows(results)}
                    </tbody>
                </table>
            </div>

            {self._generate_source_sections(by_source)}
        </div>
    </div>
</body>
</html>'''

    def _get_score_color(self, score: float) -> str:
        """Get color based on score"""
        if score >= 8.0:
            return '#28a745'  # Green
        elif score >= 6.0:
            return '#ffc107'  # Yellow
        elif score >= 4.0:
            return '#fd7e14'  # Orange
        else:
            return '#dc3545'  # Red

    def _get_score_class(self, score: float) -> str:
        """Get CSS class based on score"""
        if score >= 8.0:
            return 'score-excellent'
        elif score >= 6.0:
            return 'score-good'
        elif score >= 4.0:
            return 'score-fair'
        else:
            return 'score-poor'

    def _generate_table_rows(self, results: List[RepositoryQuality]) -> str:
        """Generate table rows for repositories"""
        rows = []
        for r in results:
            scores_dict = {s.dimension: s.score for s in r.scores}

            # Get common dimensions
            unit_tests = scores_dict.get("Unit Tests", scores_dict.get("| Unit Tests", 0))
            integration = scores_dict.get("Integration/E2E", 0)
            coverage = scores_dict.get("Coverage Tracking", 0)
            cicd = scores_dict.get("CI/CD Automation", 0)

            row = f'''
                <tr>
                    <td><a href="{r.url}" class="repo-link" target="_blank">{r.name}</a></td>
                    <td><span class="source-badge">{r.source_type.title()}</span></td>
                    <td><span class="score-badge {self._get_score_class(r.overall_score)}">{r.overall_score:.1f}/10</span></td>
                    <td><span class="score-badge {self._get_score_class(unit_tests)}">{unit_tests:.1f}/10</span></td>
                    <td><span class="score-badge {self._get_score_class(integration)}">{integration:.1f}/10</span></td>
                    <td><span class="score-badge {self._get_score_class(coverage)}">{coverage:.1f}/10</span></td>
                    <td><span class="score-badge {self._get_score_class(cicd)}">{cicd:.1f}/10</span></td>
                </tr>'''
            rows.append(row)

        return '\n'.join(rows)

    def _generate_source_sections(self, by_source: Dict[str, List[RepositoryQuality]]) -> str:
        """Generate sections grouped by source type"""
        sections = []

        for source_type in ['upstream', 'downstream', 'external']:
            repos = by_source.get(source_type, [])
            if not repos:
                continue

            avg = sum(r.overall_score for r in repos) / len(repos)
            min_score = min(r.overall_score for r in repos)
            max_score = max(r.overall_score for r in repos)

            section = f'''
            <div class="section">
                <h2 class="section-title">{source_type.title()} Repositories</h2>
                <p style="margin-bottom: 1rem;">
                    <strong>{len(repos)}</strong> repositories |
                    Average: <span class="score-badge {self._get_score_class(avg)}">{avg:.2f}/10</span> |
                    Range: {min_score:.1f} - {max_score:.1f}
                </p>
            </div>'''
            sections.append(section)

        return '\n'.join(sections)

    def generate_analysis_commands(self, output_path: Path = None) -> None:
        """Generate Claude Code commands to analyze all repositories"""
        repos = self.get_all_repositories()
        commands = []

        commands.append("# Quality Analysis Commands")
        commands.append(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        commands.append(f"# Total repositories: {len(repos)}")
        commands.append(f"# Source: architecture-context\n")

        for source_type in ['upstream', 'downstream', 'external']:
            type_repos = [r for r in repos if r['source_type'] == source_type]
            if type_repos:
                commands.append(f"\n## {source_type.title()} ({len(type_repos)} repos)")
                for repo in type_repos:
                    commands.append(f"/quality-repo-analysis {repo['url']}")

        if output_path:
            output_path.write_text('\n'.join(commands))
            print(f"Commands written to: {output_path}")
        else:
            print('\n'.join(commands))


def main():
    parser = argparse.ArgumentParser(description='Aggregate quality analysis reports')
    parser.add_argument('--reports-dir', type=Path,
                        help='Directory containing quality report markdown files')
    parser.add_argument('--output-md', type=Path, default=Path('combined_quality_report.md'),
                        help='Output path for combined markdown report')
    parser.add_argument('--output-json', type=Path,
                        help='Output path for JSON export (optional)')
    parser.add_argument('--output-html', type=Path,
                        help='Output path for HTML report (optional)')
    parser.add_argument('--generate-commands', action='store_true',
                        help='Generate analysis commands for all repositories')
    parser.add_argument('--commands-output', type=Path,
                        help='Output file for generated commands')
    parser.add_argument('--arch-context', type=Path,
                        help='Path to architecture-context directory (default: ./architecture-context)')

    args = parser.parse_args()

    aggregator = QualityReportAggregator(args.arch_context)

    if args.generate_commands:
        aggregator.generate_analysis_commands(args.commands_output)
        return

    if not args.reports_dir:
        parser.error("--reports-dir is required unless using --generate-commands")

    if not args.reports_dir.exists():
        print(f"Error: Reports directory not found: {args.reports_dir}")
        return

    print(f"Processing reports from: {args.reports_dir}")
    results = aggregator.process_reports(args.reports_dir)

    if not results:
        print("No reports found to process")
        return

    print(f"\nProcessed {len(results)} reports")

    # Generate markdown
    aggregator.generate_combined_report(results, args.output_md)

    # Generate JSON if requested
    if args.output_json:
        aggregator.export_json(results, args.output_json)

    # Generate HTML if requested
    if args.output_html:
        aggregator.generate_html(results, args.output_html)


if __name__ == '__main__':
    main()
