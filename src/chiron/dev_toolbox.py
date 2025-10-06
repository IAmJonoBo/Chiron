"""Developer productivity helpers for running quality gates and analysing coverage."""

from __future__ import annotations

import ast
import importlib
import json
import re
import subprocess
import textwrap
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Literal, cast, get_args

import yaml  # type: ignore[import-untyped]
from defusedxml import ElementTree as ET  # type: ignore[import-untyped]

from chiron.planning import ExecutionPlanStep, render_execution_plan

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


@dataclass(frozen=True, slots=True)
class QualitySuiteProgressEvent:
    """Progress update emitted while executing quality-suite gates."""

    index: int
    total: int
    command: tuple[str, ...]
    gate: QualityGate | None
    status: Literal["started", "completed"]
    result: CommandResult | None = None

    @property
    def name(self) -> str:
        if self.gate is not None:
            return self.gate.name
        return self.command[0] if self.command else "<unknown>"

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
            class_nodes = package.findall("classes/class") or package.findall("class")
            for clazz in class_nodes:
                filename = clazz.get("filename")
                if not filename:
                    continue
                line_elements = list(clazz.findall("lines/line"))
                statements_attr = clazz.get("statements")
                statements = (
                    int(statements_attr)
                    if statements_attr is not None
                    else len(line_elements)
                )
                missing_attr = clazz.get("missing")
                lines = [
                    int(line.get("number"))
                    for line in line_elements
                    if int(line.get("hits", "0")) == 0
                ]
                missing = int(missing_attr) if missing_attr is not None else len(lines)
                coverage_attr = clazz.get("line-rate") or package.get("line-rate")
                coverage = float(coverage_attr) * 100 if coverage_attr else 0.0
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


@dataclass(frozen=True, slots=True)
class QualitySuitePlan:
    """Describe a resolved quality-suite run including execution plan metadata."""

    profile: str
    gates: tuple[QualityGate, ...]
    toggles: tuple[tuple[str, bool], ...] = ()

    @property
    def execution_plan(self) -> tuple[ExecutionPlanStep, ...]:
        """Return execution-plan steps for the resolved quality gates."""

        return tuple(
            ExecutionPlanStep(
                key=gate.name,
                description=gate.description,
                command=gate.command,
            )
            for gate in self.gates
        )

    @property
    def insights(self) -> QualitySuiteInsights:
        """Return aggregated insights about the planned quality suite."""

        return build_quality_suite_insights(self)

    def render_lines(self) -> list[str]:
        """Return numbered, human-readable execution lines."""

        return render_execution_plan(self.execution_plan)

    def gate_names(self) -> tuple[str, ...]:
        """Return the names of gates in plan order."""

        return tuple(gate.name for gate in self.gates)

    def to_payload(self) -> dict[str, object]:
        """Return a JSON-serialisable payload describing the plan."""

        insights_payload = self.insights.to_payload()
        return {
            "profile": self.profile,
            "gates": [
                {
                    "name": gate.name,
                    "description": gate.description,
                    "category": gate.category,
                    "command": list(gate.command),
                    "critical": gate.critical,
                    "working_directory": (
                        str(gate.working_directory) if gate.working_directory else None
                    ),
                    "env": dict(gate.env) if gate.env else None,
                }
                for gate in self.gates
            ],
            "toggles": [
                {"identifier": identifier, "enabled": enabled}
                for identifier, enabled in self.toggles
            ],
            "plan": [
                {
                    "key": step.key,
                    "description": step.description,
                    "command": list(step.command) if step.command else None,
                }
                for step in self.execution_plan
            ],
            "insights": insights_payload,
        }


@dataclass(frozen=True, slots=True)
class QualitySuiteInsights:
    """Aggregated metadata describing a quality-suite plan."""

    profile: str
    total_gates: int
    category_breakdown: tuple[tuple[QualityCategory, int], ...]
    critical_gates: tuple[str, ...]
    optional_gates: tuple[str, ...]
    toggles: tuple[tuple[str, bool], ...]
    disabled_toggles: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "total_gates": self.total_gates,
            "category_breakdown": [
                {"category": category, "count": count}
                for category, count in self.category_breakdown
            ],
            "critical_gates": list(self.critical_gates),
            "optional_gates": list(self.optional_gates),
            "toggles": [
                {"identifier": identifier, "enabled": enabled}
                for identifier, enabled in self.toggles
            ],
            "disabled_toggles": list(self.disabled_toggles),
        }

    def render_lines(self) -> list[str]:
        lines = [
            f"Profile: {self.profile}",
            f"Total gates: {self.total_gates}",
        ]
        if self.category_breakdown:
            lines.append("Category breakdown:")
            lines.extend(
                f"  • {category}: {count}"
                for category, count in self.category_breakdown
            )
        if self.critical_gates:
            lines.append(
                "Critical gates: " + ", ".join(self.critical_gates)
            )
        if self.optional_gates:
            lines.append(
                "Optional gates: " + ", ".join(self.optional_gates)
            )
        if self.toggles:
            toggle_display = ", ".join(
                f"{identifier}={'on' if enabled else 'off'}"
                for identifier, enabled in self.toggles
            )
            lines.append(f"Toggles: {toggle_display}")
        if self.disabled_toggles:
            lines.append(
                "Disabled toggles: " + ", ".join(self.disabled_toggles)
            )
        if len(lines) == 2:  # only header lines populated
            lines.append("No additional insights available.")
        return lines


@dataclass(frozen=True, slots=True)
class QualitySuiteRecommendation:
    """Actionable recommendation derived from coverage monitoring."""

    focus: str
    module: str
    missing: int
    coverage: float
    severity: Literal["improve", "monitor"]
    missing_lines: tuple[int, ...]
    action: str

    def to_payload(self) -> dict[str, object]:
        return {
            "focus": self.focus,
            "module": self.module,
            "missing": self.missing,
            "coverage": self.coverage,
            "severity": self.severity,
            "missing_lines": list(self.missing_lines),
            "action": self.action,
        }

    def render_line(self) -> str:
        icon = "🚨" if self.severity == "improve" else "👀"
        preview = ", ".join(str(line) for line in self.missing_lines[:5]) or "(none)"
        return (
            f"{icon} {self.focus}: {self.module} — {self.coverage:.1f}% coverage, "
            f"{self.missing} missing lines (key lines: {preview}). {self.action}"
        )


@dataclass(frozen=True, slots=True)
class CoverageFocusSummary:
    """Summarise coverage hotspots for a specific focus area."""

    area: str
    modules: tuple[str, ...]
    total_missing: int
    average_coverage: float
    threshold: float

    def to_payload(self) -> dict[str, object]:
        return {
            "area": self.area,
            "modules": list(self.modules),
            "total_missing": self.total_missing,
            "average_coverage": self.average_coverage,
            "threshold": self.threshold,
        }

    def render_lines(self) -> list[str]:
        header = (
            f"{self.area}: avg {self.average_coverage:.2f}%"
            f" (threshold {self.threshold:.2f}%)"
        )
        if not self.modules:
            return [header + " — no modules flagged"]
        lines = [header]
        lines.extend(f"  • {module}" for module in self.modules)
        lines.append(f"  Missing lines: {self.total_missing}")
        return lines


