---
description: Cross-cutting testing guidance for the notebooks repository covering test types, when to use each type, and general testing principles
globs: "tests/**/*.py,tests/**/*.ts"
alwaysApply: false
---

# Testing Standards for Notebooks Repository

This document provides cross-cutting guidance for creating tests in the notebooks repository, which contains workbench images (JupyterLab, RStudio, Code Server) for Open Data Hub and OpenShift AI.

## Test Types Overview

The notebooks repository uses three primary test types:

| Test Type | Framework | Location | Purpose | When to Use |
|-----------|-----------|----------|---------|-------------|
| **Python Integration Tests** | pytest + testcontainers | `tests/test_main.py`, `tests/containers/` | Test workbench images by running them in containers | Validating Docker/Podman images, testing image entrypoints, verifying runtime behavior |
| **Python Unit Tests** | pytest | `tests/unit/` | Test Python scripts and utilities | Testing build scripts, lockfile generators, utility functions |
| **Playwright Browser Tests** | Playwright + TypeScript | `tests/browser/tests/` | Test workbench UIs in browsers | Testing web IDE functionality, user interactions, visual validation |

## When to Use Each Test Type

### Use Python Integration Tests When:
- Testing a workbench image (JupyterLab, RStudio, Code Server)
- Verifying container startup and readiness
- Testing network configurations (IPv4/IPv6)
- Validating installed packages, extensions, or libraries
- Testing Dockerfile changes
- Verifying image manifests and metadata

### Use Python Unit Tests When:
- Testing Python build scripts (e.g., `scripts/pylocks_generator.py`)
- Testing utility functions and helpers
- Validating parsers, formatters, or data transformations
- Testing logic that doesn't require container execution

### Use Playwright Browser Tests When:
- Testing UI functionality in workbench IDEs
- Validating terminal operations in Code Server
- Testing file operations through the browser
- Verifying UI rendering and visual elements
- Testing user workflows in JupyterLab or RStudio

## General Testing Principles

### Test Independence
- Tests must not depend on execution order
- Clean up resources (containers, files, networks) after each test
- Use fixtures for setup/teardown
- Avoid shared mutable state between tests

### Test Naming
- **Python**: Use descriptive names starting with `test_`
- **TypeScript**: Use descriptive test titles in natural language
- Name should describe what is being tested, not how
- Include issue references with `@allure.issue()` or test tags

### Assertions and Validation
- Use meaningful assertion messages
- Assert one logical concept per assertion (but multiple assertions per test is OK)
- Use `subtests` for parametrized variations within a test
- Prefer specific assertions over generic `assert condition`

### Resource Cleanup
- Always stop containers in `finally` blocks
- Use `timeout=0` for fast container stops in cleanup
- Clean up temporary files and directories
- Reset global state if modified

### Allure Reporting
- Add `@allure.issue("JIRA-ID")` for tests linked to Jira issues
- Add `@allure.description()` for test descriptions
- Use `@allure.step()` for complex test workflows
- Attach logs, screenshots, or artifacts to failed tests

### Performance Considerations
- Keep container startup times reasonable (use `wait_for_readiness` wisely)
- Parametrize tests to avoid duplication
- Use test marks to categorize slow vs fast tests
- Consider parallel execution limits (CI uses `workers: 1`)

### Error Handling
- Let exceptions propagate naturally (pytest captures them)
- Add context to assertion messages
- Log important debugging information
- Use `pytest.skip()` for environment-specific constraints

## Test Organization

### File Structure
```
tests/
├── test_main.py                    # Main integration tests (Dockerfiles, pyprojects, manifests)
├── conftest.py                     # pytest fixtures and configuration
├── containers/                     # Container-based integration tests
│   ├── conftest.py                # Container fixtures
│   └── workbenches/
│       ├── workbench_image_test.py    # Base workbench tests
│       ├── jupyterlab/                # JupyterLab-specific tests
│       ├── rstudio/                   # RStudio-specific tests
│       └── codeserver/                # Code Server-specific tests
├── unit/                          # Unit tests for scripts
│   └── scripts/
│       └── test_pylocks_generator.py
└── browser/                       # Playwright browser tests
    ├── tests/
    │   ├── *.spec.ts             # Test files
    │   └── models/               # Page objects
    └── playwright.config.ts      # Playwright configuration
```

### Test Discovery
- **Python**: pytest discovers files matching `test_*.py` or `*_test.py`
- **TypeScript**: Playwright discovers files matching `*.spec.ts`
- Place tests in appropriate subdirectories
- Use `conftest.py` for shared fixtures at each level

## CI/CD Integration

### Test Execution
- Python tests run via `pytest` with allure reporting
- Playwright tests run via `pnpm test` with JUnit XML output
- Both generate test reports for CI pipeline analysis
- Tests run in Konflux CI and GitHub Actions

### Test Artifacts
- JUnit XML reports: `tests/browser/results/junit.xml`
- Playwright screenshots: `tests/browser/results/playwright-output/`
- Allure reports for Python tests
- Test logs attached to CI artifacts

## Best Practices Summary

### DO ✅
- Use fixtures for setup and teardown
- Parametrize tests to cover multiple scenarios
- Add issue references and descriptions
- Clean up resources in `finally` blocks
- Use meaningful assertion messages
- Test both success and failure paths
- Use page objects for browser tests
- Validate against actual image behavior

### DON'T ❌
- Don't hardcode paths or URLs
- Don't rely on test execution order
- Don't leave containers running after tests
- Don't test implementation details
- Don't create tests without cleanup
- Don't use `sleep()` for timing (use proper wait strategies)
- Don't duplicate test logic across files
- Don't commit commented-out test code

## Common Patterns

### Container Testing Pattern
```python
container = WorkbenchContainer(image=image_name, user=1000, group_add=[0])
try:
    container.start()
    # ... test logic ...
finally:
    docker_utils.NotebookContainer(container).stop(timeout=0)
```

### Subtest Pattern
```python
def test_multiple_scenarios(subtests, workbench_image):
    for scenario in scenarios:
        with subtests.test(msg=scenario.description):
            assert scenario.validate()
```

### Browser Test Pattern
```typescript
test('feature description', async ({codeServer, page}) => {
  await page.goto(codeServer.url)
  await codeServer.isEditorVisible()
  // ... test steps ...
})
```

## Test Quality Gates

Before submitting tests:
- [ ] All tests pass locally
- [ ] Resources are properly cleaned up
- [ ] Tests have meaningful names and descriptions
- [ ] Assertions have clear messages
- [ ] Issue references added where applicable
- [ ] Tests are independent and can run in any order
- [ ] No hardcoded credentials or secrets
- [ ] Tests follow repository conventions
