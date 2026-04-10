#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   cd /path/to/odh-dashboard && /path/to/validate-build.sh
#   /path/to/validate-build.sh /path/to/odh-dashboard

REPO_ROOT="${1:-$(pwd)}"
cd "$REPO_ROOT"

if [ ! -f "Dockerfile" ]; then
  echo "ERROR: No Dockerfile found in $REPO_ROOT"
  echo "Run this script from the odh-dashboard repo root, or pass the path as an argument."
  exit 1
fi

BUILD_MODE="${BUILD_MODE:-RHOAI}"
IMAGE_TAG="${IMAGE_TAG:-odh-dashboard:local-konflux-sim}"
DOCKERFILE="${DOCKERFILE:-Dockerfile}"
KUSTOMIZE_VERSION="${KUSTOMIZE_VERSION:-v5.4.1}"
CONTAINER_NAME="odh-konflux-smoke-$$"

cleanup() {
  echo "==> Cleanup"
  if docker ps -a --filter "name=${CONTAINER_NAME}" --format '{{.Names}}' | grep -q "${CONTAINER_NAME}"; then
    echo "  Container logs (last 30 lines):"
    docker logs "${CONTAINER_NAME}" --tail 30 2>&1 || true
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "==> Phase 1: Docker build (BUILD_MODE=${BUILD_MODE})"
docker build \
  --build-arg "BUILD_MODE=${BUILD_MODE}" \
  -t "${IMAGE_TAG}" \
  -f "${DOCKERFILE}" \
  --progress=plain \
  .

echo "==> Phase 2: Verify frontend build artifacts in image"
PHASE2_OK=true
for artifact in index.html app.bundle.js; do
  if docker run --rm "${IMAGE_TAG}" test -f "/usr/src/app/frontend/public/${artifact}"; then
    echo "  OK: ${artifact}"
  else
    echo "  MISSING: ${artifact}"
    PHASE2_OK=false
  fi
done

# remoteEntry.js is only generated when Module Federation remotes are configured;
# its absence in a standard build is expected, not a failure.
if docker run --rm "${IMAGE_TAG}" test -f /usr/src/app/frontend/public/remoteEntry.js; then
  echo "  OK: remoteEntry.js (Module Federation host active)"
else
  echo "  INFO: remoteEntry.js absent — no MF remotes configured (expected for standard builds)"
fi

if [ "$PHASE2_OK" = false ]; then
  echo "  FAILED: Critical frontend artifacts missing"
  exit 1
fi

echo "==> Phase 3: Runtime smoke test"
docker run -d \
  --name "${CONTAINER_NAME}" \
  -p 8080:8080 \
  -e NODE_ENV=production \
  "${IMAGE_TAG}"

# The backend kube.ts plugin makes K8s API calls during startup.
# Outside a cluster these will fail (expected). We wait long enough
# for the plugin timeout (10s) to expire and the server to either start or crash.
echo "  Waiting for container (up to 60s, backend needs ~15s for K8s plugin timeout)..."
READY=false
for i in $(seq 1 30); do
  if ! docker ps --filter "name=${CONTAINER_NAME}" --filter "status=running" -q | grep -q .; then
    echo "  Container exited prematurely."
    echo "  Container logs:"
    docker logs "${CONTAINER_NAME}" 2>&1 || true
    exit 1
  fi

  if curl -fsS -o /dev/null "http://localhost:8080/" 2>/dev/null; then
    READY=true
    break
  fi
  sleep 2
done

if [ "$READY" = false ]; then
  echo "  Container running but HTTP not responding after 60s."
  echo "  Container logs:"
  docker logs "${CONTAINER_NAME}" 2>&1 || true
  exit 1
fi

echo "  HTTP GET / returned 200"

echo "==> Phase 4: Kustomize manifest validation"
if ! command -v kustomize >/dev/null 2>&1; then
  KUST_OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
  KUST_ARCH="$(uname -m)"
  case "${KUST_ARCH}" in
    x86_64) KUST_ARCH="amd64" ;;
    aarch64|arm64) KUST_ARCH="arm64" ;;
  esac
  echo "  Installing kustomize ${KUSTOMIZE_VERSION} (${KUST_OS}/${KUST_ARCH})..."
  curl -fsSL -o /tmp/kustomize.tar.gz \
    "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize/${KUSTOMIZE_VERSION}/kustomize_${KUSTOMIZE_VERSION}_${KUST_OS}_${KUST_ARCH}.tar.gz"
  tar -xzf /tmp/kustomize.tar.gz -C /tmp
  export PATH="/tmp:${PATH}"
fi

KUSTOMIZE_OK=true
for p in manifests/rhoai/addon manifests/rhoai/onprem manifests/odh; do
  if [ -f "$p/kustomization.yaml" ] || [ -f "$p/kustomization.yml" ]; then
    echo "  kustomize build $p"
    if ! kustomize build "$p" > /dev/null 2>&1; then
      echo "  FAIL: kustomize build $p"
      KUSTOMIZE_OK=false
    fi
  else
    echo "  SKIP: $p (no kustomization.yaml)"
  fi
done

if [ "$KUSTOMIZE_OK" = false ]; then
  echo "==> FAILED: kustomize validation"
  exit 1
fi

echo "==> All checks passed"
