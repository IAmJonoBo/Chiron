"""Shared subprocess utilities with timeouts, availability checks, and error handling.

This module provides frontier-grade subprocess execution with:
- Executable path probing and validation
- Configurable timeouts with defaults
- Graceful error handling and actionable error messages
- Security-conscious subprocess invocation
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Default timeouts for different command types (in seconds)
DEFAULT_TIMEOUTS = {
    "uv": 300,  # 5 minutes for package operations
    "syft": 180,  # 3 minutes for SBOM generation
    "cosign": 60,  # 1 minute for signing operations
    "semantic-release": 300,  # 5 minutes for release operations
    "tar": 120,  # 2 minutes for archive operations
    "git": 60,  # 1 minute for git operations
    "default": 120,  # 2 minutes default timeout
}

# Known external binaries that Chiron relies on
EXTERNAL_BINARIES = [
    "uv",
    "syft",
    "cosign",
    "semantic-release",
    "tar",
    "git",
]


class SubprocessError(Exception):
    """Base exception for subprocess-related errors."""

    pass


class ExecutableNotFoundError(SubprocessError):
    """Exception raised when a required executable is not found."""

    def __init__(self, executable: str, message: str | None = None) -> None:
        """Initialize ExecutableNotFoundError.

        Args:
            executable: Name of the executable that was not found.
            message: Optional custom error message.
        """
        self.executable = executable
        if message is None:
            message = (
                f"Required executable '{executable}' not found. "
                f"Please ensure it is installed and available in PATH."
            )
        super().__init__(message)


class SubprocessTimeoutError(SubprocessError):
    """Exception raised when a subprocess times out."""

    def __init__(
        self, command: Sequence[str], timeout: int, message: str | None = None
    ) -> None:
        """Initialize SubprocessTimeoutError.

        Args:
            command: Command that timed out.
            timeout: Timeout value in seconds.
            message: Optional custom error message.
        """
        self.command = command
        self.timeout = timeout
        if message is None:
            cmd_str = " ".join(str(c) for c in command)
            message = f"Command timed out after {timeout}s: {cmd_str}"
        super().__init__(message)


def probe_executable(executable: str) -> str | None:
    """Probe for an executable in PATH and return its absolute path.

    Args:
        executable: Name or path of the executable to probe.

    Returns:
        Absolute path to the executable if found, None otherwise.
    """
    # If already absolute and exists, return it
    path = Path(executable)
    if path.is_absolute() and path.is_file() and os.access(path, os.X_OK):
        return str(path)

    # If relative path with parent directory, resolve it
    if path.parent != Path("."):
        candidate = path.resolve()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    # Search in PATH
    resolved = shutil.which(executable)
    return resolved


def resolve_executable(executable: str, required: bool = True) -> str:
    """Resolve an executable to its absolute path with validation.

    Args:
        executable: Name or path of the executable to resolve.
        required: If True, raise exception if executable not found.
                 If False, return the original executable name.

    Returns:
        Absolute path to the executable.

    Raises:
        ExecutableNotFoundError: If executable not found and required=True.
    """
    resolved = probe_executable(executable)

    if resolved is None:
        if required:
            raise ExecutableNotFoundError(executable)
        logger.warning(
            "Executable not found in PATH, using name as-is", executable=executable
        )
        return executable

    logger.debug("Resolved executable", executable=executable, path=resolved)
    return resolved


def get_default_timeout(command: Sequence[str]) -> int:
    """Get default timeout for a command based on the executable.

    Args:
        command: Command sequence.

    Returns:
        Default timeout in seconds.
    """
    if not command:
        return DEFAULT_TIMEOUTS["default"]

    # Extract executable name (without path)
    executable = Path(str(command[0])).name

    return DEFAULT_TIMEOUTS.get(executable, DEFAULT_TIMEOUTS["default"])


def run_subprocess(
    command: Sequence[str],
    *,
    timeout: int | None = None,
    check: bool = True,
    capture_output: bool = False,
    text: bool = False,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
    resolve_executable_path: bool = True,
    required_executable: bool = True,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    """Run a subprocess with proper error handling, timeouts, and path resolution.

    This is the preferred way to run external commands in Chiron. It provides:
    - Automatic executable path resolution
    - Default timeouts based on command type
    - Graceful error handling with actionable messages
    - Structured logging

    Args:
        command: Command sequence to execute.
        timeout: Timeout in seconds. If None, uses default based on command type.
        check: If True, raise CalledProcessError on non-zero exit.
        capture_output: If True, capture stdout and stderr.
        text: If True, decode output as text.
        cwd: Working directory for the subprocess.
        env: Environment variables for the subprocess.
        resolve_executable_path: If True, resolve executable to absolute path.
        required_executable: If True, raise error if executable not found.
        **kwargs: Additional arguments passed to subprocess.run.

    Returns:
        CompletedProcess instance.

    Raises:
        ExecutableNotFoundError: If executable not found and required_executable=True.
        SubprocessTimeoutError: If command times out.
        subprocess.CalledProcessError: If command fails and check=True.
    """
    if not command:
        raise ValueError("Command must contain at least one argument")

    # Resolve executable path if requested
    if resolve_executable_path:
        resolved_exec = resolve_executable(
            str(command[0]), required=required_executable
        )
        resolved_command = [resolved_exec, *command[1:]]
    else:
        resolved_command = list(command)

    # Get default timeout if not specified
    if timeout is None:
        timeout = get_default_timeout(command)

    # Prepare logging context
    log_context = {
        "command": " ".join(str(c) for c in resolved_command),
        "timeout": timeout,
        "cwd": str(cwd) if cwd else None,
    }

    logger.info("Running subprocess", **log_context)

    try:
        result = subprocess.run(
            resolved_command,
            timeout=timeout,
            check=check,
            capture_output=capture_output,
            text=text,
            cwd=cwd,
            env=env,
            **kwargs,
        )

        logger.info(
            "Subprocess completed",
            returncode=result.returncode,
            **log_context,
        )

        return result

    except subprocess.TimeoutExpired as e:
        logger.error("Subprocess timed out", **log_context)
        raise SubprocessTimeoutError(resolved_command, timeout) from e

    except subprocess.CalledProcessError as e:
        logger.error(
            "Subprocess failed",
            returncode=e.returncode,
            stdout=e.stdout if capture_output else None,
            stderr=e.stderr if capture_output else None,
            **log_context,
        )
        raise

    except Exception as e:
        logger.error("Subprocess execution error", error=str(e), **log_context)
        raise


def check_binary_availability() -> dict[str, bool]:
    """Check availability of all known external binaries.

    Returns:
        Dictionary mapping binary name to availability status.
    """
    availability = {}
    for binary in EXTERNAL_BINARIES:
        resolved = probe_executable(binary)
        availability[binary] = resolved is not None
        if resolved:
            logger.debug("Binary available", binary=binary, path=resolved)
        else:
            logger.warning("Binary not available", binary=binary)

    return availability


def get_missing_binaries() -> list[str]:
    """Get list of required binaries that are not available.

    Returns:
        List of missing binary names.
    """
    availability = check_binary_availability()
    return [binary for binary, available in availability.items() if not available]
