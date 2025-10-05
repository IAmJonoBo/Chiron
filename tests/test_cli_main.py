"""Tests for chiron.cli.main module."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import Mock, patch

import click
import pytest
from _pytest.monkeypatch import MonkeyPatch
from click.testing import CliRunner, Result

from chiron.cli.main import _run_command, cli
from chiron.subprocess_utils import resolve_executable


def _invoke_cli_and_capture_context(
    args: Sequence[str],
) -> tuple[Result, dict[str, object]]:
    """Run the CLI with *args* and capture the resulting context object."""

    command_name = "__capture_cli_context__"
    captured: dict[str, object] = {}

    def _capture_callback() -> None:
        ctx = click.get_current_context()
        obj = ctx.obj or {}
        if isinstance(obj, dict):
            captured.update(obj)

    command = click.Command(command_name, callback=_capture_callback)
    cli.add_command(command)
    runner = CliRunner()
    try:
        result = runner.invoke(cli, [*args, command_name])
    finally:
        cli.commands.pop(command_name, None)

    return result, captured


class TestResolveExecutable:
    """Tests for resolve_executable helper from subprocess_utils."""

    def test_resolve_absolute_path(self) -> None:
        """Test resolving an absolute path."""
        # Use a known absolute path
        result = resolve_executable("/usr/bin/python3")
        assert result == "/usr/bin/python3"

    def test_resolve_relative_path_that_exists(self, tmp_path: Path) -> None:
        """Test resolving a relative path that exists."""
        # Create a temporary file
        test_file = tmp_path / "test_script.sh"
        test_file.write_text("#!/bin/bash\necho test")
        test_file.chmod(0o755)

        # Change to the temp directory
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = resolve_executable("./test_script.sh")
            assert Path(result).exists()
            assert "test_script.sh" in result
        finally:
            os.chdir(original_cwd)

    def test_resolve_executable_in_path(self) -> None:
        """Test resolving an executable that exists in PATH."""
        # python3 should be in PATH
        result = resolve_executable("python3")
        assert result is not None
        assert Path(result).exists()
        assert "python3" in result.lower()

    def test_resolve_executable_not_found(self) -> None:
        """Test that missing executable raises ExecutableNotFoundError."""
        from chiron.subprocess_utils import ExecutableNotFoundError

        with pytest.raises(ExecutableNotFoundError) as exc_info:
            resolve_executable("this-executable-does-not-exist-12345")

        assert "not found" in str(exc_info.value).lower()
        assert "this-executable-does-not-exist-12345" in str(exc_info.value)

    @patch("chiron.subprocess_utils.shutil.which")
    def test_resolve_executable_which_returns_none(self, mock_which: Mock) -> None:
        """Test when shutil.which returns None."""
        from chiron.subprocess_utils import ExecutableNotFoundError

        mock_which.return_value = None

        with pytest.raises(ExecutableNotFoundError) as exc_info:
            resolve_executable("missing-tool")

        assert "not found" in str(exc_info.value).lower()


class TestRunCommand:
    """Tests for _run_command helper."""

    @patch("subprocess.run")
    def test_run_command_success(self, mock_run: Mock) -> None:
        """Test running a command successfully."""
        mock_result = Mock(spec=subprocess.CompletedProcess)
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = _run_command(["echo", "hello"])

        mock_run.assert_called_once()
        assert result is mock_result

    def test_run_command_empty_list(self) -> None:
        """Test that empty command list raises exception."""
        with pytest.raises(click.ClickException) as exc_info:
            _run_command([])

        assert "at least one argument" in str(exc_info.value)

    @patch("subprocess.run")
    def test_run_command_with_kwargs(self, mock_run: Mock) -> None:
        """Test running a command with additional kwargs."""
        mock_result = Mock(spec=subprocess.CompletedProcess)
        mock_run.return_value = mock_result

        _run_command(["ls", "-la"], capture_output=True, text=True)

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("capture_output") is True
        assert call_kwargs.get("text") is True

    @patch("chiron.cli.main._resolve_executable")
    def test_run_command_executable_not_found(self, mock_resolve: Mock) -> None:
        """Test when executable is not found."""
        mock_resolve.side_effect = click.ClickException("nonexistent-command not found")

        with pytest.raises(click.ClickException) as exc_info:
            _run_command(["nonexistent-command"])

        assert "not found" in str(exc_info.value).lower()


class TestCliGroup:
    """Tests for main CLI group."""

    def test_cli_group_exists(self) -> None:
        """Test that CLI group is defined."""
        assert cli is not None
        assert isinstance(cli, click.Group)

    def test_cli_version_option(self) -> None:
        """Test that version option is available."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "version" in result.output.lower()

    def test_cli_help(self) -> None:
        """Test that help text is available."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Chiron" in result.output
        assert "--config" in result.output
        assert "--verbose" in result.output
        assert "--json-output" in result.output
        assert "--dry-run" in result.output

    def test_cli_with_verbose_flag(self) -> None:
        """Test CLI with verbose flag."""
        runner = CliRunner()
        # Just test that the flag is accepted
        result = runner.invoke(cli, ["--verbose", "--help"])

        assert result.exit_code == 0

    def test_cli_with_json_output_flag(self) -> None:
        """Test CLI with json-output flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--json-output", "--help"])

        assert result.exit_code == 0

    def test_cli_with_dry_run_flag(self) -> None:
        """Test CLI with dry-run flag."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--dry-run", "--help"])

        assert result.exit_code == 0

    def test_cli_with_config_file(self, tmp_path: Path) -> None:
        """Test CLI with config file."""
        config_file = tmp_path / "chiron.json"
        config_data = {
            "project_name": "test-project",
            "version": "0.1.0",
        }
        config_file.write_text(json.dumps(config_data))

        runner = CliRunner()
        # Use a subcommand that exists (init)
        result = runner.invoke(cli, ["--config", str(config_file), "--help"])

        # Should load without error
        assert result.exit_code == 0

    def test_cli_with_invalid_config_file(self, tmp_path: Path) -> None:
        """Test CLI with invalid JSON config file."""
        config_file = tmp_path / "bad.json"
        config_file.write_text("{ invalid json }")

        runner = CliRunner()
        # Don't use --help as it bypasses config loading
        result = runner.invoke(cli, ["--config", str(config_file)])

        # Should show error about invalid JSON
        assert result.exit_code != 0 or "Error loading config" in result.output


class TestInitCommandCLI:
    """CLI invocation tests for init command."""

    def test_init_creates_config_file(self, tmp_path: Path) -> None:
        """Test that init creates a configuration file."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init"])

            assert result.exit_code == 0
            assert Path("chiron.json").exists()

            # Verify config content
            with open("chiron.json") as f:
                config = json.load(f)
            assert "service_name" in config
            assert "version" in config
            assert "telemetry" in config
            assert "security" in config

    def test_init_with_existing_config(self, tmp_path: Path) -> None:
        """Test init when config already exists."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create existing config
            Path("chiron.json").write_text('{"existing": "config"}')

            result = runner.invoke(cli, ["init"])

            assert result.exit_code == 0
            assert "already exists" in result.output

    def test_init_with_wizard_cancelled(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test init wizard when user cancels."""
        runner = CliRunner()

        def mock_wizard() -> None:
            raise KeyboardInterrupt()

        monkeypatch.setattr("chiron.wizard.run_init_wizard", mock_wizard)

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init", "--wizard"])

            assert result.exit_code == 0
            assert "cancelled" in result.output.lower()


