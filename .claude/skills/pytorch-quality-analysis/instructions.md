# PyTorch Quality Analysis — Instructions

## Task

Analyze a PyTorch or ML framework repository's quality practices across 6 pillars and provide actionable recommendations.

## Input

- Repository URL (required)
- Branch name (optional, defaults to main/master)

## How to Execute

**DO NOT use the Agent tool for this analysis.**

Instead, perform the analysis yourself in the main conversation:
1. Use git:shallow-clone skill or Bash tool to clone the repository
2. Analyze all aspects described in the Process steps below
3. Use the Write tool to save the markdown report as `quality-analysis-{repo-name}.md`
4. Use Bash tool to run the HTML generator (reuse from `quality-repo-analysis`)
5. Use Bash tool to open the HTML file

This ensures files are written to the correct location and permissions are properly handled.

## Process

### Step 0: Pre-flight Checks

**CRITICAL**: Verify Python dependencies before starting.

1. **Check PyYAML availability**
   ```bash
   uv run --with pyyaml python3 -c "import yaml; print('PyYAML available')"
   ```

2. **If the check fails**, install dependencies:
   ```bash
   uv pip install -r .claude/skills/quality-repo-analysis/requirements.txt
   ```

3. **Do NOT proceed** until PyYAML is confirmed available.

### Step 1: Repository Discovery

1. Clone or access the repository (use `--depth 1` for large repos like PyTorch)
2. Identify repository type: ML framework, model library, serving tool, training tool
3. Detect primary languages (Python, C++, CUDA/HIP)
4. Identify build system (setuptools + CMake, pyproject.toml, setup.py)
5. Note the repo size — PyTorch is very large, focus on key directories

### Step 2: Testability Analysis (30%)

Examine test infrastructure comprehensively:

1. **Test File Inventory**
   - Count test files: `test_*.py`, `*_test.py`, `*_test.cpp`, `test_*.cpp`
   - Identify test directories: `test/`, `tests/`, `test/cpp/`
   - Calculate test-to-code ratio

2. **Testing Frameworks**
   - Python: pytest, unittest, hypothesis
   - C++: GoogleTest, gmock
   - Check pytest.ini, conftest.py, setup.cfg for config

3. **PyTorch-Specific Test Patterns**
   - `instantiate_device_type_tests()` — device-agnostic test generation
   - `@dtypes(torch.float32, torch.float16, ...)` — dtype coverage
   - `@parametrize` — parameterized tests
   - `OpInfo()` — operator test definitions
   - `TestCase` (from `torch.testing._internal`) — PyTorch test base class
   - `run_tests()` — test runner

4. **CI Matrix Coverage**
   - Devices tested in CI (CPU, CUDA, ROCm, XPU, MPS)
   - Dtype coverage in CI matrix
   - Platform coverage (Linux, macOS, Windows, aarch64)
   - Sharding and parallelization strategy

5. **Test Health**
   - Flaky test identification and tracking
   - Test isolation (no execution-order dependencies)
   - Coverage tracking integration (Codecov, .coveragerc)
   - PR-level coverage gates

### Step 3: Correctness Analysis (20%)

Examine numerical validation and correctness practices:

1. **Numerical Comparison Patterns**
   - Usage of `torch.testing.assert_close()` (preferred)
   - Legacy `assertEqual()` for tensor comparison (flag as gap)
   - Explicit `rtol` and `atol` tolerance specifications

2. **Gradient Verification**
   - `torch.autograd.gradcheck()` usage
   - `torch.autograd.gradgradcheck()` for second-order gradients
   - Coverage of autograd formulas

3. **Edge Case Testing**
   - NaN, Inf handling
   - Empty tensors, zero-dim tensors
   - Large tensors, boundary shapes
   - Mixed dtypes

4. **Determinism**
   - `torch.use_deterministic_algorithms()` tests
   - CUBLAS workspace config
   - Random seed management

