from __future__ import annotations

from pytest import MonkeyPatch
from typer.testing import CliRunner

from chiron.dev_toolbox import (
    CommandResult,
    QualityConfiguration,
    QualityGate,
    QualitySuitePlan,
    QualitySuiteProgressEvent,
    QualitySuiteRunReport,
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
