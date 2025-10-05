"""TUF (The Update Framework) metadata support for Chiron.

This module provides foundation for TUF metadata generation and verification
to enhance security of artifact distribution.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class TUFMetadata:
    """TUF metadata generator and verifier."""

    def __init__(self, repo_path: Path | str):
        """Initialize TUF metadata manager.

        Args:
            repo_path: Path to the repository
        """
        self.repo_path = Path(repo_path)
        self.metadata_path = self.repo_path / "metadata"
        self.targets_path = self.repo_path / "targets"

    def initialize_repo(self) -> None:
        """Initialize TUF repository structure."""
        self.metadata_path.mkdir(parents=True, exist_ok=True)
        self.targets_path.mkdir(parents=True, exist_ok=True)

    def generate_root_metadata(
        self, version: int = 1, expires_days: int = 365
    ) -> dict[str, Any]:
        """Generate root metadata (skeleton).

        Args:
            version: Metadata version number
            expires_days: Number of days until expiration

        Returns:
            Root metadata dictionary
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=expires_days)

        metadata = {
            "_type": "root",
            "spec_version": "1.0.0",
            "version": version,
            "expires": expires.isoformat(),
            "keys": {},
            "roles": {
                "root": {"keyids": [], "threshold": 1},
                "targets": {"keyids": [], "threshold": 1},
                "snapshot": {"keyids": [], "threshold": 1},
                "timestamp": {"keyids": [], "threshold": 1},
            },
            "consistent_snapshot": False,
        }

        return metadata

    def generate_targets_metadata(
        self, artifacts: list[Path], version: int = 1, expires_days: int = 90
    ) -> dict[str, Any]:
        """Generate targets metadata for artifacts.

        Args:
            artifacts: List of artifact paths
            version: Metadata version number
            expires_days: Number of days until expiration

        Returns:
            Targets metadata dictionary
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=expires_days)

        targets = {}
        for artifact in artifacts:
            if not artifact.exists():
                continue

            # Calculate hashes
            with open(artifact, "rb") as f:
                content = f.read()
                sha256 = hashlib.sha256(content).hexdigest()
                sha512 = hashlib.sha512(content).hexdigest()

            targets[artifact.name] = {
                "length": len(content),
                "hashes": {"sha256": sha256, "sha512": sha512},
                "custom": {
                    "type": "wheelhouse" if artifact.suffix == ".whl" else "bundle",
                    "platform": self._detect_platform(artifact.name),
                },
            }

        metadata = {
            "_type": "targets",
            "spec_version": "1.0.0",
            "version": version,
            "expires": expires.isoformat(),
            "targets": targets,
            "delegations": {},
        }

        return metadata

    def generate_snapshot_metadata(
        self, version: int = 1, expires_days: int = 7
    ) -> dict[str, Any]:
        """Generate snapshot metadata (skeleton).

        Args:
            version: Metadata version number
            expires_days: Number of days until expiration

        Returns:
            Snapshot metadata dictionary
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=expires_days)

        metadata = {
            "_type": "snapshot",
            "spec_version": "1.0.0",
            "version": version,
            "expires": expires.isoformat(),
            "meta": {},
        }

        return metadata

    def generate_timestamp_metadata(
        self, version: int = 1, expires_hours: int = 1
    ) -> dict[str, Any]:
        """Generate timestamp metadata (skeleton).

        Args:
            version: Metadata version number
            expires_hours: Number of hours until expiration

        Returns:
            Timestamp metadata dictionary
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=expires_hours)

        metadata = {
            "_type": "timestamp",
            "spec_version": "1.0.0",
            "version": version,
            "expires": expires.isoformat(),
            "meta": {},
        }

        return metadata

    def verify_metadata(self, metadata: dict[str, Any]) -> tuple[bool, list[str]]:
        """Verify TUF metadata (skeleton).

        Args:
            metadata: Metadata to verify

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        # Check required fields
        required = ["_type", "spec_version", "version", "expires"]
        for field in required:
            if field not in metadata:
                errors.append(f"Missing required field: {field}")

        # Check expiration
        if "expires" in metadata:
            try:
                expires = datetime.fromisoformat(
                    metadata["expires"].replace("Z", "+00:00")
                )
                if expires < datetime.now(timezone.utc):
                    errors.append("Metadata has expired")
            except ValueError:
                errors.append("Invalid expiration date format")

        # Check spec version
        if metadata.get("spec_version") not in ["1.0.0"]:
            errors.append(f"Unsupported spec version: {metadata.get('spec_version')}")

        return len(errors) == 0, errors

    def save_metadata(
        self, metadata: dict[str, Any], filename: str | None = None
    ) -> Path:
        """Save metadata to file.

        Args:
            metadata: Metadata to save
            filename: Optional custom filename

        Returns:
            Path to saved metadata file
        """
        if filename is None:
            metadata_type = metadata.get("_type", "unknown")
            version = metadata.get("version", 1)
            filename = f"{metadata_type}.{version}.json"

        filepath = self.metadata_path / filename
        with open(filepath, "w") as f:
            json.dump(metadata, f, indent=2)

        return filepath

    def load_metadata(self, filepath: Path | str) -> dict[str, Any]:
        """Load metadata from file.

        Args:
            filepath: Path to metadata file

        Returns:
            Metadata dictionary
        """
        with open(filepath) as f:
            return json.load(f)

    def _detect_platform(self, filename: str) -> str:
        """Detect platform from filename.

        Args:
            filename: Artifact filename

        Returns:
            Platform identifier
        """
        filename_lower = filename.lower()
        if "linux" in filename_lower or "manylinux" in filename_lower:
            return "linux"
        elif "macos" in filename_lower or "darwin" in filename_lower:
            return "macos"
        elif "win" in filename_lower:
            return "windows"
        else:
            return "any"


def create_tuf_repo(repo_path: Path | str, artifacts: list[Path]) -> dict[str, Path]:
    """Create a TUF repository with metadata for artifacts.

    Args:
        repo_path: Path to repository
        artifacts: List of artifacts to include

    Returns:
        Dictionary mapping metadata type to file paths
    """
    tuf = TUFMetadata(repo_path)
    tuf.initialize_repo()

    # Generate all metadata
    root = tuf.generate_root_metadata()
    targets = tuf.generate_targets_metadata(artifacts)
    snapshot = tuf.generate_snapshot_metadata()
    timestamp = tuf.generate_timestamp_metadata()

    # Save metadata
    metadata_files = {
        "root": tuf.save_metadata(root),
        "targets": tuf.save_metadata(targets),
        "snapshot": tuf.save_metadata(snapshot),
        "timestamp": tuf.save_metadata(timestamp),
    }

    return metadata_files
