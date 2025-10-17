"""Hephaestus CLI — Developer tooling for quality automation and refactoring."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from hephaestus.planning import render_execution_plan_table
from hephaestus.toolbox import (
    CoverageReport,
    DiataxisEntry,
    DocumentationSyncError,
    QualitySuiteProgressEvent,
    analyze_hotspots,
    analyze_refactor_opportunities,
    available_quality_profiles,
    build_quality_suite_monitoring,
    build_quality_suite_plan,
    coverage_focus,
    coverage_gap_summary,
    coverage_guard,
    coverage_hotspots,
    discover_diataxis_entries,
    dump_diataxis_entries,
    execute_quality_suite,
    load_quality_configuration,
    prepare_quality_suite_dry_run,
    quality_suite_manifest,
    sync_diataxis_documentation,
    sync_quality_suite_documentation,
)

Context = typer.Context

logger = logging.getLogger(__name__)

app = typer.Typer(help="Hephaestus — quality automation and refactoring toolkit")

tools_app = typer.Typer(help="Developer tools and utilities")
app.add_typer(tools_app, name="tools")

coverage_app = typer.Typer(help="Test coverage analytics")
tools_app.add_typer(coverage_app, name="coverage")

refactor_app = typer.Typer(help="Refactor insights and code health diagnostics")
tools_app.add_typer(refactor_app, name="refactor")

docs_app = typer.Typer(help="Documentation workflows")
tools_app.add_typer(docs_app, name="docs")


@app.command()
def version() -> None:
    """Display Hephaestus version."""
    from hephaestus import __version__

    typer.echo(f"Hephaestus version {__version__}")


def _render_progress_bar(completed: int, total: int, *, width: int = 24) -> str:
    """Return a textual progress bar for *completed*/*total* gates."""

    safe_total = max(total, 1)
    safe_completed = max(0, min(completed, safe_total))
    ratio = safe_completed / safe_total
    filled = int(ratio * width)
    if safe_completed == safe_total:
        filled = width
    empty = width - filled
    bar = "█" * filled + "░" * empty
    return f"[{bar}] {safe_completed}/{total}"


def _format_progress_label(event: QualitySuiteProgressEvent) -> str:
    """Return a human-readable label for a progress *event*."""

    if event.gate is None:
        return " ".join(event.command) or event.name
    label = event.gate.name
    category = event.gate.category.replace("_", " ")
    if category:
        label = f"{label} [{category}]"
    if event.gate.description and event.gate.description != event.gate.name:
        label = f"{label} — {event.gate.description}"
    return label


def _build_quality_suite_progress_renderer(
    console: Console, total: int
) -> Callable[[QualitySuiteProgressEvent], None]:
    """Return a renderer that prints progress updates to *console*."""

    def _render(event: QualitySuiteProgressEvent) -> None:
        if event.status == "started":
            completed = event.index - 1
            bar = _render_progress_bar(completed, total)
            console.print(f"[cyan]▶[/cyan] {bar} {_format_progress_label(event)}")
            return

        completed = event.index
        bar = _render_progress_bar(completed, total)
        success = bool(event.result and event.result.returncode == 0)
        icon = "[green]✅[/green]" if success else "[red]❌[/red]"
        duration = "--"
        if event.result is not None:
            duration = f"{event.result.duration:.2f}s"
        console.print(f"{icon} {bar} {_format_progress_label(event)} ({duration})")
        if not success and event.result is not None:
            output = event.result.output.strip()
            if output:
                console.print(Panel(Text(output, style="red"), title="Command output"))

    return _render


@tools_app.command("qa")
def tools_quality_suite(
    ctx: Context,
    profile: str = typer.Option(
        "full",
        "--profile",
        "-p",
        help="Quality profile to execute",
    ),
    list_profiles: bool = typer.Option(
        False,
        "--list-profiles",
        help="List available profiles and exit",
    ),
    manifest: bool = typer.Option(
        False,
        "--manifest",
        help="Print a JSON manifest for gates and plans and exit",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Show resolved gates before executing",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Display the plan without running commands",
    ),
    guide: bool = typer.Option(
        False,
        "--guide",
        help="Print an operator quickstart guide and exit",
    ),
    tests: bool | None = typer.Option(
        None,
        "--tests/--no-tests",
        help="Run pytest with coverage",
        show_default=False,
    ),
    lint: bool | None = typer.Option(
        None,
        "--lint/--no-lint",
        help="Run Ruff linting",
        show_default=False,
    ),
    types: bool | None = typer.Option(
        None,
        "--types/--no-types",
        help="Run type checking",
        show_default=False,
    ),
    security: bool | None = typer.Option(
        None,
        "--security/--no-security",
        help="Run Bandit security scan",
        show_default=False,
    ),
    docs: bool | None = typer.Option(
        None,
        "--docs/--no-docs",
        help="Build project documentation",
        show_default=False,
    ),
    build: bool | None = typer.Option(
        None,
        "--build/--no-build",
        help="Build wheel and sdist",
        show_default=False,
    ),
    contracts: bool | None = typer.Option(
        None,
        "--contracts/--no-contracts",
        help="Run Pact contract tests",
        show_default=False,
    ),
    halt: bool = typer.Option(
        True, "--halt/--keep-going", help="Stop on first failure"
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON results"),
    save_report: Path | None = typer.Option(
        None,
        "--save-report",
        help="Write JSON results to the provided path",
    ),
    monitor: bool = typer.Option(
        False,
        "--monitor",
        help="Include coverage monitoring insights",
    ),
    coverage_xml: Path = typer.Option(
        Path("coverage.xml"),
        "--coverage-xml",
        help="Path to coverage XML for monitoring insights",
    ),
    monitor_threshold: float = typer.Option(
        85.0,
        "--monitor-threshold",
        help="Threshold used to flag monitored coverage focus areas",
    ),
    monitor_limit: int = typer.Option(
        3,
        "--monitor-limit",
        min=1,
        help="Maximum modules to display per monitored focus area",
    ),
    monitor_min_statements: int = typer.Option(
        25,
        "--monitor-min-statements",
        min=0,
        help="Minimum statements required for modules to be monitored",
    ),
    sync_docs: Path | None = typer.Option(
        None,
        "--sync-docs",
        help="Update the documentation snippet at the provided path and exit",
    ),
    docs_marker: str = typer.Option(
        "QUALITY_SUITE_AUTODOC",
        "--docs-marker",
        help="Marker name used to locate the auto-generated documentation block",
    ),
) -> None:
    """Run Hephaestus quality-suite automation."""

    console: Console | None = Console() if not json_output else None

    if list_profiles:
        profiles = available_quality_profiles()
        if json_output:
            typer.echo(
                json.dumps(
                    {"profiles": [profile.name for profile in profiles]}, indent=2
                )
            )
        else:
            typer.echo("Available profiles:")
            for entry in profiles:
                typer.echo(f"  • {entry.name}: {entry.description}")
        raise typer.Exit(0)

    try:
        config = load_quality_configuration()
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if manifest:
        manifest_payload = quality_suite_manifest(config=config)
        typer.echo(json.dumps(manifest_payload, indent=2))
        raise typer.Exit(0)

    try:
        plan = build_quality_suite_plan(
            profile,
            config=config,
            toggles={
                "tests": tests,
                "lint": lint,
                "types": types,
                "security": security,
                "docs": docs,
                "build": build,
                "contracts": contracts,
            },
        )
    except KeyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if not plan.gates:
        typer.echo("No quality gates selected.")
        raise typer.Exit(code=0)

    monitoring = None
    if monitor:
        try:
            coverage_report = CoverageReport.from_xml(coverage_xml)
        except FileNotFoundError as exc:
            typer.echo(f"Coverage report not found at {coverage_xml}", err=True)
            raise typer.Exit(1) from exc
        monitoring = build_quality_suite_monitoring(
            plan,
            coverage_report,
            threshold=monitor_threshold,
            limit=monitor_limit,
            min_statements=monitor_min_statements,
            source=str(coverage_xml),
        )

    dry_run_snapshot = prepare_quality_suite_dry_run(plan, monitoring=monitoring)
    plan_insights = dry_run_snapshot.insights

    if sync_docs is not None:
        try:
            updated_path = sync_quality_suite_documentation(
                dry_run_snapshot,
                sync_docs,
                marker=docs_marker,
            )
        except DocumentationSyncError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc
        documentation_lines = list(dry_run_snapshot.render_documentation_lines())
        payload = {
            "status": "updated",
            "path": str(updated_path),
            "marker": docs_marker,
            "documentation": documentation_lines,
        }
        if json_output:
            typer.echo(json.dumps(payload, indent=2))
        else:
            typer.echo(
                f"Documentation block updated in {updated_path} using marker {docs_marker}."
            )
        raise typer.Exit(0)

    if guide:
        guide_lines = list(dry_run_snapshot.guide)
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "guide": guide_lines,
                        "dry_run": dry_run_snapshot.to_payload(),
                    },
                    indent=2,
                )
            )
        else:
            typer.echo("\n".join(guide_lines))
        raise typer.Exit(0)

    if explain or dry_run:
        if not json_output and console is not None:
            console.print("[bold]Resolved quality gates:[/bold]")
            console.print(
                render_execution_plan_table(
                    plan.execution_plan, title="Quality Gate Execution Plan"
                )
            )
            console.print("[bold]Plan insights:[/bold]")
            for line in plan_insights.render_lines():
                console.print(line)
            if monitoring is not None:
                console.print("")
                console.print("[bold]Monitoring insights:[/bold]")
                for line in monitoring.render_lines():
                    console.print(line)
            if dry_run_snapshot.actions:
                console.print("")
                console.print("[bold]Recommended actions:[/bold]")
                for action in dry_run_snapshot.actions:
                    console.print(f"• {action}")
        if dry_run:
            payload = dry_run_snapshot.to_payload()
            if json_output:
                typer.echo(json.dumps(payload, indent=2))
            raise typer.Exit(0)

    progress_callback: Callable[[QualitySuiteProgressEvent], None] | None = None
    if console is not None and plan.gates:
        console.print()
        console.rule("[bold]Quality Suite Progress[/bold]")
        progress_callback = _build_quality_suite_progress_renderer(
            console, len(plan.gates)
        )

    report = execute_quality_suite(
        plan,
        halt_on_failure=halt,
        monitoring=monitoring,
        progress=progress_callback,
    )

    payload = report.to_payload()
    if save_report is not None:
        save_report.parent.mkdir(parents=True, exist_ok=True)
        save_report.write_text(json.dumps(payload, indent=2))

    exit_code = 0 if report.succeeded else 1

    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        raise typer.Exit(exit_code)

    if console is not None:
        console.print()
        console.rule("[bold]Quality Suite Summary[/bold]")
        console.print(report.render_text_summary())
        if report.monitoring is not None:
            console.print("")
            console.print("[bold]Monitoring insights:[/bold]")
            for line in report.monitoring.render_lines():
                console.print(line)

    raise typer.Exit(exit_code)


@coverage_app.command("hotspots")
def coverage_hotspots_cli(
    xml: Path = typer.Option(
        Path("coverage.xml"), "--xml", help="Path to coverage XML"
    ),
    threshold: float = typer.Option(
        85.0, "--threshold", help="Coverage highlight threshold"
    ),
    limit: int = typer.Option(5, "--limit", min=1, help="Hotspot limit"),
) -> None:
    """Print coverage hotspots."""

    report = CoverageReport.from_xml(xml)
    typer.echo(coverage_hotspots(report, threshold=threshold, limit=limit))


@coverage_app.command("focus")
def coverage_focus_cli(
    xml: Path = typer.Option(Path("coverage.xml"), "--xml"),
    focus: Annotated[str, typer.Option("--focus")] = "service",
    threshold: float = typer.Option(85.0, "--threshold"),
    limit: int = typer.Option(3, "--limit", min=1),
    min_statements: int = typer.Option(50, "--min-statements", min=0),
) -> None:
    """Display coverage focus areas."""

    report = CoverageReport.from_xml(xml)
    typer.echo(
        coverage_focus(
            report,
            focus=focus,
            threshold=threshold,
            limit=limit,
            min_statements=min_statements,
        )
    )


@coverage_app.command("summary")
def coverage_summary_cli(
    xml: Path = typer.Option(Path("coverage.xml"), "--xml"),
) -> None:
    """Print coverage summary."""

    report = CoverageReport.from_xml(xml)
    typer.echo(report.render_summary())


@coverage_app.command("guard")
def coverage_guard_cli(
    xml: Path = typer.Option(
        Path("coverage.xml"), "--xml", help="Path to coverage XML"
    ),
    threshold: float = typer.Option(
        80.0, "--threshold", help="Minimum acceptable coverage"
    ),
    limit: int = typer.Option(5, "--limit", min=1, help="Hotspot limit"),
) -> None:
    """Fail if overall coverage drops below the specified threshold."""

    report = CoverageReport.from_xml(xml)
    passed, message = coverage_guard(report, threshold=threshold, limit=limit)
    typer.echo(message)
    if not passed:
        raise typer.Exit(1)


@coverage_app.command("gaps")
def coverage_gaps_cli(
    xml: Path = typer.Option(
        Path("coverage.xml"), "--xml", help="Path to coverage XML"
    ),
    min_statements: int = typer.Option(
        0,
        "--min-statements",
        help="Only include modules with at least this many statements",
    ),
    limit: int = typer.Option(5, "--limit", min=1, help="Number of modules to show"),
) -> None:
    """Highlight modules with the most missing lines."""

    report = CoverageReport.from_xml(xml)
    typer.echo(coverage_gap_summary(report, min_statements=min_statements, limit=limit))


@refactor_app.command("analyze")
def refactor_analyze(
    path: list[Path] = typer.Option(
        [],
        "--path",
        "-p",
        help="Files or directories to inspect (defaults to src/ and tests/)",
    ),
    coverage_xml: Path | None = typer.Option(
        None,
        "--coverage-xml",
        help="Optional coverage XML file to correlate with analysis",
    ),
    max_function_length: int = typer.Option(
        60,
        "--max-function-length",
        min=10,
        help="Maximum allowed function length before flagging",
    ),
    max_class_methods: int = typer.Option(
        12,
        "--max-class-methods",
        min=1,
        help="Maximum allowed class method count before flagging",
    ),
    max_cyclomatic_complexity: int = typer.Option(
        10,
        "--max-cyclomatic-complexity",
        min=1,
        help="Cyclomatic complexity threshold for functions",
    ),
    max_parameters: int = typer.Option(
        6,
        "--max-parameters",
        min=1,
        help="Maximum allowed number of parameters for a callable",
    ),
    min_docstring_length: int = typer.Option(
        20,
        "--min-docstring-length",
        min=1,
        help="Flag public callables without docstrings once they exceed this length",
    ),
    coverage_threshold: float = typer.Option(
        85.0,
        "--coverage-threshold",
        min=0.0,
        help="Coverage percentage gate for highlighting modules",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON report",
    ),
) -> None:
    """Run refactor opportunity analysis."""

    report = analyze_refactor_opportunities(
        tuple(path) or None,
        coverage_xml=coverage_xml,
        max_function_length=max_function_length,
        max_class_methods=max_class_methods,
        max_cyclomatic_complexity=max_cyclomatic_complexity,
        max_parameters=max_parameters,
        min_docstring_length=min_docstring_length,
        coverage_threshold=coverage_threshold,
    )

    if json_output:
        typer.echo(json.dumps(report.to_payload(), indent=2))
        return

    console = Console()
    if not report.opportunities:
        console.print("[green]No refactor opportunities detected.[/green]")
        return

    console.print()
    console.rule("[bold]Refactor Opportunities[/bold]")
    severity_styles = {
        "critical": "bold red",
        "warning": "yellow",
        "info": "cyan",
    }
    for opportunity in report.opportunities:
        style = severity_styles.get(opportunity.severity, "white")
        metric_hint = ""
        if opportunity.metric is not None and opportunity.threshold is not None:
            metric_hint = (
                f" (observed {opportunity.metric}, threshold {opportunity.threshold})"
            )
        symbol = f" · {opportunity.symbol}" if opportunity.symbol else ""
        console.print(
            f"[{style}]{opportunity.severity.upper()}[/] "
            f"{opportunity.path}:{opportunity.line}{symbol} — "
            f"{opportunity.message}{metric_hint}"
        )


@refactor_app.command("hotspots")
def refactor_hotspots(
    since: str = typer.Option(
        "12 months ago",
        "--since",
        help="Git log time specification for churn analysis",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        min=1,
        help="Number of top hotspots to display",
    ),
    min_complexity: int = typer.Option(
        10,
        "--min-complexity",
        min=0,
        help="Minimum complexity score threshold",
    ),
    min_churn: int = typer.Option(
        2,
        "--min-churn",
        min=1,
        help="Minimum number of changes threshold",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON report",
    ),
) -> None:
    """Identify code hotspots by combining churn and complexity."""

    report = analyze_hotspots(
        since=since,
        min_complexity=min_complexity,
        min_churn=min_churn,
    )

    if json_output:
        typer.echo(json.dumps(report.to_payload(), indent=2))
        return

    console = Console()
    if not report.entries:
        console.print("[green]No hotspots detected with current thresholds.[/green]")
        return

    console.print()
    console.rule("[bold]Code Hotspots (Complexity × Churn)[/bold]")
    console.print()
    console.print(
        f"Analyzed files changed since [cyan]{since}[/cyan] "
        f"with complexity ≥ {min_complexity} and churn ≥ {min_churn}"
    )
    console.print()

    for idx, entry in enumerate(report.entries[:limit], start=1):
        if entry.hotspot_score > 1000:
            style = "bold red"
        elif entry.hotspot_score > 500:
            style = "yellow"
        else:
            style = "cyan"

        console.print(
            f"[{style}]{idx:2d}.[/] {entry.path} "
            f"(complexity={entry.complexity_score}, "
            f"churn={entry.churn_count}, "
            f"[{style}]hotspot={entry.hotspot_score}[/])"
        )

    if len(report.entries) > limit:
        console.print()
        console.print(
            f"[dim]... and {len(report.entries) - limit} more. "
            f"Use --limit to see more.[/dim]"
        )


@refactor_app.command("codemod")
def refactor_codemod(
    old_name: str = typer.Option(
        ...,
        "--old-name",
        help="Current function/method name to rename",
    ),
    new_name: str = typer.Option(
        ...,
        "--new-name",
        help="New function/method name",
    ),
    path: list[Path] = typer.Option(
        [],
        "--path",
        "-p",
        help="Python files to transform",
    ),
    directory: Path | None = typer.Option(
        None,
        "--dir",
        help="Directory to scan for Python files (recursive)",
    ),
    include_tests: bool = typer.Option(
        False,
        "--include-tests",
        help="Include test files when scanning directory",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--apply",
        help="Dry run mode (default) or apply changes",
    ),
) -> None:
    """Run LibCST-based code transformations."""
    import subprocess
    import sys

    script_path = Path(
        "hephaestus-toolkit/refactoring/scripts/codemods/py/rename_function.py"
    )

    if not script_path.exists():
        typer.secho(
            f"Error: Codemod script not found: {script_path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    cmd: list[str] = [
        sys.executable,
        str(script_path),
        "--old-name",
        old_name,
        "--new-name",
        new_name,
    ]

    for file_path in path:
        cmd.append(str(file_path))

    if directory is not None:
        cmd.extend(["--dir", str(directory)])
    if include_tests:
        cmd.append("--include-tests")
    if not dry_run:
        cmd.append("--apply")

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise typer.Exit(exc.returncode) from exc


@refactor_app.command("verify")
def refactor_verify(
    path: Path = typer.Option(
        ..., "--path", "-p", help="File to generate characterization tests for"
    ),
    output: Path = typer.Option(
        Path("tests/snapshots"),
        "--output",
        help="Output directory for scaffolds",
    ),
    max_functions: int = typer.Option(
        10,
        "--max-functions",
        min=1,
        help="Maximum functions to generate tests for",
    ),
) -> None:
    """Generate pytest snapshot/characterization test scaffolds."""
    import subprocess
    import sys

    script_path = Path(
        "hephaestus-toolkit/refactoring/scripts/verify/snapshot_scaffold.py"
    )

    if not script_path.exists():
        typer.secho(
            f"Error: Verification script not found: {script_path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    cmd = [
        sys.executable,
        str(script_path),
        "--path",
        str(path),
        "--output",
        str(output),
        "--max-functions",
        str(max_functions),
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise typer.Exit(exc.returncode) from exc


@refactor_app.command("shard")
def refactor_shard(
    input_file: Path | None = typer.Option(
        None,
        "--input",
        help="File containing newline-separated paths",
    ),
    use_stdin: bool = typer.Option(
        False,
        "--stdin",
        help="Read changed files from stdin",
    ),
    shard_size: int = typer.Option(
        50,
        "--shard-size",
        min=1,
        help="Maximum files per PR shard",
    ),
    output_file: Path | None = typer.Option(
        None,
        "--output",
        help="Write shard plan to file",
    ),
    format_type: str = typer.Option(
        "markdown",
        "--format",
        "-f",
        help="Output format: markdown, text, or json",
    ),
) -> None:
    """Split large refactorings into manageable PR shards."""
    import subprocess
    import sys

    script_path = Path(
        "hephaestus-toolkit/refactoring/scripts/rollout/shard_pr_list.py"
    )

    if not script_path.exists():
        typer.secho(
            f"Error: Shard script not found: {script_path}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if not input_file and not use_stdin:
        typer.secho(
            "Error: Must specify --input or --stdin",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    cmd = [
        sys.executable,
        str(script_path),
        "--shard-size",
        str(shard_size),
        "--format",
        format_type,
    ]

    if use_stdin:
        cmd.append("--stdin")
    elif input_file:
        cmd.extend(["--input", str(input_file)])

    if output_file:
        cmd.extend(["--output", str(output_file)])

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise typer.Exit(exc.returncode) from exc


@docs_app.command("sync-diataxis")
def docs_sync_diataxis(
    config: Path = typer.Option(
        Path("docs/diataxis.json"),
        "--config",
        help="Path to Diataxis configuration JSON",
    ),
    target: Path = typer.Option(
        Path("docs/index.md"),
        "--target",
        help="Markdown file containing Diataxis markers",
    ),
    marker: str = typer.Option(
        "DIATAXIS_AUTODOC",
        "--marker",
        help="Documentation marker name to update",
    ),
    discover: bool = typer.Option(
        False,
        "--discover/--no-discover",
        help="Discover Diataxis entries from docs front matter before syncing",
    ),
    docs_dir: Path = typer.Option(
        Path("docs"),
        "--docs-dir",
        help="Docs directory to scan when using --discover",
    ),
    write_config: bool = typer.Option(
        True,
        "--write-config/--no-write-config",
        help="Persist discovered entries back to the Diataxis JSON map",
    ),
) -> None:
    """Synchronise the Diataxis documentation overview."""

    try:
        discovered_entries: dict[str, tuple[DiataxisEntry, ...]] | None = None
        if discover:
            discovered_entries = discover_diataxis_entries(docs_dir)
            if write_config:
                dump_diataxis_entries(config, discovered_entries)

        sync_diataxis_documentation(
            config,
            target,
            marker=marker,
            entries=discovered_entries,
        )
    except DocumentationSyncError as exc:
        typer.secho(f"❌ {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    if discover:
        total = sum(len(bucket) for bucket in (discovered_entries or {}).values())
        typer.echo(
            f"Discovered {total} Diataxis entries from {docs_dir} and updated {config}"
        )
    typer.echo(f"Updated {target} using {config}")


def main() -> None:
    """CLI entry point."""

    app()


if __name__ == "__main__":  # pragma: no cover
    main()
