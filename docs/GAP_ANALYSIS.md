# Chiron Gap Analysis (April 2025)

## Executive Summary

- The repository mixes production-ready claims with prototype-level code; several subsystems (CLI/service subprocess flows, supply-chain helpers, MCP tooling) remain skeletal.
- Latest pytest run (`uv run --extra dev --extra test pytest --cov=src/chiron`) finishes with **705 passed / 0 failed** and overall coverage of **89.10%**, comfortably clearing the tightened 80% gate while exercising the new benchmarking, MCP flows, dependency policy enforcement, constraints generation, and the freshly validated drift analysis plus module-boundary graph coverage alongside the upgraded developer toolbox tests.
- `chiron tools qa` now mirrors CI locally with profile-aware planning, dry-run previews, and JSON reporting, while the expanded `chiron tools coverage` suite surfaces hotspots, gap summaries, and enforces guard thresholds for the remaining supply-chain and service coverage gaps.
- Telemetry initialisation now degrades gracefully when OpenTelemetry is missing, but background OTLP exporters still log connection noise unless configuration disables them.
- MCP feature-flag tooling now resolves flags correctly, yet the tools still surface `not_implemented` for most actions.
- Pact contract tests execute against the Ruby mock (130+ pending-deprecation warnings) but remain synthetic—no real HTTP client flow has been wired in yet.
- Most `chiron.deps`, `chiron.doctor`, `chiron.remediation`, and `chiron.tools` modules lack automated coverage and remain unverified integration points despite extensive doc claims.
- Dependency graph tooling now auto-discovers `src/chiron` namespaces, preventing false negatives when generating module boundary diagrams.
- Pact fixtures allocate worker-specific ports to avoid teardown flakiness under `pytest-xdist`, reducing noise while broader HTTP coverage is still pending.

## Test Outcomes

| Scope                                      | Result | Notes |
| ------------------------------------------ | ------ | ----- |
| Unit / integration (`uv run pytest --cov`) | ✅     | 705 passed, 0 failed; coverage 89.10%; warnings dominated by Pact deprecation notices |
| Contract tests (`tests/test_contracts.py`) | ⚠️     | Execute against Pact mock but remain synthetic; no real HTTP clients or contract enforcement yet |
| Coverage gate (`--cov-fail-under=80`)      | ✅     | Gate tightened to 80%; complex dependency graph branches still need targeted tests |

**Current Blockers**

- Significant surface area in `chiron.deps` drift/graph analyzers and several CLI/service flows still lacks exhaustive branch coverage despite the uplift; conflict resolution heuristics now ship targeted tests that exercise direct-versus-transitive branches.
- OTLP exporter noise mitigated via explicit opt-in gate; continue monitoring for regressions when enabling local collectors.
- Contract coverage remains minimal until we wire the Pact mock into real client flows or provide an HTTP-level alternative.
- Security extras now pin `semgrep>=1.70,<1.80` and `click<8.2` to coexist with `rich>=13.5` and OpenTelemetry ≥1.37; running semgrep inside the main runtime environment remains brittle and should be isolated.

**Observability Noise**

- OpenTelemetry exporters are now disabled unless `telemetry.exporter_enabled` is true and a real collector endpoint is opted-in. Local placeholder endpoints such as `http://localhost:4317` require `telemetry.assume_local_collector` (or `CHIRON_ASSUME_LOCAL_COLLECTOR=1`) to avoid accidental noise during tests.

## Implementation Gaps

### Core & Telemetry

- Telemetry now guards runtime imports and skips placeholder exporters by default; dedicated integration tests are still required for real collector deployments.
- `ChironCore.health_check` now reports the packaged version dynamically via `chiron.__version__`, avoiding stale metadata in health responses.

### Feature Flags & MCP

- Global `get_feature_flags()` accessor now exists and MCP resolves flag values correctly; deterministic LLM contracts exercise health and wheelhouse flows, but several tools still return `not_implemented` and need full implementations.

### Service & CLI Workflows

- API routes execute external commands (`uv pip download`, `tar`) synchronously without sandbox guards or timeouts (`src/chiron/service/routes/api.py:107-173`, `200-233`). No tests cover failure paths or filesystem effects.
- CLI commands now live in `src/chiron/typer_cli.py`; while `src/chiron/cli/main.py` is only a compatibility shim, the Typer command tree still shells out extensively and lacks failure-path coverage.

### Supply-Chain Modules

- Several modules under `src/chiron/deps/*` now exceed 50–90% coverage, but conflict resolution and drift analysis branches still lack dedicated edge-case tests. Doctor/remediation/tooling packages remain excluded and deserve incremental backfilling.

## Documentation Gaps

- `IMPLEMENTATION_SUMMARY.md` and `ROADMAP.md` previously marked all phases ✅; several features are still skeletons or missing entry points (see MCP and feature flag issues above).
- `TESTING_IMPLEMENTATION_SUMMARY.md` claimed "1,437 lines of tests" with ≥80% coverage; the refreshed run now reaches 89.10% coverage, yet 140+ Pact warnings persist and branch-level confidence is uneven.
- `docs/README.md` highlighted guides that assume working CI reproducibility and MCP integrations; these paths require revalidation once the underlying tooling is implemented.

## Recommendations

1. **Elevate Coverage** – Maintain the >80% baseline while targeting high-risk modules (`chiron.core`, `chiron.service.routes.api`, `chiron.mcp.server`, `chiron.deps.*`) for deeper branch/path testing so the gate remains resilient.
2. **Contract Strategy** – Either provision a sandbox-friendly Pact runner (dynamic ports, bundled Ruby) or replace contract coverage with equivalent HTTP-level tests.
3. **Harden Tooling Dependencies** – Document the `semgrep`/`click` pin rationale and run heavy scanners (`semgrep`, `syft`, `cosign`) via isolated tools (`uvx`, `pipx`) to keep the runtime environment clean.
4. **Audit Documentation** – Keep the refreshed summaries (`IMPLEMENTATION_SUMMARY.md`, `TESTING_IMPLEMENTATION_SUMMARY.md`) as the source of truth; remove or archive outdated success narratives.
5. **Secure External Calls** – Wrap CLI/service subprocess calls with explicit timeouts and error messages; add dependency injection to allow mocking during tests.

## Next Steps

- Extend coverage to currently omitted subsystems (`chiron.deps`, CLI/service flows) so future gates can tighten again.
- Wire Pact contracts to actual client calls (or replace with HTTP-level contract tests) for meaningful verification.
- Continue hardening telemetry and service integrations (timeouts, dependency injection) so subprocess-heavy routes become safe to run in CI.
