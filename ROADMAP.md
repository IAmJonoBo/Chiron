# Chiron Roadmap

This roadmap tracks the implementation progress of features specified in [CHIRON_UPGRADE_PLAN.md](./CHIRON_UPGRADE_PLAN.md).

> ⚠️ **Reality Check**: Status icons below are legacy placeholders from the aspirational spec and no longer reflect the current implementation. Refer to `IMPLEMENTATION_SUMMARY.md` and `docs/GAP_ANALYSIS.md` for the up-to-date picture; prioritise updating each section before treating a ✅ as shipped.

## Status Legend

- ✅ Complete - Feature fully implemented and tested
- 🚧 In Progress - Currently being worked on
- 📋 Planned - Scheduled for implementation
- 🔍 Review - Implementation complete, under review

## Implementation Status

### Core Infrastructure (Section 1-4)

#### 1. Goals & Non-negotiables ✅

- ✅ Deterministic, hermetic builds
- ✅ Offline/air-gapped install support
- ✅ Observability defaults (OpenTelemetry)
- ✅ Policy-driven dependency management

#### 2. Tech Stack ✅

- ✅ Python 3.9+ (requires-python = ">=3.9")
- ✅ Hatchling build backend
- ✅ uv for dependency management
- ✅ OpenTelemetry SDK + FastAPI instrumentation
- ✅ pre-commit with Ruff and MyPy

#### 3. Repository Layout ✅

- ✅ `src/chiron/` - Library code
- ✅ `src/chiron/service/` - FastAPI service layer
- ✅ `src/chiron/cli/` - Command-line interface
- ✅ `tests/` - Test suite
- ✅ `docs/` - Documentation
- ✅ `.github/workflows/` - CI/CD pipelines
- ✅ `.devcontainer/` - Dev container configuration

#### 4. pyproject.toml Configuration ✅

- ✅ Basic configuration with Hatchling
- ✅ Optional dependencies for dev, security, service, docs
- ✅ Update requires-python to >=3.12 (frontier spec)
- ✅ Add cibuildwheel configuration to pyproject.toml
- ✅ Add typer to CLI optional dependencies
- ✅ Configure wheel repair commands (auditwheel/delocate/delvewheel)

### Dependency Management (Section 5)

#### 5. Dependency Policy ✅

- ✅ `constraints.py` - Hash-pinned constraints
- ✅ `supply_chain.py` - SBOM + OSV scanning
- ✅ `signing.py` - Artifact signing
- ✅ `policy.py` - Policy engine
- ✅ `bundler.py` - Wheelhouse bundler

#### 5.1 New Advanced Features ✅

- ✅ `private_mirror.py` - Private PyPI mirror automation
- ✅ `oci_packaging.py` - OCI artifact support
- ✅ `reproducibility.py` - Binary reproducibility
- ✅ `security_overlay.py` - CVE backport management

#### 5.2 Existing Modules ✅

- ✅ `drift.py` - Drift detection
- ✅ `sync.py` - Dependency sync
- ✅ `planner.py` - Upgrade planning
- ✅ `guard.py` - Change monitoring
- ✅ `upgrade_advisor.py` - Upgrade recommendations
- ✅ `safe_upgrade.py` - Safe upgrade execution
- ✅ `preflight.py` - Pre-deployment checks
- ✅ `status.py` - Dependency status
- ✅ `graph.py` - Dependency graph visualization
- ✅ `mirror_manager.py` - Mirror management
- ✅ `conflict_resolver.py` - Conflict resolution
- ✅ `verify.py` - Pipeline verification

### CI/CD Pipelines (Section 6)

#### 6.1 CI Workflow (ci.yml) ✅

- ✅ Multi-Python testing (3.9, 3.10, 3.11, 3.12)
- ✅ Multi-OS testing (Ubuntu, macOS, Windows)
- ✅ Security scanning (bandit, safety, semgrep)
- ✅ SBOM generation with Syft
- ✅ Vulnerability scanning with Grype
- ✅ Coverage reporting
- ✅ Build distribution artifacts

#### 6.2 Wheels Workflow (wheels.yml) ✅

- ✅ Basic cibuildwheel setup
- ✅ Multi-OS wheel building
- ✅ Multi-architecture support
- ✅ Update to use manylinux_2_28 (frontier spec)
- ✅ Add SBOM generation in wheels workflow (CycloneDX + Syft)
- ✅ Add OSV vulnerability scanning
- ✅ Add artifact signing with cosign (Sigstore keyless)
- ✅ Create wheelhouse bundle with checksums
- ✅ Add SLSA provenance metadata generation

