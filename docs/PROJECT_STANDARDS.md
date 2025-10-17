# Project Standards & Organization

This document defines the organizational standards, best practices, and quality requirements for the Chiron project as a frontier-grade, production-ready Python library.

## Overview

Chiron follows a comprehensive set of standards to ensure:

- **Code Quality**: Consistent, maintainable, and well-tested code
- **Security First**: Zero critical vulnerabilities, SBOM generation, artifact signing
- **Documentation**: Complete, accurate, and accessible documentation
- **Automation**: Automated quality gates and continuous validation
- **Developer Experience**: Clear guidelines, modern tooling, and helpful feedback

## Directory Structure

```
Chiron/
├── .github/                    # GitHub configuration
│   ├── workflows/              # CI/CD pipelines
│   └── copilot-instructions.md # GitHub Copilot agent instructions
├── docs/                       # Documentation (Diátaxis structure)
│   ├── getting-started/        # Tutorials for new users
│   ├── tutorials/              # Step-by-step guides
│   ├── deprecated/             # Archived documentation
│   └── *.md                    # How-to, reference, and explanation docs
├── src/chiron/                 # Main library code
│   ├── cli/                    # Command-line interface
│   ├── deps/                   # Supply chain management
│   ├── github/                 # GitHub integrations
│   ├── mcp/                    # Model Context Protocol server
│   ├── observability/          # OpenTelemetry integration
│   ├── orchestration/          # Workflow orchestration
│   ├── service/                # FastAPI service layer
│   └── *.py                    # Core modules
├── tests/                      # Test suite
│   ├── test_contracts.py       # Pact contract tests
│   └── test_*.py               # Unit and integration tests
├── hephaestus/                # Hephaestus developer toolkit (sister project)
│   └── hephaestus-toolkit/     # Refactoring utilities and scripts
├── scripts/                    # Utility scripts
├── policy/                     # OPA policy definitions
├── chaos/                      # Chaos engineering experiments
├── pyproject.toml              # Project configuration
├── mkdocs.yml                  # Documentation configuration
├── uv.lock                     # Locked dependencies
└── README.md                   # Project overview
```

## Code Standards

### Python Version

- **Required**: Python 3.12+
- **Tested**: Python 3.12.x
- **Style**: Modern Python with type hints

### Code Style

#### Formatting

- **Tool**: Ruff (replaces Black + isort)
- **Line Length**: 100 characters
- **Import Sorting**: Automatic with Ruff

#### Linting

- **Tool**: Ruff (replaces Flake8, pylint, etc.)
- **Rules**: All enabled, with project-specific exceptions in `pyproject.toml`
- **Standard**: Zero linting errors required

#### Type Checking

- **Tool**: MyPy
- **Mode**: Strict
- **Coverage**: All public APIs must be fully typed
- **Modern Syntax**: Use `dict`, `list`, `tuple` instead of `typing.Dict`, etc.

### Code Organization

#### Module Structure

```python
"""Module docstring describing purpose.

Detailed explanation of module functionality.
"""

from __future__ import annotations  # For forward references

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# Public API exports
__all__ = ["public_function", "PublicClass"]


def public_function() -> None:
    """Public function with complete docstring."""
    pass


def _private_function() -> None:
    """Private function (not in __all__)."""
    pass
```

#### Docstring Format

Use Google-style docstrings:

```python
def function(arg1: str, arg2: int = 0) -> bool:
    """One-line summary.

    Detailed explanation of what the function does.

    Args:
        arg1: Description of arg1.
        arg2: Description of arg2. Defaults to 0.

    Returns:
        Description of return value.

    Raises:
        ValueError: When input is invalid.

    Example:
        >>> function("test", 42)
        True
    """
```

## Testing Standards

### Coverage Requirements

- **Minimum Gate**: 50% (enforced in CI)
- **Target**: 65%
- **Frontier**: 80%
- **Current**: 84% ✅

### Test Organization

