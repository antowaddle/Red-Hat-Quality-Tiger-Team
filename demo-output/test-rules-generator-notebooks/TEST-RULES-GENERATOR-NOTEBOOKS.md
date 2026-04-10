# Test Rules Generator Analysis: notebooks

## Repository Profile
- **Type:** Monorepo for **containerized Open Data Hub / OpenShift AI workbench images** (Jupyter, runtimes/Elyra, Code Server, RStudio), plus shared Python (`ntb`), CI scripts, and manifests.
- **Language:** Python (primary), with **Go** tests for `scripts/buildinputs`, **TypeScript** for Playwright browser tests, **shell** for papermill/K8s flows, **R** in image-local RStudio smoke scripts.
- **Test frameworks:** **pytest** (with **pytest-cov**, **pytest-subtests**, **allure-pytest**, **doctest**), **unittest** (small CI helpers), **Go `go test` / gotestsum**, **Playwright** (browser), **manual notebooks** under `tests/manual/`.
- **Test types found:** **Unit** (`tests/unit/`, script helpers), **static/config** (`tests/test_main.py`, `make test`), **container/integration** (`tests/containers/` + Testcontainers), **cluster/E2E-style** (`ci/cached-builds/make_test.py` + `scripts/test_jupyter_with_papermill.sh` on provisioned K8s), **browser E2E** (`tests/browser/`), **security/scan** (Trivy in GHA + `security.yaml`), **manual** GPU/notebook notebooks.

## Test Discovery Summary

### Test Files Found
| Area | Paths (representative) |
|------|-------------------------|
| Static / manifest | `tests/test_main.py`, `tests/manifests.py` |
| Unit | `tests/unit/scripts/test_pylocks_generator.py` |
| Tutorial / samples | `tests/pytest_tutorial/test_01_intro.py` |
| Container (pytest) | `tests/containers/base_image_test.py`, `tests/containers/workbenches/**/*.py`, `tests/containers/runtimes/runtime_test.py` |
| Browser | `tests/browser/tests/*.ts` (e.g. `testcontainers.ts`), `playwright.config.ts` |
| Manual | `tests/manual/*.ipynb` |
| Go | `scripts/buildinputs/*_test.go` |
| Per-image notebooks | `jupyter/**/test/test_notebook.ipynb`, `codeserver/**/test/test_startup.py`, `rstudio/**/test/test_script.R` |

### Test Directories
- `tests/` — root pytest config consumers; **`tests/containers` excluded from default collection** in `pytest.ini` (heavy imports).
- `tests/unit/` — mirrors `scripts/` / tooling under test.
- `tests/containers/` — image/runtime tests; **`conftest.py`** for `--image`, Testcontainers/Ryuk, fixtures (`workbench_image`, `jupyterlab_image`, etc.).
- `tests/browser/` — Playwright project + Dockerfile for test image.
- `tests/manual/` — non-CI manual validation.

### Framework Detection
- **pytest** — `pytest.ini`, `pyproject.toml` dev deps (`pytest`, `pytest-cov`, `allure-pytest`, `pytest-subtests`, `testcontainers`, `docker`, `podman`, …).
- **uv** — `uv sync --locked`; CI uses `astral-sh/setup-uv` with Python **3.14** (per `pyproject.toml` / workflows).
- **Makefile** — `make test`, `make test-unit`, `make test-integration`, `test-%` (papermill), `validate-*-image` targets.
- **No `tox.ini`** in repo root.
- **Ruff / Pyright / prek** — `code-quality.yaml` (not pytest, but quality gate alongside tests).

## Generated Rules

### testing-standards.md
---

# Testing standards — notebooks

1. **Python version:** Target **3.14** (`requires-python` and CI); use **`uv`** and lockfile (`uv sync --locked` / `--group dev` in CI builds).

2. **Default pytest scope:** `pytest.ini` sets `testpaths = tests ntb` and **`collect_ignore = ["tests/containers"]`** so routine runs stay fast. Container tests are **opt-in**: `pytest tests/containers ...`.