#### 6.3 Release Workflow (release.yml) ✅

- ✅ PyPI trusted publishing (OIDC)
- ✅ Semantic release support
- ✅ Changelog generation

#### 6.4 Airgap Workflow (airgap.yml) ✅

- ✅ Offline bundle creation
- ✅ Multi-architecture support
- ✅ Attestation generation
- ✅ Bundle signing

### Service Mode (Section 7)

#### 7. FastAPI Service ✅

- ✅ Service implementation (`src/chiron/service/`)
- ✅ Health check endpoints
- ✅ OpenAPI documentation
- ✅ OpenTelemetry instrumentation

### Observability (Section 8)

#### 8. Observability Defaults ✅

- ✅ OpenTelemetry SDK integration
- ✅ FastAPI instrumentation
- ✅ Structured logging with structlog
- ✅ OTLP exporter support
- ✅ Trace/metric/log correlation

### Quality Gates & DX (Section 9)

#### 9. Development Experience ✅

- ✅ pre-commit hooks configured
- ✅ Ruff for linting and formatting
- ✅ MyPy for type checking (strict mode)
- ✅ pytest with coverage
- ✅ Hypothesis for property testing
- ✅ pytest-benchmark for performance
- ✅ Pact for contract testing

### Security & Supply Chain (Section 10)

#### 10. Security Hardening ✅

- ✅ SBOM generation (Syft, CycloneDX)
- ✅ Vulnerability scanning (Grype, OSV, Safety)
- ✅ Security scanning (Bandit, Semgrep)
- ✅ Supply chain modules implemented
- ✅ Add cosign signing to wheels workflow
- ✅ Add SLSA provenance metadata generation
- 🚧 Implement --require-hashes in CI

### CLI Features (Section 12)

#### 12. CLI Commands ✅

- ✅ `chiron init` - Initialize project
- ✅ `chiron build` - Build with cibuildwheel
- ✅ `chiron wheelhouse` - Create wheelhouse bundle
- ✅ `chiron airgap` - Create offline bundle
- ✅ `chiron release` - Semantic release
- ✅ `chiron verify` - Verify artifacts (stub)
- ✅ `chiron doctor` - Health checks
- ✅ `chiron serve` - Start service
- ✅ `chiron manage download` - Download packages
- ✅ `chiron manage list-packages` - List wheelhouse

#### 12.1 CLI Enhancements ✅

- ✅ Complete verify command implementation
- ✅ Add JSON schema validation for configs
- ✅ Add interactive wizard mode (via dry-run)
- ✅ Improve error messages and help text

### Advanced Features (Section 14)

#### 14.1 Schema-driven Configuration ✅

- ✅ JSON Schema for all commands
- ✅ Interactive wizard mode
- ✅ Config validation

#### 14.2 Backstage Plugin 📋

- 📋 Backstage integration
- 📋 Coverage dashboards
- 📋 Policy gate visualization

#### 14.3 Feature Flags (OpenFeature) ✅

- ✅ OpenFeature integration
- ✅ Safe toggles for sensitive operations
- ✅ Vendor-agnostic flag management

#### 14.4 OCI Distribution ✅

- ✅ OCI packaging implementation (`oci_packaging.py`)
- ✅ ORAS push/pull support (documented in workflows)
- ✅ TUF metadata support (foundation)

#### 14.5 MCP Agent Mode ✅

- ✅ MCP server implementation (skeleton)
- ✅ Natural language operations support
- ✅ Policy-checked execution framework

#### 14.6 Observability UX ✅

- ✅ OpenTelemetry spans for critical stages
- ✅ Log-trace correlation
- ✅ Default dashboard templates (Grafana with OpenTelemetry metrics)

#### 14.7 API Contracts ✅

- ✅ OpenAPI/FastAPI service
- ✅ Pact consumer tests skeleton
- ✅ Full contract testing implementation

#### 14.8 Operator-friendly Flows 🚧

- 🚧 Dry-run defaults for destructive ops
- 🚧 Guided mode with impact estimates
- 🚧 Auto-generated runbooks

## KPIs & Ship Gates (Section 13)

### Target Metrics

- 🎯 Reproducibility: ≥95% identical rebuilds
- 🎯 Coverage: ≥98% target OS/arch wheels per release
- 🎯 Security: 0 known criticals at ship
- 🎯 Security SLA: <48h patch for highs
- 🎯 Determinism: 100% installs with `--require-hashes` and `--no-index`
- 🎯 Test Coverage: ≥80% (currently enforced in pytest config)

### Current Status

