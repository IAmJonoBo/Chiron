"""Tests for dependency conflict resolver heuristics."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from chiron.deps.conflict_resolver import (
    ConflictAnalysisReport,
    ConflictResolver,
    DependencyConstraint,
    analyze_dependency_conflicts,
)


def constraint(
    package: str,
    spec: str,
    *,
    required_by: str,
    direct: bool,
) -> DependencyConstraint:
    """Helper to create dependency constraints with consistent flags."""

    return DependencyConstraint(
        package=package,
        constraint=spec,
        required_by=required_by,
        is_direct=direct,
    )


def test_detects_direct_conflict_and_generates_pin_resolution():
    resolver = ConflictResolver(conservative=True)
    constraints = {
        "fastapi": [
            constraint("fastapi", "^1.0", required_by="<root>", direct=True),
            constraint("fastapi", ">=2.0", required_by="rich-stack", direct=False),
        ]
    }

    conflicts = resolver._detect_conflicts(constraints)
    assert len(conflicts) == 1

    conflict = conflicts[0]
    assert conflict.package == "fastapi"
    assert conflict.auto_resolvable is True
    assert conflict.conflict_type == "version"
    assert conflict.severity == "error"
    assert any(
        suggestion.startswith("Use direct dependency constraint")
        for suggestion in conflict.resolution_suggestions
    )

    resolution = resolver._generate_resolution(conflict, {"dependencies": {}})
    assert resolution is not None
    assert resolution.resolution_type == "pin"
    assert resolution.target_version == "^1.0"
    assert "poetry add fastapi" in resolution.commands[0]


def test_generate_manual_resolution_when_all_transitive(monkeypatch: pytest.MonkeyPatch):
    resolver = ConflictResolver(conservative=False)
    constraints = {
        "uvicorn": [
            constraint("uvicorn", "^1.0", required_by="fastapi", direct=False),
            constraint("uvicorn", ">=2.0", required_by="observability", direct=False),
        ]
    }

    conflicts = resolver._detect_conflicts(constraints)
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.auto_resolvable is False

    resolution = resolver._generate_resolution(conflict, {"dependencies": {}})
    assert resolution is not None
    assert resolution.resolution_type == "manual"
    assert resolution.target_version is None
    assert "Manual review" in resolution.description
    assert all(cmd.startswith("poetry show") for cmd in resolution.commands)


def test_extract_constraints_includes_dev_only_when_missing():
    resolver = ConflictResolver()
    dependencies = {
        "dependencies": {
            "fastapi": "^0.103",
            "uvicorn": {"version": ">=0.23"},
        },
        "dev-dependencies": {
            "pytest": {"version": "^8.3"},
            "fastapi": {"version": "^0.110"},
        },
    }

    extracted = resolver._extract_constraints(dependencies)
    assert {"fastapi", "uvicorn", "pytest"} == set(extracted)

    fastapi_constraints = extracted["fastapi"]
    assert len(fastapi_constraints) == 1
    assert fastapi_constraints[0].is_direct is True
    assert fastapi_constraints[0].required_by == "<root>"

    pytest_constraints = extracted["pytest"]
    assert len(pytest_constraints) == 1
    assert pytest_constraints[0].required_by == "<root-dev>"
    assert pytest_constraints[0].constraint == "^8.3"


def test_analyze_conflicts_reports_summary(monkeypatch: pytest.MonkeyPatch):
    resolver = ConflictResolver()

    constraints_map = {
        "fastapi": [
            constraint("fastapi", "^1.0", required_by="<root>", direct=True),
            constraint("fastapi", ">=2.0", required_by="rich-stack", direct=False),
        ],
        "httpx": [
            constraint("httpx", "*", required_by="<root>", direct=True),
        ],
    }

    monkeypatch.setattr(
        resolver,
        "_extract_constraints",
        lambda dependencies: constraints_map,
    )

    report = resolver.analyze_conflicts({"dependencies": {}})
    assert isinstance(report, ConflictAnalysisReport)
    assert report.summary["total_conflicts"] == 1
    assert report.summary["version_conflicts"] == 1
    assert report.auto_resolvable_count == 1
    assert len(report.conflicts) == 1
    assert len(report.resolutions) == 1
    assert report.resolutions[0].resolution_type == "pin"
    assert report.conflicts[0].package == "fastapi"

    # Dataclass serialisation exercised for parity with docs examples
    serialised = report.to_dict()
    assert serialised["summary"]["total_conflicts"] == 1
    generated_at = datetime.fromisoformat(serialised["generated_at"])
    assert generated_at.tzinfo is not None
    assert generated_at <= datetime.now(UTC)


def test_analyze_dependency_conflicts_helper(monkeypatch: pytest.MonkeyPatch):
    resolver = ConflictResolver()
    monkeypatch.setattr(
        "chiron.deps.conflict_resolver.ConflictResolver", lambda conservative: resolver
    )

    monkeypatch.setattr(
        resolver,
        "analyze_conflicts",
        lambda dependencies, lock_data: ConflictAnalysisReport(
            generated_at=datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
            conflicts=[],
            resolutions=[],
            summary={"total_conflicts": 0},
            auto_resolvable_count=0,
        ),
    )

    report = analyze_dependency_conflicts({"dependencies": {}}, None, conservative=False)
    assert report.summary["total_conflicts"] == 0
    assert report.conflicts == []
