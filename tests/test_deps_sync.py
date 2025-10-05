"""Tests for chiron.deps.sync module - dependency synchronization."""

from __future__ import annotations

from pathlib import Path

import pytest
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from chiron.deps.sync import (
    ALLOWED_DRIFT_STATUSES,
    ContractError,
    ManifestWriteError,
    PackageRecord,
    Profile,
)


class TestPackageRecord:
    """Tests for PackageRecord dataclass."""

    def test_package_record_initialization(self) -> None:
        """Test PackageRecord initialization."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            constraint=">=2.28.0,<3.0.0",
            locked="2.31.0",
        )
        assert record.name == "requests"
        assert record.profile == "runtime"
        assert record.constraint == ">=2.28.0,<3.0.0"
        assert record.locked == "2.31.0"

    def test_package_record_with_extras(self) -> None:
        """Test PackageRecord with extras."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            extras=("security", "socks"),
            constraint=">=2.28.0",
            locked="2.31.0",
        )
        assert record.extras == ("security", "socks")

    def test_package_record_with_marker(self) -> None:
        """Test PackageRecord with environment marker."""
        record = PackageRecord(
            name="pywin32",
            profile="runtime",
            constraint=">=305",
            locked="305",
            marker='sys_platform == "win32"',
        )
        assert record.marker == 'sys_platform == "win32"'

    def test_requirement_prefer_locked(self) -> None:
        """Test requirement generation preferring locked version."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            constraint=">=2.28.0",
            locked="2.31.0",
        )
        req = record.requirement(prefer_locked=True)
        assert req == "requests==2.31.0"

    def test_requirement_without_locked(self) -> None:
        """Test requirement generation without locked version."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            constraint=">=2.28.0",
        )
        req = record.requirement(prefer_locked=False)
        assert req == "requests>=2.28.0"

    def test_requirement_with_marker(self) -> None:
        """Test requirement generation with environment marker."""
        record = PackageRecord(
            name="pywin32",
            profile="runtime",
            constraint=">=305",
            locked="305",
            marker='sys_platform == "win32"',
        )
        req = record.requirement()
        assert req == 'pywin32==305; sys_platform == "win32"'

    def test_requirement_with_extras(self) -> None:
        """Test requirement generation with extras."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            extras=("security", "socks"),
            locked="2.31.0",
        )
        req = record.requirement()
        assert req == "requests[security,socks]==2.31.0"

    def test_requirement_without_marker_locked(self) -> None:
        """Test requirement_without_marker with locked version."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            constraint=">=2.28.0",
            locked="2.31.0",
        )
        req = record.requirement_without_marker(prefer_locked=True)
        assert req == "requests==2.31.0"

    def test_requirement_without_marker_constraint(self) -> None:
        """Test requirement_without_marker with constraint."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            constraint=">=2.28.0,<3.0.0",
        )
        req = record.requirement_without_marker(prefer_locked=False)
        assert req == "requests>=2.28.0,<3.0.0"

    def test_requirement_without_marker_locked_fallback(self) -> None:
        """Test requirement_without_marker falls back to locked."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            locked="2.31.0",
        )
        req = record.requirement_without_marker(prefer_locked=False)
        assert req == "requests==2.31.0"

    def test_requirement_missing_both_raises(self) -> None:
        """Test that missing both constraint and locked raises error."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
        )
        with pytest.raises(ContractError, match="missing constraint and locked"):
            record.requirement_without_marker()

    def test_constraint_satisfied_true(self) -> None:
        """Test constraint_satisfied when constraint is satisfied."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            constraint=">=2.28.0,<3.0.0",
            locked="2.31.0",
        )
        assert record.constraint_satisfied() is True

    def test_constraint_satisfied_false(self) -> None:
        """Test constraint_satisfied when constraint is not satisfied."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            constraint=">=3.0.0",
            locked="2.31.0",
        )
        assert record.constraint_satisfied() is False

    def test_constraint_satisfied_no_constraint(self) -> None:
        """Test constraint_satisfied when no constraint is present."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            locked="2.31.0",
        )
        assert record.constraint_satisfied() is True

    def test_constraint_satisfied_no_locked(self) -> None:
        """Test constraint_satisfied when no locked version is present."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            constraint=">=2.28.0",
        )
        assert record.constraint_satisfied() is True

    def test_format_name_simple(self) -> None:
        """Test _format_name with simple package."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            locked="2.31.0",
        )
        assert record._format_name() == "requests"

    def test_format_name_with_extras(self) -> None:
        """Test _format_name with extras."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            extras=("security", "socks"),
            locked="2.31.0",
        )
        formatted = record._format_name()
        assert formatted == "requests[security,socks]"


class TestProfile:
    """Tests for Profile dataclass."""

    def test_profile_initialization(self) -> None:
        """Test Profile initialization."""
        profile = Profile(
            name="runtime",
            raw={"description": "Core runtime dependencies"},
        )
        assert profile.name == "runtime"
        assert profile.packages == []

    def test_profile_with_packages(self) -> None:
        """Test Profile with packages."""
        record1 = PackageRecord(
            name="requests",
            profile="runtime",
            locked="2.31.0",
        )
        record2 = PackageRecord(
            name="urllib3",
            profile="runtime",
            locked="2.0.0",
        )
        profile = Profile(
            name="runtime",
            raw={},
            packages=[record1, record2],
        )
        assert len(profile.packages) == 2
        assert profile.packages[0].name == "requests"
        assert profile.packages[1].name == "urllib3"

    def test_profile_condition_property(self) -> None:
        """Test Profile condition property."""
        profile = Profile(
            name="optional",
            raw={"condition": "extra == 'dev'"},
        )
        assert profile.condition == "extra == 'dev'"

    def test_profile_condition_none(self) -> None:
        """Test Profile condition when not present."""
        profile = Profile(
            name="runtime",
            raw={},
        )
        assert profile.condition is None


class TestContractError:
    """Tests for ContractError exception."""

    def test_contract_error_creation(self) -> None:
        """Test creating a ContractError."""
        error = ContractError("Contract parsing failed")
        assert str(error) == "Contract parsing failed"
        assert isinstance(error, RuntimeError)


class TestManifestWriteError:
    """Tests for ManifestWriteError exception."""

    def test_manifest_write_error_creation(self) -> None:
        """Test creating a ManifestWriteError."""
        error = ManifestWriteError("Failed to write manifest")
        assert str(error) == "Failed to write manifest"
        assert isinstance(error, RuntimeError)


class TestConstants:
    """Tests for module constants."""

    def test_allowed_drift_statuses(self) -> None:
        """Test ALLOWED_DRIFT_STATUSES constant."""
        assert "drift" in ALLOWED_DRIFT_STATUSES
        assert "exception" in ALLOWED_DRIFT_STATUSES
        assert len(ALLOWED_DRIFT_STATUSES) == 2


class TestPackageRecordEdgeCases:
    """Tests for edge cases in PackageRecord."""

    def test_empty_extras_tuple(self) -> None:
        """Test PackageRecord with empty extras tuple."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            extras=(),
            locked="2.31.0",
        )
        assert record._format_name() == "requests"

    def test_single_extra(self) -> None:
        """Test PackageRecord with single extra."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            extras=("security",),
            locked="2.31.0",
        )
        assert record._format_name() == "requests[security]"

    def test_constraint_with_multiple_specifiers(self) -> None:
        """Test constraint satisfaction with multiple specifiers."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            constraint=">=2.28.0,<3.0.0,!=2.29.0",
            locked="2.31.0",
        )
        assert record.constraint_satisfied() is True

    def test_constraint_with_incompatible_version(self) -> None:
        """Test constraint with excluded version."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            constraint=">=2.28.0,!=2.31.0",
            locked="2.31.0",
        )
        assert record.constraint_satisfied() is False

    def test_requirement_prefers_constraint_over_locked(self) -> None:
        """Test that prefer_locked=False uses constraint."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            constraint=">=2.28.0,<3.0.0",
            locked="2.31.0",
        )
        req = record.requirement(prefer_locked=False)
        assert req == "requests>=2.28.0,<3.0.0"

    def test_package_record_with_all_fields(self) -> None:
        """Test PackageRecord with all optional fields."""
        record = PackageRecord(
            name="requests",
            profile="runtime",
            constraint=">=2.28.0",
            locked="2.31.0",
            extras=("security",),
            marker='python_version >= "3.8"',
            owner="team@example.com",
            status="active",
            notes="Security dependency",
        )
        assert record.owner == "team@example.com"
        assert record.status == "active"
        assert record.notes == "Security dependency"

    def test_profile_with_non_dict_raw(self) -> None:
        """Test Profile with non-dict raw value."""
        # The Profile should still work but condition will be None
        profile = Profile(
            name="test",
            raw="not a dict",  # type: ignore
        )
        assert profile.condition is None
