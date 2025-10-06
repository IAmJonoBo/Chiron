"""Tests for chiron.deps.guard module - policy enforcement and upgrade guard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from chiron.deps.guard import (
    RISK_BLOCKED,
    RISK_NEEDS_REVIEW,
    RISK_SAFE,
    PackageAssessment,
    SourceSummary,
    _coerce_int,
    _coerce_str,
    _coerce_str_list,
    _evaluate_contract_metadata,
    _extract_environment_alignment,
    _extract_signature_policy,
    _extract_snoozes,
    _load_contract,
    _load_optional_json,
    _parse_contract_timestamp,
    _read_json,
)


class TestPackageAssessment:
    """Tests for PackageAssessment dataclass."""

    def test_initialization_defaults(self) -> None:
        """Test PackageAssessment initialization with defaults."""
        assessment = PackageAssessment(name="requests")
        assert assessment.name == "requests"
        assert assessment.current is None
        assert assessment.candidate is None
        assert assessment.risk == RISK_SAFE
        assert assessment.reasons == []

    def test_initialization_with_values(self) -> None:
        """Test PackageAssessment initialization with values."""
        assessment = PackageAssessment(
            name="requests",
            current="2.28.0",
            candidate="2.31.0",
            risk=RISK_NEEDS_REVIEW,
            reasons=["Minor version upgrade"],
        )
        assert assessment.name == "requests"
        assert assessment.current == "2.28.0"
        assert assessment.candidate == "2.31.0"
        assert assessment.risk == RISK_NEEDS_REVIEW
        assert assessment.reasons == ["Minor version upgrade"]

    def test_elevate_risk_to_higher_level(self) -> None:
        """Test elevating risk to a higher level."""
        assessment = PackageAssessment(name="requests", risk=RISK_SAFE)
        assessment.elevate(RISK_NEEDS_REVIEW, "Security vulnerability")

        assert assessment.risk == RISK_NEEDS_REVIEW
        assert "Security vulnerability" in assessment.reasons

    def test_elevate_risk_to_blocked(self) -> None:
        """Test elevating risk to blocked."""
        assessment = PackageAssessment(name="requests", risk=RISK_NEEDS_REVIEW)
        assessment.elevate(RISK_BLOCKED, "Critical CVE")

        assert assessment.risk == RISK_BLOCKED
        assert "Critical CVE" in assessment.reasons

    def test_elevate_risk_no_change_when_lower(self) -> None:
        """Test that risk doesn't decrease when elevating."""
        assessment = PackageAssessment(name="requests", risk=RISK_BLOCKED)
        assessment.elevate(RISK_SAFE, "All good")

        assert assessment.risk == RISK_BLOCKED
        assert "All good" in assessment.reasons

    def test_elevate_risk_without_reason(self) -> None:
        """Test elevating risk without providing a reason."""
        assessment = PackageAssessment(name="requests", risk=RISK_SAFE)
        assessment.elevate(RISK_NEEDS_REVIEW)

        assert assessment.risk == RISK_NEEDS_REVIEW
        assert assessment.reasons == []


