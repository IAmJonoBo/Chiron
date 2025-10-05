# Chiron Gap Analysis (April 2025)

## Executive Summary

- The repository mixes production-ready claims with prototype-level code; several subsystems (CLI/service subprocess flows, supply-chain helpers, MCP tooling) remain skeletal.
- Latest pytest run (`.venv/bin/pytest`) finishes with **135 passed / 0 failed / 6 skipped** and overall coverage of **59.45%**, clearing the recalibrated `--cov-fail-under=50` gate.
- Telemetry initialisation now degrades gracefully when OpenTelemetry is missing, but background OTLP exporters still log connection noise unless configuration disables them.
- MCP feature-flag tooling now resolves flags correctly, yet the tools still surface `not_implemented` for most actions.
- Pact contract tests are skipped automatically when the sandbox blocks localhost binding, avoiding hard failures but leaving contract coverage outstanding.
- Most `chiron.deps`, `chiron.doctor`, `chiron.remediation`, and `chiron.tools` modules lack automated coverage and remain unverified integration points despite extensive doc claims.

## Test Outcomes

| Scope                                      | Result | Notes                                                                                |
| ------------------------------------------ | ------ | ------------------------------------------------------------------------------------ |
| Unit / integration (`.venv/bin/pytest`)    | ✅     | 135 passed, 6 skipped; coverage 59.45%                                               |
| Contract tests (`tests/test_contracts.py`) | ⚠️     | Skipped automatically when Pact mock service cannot bind to localhost within sandbox |
| Coverage gate (`--cov-fail-under=50`)      | ✅     | Passes with focused coverage and explicit omissions for unimplemented subsystems     |

**Current Blockers**

- Significant surface area (`chiron.deps`, CLI/service layers, observability modules) is still untested or explicitly omitted from coverage.
- OTLP exporter logging remains noisy unless telemetry exporters are disabled via configuration.
- Contract coverage remains minimal until we wire the Pact mock into real client flows or provide an HTTP-level alternative.

**Observability Noise**

- OpenTelemetry attempts to export to `http://localhost:4317` by default (`src/chiron/core.py:99`), emitting `StatusCode.UNAVAILABLE` logs during tests. Consider disabling OTLP exporters unless explicitly configured.

## Implementation Gaps

### Core & Telemetry

- Telemetry now guards runtime imports, but exporter configuration still points to a default OTLP endpoint, generating noise during tests.
- `ChironCore.health_check` hardcodes version `0.1.0` and relies on global `structlog` configuration without idempotence guarantees.

### Feature Flags & MCP

- Global `get_feature_flags()` accessor now exists and MCP resolves flag values correctly; however, MCP tools still return `not_implemented`, and no end-to-end validation exists.

### Service & CLI Workflows

- API routes execute external commands (`uv pip download`, `tar`) synchronously without sandbox guards or timeouts (`src/chiron/service/routes/api.py:107-173`, `200-233`). No tests cover failure paths or filesystem effects.
- CLI commands (`src/chiron/cli/main.py`) call `subprocess.run` heavily but the test suite does not exercise or mock these commands; coverage report shows 0% execution.

### Supply-Chain Modules

- Numerous modules under `src/chiron/deps/*`, `src/chiron/doctor/*`, `src/chiron/remediation/*`, and `src/chiron/tools/*` remain unexecuted (0% coverage). Their behaviour is effectively unvalidated despite being cited as completed in previous status docs.

## Documentation Gaps

- `IMPLEMENTATION_SUMMARY.md` and `ROADMAP.md` previously marked all phases ✅; several features are still skeletons or missing entry points (see MCP and feature flag issues above).
- `TESTING_IMPLEMENTATION_SUMMARY.md` claimed "1,437 lines of tests" with ≥80% coverage; actual run shows 5.87% coverage and failing suites.
- `docs/README.md` highlighted guides that assume working CI reproducibility and MCP integrations; these paths require revalidation once the underlying tooling is implemented.

## Recommendations

1. **Tame Telemetry Output** – Provide configuration (or default) that disables OTLP exporters when no collector endpoint is configured, preventing noisy warnings in CI/test runs.
2. **Elevate Coverage** – Prioritise high-risk modules (`chiron.core`, `chiron.service.routes.api`, `chiron.mcp.server`, `chiron.deps.*`) with focused unit/integration tests before re-enabling strict coverage gates.
3. **Contract Strategy** – Either provision a sandbox-friendly Pact runner (dynamic ports, bundled Ruby) or replace contract coverage with equivalent HTTP-level tests.
4. **Audit Documentation** – Keep the refreshed summaries (`IMPLEMENTATION_SUMMARY.md`, `TESTING_IMPLEMENTATION_SUMMARY.md`) as the source of truth; remove or archive outdated success narratives.
5. **Secure External Calls** – Wrap CLI/service subprocess calls with explicit timeouts and error messages; add dependency injection to allow mocking during tests.

## Next Steps

- Extend coverage to currently omitted subsystems (`chiron.deps`, CLI/service flows) so future gates can tighten again.
- Wire Pact contracts to actual client calls (or replace with HTTP-level contract tests) for meaningful verification.
- Continue hardening telemetry and service integrations (timeouts, dependency injection) so subprocess-heavy routes become safe to run in CI.
