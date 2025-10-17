# Refactoring Toolkit - Discovery Plan

**Date:** 2025-10-06  
**Status:** ✅ Discovery Complete

## Repository Analysis

### Package Structure

- **Package root:** `src/hephaestus/`
- **Test layout:** `tests/`
- **Build system:** `pyproject.toml` with `uv.lock`
- **CLI framework:** Typer (entry point: `src/hephaestus/cli.py`)

### Quality Infrastructure

#### Pre-commit Configuration

- **File:** `.pre-commit-config.yaml`
- **Hooks present:**
  - Ruff (formatting and linting)
  - MyPy (type checking)
  - Bandit (security scanning)
  - Vale (documentation linting)
  - Deptry (dependency checking)
  - OPA/Conftest (policy validation)

#### CI/CD Workflows

- **Location:** `.github/workflows/`
- **Key workflows:**
  - `ci.yml` - Main CI pipeline with quality gates
  - `codeql.yml` - Security scanning
  - `trivy.yml` - Container vulnerability scanning
  - Coverage reporting enabled
  - SBOM generation integrated

#### Test Coverage

- **Current coverage:** ~84%
- **Coverage threshold:** 80% (enforced)
- **Test runner:** pytest with pytest-cov
- **Coverage formats:** HTML and XML reports

#### Quality Tools Present

- **Linting:** Ruff
- **Type checking:** MyPy
- **Security:** Bandit, pip-audit, grype (optional)
- **Testing:** pytest with various markers
- **Complexity:** Available via radon/xenon (to be integrated)
- **Mutation testing:** mutmut (documented in Makefile)

### CLI Integration Points

#### Existing CLI Structure

```
hephaestus
├── tools
│   ├── qa
│   ├── coverage
│   ├── refactor
│   └── docs
```

The `refactor_app` Typer group already exists and is registered under `tools`. New commands will be added to this group.

### Existing Refactoring Implementation

#### Implemented Features

1. **Hotspot Analysis** (`analyze_hotspots` in `dev_toolbox.py`)
   - Git churn mining
   - AST-based complexity scoring
   - Hotspot ranking (complexity × churn)
   - CLI command: `hephaestus tools refactor hotspots`

2. **Refactor Analysis** (`analyze_refactor_opportunities` in `dev_toolbox.py`)
   - Long function detection
   - Large class detection
   - High complexity detection
   - Coverage correlation
   - CLI command: `hephaestus tools refactor analyze`

3. **Documentation**
   - User guide: `docs/REFACTORING_GUIDE.md`
   - Implementation summary: `REFACTORING_IMPLEMENTATION.md`
   - Quick reference: Included in `QUICK_REFERENCE.md`

#### Test Coverage

- Unit tests: `tests/test_toolbox.py`
- Integration tests: `tests/test_cli.py`
- 15 new tests added, all passing

### Refactor Starter Archive

**File:** `refactor-starter-ts-py.zip`
**Contents:**

- Python codemod examples (LibCST)
- Git churn analysis script
- Hotspot analysis script (using radon)
- CI workflow templates
- TypeScript tooling (not applicable)

**Usage Strategy:**

- Extract relevant Python scripts
- Adapt to Hephaestus's architecture
- Integrate with existing CLI commands
- Maintain compatibility with uv

## Implementation Alignment

### What's Already Done ✅

1. Core hotspot analysis (complexity × churn)
2. Refactor opportunity detection
3. CLI commands under `hephaestus tools refactor`
4. Comprehensive testing (15 tests, 84% coverage)
5. User documentation

### What Needs to Be Added 📋

1. **hephaestus-toolkit/refactoring/** directory structure
2. Standalone scripts for pipeline/CI usage
3. Configuration file (`refactor.config.yaml`)
4. Additional CLI commands: `codemod`, `verify`, `shard`
5. CI workflow partial (warn-only gates)
6. Makefile targets
7. PLAYBOOK.md with five-step workflow

## Design Decisions

### 1. Script Organization

- Keep standalone scripts separate from core library
- Scripts wrap/use existing `dev_toolbox.py` functions
- Enable both CLI and direct script usage

### 2. Configuration Strategy

- YAML configuration for defaults and thresholds
- CLI arguments override config values
- Config file is optional (sensible defaults)

### 3. CI Integration

- Warn-only gates initially (non-blocking)
- Upload analysis artifacts
- Enable gradual adoption

### 4. Codemod Strategy

- Provide LibCST examples
- Focus on safe, lossless transformations
- Manual application (no auto-apply)

### 5. Characterization Tests

- Scaffold generation for selected functions
- Leverage existing pytest infrastructure
- Golden file approach (approval testing)

## Next Steps

1. Create `hephaestus-toolkit/refactoring/` structure ✅
2. Add configuration file
3. Port scripts from refactor-starter archive
4. Implement additional CLI commands
5. Add CI workflow partial
6. Create PLAYBOOK.md
7. Add Makefile targets
8. Test end-to-end workflows

## Risk Assessment

### Low Risk ✅

- Adding new directory structure
- Adding standalone scripts
- Extending existing CLI
- Adding documentation

### Medium Risk ⚠️

- Modifying Makefile (append-only)
- CI workflow partial (merge required by maintainers)

### Mitigations

- All changes are additive (no modifications to existing behavior)
- Scripts use existing infrastructure
- Configuration is optional
- Gates remain advisory (warn-only)
- Comprehensive testing before merge

## Success Criteria

- [ ] All scripts executable via CLI and directly
- [ ] Configuration file supports all documented options
- [ ] PLAYBOOK.md provides clear workflow guidance
- [ ] Makefile targets simplify common operations
- [ ] CI partial ready for manual integration
- [ ] Zero regression in existing tests
- [ ] Documentation complete and accurate
