"""Lightweight benchmarking utilities for Chiron."""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

BenchmarkCallable = Callable[[], Any]


@dataclass(slots=True)
class BenchmarkCase:
    """A single benchmarkable action."""

    name: str
    action: BenchmarkCallable
    iterations: int = 100
    warmup: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def run(self, clock: Callable[[], float]) -> BenchmarkResult:
        """Execute the benchmark case and collect timing statistics."""

        for _ in range(self.warmup):
            self.action()

        samples: list[float] = []
        for _ in range(self.iterations):
            start = clock()
            self.action()
            end = clock()
            samples.append(end - start)

        return BenchmarkResult.from_samples(
            name=self.name,
            samples=samples,
            metadata=self.metadata,
        )


@dataclass(slots=True)
class BenchmarkResult:
    """Benchmark metrics for a single case."""

    name: str
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    iterations: int
    metadata: dict[str, Any] = field(default_factory=dict)

    throughput: float = field(init=False)

    def __post_init__(self) -> None:
        self.throughput = 0.0 if self.total_time == 0 else self.iterations / self.total_time

    @classmethod
    def from_samples(
        cls, *, name: str, samples: Sequence[float], metadata: dict[str, Any]
    ) -> BenchmarkResult:
        if not samples:
            raise ValueError("Benchmark samples cannot be empty")
        total = sum(samples)
        return cls(
            name=name,
            total_time=total,
            avg_time=statistics.fmean(samples),
            min_time=min(samples),
            max_time=max(samples),
            iterations=len(samples),
            metadata=metadata,
        )


class BenchmarkSuite:
    """Collection of benchmark cases."""

    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._cases: list[BenchmarkCase] = []
        self._clock = clock or time.perf_counter

    def register(self, case: BenchmarkCase) -> None:
        """Register a new benchmark case."""
        self._cases.append(case)

    def extend(self, cases: Iterable[BenchmarkCase]) -> None:
        for case in cases:
            self.register(case)

    def cases(self) -> Sequence[BenchmarkCase]:
        """Return registered cases."""
        return tuple(self._cases)

    def run(self) -> list[BenchmarkResult]:
        """Execute all registered benchmarks."""
        return [case.run(self._clock) for case in self._cases]

    def summary(self) -> dict[str, Any]:
        """Produce a serialisable summary of benchmark results."""
        results = self.run()
        return {
            "results": [
                {
                    "name": result.name,
                    "iterations": result.iterations,
                    "total_time": result.total_time,
                    "avg_time": result.avg_time,
                    "min_time": result.min_time,
                    "max_time": result.max_time,
                    "throughput": result.throughput,
                    "metadata": result.metadata,
                }
                for result in results
            ],
            "aggregate": {
                "total_time": sum(result.total_time for result in results),
                "cases": len(results),
            },
        }


def default_suite() -> BenchmarkSuite:
    """Create the default Chiron benchmark suite."""

    suite = BenchmarkSuite()

    from chiron.core import ChironCore

    core = ChironCore({"service_name": "benchmark"})

    suite.extend(
        [
            BenchmarkCase(
                name="core.process_data",
                action=lambda: core.process_data({"payload": "value"}),
                iterations=50,
                warmup=5,
                metadata={"module": "core"},
            ),
            BenchmarkCase(
                name="core.health_check",
                action=core.health_check,
                iterations=50,
                warmup=5,
                metadata={"module": "core"},
            ),
        ]
    )

    return suite


__all__ = [
    "BenchmarkCase",
    "BenchmarkResult",
    "BenchmarkSuite",
    "default_suite",
]
