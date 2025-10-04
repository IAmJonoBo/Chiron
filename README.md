# Chiron

Build wheelhouses for air-gapped runners with automated dependency management and remediation

## Features

- 🚀 **Automated Wheelhouse Building**: Create Python wheelhouses for offline installation
- 🔒 **Air-Gapped Support**: Full offline installation capability with bundled dependencies
- 🔄 **Dependency Management**: Automated dependency resolution and remediation
- 🌐 **FastAPI Integration**: RESTful API for wheelhouse and bundle management
- 🛡️ **Security First**: SBOM generation, vulnerability scanning, and artifact signing
- 🏗️ **Modern Build System**: PEP 621/517 compliant with Hatchling backend

## Quick Start

### Installation

```bash
pip install chiron
```

### Development Setup

1. Clone the repository:
```bash
git clone https://github.com/IAmJonoBo/Chiron.git
cd Chiron
```

2. Bootstrap the development environment:
```bash
make bootstrap
```

This will:
- Install `uv` for fast package management
- Install all development dependencies
- Set up pre-commit hooks

### Using the API

Start the FastAPI server:

```bash
python -m chiron.api
```

Or with uvicorn:

```bash
uvicorn chiron.api:app --reload
```

Visit `http://localhost:8000/docs` for interactive API documentation.

## Building for Air-Gapped Environments

### Create a Wheelhouse

```bash
make wheelhouse
```

This creates a `wheelhouse/` directory with all necessary wheel files.

### Create an Airgap Bundle

```bash
make airgap
```

This creates a tarball in `airgap-bundles/` containing:
- All wheel files
- Installation instructions
- Requirements manifest

### Verify the Bundle

```bash
make verify
```

See [OFFLINE.md](OFFLINE.md) for detailed offline installation instructions.

## Development

### Available Make Targets

```bash
make help           # Show all available targets
make bootstrap      # Setup development environment
make check          # Run linting and tests
make build          # Build Python package
make release        # Create release artifacts
make wheelhouse     # Build wheelhouse
make airgap         # Create airgap bundle
make verify         # Verify airgap bundle
make clean          # Remove build artifacts
```

### Running Tests

```bash
pytest
```

### Linting

```bash
ruff check src/ tests/
ruff format src/ tests/
mypy src/
```

Or run all checks:

```bash
make check
```

## Project Structure

```
Chiron/
├── src/
│   └── chiron/
│       ├── __init__.py
│       └── api.py          # FastAPI adapter
├── tests/
├── .github/
│   └── workflows/
│       ├── ci.yml          # Continuous Integration
│       ├── wheels.yml      # Cross-platform wheel building
│       ├── release.yml     # PyPI release with security
│       └── airgap.yml      # Airgap bundle creation
├── .devcontainer/          # VS Code devcontainer
├── pyproject.toml          # PEP 621 project metadata
├── Makefile                # Build automation
├── .pre-commit-config.yaml # Pre-commit hooks
├── .gitignore
├── .editorconfig
├── README.md
├── OFFLINE.md              # Offline installation guide
└── LICENSE
```

## GitHub Actions Workflows

- **CI**: Runs linting, type checking, and tests on multiple OS and Python versions
- **Wheels**: Builds cross-platform wheels using cibuildwheel
- **Release**: Publishes to PyPI with OIDC, generates SBOM, signs artifacts
- **Airgap**: Creates offline installation bundles

## Security

All releases include:
- **SBOM**: Software Bill of Materials (CycloneDX format)
- **Vulnerability Scanning**: Automated with Syft and Grype
- **Artifact Signing**: Signed with Sigstore/cosign
- **SLSA Provenance**: Build provenance attestation

## Requirements

- Python 3.8+
- uv (installed automatically by `make bootstrap`)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run `make check` to ensure quality
5. Submit a pull request

Pre-commit hooks will automatically:
- Format code with ruff
- Run type checking with mypy
- Validate YAML, TOML, and JSON files

## License

MIT License - see [LICENSE](LICENSE) for details

## Links

- **Documentation**: [README.md](README.md)
- **Offline Guide**: [OFFLINE.md](OFFLINE.md)
- **Repository**: https://github.com/IAmJonoBo/Chiron
- **Issues**: https://github.com/IAmJonoBo/Chiron/issues
