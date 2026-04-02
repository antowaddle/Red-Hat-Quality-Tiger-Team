# Test Rules Generator Skill

Automatically generates Claude Code agent rules for test creation by analyzing existing test patterns in a repository.

## Usage

```bash
/test-rules-generator [repository-url]
```

## Examples

```bash
/test-rules-generator https://github.com/opendatahub-io/odh-dashboard
/test-rules-generator https://github.com/opendatahub-io/kserve
/test-rules-generator https://github.com/kubeflow/training-operator
```

## What It Generates

This skill analyzes a repository's existing test patterns and generates Claude Code agent rules for:

### 1. Unit Test Rules
- Testing framework and patterns
- Test file naming conventions
- Test structure (describe/it blocks)
- Mock patterns and factories
- Assertion patterns
- Coverage expectations

### 2. Mock Test Rules (if applicable)
- Mock test framework (Cypress, etc.)
- Interceptor patterns
- Page object patterns
- Test data management
- Validation patterns

### 3. E2E Test Rules (if applicable)
- E2E framework and infrastructure
- Test environment setup
- Resource management
- Cleanup patterns
- Wait strategies

### 4. Contract Test Rules (if applicable)
- Contract testing framework
- API schema validation
- BFF test patterns
- Request/response validation

## Output

The skill generates a `.claude/rules/` directory structure with:

```text
.claude/
├── rules/
│   ├── testing-standards.md    # Cross-cutting testing guidance
│   ├── unit-tests.md           # Unit test patterns
│   ├── mock-tests.md           # Mock test patterns (if found)
│   ├── e2e-tests.md            # E2E test patterns (if found)
│   └── contract-tests.md       # Contract test patterns (if found)
└── README.md                    # How to use the rules
```

## Process

### Step 1: Repository Analysis
- Clone or access the repository
- Identify test directories and frameworks
- Detect test types (unit, integration, E2E, contract, mock)
- Identify primary language and frameworks

### Step 2: Pattern Extraction

For each test type found:

1. **Sample Test Analysis**
   - Collect 5-10 representative test files
   - Extract common patterns
   - Identify framework conventions
   - Note best practices

2. **Pattern Categories**
   - Test structure and organization
   - Naming conventions
   - Setup/teardown patterns
   - Assertion styles
   - Mock/stub patterns
   - Test data management
   - Error handling

3. **Framework-Specific Patterns**
   - Jest/React Testing Library (TypeScript)
   - Go testing package
   - Cypress (E2E/Mock)
   - Contract testing frameworks
   - Custom test utilities

### Step 3: Rule Generation

Generate markdown files with:

1. **Description Section**
   - When to use this test type
   - What it tests
   - Framework and tools

2. **Structure Section**
   - File naming and location
   - Test organization
   - describe/it patterns

3. **Pattern Examples**
   - Good examples from the repo
   - Anti-patterns to avoid
   - Best practices

4. **Conventions Section**
   - Naming conventions
   - Selector patterns
   - Mock patterns
   - Assertion patterns

5. **Checklist Section**
   - Before writing tests
   - During implementation
   - After implementation
   - Quality gates

## Key Features

- **Pattern-Based Learning**: Extracts actual patterns from existing tests
- **Repository-Specific**: Tailored to the repo's conventions and structure
- **Multiple Test Types**: Handles unit, mock, E2E, and contract tests
- **Framework-Aware**: Adapts to Jest, Cypress, Go testing, etc.
- **Actionable**: Generates rules agents can immediately use

## Requirements

- Repository must be publicly accessible
- Repository must have existing tests to analyze
- Works best with TypeScript, Go, Python, JavaScript projects

## Time Estimate

- Quick analysis: 10-15 minutes
- Comprehensive analysis: 20-30 minutes
- With custom examples: 30-45 minutes

## Benefits

1. **Consistency**: Ensures agents create tests following repo conventions
2. **Quality**: Maintains test quality standards across contributions
3. **Onboarding**: New developers/agents learn patterns faster
4. **Automation**: Enables agents to auto-create tests without manual guidance
5. **Documentation**: Living documentation of test patterns
