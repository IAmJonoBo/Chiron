"""Command-line interface for Chiron."""

# mypy: disallow-any-decorated = False

import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import click
import structlog
from rich.console import Console
from rich.table import Table

from chiron import __version__
from chiron.core import ChironCore
from chiron.exceptions import ChironError
from chiron.schema_validator import validate_config

console = Console()
logger = structlog.get_logger(__name__)

WHEELHOUSE_CHECKSUM_FILENAME = "wheelhouse.sha256"


def _resolve_executable(executable: str) -> str:
    """Return an absolute path to the requested executable or raise a Click error."""

    path = Path(executable)
    if path.is_absolute():
        return str(path)

    if path.parent != Path("."):
        candidate = path.resolve()
        if candidate.exists():
            return str(candidate)

    resolved = shutil.which(executable)
    if resolved is None:
        raise click.ClickException(
            f"Required executable '{executable}' was not found on PATH."
        )
    return resolved


def _run_command(
    command: Sequence[str], **kwargs: object
) -> subprocess.CompletedProcess[str]:
    """Run a command with sanitized executable resolution."""

    if not command:
        raise click.ClickException("Command must contain at least one argument.")

    resolved = [_resolve_executable(command[0]), *command[1:]]
    return subprocess.run(resolved, **kwargs)  # noqa: S603


