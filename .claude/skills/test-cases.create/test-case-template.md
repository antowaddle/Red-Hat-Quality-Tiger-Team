# {test_case_id}: {title}

**Priority**: {P0|P1|P2}
**Objective**: {one sentence explaining the test goal}

{include Preconditions only if there are specific requirements beyond the default test environment}
**Preconditions**:
- {required state or setup before test execution}

**Test Steps**:
1. {actionable step with specific details}
2. {verify step with concrete checks}

**Expected Results**:
- {concrete, verifiable outcome}

{include Test Data only if there are specific requests, payloads, or configurations to show}
**Test Data**:
```{bash|yaml|json}
{example request, payload, or configuration}
```

{include Expected Response only if showing a concrete response body adds clarity}
**Expected Response**:
```json
{example response body with realistic data}
```

{include Validation only if the test requires verification beyond the API response, e.g., database queries}
**Validation**:
- {database query or cross-validation step}

**Automation Status**: To be filled later in the process.

**Notes**: To be filled later in the process.
