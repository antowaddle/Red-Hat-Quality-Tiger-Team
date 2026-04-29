#!/usr/bin/env python3
"""Kubernetes resource rename detector.

Detects when ConfigMaps, Secrets, CRDs, Services, or other K8s resources
are renamed in a PR. These are high-risk changes that require cross-repo coordination.

Usage:
    python3 scripts/k8s_resource_detector.py <diff_file>

Example:
    python3 scripts/k8s_resource_detector.py tmp/pr-489.diff
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


# Patterns for detecting K8s resource name changes
RESOURCE_PATTERNS = {
    "configmap": [
        r'name:\s*["\']([a-z0-9-]+)["\']',  # YAML name: "foo" or name: 'foo'
        r'Name:\s*["\']([a-z0-9-]+)["\']',  # Go Name: "foo"
        r'configMapName:\s*["\']?([a-z0-9-]+)["\']?',
        r'get\s+configmap\s+([a-z0-9-]+)',  # kubectl/oc commands
        r'ConfigMapName\s*=\s*["\']([a-z0-9-]+)["\']',  # Go constants
        r'name:\s+([a-z0-9-]+)\s*$',  # YAML name: foo (unquoted, end of line)
    ],
    "secret": [
        r'name:\s*["\']?([a-z0-9-]+)["\']?\s*.*#.*[Ss]ecret',
        r'name:\s*["\']?([a-z0-9-]+)["\']?\s*\n.*kind:\s*Secret',
        r'secretName:\s*["\']?([a-z0-9-]+)["\']?',
        r'get\s+secret\s+([a-z0-9-]+)',
    ],
    "crd": [
        r'kind:\s*CustomResourceDefinition.*\n.*name:\s*([a-z0-9.-]+)',
        r'apiVersion:.*\n.*kind:\s*([A-Z][a-zA-Z]+)',  # Custom resource kinds
    ],
    "service": [
        r'name:\s*["\']?([a-z0-9-]+)["\']?\s*.*#.*[Ss]ervice',
        r'name:\s*["\']?([a-z0-9-]+)["\']?\s*\n.*kind:\s*Service',
        r'serviceName:\s*["\']?([a-z0-9-]+)["\']?',
    ]
}


def extract_resource_names_from_lines(lines: list[str], patterns: list[str]) -> set[str]:
    """Extract resource names from diff lines using patterns.

    Args:
        lines: Lines from diff (added or deleted)
        patterns: Regex patterns to match

    Returns:
        Set of resource names found
    """
    names = set()

    for line in lines:
        for pattern in patterns:
            matches = re.findall(pattern, line, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if match and len(match) > 2:  # Filter out very short matches
                    names.add(match)

    return names


def detect_resource_renames(diff_content: str) -> dict[str, Any]:
    """Detect Kubernetes resource renames in a diff.

    Focus on YAML metadata name changes (- name: "old" + name: "new")
    and template/manifest changes, not test code references.

    Args:
        diff_content: Git diff content

    Returns:
        Dictionary with detected renames and metadata
    """
    lines = diff_content.split("\n")

    # Look for paired changes in yaml/template files
    # Pattern: - name: "old" followed by + name: "new"
    renames = []

    for i, line in enumerate(lines):
        # Look for deleted YAML name field
        if line.startswith("-") and re.search(r'^\s*-\s+name:\s*["\']?([a-z0-9-]+)["\']?', line):
            deleted_match = re.search(r'name:\s*["\']?([a-z0-9-]+)["\']?', line)
            if not deleted_match:
                continue
            old_name = deleted_match.group(1)

            # Check next few lines for corresponding add
            for j in range(i+1, min(i+5, len(lines))):
                if lines[j].startswith("+") and re.search(r'^\s*\+\s+name:\s*["\']?([a-z0-9-]+)["\']?', lines[j]):
                    added_match = re.search(r'name:\s*["\']?([a-z0-9-]+)["\']?', lines[j])
                    if added_match:
                        new_name = added_match.group(1)
                        if new_name != old_name:
                            # Check if this is in a yaml/template file
                            in_yaml = False
                            for k in range(max(0, i-20), i):
                                if '.yaml' in lines[k] or '.tmpl' in lines[k]:
                                    in_yaml = True
                                    break

                            if in_yaml or ('.yaml' in lines[0] or '.tmpl' in lines[0]):
                                renames.append({
                                    "resource_type": "configmap",  # Assume configmap for now
                                    "old_name": old_name,
                                    "new_name": new_name,
                                    "risk_level": "CRITICAL",
                                    "reason": f"ConfigMap rename detected in manifest: {old_name} → {new_name}"
                                })

    # Also check for Go Name: field changes in same pattern
    for i, line in enumerate(lines):
        if line.startswith("-") and 'Name:' in line:
            deleted_match = re.search(r'Name:\s*["\']([a-z0-9-]+)["\']', line)
            if not deleted_match:
                continue
            old_name = deleted_match.group(1)

            # Check next few lines
            for j in range(i+1, min(i+5, len(lines))):
                if lines[j].startswith("+") and 'Name:' in lines[j]:
                    added_match = re.search(r'Name:\s*["\']([a-z0-9-]+)["\']', lines[j])
                    if added_match:
                        new_name = added_match.group(1)
                        if new_name != old_name and "test" not in lines[i].lower():
                            # This is a code change, not test
                            renames.append({
                                "resource_type": "configmap",
                                "old_name": old_name,
                                "new_name": new_name,
                                "risk_level": "CRITICAL",
                                "reason": f"Resource name changed in code: {old_name} → {new_name}"
                            })

    # Deduplicate
    unique_renames = []
    seen = set()
    for r in renames:
        key = (r["old_name"], r["new_name"])
        if key not in seen:
            seen.add(key)
            unique_renames.append(r)

    return {
        "has_renames": len(unique_renames) > 0,
        "renames": unique_renames,
        "requires_cross_repo_search": len(unique_renames) > 0
    }


def main():
    parser = argparse.ArgumentParser(
        description="Detect Kubernetes resource renames in PR diff"
    )
    parser.add_argument(
        "diff_file",
        help="Path to diff file"
    )
    parser.add_argument(
        "--output",
        help="Output file for JSON results (default: stdout)"
    )

    args = parser.parse_args()

    diff_path = Path(args.diff_file)
    if not diff_path.exists():
        print(f"Error: Diff file not found: {diff_path}", file=sys.stderr)
        sys.exit(1)

    with open(diff_path) as f:
        diff_content = f.read()

    results = detect_resource_renames(diff_content)

    # Output results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"✅ Results written to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(results, indent=2))

    # Print warnings if renames detected
    if results["has_renames"]:
        print("\n🚨 KUBERNETES RESOURCE RENAME DETECTED!", file=sys.stderr)
        for rename in results["renames"]:
            new_name = rename.get('new_name', rename.get('likely_new_names', ['unknown'])[0] if 'likely_new_names' in rename else 'unknown')
            print(f"  • {rename['resource_type'].upper()}: {rename['old_name']} → {new_name}", file=sys.stderr)
        print("\n⚠️  Cross-repo search REQUIRED - other repos may hardcode these names", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
