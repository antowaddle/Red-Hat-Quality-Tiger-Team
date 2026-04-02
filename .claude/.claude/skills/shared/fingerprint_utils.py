#!/usr/bin/env python3
"""Jira fingerprinting utilities for Quality Tiger Team skills.

Records skill execution as Jira fingerprints (labels + comments) for tracking
by team-tracker dashboard.

Works with:
- Direct Jira API (via JIRA_SERVER, JIRA_USER, JIRA_TOKEN env vars)
- MCP integration (future - when Jira MCP server is configured)

Usage:
    from shared.fingerprint_utils import record_skill_execution

    results = {
        "score": 8.5,
        "critical_gaps": 2,
        "quick_wins": 5,
        "artifacts": [".claude/quality/scorecard.md", ...]
    }

    record_skill_execution(
        skill_name="quality-repo-analysis",
        repo_url="https://github.com/opendatahub-io/odh-dashboard",
        status="success",
        results=results,
    )
"""

import os
import sys
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

# Import RFE creator's proven Jira utilities
try:
    from .jira_utils import (
        require_env,
        api_call,
        create_issue,
        add_labels,
        add_comment,
        markdown_to_adf,
    )
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from jira_utils import (
        require_env,
        api_call,
        create_issue,
        add_labels,
        add_comment,
        markdown_to_adf,
    )


# ─── Configuration ─────────────────────────────────────────────────────────────

DEFAULT_PROJECT = "RHOAIENG"  # Default Jira project for tracking issues


# ─── Environment Detection ─────────────────────────────────────────────────────

def is_jira_configured() -> bool:
    """Check if Jira API access is configured via environment variables."""
    return all([
        os.getenv("JIRA_SERVER"),
        os.getenv("JIRA_USER"),
        os.getenv("JIRA_TOKEN"),
    ])


def print_setup_instructions():
    """Print instructions for configuring Jira access."""
    print("\n⚠️  Fingerprinting skipped: Jira not configured", file=sys.stderr)
    print("\nTo enable execution tracking, choose one option:\n", file=sys.stderr)
    print("Option 1: Configure Jira MCP Server (works in Ambient + local)", file=sys.stderr)
    print("  See: https://github.com/tom28881/mcp-jira-server\n", file=sys.stderr)
    print("Option 2: Set environment variables (local only)", file=sys.stderr)
    print("  export JIRA_SERVER=https://redhat.atlassian.net", file=sys.stderr)
    print("  export JIRA_USER=your-email@redhat.com", file=sys.stderr)
    print("  export JIRA_TOKEN=your-api-token\n", file=sys.stderr)


# ─── Jira Search ───────────────────────────────────────────────────────────────

def search_issues(server: str, user: str, token: str, jql: str, max_results: int = 50) -> List[Dict]:
    """Search for Jira issues using JQL.

    Args:
        server: Jira server URL
        user: Jira username/email
        token: Jira API token
        jql: JQL query string
        max_results: Maximum number of results to return

    Returns:
        List of issue objects with keys, summaries, etc.
    """
    # Use new JQL search endpoint (old /search endpoint deprecated with HTTP 410)
    # See: https://developer.atlassian.com/changelog/#CHANGE-2046
    body = {
        "jql": jql,
        "fields": ["key", "summary"],
        "maxResults": max_results,
    }
    try:
        result = api_call(server, "/search/jql", user, token, body=body, method="POST")
        return result.get("issues", []) if result else []
    except Exception as e:
        print(f"Warning: Jira search failed: {e}", file=sys.stderr)
        return []


# ─── Repository Tracking Issue Management ──────────────────────────────────────

def extract_repo_name(repo_url: str) -> str:
    """Extract repository name from URL.

    Examples:
        https://github.com/opendatahub-io/odh-dashboard -> odh-dashboard
        https://github.com/opendatahub-io/notebooks/ -> notebooks
    """
    return repo_url.rstrip("/").split("/")[-1]


def find_tracking_issue(
    server: str,
    user: str,
    token: str,
    project: str,
    repo_url: str,
) -> Optional[str]:
    """Find existing Quality Tiger Team tracking issue for a repository.

    Args:
        server: Jira server URL
        user: Jira username/email
        token: Jira API token
        project: Jira project key (e.g., "RHOAIENG")
        repo_url: Repository URL

    Returns:
        Jira issue key (e.g., "RHOAIENG-12345") or None if not found
    """
    repo_name = extract_repo_name(repo_url)

    # Search for existing tracking issue
    # Title format: [Quality Tiger Team] Repository Quality Tracking - {repo-name}
    jql = (
        f'project = "{project}" AND '
        f'summary ~ "Quality Tiger Team" AND '
        f'summary ~ "{repo_name}" AND '
        f'summary ~ "Repository Quality Tracking"'
    )

    issues = search_issues(server, user, token, jql, max_results=1)

    if issues:
        return issues[0]["key"]

    return None


