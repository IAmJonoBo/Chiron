"""Tests for reproducibility checking module."""

import hashlib
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from chiron.reproducibility import (
    ReproducibilityChecker,
    ReproducibilityReport,
    WheelInfo,
    check_reproducibility,
)


@pytest.fixture
def tmp_wheel(tmp_path: Path) -> Path:
    """Create a temporary wheel file for testing.

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to temporary wheel file
    """
    wheel_path = tmp_path / "test_package-1.0.0-py3-none-any.whl"

    with zipfile.ZipFile(wheel_path, "w") as zf:
        # Add metadata
        metadata_content = """Metadata-Version: 2.1
Name: test-package
Version: 1.0.0
Summary: A test package
Author: Test Author
"""
        zf.writestr("test_package-1.0.0.dist-info/METADATA", metadata_content)

        # Add some Python code
        zf.writestr(
            "test_package/__init__.py", "# Test package\n__version__ = '1.0.0'\n"
        )
        zf.writestr("test_package/module.py", "def hello():\n    return 'world'\n")

        # Add RECORD file
        record_content = """test_package/__init__.py,sha256=abc123,100
test_package/module.py,sha256=def456,200
test_package-1.0.0.dist-info/METADATA,sha256=ghi789,300
"""
        zf.writestr("test_package-1.0.0.dist-info/RECORD", record_content)

    return wheel_path


@pytest.fixture
def tmp_wheel_different(tmp_path: Path) -> Path:
    """Create a different temporary wheel file for testing.

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to temporary wheel file
    """
    wheel_path = tmp_path / "test_package-1.0.0-py3-none-any-different.whl"

    with zipfile.ZipFile(wheel_path, "w") as zf:
        # Add metadata with different content
        metadata_content = """Metadata-Version: 2.1
Name: test-package
Version: 1.0.0
Summary: A different test package
Author: Different Author
"""
        zf.writestr("test_package-1.0.0.dist-info/METADATA", metadata_content)

        # Add different Python code
        zf.writestr(
            "test_package/__init__.py",
            "# Different test package\n__version__ = '1.0.0'\n",
        )
        zf.writestr(
            "test_package/module.py", "def hello():\n    return 'different world'\n"
        )

        # Add RECORD file
        record_content = """test_package/__init__.py,sha256=xyz123,110
test_package/module.py,sha256=uvw456,220
test_package-1.0.0.dist-info/METADATA,sha256=rst789,310
"""
        zf.writestr("test_package-1.0.0.dist-info/RECORD", record_content)

    return wheel_path


class TestWheelInfo:
    """Test cases for WheelInfo dataclass."""

    def test_wheel_info_creation(self, tmp_wheel: Path):
        """Test WheelInfo creation."""
        wheel_info = WheelInfo(
            name=tmp_wheel.name,
            path=tmp_wheel,
            sha256="abc123",
            size=1000,
            metadata={"name": "test-package", "version": "1.0.0"},
            file_list=["file1.py", "file2.py"],
        )

        assert wheel_info.name == tmp_wheel.name
        assert wheel_info.path == tmp_wheel
        assert wheel_info.sha256 == "abc123"
        assert wheel_info.size == 1000
        assert wheel_info.metadata["name"] == "test-package"
        assert len(wheel_info.file_list) == 2

    def test_wheel_info_to_dict(self, tmp_wheel: Path):
        """Test WheelInfo to_dict conversion."""
        wheel_info = WheelInfo(
            name="test.whl",
            path=tmp_wheel,
            sha256="abc123",
            size=1000,
            metadata={"key": "value"},
            file_list=["file1.py"],
        )

        result = wheel_info.to_dict()

        assert result["name"] == "test.whl"
        assert result["path"] == str(tmp_wheel)
        assert result["sha256"] == "abc123"
        assert result["size"] == 1000
        assert result["metadata"] == {"key": "value"}
        assert result["file_list"] == ["file1.py"]


