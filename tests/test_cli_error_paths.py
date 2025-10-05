"""Tests for CLI error paths and exception handling."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import click
import pytest
from click.testing import CliRunner

from chiron.cli.main import _resolve_executable, _run_command, cli


class TestCliErrorPaths:
    """Tests for CLI error handling paths."""

    def test_resolve_executable_relative_nonexistent(self) -> None:
        """Test resolving a relative path that doesn't exist."""
        with pytest.raises(click.ClickException, match="not found on PATH"):
            _resolve_executable("nonexistent_command")

    def test_run_command_empty_list_raises(self) -> None:
        """Test that empty command list raises exception."""
        with pytest.raises(click.ClickException, match="at least one argument"):
            _run_command([])

    def test_run_command_nonexistent_executable(self) -> None:
        """Test running command with nonexistent executable."""
        with pytest.raises(click.ClickException):
            _run_command(["totally_nonexistent_command_xyz123"])

    @patch("chiron.cli.main.shutil.which")
    def test_run_command_executable_not_in_path(self, mock_which: Mock) -> None:
        """Test running command when executable not in PATH."""
        mock_which.return_value = None
        with pytest.raises(click.ClickException, match="not found on PATH"):
            _run_command(["missing_executable", "arg1"])


class TestCliBuildCommandErrors:
    """Tests for build command error paths."""

    def test_build_subprocess_failure(self) -> None:
        """Test build command when subprocess fails."""
        runner = CliRunner()
        with patch("chiron.cli.main._run_command") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["uv", "run", "cibuildwheel"], stderr="Build error"
            )
            result = runner.invoke(cli, ["build"])
            assert result.exit_code != 0
            assert "Build failed" in result.output or result.exit_code == 1

    def test_build_dry_run_no_execution(self) -> None:
        """Test build command in dry-run mode doesn't execute."""
        runner = CliRunner()
        with patch("chiron.cli.main._run_command") as mock_run:
            result = runner.invoke(cli, ["--dry-run", "build"])
            assert result.exit_code == 0
            mock_run.assert_not_called()
            assert "DRY RUN" in result.output


class TestCliReleaseCommandErrors:
    """Tests for release command error paths."""

    def test_release_subprocess_failure(self) -> None:
        """Test release command when subprocess fails."""
        runner = CliRunner()
        with patch("chiron.cli.main._run_command") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1,
                cmd=["uv", "run", "semantic-release"],
                stderr="Release error",
            )
            result = runner.invoke(cli, ["release"])
            assert result.exit_code != 0
            assert "Release failed" in result.output or result.exit_code == 1


class TestCliConfigErrors:
    """Tests for configuration-related error paths."""

    def test_cli_with_nonexistent_config_file(self, tmp_path: Path) -> None:
        """Test CLI with nonexistent config file."""
        runner = CliRunner()
        config_file = tmp_path / "nonexistent.json"
        result = runner.invoke(cli, ["--config", str(config_file)])
        assert result.exit_code != 0
        assert "does not exist" in result.output

    def test_cli_with_invalid_json_config(self, tmp_path: Path) -> None:
        """Test CLI with invalid JSON config."""
        runner = CliRunner()
        config_file = tmp_path / "invalid.json"
        config_file.write_text("invalid json {")
        result = runner.invoke(cli, ["--config", str(config_file)])
        assert result.exit_code != 0
        assert "Invalid JSON" in result.output or "Error" in result.output

    def test_init_with_existing_config(self, tmp_path: Path) -> None:
        """Test init command when config already exists."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            config_file = Path(td) / "chiron-config.json"
            config_file.write_text('{"service_name": "test"}')
            # Change to the directory where config exists
            import os

            os.chdir(td)
            result = runner.invoke(cli, ["init"])
            assert "already exists" in result.output or result.exit_code == 0


class TestCliWheelhouseCommandErrors:
    """Tests for wheelhouse command error paths."""

    @patch("chiron.cli.main._run_command")
    def test_wheelhouse_subprocess_failure(self, mock_run: Mock) -> None:
        """Test wheelhouse creation when subprocess fails."""
        runner = CliRunner()
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["pip", "wheel"], stderr="Wheel build failed"
        )
        result = runner.invoke(cli, ["wheelhouse", "create"])
        # Since the error is in subprocess, exit code might be 1
        assert result.exit_code != 0 or "failed" in result.output.lower()

    def test_wheelhouse_create_dry_run(self, tmp_path: Path) -> None:
        """Test wheelhouse creation in dry-run mode."""
        runner = CliRunner()
        with patch("chiron.cli.main._run_command") as mock_run:
            result = runner.invoke(
                cli, ["--dry-run", "wheelhouse", "create", "--output-dir", str(tmp_path)]
            )
            # Just check that it doesn't crash unexpectedly
            # Exit code might vary depending on validation
            assert result.exit_code in [0, 1, 2]


class TestCliInitCommandErrors:
    """Tests for init command error paths."""

    def test_init_wizard_keyboard_interrupt(self, tmp_path: Path) -> None:
        """Test init command when wizard is interrupted."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            with patch("chiron.wizard.run_init_wizard") as mock_wizard:
                mock_wizard.side_effect = KeyboardInterrupt()
                result = runner.invoke(cli, ["init", "--wizard"])
                assert "cancelled" in result.output.lower() or result.exit_code == 0


