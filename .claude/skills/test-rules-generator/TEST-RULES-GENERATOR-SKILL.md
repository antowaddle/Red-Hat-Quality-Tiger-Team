# Test Rules Generator Skill

**Skill Name**: `/test-rules-generator`
**Purpose**: Auto-generate test creation rules for Claude Code agents based on existing test patterns
**Type**: Pillar 2 - Agentic Flow Quality Solution
**Status**: Ready to Use

---

## Overview

The Test Rules Generator skill analyzes existing test patterns in a repository and generates comprehensive Claude Code agent rules that enable agents to automatically create tests following repository conventions.

This skill addresses the **Pillar 2 gap** identified in the quality analysis: **12/13 components lack agent test creation rules**, preventing agents from creating high-quality tests that follow repository patterns.

---

## What It Solves

### The Problem

When agents (Claude Code) create code changes, they need to create accompanying tests. However:

**Current Challenges**:
- ❌ Agents lack knowledge of repo-specific test patterns
- ❌ No automated guidance for test creation
- ❌ Test quality varies based on agent "memory" of patterns
- ❌ New contributors (human or AI) must manually learn conventions
- ❌ Inconsistent test structure across contributions

**Impact**:
- Manual test creation (time-consuming)
- Inconsistent test quality
- Missing tests for new code
- Longer review cycles
- Pattern drift over time

### The Solution

**Auto-generated agent rules** enable agents to:

✅ Understand test patterns by analyzing existing tests
✅ Extract conventions and best practices
✅ Generate actionable checklists and examples
✅ Create tests that follow repository patterns automatically
✅ Maintain consistency across all contributions

---

## Usage

```bash
/test-rules-generator [repository-url]
```

### Examples

```bash
# Frontend with multiple test types
/test-rules-generator https://github.com/opendatahub-io/odh-dashboard

# Backend with unit + E2E
/test-rules-generator https://github.com/opendatahub-io/notebooks

# Operator with Go tests
/test-rules-generator https://github.com/kserve/kserve

# Mixed Go/Python
/test-rules-generator https://github.com/kubeflow/training-operator
```

---

## What It Generates

### Directory Structure

```text
.claude/
├── rules/
│   ├── testing-standards.md    # Cross-cutting testing guidance
│   ├── unit-tests.md           # Unit test patterns
│   ├── mock-tests.md           # Mock test patterns (if Cypress found)
│   ├── e2e-tests.md            # E2E test patterns (if found)
│   └── contract-tests.md       # Contract test patterns (if BFF found)
└── README.md                    # How to use the rules
```

### Pattern Extraction

For each test type found, the skill extracts:

#### 1. File Structure
- Naming conventions (`*.test.ts`, `*_test.go`, `test_*.py`)
- Directory layout (`__tests__/`, `test/`, `*_test.go`)
- Import patterns

#### 2. Test Organization
- describe/it structure (JavaScript/TypeScript)
- Test function naming (Go, Python)
- beforeEach/afterEach usage
- Test isolation patterns

#### 3. Framework-Specific Patterns
- **Jest/React Testing Library** (JavaScript/TypeScript)
  - Render patterns
  - User interaction testing
  - Async testing
  - Mock patterns

- **Go testing package**
  - Table-driven tests
  - Helper functions
  - Test fixtures
  - Mock interfaces

- **Cypress** (E2E/Mock)
  - Command patterns
  - Intercept patterns
  - Page objects
  - Custom commands

- **Python pytest**
  - Fixture patterns
  - Parametrized tests
  - Mock patterns

#### 4. Best Practices
- Mock/stub patterns
- Assertion styles
- Error handling in tests
- Accessibility testing (if found)
- Test data management

#### 5. Quality Gates
- Linting requirements
- Coverage expectations
- Required test types
- Checklists for completeness

---

## Test Types Detected & Generated

### 1. Unit Tests

**Detection**: Files matching `*.test.ts`, `*_test.go`, `test_*.py`

**Generated Rule Content**:
```markdown
## File Structure
- Location: src/**/__tests__/*.test.ts
- Naming: [ComponentName].test.ts

## Test Organization
- Use describe() for component/function grouping
- Use it() for individual test cases
- beforeEach() for common setup

## Patterns
- Render with: render(<Component {...props} />)
- Query with: screen.getByRole(), screen.getByText()
- Assertions: expect(element).toBeInTheDocument()

## Example
[Extracted from actual repository tests]

## Checklist
- [ ] File named correctly ([Name].test.ts)
- [ ] Imports all dependencies
- [ ] Tests all public methods/props
- [ ] Handles error cases
- [ ] Passes linting
```

### 2. Mock Tests (Cypress)

**Detection**: Files in `cypress/e2e/` or matching `*.cy.ts` with `cy.intercept()`

