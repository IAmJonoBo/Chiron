# Chiron Documentation

Welcome to Chiron's documentation! This directory contains comprehensive guides for using and contributing to Chiron.

## Quick Start

- [Main README](../README.md) - Project overview and quick start
- [Installation Guide](../README.md#installation) - How to install Chiron
- [Contributing Guide](../CONTRIBUTING.md) - How to contribute

## Core Documentation

### Implementation & Status

- [Implementation Summary](../IMPLEMENTATION_SUMMARY.md) - **Current implementation status** (⭐ Primary reference)
- [Testing Progress Summary](../TESTING_PROGRESS_SUMMARY.md) - **Current testing status and metrics**
- [Gap Analysis](GAP_ANALYSIS.md) - Known gaps and future work
- [Roadmap](../ROADMAP.md) - Feature roadmap and completion status

### Quality & Standards

- [Quality Gates](QUALITY_GATES.md) - **Frontier-grade quality standards and enforcement**
- [Environment Sync](ENVIRONMENT_SYNC.md) - Dev/CI environment synchronization

### Supply Chain & Dependencies

- [Deps Modules Status](DEPS_MODULES_STATUS.md) - **Supply-chain testing roadmap**
- [CI Reproducibility Validation](CI_REPRODUCIBILITY_VALIDATION.md) - Reproducible builds guide
- [TUF Implementation Guide](TUF_IMPLEMENTATION_GUIDE.md) - TUF key management

### Monitoring & Operations

- [Grafana Deployment Guide](GRAFANA_DEPLOYMENT_GUIDE.md) - Dashboard deployment with OpenTelemetry metrics
- [MCP Integration Testing](MCP_INTEGRATION_TESTING.md) - MCP server testing guide

## Specialized Guides

### Offline & Air-Gapped Deployments

- [Offline Deployment](../OFFLINE.md) - Air-gapped installation guide

### Architecture & Planning

- [Chiron Upgrade Plan](../CHIRON_UPGRADE_PLAN.md) - Detailed architecture and design

## Deprecated Documentation

Historical documentation that has been superseded is available in [`deprecated/`](deprecated/README.md).

**Note**: Always use the current documentation linked above. Deprecated docs are kept for reference only.

## Documentation Structure

Following the [Diátaxis](https://diataxis.fr/) framework:

- **Tutorials**: Learning-oriented guides (coming soon)
- **How-to Guides**: Task-oriented instructions (Quality Gates, Environment Sync, etc.)
- **Reference**: Technical descriptions (API docs, module references)
- **Explanation**: Understanding-oriented discussions (Gap Analysis, Architecture)

## Contributing to Documentation

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines on improving documentation.

When adding documentation:

1. Follow existing structure and style
2. Update this index when adding new guides
3. Keep examples current and tested
4. Cross-reference related documents
5. Mark outdated docs as deprecated rather than deleting them
