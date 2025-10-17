from __future__ import annotations

import json
import textwrap
from datetime import UTC, datetime
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

from hephaestus.toolbox import (
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
    analyze_refactor_opportunities,
    build_quality_suite_insights,
    build_quality_suite_monitoring,
    build_quality_suite_plan,
    coverage_gap_summary,
    coverage_guard,
    discover_diataxis_entries,
    dump_diataxis_entries,
    execute_quality_suite,
    load_diataxis_entries,
    load_quality_configuration,
    prepare_quality_suite_dry_run,
    quality_suite_guide,
    quality_suite_manifest,
    resolve_quality_profile,
    run_quality_suite,
    sync_diataxis_documentation,
    sync_quality_suite_documentation,
)


def _write_coverage(tmp_path: Path) -> Path:
    xml = tmp_path / "coverage.xml"
    xml.write_text(
        textwrap.dedent(
            """<?xml version="1.0" ?>
            <coverage version="7.0.0" line-rate="0.52" lines-covered="120" lines-valid="230">
              <packages>
                <package name="hephaestus">
                  <class name="cli.main" filename="src/hephaestus/cli/main.py" line-rate="0.40" statements="80" missing="48">
                    <lines>
                      <line number="10" hits="0" />
                      <line number="11" hits="0" />
                      <line number="12" hits="1" />
                      <line number="13" hits="0" />
                    </lines>
                  </class>
                  <class name="service.runtime" filename="src/hephaestus/service/runtime.py" line-rate="0.50" statements="50" missing="25">
                    <lines>
                      <line number="20" hits="0" />
                      <line number="21" hits="0" />
                      <line number="22" hits="1" />
                    </lines>
                  </class>
                  <class name="core" filename="src/hephaestus/core.py" line-rate="1.0" statements="10" missing="0">
                    <lines>
                      <line number="1" hits="1" />
                    </lines>
                  </class>
                  <class name="deps.graph" filename="src/hephaestus/deps/graph.py" line-rate="0.62" statements="50" missing="19">
                    <lines>
                      <line number="10" hits="0" />
                      <line number="11" hits="0" />
                      <line number="12" hits="1" />
                    </lines>
                  </class>
                  <class name="deps.verify" filename="src/hephaestus/deps/verify.py" line-rate="0.55" statements="40" missing="18">
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
        "src/hephaestus/cli/main.py",
        "src/hephaestus/service/runtime.py",
    ]
    verify = report.get("src/hephaestus/deps/verify.py")
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
    assert lines[0].startswith("src/hephaestus/cli/main.py")
    assert any("service/runtime" in line for line in lines)


def test_coverage_guard(tmp_path: Path) -> None:
    xml = _write_coverage(tmp_path)
    report = CoverageReport.from_xml(xml)
    passed, message = coverage_guard(report, threshold=70.0, limit=1)
    assert not passed
    assert "below" in message
    passed_success, _ = coverage_guard(report, threshold=50.0, limit=1)
    assert passed_success


def test_build_quality_suite_monitoring_highlights_cli_and_service(
    tmp_path: Path,
) -> None:
    xml = _write_coverage(tmp_path)
    report = CoverageReport.from_xml(xml)
    plan = build_quality_suite_plan("fast")

    monitoring = build_quality_suite_monitoring(plan, report)

    focus_labels = {focus.area: focus for focus in monitoring.coverage_focus}
    assert "CLI" in focus_labels
    assert "Service" in focus_labels
    cli_focus = focus_labels["CLI"]
    service_focus = focus_labels["Service"]
    assert "src/hephaestus/cli/main.py" in cli_focus.modules
    assert cli_focus.total_missing == 48
    assert service_focus.modules[0] == "src/hephaestus/service/runtime.py"
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
                <package name="hephaestus">
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
                modules=("src/hephaestus/cli/main.py",),
                total_missing=48,
                average_coverage=40.0,
                threshold=85.0,
            ),
        ),
        recommendations=("Add CLI contract tests",),
        recommendation_details=(
            QualitySuiteRecommendation(
                focus="CLI",
                module="src/hephaestus/cli/main.py",
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
            [tool.hephaestus.toolkit.gates.docs]
            command = ["uv", "run", "--extra", "docs", "sphinx-build", "docs", "site"]
            category = "docs"
            description = "Build documentation"

            [tool.hephaestus.toolkit.profiles.docs]
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
    plan = build_quality_suite_plan("fast", toggles={"lint": False, "security": True})
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

    monkeypatch.setattr("hephaestus.toolbox.run_quality_suite", fake_run_quality_suite)

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
    result = CommandResult(
        quality_gate.command, 0, 0.12, "passed", gate=quality_gate.name
    )

    def fake_run_command(command, *, check=True, cwd=None, env=None, gate=None):
        assert tuple(command) == quality_gate.command
        assert gate == quality_gate.name
        return result

    events: list[QualitySuiteProgressEvent] = []
    monkeypatch.setattr("hephaestus.toolbox.run_command", fake_run_command)

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

    monkeypatch.setattr("hephaestus.toolbox.run_quality_suite", fake_run_quality_suite)

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


def test_sync_diataxis_documentation_updates_block(tmp_path: Path) -> None:
    config_path = tmp_path / "diataxis.json"
    config_path.write_text(
        json.dumps(
            {
                "tutorials": [
                    {
                        "title": "First run",
                        "path": "tutorials/first.md",
                        "summary": "Intro walkthrough",
                    }
                ],
                "how_to": [],
                "reference": [],
                "explanation": [],
            }
        ),
        encoding="utf-8",
    )
    doc_path = tmp_path / "index.md"
    doc_path.write_text(
        "\n".join(
            [
                "Preamble",
                "<!-- BEGIN DIATAXIS_AUTODOC -->",
                "stale",
                "<!-- END DIATAXIS_AUTODOC -->",
                "Footer",
            ]
        ),
        encoding="utf-8",
    )

    sync_diataxis_documentation(config_path, doc_path)

    contents = doc_path.read_text(encoding="utf-8")
    assert "First run" in contents
    assert "Tutorials" in contents
    assert "Updated automatically" in contents


def test_sync_diataxis_documentation_requires_markers(tmp_path: Path) -> None:
    config_path = tmp_path / "diataxis.json"
    config_path.write_text(
        json.dumps(
            {
                "tutorials": [],
                "how_to": [],
                "reference": [],
                "explanation": [],
            }
        ),
        encoding="utf-8",
    )
    doc_path = tmp_path / "index.md"
    doc_path.write_text("Missing markers", encoding="utf-8")

    with pytest.raises(DocumentationSyncError):
        sync_diataxis_documentation(config_path, doc_path)


def test_discover_diataxis_entries_extracts_front_matter(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    tutorials_dir = docs_dir / "tutorials"
    tutorials_dir.mkdir(parents=True)
    (docs_dir / "index.md").write_text("<!-- overview -->", encoding="utf-8")
    tutorials_dir.joinpath("first.md").write_text(
        textwrap.dedent(
            """---
            title: First Tutorial
            diataxis: tutorials
            summary: Walkthrough for newcomers.
            ---

            # First Tutorial
            """
        ).strip(),
        encoding="utf-8",
    )
    (docs_dir / "howto.md").write_text(
        textwrap.dedent(
            """---
            title: Build Gate
            diataxis: how_to
            summary: Run the build quality gate locally.
            ---

            # Build Gate
            """
        ).strip(),
        encoding="utf-8",
    )

    entries = discover_diataxis_entries(docs_dir)

    assert [entry.title for entry in entries["tutorials"]] == ["First Tutorial"]
    assert entries["tutorials"][0].path == "tutorials/first.md"
    assert entries["tutorials"][0].summary == "Walkthrough for newcomers."
    assert entries["how_to"][0].path == "howto.md"
    assert entries["reference"] == ()
    assert entries["explanation"] == ()

    config_path = tmp_path / "diataxis.json"
    dump_diataxis_entries(config_path, entries)
    persisted = load_diataxis_entries(config_path)
    assert persisted == entries


def test_discover_diataxis_entries_requires_summary(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    docs_dir.joinpath("guide.md").write_text(
        textwrap.dedent(
            """---
            title: Missing Summary
            diataxis: reference
            ---

            # Missing Summary
            """
        ).strip(),
        encoding="utf-8",
    )

    with pytest.raises(DocumentationSyncError):
        discover_diataxis_entries(docs_dir)


def test_load_diataxis_entries_validates_file(tmp_path: Path) -> None:
    config_path = tmp_path / "missing.json"
    with pytest.raises(DocumentationSyncError):
        load_diataxis_entries(config_path)


def test_repository_diataxis_mapping_is_in_sync() -> None:
    """Ensure docs/diataxis.json matches the discovered documentation tree."""

    config_path = Path("docs/diataxis.json")
    docs_dir = Path("docs")

    assert config_path.exists(), "Missing docs/diataxis.json configuration"
    assert docs_dir.exists(), "Missing docs directory"

    persisted = load_diataxis_entries(config_path)
    discovered = discover_diataxis_entries(docs_dir)

    assert (
        persisted == discovered
    ), "Run `hephaestus tools docs sync-diataxis --discover --docs-dir docs`"


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


def test_analyze_refactor_opportunities_highlights_complex_symbols(
    tmp_path: Path,
) -> None:
    module = tmp_path / "demo.py"
    module.write_text(
        textwrap.dedent(
            """
            def narrow_ok():
                return 1

            def sprawling_function(value):
                total = 0
                for index in range(60):
                    if value > index:
                        value += index
                    else:
                        value -= index
                    total += index
                if value % 2 == 0:
                    value += total
                else:
                    value -= total
                return value

            class Massive:
                def a(self):
                    return 1

                def b(self):
                    return 2

                def c(self):
                    return 3

                def d(self):
                    return 4

                def e(self):
                    return 5

            # TODO: tighten API surface
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    report = analyze_refactor_opportunities(
        (module,),
        max_function_length=10,
        max_class_methods=4,
    )

    kinds = {op.kind for op in report.opportunities}
    assert {"function_length", "class_size", "todo_comment"}.issubset(kinds)
    longest = max(report.opportunities, key=lambda op: op.severity_rank)
    assert longest.kind == "function_length"
    assert longest.symbol == "sprawling_function"


def test_analyze_refactor_opportunities_includes_coverage(tmp_path: Path) -> None:
    module = tmp_path / "package" / "module.py"
    module.parent.mkdir()
    module.write_text(
        textwrap.dedent(
            """
            def short():
                return 1
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    coverage_xml = tmp_path / "coverage.xml"
    coverage_xml.write_text(
        textwrap.dedent(
            f"""
            <?xml version="1.0" ?>
            <coverage version="7.0.0" line-rate="0.40" lines-covered="4" lines-valid="10">
              <packages>
                <package name="demo">
                  <class name="package.module" filename="{module}" line-rate="0.40" statements="10" missing="6">
                    <lines>
                      <line number="1" hits="0" />
                    </lines>
                  </class>
                </package>
              </packages>
            </coverage>
            """
        ).strip(),
        encoding="utf-8",
    )

    report = analyze_refactor_opportunities(
        (module,),
        coverage_xml=coverage_xml,
        coverage_threshold=80.0,
    )

    low_coverage = [
        op
        for op in report.opportunities
        if op.kind == "low_coverage" and module.name in op.message
    ]
    assert low_coverage, "Expected low coverage opportunity for module"


def test_analyze_refactor_opportunities_flags_complexity_and_parameters(
    tmp_path: Path,
) -> None:
    module = tmp_path / "complex.py"
    module.write_text(
        textwrap.dedent(
            """
            def intricate(a, b, c, d):
                total = 0
                for index in range(3):
                    if index % 2 == 0:
                        try:
                            total += index
                        except ValueError:
                            total -= 1
                    else:
                        if a > index:
                            total += a
                        else:
                            total -= index
                if total and (a and b):
                    return total
                return a + b + c + d
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    report = analyze_refactor_opportunities(
        (module,),
        max_function_length=50,
        max_class_methods=10,
        max_cyclomatic_complexity=4,
        max_parameters=3,
    )

    complexity = next(
        (op for op in report.opportunities if op.kind == "cyclomatic_complexity"),
        None,
    )
    assert complexity is not None, "Expected cyclomatic complexity finding"
    assert complexity.metric is not None and complexity.metric > complexity.threshold

    parameters = next(
        (op for op in report.opportunities if op.kind == "long_parameter_list"),
        None,
    )
    assert parameters is not None, "Expected parameter pressure finding"
    assert parameters.metric == 4
    assert parameters.threshold == 3


def test_analyze_refactor_opportunities_highlights_missing_docstrings(
    tmp_path: Path,
) -> None:
    module = tmp_path / "docstrings.py"
    module.write_text(
        textwrap.dedent(
            """
            def public_api(value):
                total = 0
                for item in range(6):
                    total += value + item
                for other in range(6):
                    total += other
                return total
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    report = analyze_refactor_opportunities(
        (module,),
        min_docstring_length=5,
    )

    docstring_issue = next(
        (op for op in report.opportunities if op.kind == "missing_docstring"),
        None,
    )
    assert docstring_issue is not None
    assert docstring_issue.symbol == "public_api"


def test_refactor_report_payload_is_sorted(tmp_path: Path) -> None:
    module = tmp_path / "refactor.py"
    module.write_text(
        textwrap.dedent(
            """
            def branchy(value):
                if value:
                    return value
                return None
            # TODO: simplify branching
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    report = analyze_refactor_opportunities((module,))

    payload = report.to_payload()
    assert payload["opportunities"], "Expected at least one opportunity"
    ranks = [item["severity_rank"] for item in payload["opportunities"]]
    assert ranks == sorted(ranks, reverse=True)


def test_analyze_hotspots_combines_churn_and_complexity(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    from hephaestus.toolbox import analyze_hotspots

    # Create a simple test file structure
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    complex_file = src_dir / "complex.py"
    complex_file.write_text(
        textwrap.dedent(
            """
            class LargeClass:
                def method1(self): pass
                def method2(self): pass
                def method3(self): pass
                def method4(self): pass
                def method5(self): pass
                def method6(self): pass
                def method7(self): pass
                def method8(self): pass

            def very_long_function():
                line1 = 1
                line2 = 2
                line3 = 3
                line4 = 4
                line5 = 5
                line6 = 6
                line7 = 7
                line8 = 8
                line9 = 9
                line10 = 10
                line11 = 11
                line12 = 12
            """
        ),
        encoding="utf-8",
    )

    simple_file = src_dir / "simple.py"
    simple_file.write_text(
        textwrap.dedent(
            """
            def simple():
                return 1
            """
        ),
        encoding="utf-8",
    )

    # Mock git log to return controlled churn data
    def fake_subprocess_run(cmd, *args, **kwargs):
        class FakeResult:
            returncode = 0
            stdout = f"{complex_file.relative_to(tmp_path)}\n{complex_file.relative_to(tmp_path)}\n{simple_file.relative_to(tmp_path)}\n"

        if cmd[0] == "git" and cmd[1] == "log":
            return FakeResult()
        raise FileNotFoundError()

    monkeypatch.setattr("subprocess.run", fake_subprocess_run)

    report = analyze_hotspots(repo_root=tmp_path, min_complexity=0, min_churn=1)

    assert len(report.entries) == 2
    # Complex file should rank higher (more complexity * more churn)
    assert report.entries[0].path == complex_file.relative_to(tmp_path)
    assert report.entries[0].churn_count == 2
    assert report.entries[0].complexity_score > 0
    assert report.entries[1].path == simple_file.relative_to(tmp_path)
    assert report.entries[1].churn_count == 1


def test_analyze_hotspots_without_git(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    from hephaestus.toolbox import analyze_hotspots

    # Create a simple test file
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    test_file = src_dir / "test.py"
    test_file.write_text(
        textwrap.dedent(
            """
            def simple():
                return 1
            """
        ),
        encoding="utf-8",
    )

    # Mock subprocess to simulate git not available
    def fake_subprocess_run(cmd, *args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr("subprocess.run", fake_subprocess_run)

    # Should not crash when git is unavailable
    report = analyze_hotspots(repo_root=tmp_path, min_complexity=0, min_churn=0)

    # Without git, there should be no churn data, so no hotspots
    # (since default min_churn is 2, but we set it to 0 here)
    assert isinstance(report.entries, tuple)


def test_hotspot_report_renders_lines() -> None:
    from hephaestus.toolbox import HotspotEntry, HotspotReport

    entry1 = HotspotEntry(
        path=Path("src/high.py"),
        complexity_score=100,
        churn_count=10,
        hotspot_score=1000,
    )
    entry2 = HotspotEntry(
        path=Path("src/low.py"),
        complexity_score=20,
        churn_count=2,
        hotspot_score=40,
    )

    report = HotspotReport(entries=(entry1, entry2))
    lines = list(report.render_lines(limit=5))

    assert len(lines) > 0
    assert "high.py" in "\n".join(lines)
    assert "hotspot=1000" in "\n".join(lines)


def test_hotspot_report_empty() -> None:
    from hephaestus.toolbox import HotspotReport

    report = HotspotReport(entries=())
    lines = list(report.render_lines())

    assert "No hotspots detected" in "\n".join(lines)


def test_hotspot_entry_payload() -> None:
    from hephaestus.toolbox import HotspotEntry

    entry = HotspotEntry(
        path=Path("src/test.py"),
        complexity_score=50,
        churn_count=5,
        hotspot_score=250,
    )

    payload = entry.to_payload()
    assert payload["path"] == "src/test.py"
    assert payload["complexity_score"] == 50
    assert payload["churn_count"] == 5
    assert payload["hotspot_score"] == 250
