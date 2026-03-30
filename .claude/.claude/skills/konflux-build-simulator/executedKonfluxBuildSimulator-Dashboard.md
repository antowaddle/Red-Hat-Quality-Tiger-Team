# Konflux Build Simulator Validation — odh-dashboard

**Date**: 2026-03-30
**Repository**: https://github.com/opendatahub-io/odh-dashboard

---

## Generated Files Reviewed

| # | File | Location |
|---|------|----------|
| 1 | GitHub Actions Workflow | `odh-dashboard/.github/workflows/konflux-build-simulator.yml` |
| 2 | Local Validation Script | `odh-dashboard/scripts/validate-konflux-build.sh` |
| 3 | Documentation | `odh-dashboard/docs/konflux-build-simulator.md` |
| 4 | Generation Report | `odh-dashboard-konflux-sim-report.md` |

---

## Overall Verdict

| File | Structure | Logic | Verdict |
|------|-----------|-------|---------|
| Workflow YAML | Valid | Broken | **Will not work** |
| Shell script | Valid (bash -n passes) | Broken | **Will not work** |
| Documentation | Well-written | Inaccurate | **Misleading** |
| Report | Good analysis | Wrong details | **Partially accurate** |

---

## 1. `.github/workflows/konflux-build-simulator.yml` — Workflow

### What Passes

- YAML structure is valid (correct indentation, no tabs)
- `name`, `on`, `jobs`, `runs-on` all present and correct
- Trigger paths (`Dockerfile`, `frontend/**`, `backend/**`, `packages/**`, `manifests/**`) are sensible
- Branch filters (`main`, `v*`, `release-*`, `f/*`) match common patterns
- Kustomize manifest validation job is sound
- Cleanup step uses `if: always()` correctly
- Summary job uses `needs` and `if: always()` correctly
- Script is executable (chmod 755)

### CRITICAL Issues

**1. Module Federation validation will ALWAYS FAIL**

The workflow assumes `curl http://localhost:8080/_mf/{module}/remoteEntry.js` will return remote entries from within the running container. But looking at the actual backend code (`backend/src/routes/module-federation.ts`), the `/_mf/{name}` routes are **proxies to external Kubernetes services** (separate pods running at port 8043). They are NOT files served locally from the container. There is a fallback route that returns **404 for all `/_mf/*` requests** when the proxy targets don't exist. Running this container standalone (outside a cluster) means all 10 MF checks would fail, causing the entire `build-validation` job to fail every time.

**2. `curl` may not exist inside the container**

The base image is `registry.access.redhat.com/ubi9/nodejs-22:latest`. UBI9 minimal/nodejs images do not ship `curl` by default. The steps `docker exec test-dashboard curl ...` would fail with `command not found`. The workflow should either install curl into the image, use `wget`, or test from outside the container with `curl http://localhost:8080/` (the port is mapped at `-p 8080:8080`).

**3. Container startup may crash outside cluster**

The backend (`backend/src/server.ts`) references Kubernetes service account CA paths (`/var/run/secrets/kubernetes.io/serviceaccount/ca.crt`). While these are logged warnings not hard failures, the app's plugins (`fastify-autoload` for `plugins/` directory) likely include Kubernetes client initialization. Running this outside a cluster may cause startup failures that aren't accounted for.

### MODERATE Issues

**4. `feature-store` is in MF_REMOTES but has NO Module Federation config**

The `packages/feature-store/package.json` has no `module-federation` property. It would always be skipped by the current logic (the `[ -d "packages/$module" ]` check would pass but curl would fail), causing a false failure.

**5. `mlflow-embedded` is missing from MF_REMOTES**

The report says "11 Module Federation remotes" but the workflow only lists 10. `mlflow-embedded` has a valid MF config (`mlflowEmbedded`) but is omitted.

**6. `[skip konflux-sim]` documented but not implemented**

The docs reference `[skip konflux-sim]` as a way to skip validation, but the workflow has no condition to check for this in PR descriptions or commit messages.

**7. Kustomize installation method is fragile**

The workflow uses `curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash` which pipes a remote script directly into bash. The `ubuntu-latest` runners already have `kustomize` pre-installed, so this step is unnecessary. If kept, it should pin a version.

