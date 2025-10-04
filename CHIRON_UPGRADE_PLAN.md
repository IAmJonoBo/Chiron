# Frontier-grade Dependency & Wheelhouse System

Gap analysis, red team, and upgrades

## Executive Summary

Your current goal—intelligent, policy-driven dependency management plus production-ready wheelhouses (built remotely with cibuildwheel) that can serve air-gapped runners—demands:

1. Hermetic, reproducible builds
2. A private index/offline bundle you control
3. End-to-end provenance (SLSA), SBOMs, and signatures
4. Cross-OS/arch wheels with proper vendoring (auditwheel/delocate/delvewheel)
5. Integration points so any system can consume your artefacts with zero Internet

---

## Gaps (typical in "messy" projects)

- **Determinism**: No universal constraints/lock (hash-pinned), mixed build backends, non-hermetic CI
- **Coverage**: Wheels missing for one or more OS/arch; shared libs not vendored; ABI drift (glibc/macOS)
- **Distribution**: No private PyPI mirror or offline "wheelhouse bundle"; air-gapped installs ad-hoc
- **Security**: No SBOM, OSV scanning, signatures, or SLSA provenance; dependency-confusion exposure
- **Governance**: No policy engine (allow/deny/upgrade windows), no compatibility matrix, no expiry/rotation for caches
- **Observability**: Build provenance, test coverage on critical paths, and supply-chain attestations are absent

## Red Team (what bites first)

- Dependency confusion / typosquatting via default index
- ABI breakage on target hosts (manylinux/macOS/Windows) due to unvendored native libs
- Cache/artefact poisoning in CI or shared runners
- Non-reproducible wheels (timestamps, env drift, non-pinned compilers)
- Transitively vulnerable deps with no OSV gate; silent regressions
- Key/secret sprawl for signing; unverifiable provenance in air-gapped nets
- Incompatible air-gap installs (wrong tags, missing extra indexes, no `--no-index` discipline)

---

## Recommendations (prioritised)

### Must

1. **One source of truth for deps**: use `uv` or `pip-tools` to generate hash-pinned constraints (`--require-hashes`) per environment; commit locks
2. **Hermetic CI**: pinned base images; no network during build except index/mirrors you control; ephemeral runners; deterministic clocks
3. **Cross-platform wheelhouse**: build with `cibuildwheel` for Linux (manylinux_2_28), macOS (universal2/x86_64/arm64 as applicable), Windows; vendor native libs with auditwheel/delocate/delvewheel
4. **Private distribution**:
   - Online side: devpi/Nexus/Artifactory as private index; GHCR/OCI as artefact store
   - Offline side: generate a portable wheelhouse bundle (tar + checksums + simple index) per release
5. **Supply-chain guarantees**: SBOM (CycloneDX), OSV scan gate, signatures (Sigstore cosign), SLSA provenance (OIDC in CI) attached to wheel bundles
6. **Policy engine**: allowlist/denylist, version ceilings, upgrade cadences, backport rules; CI blocks on policy violations
7. **Compatibility matrix & tests**: matrix by OS/arch/Python; contract/integration tests executed against the wheelhouse

### Should

- **OCI packaging for bundles**: publish wheelhouse as an OCI artefact (e.g., `ghcr.io/org/pkg/wheelhouse:<version>`), with SBOM/provenance as additional OCI layers
- **Binary reproducibility check**: rebuild subset out-of-band and compare digests (bit-for-bit or normalized)
- **Proactive CVE backports**: maintain "security constraints" overlay to pin safe minima without jumping majors

### Nice

- **Nix/Guix profile** for maximal hermeticity (optional path)
- **Auto-advice bot**: PR comments proposing safe upgrades, impact radius, and policy rationale

---

## Reference CI Blueprint

GitHub Actions (adapt for GitLab/Buildkite):

