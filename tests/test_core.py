"""Tests for ChironCore functionality."""

import pytest
from unittest.mock import patch

from chiron.core import ChironCore
from chiron.exceptions import ChironError, ChironConfigurationError


class TestChironCore:
    """Test cases for ChironCore class."""

    def test_initialization_with_defaults(self):
        """Test ChironCore initialization with default parameters."""
        core = ChironCore()
        
        assert core.config == {}
        assert core.enable_telemetry is True
        assert core.security_mode is True

    def test_initialization_with_config(self, basic_config):
        """Test ChironCore initialization with configuration."""
        core = ChironCore(config=basic_config)
        
        assert core.config == basic_config
        assert core.enable_telemetry is True
        assert core.security_mode is True

    def test_initialization_with_disabled_features(self):
        """Test ChironCore initialization with disabled features."""
        core = ChironCore(enable_telemetry=False, security_mode=False)
        
        assert core.enable_telemetry is False
        assert core.security_mode is False

    def test_validate_config_success(self, core_instance):
        """Test successful configuration validation."""
        result = core_instance.validate_config()
        assert result is True

    def test_validate_config_missing_required_field(self):
        """Test configuration validation with missing required field."""
        core = ChironCore(config={})
        
        with pytest.raises(ChironConfigurationError) as exc_info:
            core.validate_config()
        
        assert "service_name" in str(exc_info.value)

    def test_health_check(self, core_instance):
        """Test health check functionality."""
        health = core_instance.health_check()
        
        assert health["status"] == "healthy"
        assert health["version"] == "0.1.0"
        assert "timestamp" in health
        assert health["telemetry_enabled"] is False
        assert health["security_mode"] is True

    def test_process_data_success(self, core_instance, sample_data):
        """Test successful data processing."""
        result = core_instance.process_data(sample_data)
        
        assert result["processed"] is True
        assert result["original"] == sample_data

    def test_process_data_with_none_input(self, core_instance):
        """Test data processing with None input."""
        with pytest.raises(ChironError) as exc_info:
            core_instance.process_data(None)
        
        assert "Input data cannot be None" in str(exc_info.value)

    def test_process_data_with_security_disabled(self, basic_config, sample_data):
        """Test data processing with security disabled."""
        basic_config["security"]["enabled"] = False
        core = ChironCore(config=basic_config, security_mode=False)
        
        result = core.process_data(sample_data)
        assert result["processed"] is True

    @patch('chiron.core.trace')
    def test_process_data_with_telemetry(self, mock_trace, basic_config, sample_data):
        """Test data processing with telemetry enabled."""
        # Mock the tracer and span
        mock_tracer = mock_trace.get_tracer.return_value
        mock_span = mock_tracer.start_as_current_span.return_value.__enter__.return_value
        
        core = ChironCore(config=basic_config, enable_telemetry=True)
        core.tracer = mock_tracer
        
        result = core.process_data(sample_data)
        
        assert result["processed"] is True
        mock_tracer.start_as_current_span.assert_called_once_with("process_data")
        mock_span.set_attribute.assert_called_once_with("data.type", "dict")

    def test_setup_telemetry_import_error(self, basic_config):
        """Test telemetry setup with missing OpenTelemetry."""
        with patch('chiron.core.trace', side_effect=ImportError("No module")):
            core = ChironCore(config=basic_config, enable_telemetry=True)
            assert core.tracer is None

    def test_process_data_internal_exception(self, core_instance):
        """Test data processing with internal exception."""
        with patch.object(core_instance, '_validate_input', side_effect=RuntimeError("Test error")):
            with pytest.raises(ChironError) as exc_info:
                core_instance.process_data({"test": "data"})
            
            assert "Failed to process data" in str(exc_info.value)


class TestChironCoreIntegration:
    """Integration tests for ChironCore."""

    def test_full_workflow(self):
        """Test complete workflow from initialization to data processing."""
        config = {
            "service_name": "integration-test",
            "telemetry": {"enabled": False},
            "security": {"enabled": True},
        }
        
        # Initialize
        core = ChironCore(config=config, enable_telemetry=False)
        
        # Validate configuration
        assert core.validate_config() is True
        
        # Health check
        health = core.health_check()
        assert health["status"] == "healthy"
        
        # Process data
        data = {"test": "integration", "value": 123}
        result = core.process_data(data)
        
        assert result["processed"] is True
        assert result["original"] == data