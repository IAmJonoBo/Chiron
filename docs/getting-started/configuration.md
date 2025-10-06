# Configuration Guide

Learn how to configure Chiron for your specific needs.

## Configuration File

Chiron uses a `chiron.json` configuration file in your project root.

### Initialize Configuration

```bash
chiron init
```

This creates a default configuration file with sensible defaults.

## Configuration Structure

### Complete Example

```json
{
  "service_name": "my-service",
  "version": "0.1.0",
  "telemetry": {
    "enabled": true,
    "exporter_enabled": false,
    "assume_local_collector": false,
    "service_name": "my-service",
    "endpoint": "http://localhost:4317"
  },
  "security": {
    "enabled": true,
    "generate_sbom": true,
    "scan_vulnerabilities": true,
    "sign_artifacts": false
  },
  "service": {
    "host": "0.0.0.0",
    "port": 8000,
    "cors_origins": ["*"],
    "enable_docs": true
  },
  "features": {
    "allow_public_publish": false,
    "enable_experimental_features": false
  }
}
```

## Configuration Sections

### Service Information

```json
{
  "service_name": "my-service",
  "version": "0.1.0"
}
```

- **service_name**: Identifier for your service (used in telemetry and logs)
- **version**: Service version for tracking and deployment

### Telemetry

```json
{
  "telemetry": {
    "enabled": true,
    "exporter_enabled": false,
    "assume_local_collector": false,
    "service_name": "my-service",
    "endpoint": "http://localhost:4317"
  }
}
```

- **enabled**: Enable telemetry collection (structured logging, metrics)
- **exporter_enabled**: Enable OTLP exporter for sending telemetry data
- **assume_local_collector**: Assume local OpenTelemetry collector is available
- **service_name**: Service name for telemetry (defaults to main service_name)
- **endpoint**: OTLP collector endpoint

!!! note "Quiet Defaults"
    Telemetry collection is local by default. The OTLP exporter is disabled unless explicitly enabled via `exporter_enabled: true` and a collector is configured.

### Security

```json
{
  "security": {
    "enabled": true,
    "generate_sbom": true,
    "scan_vulnerabilities": true,
    "sign_artifacts": false
  }
}
```

- **enabled**: Enable security features
- **generate_sbom**: Generate Software Bill of Materials (SBOM)
- **scan_vulnerabilities**: Scan for vulnerabilities with Grype
- **sign_artifacts**: Sign artifacts with Sigstore Cosign

### Service Mode

```json
{
  "service": {
    "host": "0.0.0.0",
    "port": 8000,
    "cors_origins": ["*"],
    "enable_docs": true
  }
}
```

- **host**: Service bind address
- **port**: Service port
- **cors_origins**: Allowed CORS origins (use ["*"] for development)
- **enable_docs**: Enable OpenAPI documentation at `/docs`

### Feature Flags

```json
{
  "features": {
    "allow_public_publish": false,
    "enable_experimental_features": false
  }
}
```

Feature flags for controlling optional behaviors.

## Environment Variables

Chiron supports environment variable overrides:

### Telemetry

```bash
# Assume local OpenTelemetry collector
export CHIRON_ASSUME_LOCAL_COLLECTOR=1

# Set OTLP endpoint
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

### Development

```bash
# Disable vendored wheelhouse (allow remote package downloads)
export CHIRON_DISABLE_VENDOR_WHEELHOUSE=1

# Set log level
export CHIRON_LOG_LEVEL=DEBUG
```

### Security

```bash
# Skip signature verification (development only)
export CHIRON_SKIP_SIGNATURE_VERIFICATION=1
```

## pyproject.toml Integration

For library usage, configure Chiron in your `pyproject.toml`:

```toml
[tool.chiron]
service_name = "my-service"
version = "0.1.0"

[tool.chiron.telemetry]
enabled = true
exporter_enabled = false

[tool.chiron.security]
enabled = true
generate_sbom = true
```

## Configuration Precedence

Configuration is resolved in this order (highest priority first):

1. Environment variables
2. `chiron.json` in project root
3. `pyproject.toml` `[tool.chiron]` section
4. Default values

## Development vs Production

### Development Configuration

```json
{
  "service_name": "my-service-dev",
  "telemetry": {
    "enabled": true,
    "exporter_enabled": false
  },
  "security": {
    "enabled": true,
    "sign_artifacts": false
  },
  "service": {
    "cors_origins": ["*"],
    "enable_docs": true
  }
}
```

### Production Configuration

```json
{
  "service_name": "my-service",
  "telemetry": {
    "enabled": true,
    "exporter_enabled": true,
    "endpoint": "https://collector.prod.example.com:4317"
  },
  "security": {
    "enabled": true,
    "generate_sbom": true,
    "scan_vulnerabilities": true,
    "sign_artifacts": true
  },
  "service": {
    "host": "0.0.0.0",
    "port": 8000,
    "cors_origins": ["https://app.example.com"],
    "enable_docs": false
  }
}
```

## Quality Gates Configuration

Configure quality gates in `pyproject.toml`:

```toml
[tool.chiron.quality]
# Override default quality gates
gates = ["tests", "lint", "types", "security", "docs", "build"]

# Define custom profiles
[tool.chiron.quality.profiles]
ci = ["tests", "lint", "types", "security"]
fast = ["tests", "lint"]
```

## Validation

Validate your configuration:

```bash
# Check configuration
chiron doctor

# Validate against schema
chiron tools validate-config chiron.json
```

## Next Steps

- [Quality Gates](../QUALITY_GATES.md) - Configure quality standards
- [Environment Sync](../ENVIRONMENT_SYNC.md) - Keep environments aligned
- [Observability Sandbox](../OBSERVABILITY_SANDBOX.md) - Set up monitoring
