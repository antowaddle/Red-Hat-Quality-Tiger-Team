#!/usr/bin/env python3
"""Cross-repo reference search utility.

Searches related repositories for hardcoded references to changed resource names,
file paths, or identifiers. Critical for detecting breaking changes across repos.

Usage:
    python3 scripts/search_cross_repo_refs.py <pattern> [--repos repo1,repo2,...]

Example:
    # Search for ConfigMap name references
    python3 scripts/search_cross_repo_refs.py "model-catalog-default-sources"

    # Search specific repos only
    python3 scripts/search_cross_repo_refs.py "default-sources" --repos odh-dashboard,kserve
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_REPOS = [
    "odh-dashboard",
    "kserve",
    "notebooks",
    "model-registry",
    "data-science-pipelines-operator"
]


def search_repo(repo_path: Path, pattern: str) -> list[dict[str, Any]]:
    """Search a repository for a pattern.

    Args:
        repo_path: Path to repository
        pattern: Search pattern (plain text or regex)

    Returns:
        List of matches with file, line number, and content
    """
    if not repo_path.exists():
        return []

    try:
        # Use grep to search recursively
        result = subprocess.run(
            ["grep", "-rn", "--", pattern, str(repo_path)],
            capture_output=True,
            text=True,
            timeout=30
        )

        matches = []
        for line in result.stdout.split("\n"):
            if not line.strip():
                continue

            # Parse grep output: file:line:content
            parts = line.split(":", 2)
            if len(parts) >= 3:
                matches.append({
                    "file": parts[0].replace(str(repo_path) + "/", ""),
                    "line": parts[1],
                    "content": parts[2].strip()
                })

        return matches

    except subprocess.TimeoutExpired:
        print(f"Warning: Search timed out for {repo_path}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Warning: Search failed for {repo_path}: {e}", file=sys.stderr)
        return []


def categorize_impact(matches: list[dict[str, Any]], repo: str) -> str:
    """Categorize impact based on where references are found.

    Args:
        matches: List of matched references
        repo: Repository name

    Returns:
        Impact level: CRITICAL, HIGH, MEDIUM, LOW
    """
    if not matches:
        return "NONE"

    high_impact_patterns = [
        "/test/", "/tests/", "_test.go", ".test.ts", ".test.js",
        "cypress/", "e2e/", "integration/",
        "const ", "const(", "=",  # Constants/variables
        "client.go", "service.go", "controller.go"  # Core code
    ]

    medium_impact_patterns = [
        "README", "doc/", "docs/", ".md",
        "example/", "examples/",
        "comment", "//", "#"
    ]

    # Check if any matches are in high-impact locations
    for match in matches:
        file_path = match["file"]
        content = match["content"]

        # High impact: Tests, core code, constants
        for pattern in high_impact_patterns:
            if pattern in file_path.lower() or pattern in content:
                return "CRITICAL"

    # Medium impact: Documentation, examples
    for match in matches:
        file_path = match["file"]
        for pattern in medium_impact_patterns:
            if pattern in file_path.lower():
                return "MEDIUM"

    # Low impact: Other references
    return "LOW"


def main():
    parser = argparse.ArgumentParser(
        description="Search related repositories for hardcoded references"
    )
    parser.add_argument(
        "pattern",
        help="Pattern to search for (ConfigMap name, file path, etc.)"
    )
    parser.add_argument(
        "--repos",
        help="Comma-separated list of repos to search (default: all ODH repos)",
        default=",".join(DEFAULT_REPOS)
    )
    parser.add_argument(
        "--context-dir",
        help="Directory containing cloned context repos",
        default="context-repos"
    )
    parser.add_argument(
        "--output",
        help="Output file for JSON results (default: stdout)"
    )
    parser.add_argument(
        "--max-matches",
        type=int,
        default=50,
        help="Maximum matches to return per repo (default: 50)"
    )

    args = parser.parse_args()

    repos = [r.strip() for r in args.repos.split(",")]
    context_dir = Path(args.context_dir)

    results = {
        "pattern": args.pattern,
        "repos_searched": [],
        "affected_repos": [],
        "total_matches": 0
    }

    for repo in repos:
        repo_path = context_dir / repo
        results["repos_searched"].append(repo)

        if not repo_path.exists():
            print(f"⚠️  Repo not found: {repo} (skipping)", file=sys.stderr)
            continue

        print(f"🔍 Searching {repo}...", file=sys.stderr)
        matches = search_repo(repo_path, args.pattern)

        if matches:
            # Limit matches per repo
            matches = matches[:args.max_matches]

            impact = categorize_impact(matches, repo)
            results["total_matches"] += len(matches)

            affected = {
                "repo": repo,
                "impact": impact,
                "match_count": len(matches),
                "matches": matches
            }
            results["affected_repos"].append(affected)

            # Print summary
            impact_emoji = {
                "CRITICAL": "🔴",
                "HIGH": "🟡",
                "MEDIUM": "🟢",
                "LOW": "⚪"
            }
            emoji = impact_emoji.get(impact, "⚪")
            print(f"  {emoji} {impact}: {len(matches)} reference(s) found", file=sys.stderr)

    # Output results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n✅ Results written to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(results, indent=2))

    # Exit with status code based on critical findings
    critical_repos = [r for r in results["affected_repos"] if r["impact"] == "CRITICAL"]
    if critical_repos:
        print(f"\n🚨 CRITICAL: Found hardcoded references in {len(critical_repos)} repo(s)", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