class TestSourceSummary:
    """Tests for SourceSummary dataclass."""

    def test_initialization(self, tmp_path: Path) -> None:
        """Test SourceSummary initialization."""
        raw_path = tmp_path / "preflight.json"
        summary = SourceSummary(
            name="preflight",
            state="ok",
            message="All checks passed",
            raw_path=str(raw_path),
        )
        assert summary.name == "preflight"
        assert summary.state == "ok"
        assert summary.message == "All checks passed"
        assert summary.raw_path == str(raw_path)

    def test_initialization_with_none(self) -> None:
        """Test SourceSummary with None values."""
        summary = SourceSummary(
            name="renovate", state="missing", message=None, raw_path=None
        )
        assert summary.name == "renovate"
        assert summary.state == "missing"
        assert summary.message is None
        assert summary.raw_path is None


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_coerce_str_with_string(self) -> None:
        """Test _coerce_str with a string."""
        assert _coerce_str("test") == "test"

    def test_coerce_str_with_empty_string(self) -> None:
        """Test _coerce_str with an empty string."""
        assert _coerce_str("") is None

    def test_coerce_str_with_none(self) -> None:
        """Test _coerce_str with None."""
        assert _coerce_str(None) is None

    def test_coerce_str_with_number(self) -> None:
        """Test _coerce_str with a number."""
        assert _coerce_str(123) == "123"

    def test_coerce_int_with_int(self) -> None:
        """Test _coerce_int with an integer."""
        assert _coerce_int(42) == 42

    def test_coerce_int_with_string_number(self) -> None:
        """Test _coerce_int with a string number."""
        assert _coerce_int("42") == 42

    def test_coerce_int_with_none(self) -> None:
        """Test _coerce_int with None."""
        assert _coerce_int(None) is None

    def test_coerce_int_with_invalid_string(self) -> None:
        """Test _coerce_int with an invalid string."""
        assert _coerce_int("not a number") is None

    def test_coerce_str_list_with_list(self) -> None:
        """Test _coerce_str_list with a list."""
        assert _coerce_str_list(["a", "b", "c"]) == ["a", "b", "c"]

    def test_coerce_str_list_with_mixed_types(self) -> None:
        """Test _coerce_str_list with mixed types."""
        assert _coerce_str_list([1, "b", None, 3]) == ["1", "b", "3"]

    def test_coerce_str_list_with_none(self) -> None:
        """Test _coerce_str_list with None."""
        assert _coerce_str_list(None) == []

    def test_coerce_str_list_with_non_list(self) -> None:
        """Test _coerce_str_list with a non-list."""
        assert _coerce_str_list("not a list") == []


class TestReadJson:
    """Tests for _read_json function."""

    def test_read_json_success(self, tmp_path: Path) -> None:
        """Test reading valid JSON file."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}')

        result = _read_json(json_file)
        assert result == {"key": "value"}

    def test_read_json_file_not_found(self, tmp_path: Path) -> None:
        """Test reading non-existent JSON file."""
        with pytest.raises(FileNotFoundError):
            _read_json(tmp_path / "nonexistent.json")

    def test_read_json_invalid_json(self, tmp_path: Path) -> None:
        """Test reading invalid JSON file."""
        json_file = tmp_path / "invalid.json"
        json_file.write_text("not valid json")

        with pytest.raises(ValueError, match="Invalid JSON"):
            _read_json(json_file)


class TestLoadOptionalJson:
    """Tests for _load_optional_json function."""

    def test_load_optional_json_none_path(self) -> None:
        """Test loading with None path."""
        summary, data = _load_optional_json(None, "test")
        assert summary.name == "test"
        assert summary.state == "missing"
        assert summary.message == "path not provided"
        assert data is None

    def test_load_optional_json_missing_file(self, tmp_path: Path) -> None:
        """Test loading missing file."""
        summary, data = _load_optional_json(tmp_path / "missing.json", "test")
        assert summary.state == "missing"
        assert summary.message == "file not found"
        assert data is None

    def test_load_optional_json_success(self, tmp_path: Path) -> None:
        """Test loading valid JSON file."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}')

        summary, data = _load_optional_json(json_file, "test")
        assert summary.state == "ok"
        assert summary.message is None
        assert data == {"key": "value"}

    def test_load_optional_json_invalid_json(self, tmp_path: Path) -> None:
        """Test loading invalid JSON file."""
        json_file = tmp_path / "invalid.json"
        json_file.write_text("not json")

        summary, data = _load_optional_json(json_file, "test")
        assert summary.state == "error"
        assert "Invalid JSON" in summary.message
        assert data is None


