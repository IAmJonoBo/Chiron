from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch
from typer.testing import CliRunner

from chiron.dev_toolbox import (
    CommandResult,
    QualityConfiguration,
    QualityGate,
    QualitySuitePlan,
    QualitySuiteProgressEvent,
    QualitySuiteRunReport,
    RefactorOpportunity,
    RefactorReport,
)
from chiron.typer_cli import app


def test_tools_quality_suite_renders_progress(monkeypatch: MonkeyPatch) -> None:
    gate_tests = QualityGate(
        name="tests",
        command=("echo", "tests"),
        description="Run tests",
        category="tests",
    )
    gate_lint = QualityGate(
        name="lint",
        command=("echo", "lint"),
        description="Run lint",
        category="lint",
        critical=False,
    )
    plan = QualitySuitePlan(profile="demo", gates=(gate_tests, gate_lint))

    monkeypatch.setattr(
        "chiron.typer_cli.load_quality_configuration",
        lambda: QualityConfiguration(gates={}, profiles={}),
    )
    monkeypatch.setattr(
        "chiron.typer_cli.available_quality_profiles",
        lambda config: {"demo": tuple(gate.name for gate in plan.gates)},
    )
    monkeypatch.setattr(
        "chiron.typer_cli.build_quality_suite_plan",
        lambda profile, config=None, toggles=None: plan,
    )

    def fake_execute_quality_suite(
        plan: QualitySuitePlan,
        *,
        halt_on_failure: bool,
        monitoring=None,
        progress=None,
    ) -> QualitySuiteRunReport:
        assert halt_on_failure
        assert progress is not None
        results: list[CommandResult] = []
        total = len(plan.gates)
        for index, gate in enumerate(plan.gates, start=1):
            progress(
                QualitySuiteProgressEvent(
                    index=index,
                    total=total,
                    command=gate.command,
                    gate=gate,
                    status="started",
                )
            )
            result = CommandResult(gate.command, 0, 0.1 * index, "", gate=gate.name)
            progress(
                QualitySuiteProgressEvent(
                    index=index,
                    total=total,
                    command=gate.command,
                    gate=gate,
                    status="completed",
                    result=result,
                )
            )
            results.append(result)
        return QualitySuiteRunReport(
            plan=plan,
            results=tuple(results),
            started_at=0.0,
            finished_at=0.2,
        )

    monkeypatch.setattr(
        "chiron.typer_cli.execute_quality_suite", fake_execute_quality_suite
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["tools", "qa", "--profile", "demo"],
        catch_exceptions=False,
        prog_name="chiron",
    )

    assert result.exit_code == 0
    output = result.stdout
    assert "Quality Suite Progress" in output
    assert "▶" in output
    assert "Run tests" in output
    assert "Run lint" in output
    assert "Quality Suite — PASSED" in output


def test_tools_quality_suite_contracts_toggle_forwarded(
    monkeypatch: MonkeyPatch,
) -> None:
    gate_tests = QualityGate(
        name="tests",
        command=("echo", "tests"),
        description="Run tests",
        category="tests",
    )
    plan = QualitySuitePlan(profile="demo", gates=(gate_tests,))

    monkeypatch.setattr(
        "chiron.typer_cli.load_quality_configuration",
        lambda: QualityConfiguration(gates={}, profiles={}),
    )
    monkeypatch.setattr(
        "chiron.typer_cli.available_quality_profiles",
        lambda config: {"demo": tuple(gate.name for gate in plan.gates)},
    )

    captured_toggles: dict[str, bool | None] = {}

    def fake_build_quality_suite_plan(profile, config=None, toggles=None):
        if toggles:
            captured_toggles.update(toggles)
        return plan

    monkeypatch.setattr(
        "chiron.typer_cli.build_quality_suite_plan",
        fake_build_quality_suite_plan,
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "tools",
            "qa",
            "--profile",
            "demo",
            "--contracts",
            "--dry-run",
            "--json",
        ],
        catch_exceptions=False,
        prog_name="chiron",
    )

    assert result.exit_code == 0
    assert captured_toggles["contracts"] is True
    assert all(
        captured_toggles.get(toggle) is None
        for toggle in ["tests", "lint", "types", "security", "docs", "build"]
    )


def test_tools_docs_sync_diataxis(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_sync(
        config: Path,
        target: Path,
        *,
        marker: str,
        entries: object | None = None,
    ) -> Path:
        captured["config"] = config
        captured["target"] = target
        captured["marker"] = marker
        captured["entries"] = entries
        target.write_text("updated", encoding="utf-8")
        return target

    monkeypatch.setattr(
        "chiron.typer_cli.sync_diataxis_documentation", fake_sync
    )

    config_path = tmp_path / "map.json"
    target_path = tmp_path / "index.md"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "tools",
            "docs",
            "sync-diataxis",
            "--config",
            str(config_path),
            "--target",
            str(target_path),
            "--marker",
            "CUSTOM",
        ],
        catch_exceptions=False,
        prog_name="chiron",
    )

    assert result.exit_code == 0
    assert "Updated" in result.stdout
    assert captured["config"] == config_path
    assert captured["target"] == target_path
    assert captured["marker"] == "CUSTOM"
    assert captured["entries"] is None