3. **Markers** (registered in `pytest.ini`): `openshift`, `cuda`, `rocm`, `buildonlytest`. Use them consistently; `make test` runs `-m 'not buildonlytest'`.

4. **Reporting:** Global `addopts` include coverage (`--cov`, XML for Codecov), JUnit (`junit.xml`), doctests, short tracebacks, strict markers.

5. **Coverage policy** (`pyproject.toml`): measure **`ntb`, `ci`, `scripts`**; omit `tests/*`. Container tests are excluded from default coverage story (see ADR 0006).

6. **Non-Python:** Run **`go test`** for `scripts/buildinputs` in `make test-unit`; keep **Dockerfile.konflux** vs **Dockerfile** alignment via `scripts/check_dockerfile_alignment.sh` (invoked from `make test`).

7. **CI truthfulness:** Regenerated code must match `ci/generate_code.sh` output (`code-quality` job).

---

### unit-tests.md
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

---

### image-tests.md
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

## "Multi-layer" image validation (factual)
The repository does **not** define a single test named "five-layer"; validation is **layered in practice**:
1. **Static:** pytest on repo config + Dockerfile parity script.
2. **Post-build container pytest** (Testcontainers) on the **just-built image**.
3. **Optional K8s path:** `has_tests.py` + `make_test.py` deploys via Makefile and runs workload checks including **papermill** (`scripts/test_jupyter_with_papermill.sh` pattern for local `make test-%`).
4. **OpenShift-marked** pytest when a cluster is provisioned (`-m 'openshift and not cuda and not rocm'`).
5. **Trivy** (image or FS) and other checks (e.g. FIPS payload) in the same build workflow.

**Skopeo:** Pydantic models parse **image history** (`HistoryLayer`) to extract **ARG** declarations from layer `created_by` strings — supporting **supply-chain / build-arg introspection**, not a fixed layer count test.

## Per-image notebooks
Under each stack (e.g. `jupyter/datascience/.../test/test_notebook.ipynb`), notebooks are executed in-cluster via papermill as part of the broader validation story (not the default `make test` pytest collection).

---

### e2e-tests.md
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

---

## Pattern Analysis

### Test Structure Patterns
- **Flat + hierarchical:** Top-level `tests/test_main.py` (large manifest/pylock alignment suite); **`Test*` classes** in `base_image_test.py`; workbench-specific modules under `tests/containers/workbenches/`.
- **Heavy `conftest` at `tests/containers/`** only for container tests; root `tests/conftest.py` only configures logging.
- **Optional imports:** `TYPE_CHECKING` blocks for pytest types, `pytest_subtests`.

### Naming Conventions
- **pytest discovery:** `test_*.py`, `*_test.py`, `Test*` classes, `test_*` functions (`pytest.ini`).
- **Container modules:** `*_test.py` (e.g. `jupyterlab_test.py`, `accelerator_image_test.py`).
- **Markers** encode **runtime needs** (`cuda`, `rocm`, `openshift`).

### Fixture / Setup Patterns
- **CLI-driven images:** `--image` repeated for multiple images.
- **Skip helpers:** `skip_if_not_workbench_image`, label-based skips for RStudio vs Jupyter.
- **Testcontainers:** `DockerContainer` + `sleep infinity` + `exec`; `NotebookContainer` wrapper for stop.
- **Subtests:** `subtests.test(...)` for permutations (paths, FIPS checks, ldd results).

### Assertion Patterns
- Plain **`assert`** with messages on critical exec results (`ecode == 0`).
- **Allowlists** in ELF test for known vendor/library gaps (CUDA, ROCm, FFmpeg, ODBC, etc.) — document new skips with JIRA-style IDs where present.
- **Packaging:** `packaging.version` / markers in `test_main.py` for dependency consistency.

