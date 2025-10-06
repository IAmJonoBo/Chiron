# Refactoring Toolkit

**Location:** `dev-toolkit/refactoring/`  
**Status:** ✅ Production Ready

## Overview

This toolkit provides evidence-based refactoring tools for the Chiron project. It combines git churn analysis with code complexity metrics to identify high-value refactoring targets (hotspots).

### Key Features

- **Hotspot Analysis**: Identify code that is both complex and frequently changed
- **Refactor Analysis**: Detect long functions, large classes, and high complexity
- **Safe Codemods**: LibCST-based transformations that preserve formatting
- **Characterization Tests**: Scaffold generation for behavior-locking tests
- **PR Sharding**: Split large refactorings into manageable chunks
- **CI Integration**: Warn-only quality gates for gradual adoption

## Quick Start

### Using CLI Commands (Recommended)

```bash
# Find top refactoring priorities
chiron tools refactor hotspots --limit 10

# Analyze specific file
chiron tools refactor analyze --path src/chiron/module.py

# Export for CI/CD
chiron tools refactor hotspots --json > hotspots.json
chiron tools refactor analyze --json > opportunities.json
```

### Using Standalone Scripts

```bash
# Git churn analysis
bash dev-toolkit/refactoring/scripts/analyse/git_churn.sh "12 months ago"

# Hotspot calculation (requires radon)
python dev-toolkit/refactoring/scripts/analyse/hotspots_py.py src/chiron

# Function renaming codemod
python dev-toolkit/refactoring/scripts/codemods/py/rename_function.py \
  --old-name old_func --new-name new_func \
  --path src/module.py --dry-run

# Generate characterization tests
python dev-toolkit/refactoring/scripts/verify/snapshot_scaffold.py \
  --path src/chiron/module.py

# Plan PR shards
git diff --name-only main | python dev-toolkit/refactoring/scripts/rollout/shard_pr_list.py --stdin
```

### Using Makefile Targets

```bash
# Run hotspot analysis
make refactor-analyse

# Generate characterization test scaffolds
make refactor-verify

# Run codemods (dry-run)
make refactor-codemod
```

## Directory Structure

```
dev-toolkit/refactoring/
├── config/
│   └── refactor.config.yaml       # Configuration defaults
├── scripts/
│   ├── analyse/
│   │   ├── git_churn.sh          # Git churn analyzer
│   │   └── hotspots_py.py        # Hotspot calculator
│   ├── codemods/
│   │   └── py/
│   │       └── rename_function.py # Function renaming transformer
│   ├── verify/
│   │   └── snapshot_scaffold.py  # Test scaffold generator
│   └── rollout/
│       └── shard_pr_list.py      # PR shard planner
├── ci/
│   └── workflow.partial.yml      # CI workflow template
├── docs/
│   ├── README.md                 # This file
│   ├── PLAN.md                   # Discovery and planning
│   └── PLAYBOOK.md               # Five-step workflow guide
└── output/                        # Generated artifacts
    ├── churn.txt
    ├── hotspots.csv
    └── *.json
```

## Methodology

### Hotspot Formula

```
Hotspot Score = Complexity × Churn
```

- **Complexity**: Sum of function/method complexity in a file
- **Churn**: Number of times file changed in time window
- **Score**: Higher score = higher priority for refactoring

### Why This Works

1. **High Complexity**: Hard to understand and maintain
2. **High Churn**: Frequently changed (bug-prone, active development)
3. **Combined**: Maximum pain point and highest ROI for refactoring

### Thresholds

Default thresholds (configurable in `config/refactor.config.yaml`):

- **Critical** (red): Hotspot score > 1000
- **Warning** (yellow): Hotspot score > 500
- **Info** (cyan): Hotspot score ≤ 500
- **Minimum complexity**: 10
- **Minimum churn**: 2

## Configuration

Edit `config/refactor.config.yaml` to customize:

```yaml
prioritisation:
  timespan: "12 months"
  hotspot_formula: "complexity_sum * churn"
  max_candidates: 10
  min_complexity: 10
  min_churn: 2

refactor_analysis:
  max_function_length: 60
  max_class_methods: 12
  max_cyclomatic_complexity: 10
  max_parameters: 6

rollout:
  shard_size: 50
  require_green_main: true
```

## Workflow

Follow the five-step safe refactoring loop (see `docs/PLAYBOOK.md`):

1. **Pick Hotspots** → Identify high-value targets
2. **Add Tests** → Lock in current behavior
3. **Refactor** → Make incremental improvements
4. **Validate** → Ensure no regressions
5. **Shard & Merge** → Split into reviewable PRs