def create_tracking_issue(
    server: str,
    user: str,
    token: str,
    project: str,
    repo_url: str,
) -> Optional[str]:
    """Create new Quality Tiger Team tracking issue for a repository.

    Args:
        server: Jira server URL
        user: Jira username/email
        token: Jira API token
        project: Jira project key (e.g., "RHOAIENG")
        repo_url: Repository URL

    Returns:
        Jira issue key (e.g., "RHOAIENG-12345") or None if failed
    """
    repo_name = extract_repo_name(repo_url)

    summary = f"[Quality Tiger Team] Repository Quality Tracking - {repo_name}"

    description_md = f"""## Quality Tiger Team Tracking Issue

This issue tracks automated quality assessments and improvements for the **{repo_name}** repository.

**Repository:** {repo_url}

### Purpose

This issue serves as a central tracking point for all Quality Tiger Team skill executions on this repository:
- Quality Repo Analysis
- Konflux Build Simulator
- Test Rules Generator

### How It Works

Each time a Quality Tiger Team skill executes on this repository, it will:
1. Add execution labels to this issue
2. Post a comment with results and artifacts
3. Update status indicators

### Labels Used

- `quality-repo-analysis-executed` - Quality analysis completed
- `konflux-build-simulator-executed` - Build validation completed
- `test-rules-generator-executed` - Test rules generated
- `quality-tiger-team-success` - Last execution succeeded
- `quality-tiger-team-failure` - Last execution failed
- `quality-tiger-team-needs-review` - Manual review recommended

### Viewing Results

See comments below for chronological execution history with:
- Timestamp
- Skill executed
- Results summary
- Links to generated artifacts

---
*[Quality Tiger Team]* Automated tracking issue created by fingerprinting system
"""

    description_adf = markdown_to_adf(description_md)

    try:
        issue_key = create_issue(
            server, user, token,
            project=project,
            issue_type="Task",
            summary=summary,
            description_adf=description_adf,
            priority=None,  # Let Jira use default priority
            labels=["quality-tiger-team", "automation"],
        )
        return issue_key
    except Exception as e:
        print(f"Warning: Failed to create tracking issue: {e}", file=sys.stderr)
        return None


def find_or_create_tracking_issue(
    server: str,
    user: str,
    token: str,
    project: str,
    repo_url: str,
) -> Optional[str]:
    """Find existing tracking issue for repository or create new one.

    Args:
        server: Jira server URL
        user: Jira username/email
        token: Jira API token
        project: Jira project key (e.g., "RHOAIENG")
        repo_url: Repository URL

    Returns:
        Jira issue key (e.g., "RHOAIENG-12345") or None if failed
    """
    # Try to find existing
    issue_key = find_tracking_issue(server, user, token, project, repo_url)

    if issue_key:
        return issue_key

    # Create new if not found
    return create_tracking_issue(server, user, token, project, repo_url)


# ─── Comment Generation ────────────────────────────────────────────────────────

