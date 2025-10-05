"""Tests for chiron.wizard module - interactive wizard mode."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from chiron.wizard import ChironWizard, run_init_wizard


class TestChironWizard:
    """Tests for ChironWizard class."""

    def test_initialization(self) -> None:
        """Test wizard initialization."""
        wizard = ChironWizard()
        assert wizard.config == {}

    @patch("chiron.wizard.console")
    def test_welcome(self, mock_console: Mock) -> None:
        """Test welcome message display."""
        wizard = ChironWizard()
        wizard.welcome()

        # Should print welcome panel and blank line
        assert mock_console.print.call_count >= 2

    @patch("chiron.wizard.Confirm.ask")
    @patch("chiron.wizard.Prompt.ask")
    @patch("chiron.wizard.console")
    def test_init_project_basic(
        self, mock_console: Mock, mock_prompt: Mock, mock_confirm: Mock
    ) -> None:
        """Test basic project initialization."""
        # Mock user inputs
        mock_prompt.side_effect = [
            "my-service",  # service name
            "1.0.0",  # version
            "http://otel:4317",  # OTLP endpoint
            "my-wheelhouse",  # wheelhouse path
            "3.12 3.13",  # python versions
        ]
        mock_confirm.side_effect = [
            True,  # telemetry enabled
            True,  # security enabled
            True,  # audit logging
            False,  # require signatures
            True,  # linux
            True,  # macos
            False,  # windows
            False,  # save config
        ]

        wizard = ChironWizard()
        config = wizard.init_project()

        assert config["service_name"] == "my-service"
        assert config["version"] == "1.0.0"
        assert config["telemetry"]["enabled"] is True
        assert config["telemetry"]["otlp_endpoint"] == "http://otel:4317"
        assert config["security"]["enabled"] is True
        assert config["security"]["audit_logging"] is True
        assert config["security"]["require_signatures"] is False
        assert config["wheelhouse"]["path"] == "my-wheelhouse"
        assert "linux" in config["wheelhouse"]["platforms"]
        assert "macos" in config["wheelhouse"]["platforms"]
        assert "windows" not in config["wheelhouse"]["platforms"]
        assert "3.12" in config["wheelhouse"]["python_versions"]
        assert "3.13" in config["wheelhouse"]["python_versions"]

    @patch("chiron.wizard.Confirm.ask")
    @patch("chiron.wizard.Prompt.ask")
    @patch("chiron.wizard.console")
    def test_init_project_telemetry_disabled(
        self, mock_console: Mock, mock_prompt: Mock, mock_confirm: Mock
    ) -> None:
        """Test project initialization with telemetry disabled."""
        mock_prompt.side_effect = [
            "test-service",
            "0.1.0",
            "wheelhouse",
            "3.12",
        ]
        mock_confirm.side_effect = [
            False,  # telemetry disabled
            False,  # security disabled
            True,  # linux
            False,  # macos
            False,  # windows
            False,  # don't save
        ]

        wizard = ChironWizard()
        config = wizard.init_project()

        assert config["telemetry"]["enabled"] is False
        # OTLP endpoint should still have default
        assert "otlp_endpoint" in config["telemetry"]

    @patch("chiron.wizard.Confirm.ask")
    @patch("chiron.wizard.Prompt.ask")
    @patch("chiron.wizard.console")
    def test_init_project_security_disabled(
        self, mock_console: Mock, mock_prompt: Mock, mock_confirm: Mock
    ) -> None:
        """Test project initialization with security disabled."""
        mock_prompt.side_effect = [
            "test-service",  # service_name
            "0.1.0",  # version
            "http://localhost:4317",  # otlp_endpoint (telemetry enabled)
            "wheelhouse",  # wheelhouse_path
            "3.12 3.13",  # python_versions
        ]
        mock_confirm.side_effect = [
            True,  # telemetry enabled
            False,  # security disabled
            True,  # linux
            False,  # macos
            False,  # windows
            False,  # don't save
        ]

        wizard = ChironWizard()
        config = wizard.init_project()

        assert config["security"]["enabled"] is False
        # audit_logging and require_signatures should have defaults
        assert "audit_logging" in config["security"]
        assert "require_signatures" in config["security"]

    @patch("builtins.open")
    @patch("chiron.wizard.Confirm.ask")
    @patch("chiron.wizard.Prompt.ask")
    @patch("chiron.wizard.console")
    def test_init_project_save_config(
        self,
        mock_console: Mock,
        mock_prompt: Mock,
        mock_confirm: Mock,
        mock_open: Mock,
        tmp_path: Path,
    ) -> None:
        """Test saving configuration to file."""
        mock_prompt.side_effect = [
            "test-service",  # service_name
            "0.1.0",  # version
            "http://localhost:4317",  # otlp_endpoint (telemetry enabled)
            "wheelhouse",  # wheelhouse_path
            "3.12 3.13",  # python_versions
        ]
        mock_confirm.side_effect = [
            True,  # telemetry
            True,  # security
            True,  # audit logging
            True,  # require signatures
            True,  # linux
            False,  # macos
            False,  # windows
            True,  # save config
        ]

        # Mock file handle
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        wizard = ChironWizard()
        _config = wizard.init_project()

        # Verify file was opened for writing
        mock_open.assert_called_once()
        # Verify json.dump was called
        mock_file.write.assert_called()

    @patch("chiron.wizard.Confirm.ask")
    @patch("chiron.wizard.Prompt.ask")
    @patch("chiron.wizard.console")
    def test_build_wheelhouse_wizard(
        self, mock_console: Mock, mock_prompt: Mock, mock_confirm: Mock
    ) -> None:
        """Test wheelhouse build wizard."""
        mock_prompt.side_effect = [
            "my-wheelhouse",  # output directory
        ]
        mock_confirm.side_effect = [
            True,  # with SBOM
            False,  # no signatures
            True,  # with vuln scan
        ]

        wizard = ChironWizard()
        config = wizard.build_wheelhouse_wizard()

        assert config["output_dir"] == "my-wheelhouse"
        assert config["with_sbom"] is True
        assert config["with_signatures"] is False
        assert config["with_vuln_scan"] is True

    @patch("chiron.wizard.Confirm.ask")
    @patch("chiron.wizard.Prompt.ask")
    @patch("chiron.wizard.console")
    def test_build_wheelhouse_wizard_minimal(
        self, mock_console: Mock, mock_prompt: Mock, mock_confirm: Mock
    ) -> None:
        """Test wheelhouse build wizard with minimal options."""
        mock_prompt.side_effect = [
            "wheelhouse",  # output directory (default)
        ]
        mock_confirm.side_effect = [
            False,  # no SBOM
            False,  # no signatures
            False,  # no vuln scan
        ]

        wizard = ChironWizard()
        config = wizard.build_wheelhouse_wizard()

        assert config["with_sbom"] is False
        assert config["with_signatures"] is False
        assert config["with_vuln_scan"] is False

    @patch("chiron.wizard.Confirm.ask")
    @patch("chiron.wizard.Prompt.ask")
    @patch("chiron.wizard.console")
    def test_verify_wizard(
        self, mock_console: Mock, mock_prompt: Mock, mock_confirm: Mock
    ) -> None:
        """Test artifact verification wizard."""
        mock_prompt.side_effect = [
            "/path/to/artifact",  # target
        ]
        mock_confirm.side_effect = [
            True,  # verify signatures
            True,  # verify SBOM
            False,  # no provenance
            True,  # verify hashes
        ]

        wizard = ChironWizard()
        config = wizard.verify_wizard()

        assert config["target"] == "/path/to/artifact"
        assert config["verify_signatures"] is True
        assert config["verify_sbom"] is True
        assert config["verify_provenance"] is False
        assert config["verify_hashes"] is True

    @patch("chiron.wizard.Confirm.ask")
    @patch("chiron.wizard.Prompt.ask")
    @patch("chiron.wizard.console")
    def test_verify_wizard_no_checks(
        self, mock_console: Mock, mock_prompt: Mock, mock_confirm: Mock
    ) -> None:
        """Test verification wizard with all checks disabled."""
        mock_prompt.side_effect = [
            ".",  # target (default)
        ]
        mock_confirm.side_effect = [
            False,  # no signatures
            False,  # no SBOM
            False,  # no provenance
            False,  # no hashes
        ]

        wizard = ChironWizard()
        config = wizard.verify_wizard()

        assert config["verify_signatures"] is False
        assert config["verify_sbom"] is False
        assert config["verify_provenance"] is False
        assert config["verify_hashes"] is False

    @patch("chiron.wizard.Confirm.ask")
    def test_select_platforms_all(self, mock_confirm: Mock) -> None:
        """Test selecting all platforms."""
        mock_confirm.side_effect = [True, True, True]  # linux, macos, windows

        wizard = ChironWizard()
        platforms = wizard._select_platforms()

        assert "linux" in platforms
        assert "macos" in platforms
        assert "windows" in platforms

    @patch("chiron.wizard.Confirm.ask")
    def test_select_platforms_single(self, mock_confirm: Mock) -> None:
        """Test selecting single platform."""
        mock_confirm.side_effect = [True, False, False]  # only linux

        wizard = ChironWizard()
        platforms = wizard._select_platforms()

        assert platforms == ["linux"]

    @patch("chiron.wizard.Confirm.ask")
    def test_select_platforms_none(self, mock_confirm: Mock) -> None:
        """Test selecting no platforms."""
        mock_confirm.side_effect = [False, False, False]

        wizard = ChironWizard()
        platforms = wizard._select_platforms()

        assert platforms == []

    @patch("chiron.wizard.Prompt.ask")
    def test_select_python_versions_single(self, mock_prompt: Mock) -> None:
        """Test selecting single Python version."""
        mock_prompt.return_value = "3.12"

        wizard = ChironWizard()
        versions = wizard._select_python_versions()

        assert versions == ["3.12"]

    @patch("chiron.wizard.Prompt.ask")
    def test_select_python_versions_multiple(self, mock_prompt: Mock) -> None:
        """Test selecting multiple Python versions."""
        mock_prompt.return_value = "3.12 3.13"

        wizard = ChironWizard()
        versions = wizard._select_python_versions()

        assert "3.12" in versions
        assert "3.13" in versions

    @patch("chiron.wizard.Prompt.ask")
    def test_select_python_versions_with_extra_spaces(self, mock_prompt: Mock) -> None:
        """Test parsing Python versions with extra spaces."""
        mock_prompt.return_value = "3.12  3.13   3.14"

        wizard = ChironWizard()
        versions = wizard._select_python_versions()

        # split() handles multiple spaces
        assert len([v for v in versions if v]) >= 3

    @patch("chiron.wizard.console")
    def test_display_summary(self, mock_console: Mock) -> None:
        """Test configuration summary display."""
        wizard = ChironWizard()
        config = {
            "service_name": "test-service",
            "version": "1.0.0",
            "telemetry": {"enabled": True},
            "security": {"enabled": True},
            "wheelhouse": {
                "path": "wheelhouse",
                "platforms": ["linux", "macos"],
                "python_versions": ["3.12", "3.13"],
            },
        }

        wizard._display_summary(config)

        # Should print summary heading and table
        assert mock_console.print.call_count >= 2


@patch("chiron.wizard.ChironWizard")
def test_run_init_wizard(mock_wizard_class: Mock) -> None:
    """Test run_init_wizard function."""
    mock_wizard = Mock()
    mock_wizard.init_project.return_value = {"service_name": "test"}
    mock_wizard_class.return_value = mock_wizard

    config = run_init_wizard()

    mock_wizard_class.assert_called_once()
    mock_wizard.init_project.assert_called_once()
    assert config["service_name"] == "test"
