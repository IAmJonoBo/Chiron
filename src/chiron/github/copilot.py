"""Utilities for GitHub Copilot coding agent integration.

This module centralizes environment detection and provisioning helpers that
are shared by the CLI, GitHub Actions workflows, and local developer tooling.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

COPILOT_DISABLE_ENV_VAR = "CHIRON_DISABLE_VENDOR_WHEELHOUSE"
_COPILOT_INDICATOR_KEYS: tuple[str, ...] = (
    "GITHUB_COPILOT_AGENT_ID",
    "GITHUB_COPILOT_WORKSPACE_ID",
    "GITHUB_COPILOT_CODING_AGENT",
    "GITHUB_COPILOT_RUN_ID",
    "COPILOT_AGENT_ID",
    "COPILOT_AGENT_VERSION",
    "COPILOT_WORKSPACE_ID",
)
_DEFAULT_WORKFLOW_PATH = Path(".github/workflows/copilot-setup-steps.yml")


@dataclass(slots=True)
class CopilotStatus:
    """Summary of Copilot coding agent readiness for the current workspace."""

    workspace_root: Path
    is_agent_environment: bool
    indicator_keys: tuple[str, ...]
    wheelhouse_disabled: bool
    workflow_present: bool
    uv_available: bool
    pip_overrides_active: bool
    pip_find_links: str | None = None
    pip_no_index: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the status."""

        return {
            "workspace_root": str(self.workspace_root),
            "is_agent_environment": self.is_agent_environment,
            "indicator_keys": list(self.indicator_keys),
            "wheelhouse_disabled": self.wheelhouse_disabled,
            "workflow_present": self.workflow_present,
            "uv_available": self.uv_available,
            "pip_overrides_active": self.pip_overrides_active,
            "pip_find_links": self.pip_find_links,
            "pip_no_index": self.pip_no_index,
        }


@dataclass(slots=True)
class PrepareResult:
    """Result from preparing the workspace for the Copilot agent."""

    command: tuple[str, ...]
    env_overrides: dict[str, str | None] = field(default_factory=dict)
    success: bool = False
    exit_code: int | None = None
    dry_run: bool = False
    message: str | None = None


class CopilotProvisioningError(RuntimeError):
    """Raised when environment preparation fails."""


def _normalise_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    if env is None:
        return dict(os.environ)
    return {str(k): str(v) for k, v in env.items()}


def detect_agent_environment(
    env: Mapping[str, str] | None = None,
) -> tuple[bool, tuple[str, ...]]:
    """Return whether the current environment looks like the Copilot agent.

    Args:
        env: Optional mapping of environment variables (defaults to ``os.environ``).

    Returns:
        A tuple ``(bool, indicators)`` where ``indicators`` is a tuple of the
        environment variable names that hinted at the Copilot agent.
    """

    data = _normalise_env(env)

    indicators = [key for key in _COPILOT_INDICATOR_KEYS if key in data and data[key]]
    if indicators:
        return True, tuple(indicators)

    # Fallback heuristic: running inside GitHub Actions with any COPILOT_* key.
    if data.get("GITHUB_ACTIONS") == "true":
        dynamic_indicators = [key for key in data if key.startswith("COPILOT_")]
        if dynamic_indicators:
            return True, tuple(dynamic_indicators)

    return False, ()


def _build_uv_command(
    uv_executable: str,
    *,
    all_extras: bool,
    extras: Sequence[str] | None,
    include_dev: bool,
    additional_args: Sequence[str] | None,
) -> list[str]:
    command = [uv_executable, "sync"]

    if all_extras:
        command.append("--all-extras")
    else:
        for extra in extras or ():
            cleaned = extra.strip()
            if cleaned:
                command.extend(["--extra", cleaned])

    if include_dev:
        command.append("--dev")

    if additional_args:
        command.extend(additional_args)

    return command


def _apply_env_overrides(
    environment: dict[str, str],
    clear_offline_overrides: bool,
) -> dict[str, str | None]:
    overrides: dict[str, str | None] = {COPILOT_DISABLE_ENV_VAR: "1"}
    environment[COPILOT_DISABLE_ENV_VAR] = "1"

    if clear_offline_overrides:
        for key in ("PIP_NO_INDEX", "PIP_FIND_LINKS"):
            if key in environment:
                overrides[key] = None
                environment.pop(key, None)

    return overrides


