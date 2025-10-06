---
title: "Environment Synchronization"
diataxis: how_to
summary: Keep dev containers, CI, and local tooling aligned with automated dependency sync scripts.
---

# Environment Synchronization

This document describes the automatic synchronization mechanism between development and CI environments in Chiron.

## Overview

Chiron maintains consistency between the devcontainer configuration and GitHub Actions workflows by automatically synchronizing dependency installation commands. This ensures that developers and CI use identical dependency resolution.

## How It Works

### Automatic Synchronization

The synchronization system consists of three components:

1. **Sync Script** (`scripts/sync_env_deps.py`)
   - Extracts the canonical dependency command from `pyproject.toml`
   - Updates `.devcontainer/post-create.sh` with the correct `uv sync` command
   - Updates all GitHub Actions workflows to use the same command
   - Validates consistency across all environments

2. **Pre-commit Hook** (`.pre-commit-config.yaml`)
   - Runs automatically when relevant files are modified
   - Ensures sync before commits are made
   - Prevents drift between dev and CI environments

3. **GitHub Actions Workflow** (`.github/workflows/sync-env.yml`)
   - Runs on pushes to main or PRs that modify relevant files
   - Automatically creates PRs to sync changes on main branch
   - Validates consistency in CI

### Triggered By

Synchronization is triggered when these files change:

- `pyproject.toml` - Project dependencies
- `.devcontainer/**` - Devcontainer configuration
- `.github/workflows/ci.yml` - CI workflow
- `.github/workflows/wheels.yml` - Wheel building workflow
- `.github/workflows/airgap.yml` - Air-gapped deployment workflow
- `scripts/sync_env_deps.py` - The sync script itself

## Usage

### Manual Sync

To manually synchronize environments:

```bash
python scripts/sync_env_deps.py
```

This will:

- Update all environment configurations
- Report changes made
- Validate consistency

### Pre-commit Hook

The pre-commit hook runs automatically when you modify relevant files:

```bash
git add pyproject.toml
git commit -m "Update dependencies"
# Hook runs automatically and updates environment configs
```

To skip the hook (not recommended):

```bash
git commit --no-verify -m "Update dependencies"
```

### CI Workflow

On push to main, if sync is needed:

- A PR is automatically created with the sync changes
- The PR includes a detailed description of changes
- Review and merge the PR to apply the changes

On pull requests:

- The workflow validates that environments are in sync
- Fails if sync is needed
- Run `python scripts/sync_env_deps.py` locally to fix

## Files Synchronized

### Devcontainer

- `.devcontainer/post-create.sh` - Post-creation script
  - `uv sync` command is kept in sync with CI

### GitHub Actions

- `.github/workflows/ci.yml` - Main CI workflow
- `.github/workflows/wheels.yml` - Wheel building
- `.github/workflows/airgap.yml` - Air-gapped deployment

All workflows use the same `uv sync` command pattern.

## Benefits

1. **Consistency** - Dev and CI use identical dependency resolution
2. **Automation** - No manual updates needed
3. **Validation** - Pre-commit and CI checks prevent drift
4. **Transparency** - All changes are tracked in git
5. **Safety** - PRs for review before merging to main

## Implementation Details

### Dependency Command Extraction

The sync script extracts the canonical command by:

1. Reading `pyproject.toml` to understand dependency structure
2. Determining the appropriate `uv sync` flags
3. Applying the same command to all environments

The core synchronizer now scopes all filesystem interactions to the repository
root it is initialised with. This enables deterministic unit tests and lets the
tool operate against checked-out release branches or sandboxes without mutating
the main workspace.

### Update Strategy

Updates are applied using:

- Regex pattern matching for `uv sync` commands
- Preserves formatting and context
- Only modifies the actual command string

### Validation

Consistency validation checks:

- All files contain `uv sync` commands
- Commands use compatible flags
- No conflicting patterns exist

## Troubleshooting

### Sync Script Fails

If the sync script fails:

1. Check Python version (requires 3.12+)
2. Verify file permissions
3. Review error messages for specific issues

### Pre-commit Hook Fails

If the pre-commit hook fails:

1. Run sync manually: `python scripts/sync_env_deps.py`
2. Review and commit changes
3. Try commit again

### CI Workflow Fails

If CI validation fails:

1. Pull latest changes
2. Run sync locally: `python scripts/sync_env_deps.py`
3. Commit and push changes
4. CI should pass on next run

## Examples

### Adding New Dependencies

```bash
# Edit pyproject.toml to add dependencies
vim pyproject.toml

# Commit changes - sync runs automatically
git add pyproject.toml
git commit -m "Add new dependencies"

# Pre-commit hook updates all environment files
# Review the additional changes
git diff --cached

# Push changes
git push
```

### Manual Sync After Merge Conflict

```bash
# After resolving merge conflicts in pyproject.toml
git add pyproject.toml

# Run sync manually to update environments
python scripts/sync_env_deps.py

# Add sync changes
git add .devcontainer .github/workflows

# Complete merge
git commit
```

## Enhancement Status

All roadmap enhancements for environment sync have been implemented:

- ✅ **Additional package manager awareness** – configuration in `pyproject.toml`
  allows mapping multiple package managers (`uv`, `pip`) so CI/devcontainer scripts
  stay in parity even when alternative installers are required.
- ✅ **Tool version alignment** – Python version and uv version metadata are read
  from the project configuration and automatically applied to devcontainer images
  and GitHub Actions matrices.
- ✅ **Lockfile validation** – the sync script now verifies that every declared
  dependency (including optional extras) is represented in `uv.lock`, catching
  drift before CI jobs run.
- ✅ **Optional dependency sync** – default commands run `uv sync --all-extras --dev`
  ensuring developer environments match the superset of optional features.
- ✅ **Renovate automation** – Renovate now invokes `scripts/sync_env_deps.py`
  after dependency upgrades so environment definitions stay consistent without
  manual intervention.

## Related

- [Contributing Guide](CONTRIBUTING.md)
- Development Setup: See project README for development instructions
- [CI/CD Documentation](CI_REPRODUCIBILITY_VALIDATION.md)