@dataclass(frozen=True, slots=True)
class QualitySuiteMonitoring:
    """Machine-readable monitoring metadata for quality-suite runs."""

    coverage_focus: tuple[CoverageFocusSummary, ...]
    recommendations: tuple[str, ...]
    recommendation_details: tuple[QualitySuiteRecommendation, ...] = ()
    source: str | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "coverage_focus": [focus.to_payload() for focus in self.coverage_focus],
            "recommendations": list(self.recommendations),
            "recommendation_details": [
                detail.to_payload() for detail in self.recommendation_details
            ],
            "source": self.source,
        }

    def render_lines(self) -> list[str]:
        lines: list[str] = []
        for focus in self.coverage_focus:
            lines.extend(focus.render_lines())
        if self.recommendation_details:
            lines.append("")
            lines.append("Recommendations:")
            lines.extend(
                f"  • {detail.render_line()}" for detail in self.recommendation_details
            )
        elif self.recommendations:
            lines.append("")
            lines.append("Recommendations:")
            lines.extend(f"  • {rec}" for rec in self.recommendations)
        return lines


@dataclass(frozen=True, slots=True)
class QualitySuiteDryRun:
    """Snapshot describing a dry-run of the quality-suite tooling."""

    plan: QualitySuitePlan
    insights: QualitySuiteInsights
    monitoring: QualitySuiteMonitoring | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def guide(self) -> tuple[str, ...]:
        """Return the agent-facing guide for the resolved plan."""

        return tuple(
            quality_suite_guide(
                self.plan,
                insights=self.insights,
                monitoring=self.monitoring,
            )
        )

    @property
    def actions(self) -> tuple[str, ...]:
        """Return actionable follow-ups derived from monitoring insights."""

        if self.monitoring is None:
            return ()
        if self.monitoring.recommendation_details:
            return tuple(
                detail.action for detail in self.monitoring.recommendation_details
            )
        return self.monitoring.recommendations

    def to_payload(self) -> dict[str, object]:
        """Serialise the dry-run snapshot for downstream consumers."""

        payload: dict[str, object] = {
            "generated_at": self.generated_at.isoformat(),
            "plan": self.plan.to_payload(),
            "insights": self.insights.to_payload(),
            "guide": list(self.guide),
            "actions": list(self.actions),
        }
        if self.monitoring is not None:
            payload["monitoring"] = self.monitoring.to_payload()
        return payload

    def render_lines(self) -> list[str]:
        """Render a readable dry-run summary."""

        lines = list(self.guide)
        if self.actions:
            lines.append("")
            lines.append("Recommended actions:")
            lines.extend(f"  • {action}" for action in self.actions)
        return lines

    def render_documentation_lines(self) -> tuple[str, ...]:
        """Return Markdown describing the resolved quality suite."""

        lines: list[str] = [
            "### Developer Toolbox Quality Suite Snapshot",
            "",
            "Use the developer toolbox to keep local quality gates aligned with CI.",
            "",
            f"**Primary profile**: `{self.plan.profile}` ({len(self.plan.gates)} gates)",
            f"**Generated**: {self.generated_at.isoformat()}",
            "",
            "| Order | Gate | Category | Critical | Command |",
            "| --- | --- | --- | --- | --- |",
        ]
        for index, gate in enumerate(self.plan.gates, start=1):
            command = " ".join(gate.command)
            critical_label = "Required" if gate.critical else "Optional"
            lines.append(
                "| "
                f"{index} | `{gate.name}` | {gate.category} | {critical_label} | `"
                f"{command}` |"
            )

        lines.append("")
        if self.plan.toggles:
            toggle_summary = ", ".join(
                f"{identifier}={'on' if enabled else 'off'}"
                for identifier, enabled in self.plan.toggles
            )
            lines.append(f"**Applied toggles**: {toggle_summary}")
        else:
            lines.append("**Applied toggles**: _None_")

        if self.actions:
            lines.append("")
            lines.append("**Recommended follow-ups**:")
            lines.extend(f"- {action}" for action in self.actions)

        if self.monitoring is not None and self.monitoring.source:
            lines.append("")
            lines.append(f"**Monitoring source**: {self.monitoring.source}")

        lines.append("")
        lines.append(
            "_Updated automatically via `chiron tools qa --sync-docs docs/QUALITY_GATES.md`._"
        )
        return tuple(lines)


class DocumentationSyncError(RuntimeError):
    """Raised when documentation blocks cannot be updated automatically."""


@dataclass(frozen=True, slots=True)
class DiataxisEntry:
    """A documentation entry grouped by Diataxis category."""

    title: str
    path: str
    summary: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> DiataxisEntry:
        try:
            title = str(data["title"]).strip()
            path = str(data["path"]).strip()
            summary = str(data["summary"]).strip()
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise DocumentationSyncError(
                f"Diataxis entry is missing required key: {exc}"
            ) from exc

        if not title or not path or not summary:
            raise DocumentationSyncError(
                f"Diataxis entry must include non-empty title, path, and summary: {data}"
            )

        return cls(title=title, path=path, summary=summary)

    def to_mapping(self) -> dict[str, str]:
        return {"title": self.title, "path": self.path, "summary": self.summary}


DIATAXIS_CATEGORY_LABELS: dict[str, str] = {
    "tutorials": "Tutorials",
    "how_to": "How-to Guides",
    "reference": "Reference",
    "explanation": "Explanation",
}


