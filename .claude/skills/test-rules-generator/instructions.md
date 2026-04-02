# Test Rules Generator - Implementation Instructions

## Task

Analyze a repository's existing test patterns and generate comprehensive Claude Code agent rules that enable agents to automatically create high-quality tests following the repository's conventions.

## Input

- Repository URL (required)
- Optional: Specific test types to focus on (unit, mock, e2e, contract)

## Output

Generate `.claude/rules/` directory with test creation rules as markdown files.

## Process

### Phase 1: Repository Discovery and Test Detection

#### Step 1.1: Clone and Scan Repository

```bash
# Clone repository
git clone <repo-url> /tmp/test-analysis-repo
cd /tmp/test-analysis-repo

# Identify test directories
find . -type d -name "test" -o -name "tests" -o -name "__tests__" -o -name "cypress" -o -name "e2e" -o -name "integration"
```

#### Step 1.2: Identify Test Types and Frameworks

Detect test types by examining:

1. **Unit Tests**
   - Go: `*_test.go` files
   - TypeScript/JavaScript: `*.spec.ts`, `*.test.ts`, `__tests__/**`
   - Python: `test_*.py`, `*_test.py`
   - Framework indicators:
     - `package.json` → Jest, Mocha, Vitest
     - `go.mod` → testing package
     - `pytest.ini` → pytest

2. **Mock Tests**
   - `cypress/tests/mocked/` or `__tests__/cypress/`
   - Indicators: `cy.intercept`, page objects, mock data factories

3. **E2E Tests**
   - `cypress/tests/e2e/`, `e2e/`, `integration/`
   - Indicators: cluster setup, real API calls, `test-variables.yml`

4. **Contract Tests**
   - `contract-tests/` directories
   - BFF directories with API specs
   - Indicators: OpenAPI schemas, contract test frameworks

#### Step 1.3: Identify Test Infrastructure

Check for:
- **Mock factories**: `__mocks__/`, `mocks/`, `fixtures/`
- **Page objects**: `pages/`, `page-objects/`
- **Test utilities**: `utils/`, `helpers/`, `support/`
- **Test configuration**: `jest.config.js`, `cypress.config.ts`, `pytest.ini`
- **CI/CD**: `.github/workflows/test*.yml`

### Phase 2: Pattern Extraction

For each identified test type:

#### Step 2.1: Collect Sample Tests

Select 5-10 representative test files per type:
- Recently modified (active patterns)
- Different complexity levels
- Good examples (passing tests with clear structure)
- Coverage of different scenarios

#### Step 2.2: Extract Common Patterns

For **Unit Tests**, extract:

1. **File Structure**
   ```
   - File naming pattern (*.spec.ts, *_test.go)
   - Location pattern (adjacent to source, __tests__ directory)
   - Import patterns
   - Test organization (describe blocks, test suites)
   ```

2. **Test Structure**
   ```
   - describe/it naming conventions
   - beforeEach/afterEach usage
   - Test isolation patterns
   - Assertion library (expect, assert, should)
   ```

3. **Mock Patterns**
   ```
   - How mocks are created (jest.mock, mock factories)
   - Mock data factories location and usage
   - Spy/stub patterns
   - Mock cleanup (clearAllMocks, resetAllMocks)
   ```

4. **React Component Testing** (if applicable)
   ```
   - Render patterns (render, screen)
   - Selector priorities (testId, role, label)
   - Event simulation (fireEvent, userEvent)
   - Async testing (waitFor, findBy)
   ```

5. **Hook Testing** (if applicable)
   ```
   - renderHook patterns
   - Custom matchers
   - Stability assertions
   - Render count verification
   ```

For **Mock Tests** (Cypress), extract:

1. **Test Structure**
   ```
   - describe/it organization
   - beforeEach setup patterns
   - Visit patterns
   - Wait strategies
   ```

2. **Interceptor Patterns**
   ```
   - cy.intercept* variants used
   - Alias naming (.as patterns)
   - Mock data sources
   - Response mocking
   ```

3. **Page Object Patterns**
   ```
   - Page object location
   - Method naming (find*, should*, get*)
   - Chainable patterns
   - data-testid usage
   ```

4. **Validation Patterns**
   ```
   - Assertion styles
   - Helper utilities
   - Error validation
   - Form validation
   ```

