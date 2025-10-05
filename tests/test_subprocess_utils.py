"""Tests for subprocess utilities."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chiron.subprocess_utils import (
    DEFAULT_TIMEOUTS,
    ExecutableNotFoundError,
    SubprocessTimeoutError,
    check_binary_availability,
    get_default_timeout,
    get_missing_binaries,
    probe_executable,
    resolve_executable,
    run_subprocess,
)


class TestProbeExecutable:
    """Tests for probe_executable function."""

    def test_probe_absolute_path_exists(self, tmp_path: Path) -> None:
        """Test probing an absolute path that exists."""
        executable = tmp_path / "test_exec"
        executable.touch()
        executable.chmod(0o755)

        result = probe_executable(str(executable))
        assert result == str(executable)

    def test_probe_absolute_path_not_exists(self, tmp_path: Path) -> None:
        """Test probing an absolute path that doesn't exist."""
        executable = tmp_path / "nonexistent"
        result = probe_executable(str(executable))
        assert result is None

    def test_probe_relative_path_with_parent(self, tmp_path: Path, monkeypatch) -> None:
        """Test probing a relative path with parent directory."""
        monkeypatch.chdir(tmp_path)
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        executable = subdir / "test_exec"
        executable.touch()
        executable.chmod(0o755)

        result = probe_executable("subdir/test_exec")
        assert result is not None
        assert Path(result).name == "test_exec"

    @patch("shutil.which")
    def test_probe_in_path(self, mock_which: MagicMock) -> None:
        """Test probing executable in PATH."""
        mock_which.return_value = "/usr/bin/python3"
        result = probe_executable("python3")
        assert result == "/usr/bin/python3"
        mock_which.assert_called_once_with("python3")

    @patch("shutil.which")
    def test_probe_not_in_path(self, mock_which: MagicMock) -> None:
        """Test probing executable not in PATH."""
        mock_which.return_value = None
        result = probe_executable("nonexistent_binary")
        assert result is None
        mock_which.assert_called_once_with("nonexistent_binary")


class TestResolveExecutable:
    """Tests for resolve_executable function."""

    @patch("chiron.subprocess_utils.probe_executable")
    def test_resolve_required_found(self, mock_probe: MagicMock) -> None:
        """Test resolving a required executable that is found."""
        mock_probe.return_value = "/usr/bin/uv"
        result = resolve_executable("uv", required=True)
        assert result == "/usr/bin/uv"

    @patch("chiron.subprocess_utils.probe_executable")
    def test_resolve_required_not_found(self, mock_probe: MagicMock) -> None:
        """Test resolving a required executable that is not found."""
        mock_probe.return_value = None
        with pytest.raises(ExecutableNotFoundError) as exc_info:
            resolve_executable("missing_tool", required=True)
        assert "missing_tool" in str(exc_info.value)
        assert exc_info.value.executable == "missing_tool"

    @patch("chiron.subprocess_utils.probe_executable")
    def test_resolve_not_required_found(self, mock_probe: MagicMock) -> None:
        """Test resolving a non-required executable that is found."""
        mock_probe.return_value = "/usr/local/bin/tool"
        result = resolve_executable("tool", required=False)
        assert result == "/usr/local/bin/tool"

    @patch("chiron.subprocess_utils.probe_executable")
    def test_resolve_not_required_not_found(self, mock_probe: MagicMock) -> None:
        """Test resolving a non-required executable that is not found."""
        mock_probe.return_value = None
        result = resolve_executable("optional_tool", required=False)
        assert result == "optional_tool"


class TestGetDefaultTimeout:
    """Tests for get_default_timeout function."""

    def test_known_executable(self) -> None:
        """Test getting timeout for known executables."""
        assert get_default_timeout(["uv", "pip", "install"]) == DEFAULT_TIMEOUTS["uv"]
        assert get_default_timeout(["syft", "."]) == DEFAULT_TIMEOUTS["syft"]
        assert get_default_timeout(["cosign", "sign"]) == DEFAULT_TIMEOUTS["cosign"]

    def test_unknown_executable(self) -> None:
        """Test getting timeout for unknown executable."""
        result = get_default_timeout(["unknown_command", "arg"])
        assert result == DEFAULT_TIMEOUTS["default"]

    def test_empty_command(self) -> None:
        """Test getting timeout for empty command."""
        result = get_default_timeout([])
        assert result == DEFAULT_TIMEOUTS["default"]

    def test_executable_with_path(self) -> None:
        """Test getting timeout for executable with path."""
        result = get_default_timeout(["/usr/bin/uv", "pip", "install"])
        assert result == DEFAULT_TIMEOUTS["uv"]