def load_diataxis_entries(path: Path) -> dict[str, tuple[DiataxisEntry, ...]]:
    """Load Diataxis documentation entries from *path*."""

    if not path.exists():
        raise DocumentationSyncError(f"Diataxis configuration not found: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
        raise DocumentationSyncError(f"Invalid Diataxis configuration JSON: {exc}") from exc

    entries: dict[str, list[DiataxisEntry]] = {}
    for category, items in payload.items():
        if category not in DIATAXIS_CATEGORY_LABELS:
            raise DocumentationSyncError(
                f"Unsupported Diataxis category '{category}'. Expected one of: "
                f"{', '.join(sorted(DIATAXIS_CATEGORY_LABELS))}."
            )
        if not isinstance(items, list):
            raise DocumentationSyncError(
                f"Diataxis category '{category}' must be a list of entries."
            )
        bucket: list[DiataxisEntry] = []
        for item in items:
            if not isinstance(item, Mapping):
                raise DocumentationSyncError(
                    f"Each Diataxis entry must be a mapping, got: {item!r}"
                )
            bucket.append(DiataxisEntry.from_mapping(item))
        entries[category] = bucket

    for category in DIATAXIS_CATEGORY_LABELS:
        entries.setdefault(category, [])

    return {category: tuple(items) for category, items in entries.items()}


def dump_diataxis_entries(
    path: Path, entries: Mapping[str, Sequence[DiataxisEntry]]
) -> Path:
    """Persist *entries* to *path* as JSON."""

    serializable: dict[str, list[dict[str, str]]] = {}
    for category in DIATAXIS_CATEGORY_LABELS:
        bucket = [entry.to_mapping() for entry in entries.get(category, ())]
        serializable[category] = bucket

    path.write_text(json.dumps(serializable, indent=2) + "\n", encoding="utf-8")
    return path


FRONT_MATTER_DELIMITER = "---"


def _extract_front_matter(
    path: Path,
) -> tuple[dict[str, object], tuple[str, ...]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONT_MATTER_DELIMITER:
        return {}, tuple(lines)

    for index in range(1, len(lines)):
        if lines[index].strip() == FRONT_MATTER_DELIMITER:
            block = "\n".join(lines[1:index])
            try:
                loaded = yaml.safe_load(block) or {}
            except yaml.YAMLError as exc:  # pragma: no cover - defensive guard
                raise DocumentationSyncError(
                    f"Invalid YAML front matter in {path}: {exc}"
                ) from exc
            if not isinstance(loaded, Mapping):
                raise DocumentationSyncError(
                    f"Front matter in {path} must be a mapping, got {type(loaded).__name__}"
                )
            data = {str(key): value for key, value in loaded.items()}
            remainder = tuple(lines[index + 1 :])
            return data, remainder

    raise DocumentationSyncError(
        f"Front matter in {path} is not terminated by '{FRONT_MATTER_DELIMITER}'"
    )


def _extract_first_heading(lines: Sequence[str]) -> str | None:
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return None


def discover_diataxis_entries(docs_dir: Path) -> dict[str, tuple[DiataxisEntry, ...]]:
    """Discover Diataxis entries from Markdown front matter under *docs_dir*."""

    if not docs_dir.exists():
        raise DocumentationSyncError(f"Documentation directory not found: {docs_dir}")

    entries: dict[str, list[DiataxisEntry]] = {
        category: [] for category in DIATAXIS_CATEGORY_LABELS
    }

    markdown_files = sorted(docs_dir.rglob("*.md"))
    for path in markdown_files:
        if path.name == "index.md":
            continue

        metadata, remainder = _extract_front_matter(path)
        if not metadata:
            continue

        try:
            category = str(metadata["diataxis"]).strip()
        except KeyError:
            continue

        if category not in DIATAXIS_CATEGORY_LABELS:
            raise DocumentationSyncError(
                f"Unsupported diataxis category '{category}' in {path}"
            )

        title_value = str(metadata.get("title", "")).strip()
        if not title_value:
            heading = _extract_first_heading(remainder)
            if heading:
                title_value = heading
        if not title_value:
            raise DocumentationSyncError(
                f"Unable to determine title for {path}. Provide a 'title' front matter field or first-level heading."
            )

        summary = str(metadata.get("summary", "")).strip()
        if not summary:
            raise DocumentationSyncError(
                f"Documentation summary missing for {path}. Populate the 'summary' front matter field."
            )

        rel_path = path.relative_to(docs_dir).as_posix()
        entries[category].append(
            DiataxisEntry(title=title_value, path=rel_path, summary=summary)
        )

    return {
        category: tuple(
            sorted(bucket, key=lambda entry: entry.title.casefold())
        )
        for category, bucket in entries.items()
    }


def render_diataxis_overview(
    entries: Mapping[str, Sequence[DiataxisEntry]]
) -> tuple[str, ...]:
    """Render Markdown lines for the provided Diataxis *entries*."""

    lines: list[str] = []
    for category_key in DIATAXIS_CATEGORY_LABELS:
        label = DIATAXIS_CATEGORY_LABELS[category_key]
        lines.append(f"### {label}")
        lines.append("")
        category_entries = entries.get(category_key, ())
        if category_entries:
            for entry in category_entries:
                lines.append(
                    f"- [{entry.title}]({entry.path}) — {entry.summary}"
                )
        else:
            lines.append("_No entries yet._")
        lines.append("")

    lines.append(
        "_Updated automatically via `chiron tools docs sync-diataxis --discover`._"
    )
    return tuple(lines)


def sync_quality_suite_documentation(
    snapshot: QualitySuiteDryRun,
    path: Path,
    *,
    marker: str = "QUALITY_SUITE_AUTODOC",
) -> Path:
    """Synchronise the quality suite documentation block at *path*."""

    if not path.exists():
        raise DocumentationSyncError(f"Documentation file not found: {path}")

    begin = f"<!-- BEGIN {marker} -->"
    end = f"<!-- END {marker} -->"
    contents = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"({re.escape(begin)})(.*?)[\r\n]+({re.escape(end)})",
        re.DOTALL,
    )
    if not pattern.search(contents):
        raise DocumentationSyncError(
            f"Documentation markers '{begin}'/'{end}' not found in {path}"
        )

    block = "\n".join(snapshot.render_documentation_lines())
    replacement = f"{begin}\n{block}\n{end}"
    updated = pattern.sub(replacement, contents, count=1)
    path.write_text(updated, encoding="utf-8")
    return path


def sync_diataxis_documentation(
    config_path: Path,
    doc_path: Path,
    *,
    marker: str = "DIATAXIS_AUTODOC",
    entries: Mapping[str, Sequence[DiataxisEntry]] | None = None,
) -> Path:
    """Synchronise the Diataxis documentation block using *config_path*."""

    resolved_entries = entries or load_diataxis_entries(config_path)
    lines = render_diataxis_overview(resolved_entries)

    if not doc_path.exists():
        raise DocumentationSyncError(f"Documentation file not found: {doc_path}")

    begin = f"<!-- BEGIN {marker} -->"
    end = f"<!-- END {marker} -->"
    contents = doc_path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"({re.escape(begin)})(.*?)[\r\n]+({re.escape(end)})",
        re.DOTALL,
    )
    if not pattern.search(contents):
        raise DocumentationSyncError(
            f"Documentation markers '{begin}'/'{end}' not found in {doc_path}"
        )

    replacement = f"{begin}\n" + "\n".join(lines) + f"\n{end}"
    updated = pattern.sub(replacement, contents, count=1)
    doc_path.write_text(updated, encoding="utf-8")
    return doc_path