5. **Error Handling**
   - Proper exception types raised
   - Clear, actionable error messages
   - Input validation (shapes, dtypes, devices)

### Step 4: Completeness Analysis (15%)

Examine operator and feature coverage:

1. **Operator Coverage**
   - Count operators with OpInfo definitions
   - Check for `NotImplementedError` in operator implementations
   - Dispatcher kernel registrations completeness

2. **Subsystem Coverage**
   - Autograd backward pass formulas
   - Dynamo/Inductor compiler support per op
   - Distributed (DDP, FSDP, DTensor) coverage
   - Quantization op implementations
   - Sparse tensor support
   - Complex number support

### Step 5: Maintainability Analysis (15%)

Review documentation and code quality:

1. **Documentation**
   - Public API docstrings
   - Type hints on function signatures
   - `__all__` defined in modules
   - CONTRIBUTING.md and developer guides

2. **Agent Rules**
   - Check for `CLAUDE.md` or `AGENTS.md` in root
   - Check for `.claude/` directory
   - Examine `.claude/rules/` for test creation rules
   - Review `.claude/skills/` for custom skills
   - Check for `.cursor/rules/`

3. **Code Quality Tools**
   - Linting: ruff, flake8, mypy, pyrefly, clang-tidy, clang-format
   - Check `.lintrunner.toml` for orchestrated lint config
   - Pre-commit hooks (`.pre-commit-config.yaml`)
   - Formatters: ruff format, isort, usort

### Step 6: Compatibility Analysis (10%)

Examine API stability and cross-version support:

1. **Modern API Adoption**
   - `torch.accelerator` usage vs deprecated `torch.cuda.is_available()`
   - Deprecated API audit

2. **Backward Compatibility**
   - BC test suite presence
   - Version-conditional features
   - Serialization compatibility (model save/load across versions)

3. **Export Compatibility**
   - `torch.export.export()` coverage
   - `torch.onnx.export()` coverage
   - TorchScript (`torch.jit.script`, `torch.jit.trace`)

4. **Platform Support**
   - Python version matrix (3.10-3.14)
   - OS support (Linux, macOS, Windows)
   - Architecture support (x86_64, aarch64, s390x, RISC-V)

### Step 7: Performance Analysis (10%)

Examine benchmarking and regression detection:

1. **Benchmark Infrastructure**
   - Benchmark suites (TorchBench, operator benchmarks)
   - CI performance gates
   - Inductor perf test workflows

2. **Memory Testing**
   - Memory profiling tests
   - Peak memory tracking
   - Allocation tracking

3. **Profiling Integration**
   - `torch.profiler` usage
   - `torch.compile` performance tracking
   - Inference latency benchmarks
   - Training throughput benchmarks

4. **Distributed Scaling**
   - Multi-GPU benchmarks
   - Scaling efficiency tests

### Step 8: Gap Analysis

Compare findings against ML gold standards:

1. **PyTorch upstream patterns**
   - OpInfo-driven testing, device-agnostic patterns
   - 142-workflow CI matrix with target determination
   - Substantive CLAUDE.md and `.claude/skills/`

2. **JAX comparison**
   - Functional testing approach
   - XLA backend coverage
   - Type checking rigor

3. **TensorFlow comparison**
   - Coverage enforcement with Codecov
   - Security scanning (SAST, Dependabot)
   - Multi-platform CI breadth

4. **Tiger Team baselines** (odh-dashboard, notebooks, kserve)
   - Agent rules completeness
   - Container image testing
   - Coverage gates

### Step 9: Generate Reports (Markdown + HTML)

**First, extract the repository name from the URL:**
- For `https://github.com/owner/repo-name`, extract `repo-name`
- Use the last segment after the final `/`

1. **Save the Markdown Report**
   - **IMPORTANT**: Use Write tool with RELATIVE PATH (filename only)
   - Write as `quality-analysis-{repo-name}.md`
   - **CRITICAL**: Include YAML frontmatter (see Output Format below)

