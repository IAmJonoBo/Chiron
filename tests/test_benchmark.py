from __future__ import annotations

from collections import deque

import pytest

from chiron.benchmark import BenchmarkCase, BenchmarkResult, BenchmarkSuite


def test_benchmark_case_runs_with_warmup() -> None:
    counter = {"calls": 0}

    def action() -> None:
        counter["calls"] += 1

    clock_values = deque([0.0, 0.01, 0.02, 0.05])

    def clock() -> float:
        value = clock_values.popleft()
        clock_values.append(value)
        return value

    case = BenchmarkCase(name="test", action=action, iterations=2, warmup=1)
    result = case.run(clock)

    assert counter["calls"] == 3  # warmup + 2 iterations
    assert isinstance(result, BenchmarkResult)
    assert result.iterations == 2
    assert pytest.approx(result.total_time, rel=1e-6) == 0.04


def test_benchmark_suite_summary_returns_serialisable_results() -> None:
    suite = BenchmarkSuite(clock=lambda: 0.0)

    def action() -> None:
        pass

    suite.register(BenchmarkCase(name="noop", action=action, iterations=1))
    summary = suite.summary()

    assert summary["aggregate"]["cases"] == 1
    assert summary["results"][0]["name"] == "noop"
    assert summary["results"][0]["throughput"] == pytest.approx(0.0)
