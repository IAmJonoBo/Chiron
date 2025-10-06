# Chiron

[![CI](https://github.com/IAmJonoBo/Chiron/workflows/CI/badge.svg)](https://github.com/IAmJonoBo/Chiron/actions/workflows/ci.yml)
[![Quality Gates](https://github.com/IAmJonoBo/Chiron/workflows/Quality%20Gates/badge.svg)](https://github.com/IAmJonoBo/Chiron/actions/workflows/quality-gates.yml)
[![codecov](https://codecov.io/gh/IAmJonoBo/Chiron/branch/main/graph/badge.svg)](https://codecov.io/gh/IAmJonoBo/Chiron)
[![PyPI version](https://badge.fury.io/py/chiron.svg)](https://badge.fury.io/py/chiron)
[![Python versions](https://img.shields.io/pypi/pyversions/chiron.svg)](https://pypi.org/project/chiron/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Chiron** is a frontier-grade, production-ready Python library and service focused on security, observability, and operational excellence.

## ✨ Features

- 🏗️ **Modern Packaging**: PEP 621/517 compliant with `pyproject.toml`
- 🔒 **Security First**: SBOM generation, Sigstore signing, vulnerability scanning
- 📊 **Observability**: OpenTelemetry instrumentation with structured logging
- 🚀 **Service Mode**: FastAPI with auto-generated OpenAPI documentation
- 🛡️ **Supply Chain Security**: SLSA provenance and reproducible builds
- 🔧 **Developer Experience**: uv, pre-commit, dev containers, profile-driven `chiron tools qa`
- 🔄 **Environment Sync**: Automatic synchronization between dev and CI environments
- 📦 **Reproducible Builds**: Binary reproducibility verification and rebuild workflows
- 🐳 **Offline Deployment**: Container image caching for air-gapped environments
- 🔐 **TUF Integration**: Multi-backend key storage (AWS, Azure, Vault, keyring)
- ✅ **Quality Gates**: 8 comprehensive quality gates enforcing frontier standards
- 🎯 **89.10% Test Coverage**: Surpasses the 80% gate with healthy headroom, now covering dependency policy enforcement, constraints generation, security overlay ingestion, and the upgraded developer toolbox with profile-aware planning
- 📝 **Documentation Linting**: Vale integration for style consistency
- 🔍 **CodeQL Analysis**: Comprehensive SAST with security-extended queries
- 📈 **Coverage on Diff**: 80% threshold for changed lines
- 🧪 **Mutation Testing**: Test suite quality validation with mutmut
- 🛡️ **Container Scanning**: Trivy integration for container security
- 🔐 **Signature Verification**: Automated Sigstore/Cosign verification
- 🔄 **Reproducibility**: Automated reprotest/diffoscope validation
- 📊 **Observability Sandbox**: Complete local observability stack
- 🔥 **Chaos Testing**: Chaos Toolkit for resilience validation

## 🚀 Quick Start

### As a Library

```bash
# Install with uv (recommended)
uv add chiron

# Or with pip
pip install chiron
```

```python
from chiron import ChironCore

# Initialize with configuration
core = ChironCore({
    "service_name": "my-service",
    "telemetry": {"enabled": True},
    "security": {"enabled": True}
})

# Process data with observability
result = core.process_data({"key": "value"})
print(result)
```

### As a Service

```bash
# Install with service dependencies
uv add "chiron[service]"

# Start the service
chiron serve --host 0.0.0.0 --port 8000

# Or with configuration file
chiron init  # Creates chiron.json
chiron serve
```

Visit `http://localhost:8000/docs` for interactive API documentation.

## 📦 Installation Options

```bash
# Core library only
uv add chiron

# With all optional dependencies
uv add "chiron[dev,security,service,docs,test]"

# For development
git clone https://github.com/IAmJonoBo/Chiron.git
cd Chiron
uv sync --all-extras --dev
```

## 🛠️ CLI Commands

Chiron provides a comprehensive Typer-based CLI with rich formatting and nested commands:

```bash
# Core commands
chiron version                    # Display version
chiron init                       # Initialize project

# Dependency management (16 subcommands)
chiron deps status                # Show dependency health
chiron deps guard                 # Run dependency checks
chiron deps sync                  # Synchronize manifests
chiron deps bundle                # Create wheelhouse bundle
chiron deps scan                  # Vulnerability scanning

# Doctor diagnostics
chiron doctor offline             # Check offline readiness
chiron doctor bootstrap           # Bootstrap from wheelhouse
chiron doctor models              # Download model artifacts

# Orchestration workflows
chiron orchestrate full-dependency    # Full dependency workflow
chiron orchestrate air-gapped-prep    # Air-gapped preparation

# GitHub integration
chiron github copilot prepare     # Prepare Copilot environment
chiron github sync                # Sync artifacts

# And many more - run `chiron --help` for full list
```

All delegated script commands now share hardened exit-code handling, ensuring
consistent error messaging and reliable propagation of failures from the
underlying tooling.

### QA & Coverage Toolbox

Curate local quality gates and inspect coverage gaps without juggling multiple
commands:

```bash
# Discover and preview quality profiles before running them
chiron tools qa --list-profiles
chiron tools qa --profile fast --explain --dry-run

# Run the full suite (tests, lint, typing, security, build) and archive results
chiron tools qa --profile full --save-report reports/qa.json

# Produce machine-readable output or trim to focused gates
chiron tools qa --profile verify --no-security --json

# Surface under-tested modules and enforce coverage thresholds
chiron tools coverage hotspots --threshold 85 --limit 5
chiron tools coverage gaps --min-statements 40 --limit 3
chiron tools coverage guard --threshold 90
chiron tools coverage focus src/chiron/deps/verify.py --lines 5
```

Use these helpers to align with CI, quickly identify hotspots, and plan test
backfills while keeping automated quality gates green.

## 🏗️ Architecture

```text
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CLI Layer     │    │  Service Layer  │    │   Core Library  │
│                 │    │                 │    │                 │
│ • Commands      │◄──►│ • FastAPI       │◄──►│ • Business Logic│
│ • Rich UI       │    │ • OpenAPI       │    │ • Observability │
│ • Validation    │    │ • Middleware    │    │ • Security      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Development    │    │   Deployment    │    │   Observability │
│                 │    │                 │    │                 │
│ • uv            │    │ • Containers    │    │ • OpenTelemetry │
│ • pre-commit    │    │ • Kubernetes    │    │ • Structured    │
│ • dev container │    │ • SBOM/signing  │    │   Logging       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔒 Security Features

- **SBOM Generation**: CycloneDX and SPDX formats with Syft
- **Vulnerability Scanning**: Automated scanning with Grype
- **Artifact Signing**: Keyless signing with Sigstore Cosign
- **SLSA Provenance**: Supply chain attestation
- **Security Headers**: Comprehensive HTTP security headers
- **Input Validation**: Schema-based validation with Pydantic

## 📊 Observability

- **Distributed Tracing**: OpenTelemetry with OTLP export
- **Quiet Defaults**: OTLP exporter disabled unless `telemetry.exporter_enabled` is true and a collector is explicitly opted-in via `telemetry.assume_local_collector` or `CHIRON_ASSUME_LOCAL_COLLECTOR`
- **Structured Logging**: JSON logs with trace correlation
- **Metrics**: OpenTelemetry-compatible metrics
- **Health Checks**: Kubernetes-ready endpoints (`/health`, `/ready`, `/live`)

## 🌐 Service Mode

The FastAPI service provides:

- **OpenAPI Documentation**: Auto-generated at `/docs`
- **Health Endpoints**: `/health`, `/health/ready`, `/health/live`
- **API Versioning**: Versioned endpoints at `/api/v1`
- **CORS Support**: Configurable cross-origin requests
- **Security Middleware**: Request validation and security headers

## 🔧 Development

### Prerequisites

- Python 3.12+ (frontier-grade specification)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Environment Synchronization

Chiron automatically synchronizes dependency installation commands between the devcontainer and CI workflows:

```bash
# Manually sync environments
python scripts/sync_env_deps.py

# Pre-commit hook runs automatically
git add pyproject.toml
git commit -m "Update dependencies"
# Hook ensures devcontainer and CI use the same uv sync command
```

The sync system:

- ✅ Keeps `.devcontainer/post-create.sh` aligned with CI workflows
- ✅ Validates consistency across all environments
- ✅ Automatically creates PRs for sync changes on main branch
- ✅ Prevents environment drift with pre-commit and CI checks

See [Environment Sync Documentation](docs/ENVIRONMENT_SYNC.md) for details.

### macOS filesystem hygiene

- A pre-commit hook now runs `scripts/cleanup-macos-cruft.sh` automatically to purge Finder-created `._*`/`.DS_Store` artifacts before validation.
- For long-running sessions, set `COPYFILE_DISABLE=1` in your shell (for example, add `export COPYFILE_DISABLE=1` to `~/.bash_profile`) so macOS skips generating AppleDouble files during `uv` install or wheel extraction.
- You can run the cleanup manually at any time:

  ```bash
  bash scripts/cleanup-macos-cruft.sh --extra-path .venv
  ```

- CI runs on Linux and won't hit this bug, but keeping local working trees clean prevents sync issues and speeds up dependency installs.

### Vendored Dependencies & Offline Installs

- Refresh the repository wheelhouse with `uv run chiron wheelhouse` (defaults to packaging the `dev` and `test` extras) before running `pip install -e '.[dev,test]'` in fresh environments.
- The repository-level `sitecustomize.py` automatically points pip at `vendor/wheelhouse` and raises the network timeout so installation succeeds without extra flags.
- Generated artifacts include `manifest.json`, `requirements.txt`, and `wheelhouse.sha256` for auditability and reproducible distribution to upstream runners.
- To opt back into remote registries (for example when running GitHub Copilot coding agent), export `CHIRON_DISABLE_VENDOR_WHEELHOUSE=1` or let the bundled `copilot-setup-steps` workflow do it for you so dependencies download directly from PyPI.

### GitHub Copilot coding agent support

- `.github/workflows/copilot-setup-steps.yml` primes Copilot's ephemeral environment with `uv` and installs the dev/test extras before the agent starts, ensuring remote dependency downloads succeed.
- Keep the repository’s Copilot **Recommended allowlist** enabled (repository **Settings → Copilot → Coding agent**) so the agent can reach PyPI and other package registries. Add any internal registries to the custom allowlist if needed.

### Setup

```bash
# Clone the repository
git clone https://github.com/IAmJonoBo/Chiron.git
cd Chiron

# Install dependencies
uv sync --all-extras --dev

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest

# Start development server
uv run chiron serve --reload
```

### Dev Container

For a consistent development environment:

```bash
# Open in VS Code with dev containers
code .
# Select "Reopen in Container" when prompted
```

## 🧪 Testing

```bash
# Run all tests
uv run pytest

# Run with coverage (must exceed 50% minimum)
uv run pytest --cov=chiron --cov-report=html

# Run security tests
uv run pytest -m security

# Run contract tests
uv run pytest -m contract
```

**Test Coverage**: 89.10% (705 tests passing)

- Minimum gate: 50% ✅
- Target: 65% 🎯 (approaching)
- Frontier: 80% 🌟

See [docs/QUALITY_GATES.md](docs/QUALITY_GATES.md) for comprehensive quality standards.

## 📚 Documentation

- [Quality Gates](docs/QUALITY_GATES.md) - **NEW**: Frontier-grade quality standards
- [Testing Progress](TESTING_PROGRESS_SUMMARY.md) - **Current testing status and metrics**
- [Deps Modules Status](docs/DEPS_MODULES_STATUS.md) - **NEW**: Supply-chain testing roadmap
- [Environment Sync](docs/ENVIRONMENT_SYNC.md) - Dev/CI synchronization guide
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md) - Current status and gaps
- [TUF Implementation](docs/TUF_IMPLEMENTATION_GUIDE.md) - TUF key management
- [CI Reproducibility](docs/CI_REPRODUCIBILITY_VALIDATION.md) - Build verification
- [Grafana Deployment](docs/GRAFANA_DEPLOYMENT_GUIDE.md) - Monitoring with OpenTelemetry metrics

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run the test suite: `uv run pytest`
5. Run linting: `uv run pre-commit run --all-files`
6. Commit with conventional commit format: `git commit -m "feat: add amazing feature"`
7. Push to your branch: `git push origin feature/amazing-feature`
8. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) for the excellent web framework
- [OpenTelemetry](https://opentelemetry.io/) for observability standards
- [Sigstore](https://sigstore.dev/) for keyless signing
- [uv](https://docs.astral.sh/uv/) for fast Python package management
- [Syft](https://github.com/anchore/syft) and [Grype](https://github.com/anchore/grype) for security scanning

## 📈 Project Status

Chiron is actively developed and maintained. We follow semantic versioning and maintain backwards compatibility within major versions.

### Quality Status

- ✅ **Test Coverage**: 89.10% (exceeds the 80% frontier gate with margin)
- ✅ **Security Gate**: Zero critical vulnerabilities
- ✅ **Type Safety**: Strict MyPy checking passes
- ✅ **Code Quality**: Ruff linting passes
- ✅ **All Tests Passing**: 705 tests

### Feature Status

- ✅ Core library functionality (100% coverage)
- ✅ Observability suite (96-100% coverage)
- ✅ Service mode with FastAPI
- ✅ CLI interface with subprocess utilities
- ✅ Security and SBOM features
- ✅ Quality gates enforcement
- ✅ MCP server with real operations (wheelhouse, policy, verification)
- 🟡 Supply-chain modules (testing in progress)
- 🚧 Advanced plugin system
- 🚧 Multi-tenant support
- ✅ Performance benchmarking suite

See [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for detailed status.

---

**[Documentation](https://github.com/IAmJonoBo/Chiron/docs)** •
**[PyPI](https://pypi.org/project/chiron/)** •
**[Issues](https://github.com/IAmJonoBo/Chiron/issues)** •
**[Discussions](https://github.com/IAmJonoBo/Chiron/discussions)**

Made with ❤️ for the Python community.
