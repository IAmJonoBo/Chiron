"""Binary reproducibility checking for Chiron wheels.

This module provides tools for verifying that wheel builds are reproducible
by comparing checksums and metadata across different build environments.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class WheelInfo:
    """Information about a wheel file."""
    
    name: str
    path: Path
    sha256: str
    size: int
    metadata: dict[str, Any]
    file_list: list[str]
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "path": str(self.path),
            "sha256": self.sha256,
            "size": self.size,
            "metadata": self.metadata,
            "file_list": self.file_list,
        }


@dataclass
class ReproducibilityReport:
    """Report on wheel reproducibility."""
    
    identical: bool
    wheel1: WheelInfo
    wheel2: WheelInfo
    differences: list[str]
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "identical": self.identical,
            "wheel1": self.wheel1.to_dict(),
            "wheel2": self.wheel2.to_dict(),
            "differences": self.differences,
        }


class ReproducibilityChecker:
    """Check reproducibility of wheel builds."""
    
    def __init__(self):
        """Initialize reproducibility checker."""
        self.ignore_timestamps = True
        self.ignore_build_paths = True
    
    def analyze_wheel(self, wheel_path: Path) -> WheelInfo:
        """Analyze a wheel file.
        
        Args:
            wheel_path: Path to wheel file
            
        Returns:
            WheelInfo object
        """
        with open(wheel_path, "rb") as f:
            content = f.read()
            sha256 = hashlib.sha256(content).hexdigest()
        
        size = wheel_path.stat().st_size
        
        # Extract metadata and file list
        metadata = {}
        file_list = []
        
        try:
            with zipfile.ZipFile(wheel_path, "r") as zf:
                file_list = sorted(zf.namelist())
                
                # Try to read metadata
                for name in zf.namelist():
                    if name.endswith("METADATA"):
                        with zf.open(name) as mf:
                            metadata_text = mf.read().decode("utf-8")
                            metadata = self._parse_metadata(metadata_text)
                        break
        except Exception as e:
            metadata["error"] = str(e)
        
        return WheelInfo(
            name=wheel_path.name,
            path=wheel_path,
            sha256=sha256,
            size=size,
            metadata=metadata,
            file_list=file_list,
        )
    
    def compare_wheels(self, wheel1_path: Path, wheel2_path: Path) -> ReproducibilityReport:
        """Compare two wheels for reproducibility.
        
        Args:
            wheel1_path: Path to first wheel
            wheel2_path: Path to second wheel
            
        Returns:
            ReproducibilityReport
        """
        wheel1 = self.analyze_wheel(wheel1_path)
        wheel2 = self.analyze_wheel(wheel2_path)
        
        differences = []
        
        # Compare checksums
        if wheel1.sha256 != wheel2.sha256:
            differences.append(f"Different SHA256: {wheel1.sha256} != {wheel2.sha256}")
        
        # Compare sizes
        if wheel1.size != wheel2.size:
            differences.append(f"Different sizes: {wheel1.size} != {wheel2.size}")
        
        # Compare file lists
        if wheel1.file_list != wheel2.file_list:
            differences.append("Different file lists")
            
            # Find specific differences
            files1 = set(wheel1.file_list)
            files2 = set(wheel2.file_list)
            
            only_in_1 = files1 - files2
            if only_in_1:
                differences.append(f"Files only in wheel1: {sorted(only_in_1)[:5]}")
            
            only_in_2 = files2 - files1
            if only_in_2:
                differences.append(f"Files only in wheel2: {sorted(only_in_2)[:5]}")
        
        # Compare metadata (ignoring build-time fields if configured)
        meta_diffs = self._compare_metadata(wheel1.metadata, wheel2.metadata)
        if meta_diffs:
            differences.extend(meta_diffs)
        
        return ReproducibilityReport(
            identical=len(differences) == 0,
            wheel1=wheel1,
            wheel2=wheel2,
            differences=differences,
        )
    
    def compare_wheel_contents(
        self,
        wheel1_path: Path,
        wheel2_path: Path
    ) -> dict[str, Any]:
        """Compare contents of two wheels file-by-file.
        
        Args:
            wheel1_path: Path to first wheel
            wheel2_path: Path to second wheel
            
        Returns:
            Comparison report dictionary
        """
        differences = []
        identical_files = 0
        different_files = 0
        
        try:
            with zipfile.ZipFile(wheel1_path, "r") as zf1, zipfile.ZipFile(wheel2_path, "r") as zf2:
                files1 = set(zf1.namelist())
                files2 = set(zf2.namelist())
                
                common_files = files1 & files2
                
                for filename in sorted(common_files):
                    # Skip timestamp files if configured
                    if self.ignore_timestamps and "RECORD" in filename:
                        continue
                    
                    with zf1.open(filename) as f1, zf2.open(filename) as f2:
                        content1 = f1.read()
                        content2 = f2.read()
                        
                        if content1 == content2:
                            identical_files += 1
                        else:
                            different_files += 1
                            hash1 = hashlib.sha256(content1).hexdigest()[:16]
                            hash2 = hashlib.sha256(content2).hexdigest()[:16]
                            differences.append({
                                "file": filename,
                                "size1": len(content1),
                                "size2": len(content2),
                                "hash1": hash1,
                                "hash2": hash2,
                            })
        except Exception as e:
            return {"error": str(e)}
        
        return {
            "identical_files": identical_files,
            "different_files": different_files,
            "differences": differences[:10],  # Limit to first 10 differences
            "total_compared": identical_files + different_files,
        }
    
    def _parse_metadata(self, metadata_text: str) -> dict[str, Any]:
        """Parse wheel METADATA file.
        
        Args:
            metadata_text: Raw metadata text
            
        Returns:
            Parsed metadata dictionary
        """
        metadata = {}
        for line in metadata_text.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                
                if key in metadata:
                    # Handle multi-value fields
                    if not isinstance(metadata[key], list):
                        metadata[key] = [metadata[key]]
                    metadata[key].append(value)
                else:
                    metadata[key] = value
        
        return metadata
    
    def _compare_metadata(self, meta1: dict[str, Any], meta2: dict[str, Any]) -> list[str]:
        """Compare metadata dictionaries.
        
        Args:
            meta1: First metadata dictionary
            meta2: Second metadata dictionary
            
        Returns:
            List of differences
        """
        differences = []
        
        # Fields to ignore if configured
        ignore_fields = set()
        if self.ignore_timestamps:
            ignore_fields.add("Build-Date")
        if self.ignore_build_paths:
            ignore_fields.add("Home-page")
            ignore_fields.add("Download-URL")
        
        # Compare keys
        keys1 = set(meta1.keys()) - ignore_fields
        keys2 = set(meta2.keys()) - ignore_fields
        
        if keys1 != keys2:
            only_in_1 = keys1 - keys2
            if only_in_1:
                differences.append(f"Metadata only in wheel1: {sorted(only_in_1)}")
            
            only_in_2 = keys2 - keys1
            if only_in_2:
                differences.append(f"Metadata only in wheel2: {sorted(only_in_2)}")
        
        # Compare values for common keys
        for key in keys1 & keys2:
            if meta1[key] != meta2[key]:
                differences.append(f"Different {key}: {meta1[key]!r} != {meta2[key]!r}")
        
        return differences


def check_reproducibility(wheel1: Path, wheel2: Path) -> ReproducibilityReport:
    """Check if two wheels are reproducible.
    
    Convenience function for the most common use case.
    
    Args:
        wheel1: Path to first wheel
        wheel2: Path to second wheel
        
    Returns:
        ReproducibilityReport
    """
    checker = ReproducibilityChecker()
    return checker.compare_wheels(wheel1, wheel2)