DEFAULT_MONITORING_FOCUS: dict[str, tuple[str, ...]] = {
    "CLI": ("src/chiron/cli/", "cli/", "chiron/cli/", "src/cli/"),
    "Service": (
        "src/chiron/service/",
        "service/",
        "chiron/service/",
        "src/service/",
        "src/chiron/mcp/",
        "mcp/",
        "chiron/mcp/",
        "src/mcp/",
    ),
}


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
    "contracts": QualityGate(
        name="contracts",
        description="Run Pact contract tests (requires pact-mock-service)",
        category="tests",
        command=(
            "uv",
            "run",
            "--extra",
            "test",
            "pytest",
            "tests/test_contracts.py",
            "-k",
            "contract",
        ),
        critical=False,
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
    "docs": QualityGate(
        name="docs",
        description="Build project documentation",
        category="docs",
        command=(
            "uv",
            "run",
            "--extra",
            "docs",
            "mkdocs",
            "build",
            "--strict",
        ),
        critical=False,
    ),
    "build": QualityGate(
        name="build",
        description="Build wheel and source distribution",
        category="build",
        command=("uv", "build"),
    ),
}


DEFAULT_QUALITY_PROFILES: dict[str, tuple[str, ...]] = {
    "full": ("tests", "contracts", "lint", "types", "security", "docs", "build"),
    "fast": ("tests", "lint"),
    "verify": ("tests", "lint", "types"),
    "package": ("build",),
    "contracts": ("contracts",),
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


def _lookup_quality_gate(
    identifier: str, catalog: Mapping[str, QualityGate]
) -> QualityGate | None:
    """Return a gate matching *identifier* by name or category."""

    gate = catalog.get(identifier)
    if gate is not None:
        return gate
    return next((candidate for candidate in catalog.values() if candidate.category == identifier), None)


def build_quality_suite_plan(
    profile: str,
    *,
    config: QualityConfiguration | None = None,
    toggles: Mapping[str, bool | None] | None = None,
) -> QualitySuitePlan:
    """Construct a :class:`QualitySuitePlan` for the requested *profile*."""

    resolved_gates = resolve_quality_profile(profile, config=config)
    catalog = available_quality_gates(config)
    applied_toggles: list[tuple[str, bool]] = []

    if toggles:
        for identifier, state in toggles.items():
            if state is None:
                continue
            applied_toggles.append((identifier, bool(state)))
            if state:
                gate = _lookup_quality_gate(identifier, catalog)
                if gate is None:
                    continue
                if all(existing.name != gate.name for existing in resolved_gates):
                    resolved_gates.append(gate)
            else:
                resolved_gates = [
                    gate
                    for gate in resolved_gates
                    if gate.name != identifier and gate.category != identifier
                ]
    # Ensure stable ordering by catalog appearance to aid deterministic dry-runs.
    order = {name: index for index, name in enumerate(catalog.keys())}
    resolved_gates.sort(key=lambda gate: order.get(gate.name, len(order)))
    return QualitySuitePlan(
        profile=profile,
        gates=tuple(resolved_gates),
        toggles=tuple(applied_toggles),
    )


def build_quality_suite_insights(plan: QualitySuitePlan) -> QualitySuiteInsights:
    """Return insights for *plan* highlighting categories and toggles."""

    category_counts = Counter(gate.category for gate in plan.gates)
    category_breakdown = tuple(
        sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))
    )
    critical_gates = tuple(gate.name for gate in plan.gates if gate.critical)
    optional_gates = tuple(gate.name for gate in plan.gates if not gate.critical)
    toggles = plan.toggles
    disabled_toggles = tuple(
        identifier for identifier, enabled in toggles if not enabled
    )
    return QualitySuiteInsights(
        profile=plan.profile,
        total_gates=len(plan.gates),
        category_breakdown=category_breakdown,
        critical_gates=critical_gates,
        optional_gates=optional_gates,
        toggles=toggles,
        disabled_toggles=disabled_toggles,
    )


def quality_suite_guide(
    plan: QualitySuitePlan,
    *,
    insights: QualitySuiteInsights | None = None,
    monitoring: QualitySuiteMonitoring | None = None,
) -> list[str]:
    """Return a quickstart guide for agents interacting with the quality suite."""

    resolved_insights = insights or plan.insights
    lines: list[str] = [
        "Quality suite quickstart 🚀",
        "",
        f"Profile: {plan.profile} ({resolved_insights.total_gates} gates)",
    ]
    lines.append("Planned commands:")
    lines.extend(f"  {step}" for step in plan.render_lines())

    if resolved_insights.toggles:
        lines.append("")
        lines.append("Applied toggles:")
        lines.extend(
            f"  • {identifier}={'on' if enabled else 'off'}"
            for identifier, enabled in resolved_insights.toggles
        )

    lines.append("")
    lines.append("Suggested invocations:")
    profile_flag = f"--profile {plan.profile}"
    lines.extend(
        [
            f"  • chiron tools qa {profile_flag} --dry-run",
            f"  • chiron tools qa {profile_flag} --monitor --coverage-xml coverage.xml",
            f"  • chiron tools qa {profile_flag} --json --save-report reports/qa.json",
            f"  • chiron tools qa {profile_flag} --manifest",
        ]
    )

    contract_gate_present = "contracts" in plan.gate_names()
    lines.append("")
    if contract_gate_present:
        lines.append("Contract validation:")
        lines.append(
            "  • Ensure `pact-mock-service` is running locally before executing the contracts gate."
        )
    else:
        lines.append("Optional gates worth enabling:")
        lines.append(
            "  • Use `--contracts` to exercise Pact contract tests (requires pact-mock-service)."
        )

    if monitoring is not None:
        lines.append("")
        lines.append("Monitored follow-ups:")
        if monitoring.recommendation_details:
            lines.extend(
                f"  • {detail.render_line()}" for detail in monitoring.recommendation_details
            )
        else:
            lines.extend(f"  • {rec}" for rec in monitoring.recommendations)
    else:
        lines.append("")
        lines.append(
            "Tip: provide a coverage.xml file and --monitor to surface CLI/service gaps."
        )

    return lines


def quality_suite_manifest(
    *, config: QualityConfiguration | None = None
) -> dict[str, object]:
    """Return a manifest describing available quality gates, profiles, and plans."""

    catalog = available_quality_gates(config)
    profiles = available_quality_profiles(config)
    gates_payload = {
        name: {
            "description": gate.description,
            "category": gate.category,
            "critical": gate.critical,
            "command": list(gate.command),
            "working_directory": str(gate.working_directory) if gate.working_directory else None,
            "env": dict(gate.env) if gate.env else None,
        }
        for name, gate in catalog.items()
    }
    plans = {
        profile_name: build_quality_suite_plan(profile_name, config=config).to_payload()
        for profile_name in profiles
    }
    return {
        "gates": gates_payload,
        "profiles": {name: list(gate_names) for name, gate_names in profiles.items()},
        "plans": plans,
    }


def format_command_result(result: CommandResult) -> str:
    status = "✅" if result.returncode == 0 else "❌"
    command_display = " ".join(result.command)
    duration = f"{result.duration:.2f}s"
    return f"{status} {command_display} ({duration})"


