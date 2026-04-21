#!/usr/bin/env python3
"""Jira integration utilities for fetching issue context.

Fetches Jira Epic/Story context from issues.redhat.com to enrich PR analysis
with requirements, acceptance criteria, and team information.

Usage:
    python3 scripts/jira_utils.py get <issue_key> [--output <file>]
    python3 scripts/jira_utils.py get-epic <epic_key> [--output <file>]
    python3 scripts/jira_utils.py enrich-pr <pr_data.json> [--output <file>]

Environment:
    JIRA_TOKEN - Personal access token for issues.redhat.com
                 Get from: https://issues.redhat.com/secure/ViewProfile.jspa

Example:
    export JIRA_TOKEN="your-token-here"
    python3 scripts/jira_utils.py get RHOAIENG-12345 --output tmp/jira-12345.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import requests


JIRA_BASE_URL = "https://issues.redhat.com/rest/api/2"
PROJECT_KEY = "RHOAIENG"


class JiraClient:
    """Client for Jira REST API."""

    def __init__(self, token: Optional[str] = None):
        """
        Initialize Jira client.

        Args:
            token: Jira personal access token (defaults to JIRA_TOKEN env var)
        """
        self.token = token or os.environ.get("JIRA_TOKEN")
        if not self.token:
            raise ValueError(
                "JIRA_TOKEN environment variable not set. "
                "Get token from https://issues.redhat.com/secure/ViewProfile.jspa"
            )

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def get_issue(self, issue_key: str) -> dict[str, Any]:
        """
        Fetch issue details from Jira.

        Args:
            issue_key: Jira issue key (e.g., "RHOAIENG-12345")

        Returns:
            {
                "key": "RHOAIENG-12345",
                "summary": "Improve authentication security",
                "description": "Epic goals and details...",
                "issue_type": "Epic" | "Story" | "Task" | "Bug",
                "status": "In Progress",
                "priority": "High",
                "components": ["AI Core Dashboard", "kserve"],
                "labels": ["security", "needs-advisor"],
                "assignee": "user@redhat.com",
                "epic_link": "RHOAIENG-98765" (if Story/Task),
                "epic_name": "Security Improvements" (if Epic),
                "team": "RHOAI Dashboard",
                "acceptance_criteria": "..." (parsed from description)
            }

        Raises:
            RuntimeError: If API request fails
        """
        url = f"{JIRA_BASE_URL}/issue/{issue_key}"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise RuntimeError(
                    "Jira authentication failed. Check JIRA_TOKEN environment variable."
                ) from e
            elif e.response.status_code == 404:
                raise RuntimeError(f"Jira issue not found: {issue_key}") from e
            else:
                raise RuntimeError(f"Jira API error: {e}") from e
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Jira API request failed: {e}") from e

        data = response.json()
        fields = data.get("fields", {})

        # Extract acceptance criteria from description
        description = fields.get("description", "") or ""
        acceptance_criteria = self._extract_acceptance_criteria(description)

        # Build normalized response
        return {
            "key": data["key"],
            "summary": fields.get("summary", ""),
            "description": description,
            "issue_type": fields.get("issuetype", {}).get("name", "Unknown"),
            "status": fields.get("status", {}).get("name", "Unknown"),
            "priority": fields.get("priority", {}).get("name", "Unknown"),
            "components": [c["name"] for c in fields.get("components", [])],
            "labels": fields.get("labels", []),
            "assignee": fields.get("assignee", {}).get("emailAddress", None) if fields.get("assignee") else None,
            "epic_link": fields.get("customfield_12311140"),  # Epic Link custom field
            "epic_name": fields.get("customfield_12311141"),  # Epic Name custom field
            "team": fields.get("customfield_12310940", {}).get("value") if fields.get("customfield_12310940") else None,  # Team custom field
            "acceptance_criteria": acceptance_criteria,
            "url": f"https://issues.redhat.com/browse/{data['key']}"
        }

    def get_epic_context(self, epic_key: str) -> dict[str, Any]:
        """
        Get full Epic context including child issues.

        Args:
            epic_key: Epic issue key (e.g., "RHOAIENG-98765")

        Returns:
            {
                "epic": {...},  # Epic issue details
                "stories": [...],  # Child stories
                "tasks": [...],  # Child tasks
                "total_issues": 15
            }
        """
        # Fetch Epic itself
        epic = self.get_issue(epic_key)

        if epic["issue_type"] != "Epic":
            raise ValueError(f"{epic_key} is not an Epic (type: {epic['issue_type']})")

        # Search for child issues using JQL
        jql = f'"Epic Link" = {epic_key}'
        children = self._search_issues(jql)

        # Separate by type
        stories = [issue for issue in children if issue["issue_type"] == "Story"]
        tasks = [issue for issue in children if issue["issue_type"] in ["Task", "Sub-task"]]

        return {
            "epic": epic,
            "stories": stories,
            "tasks": tasks,
            "total_issues": len(children)
        }

    def _search_issues(self, jql: str, max_results: int = 100) -> list[dict[str, Any]]:
        """
        Search for issues using JQL.

        Args:
            jql: JQL query string
            max_results: Maximum number of results to return

        Returns:
            List of issue dictionaries
        """
        url = f"{JIRA_BASE_URL}/search"
        params = {
            "jql": jql,
            "maxResults": max_results
        }

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Jira search failed: {e}") from e

        data = response.json()
        issues = []

        for issue_data in data.get("issues", []):
            fields = issue_data.get("fields", {})
            issues.append({
                "key": issue_data["key"],
                "summary": fields.get("summary", ""),
                "issue_type": fields.get("issuetype", {}).get("name", "Unknown"),
                "status": fields.get("status", {}).get("name", "Unknown"),
                "priority": fields.get("priority", {}).get("name", "Unknown"),
                "assignee": fields.get("assignee", {}).get("emailAddress", None) if fields.get("assignee") else None,
                "url": f"https://issues.redhat.com/browse/{issue_data['key']}"
            })

        return issues

    def _extract_acceptance_criteria(self, description: str) -> Optional[str]:
        """
        Extract acceptance criteria from issue description.

        Looks for common patterns:
        - "Acceptance Criteria:"
        - "AC:"
        - Bulleted list after those headers

        Returns:
            Extracted criteria text, or None if not found
        """
        if not description:
            return None

        # Common patterns
        patterns = [
            r"(?i)acceptance criteria:?\s*\n(.*?)(?:\n\n|\Z)",
            r"(?i)^AC:?\s*\n(.*?)(?:\n\n|\Z)",
            r"(?i)criteria:?\s*\n(.*?)(?:\n\n|\Z)"
        ]

        import re
        for pattern in patterns:
            match = re.search(pattern, description, re.DOTALL | re.MULTILINE)
            if match:
                return match.group(1).strip()

        return None


def enrich_pr_with_jira(pr_data: dict[str, Any], client: JiraClient) -> dict[str, Any]:
    """
    Enrich PR data with Jira issue context.

    Args:
        pr_data: PR data from pr_extractor.py
        client: Jira client instance

    Returns:
        Enriched PR data with Jira context added
    """
    jira_keys = pr_data.get("jira_keys", [])

    if not jira_keys:
        print("No Jira keys found in PR", file=sys.stderr)
        pr_data["jira_context"] = {
            "issues": [],
            "epics": []
        }
        return pr_data

    print(f"Fetching Jira context for {len(jira_keys)} issue(s)...", file=sys.stderr)

    issues = []
    epics = []
    epic_keys_seen = set()

    for key in jira_keys:
        try:
            issue = client.get_issue(key)
            issues.append(issue)

            # If this is a Story/Task with an Epic link, fetch the Epic too
            if issue["epic_link"] and issue["epic_link"] not in epic_keys_seen:
                try:
                    epic = client.get_epic_context(issue["epic_link"])
                    epics.append(epic)
                    epic_keys_seen.add(issue["epic_link"])
                except Exception as e:
                    print(f"Warning: Could not fetch Epic {issue['epic_link']}: {e}", file=sys.stderr)

            # If this IS an Epic, fetch its context
            if issue["issue_type"] == "Epic" and key not in epic_keys_seen:
                try:
                    epic = client.get_epic_context(key)
                    epics.append(epic)
                    epic_keys_seen.add(key)
                except Exception as e:
                    print(f"Warning: Could not fetch Epic context for {key}: {e}", file=sys.stderr)

        except Exception as e:
            print(f"Warning: Could not fetch Jira issue {key}: {e}", file=sys.stderr)

    pr_data["jira_context"] = {
        "issues": issues,
        "epics": epics
    }

    return pr_data


def main():
    parser = argparse.ArgumentParser(description="Jira utilities for PR analysis")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # get command
    get_parser = subparsers.add_parser("get", help="Get Jira issue details")
    get_parser.add_argument("issue_key", help="Jira issue key (e.g., RHOAIENG-12345)")
    get_parser.add_argument("--output", help="Output file path (default: stdout)")

    # get-epic command
    epic_parser = subparsers.add_parser("get-epic", help="Get Epic context with children")
    epic_parser.add_argument("epic_key", help="Epic issue key")
    epic_parser.add_argument("--output", help="Output file path (default: stdout)")

    # enrich-pr command
    enrich_parser = subparsers.add_parser("enrich-pr", help="Enrich PR data with Jira context")
    enrich_parser.add_argument("pr_data_file", help="PR data JSON file from pr_extractor.py")
    enrich_parser.add_argument("--output", help="Output file path (default: stdout)")

    args = parser.parse_args()

    try:
        client = JiraClient()

        if args.command == "get":
            issue = client.get_issue(args.issue_key)
            output = json.dumps(issue, indent=2)

        elif args.command == "get-epic":
            epic_context = client.get_epic_context(args.epic_key)
            output = json.dumps(epic_context, indent=2)

        elif args.command == "enrich-pr":
            with open(args.pr_data_file) as f:
                pr_data = json.load(f)

            enriched = enrich_pr_with_jira(pr_data, client)
            output = json.dumps(enriched, indent=2)

        # Write output
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output)
            print(f"✓ Jira data written to {args.output}", file=sys.stderr)
        else:
            print(output)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
