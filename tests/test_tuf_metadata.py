"""Tests for TUF metadata module."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from chiron.tuf_metadata import TUFMetadata, create_tuf_repo


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a temporary repository path for testing.
    
    Args:
        tmp_path: Pytest temporary directory
        
    Returns:
        Path to temporary repository
    """
    repo_path = tmp_path / "tuf_repo"
    repo_path.mkdir(exist_ok=True)
    return repo_path


@pytest.fixture
def tmp_artifacts(tmp_path: Path) -> list[Path]:
    """Create temporary artifact files for testing.
    
    Args:
        tmp_path: Pytest temporary directory
        
    Returns:
        List of artifact paths
    """
    artifacts = []
    
    # Create some test wheel files
    wheel1 = tmp_path / "package1-1.0.0-py3-none-manylinux_2_28_x86_64.whl"
    wheel1.write_text("test wheel content 1")
    artifacts.append(wheel1)
    
    wheel2 = tmp_path / "package2-2.0.0-py3-none-macosx_10_9_x86_64.whl"
    wheel2.write_text("test wheel content 2")
    artifacts.append(wheel2)
    
    wheel3 = tmp_path / "package3-3.0.0-py3-none-win_amd64.whl"
    wheel3.write_text("test wheel content 3")
    artifacts.append(wheel3)
    
    return artifacts


