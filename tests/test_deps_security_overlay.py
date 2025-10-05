"""Tests for chiron.deps.security_overlay module - CVE tracking and security constraints."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from chiron.deps.security_overlay import (
    CVERecord,
    SecurityConstraint,
    SecurityOverlayManager,
    Severity,
)


class TestSeverity:
    """Tests for Severity enum."""

    def test_severity_values(self) -> None:
        """Test all severity levels."""
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"
        assert Severity.UNKNOWN.value == "unknown"

    def test_from_string_valid(self) -> None:
        """Test converting valid string to Severity."""
        assert Severity.from_string("critical") == Severity.CRITICAL
        assert Severity.from_string("HIGH") == Severity.HIGH
        assert Severity.from_string("Medium") == Severity.MEDIUM
        assert Severity.from_string("low") == Severity.LOW

    def test_from_string_invalid(self) -> None:
        """Test converting invalid string to Severity."""
        assert Severity.from_string("invalid") == Severity.UNKNOWN
        assert Severity.from_string("") == Severity.UNKNOWN


class TestCVERecord:
    """Tests for CVERecord dataclass."""

    def test_cve_record_creation(self) -> None:
        """Test creating a CVE record."""
        cve = CVERecord(
            cve_id="CVE-2024-1234",
            package="example-pkg",
            affected_versions=[">=1.0.0", "<1.2.0"],
            fixed_version="1.2.0",
            severity=Severity.HIGH,
            description="Security vulnerability",
            published_date="2024-01-01",
            references=["https://example.com/cve"],
        )

        assert cve.cve_id == "CVE-2024-1234"
        assert cve.package == "example-pkg"
        assert cve.affected_versions == [">=1.0.0", "<1.2.0"]
        assert cve.fixed_version == "1.2.0"
        assert cve.severity == Severity.HIGH
        assert cve.description == "Security vulnerability"
        assert cve.published_date == "2024-01-01"
        assert cve.references == ["https://example.com/cve"]

    def test_cve_record_defaults(self) -> None:
        """Test CVE record with default values."""
        cve = CVERecord(
            cve_id="CVE-2024-1234",
            package="example-pkg",
            affected_versions=[],
            fixed_version="1.0.0",
            severity=Severity.LOW,
        )

        assert cve.description == ""
        assert cve.published_date == ""
        assert cve.references == []


class TestSecurityConstraint:
    """Tests for SecurityConstraint dataclass."""

    def test_constraint_creation(self) -> None:
        """Test creating a security constraint."""
        constraint = SecurityConstraint(
            package="example-pkg",
            min_version="1.2.0",
            max_version="<2.0.0",
            reason="Security fix",
            cve_ids=["CVE-2024-1234"],
        )

        assert constraint.package == "example-pkg"
        assert constraint.min_version == "1.2.0"
        assert constraint.max_version == "<2.0.0"
        assert constraint.reason == "Security fix"
        assert constraint.cve_ids == ["CVE-2024-1234"]

    def test_constraint_defaults(self) -> None:
        """Test security constraint with default values."""
        constraint = SecurityConstraint(
            package="example-pkg",
            min_version="1.0.0",
        )

        assert constraint.max_version is None
        assert constraint.reason == ""
        assert constraint.cve_ids == []


class TestSecurityOverlayManager:
    """Tests for SecurityOverlayManager class."""

    def test_initialization_default(self, tmp_path: Path) -> None:
        """Test SecurityOverlayManager initialization with default file."""
        manager = SecurityOverlayManager()

        assert manager.overlay_file == Path("security-constraints.json")
        assert manager.constraints == {}
        assert manager.cve_database == {}

    def test_initialization_custom_file(self, tmp_path: Path) -> None:
        """Test SecurityOverlayManager initialization with custom file."""
        overlay_file = tmp_path / "custom-overlay.json"

        manager = SecurityOverlayManager(overlay_file)

        assert manager.overlay_file == overlay_file
        assert manager.constraints == {}

    def test_initialization_with_existing_file(self, tmp_path: Path) -> None:
        """Test SecurityOverlayManager loading existing overlay file."""
        overlay_file = tmp_path / "overlay.json"
        overlay_data = {
            "version": "1.0",
            "constraints": {
                "example-pkg": {
                    "min_version": "1.2.0",
                    "max_version": "<2.0.0",
                    "reason": "Security fix",
                    "cve_ids": ["CVE-2024-1234"],
                }
            },
            "cve_database": {
                "CVE-2024-1234": {
                    "package": "example-pkg",
                    "affected_versions": [">=1.0.0", "<1.2.0"],
                    "fixed_version": "1.2.0",
                    "severity": "high",
                    "description": "Security vulnerability",
                    "published_date": "2024-01-01",
                    "references": ["https://example.com"],
                }
            },
        }
        overlay_file.write_text(json.dumps(overlay_data))

        manager = SecurityOverlayManager(overlay_file)

        assert "example-pkg" in manager.constraints
        assert manager.constraints["example-pkg"].min_version == "1.2.0"
        assert "CVE-2024-1234" in manager.cve_database
        assert manager.cve_database["CVE-2024-1234"].severity == Severity.HIGH

    def test_save_overlay(self, tmp_path: Path) -> None:
        """Test saving security overlay to file."""
        overlay_file = tmp_path / "overlay.json"
        manager = SecurityOverlayManager(overlay_file)

        # Add a constraint
        manager.constraints["example-pkg"] = SecurityConstraint(
            package="example-pkg",
            min_version="1.2.0",
            max_version="<2.0.0",
            reason="Security fix",
            cve_ids=["CVE-2024-1234"],
        )

        # Add a CVE
        manager.cve_database["CVE-2024-1234"] = CVERecord(
            cve_id="CVE-2024-1234",
            package="example-pkg",
            affected_versions=[">=1.0.0", "<1.2.0"],
            fixed_version="1.2.0",
            severity=Severity.HIGH,
        )

        manager.save_overlay()

        # Verify file was created and contains correct data
        assert overlay_file.exists()
        saved_data = json.loads(overlay_file.read_text())

        assert "constraints" in saved_data
        assert "example-pkg" in saved_data["constraints"]
        assert saved_data["constraints"]["example-pkg"]["min_version"] == "1.2.0"
        assert "cve_database" in saved_data
        assert "CVE-2024-1234" in saved_data["cve_database"]

    def test_import_osv_scan_empty(self, tmp_path: Path) -> None:
        """Test importing OSV scan with no results."""
        overlay_file = tmp_path / "overlay.json"
        osv_file = tmp_path / "osv.json"

        osv_file.write_text(json.dumps({"results": []}))

        manager = SecurityOverlayManager(overlay_file)
        count = manager.import_osv_scan(osv_file)

        assert count == 0
        assert len(manager.cve_database) == 0

    def test_import_osv_scan_with_vulnerabilities(self, tmp_path: Path) -> None:
        """Test importing OSV scan with vulnerabilities."""
        overlay_file = tmp_path / "overlay.json"
        osv_file = tmp_path / "osv.json"

        osv_data = {
            "results": [
                {
                    "packages": [
                        {
                            "package": {"name": "example-pkg"},
                            "vulnerabilities": [
                                {
                                    "id": "CVE-2024-1234",
                                    "summary": "Security vulnerability",
                                    "published": "2024-01-01",
                                    "affected": [
                                        {
                                            "ranges": [
                                                {
                                                    "events": [
                                                        {"introduced": "1.0.0"},
                                                        {"fixed": "1.2.0"},
                                                    ]
                                                }
                                            ]
                                        }
                                    ],
                                    "database_specific": {
                                        "severity": [
                                            {"type": "CVSS_V3", "score": "7.5"}
                                        ]
                                    },
                                    "references": [{"url": "https://example.com"}],
                                }
                            ],
                        }
                    ]
                }
            ]
        }
        osv_file.write_text(json.dumps(osv_data))

        manager = SecurityOverlayManager(overlay_file)
        count = manager.import_osv_scan(osv_file)

        assert count == 1
        assert "CVE-2024-1234" in manager.cve_database

        cve = manager.cve_database["CVE-2024-1234"]
        assert cve.package == "example-pkg"
        assert cve.fixed_version == "1.2.0"
        assert cve.severity == Severity.HIGH

    def test_import_osv_scan_creates_constraints(self, tmp_path: Path) -> None:
        """Test that high severity CVEs create constraints."""
        overlay_file = tmp_path / "overlay.json"
        osv_file = tmp_path / "osv.json"

        osv_data = {
            "results": [
                {
                    "packages": [
                        {
                            "package": {"name": "example-pkg"},
                            "vulnerabilities": [
                                {
                                    "id": "CVE-2024-CRITICAL",
                                    "summary": "Critical vulnerability",
                                    "affected": [
                                        {
                                            "ranges": [
                                                {
                                                    "events": [
                                                        {"introduced": "1.0.0"},
                                                        {"fixed": "1.5.0"},
                                                    ]
                                                }
                                            ]
                                        }
                                    ],
                                    "database_specific": {
                                        "severity": [
                                            {"type": "CVSS_V3", "score": "9.5"}
                                        ]
                                    },
                                }
                            ],
                        }
                    ]
                }
            ]
        }
        osv_file.write_text(json.dumps(osv_data))

        manager = SecurityOverlayManager(overlay_file)
        count = manager.import_osv_scan(osv_file)

        assert count == 1
        # High/Critical severity should create a constraint
        assert "example-pkg" in manager.constraints
        constraint = manager.constraints["example-pkg"]
        assert constraint.min_version == "1.5.0"
        assert "CVE-2024-CRITICAL" in constraint.cve_ids

    def test_import_osv_scan_severity_mapping(self, tmp_path: Path) -> None:
        """Test OSV scan severity score mapping."""
        overlay_file = tmp_path / "overlay.json"
        osv_file = tmp_path / "osv.json"

        test_cases = [
            (9.5, Severity.CRITICAL),  # >= 9.0
            (7.5, Severity.HIGH),      # >= 7.0
            (5.0, Severity.MEDIUM),    # >= 4.0
            (2.0, Severity.LOW),       # < 4.0
        ]

        for score, expected_severity in test_cases:
            osv_data = {
                "results": [
                    {
                        "packages": [
                            {
                                "package": {"name": "test-pkg"},
                                "vulnerabilities": [
                                    {
                                        "id": f"CVE-{score}",
                                        "affected": [
                                            {
                                                "ranges": [
                                                    {
                                                        "events": [
                                                            {"introduced": "1.0.0"},
                                                            {"fixed": "1.1.0"},
                                                        ]
                                                    }
                                                ]
                                            }
                                        ],
                                        "database_specific": {
                                            "severity": [
                                                {"type": "CVSS_V3", "score": str(score)}
                                            ]
                                        },
                                    }
                                ],
                            }
                        ]
                    }
                ]
            }
            osv_file.write_text(json.dumps(osv_data))

            manager = SecurityOverlayManager(overlay_file)
            manager.import_osv_scan(osv_file)

            cve_id = f"CVE-{score}"
            assert cve_id in manager.cve_database
            assert manager.cve_database[cve_id].severity == expected_severity

    def test_import_osv_scan_no_fixed_version(self, tmp_path: Path) -> None:
        """Test importing CVE without fixed version."""
        overlay_file = tmp_path / "overlay.json"
        osv_file = tmp_path / "osv.json"

        osv_data = {
            "results": [
                {
                    "packages": [
                        {
                            "package": {"name": "example-pkg"},
                            "vulnerabilities": [
                                {
                                    "id": "CVE-NO-FIX",
                                    "affected": [
                                        {
                                            "ranges": [
                                                {
                                                    "events": [
                                                        {"introduced": "1.0.0"}
                                                    ]
                                                }
                                            ]
                                        }
                                    ],
                                    "database_specific": {
                                        "severity": [
                                            {"type": "CVSS_V3", "score": "9.0"}
                                        ]
                                    },
                                }
                            ],
                        }
                    ]
                }
            ]
        }
        osv_file.write_text(json.dumps(osv_data))

        manager = SecurityOverlayManager(overlay_file)
        count = manager.import_osv_scan(osv_file)

        assert count == 1
        assert "CVE-NO-FIX" in manager.cve_database
        # Should not create constraint without fixed version
        assert "example-pkg" not in manager.constraints

    def test_create_constraint_for_cve(self, tmp_path: Path) -> None:
        """Test _create_constraint_for_cve method."""
        overlay_file = tmp_path / "overlay.json"
        manager = SecurityOverlayManager(overlay_file)

        cve = CVERecord(
            cve_id="CVE-2024-1234",
            package="example-pkg",
            affected_versions=[">=1.0.0", "<1.2.0"],
            fixed_version="1.2.0",
            severity=Severity.CRITICAL,
        )

        manager._create_constraint_for_cve(cve)

        assert "example-pkg" in manager.constraints
        constraint = manager.constraints["example-pkg"]
        assert constraint.min_version == "1.2.0"
        assert "CVE-2024-1234" in constraint.cve_ids

    def test_create_constraint_updates_existing(self, tmp_path: Path) -> None:
        """Test updating existing constraint with new CVE."""
        overlay_file = tmp_path / "overlay.json"
        manager = SecurityOverlayManager(overlay_file)

        # Create initial constraint
        cve1 = CVERecord(
            cve_id="CVE-2024-0001",
            package="example-pkg",
            affected_versions=[">=1.0.0", "<1.2.0"],
            fixed_version="1.2.0",
            severity=Severity.HIGH,
        )
        manager._create_constraint_for_cve(cve1)

        # Add second CVE with higher fixed version
        cve2 = CVERecord(
            cve_id="CVE-2024-0002",
            package="example-pkg",
            affected_versions=[">=1.0.0", "<1.5.0"],
            fixed_version="1.5.0",
            severity=Severity.HIGH,
        )

        with patch.object(manager, '_compare_versions', return_value=1):
            manager._create_constraint_for_cve(cve2)

        constraint = manager.constraints["example-pkg"]
        assert constraint.min_version == "1.5.0"  # Updated to higher version
        assert len(constraint.cve_ids) == 2
        assert "CVE-2024-0001" in constraint.cve_ids
        assert "CVE-2024-0002" in constraint.cve_ids
