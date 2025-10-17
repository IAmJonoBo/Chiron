# Automation Guide

This document describes all automation in place for Chiron and how to extend it.

## Overview

Chiron employs comprehensive automation to maintain quality, security, and consistency:

- **Pre-commit Hooks**: Catch issues before commit
- **CI/CD Workflows**: Automated testing and deployment
- **Quality Gates**: Comprehensive quality enforcement
- **Dependency Management**: Automated updates and security checks
- **Documentation**: Auto-generation and validation
- **Environment Sync**: Dev/CI alignment

## Pre-commit Hooks

### Installation

```bash
# Install pre-commit
uv run pre-commit install

# Install all hooks including pre-push
uv run pre-commit install --hook-type pre-push
```

### Available Hooks

#### On Every Commit

1. **Vale** - Documentation style checking
   - Files: `*.md`
   - Style guides: Microsoft, Write Good
   - Configuration: `.vale.ini`

2. **Ruff Check** - Linting
   - Files: `*.py`
   - Auto-fixes: Simple issues
   - Configuration: `pyproject.toml`

3. **Ruff Format** - Code formatting
   - Files: `*.py`
   - Auto-formats code
   - Configuration: `pyproject.toml`

4. **Deptry** - Dependency analysis
   - Finds unused dependencies
   - Checks for missing dependencies
   - Configuration: `pyproject.toml`

5. **OPA/Conftest** - Policy enforcement
   - Policy files: `policy/*.rego`
   - Validates project structure
   - Enforces standards

#### On Push (pre-push hooks)

6. **MyPy** - Type checking
   - Strict mode
   - All `src/` files
   - Configuration: `pyproject.toml`

7. **Pytest** - Fast test suite
   - Unit tests only
   - Skips slow tests
   - Configuration: `pyproject.toml`

### Skipping Hooks

```bash
# Skip all hooks
git commit --no-verify

# Skip specific hook
SKIP=vale git commit -m "message"

# Skip multiple hooks
SKIP=vale,mypy git commit -m "message"
```

### Hook Configuration

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/errata-ai/vale
    rev: v2.29.0
    hooks:
      - id: vale
        files: \.(md|rst)$

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: local
    hooks:
      - id: deptry
        name: deptry
        entry: uv run deptry
        language: system
        pass_filenames: false

      - id: mypy
        name: mypy
        entry: uv run mypy src
        language: system
        types: [python]
        stages: [push]

      - id: pytest-fast
        name: pytest (fast)
        entry: uv run pytest -m "not slow"
        language: system
        pass_filenames: false
        stages: [push]
```

## CI/CD Workflows

### Workflow Structure

All workflows in `.github/workflows/`:

```
.github/workflows/
├── ci.yml                      # Main CI pipeline
├── quality-gates.yml           # Quality enforcement
├── codeql.yml                  # Security analysis
├── trivy.yml                   # Container scanning
├── docs-lint.yml               # Documentation validation
├── diff-cover.yml              # Coverage on changes
├── reproducibility.yml         # Build verification
├── sync-env.yml                # Environment sync
├── wheels.yml                  # Wheel building
├── release.yml                 # PyPI publishing
├── airgap.yml                  # Offline bundles
└── copilot-setup-steps.yml     # Copilot support
```

### Workflow Triggers

#### On Push

- `ci.yml` - All branches
- `quality-gates.yml` - main, develop
- `codeql.yml` - main, develop
- `trivy.yml` - All branches

#### On Pull Request

- `ci.yml` - To main
- `quality-gates.yml` - To main
- `diff-cover.yml` - All PRs
- `docs-lint.yml` - Docs changes

#### On Schedule

- `codeql.yml` - Weekly (Monday)
- `trivy.yml` - Weekly (Sunday)
- `reproducibility.yml` - Weekly

#### On Release

- `release.yml` - Version tags
- `wheels.yml` - Version tags

### Adding New Workflows

1. Create workflow file in `.github/workflows/`
2. Define triggers and jobs
3. Test with workflow dispatch
4. Document in [CI_WORKFLOWS.md](CI_WORKFLOWS.md)
5. Add badge to README if appropriate

Example workflow:

```yaml
name: New Check

on:
  push:
    branches: [main]
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - name: Install uv
        uses: astral-sh/setup-uv@v6

      - name: Set up Python
        run: uv python install 3.12

      - name: Run check
        run: |
          # Your check here
```

## Quality Gates Automation

### Local Quality Checks

```bash
# Run all gates
hephaestus tools qa --profile full

# Run specific profile
hephaestus tools qa --profile fast    # tests + lint
hephaestus tools qa --profile verify  # tests + lint + types

# Dry run (show what would run)
hephaestus tools qa --profile full --dry-run

