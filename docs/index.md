# Chiron Documentation

Welcome to **Chiron** - a frontier-grade, production-ready Python library and service focused on security, observability, and operational excellence.

## What is Chiron?

Chiron is designed for organizations that need:

- **Security-first development** with SBOM generation, vulnerability scanning, and artifact signing
- **Production-ready observability** with OpenTelemetry and structured logging
- **Modern Python packaging** following PEP 621/517 standards
- **Supply chain security** with SLSA provenance and reproducible builds
- **Operational excellence** with comprehensive health checks and monitoring

## Key Features

### 🔒 Security & Compliance

- **SBOM Generation**: Automatic Software Bill of Materials in CycloneDX and SPDX formats
- **Vulnerability Scanning**: Integrated scanning with Grype and Safety
- **Artifact Signing**: Keyless signing with Sigstore Cosign
- **SLSA Provenance**: Supply chain attestation and verification

### 📊 Observability

- **OpenTelemetry Integration**: Distributed tracing and metrics
- **Structured Logging**: JSON logs with trace correlation
- **Health Endpoints**: Kubernetes-ready health checks
- **Performance Monitoring**: Built-in metrics and profiling

### 🚀 Developer Experience

- **Modern Tooling**: uv for fast dependency management
- **Dev Containers**: Consistent development environment
- **Pre-commit Hooks**: Automated code quality checks
- **Rich CLI**: Comprehensive command-line interface

### 🏗️ Architecture

- **Library Mode**: Use as a Python library in your applications
- **Service Mode**: Deploy as a FastAPI service with OpenAPI docs
- **Plugin System**: Extensible architecture with entry points

## Quick Examples

### Library Usage

```python
from chiron import ChironCore

# Initialize with configuration
core = ChironCore({
    "service_name": "my-app",
    "telemetry": {"enabled": True},
    "security": {"enabled": True}
})

# Process data with observability
result = core.process_data({"user": "alice", "action": "login"})
```

### Service Mode

```bash
# Start the service
chiron serve --host 0.0.0.0 --port 8000

# Visit http://localhost:8000/docs for API documentation
```

### CLI Operations

```bash
# Initialize project
chiron init

# Build with security features
chiron build

# Create release with SBOM and signatures
chiron release

# Health check
chiron doctor
```

## Getting Started

1. **[Installation](getting-started/installation.md)** - Install Chiron in your environment
2. **[Quick Start](getting-started/quickstart.md)** - Get up and running in minutes
3. **[Configuration](getting-started/configuration.md)** - Configure for your needs

## Use Cases

### Enterprise Applications

- Secure data processing with audit trails
- Compliance reporting and documentation
- Multi-environment deployment with consistent security

### API Services

- FastAPI services with built-in observability
- Automatic OpenAPI documentation
- Health monitoring and alerting

### CI/CD Pipelines

- Secure build processes with SBOM generation
- Artifact signing and verification
- Vulnerability scanning and reporting

### Air-gapped Environments

- Offline package bundles with verification
- Internal PyPI mirrors
- Complete dependency auditing

## Architecture Overview

```mermaid
graph TB
    A[CLI Layer] --> B[Core Library]
    C[Service Layer] --> B
    B --> D[Security Module]
    B --> E[Observability Module]
    D --> F[SBOM Generation]
    D --> G[Vulnerability Scanning]
    D --> H[Artifact Signing]
    E --> I[OpenTelemetry]
    E --> J[Structured Logging]
    E --> K[Health Checks]
```

## Community & Support

- **Documentation**: Comprehensive guides and API reference
- **GitHub**: Issues, discussions, and contributions
- **Security**: Responsible disclosure process
- **Releases**: Semantic versioning with detailed changelogs

## Documentation overview

<!-- BEGIN DIATAXIS_AUTODOC -->
### Tutorials

- [Tutorial: First Run with Chiron](tutorials/first-run.md) — Install dependencies, execute the quality toolbox, and launch the FastAPI service locally.

### How-to Guides

- [Chiron Observability Sandbox](OBSERVABILITY_SANDBOX.md) — Stand up the local OpenTelemetry stack with docker-compose for metrics, traces, and logs.
- [Environment Synchronization](ENVIRONMENT_SYNC.md) — Keep dev containers, CI, and local tooling aligned with automated dependency sync scripts.
- [Grafana Dashboard Deployment Guide](GRAFANA_DEPLOYMENT_GUIDE.md) — Provision Grafana dashboards against the Chiron observability sandbox.
- [MCP Integration Testing Guide](MCP_INTEGRATION_TESTING.md) — Run the MCP server end-to-end with contract validation and wheelhouse planning.
- [Quality Gates - Frontier Standards](QUALITY_GATES.md) — Align local QA suites with CI using profile-aware planning, monitoring, and documentation sync.

### Reference

- [Supply-Chain (deps) Modules Status & Roadmap](DEPS_MODULES_STATUS.md) — Reference matrix for dependency governance coverage across modules.
- [Tooling Implementation Status](TOOLING_IMPLEMENTATION_STATUS.md) — Detailed catalogue of developer tooling and automation surfaced in the repo.
- [TUF Implementation Guide](TUF_IMPLEMENTATION_GUIDE.md) — Reference procedures for supply-chain signing and key management using TUF.

### Explanation

- [Chiron Gap Analysis (April 2025)](GAP_ANALYSIS.md) — Current operational, testing, and documentation gaps with recommended remediations.
- [CI Reproducibility Validation Guide](CI_REPRODUCIBILITY_VALIDATION.md) — Explanation of reproducible build guarantees and validation approach.
- [Module Boundary Testing Gap Analysis](MODULE_BOUNDARY_TESTING.md) — Rationale and coverage notes for cross-module integration tests.

_Updated automatically via `chiron tools docs sync-diataxis --discover`._
<!-- END DIATAXIS_AUTODOC -->

Use `uv run chiron tools docs sync-diataxis --discover` after adding or moving guides to refresh the Diataxis map and section automatically.
