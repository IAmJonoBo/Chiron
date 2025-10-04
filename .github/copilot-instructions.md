<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# Chiron Project Instructions

Chiron is a frontier-grade, production-ready Python library and service focused on:

- Modern packaging with pyproject.toml (PEP 621/517)
- Security-first approach with SBOM generation, Sigstore signing, and vulnerability scanning
- Service mode with FastAPI and OpenAPI documentation
- Observability with OpenTelemetry instrumentation
- Supply chain security with SLSA provenance
- Developer experience with uv, pre-commit, and dev containers

## Development Guidelines

- Use `uv` for dependency management and tool execution
- Follow conventional commits for automated versioning
- Maintain security posture with regular SBOM and vulnerability scans
- Ensure all code follows the established patterns for observability
- Use OpenFeature for feature flags and policy-as-code with OPA/Conftest

## Project Structure

- `src/chiron/` - Main library code
- `src/chiron/service/` - FastAPI service layer
- `src/chiron/cli/` - Command-line interface
- `tests/` - Test suite including property-based and contract tests
- `docs/` - Documentation following Diátaxis structure
- `.devcontainer/` - Development container configuration