class TestLoadContract:
    """Tests for _load_contract function."""

    def test_load_contract_none_path(self) -> None:
        """Test loading contract with None path."""
        summary, data = _load_contract(None)
        assert summary.state == "missing"
        assert summary.message == "path not provided"
        assert data is None

    def test_load_contract_missing_file(self, tmp_path: Path) -> None:
        """Test loading missing contract file."""
        summary, data = _load_contract(tmp_path / "missing.toml")
        assert summary.state == "missing"
        assert summary.message == "file not found"
        assert data is None

    def test_load_contract_success(self, tmp_path: Path) -> None:
        """Test loading valid TOML contract."""
        toml_file = tmp_path / "contract.toml"
        toml_file.write_text('[contract]\nstatus = "active"\n')

        summary, data = _load_contract(toml_file)
        assert summary.state == "ok"
        assert summary.message is None
        assert data is not None
        assert "contract" in data

    def test_load_contract_invalid_toml(self, tmp_path: Path) -> None:
        """Test loading invalid TOML file."""
        toml_file = tmp_path / "invalid.toml"
        toml_file.write_text("[invalid toml")

        summary, data = _load_contract(toml_file)
        assert summary.state == "error"
        assert data is None


class TestParseContractTimestamp:
    """Tests for _parse_contract_timestamp function."""

    def test_parse_none(self) -> None:
        """Test parsing None timestamp."""
        assert _parse_contract_timestamp(None) is None

    def test_parse_empty_string(self) -> None:
        """Test parsing empty string."""
        assert _parse_contract_timestamp("") is None

    def test_parse_iso_with_z(self) -> None:
        """Test parsing ISO timestamp with Z."""
        result = _parse_contract_timestamp("2025-01-01T12:00:00Z")
        assert result is not None
        assert result.tzinfo == UTC

    def test_parse_iso_with_timezone(self) -> None:
        """Test parsing ISO timestamp with timezone."""
        result = _parse_contract_timestamp("2025-01-01T12:00:00+00:00")
        assert result is not None
        assert result.tzinfo == UTC

    def test_parse_iso_without_timezone(self) -> None:
        """Test parsing ISO timestamp without timezone."""
        result = _parse_contract_timestamp("2025-01-01T12:00:00")
        assert result is not None
        assert result.tzinfo == UTC

    def test_parse_invalid_timestamp(self) -> None:
        """Test parsing invalid timestamp."""
        assert _parse_contract_timestamp("not a timestamp") is None


class TestEvaluateContractMetadata:
    """Tests for _evaluate_contract_metadata function."""

    def test_evaluate_contract_fresh(self) -> None:
        """Test evaluating fresh contract."""
        now = datetime.now(UTC)
        data = {
            "contract": {
                "status": "active",
                "last_validated": now.isoformat(),
                "default_review_days": 14,
            }
        }

        result = _evaluate_contract_metadata(data)
        assert result["status"] == "fresh"
        assert result["risk"] == RISK_SAFE
        assert result["age_days"] == 0

    def test_evaluate_contract_stale(self) -> None:
        """Test evaluating stale contract."""
        old_date = datetime.now(UTC) - timedelta(days=20)
        data = {
            "contract": {
                "status": "active",
                "last_validated": old_date.isoformat(),
                "default_review_days": 14,
            }
        }

        result = _evaluate_contract_metadata(data)
        assert result["status"] == "stale"
        assert result["risk"] == RISK_NEEDS_REVIEW
        assert result["age_days"] == 20

    def test_evaluate_contract_expired(self) -> None:
        """Test evaluating expired contract."""
        old_date = datetime.now(UTC) - timedelta(days=40)
        data = {
            "contract": {
                "status": "active",
                "last_validated": old_date.isoformat(),
                "default_review_days": 14,
            }
        }

        result = _evaluate_contract_metadata(data)
        assert result["status"] == "expired"
        assert result["risk"] == RISK_BLOCKED
        assert result["age_days"] == 40

    def test_evaluate_contract_missing_last_validated(self) -> None:
        """Test evaluating contract without last_validated."""
        data = {"contract": {"status": "active"}}

        result = _evaluate_contract_metadata(data)
        assert result["status"] == "unknown"
        assert result["risk"] == RISK_NEEDS_REVIEW
        assert result["age_days"] is None

    def test_evaluate_contract_no_contract_section(self) -> None:
        """Test evaluating data without contract section."""
        data = {}

        result = _evaluate_contract_metadata(data)
        assert result["status"] == "unknown"
        assert result["risk"] == RISK_NEEDS_REVIEW


