# Quality Gates - Frontier Standards

This document describes Chiron's comprehensive quality gates that enforce frontier-grade standards across all aspects of the codebase.

## Overview

Chiron implements 8 comprehensive quality gates that run on every push and pull request:

1. **Coverage Gate** - Ensures adequate test coverage
2. **Security Gate** - Enforces zero critical vulnerabilities
3. **Type Safety Gate** - Strict type checking with MyPy
4. **SBOM Gate** - Software Bill of Materials validation
5. **Code Quality Gate** - Linting and formatting standards
6. **Test Quality Gate** - All tests must pass
7. **Dependency Gate** - No dependency conflicts
8. **Documentation Gate** - Docs build successfully

## Quality Gate Details

### 1. Coverage Gate

**Purpose**: Ensure adequate test coverage across the codebase

**Standards**:
- **Minimum**: 50% (gate fails below this)
- **Target**: 60% (recommended for production)
- **Frontier**: 80% (frontier-grade excellence)

**Current Status**: 55.45% ✅ (exceeds minimum by 5.45%)

**How it works**:
```bash
# Run tests with coverage
uv run pytest --cov=chiron --cov-report=xml --cov-report=term-missing --cov-fail-under=50

# Check coverage against targets
COVERAGE=$(uv run coverage report | grep TOTAL | awk '{print $NF}' | sed 's/%//')
if (( $(echo "$COVERAGE >= 60" | bc -l) )); then
  echo "✅ Coverage meets target"
fi
```

**Improving Coverage**:
- Focus on high-impact modules first (deps, service, CLI)
- Add unit tests for core logic
- Add integration tests for subprocess interactions
- See [DEPS_MODULES_STATUS.md](DEPS_MODULES_STATUS.md) for systematic plan

### 2. Security Gate

**Purpose**: Enforce zero critical/high severity vulnerabilities

**Standards**:
- **Critical vulnerabilities**: 0 (gate fails on any)
- **High severity issues**: 0 (gate fails on any)
- **Medium/Low**: Allowed but logged for review

**Tools Used**:
- **Bandit**: Static security analysis for Python
- **Safety**: Known vulnerability scanning
- **Semgrep**: Pattern-based security analysis

**How it works**:
```bash
# Run Bandit
uv run bandit -r src/ -f json -o bandit-report.json
CRITICAL_COUNT=$(jq '[.results[] | select(.issue_severity == "HIGH" or .issue_severity == "CRITICAL")] | length' bandit-report.json)
if [ "$CRITICAL_COUNT" -gt 0 ]; then
  echo "❌ SECURITY GATE FAILED"
  exit 1
fi

# Run Safety
uv run safety check --json --output safety-report.json

# Run Semgrep
semgrep --config=auto --sarif-output=semgrep.sarif
```

**Common Issues**:
- Hardcoded secrets → Use environment variables or key management
- SQL injection → Use parameterized queries
- Command injection → Use `subprocess_utils` with proper escaping
- Path traversal → Validate and sanitize file paths

### 3. Type Safety Gate

**Purpose**: Ensure type safety with strict type checking

**Standards**:
- **Mode**: Strict MyPy checking enabled
- **Failures**: 0 type errors allowed
- **Coverage**: All public APIs must be typed

**Configuration** (pyproject.toml):
```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
```

**How it works**:
```bash
uv run mypy src/chiron --strict
```

**Common Issues**:
- Missing type hints → Add type annotations
- `Any` type usage → Use specific types
- Untyped third-party imports → Add type stubs or ignore_missing_imports

### 4. SBOM Gate

**Purpose**: Validate Software Bill of Materials and scan for vulnerabilities

**Standards**:
- **SBOM Format**: CycloneDX JSON + SPDX JSON
- **Component Count**: > 0 (validation check)
- **Critical Vulnerabilities**: 0 in SBOM scan
- **High Vulnerabilities**: Logged for review

**Tools Used**:
- **Syft**: SBOM generation
- **Grype**: Vulnerability scanning

