# Next Steps

## Tasks
- [x] Implement outstanding doc commitments (todo/next/planned/future/gap) — Owner: Assistant — Due: TBC (env sync + benchmarking + MCP contracts addressed this pass)
- [x] Elevate lint/type/security baselines to green — Owner: Assistant — Due: TBC
- [x] Silence OTLP placeholder noise by gating exporters behind explicit opt-in — Owner: Assistant — Completed: 2025-10-06
- [x] Backfill branch coverage for dependency conflict resolution hot paths — Owner: Assistant — Completed: 2025-10-06
- [x] Extend coverage to `chiron.deps` drift/graph analyzers — Owner: Assistant — Completed: 2025-10-06
- [x] Auto-discover dependency graph modules and harden Pact fixture isolation — Owner: Assistant — Completed: 2025-10-06

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

## Deliverables
- [x] Code commits implementing required features/tests
- [x] Updated documentation reflecting new state
- [x] Passing lint, type-check, security scan, tests, and build
- [x] Telemetry defaults updated to avoid noisy OTLP connection attempts

- ✅ Tests: `uv run --extra dev --extra test pytest --cov=src/chiron --cov-report=term` — 87.11% coverage, 739 passed / 4 skipped / 0 failed (`9c93ed†L1-L63`)
- ✅ Lint: `uv run --extra dev ruff check` — clean (`b5ad74†L1-L2`)
- ✅ Type Check: `uv run --extra dev mypy src` — clean (`99772d†L1-L2`)
- ✅ Security Scan: `uv run --extra security bandit -r src -lll` — no issues (`844d9e†L1-L21`)
- ✅ Build: `uv build` — wheel & sdist succeed (`2fb8c9†L1-L4`)

## Links
- ✅ Tests: coverage + pytest run (`9c93ed†L1-L63`)
- ✅ Coverage report: `htmlcov/index.html` generated locally (not committed)
- ✅ Docs updated: README.md, docs/QUALITY_GATES.md, docs/GAP_ANALYSIS.md
- ✅ Drift & graph coverage: `tests/test_deps_drift_status.py`, `tests/test_deps_graph.py`
- ✅ Pact fixture hardening: `tests/test_contracts.py`
- ✅ Telemetry defaults: README.md, chiron.json, docs/GAP_ANALYSIS.md capture new opt-in behaviour

## Risks / Notes
- Remaining gaps include deeper CLI/service coverage plus dependency `constraints`/`policy` branches; telemetry exporter noise addressed with explicit opt-in gate, conflict resolver heuristics, and drift/graph analytics now exercised by tests.
- Pact-related warnings remain noisy but accepted for now; dynamic port allocation reduces flake risk but HTTP-level validation is still outstanding.
