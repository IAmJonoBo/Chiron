"""Developer productivity helpers for running quality gates and analysing coverage."""

from __future__ import annotations

import importlib
import json
import subprocess
import textwrap
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Literal, cast, get_args

from defusedxml import ElementTree as ET  # type: ignore[import-untyped]

tomllib: ModuleType

try:
    import tomllib as _tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback for tests
    tomllib = importlib.import_module("tomli")
else:
    tomllib = _tomllib


class DevToolCommandError(RuntimeError):
    """Raised when an invoked developer tooling command fails."""

    def __init__(self, command: Sequence[str], returncode: int, output: str) -> None:
        super().__init__(
            f"Command {' '.join(command)} failed with exit code {returncode}:\n{output.strip()}"
        )
        self.command = tuple(command)
        self.returncode = returncode
        self.output = output


@dataclass(slots=True)
class CommandResult:
    """Stores the outcome of an executed command."""

    command: tuple[str, ...]
    returncode: int
    duration: float
    output: str
    gate: str | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "command": list(self.command),
            "returncode": self.returncode,
            "duration": self.duration,
            "output": self.output,
            "gate": self.gate,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_payload())


def run_command(
    command: Sequence[str],
    *,
    check: bool = True,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    gate: str | None = None,
) -> CommandResult:
    """Run a command returning its :class:`CommandResult`.

    ``check`` mirrors ``subprocess.run`` semantics: raise :class:`DevToolCommandError`
    if the command fails. ``cwd`` allows running the command from a different
    working directory.
    """

    start = time.perf_counter()
    completed = subprocess.run(
        command,
        check=False,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        env=dict(env) if env is not None else None,
    )
    duration = time.perf_counter() - start
    output = (completed.stdout or "") + (completed.stderr or "")
    result = CommandResult(tuple(command), completed.returncode, duration, output, gate=gate)
    if check and completed.returncode != 0:
        raise DevToolCommandError(command, completed.returncode, output)
    return result


@dataclass(slots=True)
class ModuleCoverage:
    """Coverage information for a module extracted from ``coverage.xml``."""

    name: str
    statements: int
    missing: int
    coverage: float
    missing_lines: tuple[int, ...]

    def format_missing_lines(self, limit: int | None = None) -> str:
        lines = self.missing_lines
        if limit is not None:
            lines = lines[:limit]
            suffix = " ..." if len(self.missing_lines) > limit else ""
        else:
            suffix = ""
        formatted = ", ".join(str(line) for line in lines) or "(none)"
        return formatted + suffix


class CoverageReport:
    """Utility wrapper around a ``coverage.xml`` report."""

    def __init__(self, modules: list[ModuleCoverage], summary: CoverageSummary) -> None:
        self._modules = modules
        self._module_index = {module.name: module for module in modules}
        self._summary = summary

    @classmethod
    def from_xml(cls, path: Path) -> CoverageReport:
        if not path.exists():
            raise FileNotFoundError(f"Coverage report not found: {path}")
        tree = ET.parse(path)
        modules: list[ModuleCoverage] = []
        statements_total = 0
        missing_total = 0
        for package in tree.findall(".//package"):
            for clazz in package.findall("class"):
                filename = clazz.get("filename")
                if not filename:
                    continue
                statements = int(clazz.get("statements", "0"))
                missing = int(clazz.get("missing", "0"))
                coverage_attr = clazz.get("line-rate") or package.get("line-rate")
                coverage = float(coverage_attr) * 100 if coverage_attr else 0.0
                lines = [
                    int(line.get("number"))
                    for line in clazz.findall("lines/line")
                    if int(line.get("hits", "0")) == 0
                ]
                statements_total += statements
                missing_total += missing
                modules.append(
                    ModuleCoverage(
                        name=filename,
                        statements=statements,
                        missing=missing,
                        coverage=coverage,
                        missing_lines=tuple(sorted(lines)),
                    )
                )
        modules.sort(key=lambda module: module.coverage)
        root = tree.getroot()
        coverage_attr = root.get("line-rate")
        if coverage_attr is not None:
            overall = float(coverage_attr) * 100
        else:
            overall = (1 - (missing_total / statements_total)) * 100 if statements_total else 0.0
        summary = CoverageSummary(
            total_statements=statements_total,
            total_missing=missing_total,
            coverage=overall,
        )
        return cls(modules, summary)

    def modules_below(self, threshold: float, *, limit: int | None = None) -> list[ModuleCoverage]:
        below = [module for module in self._modules if module.coverage < threshold]
        if limit is not None:
            return below[:limit]
        return below

    def get(self, name: str) -> ModuleCoverage | None:
        return self._module_index.get(name)

    def best(self, limit: int = 5) -> list[ModuleCoverage]:
        return sorted(self._modules, key=lambda module: module.coverage, reverse=True)[:limit]

    def worst(self, limit: int = 5) -> list[ModuleCoverage]:
        return self.modules_below(100.0, limit=limit)

    @property
    def summary(self) -> CoverageSummary:
        return self._summary

    def by_missing(self, *, min_statements: int = 0) -> list[ModuleCoverage]:
        modules = [
            module
            for module in self._modules
            if module.missing > 0 and module.statements >= min_statements
        ]
        modules.sort(key=lambda module: module.missing, reverse=True)
        return modules

    def all_modules(self) -> list[ModuleCoverage]:
        return list(self._modules)