class TestTUFMetadata:
    """Test cases for TUFMetadata class."""
    
    def test_initialization(self, tmp_repo: Path):
        """Test TUFMetadata initialization."""
        tuf = TUFMetadata(tmp_repo)
        
        assert tuf.repo_path == tmp_repo
        assert tuf.metadata_path == tmp_repo / "metadata"
        assert tuf.targets_path == tmp_repo / "targets"
    
    def test_initialization_with_string_path(self, tmp_repo: Path):
        """Test TUFMetadata initialization with string path."""
        tuf = TUFMetadata(str(tmp_repo))
        
        assert tuf.repo_path == tmp_repo
        assert isinstance(tuf.repo_path, Path)
    
    def test_initialize_repo(self, tmp_repo: Path):
        """Test repository structure initialization."""
        tuf = TUFMetadata(tmp_repo)
        tuf.initialize_repo()
        
        assert tuf.metadata_path.exists()
        assert tuf.metadata_path.is_dir()
        assert tuf.targets_path.exists()
        assert tuf.targets_path.is_dir()
    
    def test_initialize_repo_idempotent(self, tmp_repo: Path):
        """Test that initialize_repo can be called multiple times."""
        tuf = TUFMetadata(tmp_repo)
        tuf.initialize_repo()
        tuf.initialize_repo()  # Should not fail
        
        assert tuf.metadata_path.exists()
        assert tuf.targets_path.exists()
    
    def test_generate_root_metadata_defaults(self, tmp_repo: Path):
        """Test root metadata generation with default parameters."""
        tuf = TUFMetadata(tmp_repo)
        metadata = tuf.generate_root_metadata()
        
        assert metadata["_type"] == "root"
        assert metadata["spec_version"] == "1.0.0"
        assert metadata["version"] == 1
        assert "expires" in metadata
        assert "keys" in metadata
        assert "roles" in metadata
        assert metadata["consistent_snapshot"] is False
    
    def test_generate_root_metadata_with_version(self, tmp_repo: Path):
        """Test root metadata generation with custom version."""
        tuf = TUFMetadata(tmp_repo)
        metadata = tuf.generate_root_metadata(version=5)
        
        assert metadata["version"] == 5
    
    def test_generate_root_metadata_expiration(self, tmp_repo: Path):
        """Test root metadata expiration calculation."""
        tuf = TUFMetadata(tmp_repo)
        metadata = tuf.generate_root_metadata(expires_days=30)
        
        expires = datetime.fromisoformat(metadata["expires"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        
        # Should expire approximately 30 days from now
        delta = expires - now
        assert 29 <= delta.days <= 31
    
    def test_generate_root_metadata_roles(self, tmp_repo: Path):
        """Test root metadata roles structure."""
        tuf = TUFMetadata(tmp_repo)
        metadata = tuf.generate_root_metadata()
        
        roles = metadata["roles"]
        assert "root" in roles
        assert "targets" in roles
        assert "snapshot" in roles
        assert "timestamp" in roles
        
        for role in roles.values():
            assert "keyids" in role
            assert "threshold" in role
            assert role["threshold"] == 1
    
    def test_generate_targets_metadata(self, tmp_repo: Path, tmp_artifacts: list[Path]):
        """Test targets metadata generation."""
        tuf = TUFMetadata(tmp_repo)
        metadata = tuf.generate_targets_metadata(tmp_artifacts)
        
        assert metadata["_type"] == "targets"
        assert metadata["spec_version"] == "1.0.0"
        assert metadata["version"] == 1
        assert "expires" in metadata
        assert "targets" in metadata
        assert len(metadata["targets"]) == len(tmp_artifacts)
    
    def test_generate_targets_metadata_hashes(self, tmp_repo: Path, tmp_artifacts: list[Path]):
        """Test that targets metadata includes proper hashes."""
        tuf = TUFMetadata(tmp_repo)
        metadata = tuf.generate_targets_metadata(tmp_artifacts)
        
        for artifact in tmp_artifacts:
            target = metadata["targets"][artifact.name]
            assert "hashes" in target
            assert "sha256" in target["hashes"]
            assert "sha512" in target["hashes"]
            assert len(target["hashes"]["sha256"]) == 64  # SHA256 hex length
            assert len(target["hashes"]["sha512"]) == 128  # SHA512 hex length
    
    def test_generate_targets_metadata_custom_info(self, tmp_repo: Path, tmp_artifacts: list[Path]):
        """Test that targets metadata includes custom info."""
        tuf = TUFMetadata(tmp_repo)
        metadata = tuf.generate_targets_metadata(tmp_artifacts)
        
        for artifact in tmp_artifacts:
            target = metadata["targets"][artifact.name]
            assert "custom" in target
            assert "type" in target["custom"]
            assert "platform" in target["custom"]
            assert target["custom"]["type"] == "wheelhouse"
    
    def test_generate_targets_metadata_length(self, tmp_repo: Path, tmp_artifacts: list[Path]):
        """Test that targets metadata includes file lengths."""
        tuf = TUFMetadata(tmp_repo)
        metadata = tuf.generate_targets_metadata(tmp_artifacts)
        
        for artifact in tmp_artifacts:
            target = metadata["targets"][artifact.name]
            assert "length" in target
            assert target["length"] == len(artifact.read_text())
    
    def test_generate_targets_metadata_with_nonexistent_file(self, tmp_repo: Path, tmp_path: Path):
        """Test targets metadata generation with nonexistent file."""
        tuf = TUFMetadata(tmp_repo)
        nonexistent = tmp_path / "nonexistent.whl"
        
        metadata = tuf.generate_targets_metadata([nonexistent])
        
        # Should skip nonexistent files
        assert len(metadata["targets"]) == 0
    
    def test_generate_snapshot_metadata(self, tmp_repo: Path):
        """Test snapshot metadata generation."""
        tuf = TUFMetadata(tmp_repo)
        metadata = tuf.generate_snapshot_metadata()
        
        assert metadata["_type"] == "snapshot"
        assert metadata["spec_version"] == "1.0.0"
        assert metadata["version"] == 1
        assert "expires" in metadata
        assert "meta" in metadata
    
    def test_generate_snapshot_metadata_expiration(self, tmp_repo: Path):
        """Test snapshot metadata expiration."""
        tuf = TUFMetadata(tmp_repo)
        metadata = tuf.generate_snapshot_metadata(expires_days=7)
        
        expires = datetime.fromisoformat(metadata["expires"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        
        # Should expire approximately 7 days from now
        delta = expires - now
        assert 6 <= delta.days <= 8
    
    def test_generate_timestamp_metadata(self, tmp_repo: Path):
        """Test timestamp metadata generation."""
        tuf = TUFMetadata(tmp_repo)
        metadata = tuf.generate_timestamp_metadata()
        
        assert metadata["_type"] == "timestamp"
        assert metadata["spec_version"] == "1.0.0"
        assert metadata["version"] == 1
        assert "expires" in metadata
        assert "meta" in metadata
    
    def test_generate_timestamp_metadata_expiration(self, tmp_repo: Path):
        """Test timestamp metadata expiration."""
        tuf = TUFMetadata(tmp_repo)
        metadata = tuf.generate_timestamp_metadata(expires_hours=1)
        
        expires = datetime.fromisoformat(metadata["expires"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        
        # Should expire approximately 1 hour from now
        delta = (expires - now).total_seconds() / 3600
        assert 0.9 <= delta <= 1.1
    
    def test_verify_metadata_valid(self, tmp_repo: Path):
        """Test verification of valid metadata."""
        tuf = TUFMetadata(tmp_repo)
        metadata = tuf.generate_root_metadata()
        
        is_valid, errors = tuf.verify_metadata(metadata)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_verify_metadata_missing_required_field(self, tmp_repo: Path):
        """Test verification of metadata with missing required field."""
        tuf = TUFMetadata(tmp_repo)
        metadata = {
            "_type": "root",
            "spec_version": "1.0.0",
            # Missing "version" and "expires"
        }
        
        is_valid, errors = tuf.verify_metadata(metadata)
        
        assert is_valid is False
        assert len(errors) >= 2
        assert any("version" in error for error in errors)
        assert any("expires" in error for error in errors)
    
    def test_verify_metadata_expired(self, tmp_repo: Path):
        """Test verification of expired metadata."""
        tuf = TUFMetadata(tmp_repo)
        
        # Create metadata that expired yesterday
        past_date = datetime.now(timezone.utc) - timedelta(days=1)
        metadata = {
            "_type": "root",
            "spec_version": "1.0.0",
            "version": 1,
            "expires": past_date.isoformat()
        }
        
        is_valid, errors = tuf.verify_metadata(metadata)
        
        assert is_valid is False
        assert any("expired" in error.lower() for error in errors)
    
    def test_verify_metadata_invalid_spec_version(self, tmp_repo: Path):
        """Test verification of metadata with invalid spec version."""
        tuf = TUFMetadata(tmp_repo)
        metadata = {
            "_type": "root",
            "spec_version": "2.0.0",  # Unsupported version
            "version": 1,
            "expires": datetime.now(timezone.utc).isoformat()
        }
        
        is_valid, errors = tuf.verify_metadata(metadata)
        
        assert is_valid is False
        assert any("spec version" in error.lower() for error in errors)
    
    def test_save_metadata(self, tmp_repo: Path):
        """Test saving metadata to file."""
        tuf = TUFMetadata(tmp_repo)
        tuf.initialize_repo()
        
        metadata = tuf.generate_root_metadata()
        filepath = tuf.save_metadata(metadata)
        
        assert filepath.exists()
        assert filepath.parent == tuf.metadata_path
        assert filepath.name == "root.1.json"
    
    def test_save_metadata_custom_filename(self, tmp_repo: Path):
        """Test saving metadata with custom filename."""
        tuf = TUFMetadata(tmp_repo)
        tuf.initialize_repo()
        
        metadata = tuf.generate_root_metadata()
        filepath = tuf.save_metadata(metadata, filename="custom.json")
        
        assert filepath.exists()
        assert filepath.name == "custom.json"
    
    def test_save_and_load_metadata(self, tmp_repo: Path):
        """Test saving and loading metadata."""
        tuf = TUFMetadata(tmp_repo)
        tuf.initialize_repo()
        
        original_metadata = tuf.generate_root_metadata()
        filepath = tuf.save_metadata(original_metadata)
        
        loaded_metadata = tuf.load_metadata(filepath)
        
        assert loaded_metadata["_type"] == original_metadata["_type"]
        assert loaded_metadata["version"] == original_metadata["version"]
    
    def test_detect_platform_linux(self, tmp_repo: Path):
        """Test platform detection for Linux wheels."""
        tuf = TUFMetadata(tmp_repo)
        
        assert tuf._detect_platform("package-1.0-py3-none-manylinux_2_28_x86_64.whl") == "linux"
        assert tuf._detect_platform("package-1.0-py3-none-linux_x86_64.whl") == "linux"
    
    def test_detect_platform_macos(self, tmp_repo: Path):
        """Test platform detection for macOS wheels."""
        tuf = TUFMetadata(tmp_repo)
        
        assert tuf._detect_platform("package-1.0-py3-none-macosx_10_9_x86_64.whl") == "macos"
        assert tuf._detect_platform("package-1.0-py3-none-darwin_arm64.whl") == "macos"
    
    def test_detect_platform_windows(self, tmp_repo: Path):
        """Test platform detection for Windows wheels."""
        tuf = TUFMetadata(tmp_repo)
        
        assert tuf._detect_platform("package-1.0-py3-none-win_amd64.whl") == "windows"
        assert tuf._detect_platform("package-1.0-py3-none-win32.whl") == "windows"
    
    def test_detect_platform_any(self, tmp_repo: Path):
        """Test platform detection for platform-independent wheels."""
        tuf = TUFMetadata(tmp_repo)
        
        assert tuf._detect_platform("package-1.0-py3-none-any.whl") == "any"
        assert tuf._detect_platform("package-1.0-py3.whl") == "any"


class TestCreateTUFRepo:
    """Test cases for create_tuf_repo convenience function."""
    
    def test_create_tuf_repo(self, tmp_repo: Path, tmp_artifacts: list[Path]):
        """Test TUF repository creation."""
        metadata_files = create_tuf_repo(tmp_repo, tmp_artifacts)
        
        assert "root" in metadata_files
        assert "targets" in metadata_files
        assert "snapshot" in metadata_files
        assert "timestamp" in metadata_files
        
        # All metadata files should exist
        for filepath in metadata_files.values():
            assert filepath.exists()
            assert filepath.parent == tmp_repo / "metadata"
    
    def test_create_tuf_repo_with_string_path(self, tmp_repo: Path, tmp_artifacts: list[Path]):
        """Test TUF repository creation with string path."""
        metadata_files = create_tuf_repo(str(tmp_repo), tmp_artifacts)
        
        assert len(metadata_files) == 4
        for filepath in metadata_files.values():
            assert filepath.exists()
    
    def test_create_tuf_repo_empty_artifacts(self, tmp_repo: Path):
        """Test TUF repository creation with no artifacts."""
        metadata_files = create_tuf_repo(tmp_repo, [])
        
        # Should still create all metadata files
        assert len(metadata_files) == 4
        
        # Targets should be empty
        tuf = TUFMetadata(tmp_repo)
        targets_metadata = tuf.load_metadata(metadata_files["targets"])
        assert len(targets_metadata["targets"]) == 0
    
    def test_create_tuf_repo_validates_metadata(self, tmp_repo: Path, tmp_artifacts: list[Path]):
        """Test that created metadata is valid."""
        metadata_files = create_tuf_repo(tmp_repo, tmp_artifacts)
        
        tuf = TUFMetadata(tmp_repo)
        
        for metadata_file in metadata_files.values():
            metadata = tuf.load_metadata(metadata_file)
            is_valid, errors = tuf.verify_metadata(metadata)
            
            assert is_valid is True, f"Errors in {metadata_file.name}: {errors}"


class TestTUFMetadataIntegration:
    """Integration tests for TUF metadata."""
    
    def test_full_workflow(self, tmp_repo: Path, tmp_artifacts: list[Path]):
        """Test complete TUF workflow."""
        # Initialize
        tuf = TUFMetadata(tmp_repo)
        tuf.initialize_repo()
        
        # Generate all metadata
        root = tuf.generate_root_metadata()
        targets = tuf.generate_targets_metadata(tmp_artifacts)
        snapshot = tuf.generate_snapshot_metadata()
        timestamp = tuf.generate_timestamp_metadata()
        
        # Verify all metadata
        for metadata in [root, targets, snapshot, timestamp]:
            is_valid, errors = tuf.verify_metadata(metadata)
            assert is_valid is True, f"Validation errors: {errors}"
        
        # Save all metadata
        root_path = tuf.save_metadata(root)
        targets_path = tuf.save_metadata(targets)
        snapshot_path = tuf.save_metadata(snapshot)
        timestamp_path = tuf.save_metadata(timestamp)
        
        # Verify files exist
        assert root_path.exists()
        assert targets_path.exists()
        assert snapshot_path.exists()
        assert timestamp_path.exists()
        
        # Load and verify
        loaded_root = tuf.load_metadata(root_path)
        assert loaded_root["_type"] == "root"
    
    def test_metadata_versioning(self, tmp_repo: Path):
        """Test metadata versioning."""
        tuf = TUFMetadata(tmp_repo)
        tuf.initialize_repo()
        
        # Create multiple versions
        v1 = tuf.generate_root_metadata(version=1)
        v2 = tuf.generate_root_metadata(version=2)
        v3 = tuf.generate_root_metadata(version=3)
        
        # Save all versions
        path1 = tuf.save_metadata(v1)
        path2 = tuf.save_metadata(v2)
        path3 = tuf.save_metadata(v3)
        
        # All versions should exist
        assert path1.exists()
        assert path2.exists()
        assert path3.exists()
        
        # Filenames should reflect versions
        assert "1" in path1.name
        assert "2" in path2.name
        assert "3" in path3.name
    
    def test_metadata_expiration_times(self, tmp_repo: Path):
        """Test that different metadata types have appropriate expiration times."""
        tuf = TUFMetadata(tmp_repo)
        
        root = tuf.generate_root_metadata(expires_days=365)
        targets = tuf.generate_targets_metadata([], expires_days=90)
        snapshot = tuf.generate_snapshot_metadata(expires_days=7)
        timestamp = tuf.generate_timestamp_metadata(expires_hours=1)
        
        # Parse expiration dates
        root_expires = datetime.fromisoformat(root["expires"].replace("Z", "+00:00"))
        targets_expires = datetime.fromisoformat(targets["expires"].replace("Z", "+00:00"))
        snapshot_expires = datetime.fromisoformat(snapshot["expires"].replace("Z", "+00:00"))
        timestamp_expires = datetime.fromisoformat(timestamp["expires"].replace("Z", "+00:00"))
        
        now = datetime.now(timezone.utc)
        
        # Verify relative expiration times
        assert (root_expires - now).days > (targets_expires - now).days
        assert (targets_expires - now).days > (snapshot_expires - now).days
        assert (snapshot_expires - now).days * 24 > (timestamp_expires - now).total_seconds() / 3600
