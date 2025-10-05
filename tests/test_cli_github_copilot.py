"""Tests for GitHub Copilot CLI helpers."""

from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip("typer")

from chiron.typer_cli import app as typer_app

typer_testing_spec = importlib.util.find_spec("typer.testing")
if typer_testing_spec is None:  # pragma: no cover - optional dependency guard
    pytest.skip("typer is required for CLI tests", allow_module_level=True)

typer_testing = importlib.import_module(
    "typer.testing"
)  # pragma: no cover - optional dependency guard
CliRunner = typer_testing.CliRunner

runner = CliRunner()


def test_copilot_status_json(tmp_path: Path) -> None:
    """Status command should emit JSON with key indicators."""

    env = {
        "GITHUB_COPILOT_AGENT_ID": "abc123",
        "CHIRON_DISABLE_VENDOR_WHEELHOUSE": "1",
    }

    result = runner.invoke(
        typer_app,
        ["github", "copilot", "status", "--json"],
        env=env,
    )

    assert result.exit_code == 0, result.output

    payload = json.loads(result.stdout.strip())
    assert payload["wheelhouse_disabled"] is True
    assert "GITHUB_COPILOT_AGENT_ID" in payload["indicator_keys"]
    assert payload["workflow_present"] is True


def test_copilot_prepare_dry_run(tmp_path: Path) -> None:
    """Prepare command should show dry-run output and env overrides."""

    env = {
        "PIP_NO_INDEX": "1",
        "PIP_FIND_LINKS": "vendor/wheelhouse",
    }

    result = runner.invoke(
        typer_app,
        [
            "github",
            "copilot",
            "prepare",
            "--dry-run",
            "--uv-path",
            "/usr/bin/uv",
            "--no-all-extras",
            "--extras",
            "dev",
            "--no-dev",
        ],
        env=env,
    )

    assert result.exit_code == 0, result.output
    stdout = result.stdout
    assert "$ /usr/bin/uv sync --extra dev" in stdout
    assert "unset PIP_NO_INDEX" in stdout
    assert "Dry run — no commands executed." in stdout


def test_copilot_env_fish() -> None:
    """Environment snippet should adapt to shell choice."""

    result = runner.invoke(
        typer_app,
        ["github", "copilot", "env", "--shell", "fish"],
    )

    assert result.exit_code == 0, result.output
    assert "set -gx CHIRON_DISABLE_VENDOR_WHEELHOUSE 1" in result.stdout
    assert "set -e PIP_NO_INDEX" in result.stdout
