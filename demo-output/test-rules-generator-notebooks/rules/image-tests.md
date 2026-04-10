---
description: Image and container test patterns for validating built OCI images
globs: "tests/containers/**/*.py"
alwaysApply: false
---

# Image / container tests — notebooks

## Role
Validate **built OCI images** using **Testcontainers** (`testcontainers.core.container.DockerContainer`), **docker-py**, optional **skopeo** (`tests/containers/skopeo_utils.py`) for remote config/history, and **Allure** steps in some suites.

## Invocation
- **Local:** `make test-integration PYTEST_ARGS="--image=<ref>"` runs
  `pytest tests/containers -m 'not openshift and not cuda and not rocm' ...`
- **CI (build template):** After `make <target>`,
  `uv run pytest tests/containers -m 'not openshift and not cuda and not rocm' --image="$OUTPUT_IMAGE"`
  with `DOCKER_HOST` / `TESTCONTAINERS_*` set for **rootful Podman**; **Ryuk disabled** in CI to avoid docker.io flake.

## `tests/containers/conftest.py` patterns
- **`--image`** CLI option, **parametrized `image` fixture** (`pytest_generate_tests`).
- **`get_image_metadata` / `Image`**: labels and env from Docker inspect or skopeo; handles Podman label quirks.
- **Fixtures** skip by image **label `name`** (e.g. `workbench_image`, `jupyterlab_image`, `runtime_image`, `cuda_image`, `rocm_image`).
- **Session hooks:** Docker ping, Ryuk socket path (Linux vs macOS Podman machine), optional Reaper startup.
- **`test_frame`**: manual resource cleanup (defer-like) for networks/subprocesses.

## Representative checks (`base_image_test.py`)
- **ELF / `ldd`:** Scan executables under `/bin`, `/lib`, `/lib64`, `/opt/app-root` for broken dynamic deps (with allowlists for GPU/FIPS/RPM edge cases); uses **`pytest_subtests`**.
- **CLI smoke:** `oc version`, `skopeo --version` (skipped on RStudio where absent).
- **Writable venv:** `pip install cowsay` and run module.
- **FIPS-related:** Subtests around fake `/proc/sys/crypto/fips_enabled` and `oc` behavior.
- **File permissions:** `stat` on `/opt/app-root/...` vs expected mode/uid/gid.

## Multi-layer image validation
Validation is **layered in practice**:
1. **Static:** pytest on repo config + Dockerfile parity script.
2. **Post-build container pytest** (Testcontainers) on the **just-built image**.
3. **Optional K8s path:** `has_tests.py` + `make_test.py` deploys via Makefile and runs workload checks including **papermill**.
4. **OpenShift-marked** pytest when a cluster is provisioned (`-m 'openshift and not cuda and not rocm'`).
5. **Trivy** (image or FS) and other checks (e.g. FIPS payload) in the same build workflow.

**Skopeo:** Pydantic models parse **image history** (`HistoryLayer`) to extract **ARG** declarations from layer `created_by` strings — supporting **supply-chain / build-arg introspection**.

## Per-image notebooks
Under each stack (e.g. `jupyter/datascience/.../test/test_notebook.ipynb`), notebooks are executed in-cluster via papermill as part of the broader validation story (not the default `make test` pytest collection).

## Best Practices Summary

### DO
- Use `--image` flag to parametrize across all built image tags
- Register markers (`openshift`, `cuda`, `rocm`) for environment-gated tests
- Use `pytest_subtests` for permutation-heavy checks (ELF, FIPS)
- Disable Ryuk in CI and use explicit cleanup
- Skip tests based on image labels, not hardcoded names

### DON'T
- Import container test dependencies in unit tests
- Assume docker.io availability in CI (use Podman socket)
- Hard-code image paths — use `--image` CLI option
- Forget cleanup in `test_frame` patterns

## Implementation Checklist

### Before writing tests
- [ ] Determine which image labels trigger/skip this test
- [ ] Check if a similar test exists in `base_image_test.py`
- [ ] Verify Docker/Podman socket configuration

### During implementation
- [ ] Use `conftest.py` fixtures for image metadata
- [ ] Add appropriate markers for GPU/OpenShift gating
- [ ] Use `subtests` for permutation-based validations

### After implementation
- [ ] Run `make test-integration --image=<ref>` locally
- [ ] Verify marker-based skipping works correctly
- [ ] Ensure cleanup runs even on failure
