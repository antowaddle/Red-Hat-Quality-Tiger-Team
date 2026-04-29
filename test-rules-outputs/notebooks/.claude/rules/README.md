# Test Creation Rules

This directory contains Claude Code agent rules for creating tests in the notebooks repository.

## Purpose

These rules enable Claude Code agents to automatically generate tests that follow the repository's established patterns and conventions. They provide:

- **Framework-specific guidance** - Patterns for pytest, Playwright, testcontainers
- **Code examples** - Real patterns extracted from existing tests
- **Best practices** - Do's and don'ts for test creation
- **Implementation checklists** - Step-by-step guides for writing tests

## Rules

| Rule File | Purpose | When to Use |
|-----------|---------|-------------|
| [`testing-standards.md`](./testing-standards.md) | Cross-cutting testing principles and test type overview | Always - provides foundation for all testing |
| [`python-integration-tests.md`](./python-integration-tests.md) | pytest + testcontainers patterns for workbench images | When testing Docker/Podman images, validating runtime behavior |
| [`python-unit-tests.md`](./python-unit-tests.md) | pytest patterns for Python scripts and utilities | When testing build scripts, utilities, non-container logic |
| [`playwright-browser-tests.md`](./playwright-browser-tests.md) | Playwright/TypeScript patterns for IDE UI testing | When testing web IDE functionality, user interactions |

## How to Use

### For Claude Code Agents

When creating tests, Claude Code will automatically apply these rules based on:

1. **File patterns** - Rules specify `globs` that match test file locations
2. **Context** - The type of code or feature being tested
3. **User intent** - What the user asks to test

The rules are designed to be **actionable** - they include:
- Concrete code examples from this repository
- Pattern templates ready to adapt
- Specific do's and don'ts
- Implementation checklists

### For Developers

Use these rules as:
- **Reference documentation** - Learn testing patterns used in this repo
- **Onboarding guide** - Understand how to write tests that match conventions
- **Quality checklist** - Ensure your tests follow best practices
- **Pattern library** - Find examples of common testing scenarios

## Test Type Decision Tree

```
Need to test...

├─ Workbench image (Docker/Podman)?
│  ├─ Runtime behavior, entrypoints, containers?
│  │  → Use Python Integration Tests
│  └─ UI, user interactions, browser?
│     → Use Playwright Browser Tests
│
└─ Python code not in containers?
   └─ Scripts, utilities, parsers?
      → Use Python Unit Tests
```

## Quick Reference

### Python Integration Tests

**Use for**: Testing workbench images (JupyterLab, RStudio, Code Server)

**Key patterns**:
```python
container = WorkbenchContainer(image=image, user=1000, group_add=[0])
try:
    container.start()
    # test logic
finally:
    docker_utils.NotebookContainer(container).stop(timeout=0)
```

**Location**: `tests/test_main.py`, `tests/containers/`

### Python Unit Tests

**Use for**: Testing Python scripts and utilities

**Key patterns**:
```python
def test_function_name(tmp_path: Path) -> None:
    """Test description."""
    result = module.function(tmp_path / "file.txt")
    assert result == expected
```

**Location**: `tests/unit/`

### Playwright Browser Tests

**Use for**: Testing IDE UI functionality

**Key patterns**:
```typescript
test('@tag test name', async ({codeServer, page}) => {
  await page.goto(codeServer.url);
  await codeServer.isEditorVisible();
  // test logic
});
```

**Location**: `tests/browser/tests/`

## Repository Structure

```
notebooks/
├── .claude/
│   └── rules/                    # ← You are here
│       ├── README.md             # This file
│       ├── testing-standards.md  # General testing principles
│       ├── python-integration-tests.md
│       ├── python-unit-tests.md
│       └── playwright-browser-tests.md
├── tests/
│   ├── test_main.py             # Main integration tests
│   ├── conftest.py              # pytest configuration
│   ├── containers/              # Container integration tests
│   ├── unit/                    # Python unit tests
│   └── browser/                 # Playwright browser tests
├── scripts/                     # Python build scripts
├── jupyter/                     # JupyterLab images
├── rstudio/                     # RStudio images
└── codeserver/                  # Code Server images
```

## Common Testing Scenarios

### Scenario 1: Test a New JupyterLab Feature

1. **Determine test type**:
   - Container-level? → Integration test
   - UI-level? → Browser test

2. **Choose rule file**:
   - `python-integration-tests.md` or `playwright-browser-tests.md`

3. **Find similar test** in that category

4. **Adapt pattern** to new feature

5. **Run test locally** to verify

### Scenario 2: Test a New Build Script

1. **Use**: `python-unit-tests.md`

2. **Create test file**: `tests/unit/scripts/test_<script_name>.py`

3. **Import script**: `import scripts.<script_name> as mod`

4. **Write tests** using `tmp_path` fixture

5. **Run**: `pytest tests/unit/`

### Scenario 3: Test Dockerfile Changes

1. **Use**: `python-integration-tests.md`

2. **Find existing image test** in `tests/containers/workbenches/`

3. **Add new test method** to appropriate class

4. **Use** `WorkbenchContainer` pattern

5. **Run**: `pytest tests/containers/`

## Updating Rules

These rules were generated by analyzing existing tests in the repository. To update them:

1. **Review recent test additions** - Look for new patterns or conventions
2. **Update relevant rule file** - Add new patterns or examples
3. **Ensure examples match current code** - Verify patterns are still in use
4. **Update this README** - If adding new rule files or sections

## Test Quality Gates

Before submitting tests, ensure:

- [ ] Tests follow patterns from appropriate rule file
- [ ] All fixtures and imports are correct
- [ ] Tests pass locally
- [ ] Resources (containers, files) are cleaned up
- [ ] Meaningful test names and descriptions
- [ ] Assertion messages provide context
- [ ] Tests are independent and can run in any order
- [ ] No hardcoded credentials or secrets
- [ ] Issue references added where applicable

## Framework Versions

Current framework versions (as of generation):

- **pytest**: Latest (specified in repository dependencies)
- **Playwright**: 1.58.1
- **testcontainers**: ^11.11.0
- **TypeScript**: ^5.9.3

See `tests/browser/package.json5` for browser test dependencies.

## CI/CD Integration

Tests run in:
- **Konflux CI** - Automated build and test pipeline
- **GitHub Actions** - PR validation
- **Shift-left pipeline** - Test results forwarded to Report Portal

Test artifacts:
- JUnit XML: `tests/browser/results/junit.xml`
- Playwright screenshots: `tests/browser/results/playwright-output/`
- Allure reports for Python tests

## Getting Help

- **Testing standards**: Start with `testing-standards.md`
- **Specific framework**: See framework-specific rule files
- **Examples**: Look at existing tests in `tests/` directory
- **Issues**: Check JIRA for testing-related issues (RHOAIENG-*)

## Generated

- **Generated on**: 2026-04-29
- **Generated by**: test-rules-generator skill
- **Based on**: Analysis of [opendatahub-io/notebooks](https://github.com/opendatahub-io/notebooks)
- **Test files analyzed**: 
  - `tests/test_main.py` (872 lines)
  - `tests/containers/workbenches/workbench_image_test.py` (254 lines)
  - `tests/containers/workbenches/jupyterlab/jupyterlab_test.py`
  - `tests/unit/scripts/test_pylocks_generator.py`
  - `tests/browser/tests/codeserver.spec.ts` (99 lines)
  - Page objects, utilities, and configuration files

---

**Note**: These rules are living documentation. As testing patterns evolve in the repository, update these rules to reflect current best practices.
