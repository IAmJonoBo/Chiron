"""Compatibility shim bridging to the Typer-based Chiron CLI.

This module previously hosted a Click command tree. The authoritative CLI now
lives in :mod:`chiron.typer_cli`; this shim simply re-exports the Typer
application so historical entry points keep working without a Click
implementation.
"""

from __future__ import annotations

from collections.abc import Sequence

import typer

from chiron.typer_cli import app

__all__ = ["cli", "main"]

# Backwards-compatible name that existing entry points import.
cli = app


def main(argv: Sequence[str] | None = None) -> None:
    """Invoke the Typer CLI with optional *argv* overrides."""

    command = typer.main.get_command(cli)
    command.main(args=list(argv) if argv is not None else None, prog_name="chiron")
