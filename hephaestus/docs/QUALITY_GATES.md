# Quality Gates

<!-- BEGIN QUALITY_SUITE_AUTODOC -->

### Developer Toolbox Quality Suite Snapshot

Use the developer toolbox to keep local quality gates aligned with CI.

**Primary profile**: `full` (7 gates)
**Generated**: 2025-10-06T17:59:01.767195+00:00

| Order | Gate        | Category | Critical | Command                                                                         |
| ----- | ----------- | -------- | -------- | ------------------------------------------------------------------------------- |
| 1     | `tests`     | tests    | Required | `uv run --extra dev --extra test pytest --cov=src/hephaestus --cov-report=term` |
| 2     | `contracts` | tests    | Optional | `uv run --extra test pytest tests/test_contracts.py -k contract`                |
| 3     | `lint`      | lint     | Required | `uv run --extra dev ruff check`                                                 |
| 4     | `types`     | types    | Required | `uv run --extra dev mypy src`                                                   |
| 5     | `security`  | security | Required | `uv run --extra security bandit -r src -lll`                                    |
| 6     | `docs`      | docs     | Optional | `uv run --extra docs mkdocs build --strict`                                     |
| 7     | `build`     | build    | Required | `uv build`                                                                      |

**Applied toggles**: _None_

_Updated automatically via `hephaestus tools qa --sync-docs docs/QUALITY_GATES.md`._

<!-- END QUALITY_SUITE_AUTODOC -->
