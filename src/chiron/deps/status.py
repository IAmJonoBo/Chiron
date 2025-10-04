#!/usr/bin/env python3
"""Aggregate dependency guard and planner signals for status reporting."""

from __future__ import annotations

import json
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.metrics import Counter, Histogram, Meter
from opentelemetry.trace import Status, StatusCode

from chiron.deps import guard as upgrade_guard
from chiron.deps import planner as upgrade_planner
from chiron.observability import configure_logging, configure_metrics, configure_tracing


@dataclass(slots=True)
class GuardRun:
    """Result of executing the upgrade guard."""

    exit_code: int
    assessment: dict[str, Any] | None
    markdown: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "assessment": self.assessment,
            "markdown": self.markdown,
        }


@dataclass(slots=True)
class PlannerRun:
    """Result of generating an upgrade plan."""

    exit_code: int
    plan: dict[str, Any] | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "plan": self.plan,
            "error": self.error,
        }

    @property
    def recommended_commands(self) -> list[str]:
        if not self.plan:
            return []
        commands = self.plan.get("recommended_commands")
        if isinstance(commands, list):
            return [str(command) for command in commands]
        return []

    @property
    def summary(self) -> dict[str, int] | None:
        if not self.plan:
            return None
        summary = self.plan.get("summary")
        if isinstance(summary, dict):
            return {
                str(key): int(value)
                for key, value in summary.items()
                if isinstance(value, int)
            }
        return None


@dataclass(slots=True)
class DependencyStatus:
    """Combined dependency ecosystem status."""

    generated_at: datetime
    guard: GuardRun
    planner: PlannerRun | None
    exit_code: int
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "generated_at": self.generated_at.isoformat(),
            "exit_code": self.exit_code,
            "summary": self.summary,
            "guard": self.guard.to_dict(),
        }
        if self.planner is not None:
            payload["planner"] = self.planner.to_dict()
        else:
            payload["planner"] = None
        return payload


@dataclass(slots=True)
class PlannerSettings:
    """Configuration options for running the upgrade planner."""

    enabled: bool = True
    packages: Sequence[str] | None = None
    allow_major: bool = False
    limit: int | None = None
    skip_resolver: bool = True
    poetry: str | None = None
    project_root: Path | None = None


STATUS_TRACER_NAME = "chiron.deps_status"
STATUS_TRACER = trace.get_tracer(STATUS_TRACER_NAME)
STATUS_METER: Meter | None = None
STATUS_RUN_COUNTER: Counter | None = None
STATUS_STAGE_DURATION: Histogram | None = None
_OBSERVABILITY_BOOTSTRAPPED = False
STATUS_COMPONENT = "scripts.deps_status"


def _ensure_observability() -> None:
    global _OBSERVABILITY_BOOTSTRAPPED, STATUS_METER, STATUS_RUN_COUNTER
    global STATUS_STAGE_DURATION, STATUS_TRACER
    if _OBSERVABILITY_BOOTSTRAPPED:
        return
    configure_logging(service_name="chiron-deps-status")
    configure_tracing(
        "chiron-deps-status",
        resource_attributes={"component": STATUS_COMPONENT},
    )
    STATUS_METER = configure_metrics(
        namespace="chiron_deps_status",
        service_name="chiron-deps-status",
        resource_attributes={"component": STATUS_COMPONENT},
    )
    STATUS_TRACER = trace.get_tracer(STATUS_TRACER_NAME)
    STATUS_RUN_COUNTER = STATUS_METER.create_counter(
        "dependency_status_runs",
        unit="1",
        description="Total dependency status aggregations grouped by highest severity outcome.",
    )
    STATUS_STAGE_DURATION = STATUS_METER.create_histogram(
        "dependency_status_stage_duration_seconds",
        unit="s",
        description="Duration of dependency status stages in seconds.",
    )
    _OBSERVABILITY_BOOTSTRAPPED = True