**How it works**:
```bash
# Generate SBOM
syft . -o cyclonedx-json=sbom.json
syft . -o spdx-json=sbom-spdx.json

# Validate SBOM format
COMPONENT_COUNT=$(jq '.components | length' sbom.json)
if [ "$COMPONENT_COUNT" -eq 0 ]; then
  echo "❌ SBOM validation failed"
  exit 1
fi

# Scan for vulnerabilities
grype sbom:./sbom.json -o json --file vulnerability-report.json
CRITICAL_VULNS=$(jq '[.matches[] | select(.vulnerability.severity == "Critical")] | length' vulnerability-report.json)
if [ "$CRITICAL_VULNS" -gt 0 ]; then
  echo "❌ VULNERABILITY GATE FAILED"
  exit 1
fi
```

**Artifacts Generated**:
- `sbom.json` - CycloneDX SBOM
- `sbom-spdx.json` - SPDX SBOM
- `vulnerability-report.json` - Vulnerability scan results

### 5. Code Quality Gate

**Purpose**: Enforce code quality standards with linting and formatting

**Standards**:
- **Linting errors**: 0 allowed
- **Format violations**: 0 allowed
- **Complexity**: Monitored but not enforced

**Tools Used**:
- **Ruff**: Fast Python linter and formatter

**How it works**:
```bash
# Run linter
uv run ruff check src/chiron --output-format=json > ruff-report.json
ERROR_COUNT=$(jq 'length' ruff-report.json)
if [ "$ERROR_COUNT" -gt 0 ]; then
  echo "❌ CODE QUALITY GATE FAILED"
  exit 1
fi

# Check formatting
uv run ruff format --check src/chiron
```

**Common Issues**:
- Import order → Ruff auto-fixes with `--fix`
- Line length → Wrap at 88 characters
- Unused imports → Ruff auto-fixes with `--fix`
- Complexity → Refactor complex functions

### 6. Test Quality Gate

**Purpose**: Ensure all tests pass and maintain test quality

**Standards**:
- **Failed tests**: 0 allowed
- **Minimum tests**: 100 recommended
- **Test types**: Unit, integration, property-based

**How it works**:
```bash
# Run tests with JSON report
uv run pytest --json-report --json-report-file=test-report.json

# Validate results
FAILED_TESTS=$(jq '.summary.failed // 0' test-report.json)
if [ "$FAILED_TESTS" -gt 0 ]; then
  echo "❌ TEST QUALITY GATE FAILED"
  exit 1
fi
```

**Test Quality Metrics**:
- **Total tests**: 254 (target: 350 for 60% coverage)
- **Test types**: Unit (90%), Integration (8%), Contract (2%)
- **Average duration**: ~6 seconds
- **Flaky tests**: 0 tolerance

### 7. Dependency Gate

**Purpose**: Ensure dependency integrity and consistency

**Standards**:
- **Lock file**: Must be synchronized
- **Conflicts**: 0 allowed
- **Security**: No known vulnerabilities in dependencies

**How it works**:
```bash
# Check for dependency conflicts
uv sync --locked

# Validate pyproject.toml
python3 -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))"
```

**Common Issues**:
- Version conflicts → Adjust version constraints
- Lock file drift → Run `uv lock` to update
- Missing dependencies → Add to pyproject.toml

### 8. Documentation Gate

**Purpose**: Ensure documentation builds successfully

**Standards**:
- **Build**: Must complete without errors
- **Links**: Checked for validity
- **Strict mode**: Enabled (warnings = errors)

**How it works**:
```bash
# Build documentation
uv run mkdocs build --strict
```

**Documentation Structure**:
- `/docs` - User and developer guides
- `/docs/index.md` - Documentation homepage
- API docs - Auto-generated from docstrings

## Quality Gate Workflow

The quality gates run in parallel on GitHub Actions:

```yaml
jobs:
  coverage-gate:    # Runs in ~2 minutes
  security-gate:    # Runs in ~3 minutes
  type-safety-gate: # Runs in ~1 minute
  sbom-gate:        # Runs in ~2 minutes
  code-quality-gate:# Runs in ~1 minute
  test-quality-gate:# Runs in ~2 minutes
  dependency-gate:  # Runs in ~1 minute
  docs-gate:        # Runs in ~1 minute
  
  quality-gate-summary: # Aggregates results
    needs: [all gates above]
```

Total runtime: ~3-4 minutes (parallel execution)

## Local Development

### Running All Quality Gates Locally

```bash
# Install dependencies
uv sync

# Run all quality checks
make quality-check  # or use individual commands below
```

### Individual Gate Commands

