"""Tests for chiron.doctor modules - boundary tests."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestDoctorModuleStructure:
    """Tests for doctor module structure and existence."""

    def test_doctor_module_files_exist(self) -> None:
        """Test that doctor module files exist."""
        doctor_path = Path("src/chiron/doctor")
        assert doctor_path.exists()
        assert (doctor_path / "__init__.py").exists()
        assert (doctor_path / "models.py").exists()
        assert (doctor_path / "offline.py").exists()
        assert (doctor_path / "bootstrap.py").exists()
        assert (doctor_path / "package_cli.py").exists()

    def test_doctor_models_file_structure(self) -> None:
        """Test models.py has expected structure."""
        models_path = Path("src/chiron/doctor/models.py")
        content = models_path.read_text()
        assert "DEFAULT_SENTENCE_TRANSFORMERS" in content
        assert "DEFAULT_CROSS_ENCODERS" in content
        assert "DEFAULT_SPACY_MODELS" in content

    def test_doctor_offline_file_structure(self) -> None:
        """Test offline.py exists and has structure."""
        offline_path = Path("src/chiron/doctor/offline.py")
        assert offline_path.exists()
        content = offline_path.read_text()
        # Check it's a diagnostic CLI
        assert "offline" in content.lower() and "packaging" in content.lower()

    def test_doctor_bootstrap_file_structure(self) -> None:
        """Test bootstrap.py has expected structure."""
        bootstrap_path = Path("src/chiron/doctor/bootstrap.py")
        content = bootstrap_path.read_text()
        assert "check" in content.lower() or "manifest" in content.lower()

    def test_doctor_package_cli_file_structure(self) -> None:
        """Test package_cli.py has expected structure."""
        package_cli_path = Path("src/chiron/doctor/package_cli.py")
        content = package_cli_path.read_text()
        assert "build_parser" in content
        assert "argparse" in content


class TestDoctorModuleBoundaries:
    """Test boundaries and interfaces without importing."""

    def test_models_constants_defined(self) -> None:
        """Test that models module defines expected constants."""
        models_path = Path("src/chiron/doctor/models.py")
        content = models_path.read_text()

        # Check for the constants
        assert "DEFAULT_SENTENCE_TRANSFORMERS = [" in content
        assert "DEFAULT_CROSS_ENCODERS = [" in content
        assert "DEFAULT_SPACY_MODELS = [" in content

    def test_offline_functions_defined(self) -> None:
        """Test that offline/models module defines expected functions."""
        # Check models.py which has the actual download functions
        models_path = Path("src/chiron/doctor/models.py")
        content = models_path.read_text()

        # Check for function definitions
        assert "def _ensure_env_path(" in content
        assert "def _download_hf_snapshots(" in content
        assert "def _warm_sentence_transformers(" in content

    def test_bootstrap_structure(self) -> None:
        """Test bootstrap module structure."""
        bootstrap_path = Path("src/chiron/doctor/bootstrap.py")
        content = bootstrap_path.read_text()

        # Check for expected patterns
        assert "def " in content  # Has functions
        assert "import" in content  # Has imports

    def test_package_cli_has_parser(self) -> None:
        """Test package_cli has parser builder."""
        package_cli_path = Path("src/chiron/doctor/package_cli.py")
        content = package_cli_path.read_text()

        assert "def build_parser(" in content
        assert "ArgumentParser" in content
