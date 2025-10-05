"""Tests for chiron.deps modules - focusing on policy and constraints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from packaging.version import Version

from chiron.deps.constraints import ConstraintsConfig, ConstraintsGenerator
from chiron.deps.policy import (
    PackagePolicy,
    PolicyEngine,
    PolicyViolation,
    UpgradePolicy,
)


class TestPackagePolicy:
    """Tests for PackagePolicy dataclass."""

    def test_default_policy(self) -> None:
        """Test creating a policy with defaults."""
        policy = PackagePolicy(name="test-package")
        assert policy.name == "test-package"
        assert policy.allowed is True
        assert policy.version_ceiling is None
        assert policy.version_floor is None
        assert policy.upgrade_cadence_days is None
        assert policy.requires_review is False

    def test_blocked_package(self) -> None:
        """Test creating a blocked package policy."""
        policy = PackagePolicy(
            name="blocked-package",
            allowed=False,
            reason="Security vulnerability",
        )
        assert policy.allowed is False
        assert policy.reason == "Security vulnerability"

    def test_version_constraints(self) -> None:
        """Test policy with version constraints."""
        policy = PackagePolicy(
            name="constrained-package",
            version_ceiling="2.0.0",
            version_floor="1.0.0",
            blocked_versions=["1.5.0", "1.5.1"],
        )
        assert policy.version_ceiling == "2.0.0"
        assert policy.version_floor == "1.0.0"
        assert "1.5.0" in policy.blocked_versions


class TestPolicyViolation:
    """Tests for PolicyViolation dataclass."""

    def test_create_violation(self) -> None:
        """Test creating a policy violation."""
        violation = PolicyViolation(
            package="test-package",
            current_version="1.0.0",
            target_version="2.0.0",
            violation_type="version_ceiling",
            message="Version exceeds ceiling",
            severity="error",
        )
        assert violation.package == "test-package"
        assert violation.current_version == "1.0.0"
        assert violation.target_version == "2.0.0"
        assert violation.severity == "error"

    def test_default_severity(self) -> None:
        """Test default severity is error."""
        violation = PolicyViolation(
            package="test-package",
            current_version=None,
            target_version="1.0.0",
            violation_type="blocked_package",
            message="Package is blocked",
        )
        assert violation.severity == "error"


class TestUpgradePolicy:
    """Tests for UpgradePolicy dataclass."""

    def test_default_policy(self) -> None:
        """Test creating an upgrade policy with defaults."""
        policy = UpgradePolicy()
        assert policy.allow_major is False
        assert policy.allow_minor is True
        assert policy.allow_patch is True
        assert policy.min_age_days == 0
        assert policy.require_changelog is False

    def test_conservative_policy(self) -> None:
        """Test creating a conservative upgrade policy."""
        policy = UpgradePolicy(
            allow_major=False,
            allow_minor=False,
            allow_patch=True,
            min_age_days=7,
            require_changelog=True,
        )
        assert policy.allow_major is False
        assert policy.allow_minor is False
        assert policy.allow_patch is True
        assert policy.min_age_days == 7
        assert policy.require_changelog is True


class TestPolicyEngine:
    """Tests for PolicyEngine."""

    def test_initialization(self) -> None:
        """Test PolicyEngine initialization."""
        engine = PolicyEngine()
        assert isinstance(engine.policies, dict)
        assert isinstance(engine.global_policy, UpgradePolicy)

    def test_add_policy(self) -> None:
        """Test adding a package policy."""
        engine = PolicyEngine()
        policy = PackagePolicy(name="test-package", allowed=True)
        engine.add_policy(policy)
        assert "test-package" in engine.policies
        assert engine.policies["test-package"] == policy

    def test_check_package_allowed(self) -> None:
        """Test checking if a package is allowed."""
        engine = PolicyEngine()
        # No policy = allowed by default
        assert engine.check_package_allowed("unknown-package") is True

        # Add blocked package
        engine.add_policy(PackagePolicy(name="blocked-package", allowed=False))
        assert engine.check_package_allowed("blocked-package") is False

        # Add allowed package
        engine.add_policy(PackagePolicy(name="allowed-package", allowed=True))
        assert engine.check_package_allowed("allowed-package") is True

    def test_check_version_allowed_no_constraints(self) -> None:
        """Test version checking without constraints."""
        engine = PolicyEngine()
        # No constraints = any version allowed
        assert engine.check_version_allowed("test-package", "1.0.0") is True

    def test_check_version_allowed_with_ceiling(self) -> None:
        """Test version checking with ceiling constraint."""
        engine = PolicyEngine()
        engine.add_policy(
            PackagePolicy(name="test-package", version_ceiling="2.0.0")
        )

        # Version below ceiling should be allowed
        assert engine.check_version_allowed("test-package", "1.0.0") is True
        assert engine.check_version_allowed("test-package", "2.0.0") is True

        # Version above ceiling should be blocked
        assert engine.check_version_allowed("test-package", "3.0.0") is False

    def test_check_version_allowed_with_floor(self) -> None:
        """Test version checking with floor constraint."""
        engine = PolicyEngine()
        engine.add_policy(PackagePolicy(name="test-package", version_floor="1.0.0"))

        # Version below floor should be blocked
        assert engine.check_version_allowed("test-package", "0.9.0") is False

        # Version at or above floor should be allowed
        assert engine.check_version_allowed("test-package", "1.0.0") is True
        assert engine.check_version_allowed("test-package", "2.0.0") is True

    def test_check_version_blocked_versions(self) -> None:
        """Test version checking with blocked versions."""
        engine = PolicyEngine()
        engine.add_policy(
            PackagePolicy(
                name="test-package",
                blocked_versions=["1.5.0", "1.5.1"],
            )
        )

        # Non-blocked versions should be allowed
        assert engine.check_version_allowed("test-package", "1.4.0") is True
        assert engine.check_version_allowed("test-package", "1.6.0") is True

        # Blocked versions should not be allowed
        assert engine.check_version_allowed("test-package", "1.5.0") is False
        assert engine.check_version_allowed("test-package", "1.5.1") is False

    def test_validate_upgrade_major(self) -> None:
        """Test upgrade validation for major version change."""
        engine = PolicyEngine()
        engine.global_policy.allow_major = False

        violations = engine.validate_upgrade("test-package", "1.0.0", "2.0.0")
        assert len(violations) > 0
        assert violations[0].violation_type == "major_upgrade_blocked"

    def test_validate_upgrade_minor(self) -> None:
        """Test upgrade validation for minor version change."""
        engine = PolicyEngine()
        engine.global_policy.allow_minor = False

        violations = engine.validate_upgrade("test-package", "1.0.0", "1.1.0")
        assert len(violations) > 0
        assert violations[0].violation_type == "minor_upgrade_blocked"

    def test_validate_upgrade_patch_allowed(self) -> None:
        """Test upgrade validation for patch version change."""
        engine = PolicyEngine()
        engine.global_policy.allow_patch = True

        violations = engine.validate_upgrade("test-package", "1.0.0", "1.0.1")
        # Patch upgrades allowed, so no violations
        assert len(violations) == 0

    def test_validate_upgrade_blocked_package(self) -> None:
        """Test upgrade validation for blocked package."""
        engine = PolicyEngine()
        engine.add_policy(PackagePolicy(name="blocked-package", allowed=False))

        violations = engine.validate_upgrade("blocked-package", "1.0.0", "1.1.0")
        assert len(violations) > 0
        assert violations[0].violation_type == "blocked_package"


class TestConstraintsConfig:
    """Tests for ConstraintsConfig dataclass."""

    def test_create_config(self, tmp_path: Path) -> None:
        """Test creating a constraints configuration."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        pyproject = project_root / "pyproject.toml"
        pyproject.touch()
        output = project_root / "constraints.txt"

        config = ConstraintsConfig(
            project_root=project_root,
            pyproject_path=pyproject,
            output_path=output,
            tool="uv",
            generate_hashes=True,
        )

        assert config.project_root == project_root
        assert config.pyproject_path == pyproject
        assert config.output_path == output
        assert config.tool == "uv"
        assert config.generate_hashes is True

    def test_config_with_extras(self, tmp_path: Path) -> None:
        """Test configuration with extras."""
        config = ConstraintsConfig(
            project_root=tmp_path,
            pyproject_path=tmp_path / "pyproject.toml",
            output_path=tmp_path / "constraints.txt",
            include_extras=["dev", "test"],
        )

        assert config.include_extras == ["dev", "test"]

    def test_config_with_python_version(self, tmp_path: Path) -> None:
        """Test configuration with specific Python version."""
        config = ConstraintsConfig(
            project_root=tmp_path,
            pyproject_path=tmp_path / "pyproject.toml",
            output_path=tmp_path / "constraints.txt",
            python_version="3.12",
        )

        assert config.python_version == "3.12"


