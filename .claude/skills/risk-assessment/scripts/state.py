#!/usr/bin/env python3
"""State persistence utility for quality check orchestration.

Survives context compression by storing state in YAML files that are read
via Bash/Python scripts, not loaded into LLM context.

Usage:
    python3 scripts/state.py init <file> key=value ...
    python3 scripts/state.py set <file> key=value ...
    python3 scripts/state.py get <file> <key>
    python3 scripts/state.py read <file>
    python3 scripts/state.py write-ids <file> <id1> <id2> ...
    python3 scripts/state.py read-ids <file>
"""

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


def parse_kv_pairs(args: list[str]) -> dict[str, Any]:
    """
    Parse key=value pairs from command line arguments.

    Examples:
        ["pr_number=7292", "headless=true"]
        -> {"pr_number": 7292, "headless": True}

    Type inference:
        - "true"/"false" -> bool
        - Numeric strings -> int
        - Everything else -> str
    """
    result = {}
    for arg in args:
        if "=" not in arg:
            raise ValueError(f"Invalid key=value pair: {arg}")

        key, value = arg.split("=", 1)

        # Type inference
        if value.lower() == "true":
            result[key] = True
        elif value.lower() == "false":
            result[key] = False
        elif value.isdigit():
            result[key] = int(value)
        else:
            result[key] = value

    return result


def init(file_path: str, **kwargs) -> None:
    """Initialize state file with key-value pairs."""
    file = Path(file_path)
    file.parent.mkdir(parents=True, exist_ok=True)

    with open(file, 'w') as f:
        yaml.dump(kwargs, f, default_flow_style=False, sort_keys=False)


def set_values(file_path: str, **kwargs) -> None:
    """Update keys in existing state file (preserves other keys)."""
    file = Path(file_path)

    # Read existing state
    if file.exists():
        with open(file) as f:
            state = yaml.safe_load(f) or {}
    else:
        state = {}

    # Update with new values
    state.update(kwargs)

    # Write back
    with open(file, 'w') as f:
        yaml.dump(state, f, default_flow_style=False, sort_keys=False)


def read(file_path: str) -> dict:
    """Read entire state file as dictionary."""
    file = Path(file_path)

    if not file.exists():
        return {}

    with open(file) as f:
        return yaml.safe_load(f) or {}


def get(file_path: str, key: str) -> Any:
    """Get single value from state file."""
    state = read(file_path)
    return state.get(key)


def write_ids(file_path: str, *ids: str) -> None:
    """
    Write ID list to file (one per line, deduplicated).

    Example:
        write_ids("tmp/analyzer-ids.txt", "risk-7292", "test-7292", "risk-7292")
        -> File contains:
           risk-7292
           test-7292
    """
    file = Path(file_path)
    file.parent.mkdir(parents=True, exist_ok=True)

    # Deduplicate while preserving order
    unique_ids = []
    seen = set()
    for id in ids:
        if id not in seen:
            unique_ids.append(id)
            seen.add(id)

    with open(file, 'w') as f:
        f.write('\n'.join(unique_ids) + '\n')


def read_ids(file_path: str) -> list[str]:
    """Read ID list from file (one per line)."""
    file = Path(file_path)

    if not file.exists():
        return []

    with open(file) as f:
        return [line.strip() for line in f if line.strip()]


def main():
    parser = argparse.ArgumentParser(description="State persistence utility")
    subparsers = parser.add_subparsers(dest='command', required=True)

    # init command
    init_parser = subparsers.add_parser('init', help='Initialize state file')
    init_parser.add_argument('file', help='State file path')
    init_parser.add_argument('pairs', nargs='*', help='key=value pairs')

    # set command
    set_parser = subparsers.add_parser('set', help='Update state file')
    set_parser.add_argument('file', help='State file path')
    set_parser.add_argument('pairs', nargs='+', help='key=value pairs')

    # get command
    get_parser = subparsers.add_parser('get', help='Get single value')
    get_parser.add_argument('file', help='State file path')
    get_parser.add_argument('key', help='Key to retrieve')

    # read command
    read_parser = subparsers.add_parser('read', help='Read entire state file')
    read_parser.add_argument('file', help='State file path')

    # write-ids command
    write_ids_parser = subparsers.add_parser('write-ids', help='Write ID list')
    write_ids_parser.add_argument('file', help='File path')
    write_ids_parser.add_argument('ids', nargs='+', help='IDs to write')

    # read-ids command
    read_ids_parser = subparsers.add_parser('read-ids', help='Read ID list')
    read_ids_parser.add_argument('file', help='File path')

    args = parser.parse_args()

    try:
        if args.command == 'init':
            kv_pairs = parse_kv_pairs(args.pairs)
            init(args.file, **kv_pairs)

        elif args.command == 'set':
            kv_pairs = parse_kv_pairs(args.pairs)
            set_values(args.file, **kv_pairs)

        elif args.command == 'get':
            value = get(args.file, args.key)
            if value is not None:
                print(value)
            else:
                sys.exit(1)  # Key not found

        elif args.command == 'read':
            state = read(args.file)
            print(yaml.dump(state, default_flow_style=False, sort_keys=False))

        elif args.command == 'write-ids':
            write_ids(args.file, *args.ids)

        elif args.command == 'read-ids':
            ids = read_ids(args.file)
            print(' '.join(ids))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