For **E2E Tests**, extract:

1. **Setup Patterns**
   ```
   - Test variables (test-variables.yml)
   - User authentication
   - Namespace handling
   - Resource creation
   ```

2. **OC Command Patterns**
   ```
   - kubectl/oc command usage
   - Resource waiting
   - Cleanup patterns
   ```

3. **Navigation Patterns**
   ```
   - Page navigation
   - Route verification
   - Login flow
   ```

4. **Resource Management**
   ```
   - Creation patterns
   - Deletion/cleanup
   - Unique naming (UUIDs)
   - Namespace scoping
   ```

For **Contract Tests**, extract:

1. **Framework Patterns**
   ```
   - Test structure
   - API client usage
   - Schema loading
   - Validation patterns
   ```

2. **BFF Integration**
   ```
   - BFF startup/lifecycle
   - Mock flags
   - Health check patterns
   - Port configuration
   ```

3. **Schema Validation**
   ```
   - OpenAPI schema location
   - Reference patterns (JSON Pointer)
   - Status code validation
   - Error response testing
   ```

### Phase 3: Rule Generation

For each test type, generate a markdown rule file following this template:

```markdown
---
description: [Brief description of test type and when to use it]
globs: "[File patterns this rule applies to]"
alwaysApply: false
---

# [Test Type] Rules

[Introduction paragraph explaining what this test type is for]

## When to Write [Test Type]

[Table or list of when/why to use this test type]

## Framework and Tools

[Table of tools and their purposes]

## Test File Structure

### File Naming and Location

[Patterns extracted from repo]

### Test Organization

[describe/it patterns, structure examples]

## [Test Type]-Specific Patterns

### [Pattern Category 1]

[Code examples from the repo]

### [Pattern Category 2]

[Code examples from the repo]

## Common Patterns

[Frequently used patterns in this test type]

## Best Practices Summary

### DO ✅

- [Practice 1]
- [Practice 2]
...

### DON'T ❌

- [Anti-pattern 1]
- [Anti-pattern 2]
...

## Implementation Checklist

### Before writing tests

- [ ] [Checklist item 1]
- [ ] [Checklist item 2]

### During implementation

- [ ] [Checklist item 1]
- [ ] [Checklist item 2]

### After implementation

- [ ] [Checklist item 1]
- [ ] [Checklist item 2]
```

#### Step 3.1: Generate `testing-standards.md`

Cross-cutting guidance covering:
- Test types overview table
- When to use each test type
- General testing principles
- Test independence
- Error handling

#### Step 3.2: Generate `unit-tests.md`

Extracted patterns for:
- File structure and naming
- Test organization patterns
- Component testing (if applicable)
- Hook testing (if applicable)
- Mock patterns
- Assertion patterns
- Best practices

#### Step 3.3: Generate `mock-tests.md` (if Cypress mock tests found)

Extracted patterns for:
- Test structure
- Interceptor patterns
- Page object patterns
- Mock data management
- Validation patterns
- Accessibility testing

#### Step 3.4: Generate `e2e-tests.md` (if E2E tests found)

Extracted patterns for:
- Test setup and configuration
- Navigation patterns
- Page object patterns
- Wait strategies
- Resource management
- Cleanup patterns
- OC command patterns

#### Step 3.5: Generate `contract-tests.md` (if contract tests found)

Extracted patterns for:
- Framework setup
- BFF configuration
- Test structure
- Schema validation
- Error handling
- HTTP method patterns

### Phase 4: Generate Supporting Files

#### Step 4.1: Create `.claude/rules/README.md`

```markdown
# Test Creation Rules

This directory contains agent rules for creating tests in this repository.

## Purpose

These rules enable Claude Code agents to automatically generate tests that follow the repository's established patterns and conventions.

## Rules

- `testing-standards.md` - Overview and general principles
- `unit-tests.md` - Unit test patterns
- `mock-tests.md` - Mock test patterns (Cypress)
- `e2e-tests.md` - E2E test patterns (Cypress)
- `contract-tests.md` - Contract test patterns

## How to Use

When creating tests, Claude Code will automatically apply these rules based on file patterns and context.

## Updating Rules

These rules were generated by analyzing existing tests in the repository. To update:

1. Review recent test additions for new patterns
2. Update the relevant rule file
3. Ensure examples match current conventions

## Generated

Generated on [DATE] by test-rules-generator skill
Based on analysis of [REPO_URL]
```

