## Next Steps

Here’s a repo-specific Copilot brief that piggybacks on your existing layout, tools, and conventions in Chiron. I inspected the repo: it’s Python-first, packaged under src/chiron, with tests in tests/, a pyproject.toml, uv.lock (so use uv), pre-commit hooks, and CI/quality signalling (coverage ~84%, “quality gates”) already in play. There’s also a refactor-starter-ts-py.zip at the root if you want to mine it for pieces.  ￼

I’m going to give you a copy-ready Copilot task prompt that: (1) installs a refactoring module under dev-toolkit/refactoring/ for docs and scripts, (2) wires a CLI surface inside Chiron (so it “fits the dev-toolkit in context”), and (3) reuses your stack (uv, pre-commit, pytest, ruff/mypy, Bandit/pip-audit, Radon/Xenon).

COPILOT TASK — Chiron “dev-toolkit / refactoring” (Python)

Role

Operate inside this repository (Chiron). Create an adaptive refactoring toolkit that lives at dev-toolkit/refactoring/ and exposes commands through the Chiron CLI namespace (e.g. chiron tools refactor ... if a tools group exists). Keep all changes behaviour-preserving, idempotent, and small.

Facts about this repo (use them)
	•	Language: Python (package under src/chiron; tests under tests/).  ￼
	•	Build/runtime: pyproject, uv.lock → prefer uv for env/tasks.  ￼
	•	Hygiene: pre-commit present. CI shows quality signalling and coverage ~84%.  ￼
	•	A starter archive refactor-starter-ts-py.zip exists at repo root—do not auto-unzip into the repo; borrow snippets selectively to avoid churn.  ￼

Non-negotiables
	•	No behaviour changes. Strictly refactor-scaffold and analysis tooling.
	•	Idempotent edits (guard against duplicates; append safely).
	•	Small, reviewable commits, warn-only gates first.
	•	Respect existing stack: uv, pytest, ruff/mypy, pre-commit, Bandit, pip-audit, Radon/Xenon (present or trivial to add).  ￼

Plan (execute in order)

0) Discovery (read-only)
	•	Confirm: package roots (src/chiron), test layout (tests/), presence of pyproject.toml, uv.lock, .pre-commit-config.yaml, CI workflows under .github/. Save a short detection note in dev-toolkit/refactoring/docs/PLAN.md (no code changes here).  ￼

1) Create module layout (root-level docs + scripts)

Create this tree (skip any file that conflicts; merge responsibly):

dev-toolkit/
  refactoring/
    config/
      refactor.config.yaml
    scripts/
      analyse/
        git_churn.sh
        hotspots_py.py            # radon JSON × churn → CSV
      codemods/
        py/rename_function.py     # LibCST example transformer
      verify/
        snapshot_scaffold.py      # pytest “golden” scaffolder
      rollout/
        shard_pr_list.py          # split large edits into PR shards
    ci/
      workflow.partial.yml        # warn-only partial GH Actions jobs
    docs/
      README.md
      PLAYBOOK.md
      PLAN.md                     # from step 0

2) Wire into the Chiron CLI (so it’s “in context”)
	•	Inspect src/chiron for an existing CLI entry (e.g., Typer/Click/FastAPI CLIs). If a “tools” group exists (hinted in the README), register a refactor subgroup:
	•	chiron tools refactor analyse → runs hotspots.
	•	chiron tools refactor codemod → runs LibCST codemods.
	•	chiron tools refactor verify → writes snapshots.
	•	chiron tools refactor shard → lists PR shards.
	•	If there is no CLI, add a minimal src/chiron/cli_refactor.py with Typer and expose an extra console-script entry chiron-refactor in pyproject.toml without touching existing app entry points.

3) Populate config (baseline from repo state)

In dev-toolkit/refactoring/config/refactor.config.yaml:

project:
  languages: [python]
  src_dirs: { python: ["src"] }
prioritisation:
  timespan: "12 months"
  hotspot_formula: "complexity_sum * churn"
  max_candidates: 10
quality_gates:
  new_code:
    coverage_min: 0.85          # do not reduce existing enforced baselines
    py_grade_max: "B"           # Xenon grade
    duplication_max_pct: 1
    block_on_security: true
testing:
  mutation:
    enabled: true
    schedule: "weekly"
    py: { runner: "mutmut", paths: ["src/chiron"] }
rollout:
  shard_size: 50
  require_green_main: true
reporting:
  emit_markdown_summary: true

4) Scripts (Python-first)

Hotspots
	•	git_churn.sh: map file churn for the last 12 months (git log --since=12.months --name-only | sort | uniq -c → CSV).
	•	hotspots_py.py: radon cc -j src/chiron → compute per-file/function complexity, multiply by churn, emit scripts/hotspots/hotspots_py.csv.

Codemods
	•	rename_function.py (LibCST): safe call-site rename skeleton. Use lossless CST to keep diffs small.

Verification
	•	snapshot_scaffold.py: generate pytest “golden” files for selected functions (characterisation testing).