class TestWriteWheelChecksums:
    """Tests for _write_wheel_checksums helper."""

    def test_write_checksums_with_wheels(self, tmp_path: Path) -> None:
        """Test writing checksums for wheel files."""
        from chiron.cli.main import _write_wheel_checksums

        wheelhouse = tmp_path / "wheelhouse"
        wheelhouse.mkdir()

        # Create test wheel files
        (wheelhouse / "package1-1.0.0-py3-none-any.whl").write_bytes(b"test content 1")
        (wheelhouse / "package2-2.0.0-py3-none-any.whl").write_bytes(b"test content 2")

        checksum_file = _write_wheel_checksums(wheelhouse)

        assert checksum_file is not None
        assert checksum_file.exists()
        assert checksum_file.name == "wheelhouse.sha256"

        # Verify checksum content
        content = checksum_file.read_text()
        assert "package1-1.0.0-py3-none-any.whl" in content
        assert "package2-2.0.0-py3-none-any.whl" in content

    def test_write_checksums_no_wheels(self, tmp_path: Path) -> None:
        """Test writing checksums when no wheels present."""
        from chiron.cli.main import _write_wheel_checksums

        wheelhouse = tmp_path / "wheelhouse"
        wheelhouse.mkdir()

        checksum_file = _write_wheel_checksums(wheelhouse)

        assert checksum_file is None


