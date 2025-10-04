"""Command-line interface for Chiron."""

import json
import sys
from pathlib import Path
from typing import Optional

import click
import structlog
from rich.console import Console
from rich.table import Table

from chiron import __version__
from chiron.core import ChironCore
from chiron.exceptions import ChironError

console = Console()
logger = structlog.get_logger(__name__)


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--json-output", is_flag=True, help="Output in JSON format")
@click.pass_context
def cli(
    ctx: click.Context,
    config: Optional[Path],
    verbose: bool,
    json_output: bool,
) -> None:
    """Chiron - Frontier-grade, production-ready Python library and service."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["json_output"] = json_output

    # Load configuration
    if config:
        try:
            with open(config) as f:
                ctx.obj["config"] = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            console.print(f"[red]Error loading config: {e}[/red]")
            sys.exit(1)
    else:
        ctx.obj["config"] = {}


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize a new Chiron project."""
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
    console.print("[blue]Building project with cibuildwheel...[/blue]")

    import subprocess

    try:
        # Use uv to run cibuildwheel
        result = subprocess.run(
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

    import subprocess

    try:
        # Use semantic-release to create a release
        result = subprocess.run(
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
@click.option("--output-dir", "-o", default="wheelhouse", help="Output directory")
@click.option("--with-sbom", is_flag=True, help="Generate SBOM")
@click.option("--with-signatures", is_flag=True, help="Sign artifacts")
@click.pass_context
def wheelhouse(
    ctx: click.Context, output_dir: str, with_sbom: bool, with_signatures: bool
) -> None:
    """Create wheelhouse bundle with SBOM and signatures."""
    console.print(f"[blue]Creating wheelhouse in {output_dir}...[/blue]")

    import subprocess
    from pathlib import Path

    try:
        wheelhouse_path = Path(output_dir)
        wheelhouse_path.mkdir(exist_ok=True)

        # Download dependencies
        console.print("[blue]Downloading dependencies...[/blue]")
        subprocess.run(
            ["uv", "pip", "download", "-d", str(wheelhouse_path), "."],
            check=True,
            capture_output=True,
        )

        # Generate SBOM if requested
        if with_sbom:
            console.print("[blue]Generating SBOM...[/blue]")
            try:
                subprocess.run(
                    ["syft", str(wheelhouse_path), "-o", "cyclonedx-json=sbom.json"],
                    check=True,
                    capture_output=True,
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
                    subprocess.run(
                        [
                            "cosign",
                            "sign-blob",
                            "--yes",
                            "--bundle",
                            f"{wheel}.sigstore.json",
                            str(wheel),
                        ],
                        check=True,
                        capture_output=True,
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
) -> None:
    """Create an offline bundle for air-gapped environments."""
    console.print(f"[blue]Creating air-gapped bundle: {output}...[/blue]")

    import subprocess
    import tempfile
    from pathlib import Path

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            wheelhouse_dir = Path(temp_dir) / "wheelhouse"
            wheelhouse_dir.mkdir()

            console.print("[blue]Downloading dependencies...[/blue]")

            # Base installation
            cmd = ["uv", "pip", "download", "-d", str(wheelhouse_dir), "."]
            if include_extras:
                cmd[-1] = ".[all]"

            subprocess.run(cmd, check=True, capture_output=True)

            # Security tools
            if include_security:
                console.print("[blue]Adding security tools...[/blue]")
                for tool in ["bandit", "safety", "semgrep"]:
                    subprocess.run(
                        ["uv", "pip", "download", "-d", str(wheelhouse_dir), tool],
                        check=True,
                        capture_output=True,
                    )

            # Create bundle
            console.print(f"[blue]Creating bundle: {output}...[/blue]")
            subprocess.run(
                ["tar", "-czf", output, "-C", temp_dir, "wheelhouse/"], check=True
            )

            console.print(f"[green]Air-gapped bundle created: {output}[/green]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to create airgap bundle: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("target", required=False)
@click.pass_context
def verify(ctx: click.Context, target: Optional[str]) -> None:
    """Verify signatures, provenance, and SBOM."""
    console.print("[blue]Verifying artifacts...[/blue]")

    # This would implement the verification logic
    console.print("[yellow]Verification not yet implemented[/yellow]")


@cli.group()
def manage() -> None:
    """Manage wheelhouses and packages."""
    pass


@manage.command()
@click.argument("packages", nargs=-1, required=True)
@click.option("--output-dir", "-o", default="wheelhouse", help="Output directory")
def download(packages: tuple[str, ...], output_dir: str) -> None:
    """Download packages to wheelhouse."""
    console.print(
        f"[blue]Downloading {len(packages)} packages to {output_dir}...[/blue]"
    )

    import subprocess
    from pathlib import Path

    try:
        Path(output_dir).mkdir(exist_ok=True)

        for package in packages:
            console.print(f"[blue]Downloading {package}...[/blue]")
            subprocess.run(
                ["uv", "pip", "download", "-d", output_dir, package], check=True
            )

        console.print(f"[green]Downloaded {len(packages)} packages[/green]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Download failed: {e}[/red]")
        sys.exit(1)


@manage.command()
@click.argument("wheelhouse_dir", default="wheelhouse")
def list_packages(wheelhouse_dir: str) -> None:
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
def doctor(ctx: click.Context) -> None:
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
) -> None:
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
