"""Tests for chiron.observability.tracing module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, Mock, patch

from opentelemetry.sdk.trace import TracerProvider

from chiron.observability.tracing import _load_otlp_exporter, configure_tracing


class TestLoadOTLPExporter:
    """Tests for _load_otlp_exporter."""

    def test_load_otlp_exporter_success(self) -> None:
        """Test loading OTLP exporter when available."""
        # The exporter should be available since we installed it
        exporter_cls = _load_otlp_exporter()

        # Should return a class or None (if not installed)
        if exporter_cls is not None:
            assert isinstance(exporter_cls, type)

    @patch("chiron.observability.tracing.importlib.import_module")
    def test_load_otlp_exporter_not_available(self, mock_import: Mock) -> None:
        """Test when OTLP exporter module is not available."""
        mock_import.side_effect = ModuleNotFoundError("Module not found")

        result = _load_otlp_exporter()

        assert result is None

    @patch("chiron.observability.tracing.importlib.import_module")
    def test_load_otlp_exporter_class_not_found(self, mock_import: Mock) -> None:
        """Test when exporter class is not in the module."""
        mock_module = MagicMock()
        del mock_module.OTLPSpanExporter  # Make attribute not exist
        mock_import.return_value = mock_module

        result = _load_otlp_exporter()

        assert result is None

    @patch("chiron.observability.tracing.importlib.import_module")
    def test_load_otlp_exporter_not_a_class(self, mock_import: Mock) -> None:
        """Test when OTLPSpanExporter is not a class."""
        mock_module = MagicMock()
        mock_module.OTLPSpanExporter = "not a class"
        mock_import.return_value = mock_module

        result = _load_otlp_exporter()

        assert result is None


class TestConfigureTracing:
    """Tests for configure_tracing."""

    @patch("chiron.observability.tracing._TRACING_CONFIGURED", False)
    @patch("chiron.observability.tracing._load_otlp_exporter")
    @patch("chiron.observability.tracing.trace.set_tracer_provider")
    def test_configure_tracing_default(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test configuring tracing with defaults."""
        mock_load_exporter.return_value = None

        provider = configure_tracing("test-service")

        assert isinstance(provider, TracerProvider)
        mock_set_provider.assert_called_once()

    @patch("chiron.observability.tracing._TRACING_CONFIGURED", False)
    @patch("chiron.observability.tracing._load_otlp_exporter")
    @patch("chiron.observability.tracing.trace.set_tracer_provider")
    def test_configure_tracing_with_resource_attributes(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test configuring tracing with custom resource attributes."""
        mock_load_exporter.return_value = None
        custom_attrs = {"custom.key": "custom.value"}

        provider = configure_tracing("test-service", resource_attributes=custom_attrs)

        assert isinstance(provider, TracerProvider)

    @patch("chiron.observability.tracing._TRACING_CONFIGURED", False)
    @patch("chiron.observability.tracing._load_otlp_exporter")
    @patch("chiron.observability.tracing.trace.set_tracer_provider")
    def test_configure_tracing_with_console_exporter(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test configuring tracing with console exporter enabled."""
        mock_load_exporter.return_value = None

        provider = configure_tracing("test-service", console_exporter=True)

        assert isinstance(provider, TracerProvider)
        # Verify console span processor was added
        assert len(provider._active_span_processor._span_processors) >= 1

    @patch("chiron.observability.tracing._TRACING_CONFIGURED", False)
    @patch("chiron.observability.tracing._load_otlp_exporter")
    @patch("chiron.observability.tracing.trace.set_tracer_provider")
    def test_configure_tracing_sets_environment_variables(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test that environment variables are set correctly."""
        mock_load_exporter.return_value = None

        with patch.dict(os.environ, {}, clear=False):
            provider = configure_tracing("test-service")

            assert "OTEL_EXPORTER_OTLP_ENDPOINT" in os.environ
            assert isinstance(provider, TracerProvider)

    @patch("chiron.observability.tracing._TRACING_CONFIGURED", False)
    @patch("chiron.observability.tracing._load_otlp_exporter")
    @patch("chiron.observability.tracing.trace.set_tracer_provider")
    def test_configure_tracing_with_http_endpoint(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test configuring tracing with HTTP endpoint."""
        mock_load_exporter.return_value = None

        with patch.dict(
            os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://custom:4317"}
        ):
            provider = configure_tracing("test-service")

            assert os.environ.get("OTEL_EXPORTER_OTLP_INSECURE") == "true"
            assert isinstance(provider, TracerProvider)

    @patch("chiron.observability.tracing._TRACING_CONFIGURED", False)
    @patch("chiron.observability.tracing._load_otlp_exporter")
    @patch("chiron.observability.tracing.trace.set_tracer_provider")
    def test_configure_tracing_respects_env_vars(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test that existing environment variables are respected."""
        mock_load_exporter.return_value = None

        with patch.dict(
            os.environ,
            {
                "CHIRON_ENV": "production",
                "CHIRON_VERSION": "1.0.0",
            },
        ):
            provider = configure_tracing("test-service")

            assert isinstance(provider, TracerProvider)

    @patch("chiron.observability.tracing._TRACING_CONFIGURED", False)
    @patch("chiron.observability.tracing._load_otlp_exporter")
    @patch("chiron.observability.tracing.trace.set_tracer_provider")
    def test_configure_tracing_console_env_var(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test console exporter enabled via environment variable."""
        mock_load_exporter.return_value = None

        with patch.dict(os.environ, {"CHIRON_TRACE_CONSOLE": "true"}):
            provider = configure_tracing("test-service")

            assert isinstance(provider, TracerProvider)

    @patch("chiron.observability.tracing._TRACING_CONFIGURED", False)
    @patch("chiron.observability.tracing._load_otlp_exporter")
    @patch("chiron.observability.tracing.trace.set_tracer_provider")
    def test_configure_tracing_no_otlp_warning(
        self, mock_set_provider: Mock, mock_load_exporter: Mock, caplog
    ) -> None:
        """Test warning when OTLP exporter is not available."""
        import logging

        mock_load_exporter.return_value = None

        with caplog.at_level(logging.WARNING):
            provider = configure_tracing("test-service")

            assert "OTLP span exporter unavailable" in caplog.text
            assert isinstance(provider, TracerProvider)

    @patch("chiron.observability.tracing._TRACING_CONFIGURED", True)
    @patch("chiron.observability.tracing.trace.get_tracer_provider")
    def test_configure_tracing_idempotent(self, mock_get_provider: Mock) -> None:
        """Test that subsequent calls are idempotent."""
        mock_provider = Mock(spec=TracerProvider)
        mock_get_provider.return_value = mock_provider

        provider = configure_tracing("test-service")

        assert provider is mock_provider
        mock_get_provider.assert_called_once()

    @patch("chiron.observability.tracing._TRACING_CONFIGURED", False)
    @patch("chiron.observability.tracing._load_otlp_exporter")
    @patch("chiron.observability.tracing.trace.set_tracer_provider")
    def test_configure_tracing_with_otlp_exporter(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test configuring tracing with OTLP exporter available."""
        mock_exporter_cls = Mock()
        mock_exporter = Mock()
        mock_exporter_cls.return_value = mock_exporter
        mock_load_exporter.return_value = mock_exporter_cls

        provider = configure_tracing("test-service")

        assert isinstance(provider, TracerProvider)
        # Verify OTLP span processor was added
        assert len(provider._active_span_processor._span_processors) >= 1
        mock_exporter_cls.assert_called_once()