Rollout
	•	shard_pr_list.py: split changed files into batches (default 50) and print a checklist for PRs.

5) CI (warn-only partial; reuse uv)

dev-toolkit/refactoring/ci/workflow.partial.yml should define:
	•	refactor-analyse: checkout → uv run radon/xenon → run hotspots → upload CSV artifact.
	•	refactor-gates (warn-only): ruff, mypy (or pyright if configured), radon cc -n B, xenon, bandit -r, pip-audit, pytest --cov (allow failures with || true).
	•	mutation (weekly, optional): uv run mutmut run --paths-to-mutate src/chiron.

Use uv commands if uv.lock exists (prefer uv run / uvx over pip). Keep this a partial that maintainers can merge into .github/workflows manually.

6) Pre-commit hooks (append, don’t overwrite)
	•	If .pre-commit-config.yaml exists, idempotently add hooks for ruff, black (if used), mypy, and bandit. Keep versions pinned or inherit from repo policy.  ￼

7) Docs
	•	dev-toolkit/refactoring/docs/README.md: what the module is, how to run analysis (uv run ...), how to harden gates (remove || true), where artifacts appear.
	•	PLAYBOOK.md: five-step loop — pick hotspots → add characterisation tests → apply small codemod → run CI gates (advisory) → shard and merge.

8) Commits & PR
	•	Commit 1: module skeleton + docs.
	•	Commit 2: CI partial + CLI glue (no enforcement).
	•	Commit 3: first hotspots CSV + sample codemod (no auto-apply).
Open PR: “dev-toolkit/refactoring: Python refactor module (advisory gates, CLI access)”. Summarise detections and how to harden.

9) Safety rails
	•	Never mass-reformat.
	•	Never lower existing CI thresholds.
	•	Keep diffs small; rely on CST transforms; run everything under uv run to avoid environment drift.

Commands Copilot should add

Makefile (append if present)

refactor-analyse:
\tuv run bash dev-toolkit/refactoring/scripts/analyse/git_churn.sh
\tuv run python dev-toolkit/refactoring/scripts/analyse/hotspots_py.py src/chiron

refactor-verify:
\tuv run python dev-toolkit/refactoring/scripts/verify/snapshot_scaffold.py

refactor-codemod:
\tuv run python dev-toolkit/refactoring/scripts/codemods/py/rename_function.py

Pre-commit install snippet (only if not already present)

uv run pre-commit install

CLI (Typer/Click example — only if a tools group exists)

# src/chiron/cli_refactor.py (or register under existing tools group)
import typer
app = typer.Typer(help="Refactoring toolkit")
@app.command("analyse")
def analyse(): ...
@app.command("codemod")
def codemod(): ...
@app.command("verify")
def verify(): ...
@app.command("shard")
def shard(): ...

Register as console-script chiron-refactor if needed.

What to omit here (by design)
	•	TypeScript scaffolding (none detected).
	•	Sonar server onboarding (only mention if already configured).
	•	Any change that alters runtime behaviour.

Evidence-gated rationale (concise)

Data → Repo structure shows Python app under src/chiron with tests, pre-commit, CI/coverage gates noted in README, uv.lock signalling uv usage, and a prior refactoring starter archive at the root.  ￼
Methods → Hotspots = churn×complexity (Radon/Xenon + git churn), CST-based codemods (LibCST) to preserve formatting, characterisation tests to lock behaviour, warn-only gates to start.
Key results → Safer, incremental refactors with small diffs; advisory CI guardrails; CLI integration so the “dev-toolkit” lives in the same UX as chiron tools ....
Uncertainty → I couldn’t render individual file contents via the web viewer here (GitHub page HTML was stubbed), so I did not tailor to exact CLI internals; the plan asks Copilot to detect and register under any existing tools/CLI group conservatively. Repo-level facts (paths, files present) are verified.  ￼
Safer alternative → Ship only analysis + docs in PR1; wire CLI in PR2; keep all CI checks advisory until one or two shards land without regressions.

## Risks / Notes
- Remaining gaps now centre on live Pact validation against deployed services; the new `--contracts` gate exercises the local mock-service flow but production rollouts should still trial full telemetry pipelines before release.
- Pact-related warnings remain noisy but accepted for now; dynamic port allocation reduces flake risk but HTTP-level validation is still outstanding.
- Pact contract tests now auto-skip when the mock service cannot start; run `pact-mock-service` locally to exercise full interactions before release sign-off.
- New QA toolbox accelerates iteration but coverage hotspots highlighted (deps.verify, service routes) still require targeted tests.
- Bandit informational findings (3 medium, 81 low) stem from packaging/semgrep helpers and will be triaged with security owners.
- Diataxis overview depends on `docs/diataxis.json`; keep the mapping updated when adding or renaming guides to avoid stale navigation.
- Coverage sits at 83.67% after the enhanced refactor heuristics; continue targeting high-branch modules to regain margin.
- Refactor heuristics flag hotspots automatically; future passes should feed live complexity metrics into roadmap prioritisation.