```yaml
name: build-wheelhouse
on: [push, workflow_dispatch, release]
jobs:
  wheels:
    strategy:
      matrix:
        os: [ubuntu-24.04, macos-14, windows-2022]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - name: Install tooling
        run: |
          python -m pip install --upgrade pip
          pip install uv cibuildwheel==2.* cyclonedx-bom==4.* osv-scanner==1.* cosign
      - name: Resolve deps (hash-pinned)
        run: |
          uv pip compile pyproject.toml -o constraints.txt --generate-hashes
          uv pip sync -r constraints.txt
      - name: Build wheels
        env:
          CIBW_BUILD: "cp38-* cp39-* cp310-* cp311-* cp312-*"
          CIBW_SKIP: "pp* *_i686 *-musllinux*"
          CIBW_MANYLINUX_X86_64_IMAGE: "quay.io/pypa/manylinux_2_28_x86_64"
          CIBW_ARCHS: "x86_64"
          CIBW_TEST_COMMAND: "python -c 'import yourpkg; print(yourpkg.__version__)'"
        run: |
          python -m cibuildwheel --output-dir wheelhouse
      - name: SBOM + Vulnerability gate
        run: |
          cyclonedx-py --format json -o wheelhouse/sbom.json .
          osv-scanner --lockfile=constraints.txt --format json > wheelhouse/osv.json
      - name: Bundle wheelhouse (offline)
        run: |
          python - <<'PY'
          import hashlib, tarfile, json, os
          fn="wheelhouse.tar.gz"
          with tarfile.open(fn,"w:gz") as tar:
              tar.add("wheelhouse", arcname="wheelhouse")
          h=hashlib.sha256(open(fn,"rb").read()).hexdigest()
          open("wheelhouse.sha256","w").write(f"{h}  {fn}\n")
          meta={"commit":"${{ github.sha }}"}
          open("wheelhouse.meta.json","w").write(json.dumps(meta,indent=2))
          PY
      - name: Sign artefacts (keyless)
        env: { COSIGN_EXPERIMENTAL: "1" }
        run: |
          cosign sign-blob --yes wheelhouse.tar.gz > wheelhouse.sig
      - uses: actions/upload-artifact@v4
        with: { name: wheelhouse-${{ matrix.os }}, path: wheelhouse* }
```

Optionally add a publish job that uses `oras` to push `wheelhouse.tar.gz`, `sbom.json`, `osv.json`, `slsa.provenance` to GHCR as an OCI artefact.

---

## Air-gapped Consumption (two paths)

### A) Simple, no server

```bash
# On offline runner (bundle already copied in)
tar -xzf wheelhouse.tar.gz
pip install --no-index --find-links=wheelhouse -r requirements.txt
```

### B) Local index (devpi offline)

```bash
# Prepare once (no Internet)
devpi-server --serverdir /srv/devpi --offline &
devpi use http://localhost:3141/root/offline
devpi login root --password=''
devpi index -c offline volatile=False

# Load all wheels
find wheelhouse -name '*.whl' -print0 | xargs -0 -I{} devpi upload --from-dir {}
pip install --index-url http://localhost:3141/root/offline/simple --no-deps yourpkg==X.Y.Z
```

---

## Orchestration & Integration

- **Interfaces**: CLI (`tool smith wheelhouse build|bundle|publish|mirror`), REST (list/query artefacts), and OCI endpoints so any system can pull bundles
- **Policy hooks**: pre-merge bot comments and CI checks:
  1. Hash-pinned?
  2. Policy compliance?
  3. OSV clean?
  4. SBOM present?
  5. Provenance verified?
- **Metadata contract**: each wheelhouse carries `sbom.json`, `osv.json`, `*.sig`, `sha256`, and `slsa.provenance`. Consumers verify before install

---

## KPIs & Gates

- **Reproducibility**: ≥95% identical rebuilds (90%/50% intervals: 90–99% / 80–100%)
- **Coverage**: ≥98% target OS/arch wheels present per release
- **Security**: 0 known criticals at ship; <48h patch SLA for highs
- **Determinism**: 100% installs with `--require-hashes` and `--no-index` in air-gapped jobs

---

## Provenance Block

- **Data**: Industry packaging norms (PEP 517/518; manylinux), cibuildwheel behaviours, SBOM/OSV/Sigstore/SLSA practices
- **Methods**: Threat-model + failure-mode enumeration; CI blueprint; offline install drills
- **Key results**: Deterministic, attested wheelhouse with offline path; reduced attack surface; plug-and-play consumption
- **Uncertainty**: Exact OS/arch matrix and native-lib needs vary by your codebase. Minor tuning likely (e.g., `CIBW_*` env, QEMU)
- **Safer alternative**: Start with Linux-only wheelhouse + private index, then expand to macOS/Windows once green

