from __future__ import annotations

import textwrap
from datetime import UTC, datetime
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

from chiron.dev_toolbox import (
    CommandResult,
    CoverageFocusSummary,
    CoverageReport,
    DocumentationSyncError,
    QualityConfiguration,
    QualityGate,
    QualitySuiteMonitoring,
    QualitySuitePlan,
    QualitySuiteProgressEvent,
    QualitySuiteRecommendation,
    QualitySuiteRunReport,
    build_quality_suite_insights,
    build_quality_suite_monitoring,
    build_quality_suite_plan,
    coverage_gap_summary,
    coverage_guard,
    execute_quality_suite,
    load_quality_configuration,
    prepare_quality_suite_dry_run,
    quality_suite_guide,
    quality_suite_manifest,
    resolve_quality_profile,
    run_quality_suite,
    sync_quality_suite_documentation,
)


def _write_coverage(tmp_path: Path) -> Path:
    xml = tmp_path / "coverage.xml"
    xml.write_text(
        textwrap.dedent(
            """<?xml version="1.0" ?>
            <coverage version="7.0.0" line-rate="0.52" lines-covered="120" lines-valid="230">
              <packages>
                <package name="chiron">
                  <class name="cli.main" filename="src/chiron/cli/main.py" line-rate="0.40" statements="80" missing="48">
                    <lines>
                      <line number="10" hits="0" />
                      <line number="11" hits="0" />
                      <line number="12" hits="1" />
                      <line number="13" hits="0" />
                    </lines>
                  </class>
                  <class name="service.runtime" filename="src/chiron/service/runtime.py" line-rate="0.50" statements="50" missing="25">
                    <lines>
                      <line number="20" hits="0" />
                      <line number="21" hits="0" />
                      <line number="22" hits="1" />
                    </lines>
                  </class>
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
        "src/chiron/cli/main.py",
        "src/chiron/service/runtime.py",
    ]
    verify = report.get("src/chiron/deps/verify.py")
    assert verify is not None
    assert verify.coverage == pytest.approx(55.0)
    assert verify.missing_lines == (20, 21, 22)
    summary = report.summary
    assert summary.total_statements == 230
    assert summary.total_missing == 110
    assert summary.coverage == pytest.approx(52.0)


def test_coverage_gap_summary(tmp_path: Path) -> None:
    xml = _write_coverage(tmp_path)
    report = CoverageReport.from_xml(xml)
    summary = coverage_gap_summary(report, min_statements=30, limit=2)
    lines = summary.splitlines()
    assert lines[0].startswith("src/chiron/cli/main.py")
    assert any("service/runtime" in line for line in lines)


def test_coverage_guard(tmp_path: Path) -> None:
    xml = _write_coverage(tmp_path)
    report = CoverageReport.from_xml(xml)
    passed, message = coverage_guard(report, threshold=70.0, limit=1)
    assert not passed
    assert "below" in message
    passed_success, _ = coverage_guard(report, threshold=50.0, limit=1)
    assert passed_success


def test_build_quality_suite_monitoring_highlights_cli_and_service(tmp_path: Path) -> None:
    xml = _write_coverage(tmp_path)
    report = CoverageReport.from_xml(xml)
    plan = build_quality_suite_plan("fast")

    monitoring = build_quality_suite_monitoring(plan, report)

    focus_labels = {focus.area: focus for focus in monitoring.coverage_focus}
    assert "CLI" in focus_labels
    assert "Service" in focus_labels
    cli_focus = focus_labels["CLI"]
    service_focus = focus_labels["Service"]
    assert "src/chiron/cli/main.py" in cli_focus.modules
    assert cli_focus.total_missing == 48
    assert service_focus.modules[0] == "src/chiron/service/runtime.py"
    assert monitoring.recommendations
    assert monitoring.recommendation_details
    detail_focuses = {detail.focus for detail in monitoring.recommendation_details}
    assert {"CLI", "Service"}.issubset(detail_focuses)


def test_build_quality_suite_monitoring_handles_relative_paths(tmp_path: Path) -> None:
    xml = tmp_path / "coverage.xml"
    xml.write_text(
        textwrap.dedent(
            """<?xml version="1.0"?>
            <coverage version="7.0.0" line-rate="0.70" lines-covered="70" lines-valid="100">
              <packages>
                <package name="chiron">
                  <class name="cli" filename="cli/main.py" line-rate="0.40" statements="50" missing="30">
                    <lines>
                      <line number="10" hits="0" />
                    </lines>
                  </class>
                  <class name="service" filename="service/app.py" line-rate="0.60" statements="40" missing="16">
                    <lines>
                      <line number="5" hits="0" />
                    </lines>
                  </class>
                  <class name="mcp" filename="mcp/server.py" line-rate="0.55" statements="30" missing="14">
                    <lines>
                      <line number="8" hits="0" />
                    </lines>
                  </class>
                </package>
              </packages>
            </coverage>
            """
        ).strip(),
        encoding="utf-8",
    )

    report = CoverageReport.from_xml(xml)
    plan = build_quality_suite_plan("fast")

    monitoring = build_quality_suite_monitoring(plan, report)

    focus = {summary.area: summary for summary in monitoring.coverage_focus}
    assert "CLI" in focus and focus["CLI"].modules == ("cli/main.py",)
    assert focus["CLI"].total_missing == 30
    assert "Service" in focus
    assert "service/app.py" in focus["Service"].modules

    recommendation_modules = {
        (detail.focus, detail.module) for detail in monitoring.recommendation_details
    }
    assert ("CLI", "cli/main.py") in recommendation_modules
    assert ("Service", "service/app.py") in recommendation_modules


def test_quality_suite_run_report_serialises_monitoring_payload() -> None:
    plan = build_quality_suite_plan("fast")
    monitoring = QualitySuiteMonitoring(
        coverage_focus=(
            CoverageFocusSummary(
                area="CLI",
                modules=("src/chiron/cli/main.py",),
                total_missing=48,
                average_coverage=40.0,
                threshold=85.0,
            ),
        ),
        recommendations=("Add CLI contract tests",),
        recommendation_details=(
            QualitySuiteRecommendation(
                focus="CLI",
                module="src/chiron/cli/main.py",
                missing=48,
                coverage=40.0,
                severity="improve",
                missing_lines=(10, 11, 13),
                action="Add CLI contract tests",
            ),
        ),
        source="coverage.xml",
    )
    report = QualitySuiteRunReport(
        plan=plan,
        results=(CommandResult(("echo", "tests"), 0, 0.1, "", gate="tests"),),
        started_at=0.0,
        finished_at=1.0,
        monitoring=monitoring,
    )

    payload = report.to_payload()
    assert payload["monitoring"]["source"] == "coverage.xml"
    assert payload["monitoring"]["coverage_focus"][0]["area"] == "CLI"
    assert payload["monitoring"]["recommendations"] == ["Add CLI contract tests"]
    details = payload["monitoring"]["recommendation_details"]
    assert details[0]["focus"] == "CLI"
    assert details[0]["severity"] == "improve"
    lines = report.render_monitoring_lines()
    assert any("CLI" in line for line in lines)


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


def test_build_quality_suite_plan_applies_toggles() -> None:
    plan = build_quality_suite_plan("fast", toggles={"lint": False, "types": True})
    assert plan.gate_names() == ("tests", "types")
    assert plan.toggles == (("lint", False), ("types", True))
    lines = plan.render_lines()
    assert lines[0].startswith("1. Run pytest suite")
    assert any("mypy" in line for line in lines)


def test_quality_suite_guide_includes_monitoring_follow_ups(tmp_path: Path) -> None:
    xml = _write_coverage(tmp_path)
    report = CoverageReport.from_xml(xml)
    plan = build_quality_suite_plan("fast")
    monitoring = build_quality_suite_monitoring(plan, report)
    guide_lines = quality_suite_guide(
        plan,
        insights=build_quality_suite_insights(plan),
        monitoring=monitoring,
    )
    assert guide_lines[0].startswith("Quality suite quickstart")
    assert any("--monitor" in line for line in guide_lines)
    assert any("Monitored follow-ups" in line for line in guide_lines)
    assert any("CLI" in line for line in guide_lines)
    assert any("--contracts" in line for line in guide_lines)


def test_quality_suite_guide_prompts_for_monitoring_when_missing() -> None:
    plan = build_quality_suite_plan("fast")
    guide_lines = quality_suite_guide(plan)
    assert any("Tip:" in line for line in guide_lines)
    assert any("--contracts" in line for line in guide_lines)


def test_quality_suite_manifest_includes_plans() -> None:
    manifest = quality_suite_manifest()
    assert "fast" in manifest["profiles"]
    gates = manifest["gates"]
    assert isinstance(gates, dict)
    assert "tests" in gates
    assert "contracts" in gates
    plan_payload = manifest["plans"]["full"]
    assert plan_payload["profile"] == "full"
    assert plan_payload["plan"][0]["key"] == plan_payload["gates"][0]["name"]
    assert any(gate["name"] == "contracts" for gate in plan_payload["gates"])

    insights = plan_payload["insights"]
    assert insights["total_gates"] == len(plan_payload["gates"])
    assert "tests" in insights["critical_gates"]


def test_quality_suite_plan_insights_track_categories() -> None:
    plan = build_quality_suite_plan(
        "fast", toggles={"lint": False, "security": True}
    )
    insights = build_quality_suite_insights(plan)

    assert insights.total_gates == len(plan.gates)
    categories = dict(insights.category_breakdown)
    assert categories["tests"] == 1
    assert "security" in insights.optional_gates or not insights.optional_gates
    assert insights.disabled_toggles == ("lint",)
    assert ("security", True) in insights.toggles


def test_build_quality_suite_plan_supports_contracts_toggle() -> None:
    plan = build_quality_suite_plan("fast", toggles={"contracts": True})
    gate_names = plan.gate_names()
    assert "contracts" in gate_names
    assert plan.toggles == (("contracts", True),)
    # Contracts gate should appear after core tests for deterministic ordering.
    assert gate_names.index("contracts") > gate_names.index("tests")

    full_plan = build_quality_suite_plan("full", toggles={"contracts": False})
    assert "contracts" not in full_plan.gate_names()
    assert ("contracts", False) in full_plan.toggles


def test_execute_quality_suite_wraps_results(monkeypatch: MonkeyPatch) -> None:
    plan = build_quality_suite_plan("fast")
    command_results = [
        CommandResult(("echo", "tests"), 0, 0.1, "", gate="tests"),
        CommandResult(("echo", "lint"), 1, 0.2, "lint failed", gate="lint"),
    ]

    def fake_run_quality_suite(  # type: ignore[override]
        commands, *, halt_on_failure, progress=None
    ):
        assert halt_on_failure
        assert list(commands) == list(plan.gates)
        assert progress is None
        return command_results

    monkeypatch.setattr(
        "chiron.dev_toolbox.run_quality_suite", fake_run_quality_suite
    )

    report = execute_quality_suite(plan)

    payload = report.to_payload()
    assert payload["status"] == "failed"
    assert payload["failing_gates"] == ["lint"]
    assert payload["plan"]["profile"] == "fast"
    assert payload["results"][1]["output"] == "lint failed"
    assert payload["insights"]["profile"] == "fast"
    summary = report.render_text_summary()
    assert "lint" in summary
    assert "All gates passed" not in summary


def test_run_quality_suite_emits_progress_events(monkeypatch: MonkeyPatch) -> None:
    quality_gate = QualityGate(
        name="tests",
        command=("echo", "tests"),
        description="Run tests",
        category="tests",
    )
    result = CommandResult(quality_gate.command, 0, 0.12, "passed", gate=quality_gate.name)

    def fake_run_command(command, *, check=True, cwd=None, env=None, gate=None):
        assert tuple(command) == quality_gate.command
        assert gate == quality_gate.name
        return result

    events: list[QualitySuiteProgressEvent] = []
    monkeypatch.setattr("chiron.dev_toolbox.run_command", fake_run_command)

    outcomes = run_quality_suite([quality_gate], progress=events.append)

    assert outcomes == [result]
    assert [event.status for event in events] == ["started", "completed"]
    completed = events[-1]
    assert completed.result is result
    assert completed.index == 1 and completed.total == 1


def test_execute_quality_suite_forwards_progress(monkeypatch: MonkeyPatch) -> None:
    gate = QualityGate(
        name="tests",
        command=("echo", "tests"),
        description="Run tests",
        category="tests",
    )
    plan = QualitySuitePlan(profile="demo", gates=(gate,))
    result = CommandResult(gate.command, 0, 0.05, "", gate=gate.name)
    emitted: list[str] = []

    def fake_run_quality_suite(  # type: ignore[override]
        commands, *, halt_on_failure, progress=None
    ):
        assert halt_on_failure
        assert list(commands) == [gate]
        assert progress is not None
        progress(
            QualitySuiteProgressEvent(
                index=1,
                total=1,
                command=gate.command,
                gate=gate,
                status="started",
            )
        )
        progress(
            QualitySuiteProgressEvent(
                index=1,
                total=1,
                command=gate.command,
                gate=gate,
                status="completed",
                result=result,
            )
        )
        return [result]

    monkeypatch.setattr(
        "chiron.dev_toolbox.run_quality_suite", fake_run_quality_suite
    )

    def progress(event: QualitySuiteProgressEvent) -> None:
        emitted.append(event.status)

    report = execute_quality_suite(plan, progress=progress)

    assert report.results == (result,)
    assert emitted == ["started", "completed"]


def test_prepare_quality_suite_dry_run_serialises_actions(tmp_path: Path) -> None:
    xml = _write_coverage(tmp_path)
    report = CoverageReport.from_xml(xml)
    plan = build_quality_suite_plan("fast")
    monitoring = build_quality_suite_monitoring(
        plan,
        report,
        threshold=60.0,
        limit=2,
        min_statements=10,
        source=str(xml),
    )
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)

    dry_run = prepare_quality_suite_dry_run(
        plan,
        monitoring=monitoring,
        generated_at=timestamp,
    )

    payload = dry_run.to_payload()
    assert payload["generated_at"] == timestamp.isoformat()
    assert payload["plan"]["profile"] == "fast"
    assert payload["guide"][0].startswith("Quality suite quickstart")
    assert payload["actions"], "Expected monitoring-driven actions in dry-run payload"
    assert payload["monitoring"]["source"] == str(xml)


def test_prepare_quality_suite_dry_run_without_monitoring_has_empty_actions() -> None:
    plan = build_quality_suite_plan("fast")
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)

    dry_run = prepare_quality_suite_dry_run(
        plan,
        monitoring=None,
        generated_at=timestamp,
    )

    assert dry_run.actions == ()
    payload = dry_run.to_payload()
    assert payload["actions"] == []
    assert "monitoring" not in payload


def test_quality_suite_documentation_lines_include_docs_gate() -> None:
    plan = build_quality_suite_plan("full")
    dry_run = prepare_quality_suite_dry_run(plan)

    lines = dry_run.render_documentation_lines()

    assert any("`docs`" in line for line in lines)
    assert lines[0].startswith("### Developer Toolbox Quality Suite Snapshot")
    assert any("sync-docs" in line for line in lines)


def test_sync_quality_suite_documentation_updates_block(tmp_path: Path) -> None:
    plan = build_quality_suite_plan("full")
    dry_run = prepare_quality_suite_dry_run(plan)
    doc_path = tmp_path / "docs.md"
    doc_path.write_text(
        "\n".join(
            [
                "Intro section",
                "<!-- BEGIN QUALITY_SUITE_AUTODOC -->",
                "stale content",
                "<!-- END QUALITY_SUITE_AUTODOC -->",
                "Outro section",
            ]
        ),
        encoding="utf-8",
    )

    sync_quality_suite_documentation(dry_run, doc_path)

    updated = doc_path.read_text(encoding="utf-8")
    assert "Developer Toolbox Quality Suite Snapshot" in updated
    assert "`docs`" in updated
    assert updated.count("<!-- BEGIN QUALITY_SUITE_AUTODOC -->") == 1
    assert updated.count("<!-- END QUALITY_SUITE_AUTODOC -->") == 1


def test_sync_quality_suite_documentation_requires_markers(tmp_path: Path) -> None:
    plan = build_quality_suite_plan("full")
    dry_run = prepare_quality_suite_dry_run(plan)
    doc_path = tmp_path / "docs.md"
    doc_path.write_text("No markers present", encoding="utf-8")

    with pytest.raises(DocumentationSyncError):
        sync_quality_suite_documentation(dry_run, doc_path)


def test_quality_gate_documentation_block_matches_generator() -> None:
    plan = build_quality_suite_plan("full")
    dry_run = prepare_quality_suite_dry_run(plan)
    doc_path = Path("docs/QUALITY_GATES.md")
    contents = doc_path.read_text(encoding="utf-8")
    begin = "<!-- BEGIN QUALITY_SUITE_AUTODOC -->"
    end = "<!-- END QUALITY_SUITE_AUTODOC -->"
    assert begin in contents and end in contents
    block = contents.split(begin, 1)[1].split(end, 1)[0]
    doc_lines = [line.rstrip() for line in block.strip("\n").splitlines()]
    expected_lines = list(dry_run.render_documentation_lines())

    def _filter_generated(lines: list[str]) -> list[str]:
        return [line for line in lines if not line.startswith("**Generated**")]

    assert _filter_generated(doc_lines) == _filter_generated(expected_lines)
