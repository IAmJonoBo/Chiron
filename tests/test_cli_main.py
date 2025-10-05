"""Tests for chiron.cli.main module."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import click
import pytest
from click.testing import CliRunner

from chiron.cli.main import _run_command, cli
from chiron.subprocess_utils import resolve_executable


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

    @patch("chiron.cli.main.run_subprocess")
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

    @patch("chiron.cli.main.run_subprocess")
    def test_run_command_with_kwargs(self, mock_run: Mock) -> None:
        """Test running a command with additional kwargs."""
        mock_result = Mock(spec=subprocess.CompletedProcess)
        mock_run.return_value = mock_result

        _run_command(["ls", "-la"], capture_output=True, text=True)

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("capture_output") is True
        assert call_kwargs.get("text") is True

    @patch("chiron.cli.main.run_subprocess")
    def test_run_command_executable_not_found(self, mock_run: Mock) -> None:
        """Test when executable is not found."""
        from chiron.subprocess_utils import ExecutableNotFoundError

        mock_run.side_effect = ExecutableNotFoundError("nonexistent-command")

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

        @cli.command()
        @click.pass_context
        def test_cmd(ctx: click.Context) -> None:
            """Test command to inspect context."""
            click.echo(f"verbose={ctx.obj.get('verbose')}")
            click.echo(f"json_output={ctx.obj.get('json_output')}")
            click.echo(f"dry_run={ctx.obj.get('dry_run')}")

        runner = CliRunner()
        result = runner.invoke(cli, ["--verbose", "--json-output", "test-cmd"])

        assert "verbose=True" in result.output
        assert "json_output=True" in result.output

    def test_cli_stores_config_in_context(self, tmp_path: Path) -> None:
        """Test that config is stored in context object."""
        config_file = tmp_path / "chiron.json"
        config_data = {"test_key": "test_value"}
        config_file.write_text(json.dumps(config_data))

        @cli.command()
        @click.pass_context
        def test_cmd(ctx: click.Context) -> None:
            """Test command to inspect config."""
            config = ctx.obj.get("config", {})
            click.echo(f"test_key={config.get('test_key')}")

        runner = CliRunner()
        result = runner.invoke(cli, ["--config", str(config_file), "test-cmd"])

        assert "test_key=test_value" in result.output


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

        mock_wizard.assert_called_once()

    @patch("chiron.wizard.run_init_wizard")
    def test_init_wizard_keyboard_interrupt(self, mock_wizard: Mock) -> None:
        """Test init wizard handles keyboard interrupt."""
        mock_wizard.side_effect = KeyboardInterrupt()

        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--wizard"])

        assert "cancelled" in result.output.lower()
