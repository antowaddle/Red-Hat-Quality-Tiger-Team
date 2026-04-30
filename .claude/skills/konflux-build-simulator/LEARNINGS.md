# Konflux Build Simulator - Critical Learnings

## Issue: Hermetic npm install test with --network=none is unreliable

### Problem

The generated workflow includes this test:
```bash
docker run --rm \
  --network=none \
  -v "$(pwd)":/workspace \
  -w /workspace \
  node:22 \
  npm ci --ignore-scripts
```

This **consistently fails** with npm crash:
```
npm error Exit handler never called!
npm error This is an error with npm itself.
```

### Root Cause

`npm ci` performs validation and integrity checks that may attempt network operations even with `--ignore-scripts`. When `--network=none` is set, npm crashes instead of gracefully failing.

This is a known npm issue when running in completely isolated network environments.

### Why This Test is Flawed

1. **Docker image pull requires network**: The workflow pulls `node:22` image WITH network access, then runs npm with network disabled
2. **npm internals**: npm may try to contact registry for integrity checks even with `--ignore-scripts`
3. **Not representative**: Real hermetic builds (Hermeto/Cachi2) don't use `--network=none` - they pre-fetch tarballs
4. **Unreliable**: Crashes instead of providing useful validation

### What Actually Matters for Hermetic Builds

Hermeto/Cachi2 hermetic builds care about:
1. ✅ **No git+/github:/file: protocols** - Already validated with grep/jq
2. ✅ **All dependencies have resolved URLs** - Already validated with jq
3. ✅ **package-lock.json is in sync** - Can be validated differently

The `--network=none` test adds no additional value beyond what the lockfile validation already provides.

### Solution

**Remove the hermetic npm install test entirely.**

The workflow should only validate:
1. Lockfile compatibility (grep for unsupported protocols)
2. Resolved URLs presence (jq query)
3. Actual Docker build (which will catch real hermetic issues)

### Alternative: Lockfile Sync Validation

If you want to validate lockfile sync, use:
```bash
# Generate a fresh lockfile and compare
npm install --package-lock-only --ignore-scripts
if ! git diff --quiet package-lock.json; then
  echo "❌ package-lock.json is out of sync"
  exit 1
fi
```

This is more reliable than `--network=none`.

## Learning: Workspace Packages in package-lock.json

### Problem

Monorepo workspace packages (backend, frontend, packages/*) appear in `.packages` without `resolved` URLs:
```json
{
  "packages": {
    "": { ... },                    // Root package
    "backend": { ... },             // Workspace package (no resolved)
    "frontend": { ... },            // Workspace package (no resolved)
    "node_modules/@foo/bar": { ... } // Real dependency (has resolved)
  }
}
```

### Solution

Only check packages in `node_modules/`:
```bash
jq '.packages | to_entries[] | select(.key | startswith("node_modules/"))'
```

This excludes:
- Root package (key = "")
- Workspace packages (don't start with "node_modules/")

## Updated Workflow Template

### Phase 0: Hermetic Build Preflight (Recommended)

```yaml
- name: Validate lockfile for Hermeto/Cachi2 compatibility
  run: |
    echo "::group::Checking package-lock.json for unsupported protocols"
    # Check for protocols that Hermeto/Cachi2 cannot resolve
    UNSUPPORTED=$(grep -E '"resolved":\s*"(git\+|github:|file:)' package-lock.json || true)
    if [ -n "$UNSUPPORTED" ]; then
      echo "❌ FAIL: Found unsupported dependency protocols for hermetic builds:"
      echo "$UNSUPPORTED"
      echo ""
      echo "Hermeto/Cachi2 requires all dependencies to have HTTP/HTTPS URLs."
      echo "Replace git+, github:, and file: protocols with registry versions."
      exit 1
    fi
    echo "✅ PASS: No unsupported protocols found"
    echo "::endgroup::"

    echo "::group::Verifying all dependencies have resolved URLs"
    # Check only node_modules dependencies (skip workspace packages)
    MISSING_RESOLVED=$(jq -r '.packages | to_entries[] | select(.key | startswith("node_modules/")) | select(.value.resolved == null or .value.resolved == "") | .key' package-lock.json || true)
    if [ -n "$MISSING_RESOLVED" ]; then
      echo "❌ FAIL: Found dependencies without resolved URLs"
      echo "$MISSING_RESOLVED"
      exit 1
    fi
    echo "✅ PASS: All dependencies have resolved URLs"
    echo "::endgroup::"

# DO NOT include hermetic npm install test with --network=none
# It is unreliable and provides no additional value
```

## Key Takeaways

1. **Don't use `docker run --network=none` for npm validation** - It crashes npm
2. **Lockfile validation with grep/jq is sufficient** - Catches the actual hermetic build issues
3. **Only check node_modules packages for resolved URLs** - Workspace packages don't have them
4. **Real validation happens in Docker build phase** - That's where actual hermetic issues surface
5. **Keep Phase 0 fast and reliable** - It should fail-fast on obvious issues, not test theoretical scenarios

## References

- npm issue with --network=none: https://github.com/npm/cli/issues
- Hermeto documentation: (add link)
- Cachi2 documentation: (add link)
