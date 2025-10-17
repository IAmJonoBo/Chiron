from __future__ import annotations

from typing import Sequence

from typer.testing import CliRunner

from chiron.typer_cli import app


def _invoke(command: Sequence[str]) -> str:
    runner = CliRunner()
    result = runner.invoke(app, list(command), catch_exceptions=False)
    assert result.exit_code == 1
    message = result.stdout.strip()
    assert "Hephaestus" in message
    return message


def test_tools_qa_forwards_to_hephaestus() -> None:
    output = _invoke(["tools", "qa", "--profile", "quick"])
    assert "hephaestus tools qa" in output.lower()


def test_tools_coverage_hotspots_forwards() -> None:
    output = _invoke(["tools", "coverage", "hotspots", "--json"])
    assert "coverage hotspots" in output.lower()


def test_tools_refactor_analyze_forwards() -> None:
    output = _invoke(["tools", "refactor", "analyze", "--json"])
    assert "refactor analyze" in output.lower()


def test_tools_docs_sync_diataxis_forwards() -> None:
    output = _invoke(["tools", "docs", "sync-diataxis", "--marker", "CUSTOM"])
    assert "docs sync-diataxis" in output.lower()
