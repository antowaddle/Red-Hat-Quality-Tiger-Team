---
description: Unit test patterns and conventions for the notebooks repository
globs: "tests/unit/**/*.py"
alwaysApply: false
---

# Unit tests — notebooks

## Layout
- Place tests under **`tests/unit/`** and mirror source layout (e.g. `tests/unit/scripts/` for `scripts/pylocks_generator.py`).

## Conventions
- **Imports:** `from __future__ import annotations` where used elsewhere; standard **`pytest`** fixtures and **`assert`** style.
- **Repo root:** Resolve via `Path(__file__).resolve().parents[...]` or shared `tests._common.PROJECT_ROOT`.
- **Temp data:** `tmp_path` for lockfile snippets; optional **`pytest.skip`** when optional fixtures (e.g. real lockfile) missing.
- **Scope:** Pure logic (parsing dates, exclude-newer from headers), no Docker.

## Commands
- `./uv run pytest tests/unit/`
- `make test-unit` — pytest (excluding `tests/containers`) **plus** `go test -C scripts/buildinputs -cover ./...`.

## Best Practices Summary

### DO
- Mirror the source tree layout under `tests/unit/`
- Use `tmp_path` for ephemeral test data
- Keep unit tests free of Docker/container dependencies
- Use `pytest.skip` when optional fixtures are unavailable
- Run via `make test-unit` to include both Python and Go tests

### DON'T
- Import `testcontainers` or `docker` in unit tests
- Depend on external services or network access
- Hard-code file paths — use `PROJECT_ROOT` or `Path(__file__)`

## Implementation Checklist

### Before writing tests
- [ ] Identify the source module being tested
- [ ] Create matching directory under `tests/unit/`
- [ ] Verify `pytest.ini` markers if needed

### During implementation
- [ ] Use `assert` with descriptive messages
- [ ] Leverage `tmp_path` for file operations
- [ ] Mock external dependencies

### After implementation
- [ ] Run `make test-unit` to verify
- [ ] Check coverage with `--cov` flag
- [ ] Ensure strict markers pass
