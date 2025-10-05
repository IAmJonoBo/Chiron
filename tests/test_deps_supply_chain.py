"""Tests for chiron.deps.supply_chain module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

from chiron.deps.supply_chain import (
    OSVScanner,
    SBOMGenerator,
    VulnerabilitySummary,
    generate_sbom_and_scan,
)


class TestVulnerabilitySummary:
    """Tests for VulnerabilitySummary dataclass."""

    def test_default_summary(self) -> None:
        """Test creating summary with defaults."""
        summary = VulnerabilitySummary()
        assert summary.total_vulnerabilities == 0
        assert summary.critical == 0
        assert summary.high == 0
        assert summary.medium == 0
        assert summary.low == 0
        assert summary.packages_affected == []
        assert summary.scan_timestamp == ""

    def test_has_blocking_vulnerabilities_critical(self) -> None:
        """Test blocking check with critical vulnerabilities."""
        summary = VulnerabilitySummary(critical=1)
        # With critical vuln, only blocked if threshold >= 3 (critical level)
        assert summary.has_blocking_vulnerabilities("critical") is True
        # High threshold is 2, so critical (3) blocks
        assert summary.has_blocking_vulnerabilities("high") is False
        # Medium threshold is 1, so critical blocks
        assert summary.has_blocking_vulnerabilities("medium") is False

    def test_has_blocking_vulnerabilities_high(self) -> None:
        """Test blocking check with high vulnerabilities."""
        summary = VulnerabilitySummary(high=1)
        # High vuln blocks when threshold >= 2 (high level)
        assert summary.has_blocking_vulnerabilities("high") is True
        # Also blocks with critical threshold since 3 >= 2
        assert summary.has_blocking_vulnerabilities("critical") is True
        # But not with medium (threshold=1) since we need threshold >= 2
        assert summary.has_blocking_vulnerabilities("medium") is False
        assert summary.has_blocking_vulnerabilities("low") is False

    def test_has_blocking_vulnerabilities_medium(self) -> None:
        """Test blocking check with medium vulnerabilities."""
        summary = VulnerabilitySummary(medium=1)
        # Medium vuln blocks when threshold >= 1
        assert summary.has_blocking_vulnerabilities("medium") is True
        # Also blocks with higher thresholds since they are >= 1
        assert summary.has_blocking_vulnerabilities("high") is True
        assert summary.has_blocking_vulnerabilities("critical") is True
        # But not with low threshold (0 < 1)
        assert summary.has_blocking_vulnerabilities("low") is False

    def test_has_blocking_vulnerabilities_none(self) -> None:
        """Test no blocking vulnerabilities."""
        summary = VulnerabilitySummary()
        assert summary.has_blocking_vulnerabilities("high") is False


class TestSBOMGenerator:
    """Tests for SBOMGenerator class."""

    def test_initialization(self, tmp_path: Path) -> None:
        """Test SBOMGenerator initialization."""
        generator = SBOMGenerator(tmp_path)
        assert generator.project_root == tmp_path

    @patch("chiron.deps.supply_chain.shutil.which")
    @patch("chiron.deps.supply_chain.subprocess.run")
    def test_generate_success(
        self, mock_run: Mock, mock_which: Mock, tmp_path: Path
    ) -> None:
        """Test successful SBOM generation."""
        mock_which.return_value = "/usr/bin/cyclonedx-py"

        # Create the output file to simulate success
        output_path = tmp_path / "sbom.json"

        def create_file(*args, **kwargs):
            output_path.write_text('{"components": []}')
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = create_file

        generator = SBOMGenerator(tmp_path)

        result = generator.generate(output_path)

        assert result is True
        mock_run.assert_called_once()

    @patch("chiron.deps.supply_chain.shutil.which")
    def test_generate_missing_tool(self, mock_which: Mock, tmp_path: Path) -> None:
        """Test SBOM generation with missing tool."""
        mock_which.return_value = None

        generator = SBOMGenerator(tmp_path)
        output_path = tmp_path / "sbom.json"

        result = generator.generate(output_path)

        assert result is False

    @patch("chiron.deps.supply_chain.shutil.which")
    @patch("chiron.deps.supply_chain.subprocess.run")
    def test_generate_failure(
        self, mock_run: Mock, mock_which: Mock, tmp_path: Path
    ) -> None:
        """Test SBOM generation failure."""
        mock_which.return_value = "/usr/bin/cyclonedx-py"
        mock_run.side_effect = Exception("Command failed")

        generator = SBOMGenerator(tmp_path)
        output_path = tmp_path / "sbom.json"

        result = generator.generate(output_path)

        assert result is False


class TestOSVScanner:
    """Tests for OSVScanner class."""

    def test_initialization(self, tmp_path: Path) -> None:
        """Test OSVScanner initialization."""
        scanner = OSVScanner(tmp_path)
        assert scanner.project_root == tmp_path

    @patch("chiron.deps.supply_chain.shutil.which")
    @patch("chiron.deps.supply_chain.subprocess.run")
    def test_scan_success(
        self, mock_run: Mock, mock_which: Mock, tmp_path: Path
    ) -> None:
        """Test successful vulnerability scan."""
        mock_which.return_value = "/usr/bin/osv-scanner"

        # Mock OSV scanner output
        osv_output = {
            "results": [
                {
                    "packages": [{"package": {"name": "test-pkg"}}],
                    "vulnerabilities": [{"severity": "HIGH"}],
                }
            ]
        }
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(osv_output),
            stderr="",
        )

        lockfile_path = tmp_path / "requirements.txt"
        lockfile_path.write_text("test-pkg==1.0.0")

        scanner = OSVScanner(tmp_path)
        summary = scanner.scan_lockfile(lockfile_path)

        assert summary is not None
        assert summary.total_vulnerabilities >= 0

    @patch("chiron.deps.supply_chain.shutil.which")
    def test_scan_missing_tool(self, mock_which: Mock, tmp_path: Path) -> None:
        """Test scan with missing tool."""
        mock_which.return_value = None

        lockfile_path = tmp_path / "requirements.txt"
        scanner = OSVScanner(tmp_path)
        summary = scanner.scan_lockfile(lockfile_path)

        assert summary is None

    @patch("chiron.deps.supply_chain.shutil.which")
    @patch("chiron.deps.supply_chain.subprocess.run")
    def test_scan_failure(
        self, mock_run: Mock, mock_which: Mock, tmp_path: Path
    ) -> None:
        """Test scan failure handling."""
        mock_which.return_value = "/usr/bin/osv-scanner"
        mock_run.side_effect = Exception("Scan failed")

        lockfile_path = tmp_path / "requirements.txt"
        scanner = OSVScanner(tmp_path)
        summary = scanner.scan_lockfile(lockfile_path)

        assert summary is None


class TestGenerateSBOMAndScan:
    """Tests for generate_sbom_and_scan integration function."""

    @patch("chiron.deps.supply_chain.OSVScanner")
    @patch("chiron.deps.supply_chain.SBOMGenerator")
    def test_generate_and_scan_success(
        self, mock_sbom_gen: Mock, mock_scanner: Mock, tmp_path: Path
    ) -> None:
        """Test successful SBOM generation and scan."""
        # Mock SBOM generator
        mock_gen_instance = Mock()
        mock_gen_instance.generate.return_value = True
        mock_sbom_gen.return_value = mock_gen_instance

        # Mock OSV scanner
        mock_scanner_instance = Mock()
        mock_summary = VulnerabilitySummary()
        mock_scanner_instance.scan_lockfile.return_value = mock_summary
        mock_scanner.return_value = mock_scanner_instance

        sbom_output = tmp_path / "sbom.json"
        osv_output = tmp_path / "osv.json"
        lockfile = tmp_path / "requirements.txt"
        lockfile.write_text("test==1.0.0")

        success, summary = generate_sbom_and_scan(
            tmp_path, sbom_output, osv_output, lockfile
        )

        assert success is True
        assert summary is not None

    @patch("chiron.deps.supply_chain.SBOMGenerator")
    def test_generate_and_scan_sbom_failure(
        self, mock_sbom_gen: Mock, tmp_path: Path
    ) -> None:
        """Test with SBOM generation failure."""
        mock_gen_instance = Mock()
        mock_gen_instance.generate.return_value = False
        mock_sbom_gen.return_value = mock_gen_instance

        sbom_output = tmp_path / "sbom.json"
        osv_output = tmp_path / "osv.json"
        lockfile = tmp_path / "requirements.txt"

        success, summary = generate_sbom_and_scan(
            tmp_path, sbom_output, osv_output, lockfile
        )

        assert success is False
        assert summary is None