def test_tools_docs_sync_diataxis_with_discovery(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    fake_entries = {
        "tutorials": (),
        "how_to": (),
        "reference": (),
        "explanation": (),
    }
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "chiron.typer_cli.discover_diataxis_entries",
        lambda docs: fake_entries if docs == docs_dir else {},
    )
    monkeypatch.setattr("chiron.typer_cli.dump_diataxis_entries", lambda path, entries: path)

    def fake_sync(
        config: Path,
        target: Path,
        *,
        marker: str,
        entries: object | None = None,
    ) -> Path:
        captured["entries"] = entries
        return target

    monkeypatch.setattr(
        "chiron.typer_cli.sync_diataxis_documentation", fake_sync
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "tools",
            "docs",
            "sync-diataxis",
            "--discover",
            "--docs-dir",
            str(docs_dir),
        ],
        catch_exceptions=False,
        prog_name="chiron",
    )

    assert result.exit_code == 0
    assert "Discovered" in result.stdout
    assert captured["entries"] is fake_entries


def test_tools_refactor_analyze_outputs_summary(monkeypatch: MonkeyPatch) -> None:
    opportunity = RefactorOpportunity(
        path=Path("src/chiron/example.py"),
        line=42,
        symbol="example",
        kind="function_length",
        severity="critical",
        message="Function exceeds threshold",
        metric=120,
        threshold=30,
    )
    report = RefactorReport(opportunities=(opportunity,))

    monkeypatch.setattr(
        "chiron.typer_cli.analyze_refactor_opportunities",
        lambda paths=None, **kwargs: report,
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "tools",
            "refactor",
            "analyze",
            "--path",
            "src/chiron/example.py",
        ],
        catch_exceptions=False,
        prog_name="chiron",
    )

    assert result.exit_code == 0
    assert "Function exceeds threshold" in result.stdout


def test_tools_refactor_analyze_json_output_is_sorted(monkeypatch: MonkeyPatch) -> None:
    opportunity_high = RefactorOpportunity(
        path=Path("src/chiron/high.py"),
        line=5,
        symbol="complex",
        kind="cyclomatic_complexity",
        severity="critical",
        message="Cyclomatic complexity 12 exceeds 8",
        metric=12,
        threshold=8,
    )
    opportunity_low = RefactorOpportunity(
        path=Path("src/chiron/low.py"),
        line=3,
        symbol="helper",
        kind="function_length",
        severity="info",
        message="Function spans 15 lines",
        metric=15,
        threshold=30,
    )
    report = RefactorReport(opportunities=(opportunity_low, opportunity_high))

    monkeypatch.setattr(
        "chiron.typer_cli.analyze_refactor_opportunities",
        lambda paths=None, **kwargs: report,
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "tools",
            "refactor",
            "analyze",
            "--json",
        ],
        catch_exceptions=False,
        prog_name="chiron",
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    severities = [item["severity"] for item in payload["opportunities"]]
    assert severities == ["critical", "info"]


def test_tools_refactor_hotspots_outputs_summary(monkeypatch: MonkeyPatch) -> None:
    from chiron.dev_toolbox import HotspotEntry, HotspotReport

    entry1 = HotspotEntry(
        path=Path("src/chiron/complex.py"),
        complexity_score=500,
        churn_count=10,
        hotspot_score=5000,
    )
    entry2 = HotspotEntry(
        path=Path("src/chiron/simple.py"),
        complexity_score=50,
        churn_count=5,
        hotspot_score=250,
    )
    report = HotspotReport(entries=(entry1, entry2))

    monkeypatch.setattr(
        "chiron.typer_cli.analyze_hotspots",
        lambda **kwargs: report,
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "tools",
            "refactor",
            "hotspots",
            "--limit",
            "5",
        ],
        catch_exceptions=False,
        prog_name="chiron",
    )

    assert result.exit_code == 0
    assert "complex.py" in result.stdout
    assert "hotspot=5000" in result.stdout


def test_tools_refactor_hotspots_json_output(monkeypatch: MonkeyPatch) -> None:
    from chiron.dev_toolbox import HotspotEntry, HotspotReport

    entry = HotspotEntry(
        path=Path("src/chiron/test.py"),
        complexity_score=100,
        churn_count=20,
        hotspot_score=2000,
    )
    report = HotspotReport(entries=(entry,))

    monkeypatch.setattr(
        "chiron.typer_cli.analyze_hotspots",
        lambda **kwargs: report,
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "tools",
            "refactor",
            "hotspots",
            "--json",
        ],
        catch_exceptions=False,
        prog_name="chiron",
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "entries" in payload
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["path"] == "src/chiron/test.py"
    assert payload["entries"][0]["hotspot_score"] == 2000


def test_tools_refactor_analyze_forwards_thresholds(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_analyze(paths=None, **kwargs):
        captured["paths"] = paths
        captured["kwargs"] = kwargs
        return RefactorReport(opportunities=())

    monkeypatch.setattr(
        "chiron.typer_cli.analyze_refactor_opportunities",
        fake_analyze,
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "tools",
            "refactor",
            "analyze",
            "--max-function-length",
            "45",
            "--max-class-methods",
            "8",
            "--max-cyclomatic-complexity",
            "7",
            "--max-parameters",
            "4",
            "--min-docstring-length",
            "18",
        ],
        catch_exceptions=False,
        prog_name="chiron",
    )

    assert result.exit_code == 0
    assert captured["kwargs"]["max_cyclomatic_complexity"] == 7
    assert captured["kwargs"]["max_parameters"] == 4
    assert captured["kwargs"]["min_docstring_length"] == 18
