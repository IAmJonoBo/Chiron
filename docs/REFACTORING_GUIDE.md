---
title: "Refactoring Toolkit Migration"
diataxis: how_to
summary: Use the standalone Hephaestus project for refactoring automation and developer tooling.
---

# Refactoring Toolkit Migration

The refactoring and developer-tooling commands that previously lived inside Chiron now ship as the **Hephaestus** sister project. Install Hephaestus alongside Chiron to continue using hotspot analysis, refactor insights, characterization scaffolds, and codemods.

## Quick Start

```bash
uv tool install hephaestus
hephaestus --help
hephaestus tools refactor hotspots --limit 10
hephaestus tools qa --profile full --dry-run
```

## Why the Change?

- Keeps Chiron focused on runtime services and supply-chain automation
- Lets the developer experience toolkit evolve independently
- Enables teams to adopt Hephaestus in non-Chiron repositories

## Where to Find Documentation

All playbooks, plans, and rollout guidance now live inside the Hephaestus repository:

- `README.md` – project overview and installation notes
- `hephaestus-toolkit/refactoring/docs/README.md` – in-depth usage guide
- `hephaestus-toolkit/refactoring/docs/PLAYBOOK.md` – five-step safe refactoring workflow
- `hephaestus-toolkit/refactoring/docs/PLAN.md` – implementation plan and risk assessment

## Updating Your Automation

1. Remove references to `hephaestus tools refactor ...` or `hephaestus tools qa ...`
2. Add Hephaestus as a dependency in CI images or devcontainers
3. Replace commands with their Hephaestus equivalents, e.g.:
   - `hephaestus tools refactor analyze --json`
   - `hephaestus tools coverage hotspots`
   - `hephaestus tools docs sync-diataxis`
4. Point configuration to `[tool.hephaestus.toolkit]` inside your `pyproject.toml`

## Need Legacy Behaviour?

If you still have scripts that call the old Chiron commands, they will now emit a hand-off message. Update those scripts to call `hephaestus ...` instead so that refactoring automation continues to work.

For deeper guidance or questions, review the Hephaestus documentation or raise an issue in the Hephaestus repository.