def run_quality_suite(
    commands: Iterable[Sequence[str] | QualityGate],
    *,
    halt_on_failure: bool = True,
    progress: Callable[[QualitySuiteProgressEvent], None] | None = None,
) -> list[CommandResult]:
    """Run a series of commands returning their results."""

    resolved_commands = list(commands)
    total = len(resolved_commands)
    results: list[CommandResult] = []
    for index, command in enumerate(resolved_commands, start=1):
        if isinstance(command, QualityGate):
            command_tuple = command.command
            if progress is not None:
                progress(
                    QualitySuiteProgressEvent(
                        index=index,
                        total=total,
                        command=command_tuple,
                        gate=command,
                        status="started",
                    )
                )
            result = run_command(
                command.command,
                check=False,
                cwd=command.working_directory,
                env=command.env,
                gate=command.name,
            )
        else:
            command_tuple = tuple(command)
            if progress is not None:
                progress(
                    QualitySuiteProgressEvent(
                        index=index,
                        total=total,
                        command=command_tuple,
                        gate=None,
                        status="started",
                    )
                )
            result = run_command(command, check=False)
        if progress is not None:
            progress(
                QualitySuiteProgressEvent(
                    index=index,
                    total=total,
                    command=command_tuple,
                    gate=command if isinstance(command, QualityGate) else None,
                    status="completed",
                    result=result,
                )
            )
        results.append(result)
        if halt_on_failure and result.returncode != 0:
            break
    return results


@dataclass(frozen=True, slots=True)
class QualitySuiteRunReport:
    """Structured summary capturing the outcome of a quality-suite run."""

    plan: QualitySuitePlan
    results: tuple[CommandResult, ...]
    started_at: float
    finished_at: float
    monitoring: QualitySuiteMonitoring | None = None

    @property
    def duration(self) -> float:
        return max(0.0, self.finished_at - self.started_at)

    @property
    def status(self) -> str:
        return "passed" if self.succeeded else "failed"

    @property
    def succeeded(self) -> bool:
        return all(result.returncode == 0 for result in self.results)

    @property
    def failing_gates(self) -> tuple[str, ...]:
        return tuple(
            result.gate or (result.command[0] if result.command else "<unknown>")
            for result in self.results
            if result.returncode != 0
        )

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": self.status,
            "duration": self.duration,
            "plan": self.plan.to_payload(),
            "results": [result.to_payload() for result in self.results],
            "failing_gates": list(self.failing_gates),
            "insights": self.plan.insights.to_payload(),
        }
        if self.monitoring is not None:
            payload["monitoring"] = self.monitoring.to_payload()
        return payload

    def render_text_summary(self) -> str:
        summary = summarise_suite(self.results)
        lines = summary.splitlines() if summary else []
        if not lines:
            lines = ["No commands executed."]
        lines.append("")
        lines.append(f"Total duration: {self.duration:.2f}s")
        if self.failing_gates:
            lines.append("Failing gates:")
            lines.extend(f"  • {gate}" for gate in self.failing_gates)
        else:
            lines.append("All gates passed ✅")
        return "\n".join(line for line in lines if line)

    def render_monitoring_lines(self) -> list[str]:
        if self.monitoring is None:
            return []
        return self.monitoring.render_lines()


def execute_quality_suite(
    plan: QualitySuitePlan,
    *,
    halt_on_failure: bool = True,
    monitoring: QualitySuiteMonitoring | None = None,
    progress: Callable[[QualitySuiteProgressEvent], None] | None = None,
) -> QualitySuiteRunReport:
    """Execute *plan* and return a :class:`QualitySuiteRunReport`."""

    start = time.perf_counter()
    results = run_quality_suite(
        plan.gates,
        halt_on_failure=halt_on_failure,
        progress=progress,
    )
    end = time.perf_counter()
    return QualitySuiteRunReport(
        plan=plan,
        results=tuple(results),
        started_at=start,
        finished_at=end,
        monitoring=monitoring,
    )


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


def _module_name_variants(name: str) -> tuple[str, ...]:
    """Return normalised variants for *name* supporting relative/absolute paths."""

    normalised = name.replace("\\", "/")
    parts = [part for part in normalised.split("/") if part not in {"", "."}]
    variants: list[str] = []

    def _add(candidate: str) -> None:
        if candidate and candidate not in variants:
            variants.append(candidate)

    _add(normalised)
    trimmed = "/".join(parts)
    if trimmed:
        _add(trimmed)

    for index in range(len(parts)):
        suffix = "/".join(parts[index:])
        if not suffix:
            continue
        _add(suffix)
        for prefix in ("src", "chiron", "src/chiron"):
            prefix_with_slash = f"{prefix}/"
            if not suffix.startswith(prefix_with_slash):
                _add(prefix_with_slash + suffix)

    if trimmed:
        if not trimmed.startswith("src/chiron/"):
            _add(f"src/chiron/{trimmed}")
        if not trimmed.startswith("src/"):
            _add(f"src/{trimmed}")
        if not trimmed.startswith("chiron/"):
            _add(f"chiron/{trimmed}")

    return tuple(variants)


def _normalise_focus_prefix(prefix: str) -> str:
    """Return a canonical comparison prefix for focus matching."""

    return prefix.replace("\\", "/").lstrip("./")


def _module_matches_focus(module_name: str, prefixes: Sequence[str]) -> bool:
    """Return ``True`` when *module_name* matches any of *prefixes*."""

    if not prefixes:
        return False
    normalised_prefixes = tuple(_normalise_focus_prefix(prefix) for prefix in prefixes)
    for variant in _module_name_variants(module_name):
        candidate = variant.replace("\\", "/").lstrip("./")
        if any(candidate.startswith(prefix) for prefix in normalised_prefixes):
            return True
    return False


def build_coverage_focus_summaries(
    report: CoverageReport,
    *,
    focus_map: Mapping[str, Sequence[str]],
    threshold: float,
    limit: int,
    min_statements: int,
) -> tuple[CoverageFocusSummary, ...]:
    """Return coverage focus summaries for configured focus areas."""

    modules = report.by_missing(min_statements=min_statements)
    summaries: list[CoverageFocusSummary] = []
    for area, prefixes in focus_map.items():
        matched = [
            module
            for module in modules
            if _module_matches_focus(module.name, prefixes)
        ]
        limited = matched[:limit]
        if limited:
            total_missing = sum(module.missing for module in limited)
            average = sum(module.coverage for module in limited) / len(limited)
            modules_list = tuple(module.name for module in limited)
        else:
            total_missing = 0
            average = 100.0
            modules_list = ()
        summaries.append(
            CoverageFocusSummary(
                area=area,
                modules=modules_list,
                total_missing=total_missing,
                average_coverage=average,
                threshold=threshold,
            )
        )
    return tuple(summaries)


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


