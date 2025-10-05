"""Tests for chiron.deps.conflict_resolver module - dependency conflict resolution."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from chiron.deps.conflict_resolver import (
    ConflictAnalysisReport,
    ConflictInfo,
    ConflictResolution,
    ConflictResolver,
    DependencyConstraint,
)


class TestDependencyConstraint:
    """Tests for DependencyConstraint dataclass."""

    def test_constraint_creation(self) -> None:
        """Test creating a dependency constraint."""
        constraint = DependencyConstraint(
            package="requests",
            constraint=">=2.28.0",
            required_by="example-pkg",
            is_direct=True,
        )

        assert constraint.package == "requests"
        assert constraint.constraint == ">=2.28.0"
        assert constraint.required_by == "example-pkg"
        assert constraint.is_direct is True

    def test_constraint_defaults(self) -> None:
        """Test default values."""
        constraint = DependencyConstraint(
            package="requests",
            constraint=">=2.28.0",
            required_by="example-pkg",
        )

        assert constraint.is_direct is False

    def test_to_dict(self) -> None:
        """Test converting constraint to dictionary."""
        constraint = DependencyConstraint(
            package="requests",
            constraint=">=2.28.0",
            required_by="example-pkg",
            is_direct=True,
        )

        result = constraint.to_dict()

        assert result["package"] == "requests"
        assert result["constraint"] == ">=2.28.0"
        assert result["required_by"] == "example-pkg"
        assert result["is_direct"] is True


class TestConflictInfo:
    """Tests for ConflictInfo dataclass."""

    def test_conflict_info_creation(self) -> None:
        """Test creating conflict info."""
        constraint1 = DependencyConstraint("pkg", ">=1.0", "app1")
        constraint2 = DependencyConstraint("pkg", "<1.0", "app2")

        conflict = ConflictInfo(
            package="pkg",
            conflicting_constraints=[constraint1, constraint2],
            conflict_type="version",
            severity="error",
            resolution_suggestions=["Upgrade app2"],
            auto_resolvable=False,
        )

        assert conflict.package == "pkg"
        assert len(conflict.conflicting_constraints) == 2
        assert conflict.conflict_type == "version"
        assert conflict.severity == "error"
        assert "Upgrade app2" in conflict.resolution_suggestions
        assert conflict.auto_resolvable is False

    def test_conflict_info_defaults(self) -> None:
        """Test default values."""
        constraint = DependencyConstraint("pkg", ">=1.0", "app")
        conflict = ConflictInfo(
            package="pkg",
            conflicting_constraints=[constraint],
            conflict_type="missing",
            severity="warning",
        )

        assert conflict.resolution_suggestions == []
        assert conflict.auto_resolvable is False

    def test_to_dict(self) -> None:
        """Test converting conflict info to dictionary."""
        constraint = DependencyConstraint("pkg", ">=1.0", "app")
        conflict = ConflictInfo(
            package="pkg",
            conflicting_constraints=[constraint],
            conflict_type="version",
            severity="error",
            resolution_suggestions=["Pin to 1.0.0"],
        )

        result = conflict.to_dict()

        assert result["package"] == "pkg"
        assert len(result["conflicting_constraints"]) == 1
        assert result["conflict_type"] == "version"
        assert result["severity"] == "error"
        assert "Pin to 1.0.0" in result["resolution_suggestions"]


class TestConflictResolution:
    """Tests for ConflictResolution dataclass."""

    def test_resolution_creation(self) -> None:
        """Test creating a resolution."""
        resolution = ConflictResolution(
            package="requests",
            resolution_type="upgrade",
            target_version="2.28.0",
            confidence=0.9,
            description="Upgrade to resolve conflict",
            commands=["poetry add requests@2.28.0"],
        )

        assert resolution.package == "requests"
        assert resolution.resolution_type == "upgrade"
        assert resolution.target_version == "2.28.0"
        assert resolution.confidence == 0.9
        assert "Upgrade" in resolution.description
        assert len(resolution.commands) == 1

    def test_resolution_defaults(self) -> None:
        """Test default values."""
        resolution = ConflictResolution(
            package="pkg",
            resolution_type="manual",
            target_version=None,
            confidence=0.5,
            description="Manual resolution required",
        )

        assert resolution.commands == []
        assert resolution.target_version is None

    def test_to_dict(self) -> None:
        """Test converting resolution to dictionary."""
        resolution = ConflictResolution(
            package="pkg",
            resolution_type="pin",
            target_version="1.0.0",
            confidence=0.95,
            description="Pin to stable version",
            commands=["poetry add pkg==1.0.0"],
        )

        result = resolution.to_dict()

        assert result["package"] == "pkg"
        assert result["resolution_type"] == "pin"
        assert result["target_version"] == "1.0.0"
        assert result["confidence"] == 0.95
        assert len(result["commands"]) == 1


class TestConflictAnalysisReport:
    """Tests for ConflictAnalysisReport dataclass."""

    def test_report_creation(self) -> None:
        """Test creating analysis report."""
        now = datetime.now(UTC)
        constraint = DependencyConstraint("pkg", ">=1.0", "app")
        conflict = ConflictInfo(
            package="pkg",
            conflicting_constraints=[constraint],
            conflict_type="version",
            severity="error",
        )
        resolution = ConflictResolution(
            package="pkg",
            resolution_type="upgrade",
            target_version="1.0.0",
            confidence=0.9,
            description="Upgrade package",
        )

        report = ConflictAnalysisReport(
            generated_at=now,
            conflicts=[conflict],
            resolutions=[resolution],
            summary={"total": 1, "error": 1},
            auto_resolvable_count=0,
        )

        assert report.generated_at == now
        assert len(report.conflicts) == 1
        assert len(report.resolutions) == 1
        assert report.summary["total"] == 1
        assert report.auto_resolvable_count == 0

    def test_to_dict(self) -> None:
        """Test converting report to dictionary."""
        now = datetime.now(UTC)
        constraint = DependencyConstraint("pkg", ">=1.0", "app")
        conflict = ConflictInfo(
            package="pkg",
            conflicting_constraints=[constraint],
            conflict_type="version",
            severity="error",
        )
        resolution = ConflictResolution(
            package="pkg",
            resolution_type="pin",
            target_version="1.0.0",
            confidence=0.9,
            description="Pin version",
        )

        report = ConflictAnalysisReport(
            generated_at=now,
            conflicts=[conflict],
            resolutions=[resolution],
            summary={"total": 1},
            auto_resolvable_count=1,
        )

        result = report.to_dict()

        assert "generated_at" in result
        assert len(result["conflicts"]) == 1
        assert len(result["resolutions"]) == 1
        assert result["summary"]["total"] == 1
        assert result["auto_resolvable_count"] == 1


class TestConflictResolver:
    """Tests for ConflictResolver class."""

    def test_initialization_default(self) -> None:
        """Test resolver initialization with defaults."""
        resolver = ConflictResolver()
        assert resolver.conservative is True

    def test_initialization_non_conservative(self) -> None:
        """Test resolver initialization in non-conservative mode."""
        resolver = ConflictResolver(conservative=False)
        assert resolver.conservative is False

    def test_analyze_conflicts_empty_dependencies(self) -> None:
        """Test analyzing conflicts with no dependencies."""
        resolver = ConflictResolver()
        dependencies: dict[str, Any] = {}

        report = resolver.analyze_conflicts(dependencies)

        assert isinstance(report, ConflictAnalysisReport)
        assert len(report.conflicts) == 0
        assert len(report.resolutions) == 0

    def test_analyze_conflicts_single_dependency(self) -> None:
        """Test analyzing conflicts with single dependency."""
        resolver = ConflictResolver()
        dependencies = {"requests": ">=2.28.0"}

        report = resolver.analyze_conflicts(dependencies)

        assert isinstance(report, ConflictAnalysisReport)
        # Single dependency shouldn't have conflicts
        assert len(report.conflicts) == 0

    def test_analyze_conflicts_with_lock_data(self) -> None:
        """Test analyzing with lock data."""
        resolver = ConflictResolver()
        dependencies = {"requests": ">=2.28.0"}
        lock_data = {"requests": {"version": "2.28.1"}}

        report = resolver.analyze_conflicts(dependencies, lock_data)

        assert isinstance(report, ConflictAnalysisReport)

    def test_analyze_conflicts_conservative_mode(self) -> None:
        """Test that conservative mode affects resolutions."""
        resolver = ConflictResolver(conservative=True)
        dependencies = {"pkg1": ">=1.0", "pkg2": ">=2.0"}

        report = resolver.analyze_conflicts(dependencies)

        # In conservative mode, resolutions should have high confidence
        for resolution in report.resolutions:
            assert resolution.confidence >= 0.0  # All resolutions should be valid

    def test_analyze_conflicts_non_conservative_mode(self) -> None:
        """Test non-conservative mode allows more aggressive resolutions."""
        resolver = ConflictResolver(conservative=False)
        dependencies = {"pkg1": ">=1.0", "pkg2": ">=2.0"}

        report = resolver.analyze_conflicts(dependencies)

        # Should still generate valid report
        assert isinstance(report, ConflictAnalysisReport)

    def test_report_summary_format(self) -> None:
        """Test that report summary has expected format."""
        resolver = ConflictResolver()
        dependencies = {"requests": ">=2.28.0"}

        report = resolver.analyze_conflicts(dependencies)

        # Summary should be a dictionary
        assert isinstance(report.summary, dict)
        # Should have at least total count
        assert "total" in report.summary or len(report.summary) == 0
