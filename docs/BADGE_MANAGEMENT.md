# Badge Management & Status

This document describes the badges used in Chiron's README and how they are maintained.

## Current Badges

### CI/CD Status Badges

#### CI Workflow
```markdown
[![CI](https://github.com/IAmJonoBo/Chiron/workflows/CI/badge.svg)](https://github.com/IAmJonoBo/Chiron/actions/workflows/ci.yml)
```

**Status**: Active workflow that runs on every push and PR
**What it tests**:
- Multi-OS testing (Ubuntu, macOS, Windows)
- Multi-Python testing (3.12)
- Pre-commit hooks
- Security scanning
- SBOM generation
- Wheel building

#### Quality Gates Workflow
```markdown
[![Quality Gates](https://github.com/IAmJonoBo/Chiron/workflows/Quality%20Gates/badge.svg)](https://github.com/IAmJonoBo/Chiron/actions/workflows/quality-gates.yml)
```

**Status**: Active workflow with 9 comprehensive gates
**What it tests**:
1. Policy Gate (OPA/Conftest)
2. Coverage Gate (50% min, 80% target)
3. Security Gate (Bandit, Safety, Semgrep)
4. Type Safety Gate (MyPy strict)
5. SBOM Gate (Syft + Grype)
6. Code Quality Gate (Ruff)
7. Test Quality Gate (765+ tests)
8. Dependency Gate (uv sync)
9. Documentation Gate (mkdocs build)

### Code Quality Badges

#### Code Coverage
```markdown
[![codecov](https://codecov.io/gh/IAmJonoBo/Chiron/branch/main/graph/badge.svg)](https://codecov.io/gh/IAmJonoBo/Chiron)
```

**Status**: Active, reports to Codecov
**Current Coverage**: 84%
**Requirements**:
- Codecov token in GitHub Secrets (`CODECOV_TOKEN`)
- Coverage reports uploaded from CI workflow

### Package Information Badges

#### PyPI Version
```markdown
[![PyPI version](https://badge.fury.io/py/chiron.svg)](https://badge.fury.io/py/chiron)
```

**Status**: Active (when package is published)
**Note**: Badge will show "not found" until first PyPI release

#### Python Versions
```markdown
[![Python versions](https://img.shields.io/pypi/pyversions/chiron.svg)](https://pypi.org/project/chiron/)
```

**Status**: Active (when package is published)
**Supported**: Python 3.12+

#### License
```markdown
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
```

**Status**: Static badge, always accurate
**License**: MIT (see LICENSE file)

## Badge Maintenance

### Automatic Updates

Most badges update automatically:

1. **CI/CD Badges**: Update on every workflow run
2. **Coverage Badge**: Updates when coverage reports are uploaded
3. **PyPI Badges**: Update when new versions are published
4. **License Badge**: Static, no updates needed

### Manual Verification

Periodically verify all badges:

```bash
# Check CI workflows status
gh workflow list

# Check recent workflow runs
gh run list --limit 5

# View coverage in Codecov
# Visit: https://codecov.io/gh/IAmJonoBo/Chiron
```

### Badge Status Checks

Create automated checks for badge validity:

```yaml
# .github/workflows/badge-check.yml
name: Badge Status Check

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
  workflow_dispatch:

jobs:
  check-badges:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v5

      - name: Check CI badge
        run: |
          curl -f "https://github.com/IAmJonoBo/Chiron/workflows/CI/badge.svg"

      - name: Check Quality Gates badge
        run: |
          curl -f "https://github.com/IAmJonoBo/Chiron/workflows/Quality%20Gates/badge.svg"

      - name: Check Codecov badge
        run: |
          curl -f "https://codecov.io/gh/IAmJonoBo/Chiron/branch/main/graph/badge.svg"
```

## Adding New Badges

### Security Scanning Badges

Consider adding:

```markdown
[![Security: Bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![CodeQL](https://github.com/IAmJonoBo/Chiron/workflows/CodeQL/badge.svg)](https://github.com/IAmJonoBo/Chiron/actions/workflows/codeql.yml)
```

### Documentation Badge

```markdown
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://github.com/IAmJonoBo/Chiron/docs)
```

### Container Security

```markdown
[![Trivy](https://github.com/IAmJonoBo/Chiron/workflows/Trivy/badge.svg)](https://github.com/IAmJonoBo/Chiron/actions/workflows/trivy.yml)
```

