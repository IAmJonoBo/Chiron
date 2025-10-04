# CI Reproducibility Validation Guide

This guide provides instructions for implementing automated reproducibility validation in CI pipelines.

## Overview

Reproducible builds ensure that building the same source code produces identical binary artifacts. This guide shows how to validate reproducibility in GitHub Actions workflows.

---

## Why Reproducibility Matters

**Benefits**:
- Verify supply chain integrity
- Detect tampering or compromised build environments
- Enable independent verification
- Meet compliance requirements (SLSA Level 3+)

**Chiron Target**: ≥95% reproducibility rate

---

## 1. Basic Reproducibility Check

### Add to `.github/workflows/reproducibility.yml`

```yaml
name: Reproducibility Check

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    # Run daily at 2 AM UTC
    - cron: '0 2 * * *'

jobs:
  check-reproducibility:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.12']
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build
      
      - name: First build
        run: |
          python -m build --wheel --outdir dist1/
          ls -lah dist1/
      
      - name: Clean build artifacts
        run: |
          rm -rf build/ src/*.egg-info/
      
      - name: Second build
        run: |
          python -m build --wheel --outdir dist2/
          ls -lah dist2/
      
      - name: Compare builds
        run: |
          # Get wheel names
          WHEEL1=$(ls dist1/*.whl)
          WHEEL2=$(ls dist2/*.whl)
          
          # Compare checksums
          SHA1=$(sha256sum "$WHEEL1" | cut -d' ' -f1)
          SHA2=$(sha256sum "$WHEEL2" | cut -d' ' -f1)
          
          echo "First build:  $SHA1"
          echo "Second build: $SHA2"
          
          if [ "$SHA1" = "$SHA2" ]; then
            echo "✅ Builds are reproducible!"
            exit 0
          else
            echo "❌ Builds are NOT reproducible"
            
            # Show differences
            python -m zipfile -l "$WHEEL1" > files1.txt
            python -m zipfile -l "$WHEEL2" > files2.txt
            diff files1.txt files2.txt || true
            
            exit 1
          fi
      
      - name: Report results
        if: always()
        run: |
          if [ $? -eq 0 ]; then
            echo "reproducibility=true" >> $GITHUB_OUTPUT
          else
            echo "reproducibility=false" >> $GITHUB_OUTPUT
          fi
```

---

## 2. Advanced Reproducibility Check with Chiron

### Using Chiron's Built-in Reproducibility Checker

```yaml
name: Advanced Reproducibility Check

on:
  push:
    branches: [main]
  pull_request:

jobs:
  reproducibility:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install Chiron
        run: |
          pip install -e .
      
      - name: Build first wheel
        run: |
          python -m build --wheel --outdir build1/
      
      - name: Clean artifacts
        run: |
          rm -rf build/ src/*.egg-info/
      
      - name: Build second wheel
        run: |
          python -m build --wheel --outdir build2/
      
      - name: Check reproducibility with Chiron
        run: |
          python -c "
          from pathlib import Path
          from chiron.reproducibility import check_reproducibility
          
          wheel1 = next(Path('build1').glob('*.whl'))
          wheel2 = next(Path('build2').glob('*.whl'))
          
          report = check_reproducibility(wheel1, wheel2)
          
          print(f'Reproducible: {report.identical}')
          print(f'Wheel 1 SHA256: {report.wheel1.sha256}')
          print(f'Wheel 2 SHA256: {report.wheel2.sha256}')
          
          if report.differences:
              print('\\nDifferences:')
              for diff in report.differences:
                  print(f'  - {diff}')
          
          exit(0 if report.identical else 1)
          "
      
      - name: Upload report
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: reproducibility-report
          path: |
            build1/
            build2/
```

---

## 3. Multi-Platform Reproducibility

### Check Across Different Platforms

```yaml
name: Multi-Platform Reproducibility

on:
  workflow_dispatch:
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  build-matrix:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ['3.12']
    
    runs-on: ${{ matrix.os }}
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Build wheels
        run: |
          pip install cibuildwheel
          python -m cibuildwheel --output-dir wheelhouse
        env:
          CIBUILDWHEEL_BUILD: cp312-*
      
      - name: Upload wheels
        uses: actions/upload-artifact@v4
        with:
          name: wheels-${{ matrix.os }}
          path: wheelhouse/*.whl
  
  compare:
    needs: build-matrix
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Download all wheels
        uses: actions/download-artifact@v4
        with:
          path: wheels/
      
      - name: Compare builds
        run: |
          # For each wheel type, compare across platforms
          for wheel in wheels/wheels-ubuntu-latest/*.whl; do
            basename=$(basename "$wheel")
            
            echo "Comparing $basename across platforms..."
            
            # Get checksums
            ubuntu_sum=$(sha256sum "wheels/wheels-ubuntu-latest/$basename" | cut -d' ' -f1)
            
            # Note: Cross-platform reproducibility is challenging
            # This is mainly for documentation/analysis
            echo "Ubuntu:  $ubuntu_sum"
          done
```

