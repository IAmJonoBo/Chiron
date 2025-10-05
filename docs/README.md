# Chiron Documentation

This directory contains up-to-date documentation for the Chiron project. Key status documents were refreshed in April 2025 to reflect the current implementation and testing gaps.

## Quick Links

### High-level Status

- [GAP_ANALYSIS](GAP_ANALYSIS.md) – Current gaps, failing tests, and remediation plan
- [IMPLEMENTATION_SUMMARY](../IMPLEMENTATION_SUMMARY.md) – Reality check of feature maturity
- [TESTING_IMPLEMENTATION_SUMMARY](../TESTING_IMPLEMENTATION_SUMMARY.md) – Latest pytest outcomes and coverage

### For New Users

- [README](../README.md) – Project overview and quickstart (review alongside the status docs above)
- [CONTRIBUTING](../CONTRIBUTING.md) – How to contribute

### Additional Guides

- [ENVIRONMENT_SYNC](ENVIRONMENT_SYNC.md) – **NEW**: Automatic synchronization between dev and CI environments
- [CI_REPRODUCIBILITY_VALIDATION](CI_REPRODUCIBILITY_VALIDATION.md) – Reproducibility checks and rebuild workflows
- [GRAFANA_DEPLOYMENT_GUIDE](GRAFANA_DEPLOYMENT_GUIDE.md) – Grafana deployment notes (ensure metrics endpoints exist first)
- [MCP_INTEGRATION_TESTING](MCP_INTEGRATION_TESTING.md) – MCP testing playbook (tools currently marked experimental)
- [TUF_IMPLEMENTATION_GUIDE](TUF_IMPLEMENTATION_GUIDE.md) – TUF implementation with multi-backend key storage

## Getting Started Checklist

1. Read the refreshed [GAP_ANALYSIS](GAP_ANALYSIS.md) to understand open issues.
2. Refresh the vendored dependency wheelhouse with `uv run chiron wheelhouse` (defaults to the dev+test extras), then run tests via `python -m venv .venv && .venv/bin/pip install -e ".[dev,test]" && .venv/bin/pytest`. The install step will automatically consume the pre-populated `vendor/wheelhouse` via `sitecustomize`, keeping offline and CI parity.
3. If working on the FastAPI service, prefer exercising endpoints via `TestClient` rather than shelling out to `uv`/`tar`.
4. For MCP or feature-flag work, implement `get_feature_flags()` and convert dry-run responses into real operations before updating guides.

## Maintenance Notes

- Treat the status documents as the source of truth; older success narratives were archived but do not reflect the current codebase.
- Update documentation in lockstep with code changes, especially when enabling telemetry, MCP tooling, or supply-chain workflows.
