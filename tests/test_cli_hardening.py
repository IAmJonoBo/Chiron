from __future__ import annotations

from typing import Any

import pytest
from typer.testing import CliRunner

from chiron.typer_cli import app as typer_app

pytest.importorskip("typer")


runner = CliRunner(mix_stderr=False)


def invoke(
    command: list[str],
    monkeypatch: pytest.MonkeyPatch,
    return_value: Any,
) -> tuple[int, str, list[str] | None]:
    """Patch ``guard.main`` to control exit behaviour and invoke the CLI."""

    captured: list[list[str] | None] = []

    def fake_main(argv: list[str] | None) -> Any:
        captured.append(argv)
        return return_value

    monkeypatch.setattr("chiron.deps.guard.main", fake_main)

    result = runner.invoke(typer_app, command)
    return result.exit_code, (result.stderr or result.stdout), captured[0] if captured else None


def test_guard_accepts_none_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returning ``None`` should be treated as success."""

    exit_code, _, args = invoke(["deps", "guard"], monkeypatch, None)

    assert exit_code == 0
    assert args is None


def test_guard_handles_false_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falsey boolean results should map to exit code 1 with messaging."""

    exit_code, output, _ = invoke(["deps", "guard"], monkeypatch, False)

    assert exit_code == 1
    assert "Command 'chiron deps guard' failed with exit code 1" in output


def test_guard_rejects_invalid_exit_type(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-standard return types should raise a descriptive error."""

    exit_code, output, _ = invoke(["deps", "guard"], monkeypatch, {"unexpected": True})

    assert exit_code == 1
    assert "returned unsupported result type dict" in output


def test_guard_propagates_system_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """SystemExit from delegated scripts should propagate cleanly."""

    def raise_exit(argv: list[str] | None) -> int:
        raise SystemExit(5)

    monkeypatch.setattr("chiron.deps.guard.main", raise_exit)

    result = runner.invoke(typer_app, ["deps", "guard"])

    assert result.exit_code == 5