**Generated Rule Content**:
```markdown
## File Structure
- Location: frontend/src/__tests__/cypress/cypress/e2e/
- Naming: [feature]-mock.cy.ts

## Mock Patterns
- API mocking: cy.intercept('GET', '/api/endpoint', mockData)
- Fixture loading: cy.fixture('filename.json')
- Intercept patterns for BFF APIs

## Navigation
- cy.visitWithLogin() for authenticated pages
- cy.findByTestId() for element selection

## Example
[Extracted from actual repository tests]

## Checklist
- [ ] All API calls mocked
- [ ] Test data in fixtures
- [ ] Proper wait patterns
- [ ] Cleanup after tests
```

### 3. E2E Tests (Cypress)

**Detection**: Cypress files without mocking, or files with real cluster interaction

**Generated Rule Content**:
```markdown
## File Structure
- Location: frontend/src/__tests__/cypress/cypress/e2e/
- Naming: [feature]-e2e.cy.ts

## Setup
- Requires real OpenShift cluster
- Uses environment-specific configuration
- Authentication via cy.visitWithLogin()

## Patterns
- Real API calls (no intercepts)
- Resource creation/cleanup
- State verification across pages

## Example
[Extracted from actual repository tests]

## Checklist
- [ ] Test works on real cluster
- [ ] Cleanup resources after test
- [ ] Handles async operations
- [ ] Passes on CI environment
```

### 4. Contract Tests (BFF)

**Detection**: Files with API schema validation, response checking

**Generated Rule Content**:
```markdown
## File Structure
- Location: backend/src/routes/__tests__/
- Naming: [route].test.ts

## Patterns
- Schema validation: expect(response).toMatchSchema()
- Status code checks
- Required fields validation
- Backward compatibility checks

## Example
[Extracted from actual repository tests]

## Checklist
- [ ] All endpoints tested
- [ ] Schema validated
- [ ] Error responses tested
- [ ] Backward compatible
```

---

## Example: odh-dashboard (Gold Standard)

When run on odh-dashboard, the skill identifies and generates rules for:

### Detected Test Types
- ✅ Unit tests (Jest + React Testing Library)
- ✅ Mock tests (Cypress with API intercepts)
- ✅ E2E tests (Cypress on real clusters)
- ✅ Contract tests (BFF API validation)

### Generated Files
```
.claude/rules/
├── testing-standards.md     # Overview of all test types
├── unit-tests.md            # 150+ lines of patterns
├── cypress-mock.md          # Mock test patterns
├── cypress-e2e.md           # E2E test patterns
└── contract-tests.md        # API contract patterns
```

### Key Patterns Extracted
- File naming: `[ComponentName].test.tsx`
- Render pattern: `render(<Component />)`
- Query pattern: `screen.getByRole()`, `screen.getByText()`
- Mock pattern: `cy.intercept('GET', '/api/*', mockData)`
- Assertion style: `expect().toBeInTheDocument()`, `expect().toHaveBeenCalled()`
- Accessibility: `screen.getByRole('button', { name: 'Submit' })`

---

## Benefits

### 1. Consistency
- ✅ Agents create tests following repo conventions automatically
- ✅ Same patterns across all contributions
- ✅ No drift from established practices

### 2. Quality
- ✅ Test quality standards maintained
- ✅ All required test types created
- ✅ Proper assertions and error handling
- ✅ Accessibility testing included

### 3. Onboarding
- ✅ New developers learn patterns faster
- ✅ Agents understand conventions immediately
- ✅ Reduces "how do I test this?" questions

### 4. Automation
- ✅ Enables true "code + tests" workflow
- ✅ No manual test creation needed
- ✅ Faster development cycle

### 5. Documentation
- ✅ Living documentation of test patterns
- ✅ Examples from actual codebase
- ✅ Always up-to-date with current practices

---

## How It Works

### Phase 1: Test Discovery (2-5 min)
```bash
# Find all test files
find . -name "*.test.ts" -o -name "*.test.tsx" -o -name "*_test.go"

# Categorize by type
- Unit tests: src/**/__tests__/
- Cypress mock: cypress/e2e/*-mock.cy.ts
- Cypress E2E: cypress/e2e/*-e2e.cy.ts
- Contract: backend/**/*.test.ts (with schema validation)
```

### Phase 2: Pattern Analysis (5-10 min)
For each test type:

1. **Read representative test files**
   - 3-5 examples per type
   - Mix of simple and complex tests

2. **Extract patterns**
   - File/directory structure
   - Import statements
   - Test organization
   - Common helpers
   - Assertion styles
   - Mock patterns

3. **Identify frameworks**
   - Jest, React Testing Library
   - Cypress commands
   - Go testing package
   - pytest

### Phase 3: Rule Generation (5-10 min)
For each test type:

1. **Create rule file**
   - Markdown format
   - Clear sections
   - Code examples from actual tests

2. **Include**
   - File structure guidance
   - Framework-specific patterns
   - Best practices
   - Example tests
   - Actionable checklist

3. **Cross-reference**
   - Link to testing-standards.md
   - Reference related test types

### Phase 4: Validation (2-5 min)
- Ensure all examples are valid
- Verify patterns match current codebase
- Check for completeness

**Total Time**: 15-30 minutes per repository

---

## Agent Workflow (Using Generated Rules)

When an agent creates code and needs to write tests:

