from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace

import typer
from _pytest.monkeypatch import MonkeyPatch
from typer.testing import CliRunner

from chiron.cli.main import cli, main


def test_cli_exposes_typer_app() -> None:
    """The compatibility shim should expose the Typer application."""

    assert isinstance(cli, typer.Typer)


def test_main_invokes_typer_command(monkeypatch: MonkeyPatch) -> None:
    """Calling ``main`` should delegate to Typer's command execution."""

    invoked: dict[str, Sequence[str] | str] = {}

    def fake_get_command(app: typer.Typer) -> SimpleNamespace:
        assert app is cli
        return SimpleNamespace(
            main=lambda *, args=None, prog_name=None, standalone_mode=True: invoked.update(
                {"args": args, "prog_name": prog_name, "standalone_mode": standalone_mode}
            )
        )

    monkeypatch.setattr("chiron.cli.main.typer.main.get_command", fake_get_command)

    main(["--version"])

    assert invoked["args"] == ["--version"]
    assert invoked["prog_name"] == "chiron"
    # ``Typer`` calls ``Command.main`` with ``standalone_mode=True`` by default.
    assert invoked["standalone_mode"] is True


def test_cli_help_runs() -> None:
    """The re-exported CLI should still execute successfully."""

    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.stdout