---

## 2. `scripts/validate-konflux-build.sh` — Local Script

### What Passes

- Shell syntax is valid (`bash -n` passes)
- `set -e` is correctly used for fail-fast
- Colorized output is well-structured
- Cleanup on failure paths (`docker rm -f`) is present
- Parameterized (image name, build mode, dockerfile)

### CRITICAL Issues (same as workflow)

**1. Module Federation validation will always fail locally**

Same fundamental problem. `curl http://localhost:8080/_mf/{module}/remoteEntry.js` will 404 because the proxy targets don't exist.

**2. `curl` inside container**

Same issue as workflow; `docker exec test-dashboard-local curl ...` requires curl in the image.

### MODERATE Issues

**3. Missing cleanup on some failure paths**

The `docker build` failure path does `exit 1` but doesn't clean up any lingering resources. If `docker run` fails, there may be a partially created container left behind.

**4. `feature-store` in MF_REMOTES but has no MF config** — Same as workflow.

**5. `mlflow-embedded` missing** — Same as workflow.

**6. Hardcoded port 8080**

If the user's port 8080 is already in use, the script will fail with an opaque Docker error. No port-in-use check or configurable port.

---

## 3. `docs/konflux-build-simulator.md` — Documentation

### What Passes

- Well-structured with clear sections
- Troubleshooting guide is practical
- ODH vs RHOAI comparison table is accurate
- The "Before/After" flow diagrams effectively communicate value

### Issues

1. **Claims `[skip konflux-sim]` works** — Not implemented in the workflow
2. **Module paths are wrong** — Says check `packages/{module}/frontend/config/moduleFederation.js`, but most packages use different structures (e.g., `packages/model-registry/upstream/frontend/config/...`)
3. **Claims "All remote entries are generated"** — The remotes are NOT generated locally, they're proxied from external services. The doc mischaracterizes how Module Federation works in this project.
4. **Lists `feature-store` as a validated module** — It has no MF config
5. **Missing `mlflow-embedded`** from the module list
6. **Broken relative links** — References `./module-federation.md` and `./testing.md` which don't exist in the `docs/` directory

---

## 4. `odh-dashboard-konflux-sim-report.md` — Report

### What Passes

- Repository analysis is broadly correct (monorepo, manifests, packages count)
- BUILD_MODE gap finding is the key insight and is accurate
- JIRA cross-references add credibility
- Multi-stage build analysis (13 COPY commands) matches the Dockerfile exactly

### Issues

1. **Claims "11 federated modules found"** but only 10 are in the workflow, and `feature-store` (included) has no MF config while `mlflow-embedded` (excluded) does. The actual count of packages with `module-federation` in `package.json` is **10** (automl, autorag, eval-hub, gen-ai, maas, mlflow, mlflow-embedded, model-registry, notebooks, observability).
2. **"90%+ of historical build failures" coverage claim** — This is aspirational. The Module Federation validation (which is the largest validation phase) would never work as designed, meaning actual coverage would be significantly lower.
3. **Lists overlays as "10+"** but there are actually **39** kustomization.yaml files across the manifests directory.

---

## The Core Blocker

The Module Federation validation (Phase 3) — the most distinctive and valuable part of this simulator — is **architecturally wrong**. The `/_mf/{module}/remoteEntry.js` endpoints are reverse proxies to external Kubernetes services, not locally-served files. They will always 404 when the container runs standalone.

### Possible Fixes

- **Option A**: Validate that the build step actually *generated* the frontend assets correctly by inspecting the Docker image filesystem (`docker run --rm $IMAGE ls /usr/src/app/frontend/public/`)
- **Option B**: Validate the Module Federation webpack config and `package.json` configs are syntactically correct without runtime testing
- **Option C**: Validate against the `app-config` package's `getModuleFederationConfigs()` output

### What Does Work

The **Docker build validation (Phase 1)** and **Kustomize validation (Phase 4)** are the most solid parts and would genuinely catch real issues — particularly the BUILD_MODE=RHOAI finding, which is the critical insight from this analysis. The **runtime validation (Phase 2)** is questionable due to Kubernetes cluster dependencies but could work if the app handles a missing cluster gracefully.
