---
title: "Tutorial: First Run with Chiron"
diataxis: tutorials
summary: Install dependencies, execute the quality toolbox, and launch the FastAPI service locally.
---

# Tutorial: First Run with Chiron

This guided walkthrough exercises the developer toolbox, FastAPI service, and quality gates on a fresh workstation.

## Prerequisites

- Python 3.12 or 3.13
- [uv](https://docs.astral.sh/uv/) 0.8 or later
- Git

## 1. Clone and install

```bash
git clone https://github.com/IAmJonoBo/Chiron.git
cd Chiron
uv sync --all-extras --dev
uv run pre-commit install
```

The sync step provisions every optional extra so the CLI, FastAPI service, and security tooling are available locally.

## 2. Inspect quality profiles

```bash
uv run chiron tools qa --list-profiles
uv run chiron tools qa --profile fast --dry-run --explain
```

Dry runs preview the execution plan, highlighting which gates are required and where monitoring insights will surface.

## 3. Run the frontier profile

```bash
uv run chiron tools qa --profile full --monitor --coverage-xml coverage.xml --sync-docs docs/QUALITY_GATES.md
```

- Executes tests, lint, typing, security, docs, and build gates.
- Streams progress bars in the terminal.
- Updates documentation markers automatically when the run completes.

## 4. Launch the service

```bash
uv run chiron serve --host 127.0.0.1 --port 8000
```

Visit `http://127.0.0.1:8000/docs` for interactive OpenAPI documentation. Health checks are available at `/health`, `/ready`, and `/live`.

## 5. Explore observability

```bash
uv run chiron tools qa --profile full --monitor --coverage-xml coverage.xml --json
uv run chiron tools coverage hotspots --threshold 85 --limit 5
```

The monitoring report surfaces coverage hotspots for CLI and service modules and identifies follow-up risks for downstream automation.

## Next steps

- Try `uv run chiron tools docs sync-diataxis` to regenerate the documentation overview.
- Use `uv run chiron doctor offline` to validate air-gapped packaging workflows.
- Review [QUALITY_GATES.md](../QUALITY_GATES.md) and [ENVIRONMENT_SYNC.md](../ENVIRONMENT_SYNC.md) for deeper operational guidance.

Happy shipping!
