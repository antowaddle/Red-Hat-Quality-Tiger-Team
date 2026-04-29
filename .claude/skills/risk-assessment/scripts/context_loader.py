#!/usr/bin/env python3
"""Context loader for PR analysis.

Intelligently slices architecture-context and odh-test-context repositories
to create focused context bundles for each analyzer.

Usage:
    python3 scripts/context_loader.py <pr_data.json> <context_paths.json> [--output-dir <dir>]

Example:
    python3 scripts/context_loader.py tmp/pr-7292.json tmp/context-paths.json --output-dir tmp/contexts
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional


def detect_component_from_files(files: list[dict], repo: str) -> Optional[str]:
    """
    Detect which component is affected by changed files.

    Args:
        files: List of changed file dicts with "path" field
        repo: Repository name (e.g., "opendatahub-io/odh-dashboard")

    Returns:
        Component name (e.g., "dashboard", "kserve", "notebooks") or None
    """
    # Map repos to components
    repo_component_map = {
        "opendatahub-io/odh-dashboard": "dashboard",
        "opendatahub-io/kserve": "kserve",
        "opendatahub-io/notebooks": "notebooks",
        "opendatahub-io/data-science-pipelines-operator": "dsp-operator",
        "opendatahub-io/model-registry": "model-registry",
        "opendatahub-io/modelmesh-serving": "modelmesh"
    }

    # Direct mapping from repo
    if repo in repo_component_map:
        return repo_component_map[repo]

    # Infer from file paths if repo not in map
    file_paths = [f["path"] for f in files]

    # Common patterns
    if any("dashboard" in p.lower() for p in file_paths):
        return "dashboard"
    elif any("kserve" in p.lower() for p in file_paths):
        return "kserve"
    elif any("notebook" in p.lower() for p in file_paths):
        return "notebooks"

    return None


def is_security_related(pr_data: dict) -> bool:
    """
    Determine if PR is security-related.

    Checks:
    - Labels contain "security"
    - Changed files in security/ directories
    - Files contain "auth", "token", "credential" in path
    - Jira issues have "security" label
    """
    # Check labels
    labels = pr_data.get("metadata", {}).get("labels", [])
    if any("security" in label.lower() for label in labels):
        return True

    # Check file paths
    files = pr_data.get("files", [])
    security_patterns = ["security/", "auth", "token", "credential", "crypto", "ssl", "tls"]
    for f in files:
        path_lower = f["path"].lower()
        if any(pattern in path_lower for pattern in security_patterns):
            return True

    # Check Jira labels
    jira_context = pr_data.get("jira_context", {})
    for issue in jira_context.get("issues", []):
        if any("security" in label.lower() for label in issue.get("labels", [])):
            return True

    return False


def is_critical_path(files: list[dict]) -> bool:
    """
    Determine if PR touches critical paths.

    Critical paths:
    - Authentication/authorization
    - Data pipelines
    - API gateways
    - Operators/controllers
    """
    critical_patterns = [
        "auth",
        "operator",
        "controller",
        "reconcile",
        "webhook",
        "gateway",
        "proxy",
        "pipeline",
        "scheduler"
    ]

    for f in files:
        path_lower = f["path"].lower()
        if any(pattern in path_lower for pattern in critical_patterns):
            return True

    return False


def load_architecture_context(
    component: Optional[str],
    context_dir: Path
) -> dict[str, Any]:
    """
    Load relevant architecture context.

    Args:
        component: Component name (e.g., "dashboard", "kserve")
        context_dir: Path to architecture-context repo

    Returns:
        {
            "component": "dashboard",
            "relationships": [...],  # Integration points
            "diagrams": [...],       # Relevant architecture diagrams
            "readme": "..."          # Component README if available
        }
    """
    arch_context = {
        "component": component,
        "relationships": [],
        "diagrams": [],
        "readme": None
    }

    if not component:
        return arch_context

    # Look for component-specific architecture docs
    arch_dir = context_dir / "architecture-context"
    if not arch_dir.exists():
        return arch_context

    # Try to find component README
    readme_paths = [
        arch_dir / f"components/{component}/README.md",
        arch_dir / f"{component}/README.md",
        arch_dir / "README.md"
    ]

    for readme_path in readme_paths:
        if readme_path.exists():
            arch_context["readme"] = readme_path.read_text()[:5000]  # Limit to 5KB
            break

    # Look for architecture diagrams
    diagram_patterns = [
        f"*{component}*.md",
        f"*{component}*.mermaid",
        "architecture.md",
        "integration.md"
    ]

    for pattern in diagram_patterns:
        matches = list(arch_dir.glob(f"**/{pattern}"))
        for match in matches[:3]:  # Limit to 3 diagrams
            try:
                content = match.read_text()[:3000]  # Limit to 3KB each
                arch_context["diagrams"].append({
                    "path": str(match.relative_to(arch_dir)),
                    "content": content
                })
            except Exception:
                pass

    return arch_context


def load_test_context(
    component: Optional[str],
    repo: str,
    context_dir: Path
) -> dict[str, Any]:
    """
    Load relevant test context.

    Args:
        component: Component name
        repo: Repository name
        context_dir: Path to context-repos directory

    Returns:
        {
            "requirements": "...",    # Test requirements doc
            "patterns": "...",        # Test patterns doc
            "coverage_standards": {}  # Coverage thresholds
        }
    """
    test_context = {
        "requirements": None,
        "patterns": None,
        "coverage_standards": {
            "minimum": 70,
            "target": 80,
            "critical_functions": 100
        }
    }

    test_dir = context_dir / "odh-test-context"
    if not test_dir.exists():
        return test_context

    # Look for test requirements
    req_paths = [
        test_dir / f"tests/{component}.md" if component else None,
        test_dir / "tests/README.md",
        test_dir / "README.md"
    ]

    for req_path in req_paths:
        if req_path and req_path.exists():
            test_context["requirements"] = req_path.read_text()[:5000]
            break

    # Look for test patterns
    pattern_paths = [
        test_dir / "tests/patterns.md",
        test_dir / "tests/best-practices.md"
    ]

    for pattern_path in pattern_paths:
        if pattern_path.exists():
            test_context["patterns"] = pattern_path.read_text()[:3000]
            break

    return test_context


def load_risk_patterns(context_dir: Path) -> dict[str, Any]:
    """
    Load risk patterns for risk analysis.

    Returns:
        {
            "security_patterns": [...],
            "breaking_change_patterns": [...],
            "critical_paths": [...]
        }
    """
    # For now, return hardcoded patterns
    # TODO: Load from docs/RISK_PATTERNS.md when created
    return {
        "security_patterns": [
            {
                "pattern": "auth.*token",
                "description": "Authentication token handling",
                "risk_level": "high"
            },
            {
                "pattern": "password|credential|secret",
                "description": "Credential management",
                "risk_level": "high"
            },
            {
                "pattern": "sql.*query|database.*exec",
                "description": "SQL injection risk",
                "risk_level": "medium"
            }
        ],
        "breaking_change_patterns": [
            {
                "pattern": "API|endpoint|handler",
                "description": "API signature changes",
                "risk_level": "high"
            },
            {
                "pattern": "schema|migration|database",
                "description": "Schema changes",
                "risk_level": "medium"
            }
        ],
        "critical_paths": [
            "auth",
            "operator",
            "controller",
            "webhook",
            "gateway",
            "pipeline"
        ]
    }


def create_analyzer_contexts(
    pr_data: dict[str, Any],
    context_paths: dict[str, str]
) -> dict[str, dict[str, Any]]:
    """
    Create focused context bundles for each analyzer.

    Args:
        pr_data: PR data from pr_extractor.py
        context_paths: Context repo paths from fetch-context.sh

    Returns:
        {
            "risk": {...},
            "test": {...},
            "impact": {...},
            "crossrepo": {...}
        }
    """
    context_dir = Path(context_paths["context_dir"])
    files = pr_data.get("files", [])
    repo = pr_data.get("repo", "")
    component = detect_component_from_files(files, repo)

    # Load shared context
    arch_context = load_architecture_context(component, context_dir)
    test_context = load_test_context(component, repo, context_dir)
    risk_patterns = load_risk_patterns(context_dir)

    # Risk analyzer context
    risk_context = {
        "pr_metadata": {
            "number": pr_data["metadata"]["number"],
            "title": pr_data["metadata"]["title"],
            "author": pr_data["metadata"]["author"],
            "additions": pr_data["metadata"]["additions"],
            "deletions": pr_data["metadata"]["deletions"],
            "changed_files": pr_data["metadata"]["changed_files"]
        },
        "files": files,
        "diff": pr_data["diff"][:50000],  # Limit diff to 50KB
        "is_security_related": is_security_related(pr_data),
        "is_critical_path": is_critical_path(files),
        "risk_patterns": risk_patterns,
        "jira_context": pr_data.get("jira_context", {})
    }

    # Test validator context
    test_validator_context = {
        "pr_metadata": {
            "number": pr_data["metadata"]["number"],
            "changed_files": pr_data["metadata"]["changed_files"]
        },
        "files": files,
        "diff": pr_data["diff"][:50000],
        "test_requirements": test_context["requirements"],
        "test_patterns": test_context["patterns"],
        "coverage_standards": test_context["coverage_standards"],
        "component": component
    }

    # Impact analyzer context
    impact_context = {
        "pr_metadata": {
            "number": pr_data["metadata"]["number"],
            "title": pr_data["metadata"]["title"]
        },
        "files": files,
        "component": component,
        "architecture": arch_context,
        "jira_context": pr_data.get("jira_context", {})
    }

    # Cross-repo analyzer context
    crossrepo_context = {
        "pr_metadata": {
            "number": pr_data["metadata"]["number"],
            "repo": repo
        },
        "files": files,
        "component": component,
        "test_context_available": test_context["requirements"] is not None
    }

    return {
        "risk": risk_context,
        "test": test_validator_context,
        "impact": impact_context,
        "crossrepo": crossrepo_context
    }


def main():
    parser = argparse.ArgumentParser(description="Load and slice context for analyzers")
    parser.add_argument(
        "pr_data_file",
        help="PR data JSON file (from pr_extractor.py or jira_utils.py enrich-pr)"
    )
    parser.add_argument(
        "context_paths_file",
        help="Context paths JSON file (from fetch-context.sh)"
    )
    parser.add_argument(
        "--output-dir",
        default="tmp/contexts",
        help="Output directory for context files (default: tmp/contexts)"
    )

    args = parser.parse_args()

    try:
        # Load PR data
        with open(args.pr_data_file) as f:
            pr_data = json.load(f)

        # Load context paths
        with open(args.context_paths_file) as f:
            context_paths = json.load(f)

        print(f"Loading context for PR #{pr_data['metadata']['number']}...", file=sys.stderr)

        # Create analyzer contexts
        contexts = create_analyzer_contexts(pr_data, context_paths)

        # Write each context to separate file
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        pr_number = pr_data["metadata"]["number"]

        for analyzer_name, context in contexts.items():
            output_file = output_dir / f"{analyzer_name}-{pr_number}.json"
            with open(output_file, 'w') as f:
                json.dump(context, f, indent=2)
            print(f"✓ {analyzer_name} context: {output_file}", file=sys.stderr)

        # Also write summary
        summary = {
            "pr_number": pr_number,
            "repo": pr_data["repo"],
            "component": contexts["risk"].get("component"),
            "contexts": {
                name: str(output_dir / f"{name}-{pr_number}.json")
                for name in contexts.keys()
            }
        }

        summary_file = output_dir / f"summary-{pr_number}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"✓ Summary: {summary_file}", file=sys.stderr)
        print(json.dumps(summary, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
