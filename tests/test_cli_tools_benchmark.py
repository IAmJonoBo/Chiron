from __future__ import annotations

from typer.testing import CliRunner

from chiron.typer_cli import app


def test_tools_benchmark_cli_json(monkeypatch):
    runner = CliRunner()

    class DummySuite:
        def __init__(self) -> None:
            self._cases = []

        def cases(self):  # pragma: no cover - executed in CLI
            return self._cases

        def summary(self):
            return {
                "results": [
                    {
                        "name": "dummy",
                        "iterations": 1,
                        "total_time": 0.01,
                        "avg_time": 0.01,
                        "min_time": 0.01,
                        "max_time": 0.01,
                        "throughput": 100.0,
                        "metadata": {},
                    }
                ],
                "aggregate": {"total_time": 0.01, "cases": 1},
            }

    def fake_default_suite():
        return DummySuite()

    monkeypatch.setattr("chiron.benchmark.default_suite", fake_default_suite)

    result = runner.invoke(app, ["tools", "benchmark", "--json", "--iterations", "1", "--warmup", "0"])
    assert result.exit_code == 0
    assert "\"dummy\"" in result.stdout