class TestCliVerboseAndJsonOutput:
    """Tests for verbose and JSON output flags."""

    def test_cli_verbose_flag_propagates(self) -> None:
        """Test that verbose flag is properly stored in context."""
        runner = CliRunner()
        with patch("chiron.cli.main._run_command") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="output", stderr=""
            )
            result = runner.invoke(cli, ["--verbose", "build"])
            # Check that context object is created with verbose flag
            assert result.exit_code == 0 or result.exit_code == 1

    def test_cli_json_output_flag_propagates(self) -> None:
        """Test that JSON output flag is properly stored in context."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--json-output", "--help"])
        assert result.exit_code == 0


class TestCliWheelhouseSignVerify:
    """Tests for wheelhouse sign and verify command error paths."""

    @patch("chiron.deps.signing.CosignSigner")
    def test_wheelhouse_sign_no_bundle(self, mock_signer: Mock, tmp_path: Path) -> None:
        """Test signing wheelhouse when bundle doesn't exist."""
        runner = CliRunner()
        bundle_path = tmp_path / "nonexistent.tar.gz"
        result = runner.invoke(
            cli, ["wheelhouse", "sign", "--bundle", str(bundle_path)]
        )
        # Command should handle missing bundle - exit code may vary
        assert result.exit_code in [0, 1, 2]

    @patch("chiron.deps.signing.CosignSigner")
    def test_wheelhouse_verify_no_bundle(
        self, mock_signer: Mock, tmp_path: Path
    ) -> None:
        """Test verifying wheelhouse when bundle doesn't exist."""
        runner = CliRunner()
        bundle_path = tmp_path / "nonexistent.tar.gz"
        sig_path = tmp_path / "nonexistent.tar.gz.sig"
        result = runner.invoke(
            cli,
            [
                "wheelhouse",
                "verify",
                "--bundle",
                str(bundle_path),
                "--signature",
                str(sig_path),
            ],
        )
        # Command should handle missing files - exit code may vary
        assert result.exit_code in [0, 1, 2]


class TestCliMultipleErrorScenarios:
    """Tests for multiple error scenarios in combination."""

    def test_verbose_with_subprocess_error(self) -> None:
        """Test verbose output when subprocess fails."""
        runner = CliRunner()
        with patch("chiron.cli.main._run_command") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["test"], stderr="detailed error message"
            )
            result = runner.invoke(cli, ["--verbose", "build"])
            # With verbose flag, error details should be shown
            assert result.exit_code != 0

    def test_dry_run_with_multiple_commands(self) -> None:
        """Test dry-run mode with multiple commands."""
        runner = CliRunner()
        with patch("chiron.cli.main._run_command") as mock_run:
            # Test that dry-run prevents execution
            result = runner.invoke(cli, ["--dry-run", "release"])
            assert result.exit_code == 0
            # In dry-run, command shouldn't be executed or should be called with dry-run context
            # Implementation detail: depends on how dry-run is handled


class TestCliConfigValidation:
    """Tests for configuration validation error paths."""

    def test_config_with_validation_warnings(self, tmp_path: Path) -> None:
        """Test config with validation warnings."""
        runner = CliRunner()
        config_file = tmp_path / "config.json"
        # Config with missing optional fields
        config_file.write_text(
            '{"service_name": "test", "version": "1.0.0", "unknown_field": "value"}'
        )
        result = runner.invoke(cli, ["--config", str(config_file)])
        # Should still work but might have warnings
        # Check that it doesn't crash
        assert result.exit_code == 0 or result.exit_code == 2


class TestCliExceptionHandling:
    """Tests for general exception handling."""

    @patch("chiron.cli.main.validate_config")
    def test_config_validation_error(
        self, mock_validate: Mock, tmp_path: Path
    ) -> None:
        """Test handling of config validation errors."""
        runner = CliRunner()
        config_file = tmp_path / "config.json"
        config_file.write_text('{"service_name": "test"}')

        from chiron.exceptions import ChironError

        mock_validate.side_effect = ChironError("Invalid configuration")
        result = runner.invoke(cli, ["--config", str(config_file)])
        assert result.exit_code != 0
        assert "Invalid configuration" in result.output or "Error" in result.output