class TestRunSubprocess:
    """Tests for run_subprocess function."""

    @patch("subprocess.run")
    @patch("chiron.subprocess_utils.resolve_executable")
    def test_successful_execution(
        self, mock_resolve: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test successful subprocess execution."""
        mock_resolve.return_value = "/usr/bin/echo"
        mock_run.return_value = subprocess.CompletedProcess(
            args=["/usr/bin/echo", "hello"], returncode=0
        )

        result = run_subprocess(["echo", "hello"])

        assert result.returncode == 0
        mock_resolve.assert_called_once_with("echo", required=True)
        mock_run.assert_called_once()
        # Check that timeout was set to default
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == DEFAULT_TIMEOUTS["default"]

    @patch("subprocess.run")
    @patch("chiron.subprocess_utils.resolve_executable")
    def test_custom_timeout(self, mock_resolve: MagicMock, mock_run: MagicMock) -> None:
        """Test subprocess execution with custom timeout."""
        mock_resolve.return_value = "/usr/bin/echo"
        mock_run.return_value = subprocess.CompletedProcess(
            args=["/usr/bin/echo", "hello"], returncode=0
        )

        run_subprocess(["echo", "hello"], timeout=60)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 60

    @patch("subprocess.run")
    @patch("chiron.subprocess_utils.resolve_executable")
    def test_timeout_exception(
        self, mock_resolve: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test subprocess execution that times out."""
        mock_resolve.return_value = "/usr/bin/sleep"
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["/usr/bin/sleep", "100"], timeout=1
        )

        with pytest.raises(SubprocessTimeoutError) as exc_info:
            run_subprocess(["sleep", "100"], timeout=1)

        assert "timed out" in str(exc_info.value).lower()
        assert exc_info.value.timeout == 1

    @patch("subprocess.run")
    @patch("chiron.subprocess_utils.resolve_executable")
    def test_called_process_error(
        self, mock_resolve: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test subprocess execution that fails."""
        mock_resolve.return_value = "/usr/bin/false"
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd=["/usr/bin/false"]
        )

        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            run_subprocess(["false"], check=True)

        assert exc_info.value.returncode == 1

    @patch("subprocess.run")
    @patch("chiron.subprocess_utils.resolve_executable")
    def test_capture_output(self, mock_resolve: MagicMock, mock_run: MagicMock) -> None:
        """Test subprocess execution with output capture."""
        mock_resolve.return_value = "/usr/bin/echo"
        mock_run.return_value = subprocess.CompletedProcess(
            args=["/usr/bin/echo", "hello"],
            returncode=0,
            stdout=b"hello\n",
            stderr=b"",
        )

        result = run_subprocess(["echo", "hello"], capture_output=True)

        assert result.stdout == b"hello\n"
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["capture_output"] is True

    @patch("subprocess.run")
    @patch("chiron.subprocess_utils.resolve_executable")
    def test_working_directory(
        self, mock_resolve: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test subprocess execution with custom working directory."""
        mock_resolve.return_value = "/usr/bin/pwd"
        mock_run.return_value = subprocess.CompletedProcess(
            args=["/usr/bin/pwd"], returncode=0
        )

        run_subprocess(["pwd"], cwd=tmp_path)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == tmp_path

    @patch("subprocess.run")
    @patch("chiron.subprocess_utils.resolve_executable")
    def test_custom_environment(
        self, mock_resolve: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test subprocess execution with custom environment."""
        mock_resolve.return_value = "/usr/bin/env"
        mock_run.return_value = subprocess.CompletedProcess(
            args=["/usr/bin/env"], returncode=0
        )

        custom_env = {"MY_VAR": "value"}
        run_subprocess(["env"], env=custom_env)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["env"] == custom_env

    @patch("subprocess.run")
    def test_no_executable_resolution(self, mock_run: MagicMock) -> None:
        """Test subprocess execution without executable resolution."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["echo", "hello"], returncode=0
        )

        run_subprocess(["echo", "hello"], resolve_executable_path=False)

        # Command should not be modified
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "echo"

    def test_empty_command(self) -> None:
        """Test subprocess execution with empty command."""
        with pytest.raises(ValueError, match="at least one argument"):
            run_subprocess([])

    @patch("chiron.subprocess_utils.resolve_executable")
    def test_executable_not_found_required(self, mock_resolve: MagicMock) -> None:
        """Test subprocess execution when required executable not found."""
        mock_resolve.side_effect = ExecutableNotFoundError("missing_tool")

        with pytest.raises(ExecutableNotFoundError):
            run_subprocess(["missing_tool", "arg"])

    @patch("subprocess.run")
    @patch("chiron.subprocess_utils.resolve_executable")
    def test_executable_not_found_not_required(
        self, mock_resolve: MagicMock, mock_run: MagicMock
    ) -> None:
        """Test subprocess execution when non-required executable not found."""
        mock_resolve.return_value = "optional_tool"
        mock_run.return_value = subprocess.CompletedProcess(
            args=["optional_tool"], returncode=0
        )

        result = run_subprocess(["optional_tool"], required_executable=False)
        assert result.returncode == 0


class TestBinaryAvailability:
    """Tests for binary availability checking functions."""

    @patch("chiron.subprocess_utils.probe_executable")
    def test_check_binary_availability_all_found(self, mock_probe: MagicMock) -> None:
        """Test checking binary availability when all binaries are found."""
        mock_probe.return_value = "/usr/bin/mock"

        result = check_binary_availability()

        assert all(result.values())
        assert "uv" in result
        assert "syft" in result
        assert "cosign" in result

    @patch("chiron.subprocess_utils.probe_executable")
    def test_check_binary_availability_some_missing(
        self, mock_probe: MagicMock
    ) -> None:
        """Test checking binary availability when some binaries are missing."""

        def probe_side_effect(binary: str) -> str | None:
            return "/usr/bin/mock" if binary in ["uv", "tar", "git"] else None

        mock_probe.side_effect = probe_side_effect

        result = check_binary_availability()

        assert result["uv"] is True
        assert result["tar"] is True
        assert result["git"] is True
        assert result["syft"] is False
        assert result["cosign"] is False

    @patch("chiron.subprocess_utils.probe_executable")
    def test_get_missing_binaries_none_missing(self, mock_probe: MagicMock) -> None:
        """Test getting missing binaries when all are available."""
        mock_probe.return_value = "/usr/bin/mock"

        result = get_missing_binaries()

        assert result == []

    @patch("chiron.subprocess_utils.probe_executable")
    def test_get_missing_binaries_some_missing(self, mock_probe: MagicMock) -> None:
        """Test getting missing binaries when some are unavailable."""

        def probe_side_effect(binary: str) -> str | None:
            return (
                None
                if binary in ["syft", "cosign", "semantic-release"]
                else "/usr/bin/mock"
            )

        mock_probe.side_effect = probe_side_effect

        result = get_missing_binaries()

        assert set(result) == {"syft", "cosign", "semantic-release"}


class TestExecutableNotFoundError:
    """Tests for ExecutableNotFoundError exception."""

    def test_default_message(self) -> None:
        """Test ExecutableNotFoundError with default message."""
        error = ExecutableNotFoundError("test_tool")
        assert error.executable == "test_tool"
        assert "test_tool" in str(error)
        assert "not found" in str(error).lower()

    def test_custom_message(self) -> None:
        """Test ExecutableNotFoundError with custom message."""
        custom_msg = "Custom error message"
        error = ExecutableNotFoundError("test_tool", custom_msg)
        assert error.executable == "test_tool"
        assert str(error) == custom_msg


class TestSubprocessTimeoutError:
    """Tests for SubprocessTimeoutError exception."""

    def test_default_message(self) -> None:
        """Test SubprocessTimeoutError with default message."""
        command = ["long_running_command", "arg1"]
        error = SubprocessTimeoutError(command, timeout=30)
        assert error.command == command
        assert error.timeout == 30
        assert "timed out" in str(error).lower()
        assert "30" in str(error)

    def test_custom_message(self) -> None:
        """Test SubprocessTimeoutError with custom message."""
        command = ["test_command"]
        custom_msg = "Custom timeout message"
        error = SubprocessTimeoutError(command, timeout=60, message=custom_msg)
        assert error.command == command
        assert error.timeout == 60
        assert str(error) == custom_msg