```python
import pytest
from chiron import ChironCore

class TestChironCore:
    """Tests for ChironCore class."""

    def test_initialization(self):
        """Test core initialization with default config."""
        core = ChironCore()
        assert core is not None

    def test_initialization_with_config(self):
        """Test core initialization with custom config."""
        config = {"service_name": "test"}
        core = ChironCore(config)
        assert core.config["service_name"] == "test"

    @pytest.mark.asyncio
    async def test_async_operation(self):
        """Test async operations."""
        result = await some_async_function()
        assert result is not None

    @pytest.mark.security
    def test_security_feature(self):
        """Test security-related functionality."""
        pass

    @pytest.mark.contract
    def test_pact_contract(self):
        """Test Pact contract validation."""
        pass
```

### Test Categories

Use pytest markers for organization:

- `@pytest.mark.security` - Security-related tests
- `@pytest.mark.contract` - Pact contract tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow-running tests
- `@pytest.mark.asyncio` - Async tests

### Property-Based Testing

Use Hypothesis for property-based tests:

```python
from hypothesis import given, strategies as st

@given(st.text())
def test_function_with_any_string(input_str: str):
    """Test function handles any string input."""
    result = process_string(input_str)
    assert isinstance(result, str)
```

## Quality Gates

All code must pass 9 comprehensive quality gates:

### 1. Policy Gate

- OPA/Conftest policy enforcement
- Custom policies in `policy/` directory

### 2. Coverage Gate

- Minimum 50% coverage required
- Target 65%, frontier 80%
- Currently at 84% ✅

### 3. Security Gate

- Zero critical vulnerabilities (Bandit, Safety, Semgrep)
- SBOM generation (CycloneDX, SPDX)
- Vulnerability scanning (Grype)

### 4. Type Safety Gate

- Strict MyPy checking
- All public APIs fully typed
- No `Any` types without justification

### 5. SBOM Gate

- Automatic SBOM generation
- Validation of component count
- Vulnerability scanning

### 6. Code Quality Gate

- Ruff linting (zero errors)
- Ruff formatting check
- Import organization

### 7. Test Quality Gate

- All tests must pass
- 765+ tests currently passing

### 8. Dependency Gate

- No dependency conflicts
- Locked dependencies with uv.lock
- Deptry analysis for unused dependencies

### 9. Documentation Gate

- Documentation builds successfully
- No broken links
- Vale style consistency

## Documentation Standards

### Structure (Diátaxis Framework)

Documentation follows the Diátaxis framework:

1. **Tutorials** (`docs/tutorials/`)
   - Learning-oriented
   - Step-by-step guides for beginners
   - Example: "First Run with Chiron"

2. **How-to Guides** (`docs/`)
   - Task-oriented
   - Problem-solving guides
   - Examples: Quality Gates, Environment Sync

3. **Reference** (`docs/`)
   - Information-oriented
   - Technical descriptions
   - Examples: API docs, module status

4. **Explanation** (`docs/`)
   - Understanding-oriented
   - Background and concepts
   - Examples: Gap Analysis, Architecture

### Documentation Style

- **Format**: Markdown
- **Linter**: Vale (with Microsoft, Write Good styles)
- **Links**: All internal links must be valid
- **Code Blocks**: Include language specifiers
- **Headers**: Use ATX-style (`#`, `##`, etc.)

### API Documentation

- Auto-generated from docstrings using mkdocstrings
- Google-style docstrings required
- Include examples in docstrings

## Git Workflow

### Branch Strategy