```bash
# Coverage gate
uv run pytest --cov=chiron --cov-report=term-missing --cov-fail-under=50

# Security gate
uv run bandit -r src/ -f json
uv run safety check --json

# Type safety gate
uv run mypy src/chiron --strict

# Code quality gate
uv run ruff check src/chiron
uv run ruff format --check src/chiron

# Test quality gate
uv run pytest

# Dependency gate
uv sync --locked

# Documentation gate
uv run mkdocs build --strict
```

### Auto-fixing Common Issues

```bash
# Auto-fix linting issues
uv run ruff check --fix src/chiron

# Auto-format code
uv run ruff format src/chiron

# Update lock file
uv lock

# Run pre-commit hooks
uv run pre-commit run --all-files
```

## Continuous Improvement

### Coverage Improvement Plan

**Current**: 55.45% → **Target**: 60% → **Frontier**: 80%

Priority modules for testing:
1. **deps modules** (0% → 50%+) - Highest impact
2. **service routes** (48-77% → 80%+) - User-facing
3. **CLI commands** (30% → 60%+) - User-facing
4. **MCP server** (96% infra → real operations) - Feature enablement

See [DEPS_MODULES_STATUS.md](DEPS_MODULES_STATUS.md) for detailed plan.

### Security Improvements

- Regular dependency updates via Renovate
- SBOM generation on every build
- Vulnerability scanning in CI
- Secret scanning with GitHub Advanced Security
- Supply chain security with SLSA provenance

### Documentation Improvements

- Keep docs in sync with code
- Add usage examples for all public APIs
- Create video tutorials for complex workflows
- Maintain changelog with semantic versioning
- Update guides when features change

## Quality Metrics Dashboard

### Current Status (April 2025)

| Metric | Current | Target | Frontier | Status |
|--------|---------|--------|----------|--------|
| Coverage | 55.45% | 60% | 80% | 🟡 On Track |
| Tests | 254 | 350 | 500 | 🟡 On Track |
| Critical Vulns | 0 | 0 | 0 | 🟢 Passing |
| Type Errors | 0 | 0 | 0 | 🟢 Passing |
| Lint Errors | 0 | 0 | 0 | 🟢 Passing |
| Failed Tests | 0 | 0 | 0 | 🟢 Passing |
| Dep Conflicts | 0 | 0 | 0 | 🟢 Passing |
| Doc Build | Pass | Pass | Pass | 🟢 Passing |

**Overall Grade**: 🟡 Yellow (6/8 gates green, improving toward frontier)

### Frontier Grade Criteria

To achieve frontier-grade status (🟢 Green across all metrics):

- ✅ All 8 quality gates passing
- ⏳ Coverage ≥ 80%
- ⏳ Tests ≥ 500
- ✅ Zero critical vulnerabilities
- ✅ Zero type errors
- ✅ Zero lint errors
- ✅ Zero failed tests
- ✅ Zero dependency conflicts
- ✅ Documentation builds successfully

**Estimated Timeline**: 2-3 sprints to reach frontier grade

## Troubleshooting

### Coverage Gate Fails

```bash
# Generate detailed coverage report
uv run pytest --cov=chiron --cov-report=html
# Open htmlcov/index.html to see uncovered lines

# Focus on high-impact modules
# See DEPS_MODULES_STATUS.md for systematic plan
```

### Security Gate Fails

```bash
# Review specific issues
jq '.results[]' bandit-report.json

# Common fixes:
# - Move secrets to environment variables
# - Use subprocess_utils instead of raw subprocess
# - Validate and sanitize user input
```

### Type Safety Gate Fails

```bash
# Run MyPy with detailed output
uv run mypy src/chiron --strict --show-error-codes

# Common fixes:
# - Add type hints to functions
# - Replace Any with specific types
# - Add return type annotations
```

### SBOM Gate Fails

```bash
# Check SBOM validity
jq '.' sbom.json

# Re-generate SBOM
syft . -o cyclonedx-json=sbom.json

# Check vulnerability scan
jq '.matches[] | select(.vulnerability.severity == "Critical")' vulnerability-report.json
```

## References

- [Quality Gates Workflow](../.github/workflows/quality-gates.yml)
- [DEPS_MODULES_STATUS.md](DEPS_MODULES_STATUS.md)
- [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md)
- [CHIRON_UPGRADE_PLAN.md](../CHIRON_UPGRADE_PLAN.md)
- [CI Configuration](../.github/workflows/ci.yml)