## Scripts Reference

### Git Churn Analysis

**Script:** `scripts/analyse/git_churn.sh`

```bash
# Default: 12 months
bash scripts/analyse/git_churn.sh

# Custom time window
bash scripts/analyse/git_churn.sh "6 months ago"

# Custom output
bash scripts/analyse/git_churn.sh "12 months ago" custom-churn.txt
```

**Output:** Text file with format `<count> <file>`

### Hotspot Analysis

**Script:** `scripts/analyse/hotspots_py.py`

**Requirements:** `pip install radon`

```bash
# Default: analyze src/
python scripts/analyse/hotspots_py.py

# Custom source directory
python scripts/analyse/hotspots_py.py src/chiron

# With thresholds
python scripts/analyse/hotspots_py.py src/chiron \
  --min-complexity 20 \
  --min-churn 3

# Custom output
python scripts/analyse/hotspots_py.py src/chiron \
  --output custom-hotspots.csv
```

**Output:** CSV file with columns: file, complexity_sum, churn, hotspot_score

### Function Renaming

**Script:** `scripts/codemods/py/rename_function.py`

**Requirements:** `pip install libcst`

```bash
# Dry run (default)
python scripts/codemods/py/rename_function.py \
  --old-name old_func \
  --new-name new_func \
  src/module.py

# Apply changes
python scripts/codemods/py/rename_function.py \
  --old-name old_func \
  --new-name new_func \
  src/module.py \
  --apply

# Scan directory
python scripts/codemods/py/rename_function.py \
  --old-name old_func \
  --new-name new_func \
  --dir src/ \
  --apply
```

### Characterization Tests

**Script:** `scripts/verify/snapshot_scaffold.py`

```bash
# Generate test scaffolds
python scripts/verify/snapshot_scaffold.py \
  --path src/chiron/dev_toolbox.py

# Custom output directory
python scripts/verify/snapshot_scaffold.py \
  --path src/chiron/module.py \
  --output tests/characterization/

# Limit functions
python scripts/verify/snapshot_scaffold.py \
  --path src/chiron/module.py \
  --max-functions 5
```

**Output:** Test file with pytest scaffold in `tests/snapshots/`

### PR Sharding

**Script:** `scripts/rollout/shard_pr_list.py`

```bash
# From file
git diff --name-only main > changed.txt
python scripts/rollout/shard_pr_list.py --input changed.txt

# From stdin
git diff --name-only main | python scripts/rollout/shard_pr_list.py --stdin

# Custom shard size
python scripts/rollout/shard_pr_list.py \
  --input changed.txt \
  --shard-size 30

# JSON output
python scripts/rollout/shard_pr_list.py \
  --input changed.txt \
  --format json \
  --output pr-shards.json
```

## CI/CD Integration

### Using CI Partial

The `ci/workflow.partial.yml` file provides ready-to-use GitHub Actions jobs:

1. **refactor-analyse**: Runs hotspot and refactor analysis
2. **refactor-analyse-standalone**: Uses standalone scripts
3. **refactor-gates**: Quality gates (lint, type, complexity, tests)
4. **refactor-mutation-testing**: Weekly mutation testing

**Integration Options:**

1. **Copy into existing workflow:**
   ```bash
   # Merge jobs into .github/workflows/ci.yml
   ```

2. **Use as standalone workflow:**
   ```bash
   cp dev-toolkit/refactoring/ci/workflow.partial.yml \
      .github/workflows/refactoring.yml
   ```

All gates are **warn-only** initially (`continue-on-error: true`). Remove this flag to enforce gates.

### Manual CI Integration

```yaml
# In your CI workflow
- name: Analyze Hotspots
  run: |
    uv run chiron tools refactor hotspots --json > hotspots.json
    uv run chiron tools refactor analyze --json > opportunities.json

- name: Upload Analysis
  uses: actions/upload-artifact@v4
  with:
    name: refactor-reports
    path: |
      hotspots.json
      opportunities.json
```

## Quality Gates

### Advisory Mode (Default)

Gates initially run in advisory mode (warn-only):
- Failures don't block CI
- Allows monitoring and threshold tuning
- Gradual adoption path

### Enforcement Mode

To enforce gates, remove `continue-on-error: true` from CI jobs or use:

```bash
# Fail on complexity issues
radon cc src/chiron -n B || exit 1

# Fail on coverage drop
coverage report --fail-under=80 || exit 1
```

### Recommended Thresholds