class TestExtractSignaturePolicy:
    """Tests for _extract_signature_policy function."""

    def test_extract_signature_policy_complete(self) -> None:
        """Test extracting complete signature policy."""
        data = {
            "policies": {
                "signatures": {
                    "required": True,
                    "keyring": "production",
                    "enforced_artifacts": ["wheelhouse", "bundle"],
                    "attestation_required": ["package.tar.gz"],
                    "grace_period_days": 7,
                    "trusted_publishers": ["pypi.org"],
                    "allow_unsigned_profiles": ["dev"],
                }
            }
        }

        policy = _extract_signature_policy(data)
        assert policy is not None
        assert policy["required"] is True
        assert policy["keyring"] == "production"
        assert policy["enforced_artifacts"] == ["wheelhouse", "bundle"]
        assert policy["grace_period_days"] == 7

    def test_extract_signature_policy_missing_policies(self) -> None:
        """Test extracting signature policy when policies section is missing."""
        data = {}
        assert _extract_signature_policy(data) is None

    def test_extract_signature_policy_missing_signatures(self) -> None:
        """Test extracting signature policy when signatures section is missing."""
        data = {"policies": {}}
        assert _extract_signature_policy(data) is None


class TestExtractSnoozes:
    """Tests for _extract_snoozes function."""

    def test_extract_snoozes_complete(self) -> None:
        """Test extracting complete snoozes."""
        data = {
            "governance": {
                "snoozes": [
                    {
                        "id": "CVE-2024-1234",
                        "scope": {"package": "requests"},
                        "reason": "False positive",
                        "expires_at": "2025-12-31",
                        "requested_by": "dev@example.com",
                        "approver": "security@example.com",
                    }
                ]
            }
        }

        snoozes = _extract_snoozes(data)
        assert len(snoozes) == 1
        assert snoozes[0]["id"] == "CVE-2024-1234"
        assert snoozes[0]["reason"] == "False positive"

    def test_extract_snoozes_missing_governance(self) -> None:
        """Test extracting snoozes when governance section is missing."""
        data = {}
        assert _extract_snoozes(data) == []

    def test_extract_snoozes_empty_list(self) -> None:
        """Test extracting empty snoozes list."""
        data = {"governance": {"snoozes": []}}
        assert _extract_snoozes(data) == []

    def test_extract_snoozes_invalid_entries(self) -> None:
        """Test extracting snoozes with invalid entries."""
        data = {"governance": {"snoozes": ["invalid", {"no_id": "test"}]}}
        snoozes = _extract_snoozes(data)
        assert snoozes == []


class TestExtractEnvironmentAlignment:
    """Tests for _extract_environment_alignment function."""

    def test_extract_environment_alignment_complete(self) -> None:
        """Test extracting complete environment alignment."""
        data = {
            "environment_alignment": {
                "alert_channel": "#security",
                "default_sync_window_days": 7,
                "environments": [
                    {
                        "name": "production",
                        "profiles": ["runtime"],
                        "lockfiles": ["poetry.lock"],
                        "model_registry": "s3://models",
                        "last_synced": "2025-01-01",
                        "sync_window_days": 14,
                        "requires_signatures": True,
                    }
                ],
            }
        }

        alignment = _extract_environment_alignment(data)
        assert alignment is not None
        assert alignment["alert_channel"] == "#security"
        assert alignment["default_sync_window_days"] == 7
        assert len(alignment["environments"]) == 1
        assert alignment["environments"][0]["name"] == "production"

    def test_extract_environment_alignment_missing(self) -> None:
        """Test extracting environment alignment when missing."""
        data = {}
        assert _extract_environment_alignment(data) is None

    def test_extract_environment_alignment_empty_environments(self) -> None:
        """Test extracting environment alignment with empty environments."""
        data = {"environment_alignment": {"environments": []}}
        alignment = _extract_environment_alignment(data)
        assert alignment is not None
        assert alignment["environments"] == []
