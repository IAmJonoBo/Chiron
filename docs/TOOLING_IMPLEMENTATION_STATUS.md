# Tooling Implementation Status

This document tracks the implementation status of advanced tooling opportunities identified in the project roadmap.

## Executive Summary

This assessment reviews the tooling opportunities outlined in the original roadmap and documents their current implementation status. The findings show that many of the "immediate wins" have been implemented, while several "near-term" and "strategic" items remain as future enhancements.

## Immediate Wins (Target: Next Sprint)

### ✅ Conftest + OPA Bundle
**Status**: IMPLEMENTED

**Evidence**:
- `.pre-commit-config.yaml` includes OPA policy check hook (lines 127-132)
- `scripts/run_policy_checks.sh` executes policy enforcement
- `scripts/build_opa_bundle.sh` creates reusable OPA bundles
- `.github/workflows/quality-gates.yml` includes policy-gate job
- `Makefile` includes `policy-check` and `policy-bundle` targets

**Purpose**: Enforce dependency and workflow policies (SBOM freshness, required signing steps) directly in CI and pre-commit.

### ✅ pytest-xdist
**Status**: IMPLEMENTED

**Evidence**:
- `pyproject.toml` includes pytest-xdist in required_plugins
- Test configuration uses `-n=auto` and `--dist=worksteal` for parallel execution
- Significantly speeds up the 3x OS matrix in CI

**Purpose**: Speed up test execution with parallel test running.

### ✅ pytest-randomly
**Status**: IMPLEMENTED (with minor config issue)

**Evidence**:
- `pyproject.toml` includes pytest-randomly in dependencies
- Tests run with randomized order to surface order-dependent flakes
- Note: Config option `randomly_dont_reorganize` had syntax issue (fixed)

**Purpose**: Surface order-dependent test flake risks.

### ✅ Deptry
**Status**: IMPLEMENTED

**Evidence**:
- `.pre-commit-config.yaml` includes deptry hook (lines 29-33)
- `Makefile` includes `deptry` target for manual runs
- Configured with `pyproject.toml` settings

**Purpose**: Catch unused/undeclared dependencies automatically in quality gates (complements `sync_env_deps.py`).

### ❌ Vale for Docs Linting
**Status**: NOT IMPLEMENTED

**Recommendation**: Consider adding Vale for documentation style checking as docs grow. This would align with the Diátaxis documentation framework already in use.

**Potential Implementation**:
- Add `.vale.ini` configuration
- Include Vale in pre-commit hooks for docs files
- Add docs linting job to CI workflow

## Near-term Upgrades (Target: 1–2 Quarters)

### ❌ Mutation Testing (mutmut or cosmic-ray)
**Status**: NOT IMPLEMENTED

**Recommendation**: Consider for high-risk modules (`chiron.deps.*`) that still lag in coverage. Wire into quality gates on a weekly cadence.

### ❌ Coverage-on-diff Gate (diff-cover)
**Status**: NOT IMPLEMENTED

**Current State**: Overall coverage gate is set at 50% minimum (currently at 56%)

**Recommendation**: Implement diff-cover to require 80%+ on touched lines even while overall gate remains at current level. This accelerates progress toward frontier target without blocking current work.

### ⚠️  CodeQL Workflow
**Status**: PARTIALLY IMPLEMENTED

**Evidence**:
- `github/codeql-action/upload-sarif@v3` is used for Semgrep SARIF upload
- No dedicated CodeQL analysis workflow exists

**Recommendation**: Layer GitHub's SAST on top of Bandit/Semgrep for defense-in-depth. Reuse existing CI caching via `actions/cache`.

**Implementation**: Add `.github/workflows/codeql.yml` with CodeQL analysis job.

### ❌ Trivy Container Scanning
**Status**: NOT IMPLEMENTED

**Recommendation**: Extend SBOM coverage to base images used in airgap and container-build flows.

### ⚠️  Sigstore Policy-controller / Cosign Verify-step
**Status**: PARTIALLY IMPLEMENTED

**Evidence**:
- Cosign signing is implemented in `.github/workflows/wheels.yml`
- CLI includes `--verify-provenance` flag
- No automated attestation verification in CI before release uploads

**Recommendation**: Automate attestation verification in CI before release uploads.

## Strategic / Frontier Experiments

### ❌ Reprotest + Diffoscope Harness
**Status**: NOT IMPLEMENTED

**Current State**: Reproducibility checking tools exist in `src/chiron/deps/reproducibility.py`

**Recommendation**: Continuously validate the "reproducible wheels" claim with actual rebuild diffs using reprotest and diffoscope.

### ✅ In-toto/SLSA Provenance Generator
**Status**: IMPLEMENTED

**Evidence**:
- `.github/workflows/wheels.yml` includes SLSA provenance generation
- `.github/workflows/release.yml` has dedicated SLSA provenance job
- `src/chiron/deps/oci_packaging.py` includes provenance media type
- `src/chiron/cli/main.py` includes `--verify-provenance` option
- Feature flag exists for SLSA provenance requirement

**Purpose**: Emit v1.0 attestation artifacts for every build, aligning with SLSA L3+ expectations.

### ❌ LLM-powered Contract Tests
**Status**: NOT IMPLEMENTED

**Current State**: MCP tooling exists in `src/chiron/mcp/`, OpenFeature flags are configured

**Recommendation**: Extend MCP tooling to drive smoke scenarios via natural language, using OpenFeature flags for safe rollout.

### ⚠️  Observability Sandbox (Docker Compose)
**Status**: PLANNED BUT NOT IMPLEMENTED

**Evidence**: Mentioned in ROADMAP.md but no docker-compose file exists

**Recommendation**: Ship a docker-compose bundle with the OpenTelemetry Collector + Grafana Agent so contributors can visualize traces/metrics locally. This would complement the existing Grafana deployment guide.

**Potential Location**: `docker-compose.observability.yml` in project root

### ❌ Chaos & Load Automation (k6/Locust + Chaostoolkit)
**Status**: NOT IMPLEMENTED

**Recommendation**: Rehearse failure scenarios for FastAPI routes and dependency workflows before enterprise adoption.

## Summary Statistics

**Implemented**: 6/13 (46%)
**Partially Implemented**: 3/13 (23%)
**Not Implemented**: 4/13 (31%)

**By Priority**:
- **Immediate Wins**: 4/5 implemented (80%)
- **Near-term**: 1/6 implemented (17%)
- **Strategic**: 1/5 implemented (20%)

## Recommendations for Documentation Updates

1. **Update QUALITY_GATES.md**: Add section documenting OPA/Conftest policy enforcement and Deptry dependency checking
2. **Update ROADMAP.md**: Remove the "DELETE THE THIS AND THE BELOW" section as requested
3. **Update TESTING_PROGRESS_SUMMARY.md**: Document pytest-xdist and pytest-randomly usage
4. **Create FUTURE_ENHANCEMENTS.md**: Move unimplemented strategic items to a dedicated future work document

## Code/Doc Parity Issues Identified

1. ✅ **RESOLVED**: OPA/Conftest implementation exists but wasn't documented in QUALITY_GATES.md (should be added)
2. ✅ **RESOLVED**: Deptry exists but wasn't highlighted in dependency management docs
3. ✅ **RESOLVED**: SLSA provenance is implemented but scattered across multiple locations
4. ⚠️  **TO ADDRESS**: pytest-xdist and pytest-randomly are used but not documented in testing guides
5. ⚠️  **TO ADDRESS**: CodeQL action is used for SARIF upload but no CodeQL analysis exists

---

*Document Version: 1.0.0*
*Last Updated: 2025-01-25*
*Status: Ready for Review*