def _execute_guard_stage(
    *,
    preflight: Path | None,
    renovate: Path | None,
    cve: Path | None,
    contract: Path,
    sbom: Path | None,
    metadata: Path | None,
    sbom_max_age_days: int | None,
    fail_threshold: str,
) -> GuardRun:
    guard_start = time.perf_counter()
    guard_exit = 0
    guard_assessment: dict[str, Any] | None = None
    guard_markdown: str | None = None
    tracer = STATUS_TRACER or trace.get_tracer(STATUS_TRACER_NAME)

    with tracer.start_as_current_span("deps_status.guard_stage") as guard_span:
        guard_span.set_attribute(
            "deps_status.guard.fail_threshold", str(fail_threshold)
        )
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)
                guard_output = tmpdir_path / "guard-assessment.json"
                guard_markdown_path = tmpdir_path / "guard-summary.md"
                guard_args = _build_guard_args(
                    preflight=preflight,
                    renovate=renovate,
                    cve=cve,
                    contract=contract,
                    sbom=sbom,
                    metadata=metadata,
                    sbom_max_age_days=sbom_max_age_days,
                    fail_threshold=fail_threshold,
                    output_path=guard_output,
                    markdown_path=guard_markdown_path,
                )

                guard_exit = upgrade_guard.main(guard_args)
                guard_assessment = _load_guard_output(guard_output)
                guard_markdown = _load_markdown(guard_markdown_path)
        except Exception as exc:  # pragma: no cover - defensive telemetry path
            guard_span.record_exception(exc)
            guard_span.set_status(Status(StatusCode.ERROR))
            if STATUS_RUN_COUNTER is not None:
                STATUS_RUN_COUNTER.add(1, attributes={"outcome": "error"})
            raise
        finally:
            if STATUS_STAGE_DURATION is not None:
                STATUS_STAGE_DURATION.record(
                    time.perf_counter() - guard_start,
                    attributes={"stage": "guard"},
                )
            guard_span.set_attribute("deps_status.guard_exit_code", int(guard_exit))

    return GuardRun(
        exit_code=guard_exit,
        assessment=guard_assessment,
        markdown=guard_markdown,
    )


def _execute_planner_stage(
    *,
    sbom: Path | None,
    metadata: Path | None,
    settings: PlannerSettings,
) -> tuple[PlannerRun | None, str | None]:
    if not settings.enabled:
        return None, "planner skipped by configuration"
    if sbom is None:
        return None, "planner skipped (no SBOM provided)"

    planner_start = time.perf_counter()
    planner_run: PlannerRun | None = None
    planner_reason: str | None = None
    tracer = STATUS_TRACER or trace.get_tracer(STATUS_TRACER_NAME)

    with tracer.start_as_current_span("deps_status.planner_stage") as planner_span:
        planner_span.set_attribute(
            "deps_status.planner.enabled", bool(settings.enabled)
        )
        planner_span.set_attribute(
            "deps_status.planner.allow_major",
            bool(settings.allow_major),
        )
        planner_span.set_attribute(
            "deps_status.planner.limit",
            settings.limit if settings.limit is not None else -1,
        )
        try:
            config = _build_planner_config(
                sbom=sbom,
                metadata=metadata,
                settings=settings,
            )
            plan_result = upgrade_planner.generate_plan(config)
        except upgrade_planner.PlannerError as exc:
            planner_run = PlannerRun(exit_code=2, plan=None, error=str(exc))
            planner_reason = str(exc)
        except Exception as exc:  # pragma: no cover - defensive telemetry path
            planner_span.record_exception(exc)
            planner_span.set_status(Status(StatusCode.ERROR))
            if STATUS_RUN_COUNTER is not None:
                STATUS_RUN_COUNTER.add(1, attributes={"outcome": "error"})
            raise
        else:
            planner_run = PlannerRun(
                exit_code=plan_result.exit_code,
                plan=plan_result.to_dict(),
            )
            planner_span.set_attribute(
                "deps_status.planner_exit_code", int(plan_result.exit_code)
            )
            planner_span.set_attribute(
                "deps_status.planner_commands",
                len(planner_run.recommended_commands),
            )
        finally:
            if STATUS_STAGE_DURATION is not None:
                STATUS_STAGE_DURATION.record(
                    time.perf_counter() - planner_start,
                    attributes={"stage": "planner"},
                )
            planner_span.set_attribute(
                "deps_status.planner_exit_code",
                int(planner_run.exit_code) if planner_run is not None else -1,
            )
            planner_span.set_attribute(
                "deps_status.planner_reason",
                planner_reason or "",
            )

    return planner_run, planner_reason


def _build_guard_args(
    *,
    preflight: Path | None,
    renovate: Path | None,
    cve: Path | None,
    contract: Path,
    sbom: Path | None,
    metadata: Path | None,
    sbom_max_age_days: int | None,
    fail_threshold: str,
    output_path: Path,
    markdown_path: Path,
) -> list[str]:
    argv: list[str] = ["--contract", str(contract)]
    if preflight is not None:
        argv.extend(["--preflight", str(preflight)])
    if renovate is not None:
        argv.extend(["--renovate", str(renovate)])
    if cve is not None:
        argv.extend(["--cve", str(cve)])
    if sbom is not None:
        argv.extend(["--sbom", str(sbom)])
    if metadata is not None:
        argv.extend(["--metadata", str(metadata)])
    if sbom_max_age_days is not None:
        argv.extend(["--sbom-max-age-days", str(sbom_max_age_days)])
    argv.extend(["--output", str(output_path)])
    argv.extend(["--markdown", str(markdown_path)])
    argv.extend(["--fail-threshold", fail_threshold.lower()])
    return argv


def _load_guard_output(output_path: Path) -> dict[str, Any] | None:
    if not output_path.exists():
        return None
    try:
        return json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _load_markdown(markdown_path: Path) -> str | None:
    if not markdown_path.exists():
        return None
    return markdown_path.read_text(encoding="utf-8")