---

# CHIRON — Definitive E2E Spec (Frontier‑grade)

This section folds the gap‑analysis into a full, buildable specification for the standalone Chiron project (library and optional service), including tooling, tech stack, CI/CD, security, and offline paths.

## 1) Goals & Non‑negotiables

- Deterministic, hermetic builds across OS/arch (Linux manylinux/musllinux; macOS x86_64/arm64; Windows) with repaired wheels (auditwheel/delocate/delvewheel).
- Offline/air‑gapped installs using a signed wheelhouse bundle and `pip --no-index --find-links` with hash‑checked installs.
- Tokenless releases via PyPI Trusted Publishing (OIDC), signed artefacts, SBOMs (CycloneDX), SLSA provenance, and vulnerability gates.
- Policy‑driven dependency management (locks + allow/deny) with fast tooling (`uv`).
- Observability by default (OpenTelemetry traces/metrics/logs) when running as a service.

## 2) Baseline Tech Stack

**Languages & runtimes.** Python 3.12+ (build wheels for 3.8–3.13 as needed).

**Build & packaging.** `pyproject.toml` (PEP 621/517) with Hatchling (or current backend); `cibuildwheel` for cross‑platform wheels; `auditwheel`/`delocate`/`delvewheel` for native deps.

**Dependencies & locking.** `uv` for resolution and sync; enforce `--require-hashes` installs; constraints/locks committed.

**Security & supply chain.** PyPI Trusted Publishing (OIDC), Sigstore `cosign` (keyless), SBOMs (CycloneDX or Syft), OSV/Grype scan, SLSA provenance.

**Observability.** OpenTelemetry SDK + FastAPI instrumentation (service mode).

**Quality & DX.** `pre-commit` with Ruff (lint+format) and MyPy (strict); Renovate for updates.

## 3) Reference Repository Layout

```text
chiron/
  src/chiron/              # library code
  api/                     # optional FastAPI app (service mode)
  tests/                   # unit + property tests
  examples/                # usage & smoke tests
  pyproject.toml
  uv.lock                  # dependency lockfile
  .pre-commit-config.yaml
  .github/workflows/
    ci.yml                 # lint/type/test + sbom/scan
    wheels.yml             # cibuildwheel + bundle/sign
    publish.yml            # PyPI trusted publishing
  docs/                    # Diátaxis docs (how-to, ref, tutorials, explanations)
```

## 4) Minimal `pyproject.toml`

```toml
[build-system]
requires = ["hatchling>=1.25"]
build-backend = "hatchling.build"

[project]
name = "chiron"
version = "0.1.0"
description = "Frontier-grade dependency & wheelhouse system"
requires-python = ">=3.12"
readme = "README.md"
license = { text = "Apache-2.0" }
authors = [{ name = "Your Org", email = "[email protected]" }]

[project.optional-dependencies]
cli = ["typer>=0.12"]
otel = [
  "opentelemetry-sdk",
  "opentelemetry-exporter-otlp",
  "opentelemetry-instrumentation-fastapi",
]

[project.scripts]
chiron = "chiron.cli:main"

[tool.cibuildwheel]
build = "cp38-* cp39-* cp310-* cp311-* cp312-* cp313-*"
skip = "pp* *-musllinux_i686 *_i686"

'test-command' = "python -c \"import chiron; print(getattr(chiron,'__version__','dev'))\""

[tool.cibuildwheel.linux]
repair-wheel-command = "auditwheel repair -w {dest_dir} {wheel}"

[tool.cibuildwheel.macos]
repair-wheel-command = "delocate-wheel -w {dest_dir} -v {wheel}"

[tool.cibuildwheel.windows]
before-build = "pip install delvewheel"
repair-wheel-command = "delvewheel repair -w {dest_dir} {wheel}"
```

## 5) Dependency Policy & Offline Discipline

- Lock & sync with `uv lock && uv sync`; enforce hash‑checked installs in CI and offline: `pip install --require-hashes --no-index --find-links=wheelhouse -r requirements.txt`.
- Maintain allow/deny lists and upgrade windows; gate PRs on policy.

