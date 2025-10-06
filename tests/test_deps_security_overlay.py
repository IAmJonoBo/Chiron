"""Security overlay regression tests to improve coverage."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from chiron.deps import security_overlay
from chiron.deps.security_overlay import (
    CVERecord,
    SecurityConstraint,
    SecurityOverlayManager,
    Severity,
)


@pytest.fixture()
def fixed_datetime(monkeypatch: pytest.MonkeyPatch) -> datetime:
    frozen = datetime(2024, 1, 1, 12, 0, 0)

    class FrozenDateTime:
        @classmethod
        def now(cls) -> datetime:
            return frozen

    monkeypatch.setattr(security_overlay, "datetime", FrozenDateTime)
    return frozen


def create_overlay(tmp_path: Path) -> Path:
    overlay_data = {
        "version": "1.0",
        "updated": "2023-01-01T00:00:00",
        "constraints": {
            "demo": {
                "min_version": "1.2.3",
                "max_version": "<2.0",
                "reason": "High severity CVE",
                "cve_ids": ["CVE-1234"],
            }
        },
        "cve_database": {
            "CVE-1234": {
                "package": "demo",
                "affected_versions": [">=1.0"],
                "fixed_version": "1.2.3",
                "severity": "high",
                "description": "Sample",
                "published_date": "2022-12-01",
                "references": ["https://example.com"],
            }
        },
    }
    overlay_path = tmp_path / "overlay.json"
    overlay_path.write_text(json.dumps(overlay_data))
    return overlay_path


def test_load_and_save_overlay_round_trip(tmp_path: Path, fixed_datetime: datetime) -> None:
    overlay_path = create_overlay(tmp_path)
    manager = SecurityOverlayManager(overlay_path)
    assert "demo" in manager.constraints
    assert manager.cve_database["CVE-1234"].severity is Severity.HIGH

    manager.save_overlay()
    saved = json.loads(overlay_path.read_text())
    assert saved["version"] == "1.0"
    assert saved["updated"] == fixed_datetime.isoformat()


def test_import_osv_scan_creates_constraints(tmp_path: Path, fixed_datetime: datetime, capsys: pytest.CaptureFixture[str]) -> None:
    osv_payload = {
        "results": [
            {
                "packages": [
                    {
                        "package": {"name": "demo"},
                        "vulnerabilities": [
                            {
                                "id": "CVE-9999",
                                "summary": "Critical bug",
                                "published": "2024-01-01",
                                "references": [{"url": "https://example.com/cve"}],
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
                                        {"type": "CVSS_V3", "score": "9.1"},
                                    ]
                                },
                            }
                        ],
                    }
                ],
            }
        ]
    }

    overlay_path = tmp_path / "overlay.json"
    osv_path = tmp_path / "osv.json"
    overlay_path.write_text(json.dumps({"constraints": {}, "cve_database": {}}))
    osv_path.write_text(json.dumps(osv_payload))

    manager = SecurityOverlayManager(overlay_path)
    imported = manager.import_osv_scan(osv_path)
    captured = capsys.readouterr().out

    assert imported == 1
    assert "CVE-9999" in manager.cve_database
    assert manager.constraints["demo"].min_version == "1.5.0"
    assert "Imported 1 CVEs" in captured


def test_create_constraint_updates_existing(tmp_path: Path, fixed_datetime: datetime) -> None:
    overlay_path = create_overlay(tmp_path)
    manager = SecurityOverlayManager(overlay_path)
    manager.constraints["demo"] = SecurityConstraint(
        package="demo",
        min_version="1.0.0",
        max_version="<2.0",
        reason="Existing",
        cve_ids=["CVE-0001"],
    )

    cve = CVERecord(
        cve_id="CVE-1234",
        package="demo",
        affected_versions=[">=1.0"],
        fixed_version="1.5.0",
        severity=Severity.HIGH,
    )
    manager._create_constraint_for_cve(cve)
    constraint = manager.constraints["demo"]
    assert constraint.min_version == "1.5.0"
    assert "CVE-1234" in constraint.cve_ids


def test_compare_and_extract_helpers() -> None:
    manager = SecurityOverlayManager(Path("non-existent.json"))
    assert manager._extract_major_version("3.4.5") == 3
    assert manager._extract_major_version("v2") is None
    assert manager._compare_versions("1.2.3", "1.2.3") == 0
    assert manager._compare_versions("1.2.3", "2.0.0") < 0
    assert manager._compare_versions("2.0", "1.9.9") > 0


def test_generate_constraints_file(tmp_path: Path, fixed_datetime: datetime) -> None:
    overlay_path = create_overlay(tmp_path)
    manager = SecurityOverlayManager(overlay_path)
    output = tmp_path / "constraints.txt"
    manager.generate_constraints_file(output)
    content = output.read_text()
    assert "# Security constraints overlay" in content
    assert "demo>=1.2.3" in content
    assert "<2.0" in content


def test_check_package_version_enforces_bounds(tmp_path: Path) -> None:
    overlay_path = create_overlay(tmp_path)
    manager = SecurityOverlayManager(overlay_path)

    safe, violations = manager.check_package_version("demo", "1.2.3")
    assert safe is True
    assert violations == []

    safe, violations = manager.check_package_version("demo", "1.0.0")
    assert safe is False
    assert any("below minimum" in v for v in violations)

    safe, violations = manager.check_package_version("demo", "2.1.0")
    assert safe is False
    assert any("exceeds maximum" in v for v in violations)


def test_get_recommendations_lists_context(tmp_path: Path) -> None:
    overlay_path = create_overlay(tmp_path)
    manager = SecurityOverlayManager(overlay_path)
    recommendations = manager.get_recommendations("demo")
    assert "Minimum safe version: 1.2.3" in recommendations
    assert any("CVE-1234" in item for item in recommendations)
    assert manager.get_recommendations("missing") == []
