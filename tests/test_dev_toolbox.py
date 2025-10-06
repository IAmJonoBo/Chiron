from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from chiron.dev_toolbox import (
    CoverageReport,
    QualityConfiguration,
    QualityGate,
    coverage_gap_summary,
    coverage_guard,
    load_quality_configuration,
    resolve_quality_profile,
)
from chiron.typer_cli import app


def _write_coverage(tmp_path: Path) -> Path:
    xml = tmp_path / "coverage.xml"
    xml.write_text(
        textwrap.dedent(
            """<?xml version="1.0" ?>
            <coverage version="7.0.0" line-rate="0.63" lines-covered="63" lines-valid="100">
              <packages>
                <package name="chiron">
                  <class name="core" filename="src/chiron/core.py" line-rate="1.0" statements="10" missing="0">
                    <lines>
                      <line number="1" hits="1" />
                    </lines>
                  </class>
                  <class name="deps.graph" filename="src/chiron/deps/graph.py" line-rate="0.62" statements="50" missing="19">
                    <lines>
                      <line number="10" hits="0" />
                      <line number="11" hits="0" />
                      <line number="12" hits="1" />
                    </lines>
                  </class>
                  <class name="deps.verify" filename="src/chiron/deps/verify.py" line-rate="0.55" statements="40" missing="18">
                    <lines>
                      <line number="20" hits="0" />
                      <line number="21" hits="0" />
                      <line number="22" hits="0" />
                    </lines>
                  </class>
                </package>
              </packages>
            </coverage>
            """
        ).strip(),
        encoding="utf-8",
    )
    return xml


def test_coverage_report_parsing(tmp_path: Path) -> None:
    xml = _write_coverage(tmp_path)
    report = CoverageReport.from_xml(xml)
    worst = report.worst(limit=2)
    assert [module.name for module in worst] == [
        "src/chiron/deps/verify.py",
        "src/chiron/deps/graph.py",
    ]
    verify = report.get("src/chiron/deps/verify.py")
    assert verify is not None
    assert verify.coverage == pytest.approx(55.0)
    assert verify.missing_lines == (20, 21, 22)
    summary = report.summary
    assert summary.total_statements == 100
    assert summary.total_missing == 37
    assert summary.coverage == pytest.approx(63.0)


def test_coverage_gap_summary(tmp_path: Path) -> None:
    xml = _write_coverage(tmp_path)
    report = CoverageReport.from_xml(xml)
    summary = coverage_gap_summary(report, min_statements=30, limit=2)
    assert "deps/graph" in summary.splitlines()[0]


def test_coverage_guard(tmp_path: Path) -> None:
    xml = _write_coverage(tmp_path)
    report = CoverageReport.from_xml(xml)
    passed, message = coverage_guard(report, threshold=70.0, limit=1)
    assert not passed
    assert "below" in message
    passed_success, _ = coverage_guard(report, threshold=50.0, limit=1)
    assert passed_success


def test_quality_configuration_load(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        textwrap.dedent(
            """
            [tool.chiron.dev_toolbox.gates.docs]
            command = ["uv", "run", "--extra", "docs", "sphinx-build", "docs", "site"]
            category = "docs"
            description = "Build documentation"

            [tool.chiron.dev_toolbox.profiles.docs]
            gates = ["docs"]
            """
        ).strip(),
        encoding="utf-8",
    )
    config = load_quality_configuration(tmp_path)
    assert "docs" in config.gates
    assert config.gates["docs"].category == "docs"
    assert config.profiles["docs"] == ("docs",)


def test_resolve_quality_profile_uses_defaults() -> None:
    config = QualityConfiguration(gates={}, profiles={})
    gates = resolve_quality_profile("fast", config=config)
    assert [gate.name for gate in gates] == ["tests", "lint"]