### Step 1: Check for Rules
```bash
ls .claude/rules/
# Found: unit-tests.md, mock-tests.md, e2e-tests.md
```

### Step 2: Read Relevant Rule
```bash
# For unit test creation
cat .claude/rules/unit-tests.md
```

### Step 3: Follow Patterns
- Use same file structure
- Follow naming conventions
- Apply test organization patterns
- Use correct framework methods
- Include proper assertions

### Step 4: Use Checklist
```markdown
- [x] File named correctly (Button.test.tsx)
- [x] Imports all dependencies
- [x] Tests all props (label, onClick, disabled)
- [x] Handles error cases
- [x] Passes linting (npm run lint)
```

### Step 5: Validate
```bash
# Run tests
npm test Button.test.tsx

# Run linting
npm run lint Button.test.tsx
```

**Result**: High-quality tests that match repository patterns on first try ✅

---

## Success Metrics

### Before Implementation

| Metric | Current State |
|--------|---------------|
| Repos with agent rules | 1/13 (odh-dashboard only) |
| Test types with rules | Varies by repo |
| Agent test creation success | ~60% (requires iteration) |
| Tests passing linting first try | ~50% |
| Manual pattern explanation | Common |

### After Implementation

| Metric | Target |
|--------|--------|
| Repos with agent rules | **13/13** |
| Test types with rules | **All types in each repo** |
| Agent test creation success | **95%+** |
| Tests passing linting first try | **90%+** |
| Manual pattern explanation | **Rare** |

---

## Time Estimates

| Repository Complexity | Analysis | Generation | Validation | Total |
|----------------------|----------|------------|------------|-------|
| Simple (1-2 test types) | 5 min | 10 min | 5 min | **20 min** |
| Medium (2-3 test types) | 10 min | 20 min | 10 min | **40 min** |
| Complex (4+ test types) | 15 min | 30 min | 15 min | **1 hr** |

**Examples**:
- **kserve** (Go unit + E2E): ~30 min
- **notebooks** (Python unit + E2E + Playwright): ~45 min
- **odh-dashboard** (Unit + Mock + E2E + Contract): ~1 hr (reference - already has rules)

---

## Implementation Priority

### Phase 1: Repos with Good Test Coverage (Week 1-2)
Already have good tests, just need rules extracted:

1. notebooks (Python + Playwright + Testcontainers)
2. kserve (Go + Python + E2E)
3. training-operator (Go + E2E)
4. kueue (Go + comprehensive testing)

**Effort**: 2-3 hours each = 8-12 hours total

### Phase 2: Remaining Repos (Week 3-4)
Extract whatever patterns exist:

5. rhods-operator
6. kuberay
7. kubeflow
8. odh-model-controller
9. codeflare-operator
10. modelmesh-serving
11. trustyai-service-operator
12. data-science-pipelines

**Effort**: 1-2 hours each = 8-16 hours total

### Phase 3: Validation (Week 4)
- Test rules by creating sample tests
- Refine based on agent feedback
- Update patterns as needed

**Effort**: 4-8 hours

**Total**: 20-36 hours for all 12 repos (odh-dashboard already has rules)

---

## Example Output

When you run `/test-rules-generator https://github.com/opendatahub-io/notebooks`:

```
✅ Repository analyzed successfully
   Test types found: 3
   - Unit tests (Python/pytest)
   - E2E tests (Playwright)
   - Container tests (Testcontainers)

✅ Generated rules:
   .claude/rules/testing-standards.md
   .claude/rules/unit-tests.md
   .claude/rules/e2e-tests.md
   .claude/rules/container-tests.md

✅ Patterns extracted:
   • 15 unit test examples
   • 8 E2E test examples
   • 5 container test examples

✅ Frameworks detected:
   • pytest (fixtures, parametrize)
   • Playwright (page objects, assertions)
   • Testcontainers (GenericContainer patterns)

🎯 Next steps:
   1. Review generated rules
   2. Test agent workflow (create sample test)
   3. Refine patterns if needed
   4. Commit rules to repository
```

---

## Requirements

- Repository with existing tests
- GitHub access (to clone and analyze)
- Common test frameworks (Jest, Cypress, Go testing, pytest, etc.)

**Note**: Works best with repos that have established test patterns. For repos with minimal tests, will generate basic rules that can be enhanced over time.

---

## Related Resources

- **RHOAI-QUALITY-ANALYSIS-2026.md** - Shows agent rules gap (12/13 repos)
- **QUALITY-STRATEGY.md** - Two-pillar strategy (this is Pillar 2)
- **odh-dashboard/.claude/rules/** - Gold standard example
- **Skill location**: `.claude/skills/test-rules-generator/`

---

## Conclusion

The Test Rules Generator skill enables **sustainable quality improvement** by teaching agents to create high-quality tests automatically. Combined with PR build validation (Pillar 1), it creates a comprehensive quality framework where quality is built-in, not bolted-on.

**Start with**: Repos that have good test coverage (notebooks, kserve, training-operator, kueue)
**Expand to**: All 13 repos
**Maintain**: Update rules as patterns evolve