def _build_planner_config(
    *,
    sbom: Path,
    metadata: Path | None,
    settings: PlannerSettings,
) -> upgrade_planner.PlannerConfig:
    canonical_packages: frozenset[str] | None = None
    if settings.packages:
        canonical_packages = (
            frozenset({value.strip() for value in settings.packages if value.strip()})
            or None
        )
    project_root = settings.project_root or Path.cwd()
    return upgrade_planner.PlannerConfig(
        sbom_path=sbom,
        metadata_path=metadata,
        packages=canonical_packages,
        allow_major=settings.allow_major,
        limit=settings.limit,
        poetry_path=settings.poetry or "poetry",
        project_root=project_root,
        skip_resolver=settings.skip_resolver,
        output_path=None,
        verbose=False,
    )


def _merge_summary(
    guard_run: GuardRun,
    planner_run: PlannerRun | None,
    planner_reason: str | None,
    generated_at: datetime,
) -> tuple[int, dict[str, Any]]:
    guard_summary = guard_run.assessment.get("summary") if guard_run.assessment else {}
    highest = (
        str(guard_summary.get("highest_severity", "unknown"))
        if guard_summary
        else "unknown"
    )
    packages_flagged = guard_summary.get("packages_flagged") if guard_summary else None
    contract_risk = guard_summary.get("contract_risk") if guard_summary else None
    drift_severity = guard_summary.get("drift_severity") if guard_summary else None
    notes = guard_summary.get("notes") if guard_summary else None

    planner_exit = planner_run.exit_code if planner_run is not None else 0
    overall_exit = max(guard_run.exit_code, planner_exit)

    summary: dict[str, Any] = {
        "generated_at": generated_at.isoformat(),
        "highest_severity": highest,
        "packages_flagged": packages_flagged,
        "contract_risk": contract_risk,
        "drift_severity": drift_severity,
        "notes": notes or [],
        "guard_exit_code": guard_run.exit_code,
    }

    if planner_run is not None:
        summary["planner_exit_code"] = planner_run.exit_code
        summary["planner_summary"] = planner_run.summary
        summary["planner_error"] = planner_run.error
        summary["recommended_commands"] = planner_run.recommended_commands
    else:
        summary["planner_exit_code"] = None
        summary["planner_summary"] = None
        summary["planner_error"] = planner_reason
        summary["recommended_commands"] = []
    summary["planner_reason"] = planner_reason

    return overall_exit, summary


def generate_status(
    *,
    preflight: Path | None,
    renovate: Path | None,
    cve: Path | None,
    contract: Path,
    sbom: Path | None,
    metadata: Path | None,
    sbom_max_age_days: int | None,
    fail_threshold: str,
    planner_settings: PlannerSettings | None = None,
) -> DependencyStatus:
    """Generate a combined dependency status report."""

    _ensure_observability()
    total_start = time.perf_counter()
    moment = datetime.now(UTC)
    settings = planner_settings or PlannerSettings()

    with STATUS_TRACER.start_as_current_span("deps_status.generate_status") as span:
        span.set_attribute("deps_status.fail_threshold", str(fail_threshold))
        span.set_attribute("deps_status.planner_enabled", bool(settings.enabled))
        span.set_attribute(
            "deps_status.planner_allow_major", bool(settings.allow_major)
        )
        span.set_attribute(
            "deps_status.planner_limit",
            settings.limit if settings.limit is not None else -1,
        )

        guard_run = _execute_guard_stage(
            preflight=preflight,
            renovate=renovate,
            cve=cve,
            contract=contract,
            sbom=sbom,
            metadata=metadata,
            sbom_max_age_days=sbom_max_age_days,
            fail_threshold=fail_threshold,
        )
        span.set_attribute("deps_status.guard_exit_code", int(guard_run.exit_code))

        planner_run, planner_reason = _execute_planner_stage(
            sbom=sbom,
            metadata=metadata,
            settings=settings,
        )
        span.set_attribute("deps_status.planner_reason", planner_reason or "")

        exit_code, summary = _merge_summary(
            guard_run, planner_run, planner_reason, moment
        )
        outcome = str(summary.get("highest_severity", "unknown"))
        span.set_attribute("deps_status.outcome", outcome)
        span.set_attribute("deps_status.exit_code", int(exit_code))
        if exit_code != 0:
            span.set_status(Status(StatusCode.ERROR))
        if STATUS_RUN_COUNTER is not None:
            STATUS_RUN_COUNTER.add(1, attributes={"outcome": outcome})
        if STATUS_STAGE_DURATION is not None:
            STATUS_STAGE_DURATION.record(
                time.perf_counter() - total_start,
                attributes={"stage": "total"},
            )

        return DependencyStatus(
            generated_at=moment,
            guard=guard_run,
            planner=planner_run,
            exit_code=exit_code,
            summary=summary,
        )
