# CI/CD Workflows Reference

This document provides an overview of the CI/CD workflows used in the Chiron project.

## Available Workflows

### Quality Gates (`.github/workflows/quality-gates.yml`)

Comprehensive quality enforcement across 9 gates:

1. **Policy Gate** - OPA/Conftest policy enforcement
2. **Coverage Gate** - Minimum 50%, target 65%, frontier 80%
3. **Security Gate** - Zero critical vulnerabilities (Bandit, Safety, Semgrep)
4. **Type Safety Gate** - Strict MyPy type checking
5. **SBOM Gate** - Software Bill of Materials generation and validation
6. **Code Quality Gate** - Ruff linting and formatting
7. **Test Quality Gate** - All tests must pass (765+ tests)
8. **Dependency Gate** - No dependency conflicts
9. **Documentation Gate** - Documentation builds successfully

### CI Workflow (`.github/workflows/ci.yml`)

Main continuous integration workflow:

- Multi-Python testing (3.12)
- Multi-OS testing (Ubuntu, macOS, Windows)
- Pre-commit hook validation
- Coverage reporting to Codecov
- Security scanning
- SBOM generation
- Distribution building
- Wheel building with cibuildwheel

### Additional Workflows

- **CodeQL Analysis** (`.github/workflows/codeql.yml`) - Security analysis
- **Coverage on Diff** (`.github/workflows/diff-cover.yml`) - 80%+ coverage on changes
- **Documentation Linting** (`.github/workflows/docs-lint.yml`) - Vale style checking
- **Trivy Scanning** (`.github/workflows/trivy.yml`) - Container security
- **Sigstore Verification** (`.github/workflows/sigstore-verify.yml`) - Artifact signatures
- **Reproducibility** (`.github/workflows/reproducibility.yml`) - Build verification
- **Environment Sync** (`.github/workflows/sync-env.yml`) - Dev/CI alignment
- **Wheels** (`.github/workflows/wheels.yml`) - Multi-platform wheel building
- **Release** (`.github/workflows/release.yml`) - PyPI publishing
- **Airgap** (`.github/workflows/airgap.yml`) - Offline bundle creation

## Running Workflows Locally

### Quality Gates

Use the local quality toolbox to run the same checks as CI:

```bash
# Full quality suite
hephaestus tools qa --profile full

# Fast checks
hephaestus tools qa --profile fast

# Dry run to see what would execute
hephaestus tools qa --profile full --dry-run
```

### Individual Quality Checks

```bash
# Coverage
uv run pytest --cov=chiron --cov-report=term-missing --cov-fail-under=50

# Security
uv run bandit -r src/ -f json
uv run safety check --json

# Type safety
uv run mypy src/chiron --strict

# Code quality
uv run ruff check src/chiron
uv run ruff format --check src/chiron

# Tests
uv run pytest

# Dependencies
uv sync --locked

# Documentation
uv run mkdocs build --strict
```

## Badge Status

The following badges reflect CI/CD workflow status:

- [![CI](https://github.com/IAmJonoBo/Chiron/workflows/CI/badge.svg)](https://github.com/IAmJonoBo/Chiron/actions/workflows/ci.yml)
- [![Quality Gates](https://github.com/IAmJonoBo/Chiron/workflows/Quality%20Gates/badge.svg)](https://github.com/IAmJonoBo/Chiron/actions/workflows/quality-gates.yml)

## See Also

- [Quality Gates Documentation](QUALITY_GATES.md) - Detailed quality standards
- [Environment Sync](ENVIRONMENT_SYNC.md) - Keeping CI and dev aligned
- [Contributing Guide](CONTRIBUTING.md) - Development workflow
