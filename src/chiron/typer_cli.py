"""Chiron CLI — Unified interface for packaging, dependency, and developer tooling.

This is the main CLI entry point for the Chiron subsystem. It provides commands for:
- Offline packaging and deployment preparation
- Dependency management (guard, upgrade, drift, sync, preflight)
- Remediation of packaging and runtime failures
- Orchestration of complex workflows
- Diagnostics and health checks
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Annotated, Literal, cast

from typer import Context

try:
    import typer
except ImportError as exc:
    raise RuntimeError("Typer must be installed to use the Chiron CLI") from exc

from chiron.dev_toolbox import (
    CoverageReport,
    available_quality_gates,
    available_quality_profiles,
    coverage_focus,
    coverage_gap_summary,
    coverage_guard,
    coverage_hotspots,
    load_quality_configuration,
    resolve_quality_profile,
    run_quality_suite,
    summarise_suite,
)
from chiron.github import (
    COPILOT_DISABLE_ENV_VAR,
    CopilotProvisioningError,
    collect_status,
    format_status_json,
    generate_env_exports,
    prepare_environment,
)

logger = logging.getLogger(__name__)

VERBOSE_HELP = "Verbose output"
DRY_RUN_HELP = "Dry run mode"

_NO_ARGS = object()


class CliInvocationError(RuntimeError):
    """Raised when a delegated CLI command cannot provide a valid exit code."""


def _normalise_exit_code(result: object, *, command_name: str) -> int:
    """Translate heterogeneous return values into an integer exit status."""

    if isinstance(result, bool):
        return 0 if result else 1
    if isinstance(result, int):
        return result
    if result is None:
        return 0

    raise CliInvocationError(
        f"Command '{command_name}' returned unsupported result type "
        f"{type(result).__name__}."
    )


def _invoke_cli_callable(
    command_name: str,
    callback: Callable[..., object],
    *,
    args: Sequence[str] | None | object = _NO_ARGS,
) -> None:
    """Execute a delegated CLI callable with consistent error handling."""

    try:
        if args is _NO_ARGS:
            result = callback()
        else:
            result = callback(args)
    except typer.Exit:  # pragma: no cover - Typer manages propagation
        raise
    except SystemExit as exc:  # pragma: no cover - defensive guard
        raise typer.Exit(int(exc.code or 0))
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Error executing %s", command_name)
        typer.secho(
            f"❌ Unexpected error while executing {command_name}: {exc}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1) from exc

    try:
        exit_code = _normalise_exit_code(result, command_name=command_name)
    except CliInvocationError as exc:
        typer.secho(f"❌ {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    if exit_code != 0:
        typer.secho(
            f"Command '{command_name}' failed with exit code {exit_code}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(exit_code)


def _invoke_script_command(
    ctx: Context,
    *,
    command_name: str,
    callback: Callable[[list[str] | None], object],
    allow_empty_argv: bool = True,
) -> None:
    """Run a script-style command, forwarding any extra CLI arguments."""

    argv = list(ctx.args)
    forwarded: list[str] | None
    if allow_empty_argv:
        forwarded = argv or None
    else:
        forwarded = argv

    _invoke_cli_callable(command_name, callback, args=forwarded)

# ============================================================================
# Main Chiron CLI
# ============================================================================

VALIDATE_OPTION = "--validate/--no-validate"

app = typer.Typer(
    add_completion=False,
    help="Chiron — Packaging, dependency management, and developer tooling subsystem",
)

# ============================================================================
# Sub-applications
# ============================================================================

deps_app = typer.Typer(help="Dependency management commands")
app.add_typer(deps_app, name="deps")

packaging_app = typer.Typer(help="Offline packaging commands")
app.add_typer(packaging_app, name="package")

remediation_app = typer.Typer(help="Remediation commands")
app.add_typer(remediation_app, name="remediate")

orchestrate_app = typer.Typer(help="Orchestration workflows")
app.add_typer(orchestrate_app, name="orchestrate")

doctor_app = typer.Typer(help="Diagnostics and health checks")
app.add_typer(doctor_app, name="doctor")

tools_app = typer.Typer(help="Developer tools and utilities")
app.add_typer(tools_app, name="tools")

coverage_app = typer.Typer(help="Test coverage analytics")
tools_app.add_typer(coverage_app, name="coverage")

github_app = typer.Typer(help="GitHub Actions integration and artifact sync")
app.add_typer(github_app, name="github")

copilot_app = typer.Typer(help="GitHub Copilot coding agent helpers")
github_app.add_typer(copilot_app, name="copilot")

_SCRIPT_PROXY_CONTEXT = {
    "allow_extra_args": True,
    "ignore_unknown_options": True,
}


# ============================================================================
# Version Command
# ============================================================================


@app.command()
def version() -> None:
    """Display Chiron version."""
    from chiron import __version__

    typer.echo(f"Chiron version {__version__}")


# ============================================================================
# Packaging Commands
# ============================================================================


@packaging_app.command(
    "offline",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def package_offline(ctx: Context) -> None:
    """Execute offline packaging workflow.

    Build complete offline deployment artifacts including dependencies,
    models, and containers. Use 'chiron doctor offline' to verify readiness.
    """
    from chiron.doctor import package_cli

    _invoke_script_command(
        ctx,
        command_name="chiron package offline",
        callback=package_cli.main,
    )


# ============================================================================
# Doctor Commands
# ============================================================================


@doctor_app.command(
    "offline",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def doctor_offline(ctx: Context) -> None:
    """Diagnose offline packaging readiness.

    Validates tool availability, wheelhouse health, and configuration
    without mutating the repository.
    """
    from chiron.doctor import offline as doctor_module

    _invoke_script_command(
        ctx,
        command_name="chiron doctor offline",
        callback=doctor_module.main,
    )


@doctor_app.command(
    "bootstrap",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def doctor_bootstrap(ctx: Context) -> None:
    """Bootstrap offline environment from wheelhouse.

    Install dependencies from the offline wheelhouse, useful for
    air-gapped or restricted network environments.
    """
    from chiron.doctor import bootstrap

    _invoke_script_command(
        ctx,
        command_name="chiron doctor bootstrap",
        callback=bootstrap.main,
        allow_empty_argv=False,
    )


@doctor_app.command(
    "models",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def doctor_models(ctx: Context) -> None:
    """Download model artifacts for offline use.

    Pre-populate caches for Sentence-Transformers, Hugging Face,
    and spaCy models for air-gapped deployment.
    """
    from chiron.doctor import models

    _invoke_script_command(
        ctx,
        command_name="chiron doctor models",
        callback=models.main,
        allow_empty_argv=False,
    )


# ============================================================================
# Dependency Commands
# ============================================================================


@deps_app.command("status")
def deps_status(
    contract: Path = typer.Option(
        Path("configs/dependencies/contract.toml"),
        "--contract",
        help="Path to dependency contract file",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
    preflight: Path | None = typer.Option(
        None,
        "--preflight",
        help="Optional path to dependency preflight summary JSON file",
    ),
    renovate: Path | None = typer.Option(
        None,
        "--renovate",
        help="Optional path to Renovate insights JSON file",
    ),
    cve: Path | None = typer.Option(
        None,
        "--cve",
        help="Optional path to CVE advisories JSON file",
    ),
    sbom: Path | None = typer.Option(
        None,
        "--sbom",
        help="Optional path to SBOM document",
    ),
    metadata: Path | None = typer.Option(
        None,
        "--metadata",
        help="Optional path to additional metadata JSON file",
    ),
    sbom_max_age_days: int | None = typer.Option(
        None,
        "--sbom-max-age-days",
        help="Maximum allowed SBOM age in days before revalidation",
    ),
    fail_threshold: str = typer.Option(
        "needs-review",
        "--fail-threshold",
        case_sensitive=False,
        help="Fail when guard severity meets or exceeds this threshold",
    ),
) -> None:
    """Show dependency status and health."""
    from chiron.deps.guard import FAIL_THRESHOLD_CHOICES
    from chiron.deps.status import generate_status

    try:
        normalized_threshold = fail_threshold.lower()
        if normalized_threshold not in FAIL_THRESHOLD_CHOICES:
            raise typer.BadParameter(
                f"Invalid fail threshold '{fail_threshold}'. "
                f"Expected one of: {', '.join(sorted(FAIL_THRESHOLD_CHOICES))}."
            )

        status = generate_status(
            preflight=preflight,
            renovate=renovate,
            cve=cve,
            contract=contract,
            sbom=sbom,
            metadata=metadata,
            sbom_max_age_days=sbom_max_age_days,
            fail_threshold=normalized_threshold,
            planner_settings=None,
        )

        if json_output:
            typer.echo(json.dumps(status.to_dict(), indent=2))
        else:
            typer.echo("=== Dependency Status ===")
            typer.echo(f"Contract: {contract}")
            typer.echo(f"Generated: {status.generated_at.isoformat()}")
            typer.echo(f"Overall exit code: {status.exit_code}")
            typer.echo(f"Guard exit code: {status.guard.exit_code}")
            summary = status.summary
            if summary:
                typer.echo("Summary:")
                for key, value in summary.items():
                    typer.echo(f"  - {key}: {value}")
    except Exception as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@deps_app.command(
    "guard",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def deps_guard(ctx: Context) -> None:
    """Run dependency guard checks."""
    from chiron.deps import guard

    _invoke_script_command(
        ctx,
        command_name="chiron deps guard",
        callback=guard.main,
    )


@deps_app.command(
    "upgrade",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def deps_upgrade(ctx: Context) -> None:
    """Plan dependency upgrades."""
    from chiron.deps import planner

    _invoke_script_command(
        ctx,
        command_name="chiron deps upgrade",
        callback=planner.main,
    )


@deps_app.command(
    "drift",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def deps_drift(ctx: Context) -> None:
    """Detect dependency drift."""
    from chiron.deps import drift

    _invoke_script_command(
        ctx,
        command_name="chiron deps drift",
        callback=drift.main,
    )


@deps_app.command(
    "sync",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def deps_sync(ctx: Context) -> None:
    """Synchronize manifests from contract."""
    from chiron.deps import sync

    _invoke_script_command(
        ctx,
        command_name="chiron deps sync",
        callback=sync.main,
    )


@deps_app.command(
    "preflight",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def deps_preflight(ctx: Context) -> None:
    """Run dependency preflight checks."""
    from chiron.deps import preflight

    _invoke_script_command(
        ctx,
        command_name="chiron deps preflight",
        callback=preflight.main,
    )


@deps_app.command(
    "graph",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def deps_graph(ctx: Context) -> None:
    """Generate dependency graph visualization.

    Analyzes Python imports across the codebase and generates
    a dependency graph showing relationships between modules.
    """
    from chiron.deps import graph

    _invoke_cli_callable("chiron deps graph", graph.main)


@deps_app.command(
    "verify",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def deps_verify(ctx: Context) -> None:
    """Verify dependency pipeline setup and integration.

    Checks that all components of the dependency management pipeline
    are properly wired, scripts are importable, and CLI commands work.
    """
    from chiron.deps import verify

    _invoke_cli_callable("chiron deps verify", verify.main)


@deps_app.command("constraints")
def deps_constraints(
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output path for constraints file"),
    ] = Path("constraints.txt"),
    tool: Annotated[
        str,
        typer.Option("--tool", help="Tool to use: uv or pip-tools"),
    ] = "uv",
    extras: Annotated[
        str | None,
        typer.Option("--extras", help="Comma-separated extras to include"),
    ] = None,
) -> None:
    """Generate hash-pinned constraints for reproducible builds.

    Uses uv or pip-tools to generate --require-hashes constraints from
    pyproject.toml. This ensures deterministic, verifiable installations.

    Example:
        chiron deps constraints --output constraints.txt --extras pii,rag
    """
    from chiron.deps.constraints import generate_constraints

    extras_list = (
        [item.strip() for item in extras.split(",") if item.strip()] if extras else None
    )

    tool_normalized = tool.strip().lower()
    if tool_normalized not in {"uv", "pip-tools"}:
        typer.echo(
            "❌ Unsupported constraints tool. Choose 'uv' or 'pip-tools'",
            err=True,
        )
        raise typer.Exit(1)

    tool_literal = cast(Literal["uv", "pip-tools"], tool_normalized)

    success = generate_constraints(
        project_root=Path.cwd(),
        output_path=output,
        tool=tool_literal,
        include_extras=extras_list,
    )

    if not success:
        typer.echo("❌ Failed to generate constraints", err=True)
        raise typer.Exit(1)

    typer.echo(f"✅ Generated hash-pinned constraints: {output}")


@deps_app.command("scan")
def deps_scan(
    lockfile: Annotated[
        Path,
        typer.Option(
            "--lockfile", "-l", help="Lockfile to scan (requirements.txt, etc.)"
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output path for scan report"),
    ] = None,
    gate: Annotated[
        bool,
        typer.Option("--gate", help="Exit with error if vulnerabilities found"),
    ] = False,
    max_severity: Annotated[
        str,
        typer.Option(
            "--max-severity",
            help="Maximum severity to allow (critical, high, medium, low)",
        ),
    ] = "high",
) -> None:
    """Scan dependencies for vulnerabilities using OSV.

    Scans the specified lockfile for known vulnerabilities and reports
    findings. Can be used as a CI gate to block on critical/high vulnerabilities.

    Example:
        chiron deps scan --lockfile requirements.txt --gate --max-severity high
    """
    from chiron.deps.supply_chain import OSVScanner

    scanner = OSVScanner(Path.cwd())
    summary = scanner.scan_lockfile(lockfile, output)

    if summary is None:
        typer.echo("❌ Scan failed", err=True)
        raise typer.Exit(1)

    typer.echo("\n📊 Vulnerability Summary:")
    typer.echo(f"   Total: {summary.total_vulnerabilities}")
    typer.echo(f"   Critical: {summary.critical}")
    typer.echo(f"   High: {summary.high}")
    typer.echo(f"   Medium: {summary.medium}")
    typer.echo(f"   Low: {summary.low}")

    if summary.packages_affected:
        typer.echo(
            f"\n📦 Affected packages: {', '.join(summary.packages_affected[:5])}"
        )
        if len(summary.packages_affected) > 5:
            typer.echo(f"   ... and {len(summary.packages_affected) - 5} more")

    if gate and summary.has_blocking_vulnerabilities(max_severity):
        typer.echo(
            f"\n❌ Security gate failed: Found blocking vulnerabilities (max: {max_severity})",
            err=True,
        )
        raise typer.Exit(1)

    typer.echo("\n✅ Scan complete")


@deps_app.command("bundle")
def deps_bundle(
    wheelhouse: Annotated[
        Path,
        typer.Option("--wheelhouse", "-w", help="Wheelhouse directory to bundle"),
    ] = Path("vendor/wheelhouse"),
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output path for bundle"),
    ] = Path("wheelhouse-bundle.tar.gz"),
    sign: Annotated[
        bool,
        typer.Option("--sign", help="Sign bundle with cosign"),
    ] = False,
) -> None:
    """Create portable wheelhouse bundle for air-gapped deployment.

    Creates a tar.gz bundle with wheels, checksums, simple index, and
    metadata for offline installation. Optionally signs with cosign.

    Example:
        chiron deps bundle --wheelhouse vendor/wheelhouse --sign
    """
    from chiron.deps.bundler import create_wheelhouse_bundle
    from chiron.deps.signing import sign_wheelhouse_bundle

    typer.echo("📦 Creating wheelhouse bundle...")

    try:
        metadata = create_wheelhouse_bundle(
            wheelhouse_dir=wheelhouse,
            output_path=output,
        )

        typer.echo(f"✅ Bundle created: {output}")
        typer.echo(f"   Wheels: {metadata.wheel_count}")
        typer.echo(f"   Size: {metadata.total_size_bytes:,} bytes")

        if sign:
            typer.echo("\n🔐 Signing bundle with cosign...")
            result = sign_wheelhouse_bundle(output)

            if result.success:
                typer.echo(f"✅ Signed: {result.signature_path}")
            else:
                typer.echo(f"❌ Signing failed: {result.error_message}", err=True)
                raise typer.Exit(1)

    except Exception as e:
        typer.echo(f"❌ Bundle creation failed: {e}", err=True)
        raise typer.Exit(1)


@deps_app.command("policy")
def deps_policy(
    config: Annotated[
        Path,
        typer.Option("--config", "-c", help="Policy configuration file"),
    ] = Path("configs/dependency-policy.toml"),
    package: Annotated[
        str | None,
        typer.Option("--package", "-p", help="Check specific package"),
    ] = None,
    version: Annotated[
        str | None,
        typer.Option("--version", "-v", help="Check specific version"),
    ] = None,
    upgrade_from: Annotated[
        str | None,
        typer.Option("--upgrade-from", help="Check upgrade from version"),
    ] = None,
) -> None:
    """Check dependency policy compliance.

    Evaluates packages and upgrades against the defined policy rules
    including allowlists, denylists, version ceilings, and cadences.

    Example:
        chiron deps policy --package numpy --version 2.0.0
        chiron deps policy --package torch --upgrade-from 2.3.0 --version 2.4.0
    """
    from chiron.deps.policy import PolicyEngine, load_policy

    STATUS_ALLOWED = "   Status: ✅ Allowed"

    try:
        policy = load_policy(config)
        engine = PolicyEngine(policy)

        if package:
            allowed, reason = engine.check_package_allowed(package)

            typer.echo(f"\n📋 Package: {package}")
            if allowed:
                typer.echo(STATUS_ALLOWED)
            else:
                typer.echo("   Status: ❌ Denied")
                typer.echo(f"   Reason: {reason}")

            if version:
                allowed, reason = engine.check_version_allowed(package, version)
                typer.echo(f"\n📌 Version: {version}")
                if allowed:
                    typer.echo(STATUS_ALLOWED)
                else:
                    typer.echo("   Status: ❌ Denied")
                    typer.echo(f"   Reason: {reason}")

            if upgrade_from and version:
                violations = engine.check_upgrade_allowed(
                    package, upgrade_from, version
                )
                typer.echo(f"\n⬆️  Upgrade: {upgrade_from} → {version}")

                if not violations:
                    typer.echo(STATUS_ALLOWED)
                else:
                    typer.echo(f"   Status: ⚠️  {len(violations)} violation(s)")
                    for v in violations:
                        icon = (
                            "❌"
                            if v.severity == "error"
                            else "⚠️" if v.severity == "warning" else "ℹ️"
                        )
                        typer.echo(f"   {icon} {v.violation_type}: {v.message}")
        else:
            typer.echo("📋 Policy Configuration:")
            typer.echo(f"   Default allowed: {policy.default_allowed}")
            typer.echo(f"   Max major jump: {policy.max_major_version_jump}")
            typer.echo(f"   Allowlist packages: {len(policy.allowlist)}")
            typer.echo(f"   Denylist packages: {len(policy.denylist)}")

    except Exception as e:
        typer.echo(f"❌ Policy check failed: {e}", err=True)
        raise typer.Exit(1)


@deps_app.command("mirror")
def deps_mirror(
    action: Annotated[
        str,
        typer.Argument(help="Action: setup, upload, config"),
    ],
    wheelhouse: Annotated[
        Path,
        typer.Option("--wheelhouse", "-w", help="Wheelhouse directory"),
    ] = Path("vendor/wheelhouse"),
    mirror_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Mirror type: devpi, simple-http"),
    ] = "devpi",
    host: Annotated[
        str,
        typer.Option("--host", help="Mirror host"),
    ] = "localhost",
    port: Annotated[
        int,
        typer.Option("--port", help="Mirror port"),
    ] = 3141,
) -> None:
    """Setup and manage private PyPI mirror.

    Automates setup of devpi or simple HTTP mirror for air-gapped
    deployments. Can setup, upload wheelhouse, and generate client config.

    Example:
        chiron deps mirror setup --type devpi
        chiron deps mirror upload --wheelhouse vendor/wheelhouse
    """
    from chiron.deps.private_mirror import (
        MirrorConfig,
        MirrorType,
        setup_private_mirror,
    )

    config = MirrorConfig(
        mirror_type=MirrorType(mirror_type),
        host=host,
        port=port,
    )

    if action == "setup":
        typer.echo(f"🔧 Setting up {mirror_type} mirror...")
        success = setup_private_mirror(MirrorType(mirror_type), wheelhouse, config)

        if success:
            typer.echo("✅ Mirror setup complete")
            typer.echo(f"   Server: http://{host}:{port}")
        else:
            typer.echo("❌ Mirror setup failed", err=True)
            raise typer.Exit(1)

    elif action == "config":
        from chiron.deps.private_mirror import DevpiMirrorManager

        manager = DevpiMirrorManager(config)
        pip_conf = manager.generate_pip_conf()
        typer.echo(f"✅ Generated pip configuration: {pip_conf}")

    else:
        typer.echo(f"❌ Unknown action: {action}", err=True)
        raise typer.Exit(1)


@deps_app.command("oci")
def deps_oci(
    action: Annotated[
        str,
        typer.Argument(help="Action: package, push, pull"),
    ],
    bundle: Annotated[
        Path | None,
        typer.Option("--bundle", "-b", help="Path to wheelhouse bundle"),
    ] = None,
    repository: Annotated[
        str | None,
        typer.Option("--repository", "-r", help="Repository name (org/wheelhouse)"),
    ] = None,
    tag: Annotated[
        str,
        typer.Option("--tag", "-t", help="Tag for artifact"),
    ] = "latest",
    registry: Annotated[
        str,
        typer.Option("--registry", help="OCI registry URL"),
    ] = "ghcr.io",
    sbom: Annotated[
        Path | None,
        typer.Option("--sbom", help="Path to SBOM file"),
    ] = None,
    osv: Annotated[
        Path | None,
        typer.Option("--osv", help="Path to OSV scan results"),
    ] = None,
) -> None:
    """Package and manage wheelhouse as OCI artifacts.

    Packages wheelhouse bundles as OCI artifacts that can be pushed to
    container registries like GHCR, DockerHub, or Artifactory.

    Example:
        chiron deps oci package --bundle wheelhouse-bundle.tar.gz --repository org/wheelhouse
        chiron deps oci push --bundle wheelhouse-bundle.tar.gz --repository org/wheelhouse --tag v1.0.0
    """
    from chiron.deps.oci_packaging import OCIPackager, package_wheelhouse_as_oci

    if action == "package":
        if not bundle or not repository:
            typer.echo(
                "❌ --bundle and --repository required for package action", err=True
            )
            raise typer.Exit(1)

        typer.echo(f"📦 Packaging {bundle} as OCI artifact...")

        metadata = package_wheelhouse_as_oci(
            wheelhouse_bundle=bundle,
            repository=repository,
            tag=tag,
            registry=registry,
            sbom_path=sbom,
            osv_path=osv,
            push=False,
        )

        typer.echo("✅ OCI artifact created")
        typer.echo(f"   Repository: {metadata.registry}/{metadata.name}")
        typer.echo(f"   Tag: {metadata.tag}")

    elif action == "push":
        if not bundle or not repository:
            typer.echo(
                "❌ --bundle and --repository required for push action", err=True
            )
            raise typer.Exit(1)

        typer.echo(f"📤 Pushing to {registry}/{repository}:{tag}...")

        metadata = package_wheelhouse_as_oci(
            wheelhouse_bundle=bundle,
            repository=repository,
            tag=tag,
            registry=registry,
            sbom_path=sbom,
            osv_path=osv,
            push=True,
        )

        typer.echo("✅ Pushed successfully")
        if metadata.digest:
            typer.echo(f"   Digest: {metadata.digest}")

    elif action == "pull":
        if not repository:
            typer.echo("❌ --repository required for pull action", err=True)
            raise typer.Exit(1)

        typer.echo(f"📥 Pulling from {registry}/{repository}:{tag}...")

        packager = OCIPackager(registry)
        output_dir = packager.pull_from_registry(repository, tag)

        typer.echo(f"✅ Pulled to {output_dir}")

    else:
        typer.echo(f"❌ Unknown action: {action}", err=True)
        raise typer.Exit(1)


@deps_app.command("reproducibility")
def deps_reproducibility(
    action: Annotated[
        str,
        typer.Argument(help="Action: compute, verify, compare"),
    ],
    wheelhouse: Annotated[
        Path | None,
        typer.Option("--wheelhouse", "-w", help="Wheelhouse directory"),
    ] = None,
    digests: Annotated[
        Path,
        typer.Option("--digests", "-d", help="Digests file"),
    ] = Path("wheel-digests.json"),
    original: Annotated[
        Path | None,
        typer.Option("--original", help="Original wheel (for compare)"),
    ] = None,
    rebuilt: Annotated[
        Path | None,
        typer.Option("--rebuilt", help="Rebuilt wheel (for compare)"),
    ] = None,
) -> None:
    """Check binary reproducibility of wheels.

    Verifies that wheels can be rebuilt reproducibly by comparing
    digests and analyzing differences.

    Example:
        chiron deps reproducibility compute --wheelhouse vendor/wheelhouse
        chiron deps reproducibility verify --wheelhouse vendor/wheelhouse --digests wheel-digests.json
        chiron deps reproducibility compare --original old.whl --rebuilt new.whl
    """
    from chiron.deps.reproducibility import ReproducibilityChecker

    checker = ReproducibilityChecker()

    if action == "compute":
        if not wheelhouse:
            typer.echo("❌ --wheelhouse required for compute action", err=True)
            raise typer.Exit(1)

        typer.echo("🔍 Computing wheel digests...")
        checker.save_digests(wheelhouse, digests)
        typer.echo(f"✅ Saved digests to {digests}")

    elif action == "verify":
        if not wheelhouse:
            typer.echo("❌ --wheelhouse required for verify action", err=True)
            raise typer.Exit(1)

        typer.echo(f"🔍 Verifying wheels against {digests}...")
        reports = checker.verify_against_digests(wheelhouse, digests)

        failures = [r for r in reports.values() if not r.is_reproducible]
        if failures:
            typer.echo(
                f"\n❌ {len(failures)} wheels failed reproducibility check", err=True
            )
            raise typer.Exit(1)
        else:
            typer.echo(f"\n✅ All {len(reports)} wheels verified successfully")

    elif action == "compare":
        if not original or not rebuilt:
            typer.echo(
                "❌ --original and --rebuilt required for compare action", err=True
            )
            raise typer.Exit(1)

        typer.echo("🔍 Comparing wheels...")
        report = checker.compare_wheels(original, rebuilt)

        typer.echo(f"\nWheel: {report.wheel_name}")
        typer.echo(f"Reproducible: {'✅' if report.is_reproducible else '❌'}")
        typer.echo(f"Size match: {'✅' if report.size_match else '❌'}")

        if report.differences:
            typer.echo("\nDifferences:")
            for diff in report.differences:
                typer.echo(f"  - {diff}")

        if not report.is_reproducible:
            raise typer.Exit(1)

    else:
        typer.echo(f"❌ Unknown action: {action}", err=True)
        raise typer.Exit(1)


@deps_app.command("security")
def deps_security(
    action: Annotated[
        str,
        typer.Argument(help="Action: import-osv, generate, check"),
    ],
    overlay: Annotated[
        Path,
        typer.Option("--overlay", help="Security overlay file"),
    ] = Path("security-constraints.json"),
    osv_file: Annotated[
        Path | None,
        typer.Option("--osv-file", help="OSV scan results (for import-osv)"),
    ] = None,
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output constraints file (for generate)"),
    ] = Path("security-constraints.txt"),
    package: Annotated[
        str | None,
        typer.Option("--package", "-p", help="Package name (for check)"),
    ] = None,
    version: Annotated[
        str | None,
        typer.Option("--version", "-v", help="Version (for check)"),
    ] = None,
) -> None:
    """Manage security constraints overlay for CVE backports.

    Tracks CVEs and generates constraint overlays that pin safe versions
    without jumping major versions.

    Example:
        chiron deps security import-osv --osv-file osv-scan.json
        chiron deps security generate --output security-constraints.txt
        chiron deps security check --package requests --version 2.28.0
    """
    from chiron.deps.security_overlay import SecurityOverlayManager

    manager = SecurityOverlayManager(overlay_file=overlay)

    if action == "import-osv":
        if not osv_file:
            typer.echo("❌ --osv-file required for import-osv action", err=True)
            raise typer.Exit(1)

        typer.echo(f"📥 Importing CVEs from {osv_file}...")
        count = manager.import_osv_scan(osv_file)
        typer.echo(f"✅ Imported {count} CVEs")

    elif action == "generate":
        typer.echo("📝 Generating constraints file...")
        manager.generate_constraints_file(output)
        typer.echo(f"✅ Generated {output}")

    elif action == "check":
        if not package or not version:
            typer.echo("❌ --package and --version required for check action", err=True)
            raise typer.Exit(1)

        is_safe, violations = manager.check_package_version(package, version)

        typer.echo(f"\nPackage: {package}=={version}")
        if is_safe:
            typer.echo("✅ Safe - meets security constraints")
        else:
            typer.echo("❌ Violations found:")
            for violation in violations:
                typer.echo(f"  - {violation}")

            typer.echo("\nRecommendations:")
            for rec in manager.get_recommendations(package):
                typer.echo(f"  • {rec}")

            raise typer.Exit(1)

    else:
        typer.echo(f"❌ Unknown action: {action}", err=True)
        raise typer.Exit(1)


# ============================================================================
# Tools Commands
# ============================================================================


@tools_app.command("qa")
def tools_quality_suite(
    ctx: typer.Context,
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
        help="Run mypy type checking",
        show_default=False,
    ),
    security: bool | None = typer.Option(
        None,
        "--security/--no-security",
        help="Run Bandit security scan",
        show_default=False,
    ),
    build: bool | None = typer.Option(
        None,
        "--build/--no-build",
        help="Build wheel and sdist",
        show_default=False,
    ),
    halt: bool = typer.Option(True, "--halt/--keep-going", help="Stop on first failure"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON results"),
    save_report: Path | None = typer.Option(
        None,
        "--save-report",
        help="Write JSON results to the provided path",
    ),
) -> None:
    """Run the curated quality gate command suite."""

    config = load_quality_configuration()
    profiles = available_quality_profiles(config)

    if list_profiles:
        lines = ["Available quality profiles:"]
        for name, gate_names in sorted(profiles.items()):
            rendered = ", ".join(gate_names) if gate_names else "(none)"
            lines.append(f"  • {name}: {rendered}")
        typer.echo("\n".join(lines))
        raise typer.Exit(0)

    try:
        planned_gates = resolve_quality_profile(profile, config=config)
    except KeyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    catalog = available_quality_gates(config)

    def _apply_toggle(category: str, enabled: bool | None) -> None:
        nonlocal planned_gates
        if enabled is None:
            return
        if enabled:
            if any(gate.category == category for gate in planned_gates):
                return
            for gate in planned_gates:
                if gate.name == category:
                    return
            candidate = next(
                (gate for gate in catalog.values() if gate.category == category),
                None,
            )
            if candidate:
                planned_gates.append(candidate)
        else:
            planned_gates = [gate for gate in planned_gates if gate.category != category]

    _apply_toggle("tests", tests)
    _apply_toggle("lint", lint)
    _apply_toggle("types", types)
    _apply_toggle("security", security)
    _apply_toggle("build", build)

    if not planned_gates:
        typer.echo("No quality gates selected.")
        raise typer.Exit(code=0)

    if explain or dry_run:
        lines = ["Resolved quality gates:"]
        for gate in planned_gates:
            rendered = " ".join(gate.command)
            lines.append(f"  • {gate.name}: {rendered}")
        typer.echo("\n".join(lines))
        if dry_run:
            raise typer.Exit(0)

    results = run_quality_suite(planned_gates, halt_on_failure=halt)
    payload = [result.to_payload() for result in results]

    if json_output:
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(summarise_suite(results))

    if save_report is not None:
        save_report.parent.mkdir(parents=True, exist_ok=True)
        save_report.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if any(result.returncode != 0 for result in results):
        raise typer.Exit(1)


@coverage_app.command("hotspots")
def coverage_hotspots_cli(
    xml: Path = typer.Option(Path("coverage.xml"), "--xml", help="Path to coverage XML"),
    threshold: float = typer.Option(90.0, "--threshold", help="Coverage threshold"),
    limit: int = typer.Option(10, "--limit", min=1, help="Number of modules to show"),
) -> None:
    """List modules falling below the specified coverage threshold."""

    report = CoverageReport.from_xml(xml)
    typer.echo(coverage_hotspots(report, threshold=threshold, limit=limit))


@coverage_app.command("focus")
def coverage_focus_cli(
    module: str = typer.Argument(..., help="Module path as listed in coverage.xml"),
    xml: Path = typer.Option(Path("coverage.xml"), "--xml", help="Path to coverage XML"),
    lines: int | None = typer.Option(
        None, "--lines", min=1, help="Limit of missing lines to display"
    ),
) -> None:
    """Show missing lines for a specific module."""

    report = CoverageReport.from_xml(xml)
    typer.echo(coverage_focus(report, module, line_limit=lines))


@coverage_app.command("summary")
def coverage_summary_cli(
    xml: Path = typer.Option(Path("coverage.xml"), "--xml", help="Path to coverage XML"),
    limit: int = typer.Option(5, "--limit", min=1, help="Number of entries to include"),
) -> None:
    """Display the best and worst performing modules from coverage."""

    report = CoverageReport.from_xml(xml)
    best = report.best(limit=limit)
    worst = report.worst(limit=limit)
    lines = ["🔥 Coverage hotspots:"]
    if worst:
        lines.extend(
            f"  • {module.name} — {module.coverage:.2f}% (missing {module.missing})"
            for module in worst
        )
    else:
        lines.append("  • None! 🎉")

    lines.append(f"\n📊 Overall coverage: {report.summary.coverage:.2f}% ({report.summary.covered}/{report.summary.total_statements})")
    lines.append("\n🌟 Top performers:")
    if best:
        lines.extend(
            f"  • {module.name} — {module.coverage:.2f}%" for module in best
        )
    else:
        lines.append("  • No modules found")

    typer.echo("\n".join(lines))


@coverage_app.command("guard")
def coverage_guard_cli(
    xml: Path = typer.Option(Path("coverage.xml"), "--xml", help="Path to coverage XML"),
    threshold: float = typer.Option(80.0, "--threshold", help="Minimum acceptable coverage"),
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
    xml: Path = typer.Option(Path("coverage.xml"), "--xml", help="Path to coverage XML"),
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


@tools_app.command(
    "format-yaml",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def tools_format_yaml(ctx: Context) -> None:
    """Format YAML files consistently across the repository.

    Runs yamlfmt with additional conveniences like removing macOS
    resource fork files and Git-aware discovery.
    """
    from chiron.tools import format_yaml

    _invoke_cli_callable("chiron tools format-yaml", format_yaml.main)


@tools_app.command("benchmark")
def tools_benchmark(
    iterations: int = typer.Option(50, "--iterations", "-n", help="Iterations per case"),
    warmup: int = typer.Option(5, "--warmup", help="Warmup executions per case"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON summary"),
) -> None:
    """Run the built-in performance benchmarking suite."""

    from chiron import benchmark

    suite = benchmark.default_suite()
    for case in suite.cases():
        case.iterations = iterations
        case.warmup = warmup

    summary = suite.summary()

    if json_output:
        typer.echo(json.dumps(summary, indent=2))
        return

    typer.echo("🏎️  Chiron benchmark results")
    for result in summary["results"]:
        typer.echo(
            "  • {name}: {avg:.3f} ms avg ({throughput:.1f}/s)".format(
                name=result["name"],
                avg=result["avg_time"] * 1000,
                throughput=result["throughput"],
            )
        )

    total = summary["aggregate"]["total_time"]
    case_count = summary["aggregate"]["cases"]
    typer.echo(f"Total elapsed: {total:.3f}s across {case_count} cases")


# ============================================================================
# Remediation Commands
# ============================================================================


@remediation_app.command(
    "wheelhouse",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def remediate_wheelhouse(ctx: Context) -> None:
    """Remediate wheelhouse issues."""
    from chiron import remediation

    args = ["wheelhouse", *ctx.args]
    _invoke_cli_callable(
        "chiron remediate wheelhouse",
        remediation.main,
        args=args,
    )


@remediation_app.command(
    "runtime",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def remediate_runtime(ctx: Context) -> None:
    """Remediate runtime issues."""
    from chiron import remediation

    args = ["runtime", *ctx.args]
    _invoke_cli_callable(
        "chiron remediate runtime",
        remediation.main,
        args=args,
    )


@remediation_app.command("auto")
def remediate_auto(
    failure_type: str = typer.Argument(
        ...,
        help="Type of failure: dependency-sync, wheelhouse, mirror, artifact, drift",
    ),
    input_file: Path = typer.Option(
        None,
        "--input",
        "-i",
        help="Input file (error log or JSON report)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview actions without applying them",
    ),
    auto_apply: bool = typer.Option(
        False,
        "--auto-apply",
        help="Auto-apply remediation actions",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help=VERBOSE_HELP,
    ),
) -> None:
    """Intelligent autoremediation for common failures.

    Analyzes failure patterns and applies fixes automatically when
    confidence is high, or suggests manual actions otherwise.

    Example:
        chiron remediate auto dependency-sync --input error.log --auto-apply
    """
    import logging

    from chiron.remediation.autoremediate import AutoRemediator

    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    remediator = AutoRemediator(dry_run=dry_run, auto_apply=auto_apply)

    # Load input if provided
    if input_file:
        if not input_file.exists():
            typer.secho(f"❌ Input file not found: {input_file}", fg=typer.colors.RED)
            raise typer.Exit(1)

        if input_file.suffix == ".json":
            import json

            with input_file.open() as f:
                input_data = json.load(f)
        else:
            input_data = input_file.read_text()
    else:
        input_data = {}

    # Apply appropriate remediation
    try:
        if failure_type == "dependency-sync":
            if isinstance(input_data, str):
                result = remediator.remediate_dependency_sync_failure(input_data)
            else:
                typer.secho(
                    "❌ Dependency sync requires error log as input",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(1)

        elif failure_type == "wheelhouse":
            if isinstance(input_data, dict):
                result = remediator.remediate_wheelhouse_failure(input_data)
            else:
                typer.secho(
                    "❌ Wheelhouse remediation requires JSON report as input",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(1)

        elif failure_type == "mirror":
            mirror_path = (
                Path(input_data)
                if isinstance(input_data, str)
                else Path("vendor/mirror")
            )
            result = remediator.remediate_mirror_corruption(mirror_path)

        elif failure_type == "artifact":
            if isinstance(input_data, dict):
                artifact_path = Path(input_data.get("artifact_path", "dist"))
                result = remediator.remediate_artifact_validation_failure(
                    input_data, artifact_path
                )
            else:
                typer.secho(
                    "❌ Artifact remediation requires validation JSON as input",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(1)

        elif failure_type == "drift":
            if isinstance(input_data, dict):
                result = remediator.remediate_configuration_drift(input_data)
            else:
                typer.secho(
                    "❌ Drift remediation requires drift report JSON as input",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(1)

        else:
            typer.secho(f"❌ Unknown failure type: {failure_type}", fg=typer.colors.RED)
            raise typer.Exit(1)

        # Report results
        if result.success:
            typer.secho("✅ Remediation successful", fg=typer.colors.GREEN)
        else:
            typer.secho("⚠️  Remediation completed with issues", fg=typer.colors.YELLOW)

        if result.actions_applied:
            typer.echo("\nActions applied:")
            for action in result.actions_applied:
                typer.secho(f"  ✓ {action}", fg=typer.colors.GREEN)

        if result.actions_failed:
            typer.echo("\nActions failed:")
            for action in result.actions_failed:
                typer.secho(f"  ✗ {action}", fg=typer.colors.RED)

        if result.warnings:
            typer.echo("\nWarnings:")
            for warning in result.warnings:
                typer.secho(f"  ⚠ {warning}", fg=typer.colors.YELLOW)

        if result.errors:
            typer.echo("\nErrors:")
            for error in result.errors:
                typer.secho(f"  • {error}", fg=typer.colors.RED)

        if not result.success:
            raise typer.Exit(1)

    except Exception as exc:
        typer.secho(f"❌ Remediation failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(1)


# ============================================================================
# Orchestration Commands
# ============================================================================


@orchestrate_app.command("status")
def orchestrate_status(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed status",
    ),
) -> None:
    """Show orchestration status."""
    from chiron.orchestration import OrchestrationContext, OrchestrationCoordinator

    context = OrchestrationContext(verbose=verbose)
    coordinator = OrchestrationCoordinator(context)

    status = coordinator.get_status()

    typer.echo("=== Orchestration Status ===")
    typer.echo(f"  Dependencies Synced: {status['context']['dependencies_synced']}")
    typer.echo(f"  Wheelhouse Built: {status['context']['wheelhouse_built']}")
    typer.echo(f"  Validation Passed: {status['context']['validation_passed']}")

    if status.get("recommendations"):
        typer.echo("\nRecommendations:")
        for rec in status["recommendations"]:
            typer.echo(f"  • {rec}")

    if verbose:
        typer.echo("\nFull Status:")
        typer.echo(json.dumps(status, indent=2))


@orchestrate_app.command("full-dependency")
def orchestrate_full_dependency(
    auto_upgrade: bool = typer.Option(
        False,
        "--auto-upgrade",
        help="Automatically plan upgrades",
    ),
    force_sync: bool = typer.Option(
        False,
        "--force-sync",
        help="Force dependency sync",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=DRY_RUN_HELP,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output",
    ),
) -> None:
    """Execute full dependency workflow."""
    from chiron.orchestration import OrchestrationContext, OrchestrationCoordinator

    context = OrchestrationContext(dry_run=dry_run, verbose=verbose)
    coordinator = OrchestrationCoordinator(context)

    typer.echo("Starting full dependency workflow...")
    results = coordinator.full_dependency_workflow(
        auto_upgrade=auto_upgrade,
        force_sync=force_sync,
    )

    typer.echo("\n✅ Dependency workflow complete")
    if results.get("preflight"):
        typer.echo("  • Preflight: completed")
    if results.get("guard"):
        guard_status = results["guard"].get("status", "unknown")
        typer.echo(f"  • Guard: {guard_status}")
    if results.get("upgrade"):
        typer.echo("  • Upgrade: planned")
    if results.get("sync"):
        typer.echo("  • Sync: completed")


@orchestrate_app.command("intelligent-upgrade")
def orchestrate_intelligent_upgrade(
    auto_apply_safe: bool = typer.Option(
        False,
        "--auto-apply-safe",
        help="Automatically apply safe upgrades",
    ),
    update_mirror: bool = typer.Option(
        True,
        "--update-mirror/--no-update-mirror",
        help="Update dependency mirror",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Dry run mode",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output",
    ),
) -> None:
    """Execute intelligent upgrade workflow with mirror synchronization."""
    from chiron.orchestration import OrchestrationContext, OrchestrationCoordinator

    context = OrchestrationContext(dry_run=dry_run, verbose=verbose)
    coordinator = OrchestrationCoordinator(context)

    typer.echo("🚀 Starting intelligent upgrade workflow...")
    results = coordinator.intelligent_upgrade_workflow(
        auto_apply_safe=auto_apply_safe,
        update_mirror=update_mirror,
    )

    typer.echo("\n✅ Intelligent upgrade workflow complete")
    if results.get("advice"):
        typer.echo("  • Upgrade advice: generated")
    if results.get("auto_apply"):
        status = results["auto_apply"].get("status", "unknown")
        typer.echo(f"  • Auto-apply: {status}")
    if results.get("mirror_update"):
        typer.echo("  • Mirror: updated")
    if results.get("validation"):
        typer.echo("  • Validation: completed")
        typer.echo(f"  • Sync: {'success' if results['sync'] else 'failed'}")


@orchestrate_app.command("full-packaging")
def orchestrate_full_packaging(
    validate: bool = typer.Option(
        True,
        "--validate/--no-validate",
        help="Validate after packaging",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Dry run mode",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output",
    ),
) -> None:
    """Execute full packaging workflow."""
    from chiron.orchestration import OrchestrationContext, OrchestrationCoordinator

    context = OrchestrationContext(dry_run=dry_run, verbose=verbose)
    coordinator = OrchestrationCoordinator(context)

    typer.echo("Starting full packaging workflow...")
    results = coordinator.full_packaging_workflow(validate=validate)

    typer.echo("\n✅ Packaging workflow complete")
    if results.get("wheelhouse"):
        typer.echo(f"  • Wheelhouse: {'built' if results['wheelhouse'] else 'failed'}")
    if results.get("offline_package"):
        typer.echo(
            f"  • Offline package: {'success' if results['offline_package'] else 'failed'}"
        )
    if results.get("validation"):
        validation_ok = results["validation"].get("success", False)
        typer.echo(f"  • Validation: {'passed' if validation_ok else 'failed'}")
        if not validation_ok and results.get("remediation"):
            typer.echo("  • Remediation: recommendations generated")


@orchestrate_app.command("sync-remote")
def orchestrate_sync_remote(
    artifact_dir: Path = typer.Argument(
        ...,
        help="Directory containing remote artifacts to sync",
    ),
    validate: bool = typer.Option(
        True,
        VALIDATE_OPTION,
        help="Validate after sync",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Dry run mode",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output",
    ),
) -> None:
    """Sync remote artifacts to local environment."""
    from chiron.orchestration import OrchestrationContext, OrchestrationCoordinator

    context = OrchestrationContext(dry_run=dry_run, verbose=verbose)
    coordinator = OrchestrationCoordinator(context)

    artifact_path = artifact_dir.resolve()
    if not artifact_path.exists():
        typer.secho(
            f"Artifact directory not found: {artifact_path}", fg=typer.colors.RED
        )
        raise typer.Exit(1)

    typer.echo(f"Syncing artifacts from {artifact_path}...")
    results = coordinator.sync_remote_to_local(artifact_path, validate=validate)

    typer.echo("\n✅ Sync complete")
    if results.get("copy"):
        typer.echo("  • Artifacts: copied")
    if results.get("sync"):
        typer.echo("  • Dependencies: synced")
    if results.get("validation"):
        typer.echo("  • Validation: passed")


@orchestrate_app.command("air-gapped-prep")
def orchestrate_air_gapped_prep(
    include_models: bool = typer.Option(
        True,
        "--models/--no-models",
        help="Include model downloads",
    ),
    include_containers: bool = typer.Option(
        False,
        "--containers/--no-containers",
        help="Include container images",
    ),
    validate: bool = typer.Option(
        True,
        VALIDATE_OPTION,
        help="Validate complete package",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Dry run mode",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output",
    ),
) -> None:
    """Execute complete air-gapped preparation workflow.

    Prepares everything needed for offline deployment:
    - Dependency management and sync
    - Multi-platform wheelhouse building
    - Model downloads
    - Container images (optional)
    - Checksums and manifests
    - Complete validation

    This is the recommended workflow for air-gapped deployments.
    """
    from chiron.orchestration import OrchestrationContext, OrchestrationCoordinator

    context = OrchestrationContext(dry_run=dry_run, verbose=verbose)
    coordinator = OrchestrationCoordinator(context)

    typer.echo("🚀 Starting air-gapped preparation workflow...")
    typer.echo()

    results = coordinator.air_gapped_preparation_workflow(
        include_models=include_models,
        include_containers=include_containers,
        validate=validate,
    )

    typer.echo()
    typer.echo("=" * 60)
    typer.echo("Air-Gapped Preparation Summary")
    typer.echo("=" * 60)

    if results.get("dependencies"):
        typer.echo("✅ Dependencies: synced")

    if results.get("wheelhouse"):
        typer.echo("✅ Wheelhouse: built")
    else:
        typer.secho("❌ Wheelhouse: failed", fg=typer.colors.RED)

    if results.get("models"):
        typer.echo("✅ Models: downloaded")
    elif results.get("models") is None:
        typer.echo("⊘  Models: skipped")
    else:
        typer.secho("❌ Models: failed", fg=typer.colors.RED)

    if results.get("containers"):
        typer.echo("✅ Containers: prepared")
    elif results.get("containers") is None:
        typer.echo("⊘  Containers: skipped")
    else:
        typer.secho("❌ Containers: failed", fg=typer.colors.RED)

    if results.get("offline_package"):
        typer.echo("✅ Offline package: created")
    else:
        typer.secho("❌ Offline package: failed", fg=typer.colors.RED)

    if results.get("validation"):
        validation_ok = results["validation"].get("success", False)
        if validation_ok:
            typer.echo("✅ Validation: passed")
        else:
            typer.secho("⚠️  Validation: issues found", fg=typer.colors.YELLOW)
            if results.get("remediation"):
                typer.echo("   → Remediation recommendations generated")
    elif results.get("validation") is None:
        typer.echo("⊘  Validation: skipped")

    typer.echo()

    # Overall success check
    all_success = all(
        v is True or (isinstance(v, dict) and v.get("success"))
        for v in results.values()
        if v is not None
    )

    if all_success:
        typer.secho("✅ Air-gapped preparation complete!", fg=typer.colors.GREEN)
    else:
        typer.secho(
            "⚠️  Air-gapped preparation completed with issues", fg=typer.colors.YELLOW
        )
        raise typer.Exit(1)


@orchestrate_app.command(
    "governance",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def orchestrate_governance(ctx: Context) -> None:
    """Process dry-run governance artifacts.

    Derive governance artifacts for dry-run CI executions,
    analyzing results and determining severity levels.
    """
    from chiron.orchestration import governance

    _invoke_cli_callable("chiron orchestrate governance", governance.main)


# ============================================================================
# GitHub Copilot Commands
# ============================================================================


@copilot_app.command("status")
def copilot_status(
    json_output: bool = typer.Option(False, "--json", help="Output status as JSON"),
) -> None:
    """Show readiness information for the Copilot coding agent."""

    status = collect_status(Path.cwd())

    if json_output:
        typer.echo(format_status_json(status))
        return

    if status.is_agent_environment:
        typer.secho(
            "✅ Copilot coding agent environment detected", fg=typer.colors.GREEN
        )
        if status.indicator_keys:
            typer.echo("   Indicators: " + ", ".join(status.indicator_keys))
    else:
        typer.secho(
            "ℹ️  Copilot coding agent environment not detected", fg=typer.colors.BLUE
        )
        if status.indicator_keys:
            typer.echo(
                "   Copilot-related variables present: "
                + ", ".join(status.indicator_keys)
            )

    if status.wheelhouse_disabled:
        typer.secho(
            "✅ Vendor wheelhouse overrides disabled (remote registries enabled)",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            f"⚠️  {COPILOT_DISABLE_ENV_VAR} not set — offline wheelhouse still enforced",
            fg=typer.colors.YELLOW,
        )
        typer.echo('   Tip: eval "$(chiron github copilot env)"')

    if status.pip_overrides_active:
        typer.secho("⚠️  pip offline overrides still active", fg=typer.colors.YELLOW)
        if status.pip_no_index:
            typer.echo(f"   PIP_NO_INDEX={status.pip_no_index}")
        if status.pip_find_links:
            typer.echo(f"   PIP_FIND_LINKS={status.pip_find_links}")
    else:
        typer.secho("✅ pip overrides cleared", fg=typer.colors.GREEN)

    if status.workflow_present:
        typer.secho(
            "✅ Workflow .github/workflows/copilot-setup-steps.yml present",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho("⚠️  Copilot setup workflow not found", fg=typer.colors.YELLOW)

    if status.uv_available:
        typer.secho("✅ uv executable available", fg=typer.colors.GREEN)
    else:
        typer.secho("⚠️  uv executable not found on PATH", fg=typer.colors.YELLOW)
        typer.echo(
            "   Install uv with 'pip install uv' or visit https://docs.astral.sh/uv/"
        )

    typer.echo(
        "\nUse `chiron github copilot prepare --dry-run` to preview the provisioning step."
    )


@copilot_app.command(
    "prepare",
    context_settings=_SCRIPT_PROXY_CONTEXT,
)
def copilot_prepare(
    ctx: Context,
    all_extras: bool = typer.Option(
        True,
        "--all-extras/--no-all-extras",
        help="Sync all optional extras (matches GitHub Copilot workflow)",
    ),
    extras: str | None = typer.Option(
        None,
        "--extras",
        help="Comma-separated extras when using --no-all-extras",
    ),
    include_dev: bool = typer.Option(
        True, "--dev/--no-dev", help="Include development dependencies"
    ),
    uv_path: Path | None = typer.Option(
        None, "--uv-path", help="Explicit path to the uv executable"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview without executing uv"
    ),
    clear_offline_overrides: bool = typer.Option(
        True,
        "--clear-offline-overrides/--keep-offline-overrides",
        help="Clear pip offline overrides so remote installs succeed",
    ),
) -> None:
    """Run ``uv sync`` with Copilot-friendly settings."""

    extras_list = (
        tuple(item.strip() for item in extras.split(",") if item.strip())
        if extras and not all_extras
        else None
    )

    additional_args = list(ctx.args)

    if extras and all_extras:
        typer.secho(
            "ℹ️  Ignoring --extras because --all-extras is active.",
            fg=typer.colors.YELLOW,
        )

    result = prepare_environment(
        workspace_root=Path.cwd(),
        all_extras=all_extras,
        extras=extras_list,
        include_dev=include_dev,
        uv_path=str(uv_path) if uv_path else None,
        dry_run=dry_run,
        clear_offline_overrides=clear_offline_overrides,
        additional_args=additional_args,
    )

    if not result.command:
        message = result.message or "uv executable not found on PATH"
        typer.secho(f"❌ {message}", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.echo(f"$ {' '.join(result.command)}")

    if result.env_overrides:
        typer.echo("Environment overrides:")
        for key in sorted(result.env_overrides):
            value = result.env_overrides[key]
            if value is None:
                typer.echo(f"  unset {key}")
            else:
                typer.echo(f"  {key}={value}")

    if result.dry_run:
        typer.secho("Dry run — no commands executed.", fg=typer.colors.BLUE)
        return

    if result.success:
        typer.secho(
            "✅ Copilot environment prepared successfully", fg=typer.colors.GREEN
        )
    else:
        message = result.message or "uv sync failed"
        typer.secho(f"❌ {message}", fg=typer.colors.RED)
        raise typer.Exit(result.exit_code or 1)


@copilot_app.command("env")
def copilot_env(
    shell: str = typer.Option(
        "bash",
        "--shell",
        help="Target shell for output (bash, zsh, sh, fish, powershell, cmd)",
    ),
) -> None:
    """Emit shell commands that configure Copilot-friendly environment variables."""

    try:
        snippet = generate_env_exports(shell)
    except CopilotProvisioningError as exc:  # pragma: no cover - defensive
        typer.secho(f"❌ {exc}", fg=typer.colors.RED)
        raise typer.Exit(1) from exc

    typer.echo(snippet)


# ============================================================================
# GitHub Commands
# ============================================================================


@github_app.command("sync")
def github_sync(
    run_id: str = typer.Argument(
        ...,
        help="GitHub Actions workflow run ID",
    ),
    artifacts: list[str] = typer.Option(
        None,
        "--artifact",
        "-a",
        help="Specific artifacts to download (can be repeated)",
    ),
    output_dir: Path = typer.Option(
        Path("vendor/artifacts"),
        "--output-dir",
        "-o",
        help="Output directory for artifacts",
    ),
    sync_to: str = typer.Option(
        None,
        "--sync-to",
        help="Sync to vendor/, dist/, or var/ after download",
    ),
    merge: bool = typer.Option(
        False,
        "--merge",
        help="Merge artifacts when syncing",
    ),
    validate: bool = typer.Option(
        True,
        VALIDATE_OPTION,
        help="Validate artifacts after download",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output",
    ),
) -> None:
    """Download and sync GitHub Actions artifacts.

    Downloads artifacts from a specific workflow run and optionally
    validates and syncs them to local directories.

    Example:
        chiron github sync 12345678 --artifact wheelhouse-linux --sync-to vendor
    """
    from chiron.github import GitHubArtifactSync

    syncer = GitHubArtifactSync(
        target_dir=output_dir,
        verbose=verbose,
    )

    # Download artifacts
    typer.echo(f"📥 Downloading artifacts from run {run_id}...")
    result = syncer.download_artifacts(
        run_id,
        artifacts or None,
        output_dir,
    )

    if not result.success:
        typer.secho("❌ Artifact download failed:", fg=typer.colors.RED)
        for error in result.errors:
            typer.secho(f"  - {error}", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.secho(
        f"✅ Downloaded {len(result.artifacts_downloaded)} artifacts",
        fg=typer.colors.GREEN,
    )
    for name in result.artifacts_downloaded:
        typer.echo(f"  • {name}")

    # Validate if requested
    if validate:
        typer.echo("\n🔍 Validating artifacts...")
        all_valid = True

        for artifact_name in result.artifacts_downloaded:
            artifact_path = output_dir / artifact_name
            validation = syncer.validate_artifacts(artifact_path, "wheelhouse")

            if validation["valid"]:
                typer.secho(f"  ✅ {artifact_name}: Valid", fg=typer.colors.GREEN)
            else:
                typer.secho(
                    f"  ⚠️  {artifact_name}: Issues found", fg=typer.colors.YELLOW
                )
                for error in validation["errors"]:
                    typer.secho(f"      - {error}", fg=typer.colors.RED)
                all_valid = False

        if not all_valid:
            typer.secho(
                "\n⚠️  Some artifacts have validation issues", fg=typer.colors.YELLOW
            )

    # Sync if requested
    if sync_to:
        typer.echo(f"\n🔄 Syncing to {sync_to}/...")

        for artifact_name in result.artifacts_downloaded:
            artifact_path = output_dir / artifact_name
            success = syncer.sync_to_local(artifact_path, sync_to, merge)  # type: ignore

            if not success:
                typer.secho(f"Failed to sync {artifact_name}", fg=typer.colors.RED)
                raise typer.Exit(1)

        typer.secho(f"✅ Synced to {sync_to}/", fg=typer.colors.GREEN)


@github_app.command("validate")
def github_validate(
    artifact_dir: Path = typer.Argument(
        ...,
        help="Directory containing artifacts to validate",
    ),
    artifact_type: str = typer.Option(
        "wheelhouse",
        "--type",
        "-t",
        help="Artifact type: wheelhouse, offline-package, or models",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output",
    ),
) -> None:
    """Validate GitHub Actions artifacts.

    Checks artifact structure, manifest integrity, and content completeness.
    """
    from chiron.github import validate_artifacts

    if not artifact_dir.exists():
        typer.secho(f"❌ Directory not found: {artifact_dir}", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.echo(f"🔍 Validating {artifact_type} artifacts in {artifact_dir}...")

    validation = validate_artifacts(artifact_dir, artifact_type)  # type: ignore

    if validation["valid"]:
        typer.secho("✅ Validation passed", fg=typer.colors.GREEN)
        if validation.get("metadata"):
            typer.echo("\nMetadata:")
            for key, value in validation["metadata"].items():
                typer.echo(f"  {key}: {value}")
    else:
        typer.secho("❌ Validation failed", fg=typer.colors.RED)

        if validation.get("errors"):
            typer.echo("\nErrors:")
            for error in validation["errors"]:
                typer.secho(f"  - {error}", fg=typer.colors.RED)

        raise typer.Exit(1)

    if validation.get("warnings"):
        typer.echo("\nWarnings:")
        for warning in validation["warnings"]:
            typer.secho(f"  - {warning}", fg=typer.colors.YELLOW)


# ============================================================================
# Plugin Commands
# ============================================================================

plugin_app = typer.Typer(help="Plugin management commands")
app.add_typer(plugin_app, name="plugin")


@plugin_app.command("list")
def plugin_list() -> None:
    """List all registered Chiron plugins."""
    from chiron.plugins import list_plugins

    plugins = list_plugins()

    if not plugins:
        typer.echo("No plugins registered.")
        return

    typer.echo(f"Registered Plugins ({len(plugins)}):\n")
    for plugin in plugins:
        typer.echo(f"  • {plugin.name} v{plugin.version}")
        if plugin.description:
            typer.echo(f"    {plugin.description}")
        if plugin.author:
            typer.echo(f"    Author: {plugin.author}")
        typer.echo()


@plugin_app.command("discover")
def plugin_discover(
    entry_point: str = typer.Option(
        "chiron.plugins",
        "--entry-point",
        help="Entry point group to discover plugins from",
    ),
) -> None:
    """Discover and register plugins from entry points."""
    from chiron.plugins import discover_plugins, register_plugin

    typer.echo(f"Discovering plugins from entry point: {entry_point}")

    plugins = discover_plugins(entry_point)

    if not plugins:
        typer.echo("No plugins discovered.")
        return

    typer.echo(f"\nDiscovered {len(plugins)} plugin(s):\n")
    for plugin in plugins:
        metadata = plugin.metadata
        typer.echo(f"  • {metadata.name} v{metadata.version}")
        register_plugin(plugin)

    typer.echo("\n✅ All plugins registered successfully")


# ============================================================================
# Telemetry Commands
# ============================================================================

telemetry_app = typer.Typer(help="Telemetry and observability commands")
app.add_typer(telemetry_app, name="telemetry")


@telemetry_app.command("summary")
def telemetry_summary() -> None:
    """Display telemetry summary for recent operations."""
    from chiron.telemetry import get_telemetry

    telemetry = get_telemetry()
    summary = telemetry.get_summary()

    typer.echo("=== Chiron Telemetry Summary ===\n")
    typer.echo(f"Total Operations: {summary['total']}")
    typer.echo(f"Success: {summary['success']}")
    typer.echo(f"Failure: {summary['failure']}")
    typer.echo(f"Avg Duration: {summary['avg_duration_ms']:.2f}ms")

    if summary["total"] > 0:
        success_rate = (summary["success"] / summary["total"]) * 100
        typer.echo(f"Success Rate: {success_rate:.1f}%")


@telemetry_app.command("metrics")
def telemetry_metrics(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """Display detailed metrics for all operations."""
    from chiron.telemetry import get_telemetry

    telemetry = get_telemetry()
    metrics = telemetry.get_metrics()

    if not metrics:
        typer.echo("No metrics recorded.")
        return

    if json_output:
        import json

        data = [m.to_dict() for m in metrics]
        typer.echo(json.dumps(data, indent=2))
    else:
        typer.echo(f"=== Chiron Operations ({len(metrics)}) ===\n")
        for m in metrics:
            status = "✓" if m.success else "✗"
            typer.echo(f"{status} {m.operation}")
            typer.echo(f"  Duration: {m.duration_ms:.2f}ms")
            if m.error:
                typer.echo(f"  Error: {m.error}")
            typer.echo()


@telemetry_app.command("clear")
def telemetry_clear() -> None:
    """Clear all recorded telemetry metrics."""
    from chiron.telemetry import get_telemetry

    telemetry = get_telemetry()
    telemetry.clear_metrics()
    typer.echo("✅ Telemetry metrics cleared")


# ============================================================================
# Main Entry Point
# ============================================================================


def main() -> None:
    """Main CLI entry point."""
    try:
        app(standalone_mode=False)
    except SystemExit as exc:
        code = exc.code if exc.code is not None else 0
        raise SystemExit(code if isinstance(code, int) else 1)
    except Exception as exc:
        logger.exception("Chiron CLI failed")
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
