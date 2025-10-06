from __future__ import annotations

import json
import stat
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import click
import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner
from rich.console import Console

from chiron.cli.main import (
    WheelhouseStep,
    _build_wheelhouse_plan,
    _resolve_executable,
    _run_command,
    _select_wheelhouse_extras,
    _write_manifest,
    _write_wheel_checksums,
    wheelhouse,
)
from chiron.planning import (
    ExecutionPlanStep,
    plan_by_key,
    render_execution_plan,
    render_execution_plan_table,
)


def test_wheelhouse_help_runs() -> None:
    """The wheelhouse command should expose help output."""

    runner = CliRunner()
    result = runner.invoke(wheelhouse, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.stdout


class TestResolveExecutable:
    """Tests for executable resolution helpers."""

    def test_returns_absolute_paths_verbatim(self, tmp_path: Path) -> None:
        """Absolute executables should be returned without modification."""

        executable = tmp_path / "tool"
        executable.write_text("#!/bin/sh\n", encoding="utf-8")
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)

        assert _resolve_executable(str(executable)) == str(executable)

    def test_uses_shutil_which_for_relative_paths(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Relative executables should fall back to ``shutil.which`` resolution."""

        calls: dict[str, Any] = {}

        def fake_which(executable: str) -> str | None:
            calls["executable"] = executable
            return f"/usr/bin/{executable}"

        monkeypatch.setattr("chiron.cli.main.shutil.which", fake_which)

        resolved = _resolve_executable("python")

        assert resolved == "/usr/bin/python"
        assert calls["executable"] == "python"

    def test_raises_click_error_when_missing(self, monkeypatch: MonkeyPatch) -> None:
        """``ClickException`` should be raised when executables cannot be found."""

        monkeypatch.setattr("chiron.cli.main.shutil.which", lambda _: None)

        with pytest.raises(click.ClickException):
            _resolve_executable("missing-tool")


class TestRunCommand:
    """Tests for subprocess invocation helpers."""

    def test_requires_command_arguments(self) -> None:
        """Running a command without arguments should raise a ``ClickException``."""

        with pytest.raises(click.ClickException):
            _run_command([])

    def test_invokes_subprocess_with_resolved_executable(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """The helper should resolve and pass the executable to ``subprocess.run``."""

        invocation: dict[str, Any] = {}

        def fake_resolve(executable: str) -> str:
            invocation["resolved"] = executable
            return f"/bin/{executable}"

        monkeypatch.setattr("chiron.cli.main._resolve_executable", fake_resolve)

        def fake_run(command: Sequence[str], **kwargs: Any) -> str:
            invocation["command"] = list(command)
            invocation["kwargs"] = kwargs
            return "result"

        monkeypatch.setattr("chiron.cli.main.subprocess.run", fake_run)

        result = _run_command(["echo", "hello"], check=True)

        assert result == "result"
        assert invocation["resolved"] == "echo"
        assert invocation["command"][0] == "/bin/echo"
        assert invocation["command"][1:] == ["hello"]
        assert invocation["kwargs"] == {"check": True}


class TestWheelhouseHelpers:
    """Tests for wheelhouse manifest and checksum helpers."""

    def test_write_wheel_checksums(self, tmp_path: Path) -> None:
        """Checksums should be written for each wheel file in the directory."""

        wheel = tmp_path / "example-0.1.0-py3-none-any.whl"
        wheel.write_bytes(b"wheel-data")

        checksum_path = _write_wheel_checksums(tmp_path)

        assert checksum_path is not None
        assert checksum_path.name == "wheelhouse.sha256"

        contents = checksum_path.read_text(encoding="utf-8").strip()
        digest, filename = contents.split(maxsplit=1)
        assert filename == wheel.name
        assert len(digest) == 64  # sha256 hex digest length

    def test_write_manifest_outputs_expected_payload(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Manifest generation should include extras, dev flags, and commit info."""

        target = tmp_path / "manifest.json"
        monkeypatch.setattr("chiron.cli.main._current_git_commit", lambda: "abc1234")

        _write_manifest(target, ["dev", "docs"])

        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["extras"] == ["dev", "docs"]
        assert data["include_dev"] is True
        assert data["commit"] == "abc1234"
        assert "generated_at" in data
        assert data["create_archive"] is False

        # ``generated_at`` timestamps should be ISO formatted.
        assert "T" in data["generated_at"]


class TestWheelhousePlanning:
    """Tests for wheelhouse planning and option helpers."""

    def test_select_wheelhouse_extras_deduplicates_case_insensitive(self) -> None:
        """Extras should be normalised while preserving order."""

        selected = _select_wheelhouse_extras(
            ("Dev", "docs", "dev", " test "),
            base_only=False,
            include_all_extras=False,
            default_extras=("dev", "test"),
        )

        assert selected == ["Dev", "docs", "test"]

    def test_select_wheelhouse_extras_supports_base_only_mode(self) -> None:
        """Base-only mode should ignore extras except the explicit 'all' toggle."""

        selected = _select_wheelhouse_extras(
            ("dev",),
            base_only=True,
            include_all_extras=True,
            default_extras=("dev", "test"),
        )

        assert selected == ["all"]

    def test_build_wheelhouse_plan_generates_expected_commands(self, tmp_path: Path) -> None:
        """Planning helper should outline the required commands in execution order."""

        plan = _build_wheelhouse_plan(
            wheelhouse_path=tmp_path / "wheelhouse",
            requirements_path=tmp_path / "wheelhouse" / "requirements.txt",
            extras=["dev"],
            with_sbom=True,
            with_signatures=True,
        )

        assert plan[0] == WheelhouseStep(
            key="freeze",
            description="Freeze dependency manifest",
            command=[
                "uv",
                "pip",
                "compile",
                "pyproject.toml",
                "--generate-hashes",
                "-o",
                str(tmp_path / "wheelhouse" / "requirements.txt"),
                "--extra",
                "dev",
            ],
        )

        assert plan[1] == WheelhouseStep(
            key="download",
            description="Download dependency wheels",
            command=[
                sys.executable,
                "-m",
                "pip",
                "download",
                "-d",
                str(tmp_path / "wheelhouse"),
                "-r",
                str(tmp_path / "wheelhouse" / "requirements.txt"),
            ],
        )

        assert plan[2] == WheelhouseStep(
            key="build",
            description="Build project wheel",
            command=[
                "uv",
                "build",
                "--wheel",
                "-o",
                str(tmp_path / "wheelhouse"),
            ],
        )

        sbom_step = plan[3]
        assert sbom_step.key == "sbom"
        assert sbom_step.description == "Generate SBOM"
        assert sbom_step.command == [
            "syft",
            str(tmp_path / "wheelhouse"),
            "-o",
            "cyclonedx-json=sbom.json",
        ]

        signing_step = plan[4]
        assert signing_step.key == "sign"
        assert signing_step.description == "Sign artifacts"
        assert signing_step.command is None

    def test_render_execution_plan_formats_commands(self) -> None:
        """Execution plan formatting should quote commands deterministically."""

        plan = [
            ExecutionPlanStep(
                key="freeze",
                description="Freeze",
                command=("uv", "pip", "compile", "pyproject.toml"),
            ),
            ExecutionPlanStep(key="sign", description="Sign", command=None),
        ]

        lines = render_execution_plan(plan)

        assert lines[0].startswith("1. Freeze: uv pip compile pyproject.toml")
        assert lines[1] == "2. Sign"

    def test_render_execution_plan_table_includes_placeholders(self) -> None:
        """Rich table rendering should surface numbered steps and placeholders."""

        plan = [
            ExecutionPlanStep(
                key="freeze",
                description="Freeze",
                command=("uv", "pip"),
            ),
            ExecutionPlanStep(key="sign", description="Sign", command=None),
        ]

        table = render_execution_plan_table(plan, title="Example")
        recorded = Console(record=True)
        recorded.print(table)
        output = recorded.export_text()

        assert "Example" in output
        assert "1. Freeze" in output
        assert "uv pip" in output
        assert "2. Sign" in output
        assert "—" in output

    def test_plan_by_key_enforces_unique_keys(self) -> None:
        """Duplicate plan keys should raise a ``ValueError`` for safety."""

        plan = [
            ExecutionPlanStep(key="freeze", description="Freeze", command=("uv",)),
            ExecutionPlanStep(key="freeze", description="Again", command=("uv",)),
        ]

        with pytest.raises(ValueError):
            plan_by_key(plan)

    def test_wheelhouse_dry_run_outputs_execution_plan(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Dry-run execution should present the rich table execution plan."""

        recorded_console = Console(record=True)
        monkeypatch.setattr("chiron.cli.main.console", recorded_console)

        ctx = click.Context(
            wheelhouse,
            obj={
                "dry_run": True,
                "verbose": False,
                "json_output": False,
                "config": {},
            },
        )

        callback = wheelhouse.callback.__wrapped__  # type: ignore[attr-defined]

        with ctx:
            callback(
                ctx,
                output_dir=str(tmp_path),
                extras=("Dev", "docs"),
                base_only=False,
                include_all_extras=True,
                clean=True,
                with_sbom=False,
                with_signatures=False,
            )

        output = recorded_console.export_text()
        assert "Would create wheelhouse" in output
        assert "Wheelhouse Execution Plan" in output
        assert "1. Freeze dependency manifest" in output
        assert "uv pip compile" in output
        assert "Extras: Dev,docs,all" in output

    def test_wheelhouse_executes_plan_in_order(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Non-dry-run execution should honour the generated plan order."""

        commands: list[Sequence[str]] = []

        def fake_run(command: Sequence[str], **_: Any) -> subprocess.CompletedProcess[str]:
            commands.append(tuple(command))
            completed = subprocess.CompletedProcess(command, 0, "", "")
            return completed

        monkeypatch.setattr("chiron.cli.main._run_command", fake_run)
        monkeypatch.setattr("chiron.cli.main._current_git_commit", lambda: "deadbeef")

        ctx = click.Context(
            wheelhouse,
            obj={
                "dry_run": False,
                "verbose": False,
                "json_output": False,
                "config": {},
            },
        )

        callback = wheelhouse.callback.__wrapped__  # type: ignore[attr-defined]

        with ctx:
            callback(
                ctx,
                output_dir=str(tmp_path / "out"),
                extras=(),
                base_only=True,
                include_all_extras=False,
                clean=True,
                with_sbom=False,
                with_signatures=False,
            )

        command_keys = [command[0] for command in commands]
        assert command_keys[:3] == ["uv", sys.executable, "uv"]