## 6) CI/CD Blueprints

### Wheels + wheelhouse bundle

```yaml
name: wheels
on: [push, pull_request, release]
jobs:
  build:
    strategy:
      matrix: { os: [ubuntu-24.04, macos-14, windows-2022] }
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - name: Tooling
        run: |
          python -m pip install -U pip
          pip install uv cibuildwheel cyclonedx-bom osv-scanner cosign
      - name: Resolve & sync
        run: |
          uv lock
          uv sync
      - name: Build wheels
        run: python -m cibuildwheel --output-dir wheelhouse
      - name: SBOM & vulns
        run: |
          cyclonedx-py --format json -o wheelhouse/sbom.json .
          osv-scanner --format json --skip-git -M wheelhouse/osv.json .
      - name: Bundle (offline)
        run: |
          tar -czf wheelhouse.tar.gz wheelhouse
          sha256sum wheelhouse.tar.gz > wheelhouse.sha256
      - name: Sign
        env: { COSIGN_EXPERIMENTAL: '1' }
        run: cosign sign-blob --yes wheelhouse.tar.gz > wheelhouse.sig
      - uses: actions/upload-artifact@v4
        with: { name: wheelhouse-${{ matrix.os }}, path: wheelhouse* }
```

### Trusted Publishing (release)

```yaml
name: publish
on: { release: { types: [published] } }
jobs:
  pypi:
    runs-on: ubuntu-latest
    permissions: { id-token: write, contents: write }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - name: Build
        run: |
          python -m pip install -U build
          python -m build
      - name: Publish to PyPI (trusted)
        uses: pypa/gh-action-pypi-publish@release/v1
```

## 7) Optional Service Mode (FastAPI)

```python
# api/main.py
from fastapi import FastAPI
app = FastAPI()
@app.get('/healthz')
def health():
    return {"ok": True}
```

Add OTel via `opentelemetry-instrumentation-fastapi` and export to OTLP when present.

## 8) Observability Defaults

- Enable OTel traces/metrics/logs in service mode; add log‑trace correlation; export OTLP to your collector.

## 9) Quality Gates & DX

- `pre-commit` with Ruff (lint+format) and MyPy (strict). Example:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks: [{ id: ruff }, { id: ruff-format }]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.2
    hooks: [{ id: mypy }]
```

## 10) Security & Supply‑chain Hardening

- Enforce `--require-hashes` installs; prefer binary wheels in prod.
- Attach SBOM (CycloneDX) and scan (OSV/Grype) on every build.
- Sign artefacts with `cosign` and attach SLSA provenance.

## 11) Verification Checklist

- Wheels produced and smoke‑tested for all target OS/arch.
- SBOM generated and vulnerability gate: no criticals.
- Wheelhouse bundle signed; checksum published; provenance attached.
- Offline install succeeds with `--no-index --require-hashes`.

## 12) **Fully Automated Mode** (one‑command feature)

Provide a “zero‑to‑frontier” path that bootstraps everything with one command.

**What users do**

```
# From an empty or messy folder
uvx cookiecutter gh:your-org/chiron-template
# or
pipx run cookiecutter gh:your-org/chiron-template
```

**What it gives them**

- **Dev Container** in `.devcontainer/devcontainer.json` (Python 3.12; docker‑in‑docker; postCreate installs dev deps via `uv`).
- **Reusable GitHub workflows** (called via `workflow_call`) for CI, wheels, publish, and air‑gap bundle.
- **CLI** (`chiron`) exposing:

```
chiron init        # config, ADRs, pre-commit
chiron build       # local build via uv + cibuildwheel
chiron wheelhouse  # bundle + sbom + sign
chiron airgap pack # produce offline tar + checksums
chiron release     # trusted publish
chiron verify      # verify sigs/SBOM/provenance
chiron doctor      # policy checks & upgrade advice
```

- **Makefile** commands as a friendly command palette mapping to the CLI.
- **Renovate** & **pre‑commit** prewired; **OPA/Conftest** policy hooks optional.

**Dev Container (example)**

```json
{
  "name": "chiron",
  "image": "mcr.microsoft.com/devcontainers/python:3.12",
  "features": { "ghcr.io/devcontainers/features/docker-in-docker:2": {} },
  "postCreateCommand": "uv pip install -r dev-requirements.txt"
}
```

### 12.1) GitHub Sync & Trusted Publishing Setup

**Via GitHub CLI (recommended)**

```bash
# authenticate once (browser flow)
gh auth login
# create remote; keep local as-is
gh repo create <OWNER/REPO> --private --source=. --push
# or if the repo already exists remotely, just set default
gh repo set-default <OWNER/REPO>
# verify remote + default branch
git remote -v
git branch -M main
# first push (if not already pushed)
git push -u origin main
```

**Pure Git path**

```bash
git init -b main  # if needed
git remote add origin https://github.com/OWNER/REPO.git
# or update existing remote
# git remote set-url origin https://github.com/OWNER/REPO.git
git add -A && git commit -m "chore: bootstrap Chiron"
git push -u origin main
```

**Enable PyPI Trusted Publishing (OIDC)**

1. In **PyPI → Project → Settings → Add a publisher**, select **GitHub Actions** and this repo/workflow.
2. In your publish workflow job, grant `permissions: { id-token: write, contents: write }`.
3. Use the official action in the release job:

```yaml
- name: Publish to PyPI (trusted)
  uses: pypa/gh-action-pypi-publish@release/v1