def build_quality_suite_monitoring(
    plan: QualitySuitePlan,
    report: CoverageReport,
    *,
    focus_map: Mapping[str, Sequence[str]] = DEFAULT_MONITORING_FOCUS,
    threshold: float = 85.0,
    limit: int = 3,
    min_statements: int = 25,
    source: str | None = None,
) -> QualitySuiteMonitoring:
    """Generate monitoring metadata for *plan* using *report*."""

    focus = build_coverage_focus_summaries(
        report,
        focus_map=focus_map,
        threshold=threshold,
        limit=limit,
        min_statements=min_statements,
    )
    recommendation_details: list[QualitySuiteRecommendation] = []
    for summary in focus:
        for module_name in summary.modules:
            module = report.get(module_name)
            if module is None:
                continue
            severity: Literal["improve", "monitor"]
            if module.coverage < threshold:
                severity = "improve"
                action = (
                    f"Raise {module.name} coverage above {threshold:.1f}% (currently "
                    f"{module.coverage:.1f}%, {module.missing} missing lines)."
                    f" Target lines: {module.format_missing_lines(limit=5)}."
                )
            else:
                severity = "monitor"
                action = (
                    f"Maintain {module.name} coverage at {module.coverage:.1f}%"
                    f" (missing {module.missing} lines)."
                )
            recommendation_details.append(
                QualitySuiteRecommendation(
                    focus=summary.area,
                    module=module.name,
                    missing=module.missing,
                    coverage=module.coverage,
                    severity=severity,
                    missing_lines=module.missing_lines,
                    action=action,
                )
            )
    if recommendation_details:
        recommendations = tuple(detail.action for detail in recommendation_details)
    else:
        recommendations = (
            "All monitored focus areas meet coverage expectations.",
        )
    return QualitySuiteMonitoring(
        coverage_focus=focus,
        recommendations=recommendations,
        recommendation_details=tuple(recommendation_details),
        source=source,
    )


def prepare_quality_suite_dry_run(
    plan: QualitySuitePlan,
    *,
    monitoring: QualitySuiteMonitoring | None = None,
    generated_at: datetime | None = None,
) -> QualitySuiteDryRun:
    """Build a :class:`QualitySuiteDryRun` snapshot for the supplied *plan*."""

    return QualitySuiteDryRun(
        plan=plan,
        insights=plan.insights,
        monitoring=monitoring,
        generated_at=generated_at or datetime.now(UTC),
    )


_TODO_PATTERN = re.compile(r"#\s*(TODO|FIXME|XXX)(:?)(?=\s|$)", re.IGNORECASE)


def _iter_python_files(path: Path) -> Iterable[Path]:
    """Yield Python source files from *path*."""

    if path.is_file() and path.suffix == ".py":
        yield path
        return

    if not path.is_dir():
        return

    for candidate in sorted(path.rglob("*.py")):
        if candidate.is_file():
            yield candidate


def _build_path_index(paths: Sequence[Path]) -> dict[str, Path]:
    """Return a mapping of normalised string representations to real paths."""

    index: dict[str, Path] = {}
    cwd = Path.cwd()
    for path in paths:
        resolved = path.resolve()
        variants = {
            str(path),
            path.as_posix(),
            str(resolved),
            resolved.as_posix(),
            path.name,
        }
        try:
            relative = resolved.relative_to(cwd)
        except ValueError:
            relative = None
        if relative is not None:
            variants.add(str(relative))
            variants.add(relative.as_posix())
        parts = resolved.parts
        for anchor in ("src", "tests"):
            if anchor in parts:
                start = parts.index(anchor)
                variants.add(Path(*parts[start:]).as_posix())
        if "chiron" in parts:
            start = parts.index("chiron")
            variants.add(Path(*parts[start:]).as_posix())
        for variant in variants:
            normalised = variant.replace("\\", "/")
            index.setdefault(normalised, path)
    return index


def _severity_from_ratio(value: float, threshold: float) -> Literal["info", "warning", "critical"]:
    """Return severity based on how much *value* exceeds *threshold*."""

    if threshold <= 0:
        return "info"
    ratio = value / threshold
    if ratio >= 2.0:
        return "critical"
    if ratio >= 1.2:
        return "warning"
    return "info"


def _severity_from_shortfall(shortfall: float, threshold: float) -> Literal["info", "warning", "critical"]:
    """Return severity based on coverage shortfall."""

    if shortfall <= 0 or threshold <= 0:
        return "info"
    ratio = shortfall / threshold
    if ratio >= 0.4:
        return "critical"
    if ratio >= 0.2:
        return "warning"
    return "info"


def _node_length(node: ast.AST) -> int:
    """Return the best-effort source length of *node*."""

    end_lineno = getattr(node, "end_lineno", None)
    if not isinstance(end_lineno, int):
        return 1
    start_lineno = getattr(node, "lineno", end_lineno)
    if not isinstance(start_lineno, int):
        start_lineno = end_lineno
    return max(1, end_lineno - start_lineno + 1)


def _cyclomatic_complexity(node: ast.AST) -> int:
    """Approximate the cyclomatic complexity for the given *node*."""

    class _ComplexityVisitor(ast.NodeVisitor):
        __slots__ = ("score",)

        def __init__(self) -> None:
            self.score = 1

        def visit_If(self, node: ast.If) -> None:  # noqa: N802
            self.score += 1
            self.generic_visit(node)

        def visit_For(self, node: ast.For) -> None:  # noqa: N802
            self.score += 1
            self.generic_visit(node)

        def visit_AsyncFor(self, node: ast.AsyncFor) -> None:  # noqa: N802
            self.score += 1
            self.generic_visit(node)

        def visit_While(self, node: ast.While) -> None:  # noqa: N802
            self.score += 1
            self.generic_visit(node)

        def visit_With(self, node: ast.With) -> None:  # noqa: N802
            self.score += 1
            self.generic_visit(node)

        def visit_AsyncWith(self, node: ast.AsyncWith) -> None:  # noqa: N802
            self.score += 1
            self.generic_visit(node)

        def visit_Try(self, node: ast.Try) -> None:  # noqa: N802
            self.score += len(node.handlers)
            if node.orelse:
                self.score += 1
            if node.finalbody:
                self.score += 1
            self.generic_visit(node)

        def visit_BoolOp(self, node: ast.BoolOp) -> None:  # noqa: N802
            self.score += max(0, len(node.values) - 1)
            self.generic_visit(node)

        def visit_comprehension(self, node: ast.comprehension) -> None:  # noqa: N802
            self.score += 1 + len(node.ifs)
            self.generic_visit(node)

        def visit_IfExp(self, node: ast.IfExp) -> None:  # noqa: N802
            self.score += 1
            self.generic_visit(node)

        def visit_Match(self, node: ast.Match) -> None:  # noqa: N802
            self.score += len(node.cases)
            self.generic_visit(node)

        def visit_Assert(self, node: ast.Assert) -> None:  # noqa: N802
            self.score += 1
            self.generic_visit(node)

    visitor = _ComplexityVisitor()
    visitor.visit(node)
    return max(1, visitor.score)


