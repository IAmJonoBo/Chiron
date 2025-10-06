---
title: "Refactoring Tools - Intelligent Code Modernization"
diataxis: how_to
summary: Use hotspot analysis and refactoring insights to prioritize code improvements and manage large-scale changes safely.
---

# Refactoring Tools - Intelligent Code Modernization

This guide explains how to use Chiron's refactoring tools to identify and prioritize code improvements based on empirical evidence.

## Overview

Chiron provides two complementary refactoring analysis tools:

1. **`refactor analyze`** - Static analysis of code quality issues
2. **`refactor hotspots`** - Hotspot targeting combining git churn with complexity metrics

These tools implement the methodology outlined in Next Steps.md: prioritize refactoring efforts on code that is both complex and frequently changed, where improvements deliver maximum value.

## Quick Start

### Analyze Code Quality Issues

```bash
# Analyze the codebase for refactor opportunities
chiron tools refactor analyze

# Analyze specific paths
chiron tools refactor analyze --path src/chiron/core.py

# Output as JSON for tooling integration
chiron tools refactor analyze --json > refactor-report.json
```

### Identify Refactoring Hotspots

```bash
# Find top hotspots (complexity × churn)
chiron tools refactor hotspots

# Analyze changes from the past 6 months
chiron tools refactor hotspots --since "6 months ago"

# Show top 30 hotspots with custom thresholds
chiron tools refactor hotspots --limit 30 --min-complexity 20 --min-churn 3

# Output as JSON
chiron tools refactor hotspots --json > hotspots.json
```

## Refactor Analyze

The `refactor analyze` command performs static code analysis to identify opportunities for improvement.

### Detection Categories

1. **Function Length** - Functions exceeding length thresholds
2. **Class Size** - Classes with too many methods
3. **Cyclomatic Complexity** - Complex control flow
4. **Long Parameter Lists** - Functions with too many parameters
5. **Missing Docstrings** - Public functions without documentation
6. **Low Coverage** - Code with inadequate test coverage
7. **TODO Comments** - Marked areas for improvement

### Configuration Options

```bash
chiron tools refactor analyze \
  --max-function-length 80 \
  --max-class-methods 15 \
  --max-cyclomatic-complexity 12 \
  --max-parameters 5 \
  --min-docstring-length 30 \
  --coverage-threshold 90.0 \
  --coverage-xml coverage.xml
```

### Output Format

Text output is color-coded by severity:
- **CRITICAL** (red) - Immediate attention needed
- **WARNING** (yellow) - Should be addressed
- **INFO** (cyan) - Nice to have improvements

JSON output provides structured data for automation:

```json
{
  "generated_at": "2025-10-06T12:30:00+00:00",
  "opportunities": [
    {
      "path": "src/chiron/example.py",
      "line": 42,
      "symbol": "complex_function",
      "kind": "cyclomatic_complexity",
      "severity": "critical",
      "message": "Cyclomatic complexity 15 exceeds threshold 10",
      "metric": 15,
      "threshold": 10
    }
  ]
}
```

## Hotspot Analysis

The `refactor hotspots` command implements the hotspot targeting strategy: identify files that are both complex and frequently changed.

### Why Hotspots?

From Next Steps.md:
> "Where to start": Hotspots = complexity × churn. Prioritise files/methods that are both complex and frequently changed; that's where refactors repay fastest.

### How It Works

1. **Git Churn Analysis** - Counts file changes over a time period
2. **Complexity Scoring** - Measures code complexity based on:
   - Function/method lengths (beyond 10 lines)
   - Class sizes (beyond 5 methods)
3. **Hotspot Score** - Multiplies complexity by churn count
4. **Ranking** - Sorts files by hotspot score (highest first)

### Interpreting Results

```
Top 10 Hotspots (Complexity × Churn)

Analyzed files changed since 6 months ago with complexity ≥ 10 and churn ≥ 2

 1. src/chiron/typer_cli.py (complexity=1949, churn=45, hotspot=87705)
 2. src/chiron/dev_toolbox.py (complexity=1189, churn=38, hotspot=45182)
 3. src/chiron/deps/guard.py (complexity=848, churn=28, hotspot=23744)
```

#### Color Coding

- **Red** - Hotspot score > 1000 (high priority)
- **Yellow** - Hotspot score > 500 (medium priority)
- **Cyan** - Hotspot score ≤ 500 (low priority)

### Best Practices

1. **Start Small** - Focus on top 5-10 files initially
2. **Add Safety Nets** - Write characterization tests before refactoring
3. **Incremental Changes** - Make small, reviewable improvements
4. **Measure Impact** - Re-run analysis after changes to track progress

### Threshold Tuning

Adjust thresholds based on your codebase:

```bash
# Strict thresholds for mature codebases
chiron tools refactor hotspots --min-complexity 50 --min-churn 5

# Lenient thresholds for new projects
chiron tools refactor hotspots --min-complexity 5 --min-churn 1

# Custom time window
chiron tools refactor hotspots --since "3 months ago"
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Refactor Analysis

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly
  workflow_dispatch:

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for churn analysis

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install Chiron
        run: pip install chiron

      - name: Run Hotspot Analysis
        run: |
          chiron tools refactor hotspots --json > hotspots.json
          chiron tools refactor analyze --json > opportunities.json

      - name: Upload Reports
        uses: actions/upload-artifact@v4
        with:
          name: refactor-reports
          path: |
            hotspots.json
            opportunities.json
```

### Quality Gate Integration

Add refactoring checks to your quality suite:

```bash
# Run analysis as part of local quality gates
chiron tools qa --profile full
chiron tools refactor analyze

# Check for critical issues
chiron tools refactor analyze --json | jq '.opportunities[] | select(.severity == "critical")'
```

## Advanced Workflows

### Refactoring Roadmap

1. **Baseline** - Capture current state
   ```bash
   chiron tools refactor hotspots --json > baseline-hotspots.json
   chiron tools refactor analyze --json > baseline-opportunities.json
   ```

2. **Prioritize** - Select top candidates from hotspot analysis

3. **Safety Net** - Add characterization tests for target files
   ```bash
   # Use existing test infrastructure
   pytest tests/test_target_module.py -v
   ```

4. **Refactor** - Make incremental improvements
   - Extract methods from long functions
   - Break up large classes
   - Simplify complex control flow
   - Add documentation

5. **Validate** - Ensure no behavioral changes
   ```bash
   # Run full test suite
   chiron tools qa --profile full
   
   # Re-analyze to measure improvement
   chiron tools refactor hotspots
   ```

6. **Track Progress** - Compare before/after metrics

### Mutation Testing (Future)

For critical hotspots, consider mutation testing to validate test quality:

```bash
# Python: mutmut or similar tools
# This validates that tests actually catch bugs
mutmut run --paths-to-mutate src/chiron/hotspot_module.py
```

## Methodology References

This implementation follows industry best practices:

- **ISO/IEC 25010** - Product quality model
- **ISO/IEC 5055** - Structural quality weaknesses
- **Google's LSC practices** - Large-scale changes
- **Cognitive Complexity** - Readability metrics
- **Hotspot Analysis** - From "Your Code as a Crime Scene" by Adam Tornhill

## See Also

- [Quality Gates](QUALITY_GATES.md) - Enforce standards in CI/CD
- [Next Steps.md](../Next Steps.md) - Full refactoring methodology
- [Testing Guide](tutorials/first-run.md) - Writing characterization tests