class TestReproducibilityReport:
    """Test cases for ReproducibilityReport dataclass."""

    def test_report_creation(self, tmp_wheel: Path):
        """Test ReproducibilityReport creation."""
        wheel1 = WheelInfo(
            name="wheel1.whl",
            path=tmp_wheel,
            sha256="abc",
            size=100,
            metadata={},
            file_list=[],
        )
        wheel2 = WheelInfo(
            name="wheel2.whl",
            path=tmp_wheel,
            sha256="abc",
            size=100,
            metadata={},
            file_list=[],
        )

        report = ReproducibilityReport(
            identical=True, wheel1=wheel1, wheel2=wheel2, differences=[]
        )

        assert report.identical is True
        assert report.wheel1 == wheel1
        assert report.wheel2 == wheel2
        assert len(report.differences) == 0

    def test_report_to_dict(self, tmp_wheel: Path):
        """Test ReproducibilityReport to_dict conversion."""
        wheel1 = WheelInfo(
            name="wheel1.whl",
            path=tmp_wheel,
            sha256="abc",
            size=100,
            metadata={},
            file_list=[],
        )
        wheel2 = WheelInfo(
            name="wheel2.whl",
            path=tmp_wheel,
            sha256="def",
            size=100,
            metadata={},
            file_list=[],
        )

        report = ReproducibilityReport(
            identical=False,
            wheel1=wheel1,
            wheel2=wheel2,
            differences=["Different SHA256"],
        )

        result = report.to_dict()

        assert result["identical"] is False
        assert "wheel1" in result
        assert "wheel2" in result
        assert len(result["differences"]) == 1


class TestReproducibilityChecker:
    """Test cases for ReproducibilityChecker class."""

    def test_initialization(self):
        """Test ReproducibilityChecker initialization."""
        checker = ReproducibilityChecker()

        assert checker.ignore_timestamps is True
        assert checker.ignore_build_paths is True

    def test_analyze_wheel(self, tmp_wheel: Path):
        """Test wheel analysis."""
        checker = ReproducibilityChecker()
        wheel_info = checker.analyze_wheel(tmp_wheel)

        assert wheel_info.name == tmp_wheel.name
        assert wheel_info.path == tmp_wheel
        assert wheel_info.size == tmp_wheel.stat().st_size
        assert len(wheel_info.sha256) == 64  # SHA256 hex length
        assert len(wheel_info.file_list) > 0
        assert "test_package/__init__.py" in wheel_info.file_list

    def test_analyze_wheel_metadata(self, tmp_wheel: Path):
        """Test wheel metadata extraction."""
        checker = ReproducibilityChecker()
        wheel_info = checker.analyze_wheel(tmp_wheel)

        assert wheel_info.metadata is not None
        assert "Name" in wheel_info.metadata
        assert wheel_info.metadata["Name"] == "test-package"
        assert wheel_info.metadata["Version"] == "1.0.0"

    def test_compare_identical_wheels(self, tmp_wheel: Path):
        """Test comparison of identical wheels."""
        checker = ReproducibilityChecker()
        report = checker.compare_wheels(tmp_wheel, tmp_wheel)

        assert report.identical is True
        assert len(report.differences) == 0
        assert report.wheel1.sha256 == report.wheel2.sha256

    def test_compare_different_wheels(self, tmp_wheel: Path, tmp_wheel_different: Path):
        """Test comparison of different wheels."""
        checker = ReproducibilityChecker()
        report = checker.compare_wheels(tmp_wheel, tmp_wheel_different)

        assert report.identical is False
        assert len(report.differences) > 0
        assert report.wheel1.sha256 != report.wheel2.sha256

    def test_compare_wheel_contents_identical(self, tmp_wheel: Path):
        """Test file-by-file comparison of identical wheels."""
        checker = ReproducibilityChecker()
        result = checker.compare_wheel_contents(tmp_wheel, tmp_wheel)

        assert "identical_files" in result
        assert "different_files" in result
        assert result["identical_files"] > 0
        assert result["different_files"] == 0

    def test_compare_wheel_contents_different(
        self, tmp_wheel: Path, tmp_wheel_different: Path
    ):
        """Test file-by-file comparison of different wheels."""
        checker = ReproducibilityChecker()
        result = checker.compare_wheel_contents(tmp_wheel, tmp_wheel_different)

        assert "identical_files" in result
        assert "different_files" in result
        assert result["different_files"] > 0
        assert "differences" in result

    def test_parse_metadata(self):
        """Test metadata parsing."""
        checker = ReproducibilityChecker()
        metadata_text = """Name: test-package
Version: 1.0.0
Author: Test Author
Requires-Dist: requests>=2.0
Requires-Dist: pytest>=7.0
"""

        metadata = checker._parse_metadata(metadata_text)

        assert metadata["Name"] == "test-package"
        assert metadata["Version"] == "1.0.0"
        assert metadata["Author"] == "Test Author"
        assert isinstance(metadata["Requires-Dist"], list)
        assert len(metadata["Requires-Dist"]) == 2

    def test_compare_metadata_identical(self):
        """Test comparison of identical metadata."""
        checker = ReproducibilityChecker()
        meta1 = {"Name": "test", "Version": "1.0.0"}
        meta2 = {"Name": "test", "Version": "1.0.0"}

        differences = checker._compare_metadata(meta1, meta2)

        assert len(differences) == 0

    def test_compare_metadata_different(self):
        """Test comparison of different metadata."""
        checker = ReproducibilityChecker()
        meta1 = {"Name": "test", "Version": "1.0.0"}
        meta2 = {"Name": "test", "Version": "2.0.0"}

        differences = checker._compare_metadata(meta1, meta2)

        assert len(differences) > 0
        assert any("Version" in diff for diff in differences)

    def test_compare_metadata_ignores_timestamps(self):
        """Test that timestamp fields are ignored."""
        checker = ReproducibilityChecker()
        checker.ignore_timestamps = True

        meta1 = {"Name": "test", "Build-Date": "2024-01-01"}
        meta2 = {"Name": "test", "Build-Date": "2024-01-02"}

        differences = checker._compare_metadata(meta1, meta2)

        # Build-Date should be ignored
        assert len(differences) == 0

    def test_compare_metadata_ignores_build_paths(self):
        """Test that build path fields are ignored."""
        checker = ReproducibilityChecker()
        checker.ignore_build_paths = True

        meta1 = {"Name": "test", "Home-page": "http://example.com/path1"}
        meta2 = {"Name": "test", "Home-page": "http://example.com/path2"}

        differences = checker._compare_metadata(meta1, meta2)

        # Home-page should be ignored
        assert len(differences) == 0

    def test_analyze_wheel_with_error(self, tmp_path: Path):
        """Test wheel analysis with an invalid file."""
        checker = ReproducibilityChecker()

        # Create an empty file that's not a valid wheel
        invalid_wheel = tmp_path / "invalid.whl"
        invalid_wheel.write_text("not a zip file")

        wheel_info = checker.analyze_wheel(invalid_wheel)

        # Should still return WheelInfo with error in metadata
        assert wheel_info is not None
        assert "error" in wheel_info.metadata

    def test_compare_wheel_contents_with_missing_files(
        self, tmp_wheel: Path, tmp_path: Path
    ):
        """Test comparison when files are missing in one wheel."""
        # Create a wheel with fewer files
        minimal_wheel = tmp_path / "minimal.whl"
        with zipfile.ZipFile(minimal_wheel, "w") as zf:
            zf.writestr("test_package/__init__.py", "# Minimal\n")

        checker = ReproducibilityChecker()
        result = checker.compare_wheel_contents(tmp_wheel, minimal_wheel)

        # Should handle gracefully
        assert "identical_files" in result or "error" in result


