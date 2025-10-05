"""Tests for chiron.deps drift and status modules."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from chiron.deps.drift import (
    RISK_MAJOR,
    RISK_MINOR,
    RISK_PATCH,
    RISK_SAFE,
    DependencyDriftReport,
    DriftPolicy,
    PackageDrift,
    load_metadata,
    load_sbom,
    parse_policy,
)
from chiron.deps.status import DependencyStatus, GuardRun, PlannerRun


class TestPackageDrift:
    """Tests for PackageDrift dataclass."""

    def test_package_drift_creation(self) -> None:
        """Test creating a PackageDrift instance."""
        drift = PackageDrift(
            name="test-package",
            current="1.0.0",
            latest="2.0.0",
            severity=RISK_MAJOR,
        )
        assert drift.name == "test-package"
        assert drift.current == "1.0.0"
        assert drift.latest == "2.0.0"
        assert drift.severity == RISK_MAJOR
        assert drift.notes == []

    def test_package_drift_with_notes(self) -> None:
        """Test PackageDrift with notes."""
        drift = PackageDrift(
            name="test-package",
            current="1.0.0",
            latest="1.0.1",
            severity=RISK_PATCH,
            notes=["Security update available"],
        )
        assert len(drift.notes) == 1
        assert drift.notes[0] == "Security update available"


class TestDriftPolicy:
    """Tests for DriftPolicy dataclass."""

    def test_default_policy(self) -> None:
        """Test default drift policy."""
        policy = DriftPolicy()
        assert policy.default_update_window_days == 14
        assert policy.minor_update_window_days == 30
        assert policy.major_review_required is True
        assert policy.allow_transitive_conflicts is False
        assert policy.weight_recency == 3
        assert policy.weight_security == 5

    def test_custom_policy(self) -> None:
        """Test custom drift policy."""
        policy = DriftPolicy(
            default_update_window_days=7,
            major_review_required=False,
            weight_security=10,
        )
        assert policy.default_update_window_days == 7
        assert policy.major_review_required is False
        assert policy.weight_security == 10


class TestDriftReport:
    """Tests for DependencyDriftReport dataclass."""

    def test_drift_report_creation(self) -> None:
        """Test creating a drift report."""
        drift1 = PackageDrift("pkg1", "1.0.0", "2.0.0", RISK_MAJOR)
        drift2 = PackageDrift("pkg2", "1.0.0", "1.1.0", RISK_MINOR)
        
        report = DependencyDriftReport(
            generated_at="2025-01-01T00:00:00Z",
            packages=[drift1, drift2],
            severity=RISK_MAJOR,
            notes=["Major updates detected"],
        )
        
        assert report.generated_at == "2025-01-01T00:00:00Z"
        assert len(report.packages) == 2
        assert report.severity == RISK_MAJOR


class TestDriftUtilities:
    """Tests for drift utility functions."""

    def test_load_sbom(self, tmp_path: Path) -> None:
        """Test loading SBOM file."""
        sbom_data = {
            "components": [
                {"name": "pkg1", "version": "1.0.0"},
                {"name": "pkg2", "version": "2.0.0"},
            ]
        }
        sbom_path = tmp_path / "sbom.json"
        sbom_path.write_text(json.dumps(sbom_data))
        
        components = load_sbom(sbom_path)
        
        assert len(components) == 2
        assert components[0]["name"] == "pkg1"

    def test_load_sbom_invalid(self, tmp_path: Path) -> None:
        """Test loading invalid SBOM."""
        sbom_path = tmp_path / "sbom.json"
        sbom_path.write_text('{"components": "not-a-list"}')
        
        with pytest.raises(ValueError, match="components must be a list"):
            load_sbom(sbom_path)

    def test_load_metadata_existing(self, tmp_path: Path) -> None:
        """Test loading existing metadata."""
        metadata = {"version": "1.0.0", "timestamp": "2025-01-01"}
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata))
        
        result = load_metadata(metadata_path)
        
        assert result["version"] == "1.0.0"
        assert result["timestamp"] == "2025-01-01"

    def test_load_metadata_missing(self, tmp_path: Path) -> None:
        """Test loading non-existent metadata."""
        metadata_path = tmp_path / "missing.json"
        
        result = load_metadata(metadata_path)
        
        assert result == {}

    def test_load_metadata_none(self) -> None:
        """Test loading metadata with None path."""
        result = load_metadata(None)
        assert result == {}

    def test_parse_policy_default(self) -> None:
        """Test parsing policy with None input."""
        policy = parse_policy(None)
        
        assert isinstance(policy, DriftPolicy)
        assert policy.default_update_window_days == 14

    def test_parse_policy_custom(self) -> None:
        """Test parsing custom policy."""
        raw_policy = {
            "default_update_window_days": 7,
            "major_review_required": False,
            "autoresolver_weight_security": 10,
            "package_overrides": [
                {"name": "test-pkg", "max_days": 30}
            ],
        }
        
        policy = parse_policy(raw_policy)
        
        assert policy.default_update_window_days == 7
        assert policy.major_review_required is False
        assert policy.weight_security == 10
        assert "test-pkg" in policy.package_overrides


class TestGuardRun:
    """Tests for GuardRun dataclass."""

    def test_guard_run_creation(self) -> None:
        """Test creating a GuardRun."""
        run = GuardRun(
            exit_code=0,
            assessment={"status": "pass"},
            markdown="# Report\nAll checks passed",
        )
        
        assert run.exit_code == 0
        assert run.assessment["status"] == "pass"
        assert "All checks passed" in run.markdown

    def test_guard_run_to_dict(self) -> None:
        """Test converting GuardRun to dict."""
        run = GuardRun(
            exit_code=1,
            assessment={"status": "fail"},
            markdown="# Report\nIssues found",
        )
        
        result = run.to_dict()
        
        assert result["exit_code"] == 1
        assert result["assessment"]["status"] == "fail"


class TestPlannerRun:
    """Tests for PlannerRun dataclass."""

    def test_planner_run_creation(self) -> None:
        """Test creating a PlannerRun."""
        plan_data = {
            "recommended_commands": ["uv pip install pkg==2.0.0"],
            "summary": {"upgrades": 1, "downgrades": 0},
        }
        run = PlannerRun(exit_code=0, plan=plan_data)
        
        assert run.exit_code == 0
        assert run.plan is not None
        assert run.error is None

    def test_planner_run_recommended_commands(self) -> None:
        """Test extracting recommended commands."""
        plan_data = {
            "recommended_commands": ["cmd1", "cmd2"],
        }
        run = PlannerRun(exit_code=0, plan=plan_data)
        
        commands = run.recommended_commands
        
        assert len(commands) == 2
        assert "cmd1" in commands

    def test_planner_run_no_commands(self) -> None:
        """Test with no commands."""
        run = PlannerRun(exit_code=0, plan={})
        
        commands = run.recommended_commands
        
        assert commands == []

    def test_planner_run_summary(self) -> None:
        """Test extracting summary."""
        plan_data = {
            "summary": {"upgrades": 5, "conflicts": 2},
        }
        run = PlannerRun(exit_code=0, plan=plan_data)
        
        summary = run.summary
        
        assert summary is not None
        assert summary["upgrades"] == 5
        assert summary["conflicts"] == 2

    def test_planner_run_to_dict(self) -> None:
        """Test converting PlannerRun to dict."""
        run = PlannerRun(
            exit_code=1,
            plan=None,
            error="Planning failed",
        )
        
        result = run.to_dict()
        
        assert result["exit_code"] == 1
        assert result["plan"] is None
        assert result["error"] == "Planning failed"


class TestDependencyStatus:
    """Tests for DependencyStatus dataclass."""

    def test_dependency_status_creation(self) -> None:
        """Test creating a DependencyStatus."""
        guard = GuardRun(exit_code=0, assessment={"status": "pass"}, markdown="")
        planner = PlannerRun(exit_code=0, plan={})
        
        status = DependencyStatus(
            generated_at=datetime(2025, 1, 1, tzinfo=UTC),
            guard=guard,
            planner=planner,
            exit_code=0,
            summary={"total_packages": 10},
        )
        
        assert status.exit_code == 0
        assert status.guard.exit_code == 0
        assert status.planner is not None

    def test_dependency_status_to_dict(self) -> None:
        """Test converting DependencyStatus to dict."""
        guard = GuardRun(exit_code=0, assessment={}, markdown="")
        planner = PlannerRun(exit_code=0, plan={})
        
        status = DependencyStatus(
            generated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            guard=guard,
            planner=planner,
            exit_code=0,
            summary={"packages": 5},
        )
        
        result = status.to_dict()
        
        assert "generated_at" in result
        assert result["exit_code"] == 0
        assert "guard" in result
        assert "planner" in result

    def test_dependency_status_without_planner(self) -> None:
        """Test status without planner."""
        guard = GuardRun(exit_code=0, assessment={}, markdown="")
        
        status = DependencyStatus(
            generated_at=datetime(2025, 1, 1, tzinfo=UTC),
            guard=guard,
            planner=None,
            exit_code=0,
            summary={},
        )
        
        result = status.to_dict()
        
        assert result["planner"] is None