```

4. No long‑lived tokens needed; releases mint short‑lived creds via OIDC.

---

### 12.2) Pre‑flight & Packaging for **Any Project** (drop‑in guide)

**Pre‑flight checks**

- Define Python support matrix (e.g., 3.8–3.13); note OS/arch targets.
- Audit native deps (BLAS/SSL/etc.); plan `auditwheel`/`delocate`/`delvewheel` repair.
- Ensure `pyproject.toml` exists (PEP 621/517); set name, version, entry‑points.
- Decide policy: hash‑pinned installs, allow/deny list, upgrade windows.

**Minimal wiring steps**

1. Add/merge `pyproject.toml` (use the sample in this doc) and commit.
2. Lock deps with `uv` and commit `uv.lock`:

```bash
uv lock && uv sync
```

3. Add CI workflows from this doc (`ci.yml`, `wheels.yml`, `publish.yml`).
4. Build locally to verify tags + repairs:

```bash
python -m cibuildwheel --output-dir wheelhouse
```

5. Bundle + sign + SBOM:

```bash
# SBOM + vuln scan (example)
cyclonedx-py --format json -o wheelhouse/sbom.json .
osv-scanner --format json --skip-git -M wheelhouse/osv.json .
# bundle + sign
tar -czf wheelhouse.tar.gz wheelhouse
sha256sum wheelhouse.tar.gz > wheelhouse.sha256
cosign sign-blob --yes wheelhouse.tar.gz > wheelhouse.sig
```

6. Offline smoke test (any host):

```bash
tar -xzf wheelhouse.tar.gz
pip install --no-index --require-hashes --find-links=wheelhouse -r requirements.txt
```

7. (Optional) Add FastAPI wrapper in `api/` and enable OpenTelemetry.

**Works with any repo**: these steps are additive; no code deletion required. Start with Linux wheels, then expand to macOS/Windows once CI is green.

````

## 13) KPIs & Ship Gates
- Reproducibility ≥95% identical rebuilds (spot checks).
- Coverage ≥98% of declared OS/arch wheels per release.
- Security: 0 criticals at ship; <48h patch SLA for highs.
- Determinism: 100% prod/offline installs use `--require-hashes` and `--no-index`.

---


## 14) Enhanced UX & Intelligence Upgrades

These upgrades make Chiron powerful for experts and safe for non‑technical operators, while staying standards‑aligned.

### 14.1 Guided Mode (Schema‑driven)
- All commands accept JSON/YAML config validated against **JSON Schema**; the CLI renders an interactive wizard when flags are omitted.
- Store schemas in `schemas/` and validate pre‑flight before any action.

```json
// schemas/airgap-pack.schema.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AirgapPack",
  "type": "object",
  "properties": {
    "release": {"type": "string", "pattern": "^v?\\d+\\.\\d+\\.\\d+$"},
    "include_sbom": {"type": "boolean", "default": true},
    "sign": {"type": "boolean", "default": true},
    "dest": {"type": "string"}
  },
  "required": ["release"]
}
````

