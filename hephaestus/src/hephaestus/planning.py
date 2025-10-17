"""Utilities for describing and rendering execution plans."""

from __future__ import annotations

import shlex
from collections.abc import Sequence
from dataclasses import dataclass

from rich.table import Table


@dataclass(frozen=True, slots=True)
class ExecutionPlanStep:
    """Describe a discrete action in an execution plan."""

    key: str
    description: str
    command: Sequence[str] | None = None


def render_execution_plan(plan: Sequence[ExecutionPlanStep]) -> list[str]:
    """Return numbered, human-readable lines for *plan* steps."""

    lines: list[str] = []
    for index, step in enumerate(plan, start=1):
        prefix = f"{index}. {step.description}"
        if step.command:
            command_display = shlex.join(step.command)
            lines.append(f"{prefix}: {command_display}")
        else:
            lines.append(prefix)
    return lines


def plan_by_key(plan: Sequence[ExecutionPlanStep]) -> dict[str, ExecutionPlanStep]:
    """Index *plan* steps by their unique ``key`` values."""

    indexed: dict[str, ExecutionPlanStep] = {}
    for step in plan:
        if step.key in indexed:
            raise ValueError(f"Duplicate plan step key detected: {step.key}")
        indexed[step.key] = step
    return indexed


def render_execution_plan_table(
    plan: Sequence[ExecutionPlanStep], *, title: str | None = None
) -> Table:
    """Return a ``rich`` table representation for an execution *plan*."""

    table = Table(title=title)
    table.add_column("Step", style="cyan", overflow="fold")
    table.add_column("Command", style="magenta", overflow="fold")
    for index, step in enumerate(plan, start=1):
        description = f"{index}. {step.description}"
        command = shlex.join(step.command) if step.command else "—"
        table.add_row(description, command)
    return table
