# Next Steps

## Tasks
- [x] Implement outstanding doc commitments (todo/next/planned/future/gap) — Owner: Assistant — Due: TBC (env sync + benchmarking + MCP contracts addressed this pass)
- [x] Elevate lint/type/security baselines to green — Owner: Assistant — Due: TBC
- [x] Silence OTLP placeholder noise by gating exporters behind explicit opt-in — Owner: Assistant — Completed: 2025-10-06
- [x] Backfill branch coverage for dependency conflict resolution hot paths — Owner: Assistant — Completed: 2025-10-06
- [x] Extend coverage to `chiron.deps` drift/graph analyzers — Owner: Assistant — Completed: 2025-10-06
- [x] Auto-discover dependency graph modules and harden Pact fixture isolation — Owner: Assistant — Completed: 2025-10-06
- [x] Harden dependency governance coverage (constraints, policy engine, security overlay) — Owner: Assistant — Completed: 2025-10-06
- [x] Introduce QA/coverage developer toolbox commands — Owner: Assistant — Completed: 2025-10-06
- [x] Upgrade developer toolbox with profile-aware QA planning, guard enforcement, and coverage gap analytics — Owner: Assistant — Completed: 2025-10-06
- [x] Remove legacy Click CLI surface and expose Typer tooling via compatibility shim — Owner: Assistant — Completed: 2025-10-06
- [x] Harden Typer CLI exit handling and delegated script wrappers — Owner: Assistant — Completed: 2025-10-06
- [ ] Backfill dependency supply chain & verifier branches — Owner: Assistant — Due: TBC
- [ ] Raise service/runtime branch coverage (FastAPI app + MCP server) — Owner: Assistant — Due: TBC

## Steps
- [x] Catalogue outstanding items from docs (TODO/NEXT/PLANNED/FUTURE/GAP)
- [x] Prioritize and scope feasible implementations for this pass
- [x] Draft tests covering new behaviours before code changes (env sync script, benchmarking, MCP contracts)
- [x] Implement features/enhancements with reuse to avoid duplication
- [x] Update documentation to reflect completed work
- [x] Gate OTLP exporters behind config/env opt-in and expand telemetry tests
- [x] Design coverage plan for `chiron.deps` conflict branches before implementation
- [x] Outline coverage strategy for `chiron.deps` drift/graph modules
- [x] Validate module graph against `src/` layouts and stabilise contract teardown under xdist
- [x] Provide a one-command QA suite and coverage hotspot explorer for developers
- [x] Extend developer toolbox with configurable profiles, dry-run previews, coverage guards, and gap summaries
- [x] Swap Click-specific shims/tests for Typer-native interfaces and guards
- [x] Normalise CLI exit codes and add delegated command error handling across Typer commands

## Deliverables
- [x] Code commits implementing required features/tests
- [x] Updated documentation reflecting new state
- [x] Passing lint, type-check, security scan, tests, and build
- [x] Telemetry defaults updated to avoid noisy OTLP connection attempts
- [x] Developer toolbox (`chiron tools qa`, `chiron tools coverage`) documented for local QC alignment with profiles, guard checks, and gap summaries
- [x] Typer CLI delegated scripts now share resilient exit-code handling with regression tests

- ✅ Tests: `uv run --extra dev --extra test pytest --cov=src/chiron --cov-report=term` — 89.10% coverage, 705 passed / 0 failed (0 skipped) (`9084d8†L1-L120`)
- ✅ Lint: `uv run --extra dev ruff check` — clean (`b2f3bb†L1-L2`)
- ✅ Type Check: `uv run --extra dev mypy src` — clean (`cda571†L1-L2`)
- ✅ Security Scan: `uv run --extra security bandit -r src -lll` — no issues (`e23dda†L1-L20`)
- ✅ Build: `uv build` — wheel & sdist succeed (`8a9c6d†L1-L3`)

## Links
- ✅ Tests: coverage + pytest run (`9084d8†L1-L120`)
- ✅ Coverage report: `htmlcov/index.html` generated locally (not committed)
- ✅ Docs updated: README.md, docs/QUALITY_GATES.md, docs/GAP_ANALYSIS.md with latest coverage and test counts
- ✅ Dependency governance coverage: `tests/test_deps_constraints.py`, `tests/test_deps_policy.py`, `tests/test_deps_security_overlay.py`
- ✅ Drift & graph coverage: `tests/test_deps_drift_status.py`, `tests/test_deps_graph.py`
- ✅ Pact fixture hardening: `tests/test_contracts.py`
- ✅ Developer toolbox coverage: `tests/test_dev_toolbox.py`
- ✅ Telemetry defaults: README.md, chiron.json, docs/GAP_ANALYSIS.md capture new opt-in behaviour
- ✅ CLI compatibility shim and Typer-only tests: `src/chiron/cli/main.py`, `tests/test_cli_main.py`

## Risks / Notes
- Remaining gaps include deeper CLI/service coverage plus dependency `supply_chain`/`verify` branches; governance primitives are now exercised end-to-end but runtime enforcement needs additional scenarios. The toolbox upgrades highlight these modules explicitly in the new coverage gap summaries.
- Pact-related warnings remain noisy but accepted for now; dynamic port allocation reduces flake risk but HTTP-level validation is still outstanding.
- New QA toolbox accelerates iteration but coverage hotspots highlighted (deps.verify, service routes) still require targeted tests.
