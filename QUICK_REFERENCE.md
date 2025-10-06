# Quick Reference: New Tooling Features

This quick reference guide helps you use the newly implemented tooling features.

## 📝 Documentation Linting (Vale)

### Check Documentation Style
```bash
# Install Vale styles (first time)
vale sync

# Lint all documentation
vale docs/ *.md

# Lint specific file
vale README.md
```

### Pre-commit Integration
Vale runs automatically on modified documentation files:
```bash
git add docs/MYFILE.md
git commit -m "Update docs"  # Vale runs automatically
```

---

## 🔍 Security Scanning

### CodeQL Analysis
Runs automatically on:
- Push to main/develop
- Pull requests
- Weekly schedule (Mondays)

View results in: **GitHub → Security → Code scanning alerts**

### Trivy Container Scanning
Runs automatically on:
- Push/PR (filesystem scan)
- Push to main/develop (container scan)
- Weekly schedule (Sundays)

View results in: **GitHub → Security → Code scanning alerts**

---

## 📊 Coverage on Diff

### Check Coverage on Changed Lines
```bash
# Run tests with coverage
make test

# Check diff coverage (requires coverage.xml)
make diff-cover
```

### CI Integration
Diff-cover runs automatically on all pull requests and comments with results.

**Threshold**: 80% coverage required on changed lines

---

## 🧬 Mutation Testing

### Run Mutation Tests
```bash
# Run mutation testing (takes time!)
make mutmut-run

# View results summary
make mutmut-results

# Generate HTML report
make mutmut-html
open html/index.html  # View in browser
```

### What It Tests
Mutation testing validates your test suite by:
1. Introducing small code changes (mutations)
2. Running tests to see if they catch the mutations
3. Reporting which mutations survived (untested code paths)

---

## 🔐 Signature Verification

### Verify Signed Artifacts
Signatures are verified automatically after wheel builds complete.

View verification reports in: **GitHub → Actions → Sigstore Verification**

### Manual Verification
```bash
# Verify a wheel signature
cosign verify-blob \
  --bundle my-wheel.whl.sigstore.json \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  --certificate-identity-regexp "^https://github.com/IAmJonoBo/Chiron" \
  my-wheel.whl
```

---

## 🔄 Reproducibility Validation

### Check Build Reproducibility
Runs automatically on:
- Push to main/develop
- Pull requests
- Weekly schedule (Mondays)

### View Results
- Check **GitHub → Actions → Reproducibility Validation**
- Download diffoscope HTML reports from artifacts
- PR comments show reproducibility status

---

## 📊 Observability Sandbox

### Start the Stack
```bash
# Start all observability services
docker-compose -f docker-compose.observability.yml up -d

# Check status
docker-compose -f docker-compose.observability.yml ps
```

### Access UIs
- **Grafana**: http://localhost:3000 (admin/admin)
- **Jaeger**: http://localhost:16686
- **Prometheus**: http://localhost:9090
- **Chiron Service**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### Generate Test Data
```bash
# Send requests to generate traces
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/status
```

### View Telemetry
1. **Traces**: Open Jaeger → Select "chiron" → Find Traces
2. **Metrics**: Open Grafana → Explore → Prometheus → Query
3. **Logs**: Open Grafana → Explore → Loki → Query

### Stop the Stack
```bash
docker-compose -f docker-compose.observability.yml down

# Remove volumes too
docker-compose -f docker-compose.observability.yml down -v
```

---

## 🔥 Chaos Testing

### Prerequisites
```bash
# Install Chaos Toolkit
uv pip install chaostoolkit chaostoolkit-http requests
```

### Run Experiments

#### Service Availability Test
```bash
# Start services
docker-compose -f docker-compose.observability.yml up -d

# Run experiment
chaos run chaos/experiments/service-availability.json

# View results in journal.json
cat chaos/journal.json | jq .
```

### Monitor During Chaos
While experiments run, monitor in:
- Grafana dashboards
- Jaeger traces
- Prometheus metrics

### Create New Experiments
1. Copy existing experiment from `chaos/experiments/`
2. Modify steady-state hypothesis
3. Add chaos actions
4. Test locally
5. Document in `chaos/README.md`

---

## 🛠️ Makefile Targets

### New Targets
```bash
# Coverage
make diff-cover          # Check coverage on changed lines

# Mutation testing
make mutmut-run          # Run mutation tests
make mutmut-results      # Show mutation results
make mutmut-html         # Generate HTML report

# Existing targets
make test                # Run tests
make lint                # Run linters
make security            # Run security scans
make docs                # Start documentation server
```

---

## 🔧 Pre-commit Hooks

### Available Hooks
The following hooks run automatically on `git commit`:
- Vale (documentation style)
- Ruff (code formatting)
- Deptry (dependency checks)
- OPA/Conftest (policy checks)
- MyPy (type checking on pre-push)
- Pytest (tests on pre-push)

### Skip Hooks (When Needed)
```bash
# Skip all hooks
git commit --no-verify

# Skip specific hook
SKIP=vale git commit -m "message"
```

---

## 📋 CI/CD Workflows

### New Workflows
1. **CodeQL Analysis** (`.github/workflows/codeql.yml`)
   - Runs: Push, PR, Weekly
   - Purpose: Security analysis

2. **Coverage on Diff** (`.github/workflows/diff-cover.yml`)
   - Runs: Pull requests
   - Purpose: Ensure 80%+ coverage on changes

3. **Documentation Linting** (`.github/workflows/docs-lint.yml`)
   - Runs: Push/PR touching docs
   - Purpose: Style consistency

4. **Trivy Scanning** (`.github/workflows/trivy.yml`)
   - Runs: Push, PR, Weekly
   - Purpose: Container security

5. **Sigstore Verification** (`.github/workflows/sigstore-verify.yml`)
   - Runs: After wheel/release builds
   - Purpose: Verify signatures

6. **Reproducibility** (`.github/workflows/reproducibility.yml`)
   - Runs: Push, PR, Weekly
   - Purpose: Validate reproducible builds

---

## 📚 Documentation

### Where to Learn More
- **Observability**: `docs/OBSERVABILITY_SANDBOX.md`
- **Chaos Testing**: `chaos/README.md`
- **Tooling Status**: `docs/TOOLING_IMPLEMENTATION_STATUS.md`
- **Implementation Summary**: `COMPREHENSIVE_IMPLEMENTATION_SUMMARY.md`

---

## 🆘 Troubleshooting

### Vale Not Finding Styles
```bash
# Sync Vale styles
vale sync

# If still having issues, check .vale.ini
cat .vale.ini
```

### Observability Stack Issues
```bash
# Check logs
docker-compose -f docker-compose.observability.yml logs -f

# Restart specific service
docker-compose -f docker-compose.observability.yml restart chiron-service

# Reset everything
docker-compose -f docker-compose.observability.yml down -v
docker-compose -f docker-compose.observability.yml up -d
```

### Chaos Experiments Failing
```bash
# Ensure services are running
docker-compose -f docker-compose.observability.yml ps

# Check service health
curl http://localhost:8000/health

# Review experiment JSON syntax
cat chaos/experiments/service-availability.json | jq .
```

### Mutation Testing Slow
```bash
# Run on specific module
mutmut run --paths-to-mutate=src/chiron/specific_module.py

# Or limit number of mutations
mutmut run --test-time-base=1.0
```

---

*Quick Reference Version: 1.0.0*
*Last Updated: 2025-10-06*
