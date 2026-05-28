# PyTorch Quality Analysis Skill

Analyzes the PyTorch repository against ML framework-specific quality standards and provides actionable recommendations for improvement.

## Usage

```bash
/pytorch-quality-analysis [repository-url]
```

## Examples

```bash
/pytorch-quality-analysis https://github.com/pytorch/pytorch
/pytorch-quality-analysis https://github.com/pytorch/torchtune
/pytorch-quality-analysis https://github.com/pytorch/serve
```

## Why a PyTorch-Specific Skill?

The generic `quality-repo-analysis` skill evaluates repositories against infrastructure-focused dimensions (CI/CD, container images, coverage tracking). PyTorch and ML frameworks have unique quality patterns that require specialized analysis:

- **Numerical correctness** — gradient checking, tolerance-based assertions, determinism
- **Operator coverage** — OpInfo, device-agnostic tests, dtype coverage
- **Multi-backend testing** — CUDA, ROCm, XPU, MPS, CPU
- **Compiler stack** — Dynamo, Inductor, TorchScript, Export
- **Distributed training** — DDP, FSDP, DTensor
- **Performance regression** — benchmarks, profiling, memory tracking

This skill complements the generic analysis by adding ML-specific depth.

## What It Analyzes

This skill evaluates PyTorch repositories across **6 weighted pillars**:

### 1. Testability (30%)
- Test coverage and test-to-code ratio
- Unit, integration, and E2E test presence
- Device-agnostic test patterns (`instantiate_device_type_tests`)
- Dtype coverage (`@dtypes` decorator)
- OpInfo operator test coverage
- CI matrix breadth (devices x dtypes)
- Flaky test tracking and test isolation

### 2. Correctness (20%)
- Numerical comparison (`assert_close` vs `assertEqual`)
- Gradient verification (`gradcheck`, `gradgradcheck`)
- Tolerance specifications (explicit `rtol`, `atol`)
- Edge case coverage (NaN, Inf, empty, zero-dim tensors)
- Determinism testing (`torch.use_deterministic_algorithms`)
- Input validation and error handling
- Numerical stability (overflow, underflow, precision loss)

### 3. Completeness (15%)
- Tier 1/2 operator implementation coverage
- Dispatcher kernel registrations
- Autograd formula coverage
- Dynamo/Inductor compiler support
- Distributed support (DDP, FSDP, DTensor)
- Quantization and sparse tensor support

### 4. Maintainability (15%)
- Documentation (docstrings, type hints, `__all__` exports)
- Agent rules (CLAUDE.md, `.claude/rules/`, `.claude/skills/`)
- Linting configuration and enforcement
- Code review process and contribution guidelines

### 5. Compatibility (10%)
- Modern API adoption (`torch.accelerator`)
- Backward compatibility test suite
- Python version and platform support
- Serialization compatibility (save/load across versions)
- Export compatibility (ONNX, TorchScript, `torch.export`)

### 6. Performance (10%)
- Benchmark suites and CI performance gates
- Memory profiling and regression detection
- `torch.compile` performance tracking
- Distributed scaling benchmarks
- Profiling tool integration (`torch.profiler`)

## Output

The skill generates a comprehensive report in **two formats**:

### 1. Markdown Report
A detailed markdown document saved as `quality-analysis-{repo}.md` with:

- **YAML Frontmatter** — Structured data for reliable HTML generation
- **Quality Scorecard** — Scores across all 6 pillars
- **Critical Gaps** — High-priority issues with severity and effort estimates
- **Quick Wins** — Low-effort, high-impact improvements
- **Detailed Findings** — Pillar-by-pillar analysis
- **Recommendations** — Prioritized action items (P0/P1/P2)
- **Comparison** — Benchmarking against ML gold standards

### 2. HTML Report (Interactive) — Generated Automatically
Reuses the existing `html_generator.py` from `quality-repo-analysis` to produce an interactive HTML dashboard with animated scores, color-coded severity, and collapsible sections.

Both files are created automatically when you run the skill.

## Gold Standards

The analysis compares repositories against these ML framework gold standards:

- **PyTorch upstream** — OpInfo coverage, device-agnostic testing, comprehensive CI matrix
- **JAX** — Functional testing patterns, XLA backend coverage
- **TensorFlow** — Coverage enforcement, security scanning, multi-platform CI
- **odh-dashboard** — Agent rules, contract testing (from Tiger Team baselines)

## Scoring Criteria

Each pillar is scored 0-10:

- **10**: Gold standard, exceeds expectations
- **8-9**: Strong practices, minor gaps
- **6-7**: Adequate, moderate improvements needed
- **4-5**: Weak, significant gaps
- **0-3**: Critical gaps, major work required

Overall score is weighted average:
- Testability: 30%
- Correctness: 20%
- Completeness: 15%
- Maintainability: 15%
- Compatibility: 10%
- Performance: 10%

## Relationship to Generic Skill

This skill is designed to **complement** the generic `quality-repo-analysis` skill:

| Aspect | Generic Skill | PyTorch Skill |
|--------|--------------|---------------|
| Scope | Any repository | ML frameworks (PyTorch-focused) |
| Dimensions | 7 (infra-focused) | 6 (ML-specific) |
| Patterns | CI/CD, containers, coverage | Gradcheck, OpInfo, Dynamo, distributed |
| Gold standards | odh-dashboard, notebooks, kserve | PyTorch upstream, JAX, TensorFlow |

## Time Estimate

- Quick analysis: 10-15 minutes
- Comprehensive analysis: 20-30 minutes
- With detailed recommendations: 30-45 minutes

## Requirements

- Repository must be publicly accessible
- Works best with Python/C++/CUDA ML framework projects
- Python 3.6+ required for HTML report generation
- PyYAML required for YAML frontmatter parsing

## Files

- `SKILL.md` — This documentation
- `instructions.md` — Detailed analysis instructions for the agent
- `sample_report.md` — Example output report