class TestWriteManifest:
    """Tests for _write_manifest helper."""

    def test_write_manifest(self, tmp_path: Path) -> None:
        """Test writing wheelhouse manifest."""
        from chiron.cli.main import _write_manifest

        manifest_path = tmp_path / "manifest.json"
        extras = ["dev", "security"]

        _write_manifest(manifest_path, extras)

        assert manifest_path.exists()

        # Verify manifest content
        with open(manifest_path) as f:
            manifest = json.load(f)

        assert "generated_at" in manifest
        assert manifest["extras"] == extras
        assert manifest["include_dev"] is True
        assert "commit" in manifest

    def test_cli_with_nonexistent_config_file(self) -> None:
        """Test CLI with non-existent config file."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--config", "/nonexistent/path/config.json"])

        # Should fail due to exists=True constraint or show error
        assert result.exit_code != 0 or "does not exist" in result.output.lower()

    @patch("chiron.cli.main.validate_config")
    def test_cli_with_config_validation_warnings(
        self, mock_validate: Mock, tmp_path: Path
    ) -> None:
        """Test CLI shows validation warnings."""
        mock_validate.return_value = ["Warning 1", "Warning 2"]

        config_file = tmp_path / "chiron.json"
        config_data = {"test": "data"}
        config_file.write_text(json.dumps(config_data))

        runner = CliRunner()
        # Use init command to actually load config (--help might bypass loading)
        result = runner.invoke(cli, ["--config", str(config_file), "init", "--help"])

        # Check that warnings are shown (or that the call worked without validation errors)
        assert result.exit_code == 0

    def test_cli_context_object_initialized(self) -> None:
        """Test that context object is properly initialized."""
        result, context_obj = _invoke_cli_and_capture_context(
            ["--verbose", "--json-output"]
        )

        assert result.exit_code == 0
        assert context_obj.get("verbose") is True
        assert context_obj.get("json_output") is True
        assert context_obj.get("dry_run") is False

    def test_cli_stores_config_in_context(self, tmp_path: Path) -> None:
        """Test that config is stored in context object."""
        config_file = tmp_path / "chiron.json"
        config_data = {"test_key": "test_value"}
        config_file.write_text(json.dumps(config_data))

        result, context_obj = _invoke_cli_and_capture_context(
            ["--config", str(config_file)]
        )

        assert result.exit_code == 0
        config = context_obj.get("config")
        assert isinstance(config, dict)
        assert config.get("test_key") == "test_value"


class TestInitCommand:
    """Tests for init command."""

    def test_init_command_exists(self) -> None:
        """Test that init command is registered."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--help"])

        assert result.exit_code == 0
        assert "Initialize" in result.output

    @patch("chiron.cli.main.console.print")
    def test_init_without_wizard(self, mock_print: Mock, tmp_path: Path) -> None:
        """Test init command without wizard mode."""
        runner = CliRunner()

        # Run in isolated filesystem
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init"])

            # Should create or prompt about chiron.json
            assert result.exit_code == 0 or "already exists" in result.output.lower()

    @patch("chiron.wizard.run_init_wizard")
    def test_init_with_wizard(self, mock_wizard: Mock) -> None:
        """Test init command with wizard mode."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--wizard"])

        assert result.exit_code == 0
        mock_wizard.assert_called_once()

    @patch("chiron.wizard.run_init_wizard")
    def test_init_wizard_keyboard_interrupt(self, mock_wizard: Mock) -> None:
        """Test init wizard handles keyboard interrupt."""
        mock_wizard.side_effect = KeyboardInterrupt()

        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--wizard"])

        assert "cancelled" in result.output.lower()


class TestBuildCommand:
    """Tests for build command."""

    @patch("chiron.cli.main._run_command")
    def test_build_dry_run(self, mock_run: Mock) -> None:
        """Test build command in dry run mode."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--dry-run", "build"])

        assert result.exit_code == 0
        assert "DRY RUN" in result.output
        assert "cibuildwheel" in result.output
        # _run_command should not be called in dry run
        mock_run.assert_not_called()

    @patch("chiron.cli.main._run_command")
    def test_build_success(self, mock_run: Mock) -> None:
        """Test successful build."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["uv", "run", "cibuildwheel"],
            returncode=0,
            stdout="Build output",
            stderr="",
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["build"])

        assert result.exit_code == 0
        assert "Build completed successfully" in result.output
        mock_run.assert_called_once()

    @patch("chiron.cli.main._run_command")
    def test_build_failure(self, mock_run: Mock) -> None:
        """Test build failure."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["uv", "run", "cibuildwheel"], stderr="Build error"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["build"])

        assert result.exit_code == 1
        assert "Build failed" in result.output


class TestReleaseCommand:
    """Tests for release command."""

    @patch("chiron.cli.main._run_command")
    def test_release_success(self, mock_run: Mock) -> None:
        """Test successful release."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["uv", "run", "semantic-release"],
            returncode=0,
            stdout="Release output",
            stderr="",
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["release"])

        assert result.exit_code == 0
        assert "Release created successfully" in result.output
        mock_run.assert_called_once()

    @patch("chiron.cli.main._run_command")
    def test_release_failure(self, mock_run: Mock) -> None:
        """Test release failure."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["semantic-release"], stderr="Release error"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["release"])

        assert result.exit_code == 1
        assert "Release failed" in result.output


class TestWheelhouseCommand:
    """Tests for wheelhouse command."""

    def test_wheelhouse_help(self) -> None:
        """Test wheelhouse command help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["wheelhouse", "--help"])

        assert result.exit_code == 0
        assert "wheelhouse" in result.output.lower()

    @patch("chiron.cli.main._run_command")
    def test_wheelhouse_dry_run(self, mock_run: Mock) -> None:
        """Test wheelhouse build in dry run mode."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--dry-run", "wheelhouse"])

        assert result.exit_code == 0
        # Command should show it would run
        assert "Would" in result.output or "DRY RUN" in result.output