def generate_execution_comment(
    skill_name: str,
    repo_url: str,
    status: str,
    results: Dict[str, Any],
) -> str:
    """Generate markdown comment documenting skill execution.

    Args:
        skill_name: Name of skill (e.g., "quality-repo-analysis")
        repo_url: Repository URL
        status: Execution status ("success" or "failure")
        results: Skill-specific results dictionary

    Returns:
        Markdown-formatted comment text
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    status_emoji = "✅" if status == "success" else "❌"
    skill_display = skill_name.replace("-", " ").title()

    lines = [
        f"## {skill_display} - {timestamp}",
        "",
        f"**Repository:** {repo_url}",
        f"**Status:** {status_emoji} {status.title()}",
        "",
    ]

    # Add skill-specific results
    if "score" in results:
        lines.append(f"**Quality Score:** {results['score']}/10")

    if "critical_gaps" in results:
        count = results["critical_gaps"]
        lines.append(f"**Critical Gaps:** {count}")

    if "quick_wins" in results:
        count = results["quick_wins"]
        lines.append(f"**Quick Wins:** {count}")

    if "build_status" in results:
        lines.append(f"**Build Status:** {results['build_status']}")

    if "validation_phases" in results:
        lines.append(f"**Validation Phases:** {results['validation_phases']}")

    if "test_types" in results:
        types = ", ".join(results["test_types"])
        lines.append(f"**Test Types Analyzed:** {types}")

    if "patterns_extracted" in results:
        lines.append(f"**Patterns Extracted:** {results['patterns_extracted']}")

    # Add error info if failed
    if status == "failure" and "error" in results:
        lines.extend([
            "",
            "### Error Details",
            f"```\n{results['error']}\n```",
        ])

    # Add artifacts if present
    if "artifacts" in results and results["artifacts"]:
        lines.extend([
            "",
            "### Artifacts Generated",
        ])
        for artifact in results["artifacts"]:
            lines.append(f"- `{artifact}`")

    # Add recommendations if present
    if "recommendations" in results and results["recommendations"]:
        lines.extend([
            "",
            "### Key Recommendations",
        ])
        for rec in results["recommendations"][:5]:  # Top 5
            lines.append(f"- {rec}")

    lines.extend([
        "",
        "---",
        f"*[Quality Tiger Team]* Automated tracking by {skill_name} skill",
    ])

    return "\n".join(lines)


# ─── Main Fingerprinting Function ──────────────────────────────────────────────

def record_skill_execution(
    skill_name: str,
    repo_url: str,
    status: str,
    results: Dict[str, Any],
    project: str = DEFAULT_PROJECT,
) -> bool:
    """Record skill execution as Jira fingerprint.

    Creates or updates a tracking issue for the repository with:
    - Labels indicating which skill ran and status
    - Comment documenting execution details and results

    Args:
        skill_name: Name of skill (e.g., "quality-repo-analysis")
        repo_url: Repository URL (e.g., "https://github.com/opendatahub-io/odh-dashboard")
        status: Execution status - "success" or "failure"
        results: Dictionary of skill-specific results to include
        project: Jira project key (default: "RHOAIENG")

    Returns:
        True if fingerprint recorded successfully, False otherwise

    Example:
        results = {
            "score": 8.5,
            "critical_gaps": 2,
            "quick_wins": 5,
            "artifacts": [".claude/quality/scorecard.md"],
        }
        record_skill_execution(
            skill_name="quality-repo-analysis",
            repo_url="https://github.com/opendatahub-io/odh-dashboard",
            status="success",
            results=results,
        )
    """
    # Validate inputs
    if status not in ["success", "failure"]:
        print(f"Warning: Invalid status '{status}' (expected 'success' or 'failure')",
              file=sys.stderr)
        return False

    # Check if Jira is configured
    if not is_jira_configured():
        print_setup_instructions()
        return False

    # Get credentials
    server, user, token = require_env()

    if not all([server, user, token]):
        print("Error: Missing Jira credentials", file=sys.stderr)
        return False

    try:
        # Find or create tracking issue
        print(f"\n🔍 Finding tracking issue for {extract_repo_name(repo_url)}...")
        issue_key = find_or_create_tracking_issue(server, user, token, project, repo_url)

        if not issue_key:
            print("❌ Could not find or create tracking issue", file=sys.stderr)
            return False

        print(f"📌 Using tracking issue: {issue_key}")

        # Prepare labels
        labels = [
            f"{skill_name}-executed",
            f"quality-tiger-team-{status}",
        ]

        # Remove opposite status label (success vs failure)
        # This ensures we always have the latest status
        opposite_status = "success" if status == "failure" else "failure"
        # Note: add_labels in jira_utils.py doesn't remove, it only adds
        # For now, we'll just add - labels accumulate

        # Add labels
        print(f"🏷️  Adding labels: {', '.join(labels)}")
        add_labels(server, user, token, issue_key, labels)

        # Generate and post comment
        print("💬 Posting execution comment...")
        comment_md = generate_execution_comment(skill_name, repo_url, status, results)
        comment_adf = markdown_to_adf(comment_md)
        add_comment(server, user, token, issue_key, comment_adf)

        # Success
        print(f"\n✅ Fingerprint recorded successfully!")
        print(f"   Issue: {server}/browse/{issue_key}")
        print(f"   Labels: {', '.join(labels)}")

        return True

    except Exception as e:
        print(f"\n❌ Fingerprinting failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


# ─── CLI for Testing ───────────────────────────────────────────────────────────

def main():
    """CLI for testing fingerprinting functionality."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", required=True,
                        help="Skill name (e.g., quality-repo-analysis)")
    parser.add_argument("--repo", required=True,
                        help="Repository URL")
    parser.add_argument("--status", choices=["success", "failure"], default="success",
                        help="Execution status")
    parser.add_argument("--project", default=DEFAULT_PROJECT,
                        help=f"Jira project (default: {DEFAULT_PROJECT})")

    args = parser.parse_args()

    # Test results
    results = {
        "score": 8.5,
        "critical_gaps": 2,
        "quick_wins": 5,
        "artifacts": [
            ".claude/quality/scorecard.md",
            ".claude/quality/critical-gaps.md",
        ],
    }

    success = record_skill_execution(
        skill_name=args.skill,
        repo_url=args.repo,
        status=args.status,
        results=results,
        project=args.project,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
