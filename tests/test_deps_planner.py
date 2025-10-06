"""Tests for chiron.deps.planner module - upgrade planning."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from chiron.deps.planner import (
    PlanEntry,
    PlannerConfig,
    PlannerError,
    PlannerResult,
    ResolverResult,
    UpgradeCandidate,
)


class TestPlannerError:
    """Tests for PlannerError exception."""

    def test_planner_error_creation(self) -> None:
        """Test creating a PlannerError."""
        error = PlannerError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, RuntimeError)


class TestPlannerConfig:
    """Tests for PlannerConfig dataclass."""

    def test_planner_config_initialization(self, tmp_path: Path) -> None:
        """Test PlannerConfig initialization."""
        sbom_path = tmp_path / "sbom.json"
        config = PlannerConfig(
            sbom_path=sbom_path,
            metadata_path=None,
            packages=None,
            allow_major=False,
            limit=None,
            poetry_path="poetry",
            project_root=tmp_path,
            skip_resolver=False,
            output_path=None,
            verbose=False,
        )
        assert config.sbom_path == sbom_path
        assert config.allow_major is False
        assert config.skip_resolver is False
        assert config.verbose is False

    def test_planner_config_with_packages(self, tmp_path: Path) -> None:
        """Test PlannerConfig with specific packages."""
        packages = frozenset(["requests", "urllib3"])
        config = PlannerConfig(
            sbom_path=tmp_path / "sbom.json",
            metadata_path=None,
            packages=packages,
            allow_major=True,
            limit=10,
            poetry_path="poetry",
            project_root=tmp_path,
            skip_resolver=True,
            output_path=tmp_path / "output.json",
            verbose=True,
        )
        assert config.packages == packages
        assert config.allow_major is True
        assert config.limit == 10
        assert config.skip_resolver is True
        assert config.verbose is True


class TestUpgradeCandidate:
    """Tests for UpgradeCandidate dataclass."""

    def test_upgrade_candidate_initialization(self) -> None:
        """Test UpgradeCandidate initialization."""
        candidate = UpgradeCandidate(
            name="requests",
            canonical_name="requests",
            current="2.28.0",
            latest="2.31.0",
            severity="minor",
            notes=["Minor version upgrade"],
        )
        assert candidate.name == "requests"
        assert candidate.canonical_name == "requests"
        assert candidate.current == "2.28.0"
        assert candidate.latest == "2.31.0"
        assert candidate.severity == "minor"
        assert len(candidate.notes) == 1

    def test_upgrade_candidate_to_dict(self) -> None:
        """Test UpgradeCandidate to_dict serialization."""
        candidate = UpgradeCandidate(
            name="requests",
            canonical_name="requests",
            current="2.28.0",
            latest="2.31.0",
            severity="minor",
            notes=["Test note"],
            score=0.8,
            score_breakdown={"security": 0.5, "stability": 0.3},
        )
        result = candidate.to_dict()
        assert result["name"] == "requests"
        assert result["current"] == "2.28.0"
        assert result["latest"] == "2.31.0"
        assert result["severity"] == "minor"
        assert result["score"] == 0.8
        assert "security" in result["score_breakdown"]

    def test_upgrade_candidate_defaults(self) -> None:
        """Test UpgradeCandidate default values."""
        candidate = UpgradeCandidate(
            name="test",
            canonical_name="test",
            current=None,
            latest=None,
            severity="patch",
            notes=[],
        )
        assert candidate.score == 0.0
        assert candidate.score_breakdown == {}


class TestResolverResult:
    """Tests for ResolverResult dataclass."""

    def test_resolver_result_success(self) -> None:
        """Test ResolverResult for successful resolution."""
        result = ResolverResult(
            status="success",
            command=["poetry", "add", "requests@2.31.0"],
            returncode=0,
            duration_s=1.5,
            stdout="Successfully resolved",
            stderr="",
        )
        assert result.status == "success"
        assert result.returncode == 0
        assert result.duration_s == 1.5

    def test_resolver_result_failure(self) -> None:
        """Test ResolverResult for failed resolution."""
        result = ResolverResult(
            status="failure",
            command=["poetry", "add", "requests@9.9.9"],
            returncode=1,
            duration_s=0.5,
            stdout="",
            stderr="Package not found",
            reason="Version does not exist",
        )
        assert result.status == "failure"
        assert result.returncode == 1
        assert result.reason == "Version does not exist"

    def test_resolver_result_to_dict(self) -> None:
        """Test ResolverResult to_dict serialization."""
        result = ResolverResult(
            status="success",
            command=["poetry", "update"],
            returncode=0,
            duration_s=2.0,
            stdout="Updated",
            stderr="",
            reason="Test reason",
        )
        data = result.to_dict()
        assert data["status"] == "success"
        assert data["command"] == ["poetry", "update"]
        assert data["returncode"] == 0
        assert data["duration_s"] == 2.0
        assert data["reason"] == "Test reason"

    def test_resolver_result_to_dict_without_reason(self) -> None:
        """Test ResolverResult to_dict without reason."""
        result = ResolverResult(
            status="success",
            command=["poetry", "update"],
            returncode=0,
            duration_s=1.0,
            stdout="",
            stderr="",
        )
        data = result.to_dict()
        assert "reason" not in data


class TestPlanEntry:
    """Tests for PlanEntry dataclass."""

    def test_plan_entry_initialization(self) -> None:
        """Test PlanEntry initialization."""
        candidate = UpgradeCandidate(
            name="requests",
            canonical_name="requests",
            current="2.28.0",
            latest="2.31.0",
            severity="minor",
            notes=[],
        )
        resolver = ResolverResult(
            status="success",
            command=["poetry", "add", "requests@2.31.0"],
            returncode=0,
            duration_s=1.5,
            stdout="Success",
            stderr="",
        )
        entry = PlanEntry(candidate=candidate, resolver=resolver)
        assert entry.candidate.name == "requests"
        assert entry.resolver.status == "success"

    def test_plan_entry_to_dict(self) -> None:
        """Test PlanEntry to_dict serialization."""
        candidate = UpgradeCandidate(
            name="test",
            canonical_name="test",
            current="1.0.0",
            latest="2.0.0",
            severity="major",
            notes=["Breaking changes"],
        )
        resolver = ResolverResult(
            status="failure",
            command=["poetry", "add", "test@2.0.0"],
            returncode=1,
            duration_s=0.5,
            stdout="",
            stderr="Conflict",
        )
        entry = PlanEntry(candidate=candidate, resolver=resolver)
        data = entry.to_dict()
        assert "candidate" in data
        assert "resolver" in data
        assert data["candidate"]["name"] == "test"
        assert data["resolver"]["status"] == "failure"


class TestPlannerResult:
    """Tests for PlannerResult dataclass."""

    def test_planner_result_initialization(self, tmp_path: Path) -> None:
        """Test PlannerResult initialization."""
        config = PlannerConfig(
            sbom_path=tmp_path / "sbom.json",
            metadata_path=None,
            packages=None,
            allow_major=False,
            limit=None,
            poetry_path="poetry",
            project_root=tmp_path,
            skip_resolver=False,
            output_path=None,
            verbose=False,
        )
        now = datetime.now(UTC)
        result = PlannerResult(
            generated_at=now,
            config=config,
            attempts=[],
            summary={"total": 0, "success": 0, "failure": 0},
            recommended_commands=[],
            exit_code=0,
        )
        assert result.generated_at == now
        assert result.exit_code == 0
        assert result.summary["total"] == 0

    def test_planner_result_with_attempts(self, tmp_path: Path) -> None:
        """Test PlannerResult with upgrade attempts."""
        config = PlannerConfig(
            sbom_path=tmp_path / "sbom.json",
            metadata_path=None,
            packages=frozenset(["requests"]),
            allow_major=True,
            limit=None,
            poetry_path="poetry",
            project_root=tmp_path,
            skip_resolver=False,
            output_path=None,
            verbose=False,
        )
        candidate = UpgradeCandidate(
            name="requests",
            canonical_name="requests",
            current="2.28.0",
            latest="2.31.0",
            severity="minor",
            notes=[],
        )
        resolver = ResolverResult(
            status="success",
            command=["poetry", "add", "requests@2.31.0"],
            returncode=0,
            duration_s=1.5,
            stdout="Success",
            stderr="",
        )
        entry = PlanEntry(candidate=candidate, resolver=resolver)

        result = PlannerResult(
            generated_at=datetime.now(UTC),
            config=config,
            attempts=[entry],
            summary={"total": 1, "success": 1, "failure": 0},
            recommended_commands=["poetry add requests@2.31.0"],
            exit_code=0,
        )
        assert len(result.attempts) == 1
        assert result.summary["success"] == 1
        assert len(result.recommended_commands) == 1

    def test_planner_result_to_dict(self, tmp_path: Path) -> None:
        """Test PlannerResult to_dict serialization."""
        config = PlannerConfig(
            sbom_path=tmp_path / "sbom.json",
            metadata_path=tmp_path / "metadata.json",
            packages=frozenset(["requests", "urllib3"]),
            allow_major=True,
            limit=5,
            poetry_path="poetry",
            project_root=tmp_path,
            skip_resolver=False,
            output_path=tmp_path / "output.json",
            verbose=True,
        )
        result = PlannerResult(
            generated_at=datetime.now(UTC),
            config=config,
            attempts=[],
            summary={"total": 2, "success": 1, "failure": 1},
            recommended_commands=["poetry add requests@2.31.0"],
            exit_code=0,
            upgrade_advice={"recommendations": ["Use latest versions"]},
        )
        data = result.to_dict()
        assert "generated_at" in data
        assert data["allow_major"] is True
        assert data["summary"]["total"] == 2
        assert len(data["recommended_commands"]) == 1
        assert "upgrade_advice" in data
        assert data["packages_requested"] == ["requests", "urllib3"]

    def test_planner_result_to_dict_without_advice(self, tmp_path: Path) -> None:
        """Test PlannerResult to_dict without upgrade advice."""
        config = PlannerConfig(
            sbom_path=tmp_path / "sbom.json",
            metadata_path=None,
            packages=None,
            allow_major=False,
            limit=None,
            poetry_path="poetry",
            project_root=tmp_path,
            skip_resolver=True,
            output_path=None,
            verbose=False,
        )
        result = PlannerResult(
            generated_at=datetime.now(UTC),
            config=config,
            attempts=[],
            summary={},
            recommended_commands=[],
            exit_code=0,
        )
        data = result.to_dict()
        assert "upgrade_advice" not in data
        assert data["skip_resolver"] is True


class TestDataClassSerialization:
    """Tests for complete serialization workflow."""

    def test_full_serialization_workflow(self, tmp_path: Path) -> None:
        """Test complete serialization of planner result."""
        config = PlannerConfig(
            sbom_path=tmp_path / "sbom.json",
            metadata_path=None,
            packages=frozenset(["requests"]),
            allow_major=False,
            limit=1,
            poetry_path="poetry",
            project_root=tmp_path,
            skip_resolver=False,
            output_path=None,
            verbose=False,
        )
        candidate = UpgradeCandidate(
            name="requests",
            canonical_name="requests",
            current="2.28.0",
            latest="2.30.0",
            severity="minor",
            notes=["Security fix"],
            score=0.9,
            score_breakdown={"security": 0.6, "stability": 0.3},
        )
        resolver = ResolverResult(
            status="success",
            command=["poetry", "add", "requests@2.30.0"],
            returncode=0,
            duration_s=1.8,
            stdout="Resolved successfully",
            stderr="",
            reason="No conflicts",
        )
        entry = PlanEntry(candidate=candidate, resolver=resolver)
        result = PlannerResult(
            generated_at=datetime.now(UTC),
            config=config,
            attempts=[entry],
            summary={"total": 1, "success": 1},
            recommended_commands=["poetry add requests@2.30.0"],
            exit_code=0,
        )

        data = result.to_dict()
        assert data["summary"]["success"] == 1
        assert len(data["attempts"]) == 1
        assert data["attempts"][0]["candidate"]["name"] == "requests"
        assert data["attempts"][0]["resolver"]["status"] == "success"
