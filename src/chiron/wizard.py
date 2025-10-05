"""Interactive wizard mode for Chiron operations.

This module provides interactive prompts and guidance for common Chiron tasks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()


class ChironWizard:
    """Interactive wizard for Chiron operations."""

    def __init__(self) -> None:
        """Initialize wizard."""
        self.config: dict[str, Any] = {}

    def welcome(self) -> None:
        """Display welcome message."""
        console.print(
            Panel.fit(
                "[bold cyan]Chiron Interactive Setup Wizard[/bold cyan]\n\n"
                "This wizard will guide you through setting up Chiron\n"
                "for your project.",
                border_style="cyan",
            )
        )
        console.print()

    def init_project(self) -> dict[str, Any]:
        """Interactive project initialization.

        Returns:
            Configuration dictionary
        """
        self.welcome()

        # Basic settings
        console.print("[bold]Basic Settings[/bold]")
        service_name = Prompt.ask("Service name", default="chiron-service")

        version = Prompt.ask("Version", default="0.1.0")

        # Telemetry settings
        console.print("\n[bold]Telemetry Settings[/bold]")
        telemetry_enabled = Confirm.ask("Enable OpenTelemetry?", default=True)

        otlp_endpoint = "http://localhost:4317"
        if telemetry_enabled:
            otlp_endpoint = Prompt.ask("OTLP endpoint", default="http://localhost:4317")

        # Security settings
        console.print("\n[bold]Security Settings[/bold]")
        security_enabled = Confirm.ask("Enable security features?", default=True)

        audit_logging = True
        require_signatures = False
        if security_enabled:
            audit_logging = Confirm.ask("Enable audit logging?", default=True)
            require_signatures = Confirm.ask(
                "Require artifact signatures?", default=False
            )

        # Wheelhouse settings
        console.print("\n[bold]Wheelhouse Settings[/bold]")
        wheelhouse_path = Prompt.ask("Wheelhouse path", default="wheelhouse")

        platforms = self._select_platforms()
        python_versions = self._select_python_versions()

        # Build configuration
        config = {
            "service_name": service_name,
            "version": version,
            "telemetry": {
                "enabled": telemetry_enabled,
                "otlp_endpoint": otlp_endpoint,
            },
            "security": {
                "enabled": security_enabled,
                "audit_logging": audit_logging,
                "require_signatures": require_signatures,
            },
            "wheelhouse": {
                "path": wheelhouse_path,
                "platforms": platforms,
                "python_versions": python_versions,
            },
        }

        # Summary
        self._display_summary(config)

        if Confirm.ask("\nSave this configuration?", default=True):
            config_path = Path("chiron.json")
            import json

            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
            console.print(f"\n[green]✓[/green] Configuration saved to {config_path}")

        return config

    def build_wheelhouse_wizard(self) -> dict[str, Any]:
        """Interactive wheelhouse build configuration.

        Returns:
            Build configuration dictionary
        """
        console.print(
            Panel.fit(
                "[bold cyan]Wheelhouse Build Wizard[/bold cyan]", border_style="cyan"
            )
        )
        console.print()

        output_dir = Prompt.ask("Output directory", default="wheelhouse")

        with_sbom = Confirm.ask("Generate SBOM?", default=True)

        with_signatures = Confirm.ask("Sign artifacts with Sigstore?", default=True)

        with_vuln_scan = Confirm.ask("Scan for vulnerabilities?", default=True)

        config = {
            "output_dir": output_dir,
            "with_sbom": with_sbom,
            "with_signatures": with_signatures,
            "with_vuln_scan": with_vuln_scan,
        }

        # Show what will be done
        console.print("\n[bold]Build Plan:[/bold]")
        table = Table(show_header=False)
        table.add_column("Action")
        table.add_column("Status")

        table.add_row("Output directory", output_dir)
        table.add_row("Generate SBOM", "✓" if with_sbom else "✗")
        table.add_row("Sign artifacts", "✓" if with_signatures else "✗")
        table.add_row("Vulnerability scan", "✓" if with_vuln_scan else "✗")

        console.print(table)

        return config

    def verify_wizard(self) -> dict[str, Any]:
        """Interactive artifact verification.

        Returns:
            Verification configuration dictionary
        """
        console.print(
            Panel.fit(
                "[bold cyan]Artifact Verification Wizard[/bold cyan]",
                border_style="cyan",
            )
        )
        console.print()

        target = Prompt.ask("Path to artifact or directory", default=".")

        verify_signatures = Confirm.ask("Verify signatures?", default=True)

        verify_sbom = Confirm.ask("Verify SBOM?", default=True)

        verify_provenance = Confirm.ask("Verify provenance?", default=True)

        verify_hashes = Confirm.ask("Verify checksums?", default=True)

        config = {
            "target": target,
            "verify_signatures": verify_signatures,
            "verify_sbom": verify_sbom,
            "verify_provenance": verify_provenance,
            "verify_hashes": verify_hashes,
        }

        return config

    def _select_platforms(self) -> list[str]:
        """Select target platforms.

        Returns:
            List of selected platforms
        """
        console.print("\nSelect target platforms:")

        linux = Confirm.ask("  • Linux", default=True)
        macos = Confirm.ask("  • macOS", default=True)
        windows = Confirm.ask("  • Windows", default=True)

        platforms = []
        if linux:
            platforms.append("linux")
        if macos:
            platforms.append("macos")
        if windows:
            platforms.append("windows")

        return platforms

    def _select_python_versions(self) -> list[str]:
        """Select Python versions.

        Returns:
            List of selected Python versions
        """
        console.print("\nSelect Python versions:")
        console.print("  (Space-separated, e.g., '3.12 3.13')")

        versions_input = Prompt.ask("Python versions", default="3.12 3.13")

        return versions_input.split()

    def _display_summary(self, config: dict[str, Any]) -> None:
        """Display configuration summary.

        Args:
            config: Configuration dictionary
        """
        console.print("\n[bold]Configuration Summary:[/bold]")

        table = Table(show_header=False)
        table.add_column("Setting", style="cyan")
        table.add_column("Value")

        table.add_row("Service Name", config["service_name"])
        table.add_row("Version", config["version"])
        table.add_row("Telemetry", "✓" if config["telemetry"]["enabled"] else "✗")
        table.add_row("Security", "✓" if config["security"]["enabled"] else "✗")
        table.add_row("Wheelhouse Path", config["wheelhouse"]["path"])
        table.add_row("Platforms", ", ".join(config["wheelhouse"]["platforms"]))
        table.add_row(
            "Python Versions", ", ".join(config["wheelhouse"]["python_versions"])
        )

        console.print(table)


def run_init_wizard() -> dict[str, Any]:
    """Run the initialization wizard.

    Returns:
        Configuration dictionary
    """
    wizard = ChironWizard()
    return wizard.init_project()


def run_build_wizard() -> dict[str, Any]:
    """Run the build wizard.

    Returns:
        Build configuration dictionary
    """
    wizard = ChironWizard()
    return wizard.build_wheelhouse_wizard()


def run_verify_wizard() -> dict[str, Any]:
    """Run the verification wizard.

    Returns:
        Verification configuration dictionary
    """
    wizard = ChironWizard()
    return wizard.verify_wizard()