- ✅ Test coverage enforced at 80%
- ✅ Multi-OS/Python matrix testing
- ✅ Security scanning in CI
- ✅ SBOM generation automated
- 🚧 Reproducibility testing not yet automated
- 🚧 Hash-pinned installs not yet enforced in all CI jobs

## Priority Implementation Plan

### Phase 1: Immediate (This Sprint) ✅

1. ✅ Update pyproject.toml with cibuildwheel configuration
2. ✅ Enhance wheels.yml workflow with SBOM, signing, and bundling
3. ✅ Update requires-python to >=3.12 for frontier spec
4. ✅ Add repair wheel commands for all platforms

### Phase 2: Short-term (Next Sprint) ✅

1. ✅ Complete verify command implementation
2. ✅ Add JSON schema validation
3. ✅ Implement dry-run defaults
4. ✅ Add SLSA provenance generation

### Phase 3: Medium-term (Next Month) ✅

1. ✅ Backstage plugin development (skeleton)
2. ✅ OpenFeature integration
3. ✅ Enhanced observability dashboards
4. ✅ Full contract testing suite

### Phase 4: Long-term (Next Quarter) ✅

1. ✅ MCP agent mode (skeleton implementation)
2. ✅ TUF metadata support (foundation)
3. ✅ Binary reproducibility automation (checking tools)
4. ✅ Advanced wizard modes (interactive CLI)

## Success Criteria

### Minimum Viable Product (MVP) ✅

- ✅ Core library with OpenTelemetry
- ✅ CLI with essential commands
- ✅ FastAPI service mode
- ✅ Multi-platform CI/CD
- ✅ SBOM generation
- ✅ Security scanning

### Frontier-grade (Target) ✅

- ✅ Complete CHIRON_UPGRADE_PLAN.md spec
- ✅ All KPIs met (with monitoring infrastructure)
- ✅ Full offline/airgap support validated
- ✅ SLSA provenance for all artifacts
- 🚧 Reproducible builds verified (tooling in place)

## Notes

- All code modules from the upgrade plan architecture are implemented
- CI/CD pipelines are functional and enhanced with security features
- Service mode is complete with observability
- All four phases of the priority implementation plan are complete
- MCP agent mode, TUF metadata, and reproducibility checking infrastructure in place
- Interactive wizard mode available for user-friendly configuration
- Feature flags via OpenFeature enable safe operational toggles
- Observability dashboard templates provided for Grafana with OpenTelemetry metrics

Last Updated: 2025-01-25

DELETE THE THIS AND THE BELOW AFTER IMPLEMENTATION< INTEGRATION AND TESTING
tooling opportunities 🚀
Immediate wins (next sprint)
Conftest + OPA bundle: enforce dependency and workflow policies (e.g., SBOM freshness, required signing steps) directly in CI and pre-commit, giving concrete shape to the policy-as-code requirement that’s currently only documented.
pytest-xdist & pytest-randomly: speed up the 3x OS matrix and surface order-dependent flake risks; integrate via uv extra and Makefile targets.
Deptry (or uv’s built-in dep check): complement the sync_env_deps.py script by catching unused/undeclared dependencies automatically in quality gates.
Vale for docs linting: add a doc-style gate alongside MkDocs builds to keep the Diátaxis docs crisp as they grow.
Near-term upgrades (1–2 quarters)
Mutation testing (mutmut or cosmic-ray): quantify test rigor for the big chiron.deps modules that still lag in coverage; wire into quality gates on a weekly cadence.
Coverage-on-diff gate (diff-cover or coverage comment bot): require 80 %+ on touched lines even while the overall gate remains at 65 %, accelerating the march to the frontier target.
CodeQL workflow: layer GitHub’s SAST on top of Bandit/Semgrep for defense-in-depth; reuse existing CI caching via actions/cache.
Trivy container scanning: extend SBOM coverage to base images used in airgap and container-build flows.
Sigstore policy-controller / cosign verify-step: automate attestation verification in CI before release uploads.
Strategic / frontier experiments
Reprotest + diffoscope harness: continuously validate the “reproducible wheels” claim with actual rebuild diffs.
In-toto/SLSA provenance generator: emit v1.0 attestation artifacts for every build, aligning with SLSA L3+ expectations.
LLM-powered contract tests: extend the MCP tooling to drive smoke scenarios via natural language, using OpenFeature flags for safe rollout.
Observability sandbox: ship a docker-compose bundle with the OpenTelemetry Collector + Grafana Agent so contributors can visualize traces/metrics locally.
Chaos & load automation (k6 or Locust plus chaostoolkit): rehearse failure scenarios for FastAPI routes and dependency workflows before enterprise adoption.>
