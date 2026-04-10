---
description: End-to-end and browser test patterns for notebooks workbench validation
globs: "tests/browser/**/*.ts, ci/**/*.py"
alwaysApply: false
---

# End-to-end and browser tests — notebooks

## Kubernetes / OpenShift (Makefile + Python driver)
- **`ci/cached-builds/make_test.py`:** Creates namespace, `kubectl` context, runs **`make deploy*-<target>`**, waits for pod stability, then invokes validation (including papermill flows where applicable). Mirrors **OpenShift release** job patterns (documented in file header).
- **Gated in CI:** Runs only if `has_tests.py` reports tests and **provision-k8s** succeeds; **skipped on `linux/s390x`** for runtime Elyra pip install limitations.
- **`scripts/test_jupyter_with_papermill.sh`:** Used from **`make test-<notebook>`** after deploy; copies imagestream "source of truth" and `test_notebook.ipynb` into pod; **failure if output contains `FAILED`**.

## Browser (Playwright)
- **`tests/browser/`:** Playwright + **testcontainers-node** setup (`testcontainers.ts`) sets `DOCKER_HOST` / Podman socket and Ryuk flags.
- **Workflows:** `build-browser-tests.yaml` builds/pushes multi-arch test image; `test-playwright-action.yaml` validates the **Playwright action** with image from `playwright.config.ts` (`DEFAULT_TEST_IMAGE`).
- **Classification:** UI/E2E against workbench UIs in containerized browser — separate from pytest container suites.

## Manual
- **`tests/manual/`** GPU/pytorch/tensorflow notebooks — documented manual validation, not wired to default CI pytest.

## Best Practices Summary

### DO
- Use `make_test.py` pattern for K8s deployment validation
- Leverage `has_tests.py` to skip when no tests are relevant
- Use Playwright + testcontainers-node for browser-based E2E
- Wait for pod stability before running validation scripts
- Use papermill for notebook execution validation

### DON'T
- Run E2E tests without a provisioned cluster
- Assume s390x support for Elyra/papermill paths
- Mix browser E2E with container pytest suites
- Skip cleanup of namespaces and deployed resources

## Implementation Checklist

### Before writing tests
- [ ] Confirm cluster access (OpenShift or Kind)
- [ ] Check if `has_tests.py` will detect the new test
- [ ] Identify the correct `make deploy*-<target>` pattern

### During implementation
- [ ] Use papermill for notebook execution flows
- [ ] Add proper wait strategies for pod readiness
- [ ] Handle cleanup in all exit paths

### After implementation
- [ ] Verify with `make test-<target>` locally
- [ ] Confirm CI workflow detects and runs the test
- [ ] Check s390x/GPU marker exclusions are correct