def _current_git_commit() -> str | None:
    """Return the current git commit SHA if available."""

    try:
        result = _run_command(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (
        click.ClickException,
        subprocess.CalledProcessError,
    ):  # pragma: no cover - best effort
        return None

    return result.stdout.strip() or None


def _write_wheel_checksums(wheelhouse_dir: Path) -> Path | None:
    """Generate SHA256 sums for wheels in *wheelhouse_dir*.

    Returns the path of the checksum file when wheels are present, otherwise ``None``.
    """

    wheels = sorted(wheelhouse_dir.glob("*.whl"))
    if not wheels:
        return None

    checksum_path = wheelhouse_dir / WHEELHOUSE_CHECKSUM_FILENAME
    lines: list[str] = []
    for wheel in wheels:
        sha256 = hashlib.sha256()
        with wheel.open("rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                sha256.update(chunk)
        lines.append(f"{sha256.hexdigest()}  {wheel.name}\n")

    checksum_path.write_text("".join(lines), encoding="utf-8")
    return checksum_path


def _write_manifest(path: Path, extras: Sequence[str]) -> None:
    """Write a lightweight wheelhouse manifest."""

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "extras": list(extras),
        "include_dev": "dev" in extras,
        "create_archive": False,
        "commit": _current_git_commit(),
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--json-output", is_flag=True, help="Output in JSON format")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be done without making changes"
)
@click.pass_context
def cli(
    ctx: click.Context,
    config: Path | None,
    verbose: bool,
    json_output: bool,
    dry_run: bool,
) -> None:
    """Chiron - Frontier-grade, production-ready Python library and service."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["json_output"] = json_output
    ctx.obj["dry_run"] = dry_run

    # Load configuration
    if config:
        try:
            with open(config) as f:
                ctx.obj["config"] = json.load(f)

            # Validate configuration against schema
            errors = validate_config(ctx.obj["config"])
            if errors:
                console.print("[yellow]Configuration validation warnings:[/yellow]")
                for error in errors:
                    console.print(f"  • {error}")
                if not verbose:
                    console.print("[dim]Use --verbose to see all details[/dim]")
        except (json.JSONDecodeError, OSError) as e:
            console.print(f"[red]Error loading config: {e}[/red]")
            sys.exit(1)
    else:
        ctx.obj["config"] = {}


@cli.command()
@click.option("--wizard", is_flag=True, help="Use interactive wizard mode")
def init(wizard: bool) -> None:
    """Initialize a new Chiron project."""
    if wizard:
        from chiron.wizard import run_init_wizard

        try:
            run_init_wizard()
            # Config is already saved by wizard
            return
        except KeyboardInterrupt:
            console.print("\n[yellow]Wizard cancelled[/yellow]")
            return

    config_path = Path("chiron.json")

    if config_path.exists():
        console.print("[yellow]Configuration file already exists[/yellow]")
        return

    default_config = {
        "service_name": "chiron-service",
        "version": "0.1.0",
        "telemetry": {
            "enabled": True,
            "otlp_endpoint": "http://localhost:4317",
        },
        "security": {
            "enabled": True,
            "audit_logging": True,
        },
    }

    with open(config_path, "w") as f:
        json.dump(default_config, f, indent=2)

    console.print(f"[green]Created configuration file: {config_path}[/green]")


@cli.command()
@click.pass_context
def build(ctx: click.Context) -> None:
    """Build the project with cibuildwheel."""
    dry_run = ctx.obj.get("dry_run", False)

    if dry_run:
        console.print("[yellow]DRY RUN - No changes will be made[/yellow]")
        console.print("[blue]Would execute: uv run cibuildwheel --platform auto[/blue]")
        console.print("[dim]Run without --dry-run to actually build[/dim]")
        return

    console.print("[blue]Building project with cibuildwheel...[/blue]")

    try:
        # Use uv to run cibuildwheel
        result = _run_command(
            ["uv", "run", "cibuildwheel", "--platform", "auto"],
            check=True,
            capture_output=True,
            text=True,
        )
        console.print("[green]Build completed successfully[/green]")
        if ctx.obj["verbose"]:
            console.print(result.stdout)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print(e.stderr)
        sys.exit(1)


@cli.command()
@click.pass_context
def release(ctx: click.Context) -> None:
    """Cut a semantic release."""
    console.print("[blue]Creating semantic release...[/blue]")

    try:
        # Use semantic-release to create a release
        result = _run_command(
            ["uv", "run", "semantic-release", "version"],
            check=True,
            capture_output=True,
            text=True,
        )
        console.print("[green]Release created successfully[/green]")
        if ctx.obj["verbose"]:
            console.print(result.stdout)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Release failed: {e}[/red]")
        if ctx.obj["verbose"]:
            console.print(e.stderr)
        sys.exit(1)


@cli.command()
@click.option(
    "--output-dir",
    "-o",
    default="vendor/wheelhouse",
    show_default=True,
    help="Output directory for the wheelhouse",
)
@click.option(
    "--extra",
    "-e",
    "extras",
    multiple=True,
    help="Extra requirement groups to include (defaults to dev,test unless --base-only)",
)
@click.option(
    "--base-only",
    is_flag=True,
    help="Only package core dependencies (ignore default extras).",
)
@click.option(
    "--include-all-extras",
    is_flag=True,
    help="Include the consolidated 'all' extra in addition to any explicit extras.",
)
@click.option(
    "--clean/--no-clean",
    default=True,
    show_default=True,
    help="Clean the output directory before downloading dependencies.",
)
@click.option("--with-sbom", is_flag=True, help="Generate SBOM")
@click.option("--with-signatures", is_flag=True, help="Sign artifacts")
@click.pass_context
def wheelhouse(
    ctx: click.Context,
    output_dir: str,
    extras: tuple[str, ...],
    base_only: bool,
    include_all_extras: bool,
    clean: bool,
    with_sbom: bool,
    with_signatures: bool,
) -> None:
    """Create/offline-sync wheelhouse bundles for reproducible installs."""

    dry_run = ctx.obj.get("dry_run", False)
    default_extras: tuple[str, ...] = ("dev", "test")

    if base_only:
        selected_extras: list[str] = []
    elif extras:
        # Preserve user-specified ordering while removing duplicates
        seen: set[str] = set()
        selected_extras = []
        for extra in extras:
            extra_name = extra.strip()
            if not extra_name or extra_name in seen:
                continue
            selected_extras.append(extra_name)
            seen.add(extra_name)
    else:
        selected_extras = list(default_extras)

    if include_all_extras and "all" not in selected_extras:
        selected_extras.append("all")

    extras_label = ",".join(selected_extras) if selected_extras else "(base only)"

    if dry_run:
        console.print("[yellow]DRY RUN - No changes will be made[/yellow]")
        console.print(f"[blue]Would create wheelhouse in: {output_dir}[/blue]")
        console.print(f"[blue]Extras: {extras_label}[/blue]")
        console.print(f"[blue]Clean output directory: {clean}[/blue]")
        console.print(f"[blue]Generate SBOM: {with_sbom}[/blue]")
        console.print(f"[blue]Sign artifacts: {with_signatures}[/blue]")
        console.print("[dim]Run without --dry-run to actually create wheelhouse[/dim]")
        return

    console.print(
        f"[blue]Creating wheelhouse in {output_dir} (extras: {extras_label})...[/blue]"
    )

    try:
        wheelhouse_path = Path(output_dir)
        wheelhouse_path.mkdir(parents=True, exist_ok=True)

        if clean:
            for path in wheelhouse_path.iterdir():
                try:
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                except FileNotFoundError:
                    continue

        console.print("[blue]Freezing dependency manifest...[/blue]")
        requirements_path = wheelhouse_path / "requirements.txt"
        compile_cmd = [
            "uv",
            "pip",
            "compile",
            "pyproject.toml",
            "--generate-hashes",
            "-o",
            str(requirements_path),
        ]
        for extra in selected_extras:
            compile_cmd.extend(["--extra", extra])
        _run_command(
            compile_cmd,
            check=True,
            capture_output=not ctx.obj.get("verbose", False),
            text=True,
        )

        console.print("[blue]Downloading dependency wheels...[/blue]")
        _run_command(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "-d",
                str(wheelhouse_path),
                "-r",
                str(requirements_path),
            ],
            check=True,
            capture_output=not ctx.obj.get("verbose", False),
            text=True,
        )

        console.print("[blue]Building project wheel...[/blue]")
        _run_command(
            ["uv", "build", "--wheel", "-o", str(wheelhouse_path)],
            check=True,
            capture_output=not ctx.obj.get("verbose", False),
            text=True,
        )

        manifest_path = wheelhouse_path / "manifest.json"
        _write_manifest(manifest_path, selected_extras)

        checksum_path = _write_wheel_checksums(wheelhouse_path)

        wheel_count = len(list(wheelhouse_path.glob("*.whl")))
        console.print(
            f"[green]Fetched {wheel_count} wheel(s) into {wheelhouse_path.resolve()}[/green]"
        )

        if checksum_path:
            console.print(f"[green]Wrote checksums to {checksum_path}[/green]")

        # Generate SBOM if requested
        if with_sbom:
            console.print("[blue]Generating SBOM...[/blue]")
            try:
                _run_command(
                    ["syft", str(wheelhouse_path), "-o", "cyclonedx-json=sbom.json"],
                    check=True,
                    capture_output=not ctx.obj.get("verbose", False),
                    text=True,
                )
                console.print("[green]SBOM generated: sbom.json[/green]")
            except (subprocess.CalledProcessError, FileNotFoundError):
                console.print(
                    "[yellow]Syft not found, skipping SBOM generation[/yellow]"
                )

        # Sign artifacts if requested
        if with_signatures:
            console.print("[blue]Signing artifacts...[/blue]")
            try:
                for wheel in wheelhouse_path.glob("*.whl"):
                    _run_command(
                        [
                            "cosign",
                            "sign-blob",
                            "--yes",
                            "--bundle",
                            f"{wheel}.sigstore.json",
                            str(wheel),
                        ],
                        check=True,
                        capture_output=not ctx.obj.get("verbose", False),
                        text=True,
                    )
                console.print("[green]Artifacts signed with Sigstore[/green]")
            except (subprocess.CalledProcessError, FileNotFoundError):
                console.print("[yellow]Cosign not found, skipping signing[/yellow]")

        console.print(f"[green]Wheelhouse created in {output_dir}[/green]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Wheelhouse creation failed: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--output", "-o", default="airgap-bundle.tar.gz", help="Output file")
@click.option(
    "--include-extras", is_flag=True, help="Include all optional dependencies"
)
@click.option(
    "--include-security", is_flag=True, help="Include security scanning tools"
)
@click.pass_context
def airgap(
    ctx: click.Context, output: str, include_extras: bool, include_security: bool
) -> None:  # type: ignore[no-untyped-def]
    """Create an offline bundle for air-gapped environments."""
    dry_run = ctx.obj.get("dry_run", False)

    if dry_run:
        console.print("[yellow]DRY RUN - No changes will be made[/yellow]")
        console.print(f"[blue]Would create air-gapped bundle: {output}[/blue]")
        console.print(f"[blue]Include extras: {include_extras}[/blue]")
        console.print(f"[blue]Include security tools: {include_security}[/blue]")
        console.print("[dim]Run without --dry-run to actually create bundle[/dim]")
        return

    console.print(f"[blue]Creating air-gapped bundle: {output}...[/blue]")

    import tempfile

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            wheelhouse_dir = Path(temp_dir) / "wheelhouse"
            wheelhouse_dir.mkdir()

            console.print("[blue]Downloading dependencies...[/blue]")

            # Base installation
            cmd = ["uv", "pip", "download", "-d", str(wheelhouse_dir), "."]
            if include_extras:
                cmd[-1] = ".[all]"

            _run_command(cmd, check=True, capture_output=True)

            # Security tools
            if include_security:
                console.print("[blue]Adding security tools...[/blue]")
                for tool in ["bandit", "safety", "semgrep"]:
                    _run_command(
                        ["uv", "pip", "download", "-d", str(wheelhouse_dir), tool],
                        check=True,
                        capture_output=True,
                    )

            # Create bundle
            console.print(f"[blue]Creating bundle: {output}...[/blue]")
            _run_command(
                ["tar", "-czf", output, "-C", temp_dir, "wheelhouse/"], check=True
            )

            console.print(f"[green]Air-gapped bundle created: {output}[/green]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to create airgap bundle: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("target", required=False)
@click.option("--verify-signatures", is_flag=True, help="Verify Sigstore signatures")
@click.option("--verify-sbom", is_flag=True, help="Verify SBOM integrity")
@click.option("--verify-provenance", is_flag=True, help="Verify SLSA provenance")
@click.option("--verify-hashes", is_flag=True, help="Verify file checksums")
@click.option("--all", "verify_all", is_flag=True, help="Verify all attestations")
@click.pass_context
def verify(
    ctx: click.Context,
    target: str | None,
    verify_signatures: bool,
    verify_sbom: bool,
    verify_provenance: bool,
    verify_hashes: bool,
    verify_all: bool,
) -> None:  # type: ignore[no-untyped-def]
    """Verify signatures, provenance, and SBOM of artifacts."""
    console.print("[blue]Verifying artifacts...[/blue]")

    # If --all is specified, enable all verifications
    if verify_all:
        verify_signatures = verify_sbom = verify_provenance = verify_hashes = True

    # Default to hash verification if nothing specified
    if not any([verify_signatures, verify_sbom, verify_provenance, verify_hashes]):
        verify_hashes = True

    target_path = Path(target) if target else Path(".")
    if not target_path.exists():
        console.print(f"[red]Target not found: {target}[/red]")
        sys.exit(1)

    results: list[tuple[str, bool | None]] = []
    all_passed = True

    # Verify hashes
    if verify_hashes:
        console.print("[blue]Verifying checksums...[/blue]")
        sha256_file = (
            target_path / WHEELHOUSE_CHECKSUM_FILENAME
            if target_path.is_dir()
            else target_path.parent / WHEELHOUSE_CHECKSUM_FILENAME
        )

        if sha256_file.exists():
            try:
                result = _run_command(
                    ["sha256sum", "-c", str(sha256_file)],
                    cwd=sha256_file.parent,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    console.print("[green]✓ Checksums verified[/green]")
                    results.append(("Checksums", True))
                else:
                    console.print("[red]✗ Checksum verification failed[/red]")
                    if ctx.obj["verbose"]:
                        console.print(result.stderr)
                    results.append(("Checksums", False))
                    all_passed = False
            except Exception as e:
                console.print(f"[yellow]⚠ Checksum verification error: {e}[/yellow]")
                results.append(("Checksums", False))
                all_passed = False
        else:
            console.print("[yellow]⚠ No checksums file found[/yellow]")
            results.append(("Checksums", None))

    # Verify signatures
    if verify_signatures:
        console.print("[blue]Verifying Sigstore signatures...[/blue]")
        sig_files = (
            list(target_path.glob("*.sigstore.json"))
            if target_path.is_dir()
            else list(target_path.parent.glob("*.sigstore.json"))
        )

        if sig_files:
            try:
                # Check if cosign is available
                _run_command(["cosign", "version"], capture_output=True, check=True)

                verified_count = 0
                for sig_file in sig_files:
                    artifact = sig_file.with_suffix("").with_suffix(
                        ""
                    )  # Remove .sigstore.json
                    if artifact.exists():
                        result = _run_command(
                            [
                                "cosign",
                                "verify-blob",
                                "--bundle",
                                str(sig_file),
                                str(artifact),
                            ],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if result.returncode == 0:
                            verified_count += 1

                if verified_count == len(sig_files):
                    console.print(
                        f"[green]✓ All {verified_count} signatures verified[/green]"
                    )
                    results.append(("Signatures", True))
                else:
                    console.print(
                        f"[yellow]⚠ Only {verified_count}/{len(sig_files)} signatures verified[/yellow]"
                    )
                    results.append(("Signatures", False))
                    all_passed = False
            except FileNotFoundError:
                console.print(
                    "[yellow]⚠ Cosign not found, skipping signature verification[/yellow]"
                )
                results.append(("Signatures", None))
            except Exception as e:
                console.print(f"[red]✗ Signature verification failed: {e}[/red]")
                results.append(("Signatures", False))
                all_passed = False
        else:
            console.print("[yellow]⚠ No signature files found[/yellow]")
            results.append(("Signatures", None))

    # Verify SBOM
    if verify_sbom:
        console.print("[blue]Verifying SBOM integrity...[/blue]")
        sbom_files = (
            list(target_path.glob("**/sbom*.json"))
            if target_path.is_dir()
            else list(target_path.parent.glob("**/sbom*.json"))
        )

        if sbom_files:
            try:
                import json

                valid_count = 0
                for sbom_file in sbom_files:
                    with open(sbom_file) as f:
                        sbom = json.load(f)
                        # Basic validation - check for required CycloneDX fields
                        if "bomFormat" in sbom and "specVersion" in sbom:
                            valid_count += 1

                if valid_count == len(sbom_files):
                    console.print(f"[green]✓ All {valid_count} SBOMs validated[/green]")
                    results.append(("SBOM", True))
                else:
                    console.print(
                        f"[yellow]⚠ Only {valid_count}/{len(sbom_files)} SBOMs valid[/yellow]"
                    )
                    results.append(("SBOM", False))
                    all_passed = False
            except Exception as e:
                console.print(f"[red]✗ SBOM verification failed: {e}[/red]")
                results.append(("SBOM", False))
                all_passed = False
        else:
            console.print("[yellow]⚠ No SBOM files found[/yellow]")
            results.append(("SBOM", None))

    # Verify provenance
    if verify_provenance:
        console.print("[blue]Verifying SLSA provenance...[/blue]")
        prov_files = (
            list(target_path.glob("**/provenance.json"))
            if target_path.is_dir()
            else list(target_path.parent.glob("**/provenance.json"))
        )

        if prov_files:
            try:
                import json

                valid_count = 0
                for prov_file in prov_files:
                    with open(prov_file) as f:
                        prov = json.load(f)
                        # Basic validation - check for required SLSA fields
                        if "buildType" in prov and "subject" in prov:
                            valid_count += 1

                if valid_count == len(prov_files):
                    console.print(
                        f"[green]✓ All {valid_count} provenance files validated[/green]"
                    )
                    results.append(("Provenance", True))
                else:
                    console.print(
                        f"[yellow]⚠ Only {valid_count}/{len(prov_files)} provenance files valid[/yellow]"
                    )
                    results.append(("Provenance", False))
                    all_passed = False
            except Exception as e:
                console.print(f"[red]✗ Provenance verification failed: {e}[/red]")
                results.append(("Provenance", False))
                all_passed = False
        else:
            console.print("[yellow]⚠ No provenance files found[/yellow]")
            results.append(("Provenance", None))

    # Print summary
    console.print("\n[bold]Verification Summary:[/bold]")
    for check, status in results:
        if status is True:
            console.print(f"  [green]✓[/green] {check}")
        elif status is False:
            console.print(f"  [red]✗[/red] {check}")
        else:
            console.print(f"  [yellow]⚠[/yellow] {check} (skipped)")

    if not all_passed:
        sys.exit(1)


@cli.group()
def manage() -> None:  # type: ignore[no-untyped-def]
    """Manage wheelhouses and packages."""
    pass


@manage.command()
@click.argument("packages", nargs=-1, required=True)
@click.option("--output-dir", "-o", default="wheelhouse", help="Output directory")
def download(packages: tuple[str, ...], output_dir: str) -> None:  # type: ignore[no-untyped-def]
    """Download packages to wheelhouse."""
    console.print(
        f"[blue]Downloading {len(packages)} packages to {output_dir}...[/blue]"
    )

    try:
        Path(output_dir).mkdir(exist_ok=True)

        for package in packages:
            console.print(f"[blue]Downloading {package}...[/blue]")
            _run_command(
                ["uv", "pip", "download", "-d", output_dir, package], check=True
            )

        console.print(f"[green]Downloaded {len(packages)} packages[/green]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Download failed: {e}[/red]")
        sys.exit(1)


@manage.command()
@click.argument("wheelhouse_dir", default="wheelhouse")
def list_packages(wheelhouse_dir: str) -> None:  # type: ignore[no-untyped-def]
    """List packages in wheelhouse."""
    from pathlib import Path

    wheelhouse_path = Path(wheelhouse_dir)
    if not wheelhouse_path.exists():
        console.print(f"[red]Wheelhouse directory not found: {wheelhouse_dir}[/red]")
        return

    wheels = list(wheelhouse_path.glob("*.whl"))
    tarballs = list(wheelhouse_path.glob("*.tar.gz"))

    if not wheels and not tarballs:
        console.print(f"[yellow]No packages found in {wheelhouse_dir}[/yellow]")
        return

    table = Table(title=f"Packages in {wheelhouse_dir}")
    table.add_column("Package", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Size", style="blue")

    for wheel in sorted(wheels):
        size = wheel.stat().st_size
        table.add_row(wheel.name, "wheel", f"{size:,} bytes")

    for tarball in sorted(tarballs):
        size = tarball.stat().st_size
        table.add_row(tarball.name, "source", f"{size:,} bytes")

    console.print(table)


@cli.command()
@click.pass_context
def doctor(ctx: click.Context) -> None:  # type: ignore[no-untyped-def]
    """Run policy checks and provide upgrade advice."""
    console.print("[blue]Running health checks...[/blue]")

    try:
        core = ChironCore(config=ctx.obj["config"])
        health = core.health_check()

        if ctx.obj["json_output"]:
            console.print(json.dumps(health, indent=2))
        else:
            table = Table(title="Chiron Health Check")
            table.add_column("Component", style="cyan")
            table.add_column("Status", style="green")

            for key, value in health.items():
                table.add_row(key, str(value))

            console.print(table)

    except ChironError as e:
        console.print(f"[red]Health check failed: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
@click.pass_context
def serve(
    ctx: click.Context,
    host: str,
    port: int,
    reload: bool,
) -> None:  # type: ignore[no-untyped-def]
    """Start the Chiron service."""
    console.print(f"[blue]Starting Chiron service on {host}:{port}...[/blue]")

    try:
        import uvicorn

        from chiron.service.app import create_app

        app = create_app(config=ctx.obj["config"])
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=reload,
            log_config=None,  # Use our structured logging
        )
    except ImportError:
        console.print("[red]Service dependencies not installed[/red]")
        console.print("Install with: uv pip install chiron[service]")
        sys.exit(1)


if __name__ == "__main__":
    cli()
