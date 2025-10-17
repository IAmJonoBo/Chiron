# Quick Start Guide

Get up and running with Chiron in minutes.

## Prerequisites

Make sure you have completed the [installation](installation.md) steps.

## Your First Chiron Application

### Library Mode

Create a simple Python script using Chiron as a library:

```python
# example.py
from chiron import ChironCore

# Initialize Chiron
core = ChironCore({
    "service_name": "my-first-app",
    "telemetry": {"enabled": True},
    "security": {"enabled": True}
})

# Process some data
result = core.process_data({
    "user": "alice",
    "action": "login",
    "timestamp": "2024-01-01T00:00:00Z"
})

print(f"Result: {result}")
```

Run it:

```bash
python example.py
```

### Service Mode

Start Chiron as a FastAPI service:

```bash
# Initialize configuration
chiron init

# Start the service
chiron serve --host 0.0.0.0 --port 8000

# Or with auto-reload for development
chiron serve --reload
```

Visit the interactive API documentation at `http://localhost:8000/docs`.

## CLI Operations

### Health Check

Verify your Chiron installation:

```bash
chiron doctor
```

### Dependency Management

```bash
# Check dependency status
chiron deps status

# Run dependency checks
chiron deps guard

# Sync dependency manifests
chiron deps sync
```

### Quality Gates

Run quality checks locally:

```bash
# Run all quality gates
hephaestus tools qa --profile full

# Run fast checks (tests + lint)
hephaestus tools qa --profile fast

# Run with coverage monitoring
hephaestus tools qa --profile full --monitor --coverage-xml coverage.xml
```

### Creating a Wheelhouse

Bundle dependencies for offline installation:

```bash
# Create wheelhouse with default extras (dev, test)
chiron deps bundle

# Create with specific extras
chiron deps bundle --extras "service,security"
```

## Working with Configuration

Chiron uses a `chiron.json` configuration file. Initialize it with:

```bash
chiron init
```

Edit the generated `chiron.json`:

```json
{
  "service_name": "my-service",
  "version": "0.1.0",
  "telemetry": {
    "enabled": true,
    "exporter_enabled": false,
    "assume_local_collector": false
  },
  "security": {
    "enabled": true,
    "generate_sbom": true,
    "scan_vulnerabilities": true
  },
  "service": {
    "host": "0.0.0.0",
    "port": 8000,
    "cors_origins": ["*"]
  }
}
```

## Development Workflow

### Run Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=chiron --cov-report=html

# Run specific test categories
uv run pytest -m security
uv run pytest -m contract
```

### Code Quality

```bash
# Lint code
uv run ruff check

# Auto-fix linting issues
uv run ruff check --fix

# Format code
uv run ruff format

# Type checking
uv run mypy src
```

### Pre-commit Hooks

Install and use pre-commit hooks:

```bash
# Install hooks
uv run pre-commit install

# Run manually on all files
uv run pre-commit run --all-files

# Skip hooks when needed
git commit --no-verify
```

## Observability

### Local Observability Stack

Start the complete observability stack with Grafana, Prometheus, and Tempo:

```bash
# Start the stack
docker-compose -f docker-compose.observability.yml up -d

# View logs
docker-compose -f docker-compose.observability.yml logs -f

# Access interfaces
# - Grafana: http://localhost:3000 (admin/admin)
# - Prometheus: http://localhost:9090
# - Jaeger: http://localhost:16686
```

See the [Observability Sandbox Guide](../OBSERVABILITY_SANDBOX.md) for details.

## Next Steps

- [Configuration Guide](configuration.md) - Detailed configuration options
- [Quality Gates](../QUALITY_GATES.md) - Understand the quality standards
- [Tutorial: First Run](../tutorials/first-run.md) - Comprehensive walkthrough
- [MCP Integration Testing](../MCP_INTEGRATION_TESTING.md) - Test the MCP server
