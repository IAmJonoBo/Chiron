"""Tests for dependency verification helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pytest

from chiron.deps import verify


@dataclass
class StubCommand:
    """Lightweight stand-in for Click/Typer command groups."""

    commands: dict[str, StubCommand]


@pytest.fixture()
def stub_cli_root() -> StubCommand:
    """Create a nested command structure without importing Typer."""

    return StubCommand(
        commands={
            "deps": StubCommand(
                commands={
                    "guard": StubCommand(commands={}),
                    "verify": StubCommand(commands={}),
                    "reproducibility": StubCommand(commands={}),
                }
            ),
            "tools": StubCommand(
                commands={
                    "qa": StubCommand(commands={}),
                    "coverage": StubCommand(
                        commands={"guard": StubCommand(commands={})}
                    ),
                }
            ),
            "github": StubCommand(
                commands={
                    "sync": StubCommand(commands={}),
                    "copilot": StubCommand(
                        commands={"prepare": StubCommand(commands={})}
                    ),
                }
            ),
            "plugin": StubCommand(commands={"list": StubCommand(commands={})}),
        }
    )


class TestCheckScriptImports:
    """Tests for ``check_script_imports``."""

    def _configure_scripts(self, tmp_path: Path, files: dict[str, str]) -> Path:
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        for name, content in files.items():
            (scripts_dir / name).write_text(content, encoding="utf-8")
        return scripts_dir

    def test_detects_valid_scripts(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._configure_scripts(
            tmp_path,
            {
                "preflight_deps.py": 'run_module("chiron.deps.preflight")\n',
                "sync_env_deps.py": "def main():\n    return 0\n",
                "policy_context.py": "def main():\n    return 0\n",
            },
        )

        monkeypatch.setattr(verify, "REPO_ROOT", tmp_path)
        results = verify.check_script_imports()

        assert all(results.values())

    def test_handles_missing_and_invalid_scripts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._configure_scripts(
            tmp_path,
            {
                "preflight_deps.py": "print('noop')\n",
            },
        )

        monkeypatch.setattr(verify, "REPO_ROOT", tmp_path)
        results = verify.check_script_imports()

        assert any(not passed for passed in results.values())


class TestCheckCliCommands:
    """Tests for ``check_cli_commands``."""

    def test_cli_structure_detected(
        self,
        stub_cli_root: StubCommand,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(verify, "_load_cli_root", lambda: stub_cli_root)
        results = verify.check_cli_commands()

        assert results["cli_module"] is True
        assert all(
            results[key]
            for key in (
                "deps.guard",
                "deps.verify",
                "deps.reproducibility",
                "tools.qa",
                "tools.coverage.guard",
                "github.sync",
                "github.copilot.prepare",
            )
        )

    def test_missing_command_path(
        self,
        stub_cli_root: StubCommand,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Remove the github copilot group to trigger a failure.
        pruned = stub_cli_root
        pruned.commands["github"].commands.pop("copilot")  # type: ignore[index]
        monkeypatch.setattr(verify, "_load_cli_root", lambda: pruned)

        results = verify.check_cli_commands()

        assert results["github.copilot.prepare"] is False

    def test_import_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(verify, "_load_cli_root", lambda: None)

        results = verify.check_cli_commands()

        assert results == {"cli_module": False}


class TestCheckWorkflowIntegration:
    """Tests for ``check_workflow_integration``."""

    def _write_workflow(self, root: Path, name: str, lines: Iterable[str]) -> None:
        workflow_dir = root / ".github" / "workflows"
        workflow_dir.mkdir(parents=True, exist_ok=True)
        (workflow_dir / name).write_text("\n".join(lines), encoding="utf-8")

    def test_workflow_checks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._write_workflow(
            tmp_path,
            "ci.yml",
            ["run: uv sync --all-extras --dev"],
        )
        self._write_workflow(
            tmp_path,
            "airgap.yml",
            ["run: chiron doctor"],
        )
        self._write_workflow(
            tmp_path,
            "sync-env.yml",
            ["run: python scripts/sync_env_deps.py"],
        )

        monkeypatch.setattr(verify, "REPO_ROOT", tmp_path)
        results = verify.check_workflow_integration()

        assert all(results.values())

    def test_missing_workflow_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._write_workflow(
            tmp_path,
            "ci.yml",
            ["run: echo noop"],
        )

        monkeypatch.setattr(verify, "REPO_ROOT", tmp_path)
        results = verify.check_workflow_integration()

        assert any(not passed for passed in results.values())


class TestCheckDocumentation:
    """Tests for ``check_documentation``."""

    def _write_docs(self, tmp_path: Path, files: dict[str, str]) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        for name, content in files.items():
            (docs_dir / name).write_text(content, encoding="utf-8")

    def test_documentation_presence(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._write_docs(
            tmp_path,
            {
                "DEPS_MODULES_STATUS.md": "supply_chain.py coverage",
                "CI_REPRODUCIBILITY_VALIDATION.md": "Verify supply chain integrity",
            },
        )

        monkeypatch.setattr(verify, "REPO_ROOT", tmp_path)
        results = verify.check_documentation()

        assert all(results.values())

    def test_missing_documentation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._write_docs(
            tmp_path,
            {"DEPS_MODULES_STATUS.md": "stub"},
        )

        monkeypatch.setattr(verify, "REPO_ROOT", tmp_path)
        results = verify.check_documentation()

        assert any(not passed for passed in results.values())