class TestCheckReproducibilityFunction:
    """Test cases for the convenience function."""

    def test_check_reproducibility_identical(self, tmp_wheel: Path):
        """Test convenience function with identical wheels."""
        report = check_reproducibility(tmp_wheel, tmp_wheel)

        assert isinstance(report, ReproducibilityReport)
        assert report.identical is True

    def test_check_reproducibility_different(
        self, tmp_wheel: Path, tmp_wheel_different: Path
    ):
        """Test convenience function with different wheels."""
        report = check_reproducibility(tmp_wheel, tmp_wheel_different)

        assert isinstance(report, ReproducibilityReport)
        assert report.identical is False


class TestReproducibilityCheckerIntegration:
    """Integration tests for reproducibility checking."""

    def test_full_workflow(self, tmp_wheel: Path, tmp_wheel_different: Path):
        """Test complete workflow from analysis to comparison."""
        checker = ReproducibilityChecker()

        # Analyze both wheels
        wheel1_info = checker.analyze_wheel(tmp_wheel)
        wheel2_info = checker.analyze_wheel(tmp_wheel_different)

        assert wheel1_info.sha256 != wheel2_info.sha256

        # Compare wheels
        report = checker.compare_wheels(tmp_wheel, tmp_wheel_different)

        assert report.identical is False
        assert len(report.differences) > 0

        # Check detailed comparison
        content_comparison = checker.compare_wheel_contents(
            tmp_wheel, tmp_wheel_different
        )

        assert content_comparison["different_files"] > 0

    def test_reproducibility_with_config_options(
        self, tmp_wheel: Path, tmp_wheel_different: Path
    ):
        """Test reproducibility checking with different configuration options."""
        # Test with timestamps ignored
        checker1 = ReproducibilityChecker()
        checker1.ignore_timestamps = True
        checker1.ignore_build_paths = False

        report1 = checker1.compare_wheels(tmp_wheel, tmp_wheel_different)

        # Test with build paths ignored
        checker2 = ReproducibilityChecker()
        checker2.ignore_timestamps = False
        checker2.ignore_build_paths = True

        report2 = checker2.compare_wheels(tmp_wheel, tmp_wheel_different)

        # Both should detect differences
        assert report1.identical is False
        assert report2.identical is False