#### Step 4.2: Create Summary Report

Generate `TEST-RULES-ANALYSIS.md` in the repo root with:

1. **Summary**
   - Test types found
   - Frameworks detected
   - Number of sample tests analyzed
   - Patterns extracted

2. **Generated Rules**
   - List of rule files created
   - Coverage summary

3. **Key Patterns**
   - Most common patterns per test type
   - Unique conventions found

4. **Recommendations**
   - Gaps in test coverage
   - Suggested improvements
   - Additional rules to consider

### Phase 5: Validation

#### Step 5.1: Verify Rule Completeness

Check each generated rule for:
- [ ] Clear description and purpose
- [ ] Framework and tools section
- [ ] File structure guidance
- [ ] Pattern examples from the repo
- [ ] Best practices section
- [ ] Implementation checklist

#### Step 5.2: Verify Rule Accuracy

Validate that:
- [ ] Examples are from actual repo code
- [ ] Patterns match current conventions
- [ ] File paths are correct
- [ ] Framework versions match

#### Step 5.3: Test Application

For one test type:
- [ ] Create a new test following the generated rule
- [ ] Verify it matches existing patterns
- [ ] Confirm linting passes
- [ ] Adjust rule if needed

## Output Format

```text
.claude/
├── rules/
│   ├── testing-standards.md
│   ├── unit-tests.md
│   ├── mock-tests.md (if applicable)
│   ├── e2e-tests.md (if applicable)
│   ├── contract-tests.md (if applicable)
│   └── README.md
└── TEST-RULES-ANALYSIS.md (in repo root)
```

## Error Handling

### Repository Issues

- **Private repo**: Request user access or local path
- **No tests found**: Analyze documentation and recommend test patterns
- **Polyglot repo**: Generate language-specific rules

### Framework Issues

- **Unknown framework**: Extract patterns anyway, note framework for manual review
- **Multiple frameworks**: Generate separate sections or files per framework
- **Custom framework**: Focus on patterns, note customization

### Quality Issues

- **Inconsistent patterns**: Document variations, recommend standardization
- **Poor test examples**: Note quality issues, suggest improvements
- **Outdated patterns**: Flag deprecated patterns, suggest modern alternatives

## Time Estimates

- **Discovery**: 5-10 minutes
- **Pattern extraction**: 15-20 minutes per test type
- **Rule generation**: 10-15 minutes per rule file
- **Validation**: 5-10 minutes
- **Total**: 30-60 minutes for comprehensive analysis

## Key Files to Examine

### Test Files
- `**/*_test.go`, `**/*.spec.ts`, `**/*.test.ts`
- `cypress/tests/mocked/**/*.cy.ts`
- `cypress/tests/e2e/**/*.cy.ts`
- `contract-tests/**/*.test.ts`

### Test Infrastructure
- `**/__mocks__/**`
- `**/pages/**` (page objects)
- `**/fixtures/**`
- `**/utils/**` (test utilities)

### Configuration
- `jest.config.*`, `cypress.config.*`
- `package.json` (test scripts)
- `.github/workflows/test*.yml`

### Documentation
- `docs/testing.md`, `CONTRIBUTING.md`
- Existing `.claude/rules/` (if any)

## Special Considerations

### For TypeScript/React Projects

- Extract React Testing Library patterns
- Document hook testing patterns
- Identify custom matchers
- Note accessibility testing patterns

### For Go Projects

- Extract table-driven test patterns
- Document test suite organization
- Note envtest usage (for operators)
- Identify mock patterns

### For Monorepos

- Generate rules per package if patterns differ
- Create shared rules for common patterns
- Note package-specific conventions

### For Projects with BFFs

- Extract BFF testing patterns
- Document contract test setup
- Note OpenAPI schema patterns
- Identify mock client patterns

## Success Criteria

Generated rules should enable an agent to:
- [ ] Create new tests without manual guidance
- [ ] Follow repository conventions automatically
- [ ] Use correct frameworks and tools
- [ ] Apply appropriate patterns and structure
- [ ] Pass linting and validation
- [ ] Match quality of existing tests

