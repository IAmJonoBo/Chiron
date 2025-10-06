"""Dependency pipeline verification helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from click import Command
    from typer import Typer
else:  # pragma: no cover - fallback typing when optional deps missing
    Command = Any
    Typer = Any

GetCommand = Callable[[Typer], Command]

try:  # pragma: no cover - Typer is an optional runtime dependency
    from typer.main import get_command as _get_command
except Exception:  # pragma: no cover - fallback when Typer missing

    def _missing_get_command(app: Typer) -> Command:
        raise RuntimeError("Typer is not installed")

    get_command: GetCommand = cast(GetCommand, _missing_get_command)
else:
    get_command = cast(GetCommand, _get_command)

REPO_ROOT = Path(__file__).resolve().parents[1]

_SCRIPT_CHECKS: dict[str, tuple[str, str]] = {
    "scripts/preflight_deps.py": (
        "preflight_deps.py",
        'run_module("chiron.deps.preflight")',
    ),
    "scripts/sync_env_deps.py": ("sync_env_deps.py", "def main"),
    "scripts/policy_context.py": ("policy_context.py", "def main"),
}

_CLI_PATHS: dict[str, tuple[str, ...]] = {
    "cli_module": (),
    "deps.guard": ("deps", "guard"),
    "deps.verify": ("deps", "verify"),
    "deps.reproducibility": ("deps", "reproducibility"),
    "tools.qa": ("tools", "qa"),
    "tools.coverage.guard": ("tools", "coverage", "guard"),
    "github.sync": ("github", "sync"),
    "github.copilot.prepare": ("github", "copilot", "prepare"),
}

_WORKFLOW_CHECKS: dict[str, tuple[str, Iterable[str]]] = {
    "ci.yml uses uv sync": ("ci.yml", ["uv sync --all-extras --dev"]),
    "airgap.yml runs doctor": ("airgap.yml", ["chiron doctor"]),
    "sync-env.yml runs synchroniser": (
        "sync-env.yml",
        ["python scripts/sync_env_deps.py"],
    ),
}

_DOCUMENTATION_CHECKS: dict[str, tuple[str, str]] = {
    "docs/DEPS_MODULES_STATUS.md": (
        "DEPS_MODULES_STATUS.md",
        "supply_chain.py",
    ),
    "docs/CI_REPRODUCIBILITY_VALIDATION.md": (
        "CI_REPRODUCIBILITY_VALIDATION.md",
        "supply chain integrity",
    ),
}


def check_script_imports() -> dict[str, bool]:
    """Validate that helper scripts exist and delegate to the expected modules."""

    scripts_dir = REPO_ROOT / "scripts"
    results: dict[str, bool] = {}

    for label, (filename, marker) in _SCRIPT_CHECKS.items():
        script_path = scripts_dir / filename
        if not script_path.exists():
            results[label] = False
            continue

        content = script_path.read_text(encoding="utf-8")
        results[label] = marker in content

    return results


def _load_cli_root() -> Any | None:
    try:
        from chiron import typer_cli
    except Exception:  # pragma: no cover - optional import guard
        return None

    try:
        return get_command(typer_cli.app)
    except Exception:  # pragma: no cover - defensive
        return None


def _has_command_path(root: Any, path: tuple[str, ...]) -> bool:
    current = root
    for segment in path:
        commands = getattr(current, "commands", {})
        if segment not in commands:
            return False
        current = commands[segment]
    return True


def check_cli_commands() -> dict[str, bool]:
    """Inspect the Typer CLI tree to ensure critical commands are wired up."""

    root = _load_cli_root()
    if root is None:
        return {"cli_module": False}

    results: dict[str, bool] = {}
    for label, path in _CLI_PATHS.items():
        if not path:
            results[label] = True
        else:
            results[label] = _has_command_path(root, path)

    return results


def check_workflow_integration() -> dict[str, bool]:
    """Ensure automation workflows call into the hardened tooling."""

    workflows_dir = REPO_ROOT / ".github" / "workflows"
    results: dict[str, bool] = {}

    for label, (filename, markers) in _WORKFLOW_CHECKS.items():
        workflow_path = workflows_dir / filename
        if not workflow_path.exists():
            results[label] = False
            continue

        content = workflow_path.read_text(encoding="utf-8")
        results[label] = all(marker in content for marker in markers)

    return results


def check_documentation() -> dict[str, bool]:
    """Verify documentation highlights the supply-chain hardening story."""

    docs_dir = REPO_ROOT / "docs"
    results: dict[str, bool] = {}

    for label, (filename, marker) in _DOCUMENTATION_CHECKS.items():
        doc_path = docs_dir / filename
        if not doc_path.exists():
            results[label] = False
            continue

        content = doc_path.read_text(encoding="utf-8")
        results[label] = marker in content

    return results


def main() -> int:
    """Run the verification checks and emit a human-readable summary."""

    print("🔍 Verifying Dependency Pipeline Setup")
    print("=" * 60)

    groups = {
        "📦 Checking Script Delegates": check_script_imports(),
        "🖥️  Checking CLI Commands": check_cli_commands(),
        "⚙️  Checking Workflow Integration": check_workflow_integration(),
        "📚 Checking Documentation": check_documentation(),
    }

    overall = True
    for heading, checks in groups.items():
        print(f"\n{heading}")
        for name, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {name}")
            overall &= passed

    print("\n" + "=" * 60)
    if overall:
        print("✅ All checks passed! Dependency pipeline is properly configured.")
        return 0

    print("❌ Some checks failed. Review the output above.")
    return 1


if __name__ == "__main__":  # pragma: no cover - manual invocation
    import sys

    sys.exit(main())