- **main**: Production-ready code
- **develop**: Development branch (if used)
- **feature/**: Feature branches
- **fix/**: Bug fix branches
- **copilot/**: GitHub Copilot agent branches

### Commit Messages

Use Conventional Commits format:

```
type(scope): short description

Longer description if needed.

Breaking Change: description of breaking change

Refs: #issue-number
```

Types:

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Maintenance tasks
- `ci`: CI/CD changes

### Pull Requests

1. Create feature branch from main
2. Make changes with tests
3. Run quality gates locally: `hephaestus tools qa --profile full`
4. Commit with conventional commit format
5. Push and create PR
6. Address review feedback
7. Squash and merge when approved

## CI/CD Standards

### Workflows

All workflows in `.github/workflows/`:

- **CI** (`ci.yml`): Multi-OS, multi-Python testing
- **Quality Gates** (`quality-gates.yml`): 9 comprehensive gates
- **Security Scanning**: CodeQL, Trivy, Semgrep
- **Wheels** (`wheels.yml`): Multi-platform wheel building
- **Release** (`release.yml`): PyPI publishing with OIDC
- **Documentation** (`docs-lint.yml`): Vale style checking

### Badge Requirements

All badges in README must reflect actual CI/CD status:

- CI status
- Quality gates status
- Code coverage (Codecov)
- PyPI version
- Python versions
- License

## Dependency Management

### Tool: uv

- **Lock File**: `uv.lock` (committed)
- **Installation**: `uv sync --all-extras --dev`
- **Updates**: `uv lock --upgrade`

### Dependency Groups

- **Core**: Required for library usage
- **dev**: Development tools (ruff, mypy, pre-commit)
- **test**: Testing frameworks (pytest, coverage)
- **security**: Security tools (bandit, safety)
- **service**: FastAPI dependencies
- **docs**: Documentation tools (mkdocs)

### Version Constraints

- Use `>=` for minimum versions
- Use `<` for known incompatibilities
- Lock specific versions in `uv.lock`

## Security Standards

### SBOM Generation

- Automatic generation on every build
- CycloneDX and SPDX formats
- Syft for SBOM creation

### Vulnerability Scanning

- Grype for SBOM scanning
- Safety for Python dependencies
- Bandit for code security issues
- Semgrep for security patterns

### Artifact Signing

- Sigstore Cosign for keyless signing
- SLSA provenance generation
- Signature verification in workflows

### Secret Management

- Never commit secrets
- Use GitHub Secrets for CI/CD
- Use environment variables for configuration

## Automation Standards

### Pre-commit Hooks

Required hooks (`.pre-commit-config.yaml`):

1. Vale (documentation style)
2. Ruff (code formatting and linting)
3. Deptry (dependency checks)
4. OPA/Conftest (policy checks)
5. MyPy (type checking on pre-push)
6. Pytest (tests on pre-push)

### Quality Toolbox

Use `hephaestus tools qa` for local quality checks:

```bash
# Full suite
hephaestus tools qa --profile full

# Fast checks
hephaestus tools qa --profile fast

# With monitoring
hephaestus tools qa --profile full --monitor --coverage-xml coverage.xml
```

### Environment Sync

- Automatic sync between devcontainer and CI
- Script: `scripts/sync_env_deps.py`
- Pre-commit hook ensures consistency

## Release Standards

### Versioning

- Semantic Versioning (SemVer): MAJOR.MINOR.PATCH
- Automated with semantic-release
- Changelog generated automatically

### Release Process

1. Merge feature to main
2. Automated version bump
3. Changelog generation
4. PyPI publishing (OIDC)
5. GitHub release creation
6. Artifact signing
7. SBOM generation

### Release Artifacts

- Source distribution (`.tar.gz`)
- Wheel distribution (`.whl`)
- SBOM (CycloneDX, SPDX)
- Signatures (Sigstore)
- SLSA provenance

## Maintenance Standards

### Technical Debt

- Track in GitHub Issues with `tech-debt` label
- Address during refactoring sprints
- Use refactoring tools: `hephaestus tools refactor hotspots`

### Deprecation Policy

1. Announce deprecation in docs and code
2. Provide deprecation warnings for 2 minor versions
3. Remove in next major version
4. Provide migration guide

### Monitoring

- Track quality metrics over time
- Monitor test coverage trends
- Review security scan results weekly
- Update dependencies monthly

## Enforcement

### Automated Enforcement

- CI/CD workflows enforce all standards
- Pre-commit hooks catch issues early
- Quality gates prevent regression

### Manual Review

- Code reviews for all PRs
- Architecture reviews for major changes
- Security reviews for sensitive code
- Documentation reviews for user-facing changes

### Exceptions

- Document exceptions in code comments
- Link to issue tracking exception
- Review exceptions quarterly

## References

- [Quality Gates](QUALITY_GATES.md) - Detailed gate descriptions
- [Contributing Guide](CONTRIBUTING.md) - Contribution workflow
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md) - Current status
- [CI/CD Workflows](CI_WORKFLOWS.md) - Workflow reference
- [Upgrade Plan](CHIRON_UPGRADE_PLAN.md) - Version upgrade guidelines

## Updates

This document is a living standard. Update as practices evolve:

1. Propose changes via PR
2. Discuss in PR review
3. Update documentation
4. Communicate changes to team

Last Updated: 2025-01-06