```python
# cli/wizard.py (excerpt)
import json, pathlib
import jsonschema
import typer
app = typer.Typer()
SCHEMA = json.loads(pathlib.Path('schemas/airgap-pack.schema.json').read_text())

@app.command()
def airgap_pack(release: str = typer.Option(None), dest: str = "build/"):
    cfg = {"release": release, "include_sbom": True, "sign": True, "dest": dest}
    jsonschema.validate(cfg, SCHEMA)
    # then call the underlying implementation: chiron.airgap.pack(cfg)
```

### 14.2 Backstage Plugin (single pane of glass)

- Ship a Backstage plugin exposing: wheel coverage, SBOM/signature/provenance status, policy gates, and one‑click **Create Offline Bundle**.
- Suggested structure:

```
backstage/
  plugins/
    chiron/
      src/components/ChironCard.tsx
      src/plugin.ts
      package.json
```

- The card surfaces green/red indicators and links to CI artefacts.

### 14.3 Feature Flags (OpenFeature)

Enable safe toggles for sensitive ops (e.g., public publish) with vendor‑agnostic **OpenFeature**.

```python
# chiron/flags.py (excerpt)
from openfeature import api
client = api.get_client("chiron")

def allow_public_publish() -> bool:
    return client.get_boolean_value("allow-public-publish", False)
```

Guard risky paths in the CLI/service using this flag; document default "off".

### 14.4 Distribution via OCI (+ optional TUF)

Treat the wheelhouse bundle as an **OCI artefact** so any registry works (GHCR/Artifactory/ACR).

```bash
# Push
oras push ghcr.io/OWNER/REPO/wheelhouse:v${VERSION} \
  wheelhouse.tar.gz:application/vnd.chiron.wheelhouse.targz \
  wheelhouse/sbom.json:application/vnd.cyclonedx+json \
  wheelhouse.sig:application/vnd.dev.sigstore.signature

# Pull
oras pull ghcr.io/OWNER/REPO/wheelhouse:v${VERSION} -o ./download
```

Optional hardening: publish TUF metadata alongside artefacts; verify freshness in air‑gapped installs before use.

### 14.5 Agent/Assistant Mode (MCP, opt‑in)

Offer a natural‑language operator for common tasks under strict policy checks.

```
mcp/
  chiron.server.json   # declares tools: build_wheelhouse, bundle_airgap, publish_oci, verify
```

The MCP server wraps `chiron` commands; the host (IDE/assistant) connects via MCP, presents a plan, and executes only after a dry‑run diff. Identity uses short‑lived OIDC where available.

### 14.6 Observability UX that explains itself

Emit **OpenTelemetry** spans around critical stages (resolve → build → repair → sbom → sign → publish → verify) with log‑trace correlation.

```python
# chiron/otel.py (excerpt)
from opentelemetry import trace
tracer = trace.get_tracer("chiron")

def build_wheelhouse():
    with tracer.start_as_current_span("wheelhouse.build") as span:
        span.set_attribute("chiron.python", "3.12")
        # ... run cibuildwheel, collect timings, attach artefact counts
```

Ship a default dashboard (JSON) that graphs timings, error rates, and policy gate failures.

### 14.7 Contracts & API ergonomics

- **Service adapter** exposes OpenAPI (REST) and keeps endpoints versioned.
- Protect integrators with **consumer‑driven contracts** (Pact). Example consumer test skeleton:

```python
# tests/contracts/test_api_contract.py (sketch)
from pact import Consumer, Provider
pact = Consumer('chiron-consumer').has_pact_with(Provider('chiron-service'))

def test_get_health():
    (pact
     .given('service healthy')
     .upon_receiving('health check')
     .with_request('GET', '/healthz')
     .will_respond_with(200, body={"ok": True}))
    with pact:
        # call your client here
        pass
```

### 14.8 Operator‑friendly flows

- **Dry‑run by default** for destructive ops; require an explicit `--confirm`.
- **Guided mode** prints each action, estimated impact, and verification steps.
- **Runbooks**: auto‑generate a short “What happened & how to roll back” note after each run.

---

This spec, combined with the earlier gap‑analysis and blueprint, forms the definitive guide to build, ship, and operate Chiron at frontier grade.