@dataclass(slots=True)
class CoverageSummary:
    """Aggregate view of overall coverage."""

    total_statements: int
    total_missing: int
    coverage: float

    @property
    def covered(self) -> int:
        return self.total_statements - self.total_missing


QualityCategory = Literal[
    "tests",
    "lint",
    "types",
    "security",
    "build",
    "docs",
    "format",
    "other",
]


@dataclass(slots=True)
class QualityGate:
    """Metadata describing a reusable quality gate command."""

    name: str
    command: tuple[str, ...]
    description: str
    category: QualityCategory = "other"
    critical: bool = True
    working_directory: Path | None = None
    env: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if self.env is not None and not isinstance(self.env, dict):
            object.__setattr__(self, "env", dict(self.env))


@dataclass(slots=True)
class QualityConfiguration:
    """Profiles and gate overrides loaded from project configuration."""

    gates: dict[str, QualityGate]
    profiles: dict[str, tuple[str, ...]]


DEFAULT_QUALITY_GATES: dict[str, QualityGate] = {
    "tests": QualityGate(
        name="tests",
        description="Run pytest suite with coverage",
        category="tests",
        command=(
            "uv",
            "run",
            "--extra",
            "dev",
            "--extra",
            "test",
            "pytest",
            "--cov=src/chiron",
            "--cov-report=term",
        ),
    ),
    "lint": QualityGate(
        name="lint",
        description="Run Ruff lint checks",
        category="lint",
        command=("uv", "run", "--extra", "dev", "ruff", "check"),
    ),
    "types": QualityGate(
        name="types",
        description="Run mypy type checks",
        category="types",
        command=("uv", "run", "--extra", "dev", "mypy", "src"),
    ),
    "security": QualityGate(
        name="security",
        description="Run Bandit security scan",
        category="security",
        command=("uv", "run", "--extra", "security", "bandit", "-r", "src", "-lll"),
    ),
    "build": QualityGate(
        name="build",
        description="Build wheel and source distribution",
        category="build",
        command=("uv", "build"),
    ),
}


DEFAULT_QUALITY_PROFILES: dict[str, tuple[str, ...]] = {
    "full": ("tests", "lint", "types", "security", "build"),
    "fast": ("tests", "lint"),
    "verify": ("tests", "lint", "types"),
    "package": ("build",),
}


def load_quality_configuration(root: Path | None = None) -> QualityConfiguration:
    """Load optional quality gate overrides from ``pyproject.toml``."""

    base = root or Path.cwd()
    pyproject = base / "pyproject.toml"
    if not pyproject.exists():
        return QualityConfiguration(gates={}, profiles={})
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)
    config = (
        data.get("tool", {})
        .get("chiron", {})
        .get("dev_toolbox", {})
    )
    gates_config = config.get("gates", {}) if isinstance(config, dict) else {}
    profiles_config = config.get("profiles", {}) if isinstance(config, dict) else {}
    gates: dict[str, QualityGate] = {}
    for name, payload in gates_config.items():
        if not isinstance(payload, dict):
            continue
        command = payload.get("command")
        if not isinstance(command, list) or not all(isinstance(entry, str) for entry in command):
            continue
        category = payload.get("category", "other")
        description = payload.get("description", name)
        critical = bool(payload.get("critical", True))
        cwd_value = payload.get("cwd")
        working_directory = (
            (base / cwd_value)
            if isinstance(cwd_value, str)
            else None
        )
        env_payload = payload.get("env", {})
        env = (
            {key: str(value) for key, value in env_payload.items()}
            if isinstance(env_payload, dict)
            else None
        )
        category_literal = (
            category if isinstance(category, str) and category in get_args(QualityCategory) else "other"
        )
        gates[name] = QualityGate(
            name=name,
            command=tuple(command),
            description=description,
            category=cast(QualityCategory, category_literal),
            critical=critical,
            working_directory=working_directory,
            env=env,
        )
    profiles: dict[str, tuple[str, ...]] = {}
    for name, payload in profiles_config.items():
        gates_list = payload.get("gates") if isinstance(payload, dict) else None
        if isinstance(gates_list, list) and all(isinstance(entry, str) for entry in gates_list):
            profiles[name] = tuple(gates_list)
    return QualityConfiguration(gates=gates, profiles=profiles)


def _merge_gate_catalog(config: QualityConfiguration | None) -> dict[str, QualityGate]:
    merged = dict(DEFAULT_QUALITY_GATES)
    if config:
        merged.update(config.gates)
    return merged


def _merge_profiles(config: QualityConfiguration | None) -> dict[str, tuple[str, ...]]:
    merged = dict(DEFAULT_QUALITY_PROFILES)
    if config:
        merged.update(config.profiles)
    return merged


