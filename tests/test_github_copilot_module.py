"""Unit tests for ``chiron.github.copilot`` helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from chiron.github import copilot


def test_detect_agent_environment_when_indicator_present() -> None:
    is_agent, indicators = copilot.detect_agent_environment(
        {"GITHUB_COPILOT_AGENT_ID": "abc123"}
    )

    assert is_agent is True
    assert indicators == ("GITHUB_COPILOT_AGENT_ID",)


def test_detect_agent_environment_github_actions_fallback() -> None:
    env = {"GITHUB_ACTIONS": "true", "COPILOT_JOB_ID": "42"}

    is_agent, indicators = copilot.detect_agent_environment(env)

    assert is_agent is True
    assert indicators == ("COPILOT_JOB_ID",)


def test_detect_agent_environment_without_indicators() -> None:
    is_agent, indicators = copilot.detect_agent_environment({"GITHUB_ACTIONS": "true"})

    assert is_agent is False
    assert indicators == ()


def test_apply_env_overrides_clears_offline_settings() -> None:
    environment = {"PIP_NO_INDEX": "1", "PIP_FIND_LINKS": "https://example"}

    overrides = copilot._apply_env_overrides(
        environment, clear_offline_overrides=True
    )  # pylint: disable=protected-access

    assert overrides == {
        copilot.COPILOT_DISABLE_ENV_VAR: "1",
        "PIP_NO_INDEX": None,
        "PIP_FIND_LINKS": None,
    }
    assert environment == {copilot.COPILOT_DISABLE_ENV_VAR: "1"}


def test_prepare_environment_dry_run_sets_expected_command() -> None:
    result = copilot.prepare_environment(
        workspace_root=None,
        all_extras=False,
        extras=["dev"],
        include_dev=False,
        uv_path="/usr/bin/uv",
        dry_run=True,
        clear_offline_overrides=True,
        env={"PIP_NO_INDEX": "1", "PIP_FIND_LINKS": "https://example"},
    )

    assert result.dry_run is True
    assert result.success is True
    assert result.command == ("/usr/bin/uv", "sync", "--extra", "dev")
    assert result.env_overrides == {
        copilot.COPILOT_DISABLE_ENV_VAR: "1",
        "PIP_NO_INDEX": None,
        "PIP_FIND_LINKS": None,
    }


def test_prepare_environment_invokes_uv_process(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    workspace = tmp_path_factory.mktemp("copilot")

    with patch("chiron.github.copilot.subprocess.run") as mock_run:
        mock_run.return_value = SimpleNamespace(returncode=0)

        result = copilot.prepare_environment(
            workspace_root=workspace,
            uv_path="/usr/bin/uv",
            dry_run=False,
            env={},
        )

    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0][0] == "/usr/bin/uv"
    assert kwargs["cwd"] == workspace
    env = kwargs["env"]
    assert env[copilot.COPILOT_DISABLE_ENV_VAR] == "1"
    assert "PIP_NO_INDEX" not in env
    assert "PIP_FIND_LINKS" not in env
    assert result.success is True
    assert result.exit_code == 0


def test_prepare_environment_handles_uv_missing() -> None:
    with patch("chiron.github.copilot.shutil.which", return_value=None):
        result = copilot.prepare_environment(uv_path=None, env={})

    assert result.success is False
    assert result.command == ()
    assert result.message == "uv executable not found on PATH"


def test_collect_status_reports_overrides(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    workspace = tmp_path_factory.mktemp("status")
    env = {"PIP_FIND_LINKS": "https://example", "PIP_NO_INDEX": "1"}

    with patch("chiron.github.copilot.shutil.which", return_value="/usr/bin/uv"):
        status = copilot.collect_status(
            workspace_root=workspace, env=env, workflow_path=workspace / "missing.yml"
        )

    assert status.pip_overrides_active is True
    assert status.workflow_present is False
    assert status.uv_available is True
    assert status.indicator_keys == ()