2. **Generate HTML Report**
   - Reuse the HTML generator from `quality-repo-analysis`:
   ```bash
   uv run --with pyyaml python3 .claude/skills/quality-repo-analysis/html_generator.py \
     quality-analysis-{repo-name}.md \
     quality-report-{repo-name}.html
   ```

3. **Open the HTML Report**
   ```bash
   open quality-report-{repo-name}.html    # macOS
   xdg-open quality-report-{repo-name}.html  # Linux
   ```

4. **Provide Summary**
   - Report file paths to the user
   - Highlight top 3 critical gaps
   - List quick wins

## Output Format

**IMPORTANT**: Reports MUST include YAML frontmatter for structured data extraction.

```markdown
---
repository: "pytorch/pytorch"
overall_score: 7.1
scorecard:
  - dimension: "Testability"
    score: 8.0
    status: "Massive test corpus (~1,700+ files); device-agnostic patterns; rich OpInfo coverage"
  - dimension: "Correctness"
    score: 7.5
    status: "Good gradcheck coverage; assert_close adoption; mixed legacy assertEqual usage"
  - dimension: "Completeness"
    score: 8.0
    status: "Comprehensive op coverage; strong Dynamo/distributed support"
  - dimension: "Maintainability"
    score: 6.0
    status: "CLAUDE.md present; good linting; no .claude/rules/"
  - dimension: "Compatibility"
    score: 5.0
    status: "Multi-platform CI; BC tests exist; some deprecated APIs remain"
  - dimension: "Performance"
    score: 6.0
    status: "Benchmarks exist; profiling available; no PR-level perf gates"
critical_gaps:
  - title: "No PR-level coverage enforcement"
    impact: "Coverage regressions merge undetected"
    severity: "HIGH"
    effort: "8-12 hours"
  - title: "Mixed assertEqual/assert_close usage"
    impact: "Inconsistent numerical validation across test suite"
    severity: "MEDIUM"
    effort: "4-8 hours"
  - title: "No .claude/rules/ for test automation"
    impact: "AI agents lack structured guidance on test patterns"
    severity: "MEDIUM"
    effort: "2-3 hours"
quick_wins:
  - title: "Add .claude/rules/ for test patterns"
    effort: "2-3 hours"
    impact: "Consistent AI-generated tests"
  - title: "Integrate Codecov with PR coverage gates"
    effort: "4-6 hours"
    impact: "Automated coverage regression detection"
  - title: "Migrate assertEqual to assert_close in core test files"
    effort: "4-8 hours"
    impact: "Consistent numerical validation"
recommendations:
  priority_0:
    - "Integrate Codecov with PR coverage gates and minimum thresholds"
    - "Migrate remaining assertEqual tensor comparisons to assert_close"
  priority_1:
    - "Create .claude/rules/ with test type rules for AI agent guidance"
    - "Add PR-level performance regression gates for critical paths"
    - "Consolidate Flake8 + Ruff into Ruff-only"
  priority_2:
    - "Add pre-commit framework for enforced local checks"
    - "Create AGENTS.md for broader AI agent compatibility"
---

# Quality Analysis: [Repository Name]

## Executive Summary
- Overall Score: X/10
- Key Strengths: ...
- Critical Gaps: ...
- Agent Rules Status: [Present/Missing/Incomplete]

## Quality Scorecard
| Pillar | Score | Weight | Status |
|--------|-------|--------|--------|
| Testability | X/10 | 30% | ... |
| Correctness | X/10 | 20% | ... |
| Completeness | X/10 | 15% | ... |
| Maintainability | X/10 | 15% | ... |
| Compatibility | X/10 | 10% | ... |
| Performance | X/10 | 10% | ... |

## Critical Gaps
1. [Gap description]
   - Impact: ...
   - Severity: HIGH/MEDIUM/LOW
   - Effort: X hours

## Quick Wins
1. [Improvement description]
   - Effort: X hours
   - Impact: [description]

## Detailed Findings

### Testability
[Analysis of test coverage, frameworks, device-agnostic patterns, OpInfo...]

### Correctness
[Analysis of numerical validation, gradcheck, edge cases, determinism...]

### Completeness
[Analysis of operator coverage, subsystem support...]

### Maintainability
[Analysis of documentation, agent rules, linting...]

### Compatibility
[Analysis of API modernization, BC tests, platform support...]

### Performance
[Analysis of benchmarks, profiling, regression detection...]

## Recommendations

### Priority 0 (Critical)
[Items...]

### Priority 1 (High Value)
[Items...]

### Priority 2 (Nice-to-Have)
[Items...]

## Comparison to Gold Standards
| Pillar | This Repo | PyTorch upstream | JAX | TensorFlow |
|--------|-----------|-----------------|-----|------------|
| Testability | X/10 | 8/10 | 7/10 | 8/10 |
| ... | | | | |

## PyTorch-Specific Patterns Detected
[Summary of patterns found: OpInfo, gradcheck, device tests, Dynamo, distributed...]

## File Paths Reference
[Key configuration files analyzed]
```

