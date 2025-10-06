# Refactoring Playbook: Five-Step Safe Refactoring Loop

This playbook describes the recommended workflow for safe, incremental refactoring using Chiron's refactoring toolkit.

## Overview

The five-step loop ensures that refactorings are:
- **Evidence-based:** Target hotspots with highest ROI
- **Safe:** Protected by characterization tests
- **Incremental:** Small, reviewable changes
- **Validated:** Quality gates verify no regressions
- **Manageable:** Large changes split into shards

## The Five-Step Loop

```
┌─────────────────────────────────────────────────────┐
│  1. Pick Hotspots  →  2. Add Tests  →  3. Refactor │
│         ↑                                    ↓      │
│         └────  5. Shard & Merge  ←  4. Validate  ──┘
└─────────────────────────────────────────────────────┘
```

---

## Step 1: Pick Hotspots 🎯

**Goal:** Identify code with the highest refactoring ROI

### Actions

```bash
# Find top 10 refactoring priorities
chiron tools refactor hotspots --limit 10

# Get detailed analysis of specific file
chiron tools refactor analyze --path src/chiron/target_module.py

# Export for CI/CD tracking
chiron tools refactor hotspots --json > hotspots.json
```

### Criteria

Hotspots are ranked by: **Complexity × Churn**

- **High complexity:** Hard to understand and maintain
- **High churn:** Frequently changed (bug-prone)
- **Combined:** Maximum pain point and ROI

### Decision Points

- Focus on files with hotspot score > 1000 (critical)
- Consider files with score > 500 (warning)
- Skip files with score < 500 unless specific needs

### Output Example

```
Code Hotspots (Complexity × Churn)

 1. src/chiron/typer_cli.py (complexity=1949, churn=2, hotspot=3898)
 2. src/chiron/dev_toolbox.py (complexity=1189, churn=2, hotspot=2378)
```

**Decision:** Choose `typer_cli.py` as first refactoring target

---

## Step 2: Add Characterization Tests 🛡️

**Goal:** Lock in current behavior before refactoring

### Actions

```bash
# Generate snapshot test scaffolding
chiron tools refactor verify --path src/chiron/target_module.py --output tests/snapshots/

# Or manually create characterization tests
# See tests/test_*.py for patterns
```

### Characterization Test Patterns

#### Golden File Testing
```python
def test_module_behavior_snapshot():
    """Lock in current behavior before refactoring."""
    input_data = load_test_input()
    actual = target_function(input_data)
    
    # First run: generates golden file
    # Subsequent runs: compares against golden
    assert_matches_snapshot(actual, "target_function_output.json")
```

#### Property-Based Testing
```python
from hypothesis import given, strategies as st

@given(st.text(), st.integers())
def test_function_properties(text_input, int_input):
    """Verify properties hold for all inputs."""
    result = target_function(text_input, int_input)
    
    # Properties that must always be true
    assert result is not None
    assert len(result) >= 0
```

#### Regression Testing
```python
def test_known_edge_cases():
    """Capture specific known behaviors."""
    # Known good behavior
    assert target_function("") == default_value
    assert target_function(None) == error_response
    
    # Known edge cases
    assert target_function(large_input) == expected_output
```

### Integration with Existing Tests

Chiron already has comprehensive test infrastructure:

```bash
# Run existing tests to establish baseline
uv run pytest tests/test_target_module.py -v

# Add new characterization tests
# Follow patterns in tests/test_dev_toolbox.py
```

### Coverage Check

```bash
# Ensure target code is covered
uv run pytest --cov=src/chiron/target_module tests/test_target_module.py
```

**Threshold:** Aim for >80% coverage of code to be refactored

---

## Step 3: Apply Small Codemod 🔧

**Goal:** Make incremental, safe transformations

### Manual Refactoring

Most refactorings are manual but guided:

1. **Extract Method:** Break long functions into smaller ones
2. **Simplify Conditionals:** Reduce cyclomatic complexity
3. **Rename for Clarity:** Improve readability
4. **Remove Duplication:** DRY principle
5. **Add Documentation:** Explain complex logic

### Automated Codemods (Optional)

For repetitive transformations:

```bash
# Run LibCST codemod (dry-run by default)
chiron tools refactor codemod \
  --path src/chiron/target_module.py \
  --transform rename_function \
  --old-name old_func \
  --new-name new_func \
  --dry-run

# Apply after review
chiron tools refactor codemod ... --no-dry-run
```

### Available Transformations

See `dev-toolkit/refactoring/scripts/codemods/py/` for examples:
- `rename_function.py` - Safe function/method renaming
- (More transformations to be added)

### Best Practices

- **One refactoring at a time:** Don't mix concerns
- **Keep diffs small:** <200 lines changed
- **Preserve behavior:** No functional changes
- **Maintain formatting:** Use ruff for consistency
- **Update tests:** Adjust tests for renamed symbols only

---

## Step 4: Run CI Gates (Advisory) ✓

**Goal:** Verify no regressions

### Local Validation

```bash
# Full quality suite
chiron tools qa --profile full

# Specific checks
make lint          # Ruff formatting and linting
make mypy          # Type checking
make test          # Full test suite
make coverage      # Coverage report
make security      # Security scans
```

### CI Pipeline Validation

The CI gates are initially **advisory** (warn-only):

```yaml
# From dev-toolkit/refactoring/ci/workflow.partial.yml
- name: Refactor Analysis
  run: |
    chiron tools refactor hotspots --json > hotspots.json
    chiron tools refactor analyze --json > opportunities.json
  continue-on-error: true  # Advisory only
```