def test_tools_quality_suite_cli(monkeypatch) -> None:
    runner = CliRunner()
    captured: dict[str, list[QualityGate]] = {}

    class DummyResult:
        def __init__(self, command):
            self.command = tuple(command)
            self.returncode = 0
            self.duration = 0.1
            self.output = ""
            self.gate = "tests"

        def to_json(self):
            return json.dumps(
                {
                    "command": list(self.command),
                    "returncode": self.returncode,
                    "duration": self.duration,
                    "output": self.output,
                }
            )

        def to_payload(self):
            return {
                "command": list(self.command),
                "returncode": self.returncode,
                "duration": self.duration,
                "output": self.output,
                "gate": self.gate,
            }

    def fake_run_quality_suite(commands, halt_on_failure=True):
        captured["commands"] = list(commands)
        return [DummyResult(commands[0].command)]

    def fake_summarise(results):
        return "ok"

    monkeypatch.setattr(
        "chiron.typer_cli.load_quality_configuration",
        lambda: QualityConfiguration(gates={}, profiles={}),
    )
    monkeypatch.setattr("chiron.typer_cli.run_quality_suite", fake_run_quality_suite)
    monkeypatch.setattr("chiron.typer_cli.summarise_suite", fake_summarise)

    result = runner.invoke(
        app,
        [
            "tools",
            "qa",
            "--profile",
            "fast",
        ],
    )
    assert result.exit_code == 0
    gate_names = [gate.name for gate in captured["commands"]]
    assert gate_names == ["tests", "lint"]


def test_tools_quality_suite_cli_json(monkeypatch) -> None:
    runner = CliRunner()

    class DummyResult:
        def __init__(self, command):
            self.command = tuple(command)
            self.returncode = 0
            self.duration = 0.5
            self.output = ""
            self.gate = "tests"

        def to_json(self):
            return json.dumps(
                {
                    "command": list(self.command),
                    "returncode": self.returncode,
                    "duration": self.duration,
                    "output": self.output,
                }
            )

        def to_payload(self):
            return {
                "command": list(self.command),
                "returncode": self.returncode,
                "duration": self.duration,
                "output": self.output,
                "gate": self.gate,
            }

    monkeypatch.setattr(
        "chiron.typer_cli.load_quality_configuration",
        lambda: QualityConfiguration(gates={}, profiles={}),
    )
    monkeypatch.setattr(
        "chiron.typer_cli.run_quality_suite",
        lambda commands, halt_on_failure=True: [DummyResult(commands[0].command)],
    )
    monkeypatch.setattr("chiron.typer_cli.summarise_suite", lambda results: "ignored")

    result = runner.invoke(app, ["tools", "qa", "--tests", "--no-lint", "--no-types", "--no-security", "--no-build", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload[0]["command"][0] == "uv"


def test_tools_quality_suite_cli_list_profiles(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(
        "chiron.typer_cli.load_quality_configuration",
        lambda: QualityConfiguration(gates={}, profiles={}),
    )
    result = runner.invoke(app, ["tools", "qa", "--list-profiles"])
    assert result.exit_code == 0
    assert "fast" in result.stdout


def test_tools_coverage_hotspots_cli(tmp_path: Path) -> None:
    xml = _write_coverage(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["tools", "coverage", "hotspots", "--xml", str(xml), "--threshold", "80", "--limit", "2"])
    assert result.exit_code == 0
    assert "deps/verify" in result.stdout


def test_tools_coverage_focus_cli(tmp_path: Path) -> None:
    xml = _write_coverage(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "tools",
            "coverage",
            "focus",
            "src/chiron/deps/graph.py",
            "--xml",
            str(xml),
            "--lines",
            "2",
        ],
    )
    assert result.exit_code == 0
    assert "Missing lines: 10, 11" in result.stdout


def test_tools_coverage_summary_cli(tmp_path: Path) -> None:
    xml = _write_coverage(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["tools", "coverage", "summary", "--xml", str(xml), "--limit", "1"])
    assert result.exit_code == 0
    assert "Top performers" in result.stdout


def test_tools_coverage_guard_cli(tmp_path: Path) -> None:
    xml = _write_coverage(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["tools", "coverage", "guard", "--xml", str(xml), "--threshold", "70"])
    assert result.exit_code == 1
    assert "below" in result.stdout


def test_tools_coverage_gaps_cli(tmp_path: Path) -> None:
    xml = _write_coverage(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "tools",
            "coverage",
            "gaps",
            "--xml",
            str(xml),
            "--limit",
            "2",
            "--min-statements",
            "30",
        ],
    )
    assert result.exit_code == 0
    assert "deps/graph" in result.stdout