## Key Files to Examine

### Test Infrastructure
- `test/` — Main test directory
- `test/conftest.py` — pytest configuration and sharding
- `pytest.ini` — pytest settings
- `torch/testing/_internal/` — Test utilities and harness
- `torch/testing/_internal/opinfo/` — OpInfo operator definitions
- `torch/testing/_internal/common_device_type.py` — Device-agnostic testing
- `tools/code_coverage/` — Coverage tooling

### Correctness
- `torch/testing/` — `assert_close` and comparison utilities
- `torch/autograd/` — `gradcheck` implementation
- `test/test_autograd.py` — Autograd test suite

### CI/CD
- `.github/workflows/*.yml` — GitHub Actions workflows
- `.ci/` — CI scripts and Docker configs
- `.lintrunner.toml` — Lint orchestration

### Documentation & Agent Rules
- `CLAUDE.md` — Agent guidelines
- `.claude/skills/` — Claude skills
- `.claude/rules/` — Agent rules (if present)
- `CONTRIBUTING.md` — Contribution guidelines

### Code Quality
- `pyproject.toml` — Ruff, isort, usort, codespell config
- `.flake8` — Flake8 config
- `mypy.ini` — Type checking config
- `.clang-format` / `.clang-tidy` — C++ formatting/analysis
- `.coveragerc` — Coverage config

## Special Considerations

### For PyTorch Core
- Check OpInfo completeness for all operator categories
- Verify device-agnostic test coverage across CUDA/ROCm/XPU/MPS
- Assess Dynamo/Inductor compiler stack test depth
- Review distributed testing (DDP, FSDP, DTensor)

### For PyTorch Ecosystem Projects (torchtune, torchserve, etc.)
- May not have OpInfo or device-agnostic patterns
- Focus on integration testing with PyTorch core
- Check model training/inference test coverage
- Verify export compatibility testing

### For Very Large Repos
- Focus on key directories: `.github/`, `test/`, `torch/testing/`, root configs
- Use `--depth 1` for cloning
- Sample representative test files rather than analyzing all

## Error Handling

If repository is:
- **Private**: Request user to provide access or run locally
- **Very large**: Focus on key directories (PyTorch has 21,000+ files)
- **Not ML**: Recommend using the generic `quality-repo-analysis` skill instead
- **Ecosystem project**: Adjust expectations for OpInfo/device-agnostic patterns

## Time Management

- Quick scan: 10-15 minutes (high-level pillar scores)
- Standard analysis: 20-30 minutes (detailed findings)
- Comprehensive: 30-45 minutes (with code examples and implementation guidance)

Adjust depth based on repository size and complexity.