# With monitoring
hephaestus tools qa --profile full --monitor --coverage-xml coverage.xml
```

### Custom Quality Profiles

Add to `pyproject.toml`:

```toml
[tool.chiron.quality.profiles]
custom = ["tests", "lint", "types", "security"]
minimal = ["lint"]
```

### Gate Configuration

Override gates in `pyproject.toml`:

```toml
[tool.chiron.quality.gates.tests]
command = ["uv", "run", "pytest", "--maxfail=1"]
critical = true

[tool.chiron.quality.gates.lint]
command = ["uv", "run", "ruff", "check", "--select=E,F"]
critical = true
```

## Dependency Management Automation

### Automated Updates

Use Renovate for dependency updates (`.renovate.json`):

```json
{
  "extends": ["config:base"],
  "schedule": ["before 5am on Monday"],
  "packageRules": [
    {
      "matchPackagePatterns": ["*"],
      "groupName": "all dependencies",
      "groupSlug": "all"
    }
  ]
}
```

### Security Scanning

Automated with GitHub workflows:

1. **Dependabot** - GitHub's built-in scanner
2. **Safety** - Python package scanner
3. **Bandit** - Code security scanner
4. **Grype** - SBOM vulnerability scanner

### Dependency Sync

Automatic sync between dev and CI:

```bash
# Manual sync
python scripts/sync_env_deps.py

# Automated via pre-commit hook
# Runs on changes to pyproject.toml
```

## Documentation Automation

### Auto-generation

#### API Documentation

From docstrings using mkdocstrings:

```yaml
# mkdocs.yml
plugins:
  - mkdocstrings:
      handlers:
        python:
          options:
            docstring_style: google
            show_source: true
```

#### Quality Suite Documentation

Auto-sync quality gates:

```bash
# Update documentation with current gates
hephaestus tools qa --profile full --sync-docs docs/QUALITY_GATES.md
```

#### Diátaxis Structure

Auto-sync documentation structure:

```bash
# Update index with Diátaxis sections
hephaestus tools docs sync-diataxis --discover
```

### Link Validation

Automated in docs-lint workflow:

```yaml
- name: Check links
  run: |
    uv run mkdocs build --strict
```

### Style Consistency

Vale runs automatically on documentation:

```bash
# Manual check
vale docs/ *.md