def collect_status(
    workspace_root: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    workflow_path: Path | None = None,
) -> CopilotStatus:
    """Collect Copilot readiness metadata for the given workspace."""

    root = workspace_root or Path.cwd()
    data = _normalise_env(env)
    workflow = workflow_path or (root / _DEFAULT_WORKFLOW_PATH)

    is_agent, indicators = detect_agent_environment(data)

    wheelhouse_disabled = bool(data.get(COPILOT_DISABLE_ENV_VAR))
    workflow_present = workflow.exists()
    uv_available = shutil.which("uv") is not None

    pip_find_links = data.get("PIP_FIND_LINKS")
    pip_no_index = data.get("PIP_NO_INDEX")
    pip_overrides_active = any(
        value and str(value).lower() not in {"0", "false"}
        for value in (pip_find_links, pip_no_index)
    )

    return CopilotStatus(
        workspace_root=root,
        is_agent_environment=is_agent,
        indicator_keys=indicators,
        wheelhouse_disabled=wheelhouse_disabled,
        workflow_present=workflow_present,
        uv_available=uv_available,
        pip_overrides_active=pip_overrides_active,
        pip_find_links=pip_find_links,
        pip_no_index=pip_no_index,
    )


def prepare_environment(
    workspace_root: Path | None = None,
    *,
    all_extras: bool = True,
    extras: Sequence[str] | None = None,
    include_dev: bool = True,
    uv_path: str | None = None,
    dry_run: bool = False,
    clear_offline_overrides: bool = True,
    additional_args: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    timeout: int | None = 900,
) -> PrepareResult:
    """Run ``uv sync`` with the right overrides for the Copilot agent."""

    root = workspace_root or Path.cwd()
    data = _normalise_env(env)
    uv_executable = uv_path or shutil.which("uv")

    if not uv_executable:
        return PrepareResult(
            command=(),
            message="uv executable not found on PATH",
            env_overrides={},
            success=False,
            dry_run=dry_run,
        )

    args = _build_uv_command(
        uv_executable,
        all_extras=all_extras,
        extras=extras,
        include_dev=include_dev,
        additional_args=additional_args,
    )
    env_overrides = _apply_env_overrides(data, clear_offline_overrides)

    result = PrepareResult(
        command=tuple(args),
        env_overrides=env_overrides,
        success=True,
        dry_run=dry_run,
    )

    if dry_run:
        return result

    completed = subprocess.run(  # noqa: S603 - arguments constructed above
        args,
        cwd=root,
        env=data,
        check=False,
        timeout=timeout,
    )

    result.exit_code = completed.returncode
    result.success = completed.returncode == 0

    if not result.success:
        result.message = (
            "uv sync exited with non-zero status"
            if result.exit_code is None
            else f"uv sync failed with exit code {result.exit_code}"
        )

    return result


def generate_env_exports(shell: str = "bash") -> str:
    """Return shell-specific commands to configure the Copilot environment."""

    shell_normalised = shell.lower()
    if shell_normalised in {"bash", "zsh", "sh"}:
        return "\n".join(
            [
                f"export {COPILOT_DISABLE_ENV_VAR}=1",
                "unset PIP_NO_INDEX",
                "unset PIP_FIND_LINKS",
            ]
        )

    if shell_normalised == "fish":
        return "\n".join(
            [
                f"set -gx {COPILOT_DISABLE_ENV_VAR} 1",
                "set -e PIP_NO_INDEX",
                "set -e PIP_FIND_LINKS",
            ]
        )

    if shell_normalised in {"powershell", "pwsh"}:
        return "\n".join(
            [
                f'$Env:{COPILOT_DISABLE_ENV_VAR} = "1"',
                "Remove-Item Env:PIP_NO_INDEX -ErrorAction SilentlyContinue",
                "Remove-Item Env:PIP_FIND_LINKS -ErrorAction SilentlyContinue",
            ]
        )

    if shell_normalised == "cmd":
        return "\r\n".join(
            [
                f"set {COPILOT_DISABLE_ENV_VAR}=1",
                "set PIP_NO_INDEX=",
                "set PIP_FIND_LINKS=",
            ]
        )

    raise CopilotProvisioningError(f"Unsupported shell: {shell}")


def format_status_json(status: CopilotStatus) -> str:
    """Return a formatted JSON string for the given status."""

    return json.dumps(status.as_dict(), indent=2, sort_keys=True)