Based on Chiron's current state:

- Coverage: ≥ 80%
- Complexity grade: B or better
- Duplication: < 1%
- Security: Block on high/critical findings

## Hardening Guide

To transition from advisory to enforced gates:

1. **Monitor Initial Results**
   ```bash
   # Run analysis weekly for 2-4 weeks
   chiron tools refactor hotspots --json > baseline-$(date +%Y%m%d).json
   ```

2. **Tune Thresholds**
   - Adjust `config/refactor.config.yaml`
   - Ensure current codebase passes gates

3. **Remove Advisory Flag**
   ```yaml
   # Remove from CI jobs:
   # continue-on-error: true
   ```

4. **Gradual Rollout**
   - Start with one gate (e.g., linting)
   - Add gates incrementally
   - Communicate with team

5. **Track Progress**
   ```bash
   # Compare hotspots over time
   diff baseline-hotspots.json current-hotspots.json
   ```

## Dependencies

### Required

- Python 3.12+
- git (for churn analysis)
- pytest (for testing)

### Optional

- **radon**: Complexity metrics (`pip install radon`)
- **xenon**: Complexity grading (`pip install xenon`)
- **libcst**: Safe code transformations (`pip install libcst`)
- **mutmut**: Mutation testing (`pip install mutmut`)

All optional dependencies can be installed via uv:

```bash
uv pip install radon xenon libcst mutmut
```

## Examples

### Example 1: Weekly Hotspot Review

```bash
# Generate weekly report
chiron tools refactor hotspots --limit 20 > reports/hotspots-$(date +%Y%m%d).txt

# Compare with last week
diff reports/hotspots-$(date -d '7 days ago' +%Y%m%d).txt \
     reports/hotspots-$(date +%Y%m%d).txt
```

### Example 2: Pre-Refactoring Workflow

```bash
# 1. Identify target
chiron tools refactor hotspots --limit 1

# 2. Analyze in detail
chiron tools refactor analyze --path src/chiron/target.py

# 3. Generate characterization tests
python dev-toolkit/refactoring/scripts/verify/snapshot_scaffold.py \
  --path src/chiron/target.py

# 4. Run tests to establish baseline
pytest tests/snapshots/test_characterization_target.py

# 5. Refactor (manually)
# ... make changes ...

# 6. Validate
pytest tests/snapshots/test_characterization_target.py
make lint test coverage
```

### Example 3: Large Refactoring

```bash
# 1. Make changes across many files
# ... refactor ...

# 2. See what changed
git diff --name-only main > changed-files.txt

# 3. Plan PR shards
python dev-toolkit/refactoring/scripts/rollout/shard_pr_list.py \
  --input changed-files.txt \
  --shard-size 30 \
  --output pr-plan.md

# 4. Create branches for each shard
# Follow checklist in pr-plan.md
```

## Troubleshooting

### Churn analysis fails

**Issue:** `git log` fails or returns empty results

**Solutions:**
- Ensure you're in a git repository
- Check if repository has commits in time window
- Verify git is in PATH

### Radon not found

**Issue:** `radon: command not found`

**Solution:**
```bash
uv pip install radon
# or
pip install radon
```

### LibCST parse errors

**Issue:** Syntax errors when running codemods

**Solution:**
- Ensure Python files are syntactically valid
- Check Python version compatibility
- Use `--dry-run` to preview changes first

### No hotspots found

**Issue:** Analysis returns empty results

**Possible causes:**
- Complexity threshold too high
- Churn threshold too high
- Time window too short

**Solution:**
```bash
# Lower thresholds
chiron tools refactor hotspots \
  --min-complexity 5 \
  --min-churn 1 \
  --since "24 months ago"
```

## Further Reading

- **PLAYBOOK.md**: Five-step safe refactoring workflow
- **PLAN.md**: Discovery and implementation planning
- **docs/REFACTORING_GUIDE.md**: User guide (project root)
- **REFACTORING_IMPLEMENTATION.md**: Technical details (project root)

## References

- **Your Code as a Crime Scene** (Adam Tornhill) - Hotspot methodology
- **Working Effectively with Legacy Code** (Michael Feathers) - Characterization tests
- **Refactoring** (Martin Fowler) - Refactoring patterns
- **LibCST Documentation**: https://libcst.readthedocs.io/

## Support

For issues or questions:

1. Check troubleshooting section above
2. Review PLAYBOOK.md for workflow guidance
3. Consult main documentation in `docs/REFACTORING_GUIDE.md`
4. Open an issue with `refactoring` label
