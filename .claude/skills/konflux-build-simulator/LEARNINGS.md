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

## Issue: Module Federation remoteEntry.js validation for host frontend

### Problem

The workflow was checking for `remoteEntry.js` in the main frontend build output:
```bash
docker cp odh-dashboard-test:/usr/src/app/frontend/public ./dist-check

if [ ! -f "dist-check/remoteEntry.js" ]; then
  echo "❌ FAIL: remoteEntry.js not found"
  exit 1
fi
```

This **incorrectly assumes** that the host frontend always generates a `remoteEntry.js` file.

### Root Cause

In Module Federation architecture:
- **Remote packages** (like gen-ai, model-registry) generate `remoteEntry.js` to expose their modules
- **Host application** (main frontend) may or may not generate `remoteEntry.js` depending on configuration

Looking at `frontend/config/moduleFederation.js`:
```javascript
moduleFederationPlugins: mfConfig.length > 0
  ? [
      new ModuleFederationPlugin({
        name: 'host',
        filename: 'remoteEntry.js',
        exposes: {},  // Host doesn't expose anything
        // ...
      }),
    ]
  : [],
```

The ModuleFederationPlugin is **only added if `mfConfig.length > 0`** (i.e., if federated modules are discovered from workspace packages).

If no federated modules are detected (e.g., packages don't have `module-federation` in package.json), the plugin isn't loaded and no `remoteEntry.js` is generated.

### Why This Matters

The host frontend's `remoteEntry.js`:
- Is **optional** - only exists when federated modules are configured
- Has **empty `exposes: {}`** - the host doesn't expose modules
- Is **not critical for runtime** - the host consumes remotes, it doesn't serve as one

### Solution

**Make remoteEntry.js check optional, check for main bundle instead:**

```yaml
- name: Validate Module Federation artifacts
  run: |
    # Copy dist from container
    docker cp odh-dashboard-test:/usr/src/app/frontend/public ./dist-check

    # Check for main app bundle (always required)
    if [ ! -f "dist-check/app.bundle.js" ]; then
      echo "❌ FAIL: app.bundle.js not found - build did not complete"
      exit 1
    fi

    echo "✅ PASS: Main app bundle present"

    # Check for remoteEntry.js (optional - only generated if federated modules exist)
    if [ -f "dist-check/remoteEntry.js" ]; then
      SIZE=$(stat -f%z dist-check/remoteEntry.js 2>/dev/null || stat -c%s dist-check/remoteEntry.js)
      if [ "$SIZE" -lt 100 ]; then
        echo "❌ FAIL: remoteEntry.js is suspiciously small ($SIZE bytes)"
        exit 1
      fi

      echo "✅ PASS: remoteEntry.js present and valid ($SIZE bytes)"

      # Check for missing webpack chunks (only if remoteEntry exists)
      CHUNK_REFS=$(grep -o 'chunk[0-9]\+' dist-check/remoteEntry.js || true)
      # ... chunk validation ...
    else
      echo "ℹ️  INFO: No remoteEntry.js found (no federated modules configured)"
    fi
```

### Distinction: Host vs Remote Validation

- **Host frontend** (main dashboard):
  - `app.bundle.js` is **required** (main application code)
  - `remoteEntry.js` is **optional** (only if MF configured)
  
- **Remote packages** (gen-ai, model-registry):
  - `remoteEntry.js` is **required** (exposes modules to host)
  - Should be checked in package-specific validation

The skill's module validation code is correct - it checks remoteEntry.js for **remote packages**, which should have it.

The PR workflow was wrong - it checked remoteEntry.js for the **host**, which may not have it.

## Key Takeaways

1. **Don't use `docker run --network=none` for npm validation** - It crashes npm
2. **Lockfile validation with grep/jq is sufficient** - Catches the actual hermetic build issues
3. **Only check node_modules packages for resolved URLs** - Workspace packages don't have them
4. **Real validation happens in Docker build phase** - That's where actual hermetic issues surface
5. **Keep Phase 0 fast and reliable** - It should fail-fast on obvious issues, not test theoretical scenarios
6. **Host frontend remoteEntry.js is optional** - Only remote packages require it
7. **Check app.bundle.js instead** - This is always generated by the main frontend build

## References

- npm issue with --network=none: https://github.com/npm/cli/issues
- Hermeto documentation: (add link)
- Cachi2 documentation: (add link)