def _count_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Return a normalised parameter count for *node*."""

    args = node.args
    total = len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)
    if args.vararg is not None:
        total += 1
    if args.kwarg is not None:
        total += 1
    if args.posonlyargs:
        return total
    if args.args:
        first = args.args[0].arg
        if first in {"self", "cls"}:
            total = max(0, total - 1)
    return total


def _resolve_coverage_path(
    module_name: str,
    index: Mapping[str, Path],
) -> Path | None:
    """Resolve *module_name* from coverage report to an indexed source path."""

    for variant in _module_name_variants(module_name):
        candidate = index.get(variant)
        if candidate is not None:
            return candidate
    return None


@dataclass(frozen=True, slots=True)
class RefactorOpportunity:
    """Represents a discovered opportunity to refactor or simplify code."""

    path: Path
    line: int
    symbol: str | None
    kind: Literal[
        "function_length",
        "class_size",
        "todo_comment",
        "low_coverage",
        "cyclomatic_complexity",
        "long_parameter_list",
        "missing_docstring",
    ]
    severity: Literal["info", "warning", "critical"]
    message: str
    metric: float | int | None = None
    threshold: float | int | None = None

    @property
    def severity_rank(self) -> int:
        return {"info": 1, "warning": 2, "critical": 3}[self.severity]

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "path": self.path.as_posix(),
            "line": self.line,
            "symbol": self.symbol,
            "kind": self.kind,
            "severity": self.severity,
            "severity_rank": self.severity_rank,
            "message": self.message,
        }
        if self.metric is not None:
            payload["metric"] = self.metric
        if self.threshold is not None:
            payload["threshold"] = self.threshold
        return payload


@dataclass(frozen=True, slots=True)
class RefactorReport:
    """Aggregate report for refactor opportunities."""

    opportunities: tuple[RefactorOpportunity, ...]
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        ordered = tuple(
            sorted(
                self.opportunities,
                key=lambda op: (op.severity_rank, op.metric or 0.0),
                reverse=True,
            )
        )
        object.__setattr__(self, "opportunities", ordered)

    def to_payload(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "opportunities": [op.to_payload() for op in self.opportunities],
        }

    def render_lines(self) -> Iterable[str]:
        if not self.opportunities:
            yield "No refactor opportunities detected."
            return

        for opportunity in self.opportunities:
            location = f"{opportunity.path}:{opportunity.line}"
            symbol = f" · {opportunity.symbol}" if opportunity.symbol else ""
            metric_hint = ""
            if opportunity.metric is not None and opportunity.threshold is not None:
                metric_hint = (
                    f" (observed {opportunity.metric}, threshold {opportunity.threshold})"
                )
            yield (
                f"[{opportunity.severity.upper()}] {location}{symbol} — "
                f"{opportunity.message}{metric_hint}"
            )


def analyze_refactor_opportunities(
    paths: Sequence[Path | str] | None = None,
    *,
    coverage_xml: Path | None = None,
    max_function_length: int = 60,
    max_class_methods: int = 10,
    max_cyclomatic_complexity: int = 10,
    max_parameters: int = 6,
    min_docstring_length: int = 20,
    coverage_threshold: float = 85.0,
) -> RefactorReport:
    """Inspect the repository and surface potential refactor opportunities."""

    if not paths:
        default_paths = [Path("src"), Path("tests")]
    else:
        default_paths = [Path(path) for path in paths]

    python_files = sorted({candidate.resolve() for path in default_paths for candidate in _iter_python_files(path)})
    path_index = _build_path_index(python_files)

    opportunities: list[RefactorOpportunity] = []

    for source_path in python_files:
        try:
            source = source_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):  # pragma: no cover - defensive guard
            continue

        try:
            tree = ast.parse(source, filename=str(source_path))
        except SyntaxError:
            continue

        class _Visitor(ast.NodeVisitor):
            __slots__ = ("source_path", "collector", "scope")

            def __init__(self, source_path: Path, collector: list[RefactorOpportunity]) -> None:
                self.source_path = source_path
                self.collector = collector
                self.scope: list[str] = []

            def _qualname(self, name: str) -> str:
                if not self.scope:
                    return name
                return ".".join((*self.scope, name))

            def _process_function(
                self, node: ast.FunctionDef | ast.AsyncFunctionDef
            ) -> None:
                qualname = self._qualname(node.name)
                length = _node_length(node)
                if length > max_function_length:
                    severity = _severity_from_ratio(length, max_function_length)
                    self.collector.append(
                        RefactorOpportunity(
                            path=self.source_path,
                            line=node.lineno,
                            symbol=qualname,
                            kind="function_length",
                            severity=severity,
                            message=f"Function spans {length} lines (limit {max_function_length}).",
                            metric=length,
                            threshold=max_function_length,
                        )
                    )

                complexity = _cyclomatic_complexity(node)
                if complexity > max_cyclomatic_complexity:
                    severity = _severity_from_ratio(
                        float(complexity), float(max_cyclomatic_complexity)
                    )
                    self.collector.append(
                        RefactorOpportunity(
                            path=self.source_path,
                            line=node.lineno,
                            symbol=qualname,
                            kind="cyclomatic_complexity",
                            severity=severity,
                            message=(
                                "Cyclomatic complexity "
                                f"{complexity} exceeds {max_cyclomatic_complexity}."
                            ),
                            metric=complexity,
                            threshold=max_cyclomatic_complexity,
                        )
                    )

                parameter_count = _count_parameters(node)
                if parameter_count > max_parameters:
                    severity = _severity_from_ratio(parameter_count, max_parameters)
                    self.collector.append(
                        RefactorOpportunity(
                            path=self.source_path,
                            line=node.lineno,
                            symbol=qualname,
                            kind="long_parameter_list",
                            severity=severity,
                            message=(
                                f"Function accepts {parameter_count} parameters "
                                f"(limit {max_parameters})."
                            ),
                            metric=parameter_count,
                            threshold=max_parameters,
                        )
                    )

                if (
                    length >= min_docstring_length
                    and not node.name.startswith("_")
                    and ast.get_docstring(node) is None
                ):
                    severity = _severity_from_ratio(length, min_docstring_length)
                    self.collector.append(
                        RefactorOpportunity(
                            path=self.source_path,
                            line=node.lineno,
                            symbol=qualname,
                            kind="missing_docstring",
                            severity=severity,
                            message=(
                                "Public function lacks docstring despite spanning "
                                f"{length} lines."
                            ),
                            metric=length,
                            threshold=min_docstring_length,
                        )
                    )

                self.scope.append(node.name)
                self.generic_visit(node)
                self.scope.pop()

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._process_function(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._process_function(node)

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                methods = [
                    child
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                if len(methods) > max_class_methods:
                    severity = _severity_from_ratio(len(methods), max_class_methods)
                    self.collector.append(
                        RefactorOpportunity(
                            path=self.source_path,
                            line=node.lineno,
                            symbol=self._qualname(node.name),
                            kind="class_size",
                            severity=severity,
                            message=(
                                f"Class declares {len(methods)} methods (limit {max_class_methods})."
                            ),
                            metric=len(methods),
                            threshold=max_class_methods,
                        )
                    )
                self.scope.append(node.name)
                self.generic_visit(node)
                self.scope.pop()

        _Visitor(source_path, opportunities).visit(tree)

        for match in _TODO_PATTERN.finditer(source):
            line = source[: match.start()].count("\n") + 1
            opportunities.append(
                RefactorOpportunity(
                    path=source_path,
                    line=line,
                    symbol=None,
                    kind="todo_comment",
                    severity="warning",
                    message="TODO marker present — resolve before release.",
                )
            )

    if coverage_xml is None:
        default_coverage = Path("coverage.xml")
        if default_coverage.exists():
            coverage_xml = default_coverage

    if coverage_xml is not None and coverage_xml.exists():
        report = CoverageReport.from_xml(coverage_xml)
        for module in report.modules_below(coverage_threshold):
            matched = _resolve_coverage_path(module.name, path_index)
            if matched is None:
                continue
            shortfall = max(0.0, coverage_threshold - module.coverage)
            severity = _severity_from_shortfall(shortfall, coverage_threshold)
            opportunities.append(
                RefactorOpportunity(
                    path=matched,
                    line=1,
                    symbol=None,
                    kind="low_coverage",
                    severity=severity,
                    message=(
                        f"{module.name} coverage {module.coverage:.1f}% below "
                        f"{coverage_threshold:.1f}% gate (missing {module.missing} lines)."
                    ),
                    metric=module.coverage,
                    threshold=coverage_threshold,
                )
            )

    return RefactorReport(opportunities=tuple(opportunities))


@dataclass(frozen=True, slots=True)
class HotspotEntry:
    """Represents a file hotspot based on churn and complexity."""

    path: Path
    complexity_score: int
    churn_count: int
    hotspot_score: int

    def to_payload(self) -> dict[str, object]:
        return {
            "path": self.path.as_posix(),
            "complexity_score": self.complexity_score,
            "churn_count": self.churn_count,
            "hotspot_score": self.hotspot_score,
        }


@dataclass(frozen=True, slots=True)
class HotspotReport:
    """Report of code hotspots ranked by churn × complexity."""

    entries: tuple[HotspotEntry, ...]
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_payload(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "entries": [entry.to_payload() for entry in self.entries],
        }

    def render_lines(self, *, limit: int = 20) -> Iterable[str]:
        """Render hotspot report as human-readable lines."""
        if not self.entries:
            yield "No hotspots detected."
            return

        yield f"Top {min(limit, len(self.entries))} Hotspots (complexity × churn):"
        yield ""
        for idx, entry in enumerate(self.entries[:limit], start=1):
            yield (
                f"{idx:2d}. {entry.path} "
                f"(complexity={entry.complexity_score}, "
                f"churn={entry.churn_count}, "
                f"hotspot={entry.hotspot_score})"
            )


def analyze_hotspots(
    *,
    since: str = "12 months ago",
    repo_root: Path | None = None,
    min_complexity: int = 10,
    min_churn: int = 2,
) -> HotspotReport:
    """Analyze code hotspots by combining git churn with complexity metrics.

    This implements the hotspot targeting strategy from Next Steps.md:
    prioritize files that are both complex and frequently changed.

    Args:
        since: Git log time specification (e.g., "12 months ago", "6 months ago")
        repo_root: Repository root directory (defaults to current working directory)
        min_complexity: Minimum complexity score to include (NLOC + CCN threshold)
        min_churn: Minimum number of changes to include

    Returns:
        HotspotReport with entries sorted by hotspot score (complexity × churn)
    """
    root = (repo_root or Path.cwd()).resolve()

    # Step 1: Collect git churn data (past N months)
    churn_data: dict[Path, int] = {}
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                f"--since={since}",
                "--name-only",
                "--pretty=format:",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and line.endswith(".py"):
                    file_path = root / line
                    if file_path.exists():
                        churn_data[file_path] = churn_data.get(file_path, 0) + 1
    except FileNotFoundError:
        # Git not available, skip churn analysis
        pass

    # Step 2: Collect complexity data using existing analyze_refactor_opportunities
    complexity_data: dict[Path, int] = {}
    python_files = sorted({
        candidate.resolve()
        for path in [root / "src", root / "tests"]
        if path.exists()
        for candidate in _iter_python_files(path)
    })

    for source_path in python_files:
        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            # Calculate complexity score as sum of function/method lengths + class sizes
            score = 0
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_lines = _node_length(node)
                    score += max(0, func_lines - 10)  # Penalize long functions
                elif isinstance(node, ast.ClassDef):
                    class_methods = sum(
                        1 for n in node.body
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    )
                    score += max(0, class_methods - 5)  # Penalize large classes
            complexity_data[source_path] = score
        except (SyntaxError, OSError):
            continue

    # Step 3: Combine churn and complexity to calculate hotspot scores
    all_files = set(churn_data.keys()) | set(complexity_data.keys())
    entries: list[HotspotEntry] = []

    for file_path in all_files:
        complexity = complexity_data.get(file_path, 0)
        churn = churn_data.get(file_path, 0)

        # Apply filters
        if complexity < min_complexity or churn < min_churn:
            continue

        hotspot_score = complexity * churn
        entries.append(
            HotspotEntry(
                path=file_path.relative_to(root) if file_path.is_relative_to(root) else file_path,
                complexity_score=complexity,
                churn_count=churn,
                hotspot_score=hotspot_score,
            )
        )

    # Sort by hotspot score (highest first)
    entries.sort(key=lambda e: e.hotspot_score, reverse=True)

    return HotspotReport(entries=tuple(entries))


__all__ = [
    "CommandResult",
    "CoverageFocusSummary",
    "CoverageSummary",
    "CoverageReport",
    "DEFAULT_MONITORING_FOCUS",
    "DevToolCommandError",
    "HotspotEntry",
    "HotspotReport",
    "ModuleCoverage",
    "QualityConfiguration",
    "QualityGate",
    "QualitySuiteInsights",
    "QualitySuiteMonitoring",
    "QualitySuitePlan",
    "QualitySuiteRecommendation",
    "QualitySuiteProgressEvent",
    "QualitySuiteRunReport",
    "QualitySuiteDryRun",
    "RefactorOpportunity",
    "RefactorReport",
    "analyze_hotspots",
    "analyze_refactor_opportunities",
    "available_quality_gates",
    "available_quality_profiles",
    "build_coverage_focus_summaries",
    "build_quality_suite_insights",
    "build_quality_suite_monitoring",
    "build_quality_suite_plan",
    "coverage_gap_summary",
    "coverage_focus",
    "coverage_hotspots",
    "coverage_guard",
    "execute_quality_suite",
    "format_command_result",
    "load_quality_configuration",
    "quality_suite_guide",
    "quality_suite_manifest",
    "prepare_quality_suite_dry_run",
    "run_command",
    "run_quality_suite",
    "resolve_quality_profile",
    "summarise_suite",
]