class TestConstraintsGenerator:
    """Tests for ConstraintsGenerator."""

    def test_initialization(self, tmp_path: Path) -> None:
        """Test ConstraintsGenerator initialization."""
        config = ConstraintsConfig(
            project_root=tmp_path,
            pyproject_path=tmp_path / "pyproject.toml",
            output_path=tmp_path / "constraints.txt",
        )
        generator = ConstraintsGenerator(config)
        assert generator.config == config

    @patch("chiron.deps.constraints.run_subprocess")
    def test_generate_with_uv_success(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test successful constraints generation with uv."""
        config = ConstraintsConfig(
            project_root=tmp_path,
            pyproject_path=tmp_path / "pyproject.toml",
            output_path=tmp_path / "constraints.txt",
            tool="uv",
        )
        generator = ConstraintsGenerator(config)

        # Mock successful subprocess
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = generator.generate()

        assert result is True
        mock_run.assert_called_once()
        # Check that uv command was used
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "uv"

    @patch("chiron.deps.constraints.run_subprocess")
    def test_generate_with_uv_failure(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test failed constraints generation with uv."""
        config = ConstraintsConfig(
            project_root=tmp_path,
            pyproject_path=tmp_path / "pyproject.toml",
            output_path=tmp_path / "constraints.txt",
            tool="uv",
        )
        generator = ConstraintsGenerator(config)

        # Mock failed subprocess
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error generating constraints"
        mock_run.return_value = mock_result

        result = generator.generate()

        assert result is False

    @patch("chiron.deps.constraints.run_subprocess")
    def test_generate_with_pip_tools(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test constraints generation with pip-tools."""
        config = ConstraintsConfig(
            project_root=tmp_path,
            pyproject_path=tmp_path / "pyproject.toml",
            output_path=tmp_path / "constraints.txt",
            tool="pip-tools",
        )
        generator = ConstraintsGenerator(config)

        # Mock successful subprocess
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = generator.generate()

        assert result is True
        mock_run.assert_called_once()
        # Check that pip-compile command was used
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "pip-compile"

    @patch("chiron.deps.constraints.run_subprocess")
    def test_generate_with_hashes(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test constraints generation with hash generation."""
        config = ConstraintsConfig(
            project_root=tmp_path,
            pyproject_path=tmp_path / "pyproject.toml",
            output_path=tmp_path / "constraints.txt",
            tool="uv",
            generate_hashes=True,
        )
        generator = ConstraintsGenerator(config)

        # Mock successful subprocess
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        generator.generate()

        # Check that --generate-hashes was passed
        call_args = mock_run.call_args[0][0]
        assert "--generate-hashes" in call_args

    @patch("chiron.deps.constraints.run_subprocess")
    def test_generate_with_extras(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test constraints generation with extras."""
        config = ConstraintsConfig(
            project_root=tmp_path,
            pyproject_path=tmp_path / "pyproject.toml",
            output_path=tmp_path / "constraints.txt",
            tool="uv",
            include_extras=["dev", "test"],
        )
        generator = ConstraintsGenerator(config)

        # Mock successful subprocess
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        generator.generate()

        # Check that extras were passed
        call_args = mock_run.call_args[0][0]
        assert "--extra" in call_args
        assert "dev" in call_args
        assert "test" in call_args