### Image Testing Patterns
- **Labels:** `io.openshift.build.source-location` and **`name`** label drive skips and AIPCC detection (`uv.lock.d`, `PIP_INDEX_URL`).
- **Remote vs local:** Prefer local `docker inspect`; fall back to **skopeo** for registry-only refs.
- **GPU:** Separate modules (`gpu_library_loading_test.py`, `accelerator_image_test.py`) and markers for CUDA/ROCm.

## Key Patterns Extracted

### Most Common Patterns
- **pytest + uv** everywhere; **strict marker registration**.
- **Ignore `tests/containers` by default** to keep collection fast.
- **Testcontainers + Podman** in CI with **Ryuk disabled** and explicit socket env vars.
- **Parametrized `--image`** for one test suite across all built tags.
- **Codecov** for Python and Go coverage from **`code-quality.yaml`**.

### Unique Conventions
- **`make test`** = **fast static pytest** + **Dockerfile Konflux alignment script** (not full image pytest).
- **Dual Dockerfile** maintenance checked by stripping comments/LABEL blocks and comparing.
- **`ntb` package** tested under `ntb` testpath alongside `tests/`.
- **OpenShift CI parity** encoded in **`make_test.py`** comments and behavior.
- **Per-image `test_notebook.ipynb`** tree for papermill validation tied to image lineage (minimal + datascience for inherited stacks).

## Recommendations

### Test Coverage Gaps
- **`tests/containers` excluded** from default runs — risk of **only CI build jobs** catching regressions unless authors run integration locally.
- **s390x:** Makefile image tests skipped — coverage gap on that arch for Elyra/papermill paths.
- **Browser tests:** Separate image build path; ensure **DEFAULT_TEST_IMAGE** stays aligned with production workbench images.

### Suggested Improvements
- Document **`--image`** and marker matrix in contributor docs (single page).
- Add **smoke marker** subset for quicker container runs in pre-commit (optional).
- Consolidate **allowlist comments** in ELF test into a tracked issue list for tech debt visibility.

### Additional Rules to Consider
- **Konflux vs ODH:** `KONFLUX` must match between build and tests (already in `AGENTS.md`); encode in test rules for any new image-level assertions.
- **AIPCC / rh-index:** When `PIP_INDEX_URL` absent in env, tests may hit public PyPI — keep **`cowsay`-style** packages that exist on restricted indexes.
- **Security:** Trivy FS scan regenerates locks with `uv lock` per `security.yaml` — account for that in local "repro CI" runs.

## CI/CD Integration

### Test Workflows
| Workflow | Role |
|----------|------|
| **`code-quality.yaml`** | `make test` (pytest static + Dockerfile check), **Go tests** + Codecov, **yamllint/json/hadolint/kustomize**, **`ci/generate_code.sh`**, **prek** |
| **`build-notebooks-pr.yaml` / `build-notebooks-TEMPLATE.yaml`** | Matrix build → **pytest Testcontainers** → optional **K8s `make_test.py`** → **OpenShift pytest** → **Trivy** → further checks |
| **`security.yaml`** | Trivy FS + SARIF upload |
| **`build-browser-tests.yaml`**, **`test-playwright-action.yaml`** | Browser test image and action validation |
| **`test-*` workflows** (`test-install-podman`, `test-provision-k8s`, …) | **Action/component tests** for reusable GHA pieces |

### Automated Test Execution
- **PR path:** `gen_gha_matrix_jobs.py` selects targets from diffs; builds use Podman + cache; **pytest** runs against **`OUTPUT_IMAGE`**.
- **Artifacts:** `coverage.xml`, `junit.xml`, Go JUnit, Codecov uploads (`pytest-tests` and `go-tests` jobs).
- **Local parity:** `make test` ≈ CI pytest slice; **`make test-integration`** for container tests; **full parity** requires Podman/K8s and same env vars as template.

---

*Analysis based on repository contents under `/Users/acoughli/qualityTigerTeam/notebooks/` as of the scan for this report.*