def available_quality_profiles(
    config: QualityConfiguration | None = None,
) -> dict[str, tuple[str, ...]]:
    """Return the merged set of quality profiles."""

    return _merge_profiles(config)


def available_quality_gates(
    config: QualityConfiguration | None = None,
) -> dict[str, QualityGate]:
    """Return the merged catalog of quality gates."""

    return _merge_gate_catalog(config)


def resolve_quality_profile(
    profile: str,
    *,
    config: QualityConfiguration | None = None,
) -> list[QualityGate]:
    """Resolve a profile name to concrete quality gates."""

    profiles = _merge_profiles(config)
    if profile not in profiles:
        available = ", ".join(sorted(profiles))
        raise KeyError(f"Unknown quality profile '{profile}'. Available: {available}")
    catalog = _merge_gate_catalog(config)
    gates: list[QualityGate] = []
    for gate_name in profiles[profile]:
        gate = catalog.get(gate_name)
        if gate is not None:
            gates.append(gate)
    return gates


def format_command_result(result: CommandResult) -> str:
    status = "✅" if result.returncode == 0 else "❌"
    command_display = " ".join(result.command)
    duration = f"{result.duration:.2f}s"
    return f"{status} {command_display} ({duration})"


def run_quality_suite(
    commands: Iterable[Sequence[str] | QualityGate], *, halt_on_failure: bool = True
) -> list[CommandResult]:
    """Run a series of commands returning their results."""

    results: list[CommandResult] = []
    for command in commands:
        if isinstance(command, QualityGate):
            result = run_command(
                command.command,
                check=False,
                cwd=command.working_directory,
                env=command.env,
                gate=command.name,
            )
        else:
            result = run_command(command, check=False)
        results.append(result)
        if halt_on_failure and result.returncode != 0:
            break
    return results


def summarise_suite(results: Sequence[CommandResult]) -> str:
    summary_lines = []
    for result in results:
        line = format_command_result(result)
        if result.gate:
            line = f"{line} ← {result.gate}"
        summary_lines.append(line)
    summary = summary_lines
    return "\n".join(summary)


def coverage_hotspots(report: CoverageReport, *, threshold: float, limit: int) -> str:
    modules = report.modules_below(threshold, limit=limit)
    if not modules:
        return "All modules meet the coverage threshold."
    lines = [
        f"{module.name}: {module.coverage:.2f}% ({module.missing} missing of {module.statements})"
        for module in modules
    ]
    return "\n".join(lines)


def coverage_focus(report: CoverageReport, module_name: str, *, line_limit: int | None = None) -> str:
    module = report.get(module_name)
    if not module:
        available = "\n".join(module.name for module in report.worst(limit=10))
        message = textwrap.dedent(
            f"""Module '{module_name}' not found in coverage report.
            Available modules include:
            {available}
            """
        ).strip()
        return message
    header = f"{module.name}: {module.coverage:.2f}% (missing {module.missing} lines)"
    missing = module.format_missing_lines(limit=line_limit)
    return header + "\nMissing lines: " + missing


def coverage_gap_summary(
    report: CoverageReport,
    *,
    min_statements: int = 0,
    limit: int = 5,
) -> str:
    """Highlight modules with the highest absolute number of missing lines."""

    modules = report.by_missing(min_statements=min_statements)
    if not modules:
        return "No gaps detected beyond the specified filters."
    lines = [
        f"{module.name}: {module.missing} missing / {module.statements} statements"
        for module in modules[:limit]
    ]
    return "\n".join(lines)


def coverage_guard(
    report: CoverageReport,
    *,
    threshold: float,
    limit: int = 5,
) -> tuple[bool, str]:
    """Assess whether overall coverage satisfies the required threshold."""

    summary = report.summary
    coverage_value = summary.coverage
    if coverage_value >= threshold:
        message = (
            f"✅ Coverage {coverage_value:.2f}% meets threshold {threshold:.2f}%"
            f" ({summary.covered}/{summary.total_statements} lines)"
        )
        return True, message
    hotspots = coverage_hotspots(report, threshold=threshold, limit=limit)
    if hotspots.strip() == "All modules meet the coverage threshold.":
        hotspot_section = "  (no hotspot modules identified)"
    else:
        hotspot_section = textwrap.indent(hotspots, prefix="  • ")
    message = textwrap.dedent(
        f"""
        ❌ Coverage {coverage_value:.2f}% is below the required {threshold:.2f}%.
        Missing lines: {summary.total_missing} (covered {summary.covered} of {summary.total_statements}).
        Hotspots:
{hotspot_section}
        """
    ).strip()
    return False, message


__all__ = [
    "CommandResult",
    "CoverageSummary",
    "CoverageReport",
    "DevToolCommandError",
    "ModuleCoverage",
    "QualityConfiguration",
    "QualityGate",
    "available_quality_gates",
    "available_quality_profiles",
    "coverage_gap_summary",
    "coverage_focus",
    "coverage_hotspots",
    "coverage_guard",
    "format_command_result",
    "load_quality_configuration",
    "run_command",
    "run_quality_suite",
    "resolve_quality_profile",
    "summarise_suite",
]