### Quality Thresholds

Must maintain:
- ✅ All tests passing
- ✅ Coverage ≥ 80%
- ✅ No new linting errors
- ✅ No new type errors
- ✅ No new security findings
- ⚠️ Hotspot score improved or maintained

### Mutation Testing (Weekly)

Optional but recommended:

```bash
# Run mutation tests on changed code
make mutmut-run

# Review results
make mutmut-results

# Generate HTML report
make mutmut-html
```

---

## Step 5: Shard and Merge 📦

**Goal:** Manage large changes with small, reviewable PRs

### Sharding Strategy

For refactorings affecting many files:

```bash
# List files needing refactoring
chiron tools refactor shard \
  --input changed_files.txt \
  --shard-size 50 \
  --output pr_shards.md
```

### Output Example

```markdown
## PR Shards for Refactoring

### Shard 1 (50 files)
- [ ] src/chiron/module_a.py
- [ ] src/chiron/module_b.py
...

### Shard 2 (50 files)
- [ ] src/chiron/module_x.py
...
```

### PR Guidelines

**Each PR should:**
1. Address one logical refactoring
2. Include characterization tests
3. Pass all quality gates
4. Have clear commit messages
5. Include before/after metrics

**PR Description Template:**

```markdown
## Refactoring: [Brief Description]

### Hotspot Analysis
- File: `src/chiron/target.py`
- Before: complexity=150, churn=5, hotspot=750
- After: complexity=80, churn=5, hotspot=400
- Improvement: 47% reduction in hotspot score

### Changes Made
- Extracted 3 long functions
- Reduced cyclomatic complexity from 15 to 8
- Added documentation to complex sections

### Validation
- ✅ All tests passing (765 tests)
- ✅ Coverage maintained at 84%
- ✅ No new linting/type errors
- ✅ Characterization tests added
- ✅ Manual smoke testing complete

### Related
- Hotspot analysis: [link to artifact]
- Closes #[issue number]
```

### Merge Strategy

1. **Green main required:** Ensure main branch is stable
2. **One shard at a time:** Don't stack PRs
3. **Monitor metrics:** Track improvement over time
4. **Communicate:** Keep team informed

---

## Anti-Patterns to Avoid ⚠️

### 1. Mass Reformatting
**Don't:** Reformat entire codebase in one PR
**Do:** Let pre-commit hooks handle formatting incrementally

### 2. Mixing Refactoring with Features
**Don't:** Add new functionality while refactoring
**Do:** Separate refactoring PRs from feature PRs

### 3. Skipping Tests
**Don't:** Refactor without test coverage
**Do:** Add characterization tests first

### 4. Large Diffs
**Don't:** Change 50 files in one PR
**Do:** Use sharding to keep PRs reviewable

### 5. Lowering Standards
**Don't:** Reduce coverage or quality thresholds
**Do:** Maintain or improve quality metrics

---

## Iteration and Continuous Improvement

After completing one cycle:

```bash
# Re-run hotspot analysis
chiron tools refactor hotspots --limit 10

# Compare with baseline
diff baseline-hotspots.json current-hotspots.json

# Track progress
echo "Hotspots resolved: X"
echo "Average complexity reduction: Y%"
```

### Success Metrics

- **Hotspot count:** Decreasing over time
- **Average complexity:** Trending down
- **Test coverage:** Maintained or improved
- **Bug rate:** Reduced in refactored code
- **Development velocity:** Improved in affected areas

---

## Example Workflow

**Week 1: Discovery**
```bash
chiron tools refactor hotspots > week1-hotspots.txt
# Choose top 3 files for refactoring sprint
```

**Week 2: File 1 - Prepare & Refactor**
```bash
# Add characterization tests
pytest tests/test_target1.py --cov

# Refactor in small commits
git commit -m "refactor: extract long method from target1"
git commit -m "refactor: simplify conditionals in target1"

# Validate
make lint test coverage
```

**Week 3: File 1 - PR & Merge**
```bash
# Open PR with before/after metrics
# Review, approve, merge

# Re-run analysis
chiron tools refactor analyze --path src/chiron/target1.py
```

**Week 4: Files 2-3 - Repeat**

---

## Tool Reference

### CLI Commands

```bash
# Analysis
chiron tools refactor hotspots [--limit N] [--json]
chiron tools refactor analyze --path FILE [--json]

# Transformation
chiron tools refactor codemod --transform NAME --path FILE [--dry-run]

# Verification
chiron tools refactor verify --path FILE [--output DIR]

# Planning
chiron tools refactor shard --input FILES --shard-size N
```

### Makefile Targets

```bash
make refactor-analyse    # Run hotspot analysis
make refactor-verify     # Generate verification scaffolds
make refactor-codemod    # Run codemods
```

### Scripts

```bash
# Standalone scripts (CI/CD)
bash dev-toolkit/refactoring/scripts/analyse/git_churn.sh
python dev-toolkit/refactoring/scripts/analyse/hotspots_py.py src/chiron
```

---

## Further Reading

- `docs/REFACTORING_GUIDE.md` - User guide and configuration
- `REFACTORING_IMPLEMENTATION.md` - Technical details
- `dev-toolkit/refactoring/docs/README.md` - Toolkit overview
- `dev-toolkit/refactoring/docs/PLAN.md` - Discovery and planning

## References

- **Working Effectively with Legacy Code** (Michael Feathers)
- **Refactoring** (Martin Fowler)
- **Your Code as a Crime Scene** (Adam Tornhill) - Hotspot methodology
- ISO/IEC 25010:2011 - Software quality model
