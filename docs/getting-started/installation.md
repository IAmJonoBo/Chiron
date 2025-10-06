# Installation

This guide covers installing Chiron in various environments.

## Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Standard Installation

### Using uv (Recommended)

```bash
# Install core library
uv add chiron

# Install with all extras
uv add "chiron[dev,security,service,docs,test]"
```

### Using pip

```bash
# Install core library
pip install chiron

# Install with all extras
pip install "chiron[dev,security,service,docs,test]"
```

## Development Installation

For contributing or local development:

```bash
# Clone the repository
git clone https://github.com/IAmJonoBo/Chiron.git
cd Chiron

# Install dependencies with uv
uv sync --all-extras --dev

# Install pre-commit hooks
uv run pre-commit install

# Verify installation
uv run pytest
```

## Optional Dependencies

Chiron provides several optional dependency groups:

- **dev**: Development tools (ruff, mypy, pre-commit)
- **security**: Security scanning tools (bandit, safety)
- **service**: FastAPI service dependencies
- **docs**: Documentation building tools (mkdocs)
- **test**: Testing frameworks (pytest, coverage)

Install specific groups as needed:

```bash
# Install with security tools
uv add "chiron[security]"

# Install with service dependencies
uv add "chiron[service]"
```

## Container Installation

For containerized environments:

```dockerfile
FROM python:3.12-slim

# Install uv
RUN pip install uv

# Install Chiron
RUN uv add chiron

# Or with all extras
RUN uv add "chiron[service,security]"
```

## Verification

Verify your installation:

```bash
# Check version
chiron version

# Run tests
uv run pytest

# Check all systems
chiron doctor
```

## Troubleshooting

### macOS Filesystem Issues

If you encounter filesystem artifacts on macOS:

```bash
# Clean up macOS cruft
bash scripts/cleanup-macos-cruft.sh --extra-path .venv

# Set environment variable to prevent future issues
export COPYFILE_DISABLE=1
```

### Offline Installation

For air-gapped environments, see the [offline deployment guide](../OFFLINE.md).

## Next Steps

- [Quick Start Guide](quickstart.md) - Get started with your first Chiron application
- [Configuration Guide](configuration.md) - Configure Chiron for your needs
- [Tutorial: First Run](../tutorials/first-run.md) - Complete walkthrough
