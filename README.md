# Chiron

[![CI](https://github.com/IAmJonoBo/Chiron/workflows/CI/badge.svg)](https://github.com/IAmJonoBo/Chiron/actions/workflows/ci.yml)
[![Security Scan](https://github.com/IAmJonoBo/Chiron/workflows/Security%20Scan/badge.svg)](https://github.com/IAmJonoBo/Chiron/actions)
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
- 🔧 **Developer Experience**: uv, pre-commit, dev containers

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

Chiron provides a comprehensive CLI for all operations:

```bash
chiron init         # Initialize project with config
chiron build        # Build with cibuildwheel
chiron release      # Create semantic release
chiron wheelhouse   # Bundle with SBOM and signatures
chiron airgap pack  # Create offline bundle
chiron verify       # Verify signatures and provenance
chiron doctor       # Health check and policy validation
chiron serve        # Start the service
```

## 🏗️ Architecture

```
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
- **Structured Logging**: JSON logs with trace correlation
- **Metrics**: Prometheus-compatible metrics
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

- Python 3.9+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

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

# Run with coverage
uv run pytest --cov=chiron --cov-report=html

# Run security tests
uv run pytest -m security

# Run contract tests
uv run pytest -m contract
```

## 📚 Documentation

- [API Documentation](https://github.com/IAmJonoBo/Chiron/docs/api/) - Complete API reference
- [User Guide](https://github.com/IAmJonoBo/Chiron/docs/guide/) - Tutorials and how-tos
- [Architecture](https://github.com/IAmJonoBo/Chiron/docs/architecture/) - System design
- [Security](https://github.com/IAmJonoBo/Chiron/docs/security/) - Security practices

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

- ✅ Core library functionality
- ✅ Service mode with FastAPI
- ✅ CLI interface
- ✅ Security and SBOM features
- ✅ CI/CD pipeline with security scanning
- 🚧 Advanced plugin system
- 🚧 Multi-tenant support
- 📋 Performance benchmarking suite

---

<div align="center">

**[Documentation](https://github.com/IAmJonoBo/Chiron/docs)** • 
**[PyPI](https://pypi.org/project/chiron/)** • 
**[Issues](https://github.com/IAmJonoBo/Chiron/issues)** • 
**[Discussions](https://github.com/IAmJonoBo/Chiron/discussions)**

Made with ❤️ for the Python community

</div>