# Pre-commit hook
# Runs on all .md files
```

## Environment Synchronization

### Dev Container ↔ CI Sync

Automatic sync of dependency installation:

1. Update `pyproject.toml`
2. Pre-commit hook runs `sync_env_deps.py`
3. Updates `.devcontainer/post-create.sh`
4. Updates `.github/workflows/*.yml`

### Manual Sync

```bash
# Sync all environments
python scripts/sync_env_deps.py

# Check sync status
python scripts/sync_env_deps.py --check
```

### Sync Configuration

`.github/sync-env.yml`:

```yaml
name: Environment Sync

on:
  push:
    paths:
      - pyproject.toml

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - name: Sync environments
        run: python scripts/sync_env_deps.py

      - name: Create PR if needed
        uses: peter-evans/create-pull-request@v5
        with:
          title: "chore: Sync environment dependencies"
          branch: sync/env-deps
```

## Build Automation

### Wheel Building

Multi-platform wheels with cibuildwheel:

```yaml
# .github/workflows/wheels.yml
- name: Build wheels
  uses: pypa/cibuildwheel@v3.2.0
  env:
    CIBW_BUILD: cp312-*
    CIBW_ARCHS_LINUX: x86_64 aarch64
    CIBW_ARCHS_MACOS: x86_64 arm64
    CIBW_ARCHS_WINDOWS: x86_64
```

### SBOM Generation

Automatic on every build:

```bash
# Manual generation
syft . -o cyclonedx-json=sbom.json
syft . -o spdx-json=sbom-spdx.json
```

### Signing

Automatic with Sigstore:

```bash
# Manual signing
cosign sign-blob --bundle chiron.tar.gz.bundle chiron.tar.gz
```

## Release Automation

### Semantic Release

Automatic version bumping and changelog:

```yaml
# .github/workflows/release.yml
- name: Semantic Release
  uses: cycjimmy/semantic-release-action@v4
  with:
    semantic_version: 19
```

### PyPI Publishing

Automated with OIDC (no token needed):

```yaml
- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@release/v1
  with:
    packages-dir: dist/
```

### GitHub Releases

Automatic creation with artifacts:

```yaml
- name: Create Release
  uses: softprops/action-gh-release@v1
  with:
    files: |
      dist/*
      sbom.json
      sbom-spdx.json
```

## Testing Automation

### Test Selection

```bash
# Run all tests
uv run pytest

# Run by marker
uv run pytest -m security
uv run pytest -m "not slow"

# Run specific category
uv run pytest tests/test_core.py
```

### Coverage Automation

```bash
# Generate coverage
uv run pytest --cov=src/chiron --cov-report=html --cov-report=xml

# Upload to Codecov (CI)
codecov -f coverage.xml
```

### Mutation Testing

```bash
# Run mutation tests
uv run mutmut run

# Check results
uv run mutmut results

# Generate HTML report
uv run mutmut html
```

## Monitoring Automation

### Coverage Monitoring

Track coverage trends:

```bash
# Monitor current coverage
hephaestus tools coverage guard --threshold 80

# Find hotspots
hephaestus tools coverage hotspots --threshold 85 --limit 5

# Identify gaps
hephaestus tools coverage gaps --min-statements 40
```

### Quality Metrics

Track quality over time:

```bash
# Run with monitoring
hephaestus tools qa --profile full --monitor --coverage-xml coverage.xml

# Generate report
hephaestus tools qa --profile full --save-report reports/qa.json
```

## Extending Automation

### Adding Pre-commit Hook

1. Add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: my-check
      name: My Custom Check
      entry: scripts/my_check.sh
      language: script
      pass_filenames: false
```

2. Create script:

```bash
#!/bin/bash
# scripts/my_check.sh
echo "Running custom check..."
# Your check here
```

3. Make executable:

```bash
chmod +x scripts/my_check.sh
```

4. Test:

```bash
uv run pre-commit run my-check --all-files
```

### Adding CI Workflow

See "Adding New Workflows" section above.

### Adding Quality Gate

1. Add to `pyproject.toml`:

```toml
[tool.chiron.quality.gates.my-gate]
command = ["my-command", "arg1", "arg2"]
description = "My custom gate"
category = "custom"
critical = true
```

2. Add to profile:

```toml
[tool.chiron.quality.profiles]
full = ["tests", "lint", "types", "my-gate"]
```

3. Run:

```bash
hephaestus tools qa --profile full
```

## Troubleshooting

### Pre-commit Hook Fails

```bash
# Run manually to see error
uv run pre-commit run --all-files

# Update hooks
uv run pre-commit autoupdate

# Clear cache
uv run pre-commit clean
```

### CI Workflow Fails

```bash
# View logs
gh run list
gh run view <run-id>

# Re-run failed jobs
gh run rerun <run-id>

# Trigger workflow manually
gh workflow run ci.yml
```

### Quality Gate Fails

```bash
# Run gate individually
hephaestus tools qa --profile <profile> --explain

# Show what would run
hephaestus tools qa --profile <profile> --dry-run

# Check gate configuration
uv run python -c "from hephaestus.toolbox import DEFAULT_QUALITY_GATES; print(DEFAULT_QUALITY_GATES)"
```

## Best Practices

1. **Run Locally First**: Test automation locally before pushing
2. **Start Small**: Add automation incrementally
3. **Document Changes**: Update this guide when adding automation
4. **Monitor Performance**: Track automation execution time
5. **Review Regularly**: Review automation effectiveness quarterly

## Related Documentation

- [CI/CD Workflows](CI_WORKFLOWS.md) - Workflow reference
- [Quality Gates](QUALITY_GATES.md) - Quality standards
- [Project Standards](PROJECT_STANDARDS.md) - Overall standards
- [Contributing Guide](CONTRIBUTING.md) - Development workflow

## Automation Inventory

| Category       | Tool            | Trigger      | Status    |
| -------------- | --------------- | ------------ | --------- |
| **Pre-commit** | Vale            | Every commit | ✅ Active |
| **Pre-commit** | Ruff            | Every commit | ✅ Active |
| **Pre-commit** | Deptry          | Every commit | ✅ Active |
| **Pre-commit** | OPA             | Every commit | ✅ Active |
| **Pre-commit** | MyPy            | Pre-push     | ✅ Active |
| **Pre-commit** | Pytest          | Pre-push     | ✅ Active |
| **CI**         | Multi-OS Tests  | Push/PR      | ✅ Active |
| **CI**         | Quality Gates   | Push/PR      | ✅ Active |
| **CI**         | Security Scan   | Push/PR      | ✅ Active |
| **CI**         | CodeQL          | Weekly       | ✅ Active |
| **CI**         | Trivy           | Weekly       | ✅ Active |
| **CI**         | Docs Build      | Push/PR      | ✅ Active |
| **CI**         | Reproducibility | Weekly       | ✅ Active |
| **CI**         | Env Sync        | Push         | ✅ Active |
| **Release**    | Wheels          | Tag          | ✅ Active |
| **Release**    | PyPI Publish    | Tag          | ✅ Active |
| **Release**    | SBOM            | Build        | ✅ Active |
| **Release**    | Signing         | Build        | ✅ Active |

Last Updated: 2025-01-06