---

## 4. Integrate with wheels.yml

### Add Reproducibility Check to Existing Workflow

```yaml
# In .github/workflows/wheels.yml

jobs:
  # ... existing build job ...
  
  verify-reproducibility:
    needs: build
    runs-on: ubuntu-latest
    if: github.event_name == 'push' || github.event_name == 'schedule'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Download artifacts
        uses: actions/download-artifact@v4
        with:
          name: wheels
          path: original-wheels/
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Rebuild wheels
        run: |
          pip install cibuildwheel
          python -m cibuildwheel --output-dir rebuilt-wheels
        env:
          CIBUILDWHEEL_BUILD: cp312-manylinux_x86_64
      
      - name: Compare wheels
        run: |
          # Compare pure Python wheels (these should be identical)
          for original in original-wheels/*-py3-none-any.whl; do
            if [ -f "$original" ]; then
              basename=$(basename "$original")
              rebuilt="rebuilt-wheels/$basename"
              
              if [ -f "$rebuilt" ]; then
                original_sum=$(sha256sum "$original" | cut -d' ' -f1)
                rebuilt_sum=$(sha256sum "$rebuilt" | cut -d' ' -f1)
                
                if [ "$original_sum" = "$rebuilt_sum" ]; then
                  echo "✅ $basename is reproducible"
                else
                  echo "❌ $basename is NOT reproducible"
                  echo "   Original: $original_sum"
                  echo "   Rebuilt:  $rebuilt_sum"
                fi
              fi
            fi
          done
      
      - name: Create reproducibility report
        run: |
          cat > reproducibility-report.md << 'EOF'
          # Reproducibility Report
          
          ## Summary
          
          - Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
          - Commit: ${{ github.sha }}
          - Branch: ${{ github.ref_name }}
          
          ## Results
          
          See job logs for detailed comparison.
          EOF
          
          cat reproducibility-report.md >> $GITHUB_STEP_SUMMARY
```

---

## 5. Reproducibility Metrics

### Track Reproducibility Over Time

Create `.github/workflows/reproducibility-metrics.yml`:

```yaml
name: Reproducibility Metrics

on:
  schedule:
    - cron: '0 3 * * *'  # Daily at 3 AM UTC

jobs:
  collect-metrics:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Build and compare
        id: check
        run: |
          # Build twice
          python -m pip install build
          python -m build --wheel --outdir dist1/
          rm -rf build/ src/*.egg-info/
          python -m build --wheel --outdir dist2/
          
          # Compare
          WHEEL1=$(ls dist1/*.whl)
          WHEEL2=$(ls dist2/*.whl)
          SHA1=$(sha256sum "$WHEEL1" | cut -d' ' -f1)
          SHA2=$(sha256sum "$WHEEL2" | cut -d' ' -f1)
          
          if [ "$SHA1" = "$SHA2" ]; then
            echo "reproducible=1" >> $GITHUB_OUTPUT
          else
            echo "reproducible=0" >> $GITHUB_OUTPUT
          fi
      
      - name: Push metrics
        run: |
          # Push to Prometheus Pushgateway or similar
          cat << EOF | curl --data-binary @- http://pushgateway:9091/metrics/job/chiron
          # TYPE chiron_reproducibility_check gauge
          # HELP chiron_reproducibility_check Result of reproducibility check (1=reproducible, 0=not)
          chiron_reproducibility_check{commit="${{ github.sha }}"} ${{ steps.check.outputs.reproducible }}
          EOF
```

---

## 6. Detailed Comparison Script

### Python Script for Detailed Analysis

Create `scripts/compare_wheels.py`:

