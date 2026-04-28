#!/usr/bin/env python3
"""YAML frontmatter utilities for artifact files.

All artifacts use YAML frontmatter for structured metadata:
    ---
    pr_number: 7292
    decision: WARN
    overall_risk: 55
    ---

    # Markdown content here...

Usage:
    python3 scripts/frontmatter.py read <file>
    python3 scripts/frontmatter.py write <file> <frontmatter.yaml> <body.md>
    python3 scripts/frontmatter.py validate <schema> <file>
    python3 scripts/frontmatter.py schema <schema_name>
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml


# ─── Schema Definitions ───────────────────────────────────────────────────────

SCHEMAS = {
    "pr-analysis": {
        "pr_number": {"type": "int", "required": True},
        "repo": {"type": "str", "required": True},
        "decision": {"type": "str", "required": True, "enum": ["APPROVE", "WARN"]},
        "overall_risk": {"type": "int", "required": True},
        "timestamp": {"type": "str", "required": True},
        "analyzers_complete": {"type": "bool", "required": True},
        "jira_epic": {"type": "str", "required": False},
    },
    "risk-finding": {
        "pr_number": {"type": "int", "required": True},
        "repo": {"type": "str", "required": True},
        "overall_risk": {"type": "int", "required": True},
        "security_risk": {"type": "int", "required": True},
        "breaking_risk": {"type": "int", "required": True},
        "critical_path_risk": {"type": "int", "required": True},
        "dependency_risk": {"type": "int", "required": True},
        "patterns_matched": {"type": "list", "required": False},
        "top_risks": {"type": "list", "required": True},
        "recommendations": {"type": "list", "required": True},
    },
    "test-coverage": {
        "pr_number": {"type": "int", "required": True},
        "coverage_percent": {"type": "int", "required": True},
        "functions_changed": {"type": "int", "required": True},
        "functions_tested": {"type": "int", "required": True},
        "missing_tests": {"type": "list", "required": False},
        "repo_requirements": {"type": "dict", "required": True},
        "meets_standards": {"type": "bool", "required": True},
    },
    "impact-assessment": {
        "pr_number": {"type": "int", "required": True},
        "component": {"type": "str", "required": True},
        "blast_radius": {"type": "str", "required": True, "enum": ["low", "medium", "high"]},
        "affected_components": {"type": "list", "required": True},
        "integration_points": {"type": "list", "required": True},
        "breaking_changes": {"type": "bool", "required": True},
    },
    "crossrepo-intel": {
        "pr_number": {"type": "int", "required": True},
        "affected_test_repos": {"type": "list", "required": True},
        "breaking_tests": {"type": "list", "required": True},
        "related_tests": {"type": "list", "required": False},
        "requires_test_updates": {"type": "bool", "required": True},
    },
}


# ─── Read/Write Functions ─────────────────────────────────────────────────────

def read(file_path: str) -> tuple[dict, str]:
    """
    Parse markdown file with YAML frontmatter.

    Returns:
        (frontmatter_dict, body_markdown)

    Example:
        frontmatter, body = read("artifacts/pr-analyses/pr-7292-analysis.md")
        print(frontmatter["decision"])  # "WARN"
        print(body)  # "# Quality Intelligence Report\n..."
    """
    file = Path(file_path)

    if not file.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    content = file.read_text()

    # Match frontmatter: ^---\n...\n---\n
    match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)

    if not match:
        # No frontmatter, return empty dict and full content as body
        return {}, content

    frontmatter_yaml = match.group(1)
    body = match.group(2)

    frontmatter = yaml.safe_load(frontmatter_yaml) or {}

    return frontmatter, body


def write(file_path: str, frontmatter: dict, body: str) -> None:
    """
    Write markdown file with YAML frontmatter.

    Example:
        frontmatter = {"pr_number": 7292, "decision": "WARN"}
        body = "# Quality Intelligence Report\n..."
        write("artifacts/pr-analyses/pr-7292-analysis.md", frontmatter, body)
    """
    file = Path(file_path)
    file.parent.mkdir(parents=True, exist_ok=True)

    frontmatter_yaml = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)

    content = f"---\n{frontmatter_yaml}---\n{body}"

    file.write_text(content)


# ─── Validation Functions ─────────────────────────────────────────────────────

def validate(schema_name: str, frontmatter: dict) -> None:
    """
    Validate frontmatter against schema.

    Raises:
        ValueError: If validation fails
    """
    if schema_name not in SCHEMAS:
        raise ValueError(f"Unknown schema: {schema_name}")

    schema = SCHEMAS[schema_name]

    # Check required fields
    for field_name, field_spec in schema.items():
        if field_spec.get("required", False):
            if field_name not in frontmatter:
                raise ValueError(f"Missing required field: {field_name}")

    # Check field types
    for field_name, value in frontmatter.items():
        if field_name not in schema:
            # Allow extra fields (forward compatibility)
            continue

        field_spec = schema[field_name]
        expected_type = field_spec["type"]

        # Type checking
        if expected_type == "int" and not isinstance(value, int):
            raise ValueError(f"Field {field_name} must be int, got {type(value).__name__}")
        elif expected_type == "str" and not isinstance(value, str):
            raise ValueError(f"Field {field_name} must be str, got {type(value).__name__}")
        elif expected_type == "bool" and not isinstance(value, bool):
            raise ValueError(f"Field {field_name} must be bool, got {type(value).__name__}")
        elif expected_type == "list" and not isinstance(value, list):
            raise ValueError(f"Field {field_name} must be list, got {type(value).__name__}")
        elif expected_type == "dict" and not isinstance(value, dict):
            raise ValueError(f"Field {field_name} must be dict, got {type(value).__name__}")

        # Enum checking
        if "enum" in field_spec:
            if value not in field_spec["enum"]:
                raise ValueError(f"Field {field_name} must be one of {field_spec['enum']}, got {value}")


def get_schema(schema_name: str) -> dict:
    """Get schema definition."""
    if schema_name not in SCHEMAS:
        raise ValueError(f"Unknown schema: {schema_name}")
    return SCHEMAS[schema_name]


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Frontmatter utilities")
    subparsers = parser.add_subparsers(dest='command', required=True)

    # read command
    read_parser = subparsers.add_parser('read', help='Read frontmatter from file')
    read_parser.add_argument('file', help='File path')
    read_parser.add_argument('--body', action='store_true', help='Print body instead of frontmatter')

    # write command
    write_parser = subparsers.add_parser('write', help='Write file with frontmatter')
    write_parser.add_argument('file', help='File path')
    write_parser.add_argument('--frontmatter', required=True, help='Frontmatter YAML file')
    write_parser.add_argument('--body', required=True, help='Body markdown file')

    # validate command
    validate_parser = subparsers.add_parser('validate', help='Validate frontmatter')
    validate_parser.add_argument('schema', help='Schema name')
    validate_parser.add_argument('file', help='File to validate')

    # schema command
    schema_parser = subparsers.add_parser('schema', help='Print schema definition')
    schema_parser.add_argument('name', help='Schema name')

    args = parser.parse_args()

    try:
        if args.command == 'read':
            frontmatter, body = read(args.file)
            if args.body:
                print(body)
            else:
                print(yaml.dump(frontmatter, default_flow_style=False, sort_keys=False))

        elif args.command == 'write':
            # Read frontmatter YAML
            with open(args.frontmatter) as f:
                frontmatter = yaml.safe_load(f)

            # Read body markdown
            with open(args.body) as f:
                body = f.read()

            write(args.file, frontmatter, body)
            print(f"Written to {args.file}")

        elif args.command == 'validate':
            frontmatter, _ = read(args.file)
            validate(args.schema, frontmatter)
            print(f"✓ Valid {args.schema} schema")

        elif args.command == 'schema':
            schema = get_schema(args.name)
            print(yaml.dump(schema, default_flow_style=False, sort_keys=False))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
