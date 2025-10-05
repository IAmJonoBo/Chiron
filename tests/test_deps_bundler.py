"""Tests for chiron.deps.bundler module."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from chiron.deps.bundler import BundleMetadata, WheelhouseBundler


class TestBundleMetadata:
    """Tests for BundleMetadata class."""

    def test_metadata_creation(self) -> None:
        """Test creating metadata with required fields."""
        metadata = BundleMetadata(
            created_at="2025-01-01T00:00:00Z",
            commit_sha="abc123",
            wheel_count=5,
        )

        assert metadata.created_at == "2025-01-01T00:00:00Z"
        assert metadata.commit_sha == "abc123"
        assert metadata.wheel_count == 5
        assert metadata.total_size_bytes == 0
        assert isinstance(metadata.checksums, dict)

    def test_metadata_to_dict(self) -> None:
        """Test converting metadata to dictionary."""
        metadata = BundleMetadata(
            created_at="2025-01-01T00:00:00Z",
            commit_sha="abc123",
            git_ref="main",
            python_version="3.12",
            platform="linux",
            wheel_count=3,
            total_size_bytes=1024,
            checksums={"file1.whl": "hash1", "file2.whl": "hash2"},
        )

        result = metadata.to_dict()

        assert result["created_at"] == "2025-01-01T00:00:00Z"
        assert result["commit_sha"] == "abc123"
        assert result["git_ref"] == "main"
        assert result["python_version"] == "3.12"
        assert result["platform"] == "linux"
        assert result["wheel_count"] == 3
        assert result["total_size_bytes"] == 1024
        assert result["checksums"]["file1.whl"] == "hash1"
        assert result["checksums"]["file2.whl"] == "hash2"

    def test_metadata_defaults(self) -> None:
        """Test metadata default values."""
        metadata = BundleMetadata(created_at="2025-01-01T00:00:00Z")

        assert metadata.commit_sha is None
        assert metadata.git_ref is None
        assert metadata.python_version is None
        assert metadata.platform is None
        assert metadata.wheel_count == 0
        assert metadata.total_size_bytes == 0
        assert metadata.checksums == {}


class TestWheelhouseBundler:
    """Tests for WheelhouseBundler class."""

    def test_bundler_init_with_existing_dir(self, tmp_path: Path) -> None:
        """Test initializing bundler with existing directory."""
        wheelhouse_dir = tmp_path / "wheelhouse"
        wheelhouse_dir.mkdir()

        bundler = WheelhouseBundler(wheelhouse_dir)

        assert bundler.wheelhouse_dir == wheelhouse_dir

    def test_bundler_init_with_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test initializing bundler with non-existent directory."""
        wheelhouse_dir = tmp_path / "nonexistent"

        with pytest.raises(ValueError, match="Wheelhouse directory not found"):
            WheelhouseBundler(wheelhouse_dir)

    def test_create_bundle_with_no_wheels(self, tmp_path: Path) -> None:
        """Test creating bundle with no wheels."""
        wheelhouse_dir = tmp_path / "wheelhouse"
        wheelhouse_dir.mkdir()
        bundler = WheelhouseBundler(wheelhouse_dir)

        output_path = tmp_path / "bundle.tar.gz"

        with pytest.raises(ValueError, match="No wheels found"):
            bundler.create_bundle(output_path)

    def test_create_bundle_with_wheels(self, tmp_path: Path) -> None:
        """Test creating bundle with wheels."""
        wheelhouse_dir = tmp_path / "wheelhouse"
        wheelhouse_dir.mkdir()

        # Create dummy wheel files
        wheel1 = wheelhouse_dir / "package1-1.0.0-py3-none-any.whl"
        wheel2 = wheelhouse_dir / "package2-2.0.0-py3-none-any.whl"
        wheel1.write_text("wheel1 content")
        wheel2.write_text("wheel2 content")

        bundler = WheelhouseBundler(wheelhouse_dir)
        output_path = tmp_path / "bundle.tar.gz"

        # Create bundle
        metadata = bundler.create_bundle(
            output_path,
            include_sbom=False,
            include_osv=False,
            commit_sha="test123",
            git_ref="main",
        )

        # Verify output file was created
        assert output_path.exists()
        assert output_path.stat().st_size > 0

        # Verify metadata
        assert metadata.wheel_count == 2
        assert metadata.commit_sha == "test123"
        assert metadata.git_ref == "main"
        assert metadata.total_size_bytes > 0

    def test_create_bundle_includes_metadata(self, tmp_path: Path) -> None:
        """Test that bundle includes metadata file."""
        wheelhouse_dir = tmp_path / "wheelhouse"
        wheelhouse_dir.mkdir()

        # Create dummy wheel
        wheel = wheelhouse_dir / "test-1.0.0-py3-none-any.whl"
        wheel.write_text("test wheel")

        bundler = WheelhouseBundler(wheelhouse_dir)
        output_path = tmp_path / "bundle.tar.gz"

        metadata = bundler.create_bundle(
            output_path, include_sbom=False, include_osv=False
        )

        # Extract and verify metadata file exists
        with tarfile.open(output_path, "r:gz") as tar:
            members = tar.getnames()
            assert "wheelhouse/metadata.json" in members or any(
                "metadata.json" in m for m in members
            )

    def test_create_bundle_calculates_checksums(self, tmp_path: Path) -> None:
        """Test that bundle calculates checksums for wheels."""
        wheelhouse_dir = tmp_path / "wheelhouse"
        wheelhouse_dir.mkdir()

        # Create dummy wheel
        wheel = wheelhouse_dir / "test-1.0.0-py3-none-any.whl"
        wheel.write_text("test content")

        bundler = WheelhouseBundler(wheelhouse_dir)
        output_path = tmp_path / "bundle.tar.gz"

        metadata = bundler.create_bundle(
            output_path, include_sbom=False, include_osv=False
        )

        # Verify checksums were calculated
        assert len(metadata.checksums) > 0
        assert "test-1.0.0-py3-none-any.whl" in metadata.checksums

    def test_create_bundle_with_sbom(self, tmp_path: Path) -> None:
        """Test creating bundle with SBOM file."""
        wheelhouse_dir = tmp_path / "wheelhouse"
        wheelhouse_dir.mkdir()

        # Create dummy wheel and SBOM
        wheel = wheelhouse_dir / "test-1.0.0-py3-none-any.whl"
        wheel.write_text("test content")

        sbom = wheelhouse_dir / "sbom.json"
        sbom.write_text(json.dumps({"bomFormat": "CycloneDX"}))

        bundler = WheelhouseBundler(wheelhouse_dir)
        output_path = tmp_path / "bundle.tar.gz"

        metadata = bundler.create_bundle(
            output_path, include_sbom=True, include_osv=False
        )

        assert output_path.exists()

        # Verify SBOM is included
        with tarfile.open(output_path, "r:gz") as tar:
            members = tar.getnames()
            assert any("sbom.json" in m for m in members)

    def test_create_bundle_with_osv(self, tmp_path: Path) -> None:
        """Test creating bundle with OSV scan results."""
        wheelhouse_dir = tmp_path / "wheelhouse"
        wheelhouse_dir.mkdir()

        # Create dummy wheel and OSV results
        wheel = wheelhouse_dir / "test-1.0.0-py3-none-any.whl"
        wheel.write_text("test content")

        # The bundler looks for osv.json (not osv-scan.json)
        osv = wheelhouse_dir / "osv.json"
        osv.write_text(json.dumps({"vulnerabilities": []}))

        bundler = WheelhouseBundler(wheelhouse_dir)
        output_path = tmp_path / "bundle.tar.gz"

        metadata = bundler.create_bundle(
            output_path, include_sbom=False, include_osv=True
        )

        assert output_path.exists()

        # Verify OSV results are included
        with tarfile.open(output_path, "r:gz") as tar:
            members = tar.getnames()
            assert any("osv.json" in m for m in members)

    def test_create_bundle_with_requirements_txt(self, tmp_path: Path) -> None:
        """Test that bundle includes requirements.txt if present."""
        wheelhouse_dir = tmp_path / "wheelhouse"
        wheelhouse_dir.mkdir()

        # Create dummy wheel and requirements.txt
        wheel = wheelhouse_dir / "test-1.0.0-py3-none-any.whl"
        wheel.write_text("test content")

        requirements = wheelhouse_dir / "requirements.txt"
        requirements.write_text("test==1.0.0\n")

        bundler = WheelhouseBundler(wheelhouse_dir)
        output_path = tmp_path / "bundle.tar.gz"

        bundler.create_bundle(output_path, include_sbom=False, include_osv=False)

        # Verify requirements.txt is included
        with tarfile.open(output_path, "r:gz") as tar:
            members = tar.getnames()
            assert any("requirements.txt" in m for m in members)
