#!/usr/bin/env python3
"""PR metadata extraction using gh CLI.

Extracts comprehensive PR information including metadata, diff, changed files,
commits, and Jira issue keys for quality analysis.

Usage:
    python3 scripts/pr_extractor.py <pr_number> <repo> [--output <file>]

Example:
    python3 scripts/pr_extractor.py 7292 opendatahub-io/odh-dashboard --output tmp/pr-7292.json
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_gh_command(args: list[str]) -> str:
    """
    Run gh CLI command and return output.

    Raises:
        RuntimeError: If gh command fails
    """
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"gh CLI error: {e.stderr}") from e
    except FileNotFoundError:
        raise RuntimeError("gh CLI not found. Install from https://cli.github.com/")


def extract_jira_keys(text: str) -> list[str]:
    """
    Extract Jira issue keys from text.

    Patterns matched:
    - RHOAIENG-12345
    - RHOAI-123
    - RHODS-456

    Returns:
        List of unique Jira keys found (uppercase)
    """
    if not text:
        return []

    # Match Jira key pattern: PROJECT-NUMBER
    # Common Red Hat AI projects: RHOAIENG, RHOAI, RHODS, ODH
    pattern = r'\b(RHOAIENG|RHOAI|RHODS|ODH)-\d+\b'
    matches = re.findall(pattern, text, re.IGNORECASE)

    # Deduplicate and uppercase
    unique_keys = []
    seen = set()
    for match in matches:
        key_upper = match.upper()
        if key_upper not in seen:
            unique_keys.append(key_upper)
            seen.add(key_upper)

    return unique_keys


def get_pr_metadata(pr_number: int, repo: str) -> dict[str, Any]:
    """
    Fetch PR metadata using gh CLI.

    Returns:
        {
            "number": 7292,
            "title": "Add authentication middleware",
            "author": "username",
            "state": "open",
            "mergeable": "MERGEABLE",
            "draft": false,
            "created_at": "2026-04-15T10:30:00Z",
            "updated_at": "2026-04-17T14:22:00Z",
            "body": "PR description...",
            "labels": ["enhancement", "security"],
            "url": "https://github.com/org/repo/pull/7292",
            "head_ref": "feature/auth-middleware",
            "base_ref": "main",
            "additions": 450,
            "deletions": 120,
            "changed_files": 12
        }
    """
    # Fetch PR as JSON
    pr_json = run_gh_command([
        "pr", "view", str(pr_number),
        "--repo", repo,
        "--json", "number,title,author,state,mergeable,isDraft,createdAt,updatedAt,body,labels,url,headRefName,baseRefName,additions,deletions,changedFiles"
    ])

    pr_data = json.loads(pr_json)

    # Normalize field names
    return {
        "number": pr_data["number"],
        "title": pr_data["title"],
        "author": pr_data["author"]["login"],
        "state": pr_data["state"],
        "mergeable": pr_data["mergeable"],
        "draft": pr_data["isDraft"],
        "created_at": pr_data["createdAt"],
        "updated_at": pr_data["updatedAt"],
        "body": pr_data.get("body", ""),
        "labels": [label["name"] for label in pr_data.get("labels", [])],
        "url": pr_data["url"],
        "head_ref": pr_data["headRefName"],
        "base_ref": pr_data["baseRefName"],
        "additions": pr_data["additions"],
        "deletions": pr_data["deletions"],
        "changed_files": pr_data["changedFiles"]
    }


def get_pr_diff(pr_number: int, repo: str) -> str:
    """Get full PR diff."""
    return run_gh_command([
        "pr", "diff", str(pr_number),
        "--repo", repo
    ])


def get_changed_files(pr_number: int, repo: str) -> list[dict[str, Any]]:
    """
    Get list of changed files with stats.

    Returns:
        [
            {
                "path": "pkg/security/auth.go",
                "additions": 45,
                "deletions": 10,
                "changes": 55
            },
            ...
        ]
    """
    files_json = run_gh_command([
        "pr", "view", str(pr_number),
        "--repo", repo,
        "--json", "files"
    ])

    data = json.loads(files_json)

    return [
        {
            "path": f["path"],
            "additions": f["additions"],
            "deletions": f["deletions"],
            "changes": f["additions"] + f["deletions"]
        }
        for f in data.get("files", [])
    ]


def get_commits(pr_number: int, repo: str) -> list[dict[str, str]]:
    """
    Get PR commits.

    Returns:
        [
            {
                "sha": "abc123...",
                "message": "Add authentication middleware",
                "author": "username"
            },
            ...
        ]
    """
    commits_json = run_gh_command([
        "pr", "view", str(pr_number),
        "--repo", repo,
        "--json", "commits"
    ])

    data = json.loads(commits_json)

    return [
        {
            "sha": c["oid"],
            "message": c["messageHeadline"],
            "author": c["authors"][0]["login"] if c.get("authors") else "unknown"
        }
        for c in data.get("commits", [])
    ]


def extract_pr_data(pr_number: int, repo: str) -> dict[str, Any]:
    """
    Extract complete PR data for analysis.

    Returns comprehensive PR bundle with metadata, diff, files, commits, and Jira keys.
    """
    print(f"Fetching PR #{pr_number} from {repo}...", file=sys.stderr)

    # Fetch all data
    metadata = get_pr_metadata(pr_number, repo)
    diff = get_pr_diff(pr_number, repo)
    files = get_changed_files(pr_number, repo)
    commits = get_commits(pr_number, repo)

    # Extract Jira keys from multiple sources
    jira_keys = []
    jira_keys.extend(extract_jira_keys(metadata["title"]))
    jira_keys.extend(extract_jira_keys(metadata["body"]))
    jira_keys.extend(extract_jira_keys(metadata["head_ref"]))

    # Deduplicate while preserving order
    unique_jira_keys = []
    seen = set()
    for key in jira_keys:
        if key not in seen:
            unique_jira_keys.append(key)
            seen.add(key)

    # Combine all commit messages for Jira key extraction
    all_commit_messages = " ".join(c["message"] for c in commits)
    commit_jira_keys = extract_jira_keys(all_commit_messages)
    for key in commit_jira_keys:
        if key not in seen:
            unique_jira_keys.append(key)
            seen.add(key)

    return {
        "repo": repo,
        "metadata": metadata,
        "diff": diff,
        "files": files,
        "commits": commits,
        "jira_keys": unique_jira_keys,
        "extracted_at": subprocess.run(
            ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
            capture_output=True,
            text=True
        ).stdout.strip()
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract PR metadata using gh CLI"
    )
    parser.add_argument(
        "pr_number",
        type=int,
        help="PR number"
    )
    parser.add_argument(
        "repo",
        help="Repository (e.g., opendatahub-io/odh-dashboard)"
    )
    parser.add_argument(
        "--output",
        help="Output file path (default: stdout)"
    )

    args = parser.parse_args()

    try:
        pr_data = extract_pr_data(args.pr_number, args.repo)

        # Output as JSON
        json_output = json.dumps(pr_data, indent=2)

        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json_output)
            print(f"✓ PR data written to {args.output}", file=sys.stderr)
        else:
            print(json_output)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
