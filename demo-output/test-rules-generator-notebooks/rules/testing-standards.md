---
description: Cross-cutting testing standards for the notebooks repository
globs: "tests/**/*.py, ntb/**/*.py"
alwaysApply: false
---

# Testing standards — notebooks

1. **Python version:** Target **3.14** (`requires-python` and CI); use **`uv`** and lockfile (`uv sync --locked` / `--group dev` in CI builds).

2. **Default pytest scope:** `pytest.ini` sets `testpaths = tests ntb` and **`collect_ignore = ["tests/containers"]`** so routine runs stay fast. Container tests are **opt-in**: `pytest tests/containers ...`.

3. **Markers** (registered in `pytest.ini`): `openshift`, `cuda`, `rocm`, `buildonlytest`. Use them consistently; `make test` runs `-m 'not buildonlytest'`.

4. **Reporting:** Global `addopts` include coverage (`--cov`, XML for Codecov), JUnit (`junit.xml`), doctests, short tracebacks, strict markers.

5. **Coverage policy** (`pyproject.toml`): measure **`ntb`, `ci`, `scripts`**; omit `tests/*`. Container tests are excluded from default coverage story (see ADR 0006).

6. **Non-Python:** Run **`go test`** for `scripts/buildinputs` in `make test-unit`; keep **Dockerfile.konflux** vs **Dockerfile** alignment via `scripts/check_dockerfile_alignment.sh` (invoked from `make test`).

7. **CI truthfulness:** Regenerated code must match `ci/generate_code.sh` output (`code-quality` job).
