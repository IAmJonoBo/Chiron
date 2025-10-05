"""Tests for chiron.deps modules - focusing on policy and constraints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from chiron.deps.constraints import ConstraintsConfig, ConstraintsGenerator
from chiron.deps.policy import (
    DependencyPolicy,
    PackagePolicy,
    PolicyEngine,
    PolicyViolation,
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


class TestPolicyEngine:
    """Tests for PolicyEngine."""

    def test_initialization(self) -> None:
        """Test PolicyEngine initialization."""
        policy = DependencyPolicy()
        engine = PolicyEngine(policy)
        assert engine.policy is policy
        assert isinstance(engine._last_upgrade_timestamps, dict)

    def test_check_package_allowed_default(self) -> None:
        """Test package allowed with default policy."""
        policy = DependencyPolicy(default_allowed=True)
        engine = PolicyEngine(policy)

        allowed, reason = engine.check_package_allowed("test-package")
        assert allowed is True
        assert reason is None

    def test_check_package_denied_default(self) -> None:
        """Test package denied with default policy."""
        policy = DependencyPolicy(default_allowed=False)
        engine = PolicyEngine(policy)

        allowed, reason = engine.check_package_allowed("test-package")
        assert allowed is False
        assert "not in allowlist" in reason.lower()

    def test_check_package_in_denylist(self) -> None:
        """Test package in denylist is blocked."""
        blocked_pkg = PackagePolicy(
            name="blocked-package",
            allowed=False,
            reason="Security vulnerability"
        )
        policy = DependencyPolicy()
        policy.denylist["blocked-package"] = blocked_pkg
        engine = PolicyEngine(policy)

        allowed, reason = engine.check_package_allowed("blocked-package")
        assert allowed is False
        assert "Security vulnerability" in reason

    def test_check_version_allowed_no_constraints(self) -> None:
        """Test version checking without constraints."""
        policy = DependencyPolicy()
        engine = PolicyEngine(policy)
        # No constraints = any version allowed
        allowed, reason = engine.check_version_allowed("test-package", "1.0.0")
        assert allowed is True
        assert reason is None

    def test_check_version_allowed_with_ceiling(self) -> None:
        """Test version checking with ceiling constraint."""
        pkg_policy = PackagePolicy(name="test-package", version_ceiling="2.0.0")
        policy = DependencyPolicy()
        policy.allowlist["test-package"] = pkg_policy
        engine = PolicyEngine(policy)

        # Version below ceiling should be allowed
        allowed, _ = engine.check_version_allowed("test-package", "1.0.0")
        assert allowed is True

        allowed, _ = engine.check_version_allowed("test-package", "2.0.0")
        assert allowed is True

        # Version above ceiling should be blocked
        allowed, reason = engine.check_version_allowed("test-package", "3.0.0")
        assert allowed is False
        assert "ceiling" in reason.lower()

    def test_check_version_allowed_with_floor(self) -> None:
        """Test version checking with floor constraint."""
        pkg_policy = PackagePolicy(name="test-package", version_floor="1.0.0")
        policy = DependencyPolicy()
        policy.allowlist["test-package"] = pkg_policy
        engine = PolicyEngine(policy)

        # Version below floor should be blocked
        allowed, reason = engine.check_version_allowed("test-package", "0.9.0")
        assert allowed is False
        assert "floor" in reason.lower()

        # Version at or above floor should be allowed
        allowed, _ = engine.check_version_allowed("test-package", "1.0.0")
        assert allowed is True

        allowed, _ = engine.check_version_allowed("test-package", "2.0.0")
        assert allowed is True

    def test_check_version_blocked_versions(self) -> None:
        """Test version checking with blocked versions."""
        pkg_policy = PackagePolicy(
            name="test-package",
            blocked_versions=["1.5.0", "1.5.1"],
        )
        policy = DependencyPolicy()
        policy.allowlist["test-package"] = pkg_policy
        engine = PolicyEngine(policy)

        # Non-blocked versions should be allowed
        allowed, _ = engine.check_version_allowed("test-package", "1.4.0")
        assert allowed is True

        allowed, _ = engine.check_version_allowed("test-package", "1.6.0")
        assert allowed is True

        # Blocked versions should not be allowed
        allowed, reason = engine.check_version_allowed("test-package", "1.5.0")
        assert allowed is False
        assert "blocked" in reason.lower()

        allowed, _ = engine.check_version_allowed("test-package", "1.5.1")
        assert allowed is False

    def test_check_upgrade_allowed_major_jump(self) -> None:
        """Test upgrade checking with major version jump limit."""
        policy = DependencyPolicy(max_major_version_jump=1)
        engine = PolicyEngine(policy)

        # Single major version jump should be allowed
        violations = engine.check_upgrade_allowed("test-package", "1.0.0", "2.0.0")
        major_jump_violations = [v for v in violations if v.violation_type == "major_version_jump"]
        assert len(major_jump_violations) == 0

        # Multiple major version jumps should create violations
        violations = engine.check_upgrade_allowed("test-package", "1.0.0", "3.0.0")
        major_jump_violations = [v for v in violations if v.violation_type == "major_version_jump"]
        assert len(major_jump_violations) > 0

    def test_check_upgrade_allowed_with_denied_package(self) -> None:
        """Test upgrade checking for denied package."""
        blocked_pkg = PackagePolicy(
            name="blocked-package",
            allowed=False,
            reason="Security vulnerability"
        )
        policy = DependencyPolicy()
        policy.denylist["blocked-package"] = blocked_pkg
        engine = PolicyEngine(policy)

        violations = engine.check_upgrade_allowed("blocked-package", "1.0.0", "1.1.0")
        assert len(violations) > 0
        assert any(v.violation_type == "package_denied" for v in violations)


class TestDependencyPolicy:
    """Tests for DependencyPolicy dataclass."""

    def test_default_policy(self) -> None:
        """Test creating a policy with defaults."""
        policy = DependencyPolicy()
        assert policy.default_allowed is True
        assert policy.max_major_version_jump == 1
        assert policy.require_security_review is True
        assert policy.allow_pre_releases is False

    def test_load_from_toml_missing_file(self, tmp_path: Path) -> None:
        """Test loading policy from non-existent TOML file."""
        config_path = tmp_path / "nonexistent.toml"
        policy = DependencyPolicy.from_toml(config_path)
        # Should return default policy
        assert policy.default_allowed is True


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
        # Check that uv command was used (path should contain 'uv')
        call_args = mock_run.call_args[0][0]
        assert "uv" in call_args[0]

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

    @patch("chiron.deps.constraints.shutil.which")
    @patch("chiron.deps.constraints.run_subprocess")
    def test_generate_with_pip_tools(
        self, mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path
    ) -> None:
        """Test constraints generation with pip-tools."""
        # Mock pip-compile being available
        mock_which.return_value = "/usr/bin/pip-compile"

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
        assert "pip-compile" in call_args[0]

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