```python
"""Compare two wheel builds for reproducibility."""

import hashlib
import sys
import zipfile
from pathlib import Path


def compare_wheels(wheel1_path: Path, wheel2_path: Path) -> dict:
    """Compare two wheels and return detailed differences."""
    
    results = {
        "identical": False,
        "sha256_match": False,
        "size_match": False,
        "file_list_match": False,
        "content_differences": []
    }
    
    # Compare sizes
    size1 = wheel1_path.stat().st_size
    size2 = wheel2_path.stat().st_size
    results["size_match"] = (size1 == size2)
    
    # Compare checksums
    with open(wheel1_path, "rb") as f:
        sha1 = hashlib.sha256(f.read()).hexdigest()
    with open(wheel2_path, "rb") as f:
        sha2 = hashlib.sha256(f.read()).hexdigest()
    
    results["sha256_match"] = (sha1 == sha2)
    
    if results["sha256_match"]:
        results["identical"] = True
        return results
    
    # Compare contents
    with zipfile.ZipFile(wheel1_path) as zf1, zipfile.ZipFile(wheel2_path) as zf2:
        files1 = set(zf1.namelist())
        files2 = set(zf2.namelist())
        
        results["file_list_match"] = (files1 == files2)
        
        # Find files only in one wheel
        only_in_1 = files1 - files2
        only_in_2 = files2 - files1
        
        if only_in_1:
            results["content_differences"].append(
                f"Files only in wheel1: {list(only_in_1)}"
            )
        if only_in_2:
            results["content_differences"].append(
                f"Files only in wheel2: {list(only_in_2)}"
            )
        
        # Compare common files
        common_files = files1 & files2
        for filename in common_files:
            if filename.endswith(".pyc") or "RECORD" in filename:
                continue  # Skip bytecode and RECORD files
            
            content1 = zf1.read(filename)
            content2 = zf2.read(filename)
            
            if content1 != content2:
                results["content_differences"].append(
                    f"Different content: {filename}"
                )
    
    return results


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python compare_wheels.py <wheel1> <wheel2>")
        sys.exit(1)
    
    wheel1 = Path(sys.argv[1])
    wheel2 = Path(sys.argv[2])
    
    if not wheel1.exists() or not wheel2.exists():
        print("Error: One or both wheel files not found")
        sys.exit(1)
    
    results = compare_wheels(wheel1, wheel2)
    
    print(f"\n{'='*60}")
    print("Reproducibility Check Results")
    print(f"{'='*60}\n")
    
    print(f"Wheel 1: {wheel1.name}")
    print(f"Wheel 2: {wheel2.name}\n")
    
    print(f"✅ Identical:         {results['identical']}")
    print(f"{'✅' if results['sha256_match'] else '❌'} SHA256 Match:     {results['sha256_match']}")
    print(f"{'✅' if results['size_match'] else '❌'} Size Match:       {results['size_match']}")
    print(f"{'✅' if results['file_list_match'] else '❌'} File List Match:  {results['file_list_match']}")
    
    if results['content_differences']:
        print(f"\n⚠️  Content Differences:")
        for diff in results['content_differences'][:10]:
            print(f"  - {diff}")
        if len(results['content_differences']) > 10:
            print(f"  ... and {len(results['content_differences']) - 10} more")
    
    print(f"\n{'='*60}\n")
    
    sys.exit(0 if results['identical'] else 1)
```

Use in workflow:

```yaml
- name: Detailed comparison
  run: |
    python scripts/compare_wheels.py \
      dist1/*.whl \
      dist2/*.whl
```

---

## 7. Troubleshooting Non-Reproducible Builds

### Common Causes

1. **Timestamps**: Build/modification times embedded in artifacts
2. **Build paths**: Absolute paths in bytecode or metadata
3. **Random ordering**: Non-deterministic file ordering
4. **Environment differences**: Different Python versions, OS, etc.
5. **Dependencies**: Different dependency versions

### Solutions

**Set SOURCE_DATE_EPOCH**:
```bash
export SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)
python -m build
```

**Use consistent Python version**:
```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.12.3'  # Exact version
```

**Sort file listings**:
```python
# In setup.py or build script
import os
os.environ['LC_ALL'] = 'C'
```

---

## 8. Best Practices

### Do's

- ✅ Use exact dependency versions
- ✅ Set SOURCE_DATE_EPOCH
- ✅ Use deterministic tools
- ✅ Document known non-reproducible elements
- ✅ Track reproducibility metrics over time

### Don'ts

- ❌ Don't embed timestamps
- ❌ Don't use randomness in build
- ❌ Don't depend on build environment
- ❌ Don't ignore reproducibility failures
- ❌ Don't assume all builds are reproducible

---

## 9. Reporting

### Generate Reproducibility Report

```yaml
- name: Generate report
  run: |
    cat > reproducibility-report.json << EOF
    {
      "commit": "${{ github.sha }}",
      "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
      "reproducible": ${{ steps.check.outputs.reproducible }},
      "platform": "${{ runner.os }}",
      "python_version": "${{ matrix.python-version }}"
    }
    EOF

- name: Upload report
  uses: actions/upload-artifact@v4
  with:
    name: reproducibility-report
    path: reproducibility-report.json
```

---

## 10. Next Steps

1. **Implement basic check**: Start with simple SHA256 comparison
2. **Add to CI**: Integrate into wheels.yml workflow
3. **Monitor metrics**: Track reproducibility rate over time
4. **Investigate failures**: When builds aren't reproducible, find why
5. **Document findings**: Share learnings with team

---

## References

- [Reproducible Builds Project](https://reproducible-builds.org/)
- [SLSA Framework](https://slsa.dev/)
- [SOURCE_DATE_EPOCH spec](https://reproducible-builds.org/specs/source-date-epoch/)
- [Python Wheel Reproducibility](https://github.com/pypa/wheel/pull/383)

---

## Conclusion

Implementing reproducibility validation in CI ensures build integrity and enables supply chain verification. Start with basic checks and iterate based on your findings.

For production deployment, aim for ≥95% reproducibility rate as specified in `CHIRON_UPGRADE_PLAN.md`.