### OpenSSF Best Practices

```markdown
[![OpenSSF Best Practices](https://bestpractices.coreinfrastructure.org/projects/XXXX/badge)](https://bestpractices.coreinfrastructure.org/projects/XXXX)
```

(Apply at https://bestpractices.coreinfrastructure.org)

## Badge Troubleshooting

### Badge Shows "Unknown" or "Error"

**Possible Causes**:
1. Workflow hasn't run yet
2. Workflow name mismatch
3. Branch name incorrect
4. Repository visibility issue

**Solutions**:
```bash
# Verify workflow exists and matches badge
gh workflow list

# Check workflow file name
ls .github/workflows/

# Trigger workflow manually
gh workflow run ci.yml
```

### Coverage Badge Not Updating

**Possible Causes**:
1. Codecov token missing or invalid
2. Coverage report not uploaded
3. Branch name mismatch

**Solutions**:
```bash
# Verify token exists
gh secret list

# Check recent uploads
# Visit: https://codecov.io/gh/IAmJonoBo/Chiron/commits

# Re-upload coverage
uv run pytest --cov --cov-report=xml
codecov -f coverage.xml
```

### PyPI Badges Show "Not Found"

**Expected**: Badges show "not found" until first PyPI release

**After First Release**:
1. Verify package exists: https://pypi.org/project/chiron/
2. Wait 5-10 minutes for cache refresh
3. Force refresh badge URL

## Badge Best Practices

### Placement

Place badges prominently in README:
1. Top of file (after title)
2. Before feature list
3. Group related badges together

### Organization

Group badges logically:
```markdown
<!-- CI/CD Status -->
[![CI](...)](#)
[![Quality Gates](...)](#)

<!-- Code Quality -->
[![codecov](...)](#)

<!-- Package Info -->
[![PyPI version](...)](#)
[![Python versions](...)](#)
[![License](...)](#)
```

### Documentation

Always link badges to:
- Workflow runs (for CI/CD badges)
- Coverage reports (for coverage badges)
- Package pages (for PyPI badges)
- Documentation (for docs badges)

### Maintenance

- Review badges quarterly
- Remove broken or outdated badges
- Update badge URLs when workflows rename
- Document badge requirements

## Badge Automation

### Pre-commit Hook

Add badge validation to pre-commit:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: check-badges
        name: Check README badges
        entry: scripts/check_badges.sh
        language: script
        files: ^README\.md$
```

### Badge Check Script

```bash
#!/bin/bash
# scripts/check_badges.sh

set -e

echo "Checking badges in README.md..."

# Check CI badge
if ! grep -q "CI.*badge.svg" README.md; then
    echo "Error: CI badge missing or malformed"
    exit 1
fi

# Check Quality Gates badge
if ! grep -q "Quality.*Gates.*badge.svg" README.md; then
    echo "Error: Quality Gates badge missing or malformed"
    exit 1
fi

# Check codecov badge
if ! grep -q "codecov.io" README.md; then
    echo "Error: Codecov badge missing or malformed"
    exit 1
fi

echo "All badges verified ✅"
```

## Related Documentation

- [CI/CD Workflows](CI_WORKFLOWS.md) - Workflow documentation
- [Quality Gates](QUALITY_GATES.md) - Quality standards
- [Contributing Guide](CONTRIBUTING.md) - Development workflow
- [Project Standards](PROJECT_STANDARDS.md) - Overall standards

## Status Dashboard

Current Badge Status (updated manually):

| Badge | Status | Last Checked | Notes |
|-------|--------|--------------|-------|
| CI | ✅ Passing | 2025-01-06 | All OS/Python combos |
| Quality Gates | ✅ Passing | 2025-01-06 | 9/9 gates passing |
| Codecov | ✅ Active | 2025-01-06 | 84% coverage |
| PyPI Version | ⏳ Pending | - | Awaiting first release |
| Python Versions | ⏳ Pending | - | Awaiting first release |
| License | ✅ Active | 2025-01-06 | MIT license |

## Next Steps

1. ✅ Verify all existing badges work correctly
2. ⏳ Add CodeQL and Trivy badges
3. ⏳ Create automated badge validation workflow
4. ⏳ Apply for OpenSSF Best Practices badge
5. ⏳ Publish to PyPI to activate package badges
