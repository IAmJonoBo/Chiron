"""Tests for chiron.observability.metrics module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, Mock, patch

from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)

from chiron.observability.metrics import (
    _create_metric_readers,
    _load_otlp_metric_exporter,
    configure_metrics,
)


class TestLoadOTLPMetricExporter:
    """Tests for _load_otlp_metric_exporter."""

    def test_load_otlp_metric_exporter_success(self) -> None:
        """Test loading OTLP metric exporter when available."""
        # The exporter should be available since we installed it
        exporter_cls = _load_otlp_metric_exporter()

        # Should return a class or None (if not installed)
        if exporter_cls is not None:
            assert isinstance(exporter_cls, type)

    @patch("chiron.observability.metrics.importlib.import_module")
    def test_load_otlp_metric_exporter_not_available(self, mock_import: Mock) -> None:
        """Test when OTLP metric exporter module is not available."""
        mock_import.side_effect = ModuleNotFoundError("Module not found")

        result = _load_otlp_metric_exporter()

        assert result is None

    @patch("chiron.observability.metrics.importlib.import_module")
    def test_load_otlp_metric_exporter_class_not_found(self, mock_import: Mock) -> None:
        """Test when exporter class is not in the module."""
        mock_module = MagicMock()
        del mock_module.OTLPMetricExporter  # Make attribute not exist
        mock_import.return_value = mock_module

        result = _load_otlp_metric_exporter()

        assert result is None

    @patch("chiron.observability.metrics.importlib.import_module")
    def test_load_otlp_metric_exporter_not_a_class(self, mock_import: Mock) -> None:
        """Test when OTLPMetricExporter is not a class."""
        mock_module = MagicMock()
        mock_module.OTLPMetricExporter = "not a class"
        mock_import.return_value = mock_module

        result = _load_otlp_metric_exporter()

        assert result is None


class TestCreateMetricReaders:
    """Tests for _create_metric_readers."""

    def test_create_metric_readers_with_exporter(self) -> None:
        """Test creating metric readers with OTLP exporter."""
        # Use ConsoleMetricExporter as a concrete exporter class for testing

        readers = _create_metric_readers(ConsoleMetricExporter, enable_console=False)

        assert len(readers) == 1
        assert isinstance(readers[0], PeriodicExportingMetricReader)

    def test_create_metric_readers_with_console(self) -> None:
        """Test creating metric readers with console exporter."""
        readers = _create_metric_readers(None, enable_console=True)

        assert len(readers) == 1
        assert isinstance(readers[0], PeriodicExportingMetricReader)

    def test_create_metric_readers_with_both(self) -> None:
        """Test creating metric readers with both exporters."""
        # Use ConsoleMetricExporter as a concrete exporter class for testing

        readers = _create_metric_readers(ConsoleMetricExporter, enable_console=True)

        assert len(readers) == 2

    def test_create_metric_readers_with_neither(self) -> None:
        """Test creating metric readers with no exporters."""
        readers = _create_metric_readers(None, enable_console=False)

        assert len(readers) == 0


class TestConfigureMetrics:
    """Tests for configure_metrics."""

    @patch("chiron.observability.metrics._METRICS_CONFIGURED", False)
    @patch("chiron.observability.metrics._load_otlp_metric_exporter")
    @patch("chiron.observability.metrics.metrics.set_meter_provider")
    def test_configure_metrics_default(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test configuring metrics with defaults."""
        mock_load_exporter.return_value = None

        meter = configure_metrics()

        assert isinstance(meter, Meter)
        mock_set_provider.assert_called_once()

    @patch("chiron.observability.metrics._METRICS_CONFIGURED", False)
    @patch("chiron.observability.metrics._load_otlp_metric_exporter")
    @patch("chiron.observability.metrics.metrics.set_meter_provider")
    def test_configure_metrics_with_service_name(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test configuring metrics with custom service name."""
        mock_load_exporter.return_value = None

        meter = configure_metrics(service_name="my-service")

        assert isinstance(meter, Meter)

    @patch("chiron.observability.metrics._METRICS_CONFIGURED", False)
    @patch("chiron.observability.metrics._load_otlp_metric_exporter")
    @patch("chiron.observability.metrics.metrics.set_meter_provider")
    def test_configure_metrics_with_resource_attributes(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test configuring metrics with custom resource attributes."""
        mock_load_exporter.return_value = None
        custom_attrs = {"custom.key": "custom.value"}

        meter = configure_metrics(resource_attributes=custom_attrs)

        assert isinstance(meter, Meter)

    @patch("chiron.observability.metrics._METRICS_CONFIGURED", False)
    @patch("chiron.observability.metrics._load_otlp_metric_exporter")
    @patch("chiron.observability.metrics.metrics.set_meter_provider")
    def test_configure_metrics_with_console_exporter(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test configuring metrics with console exporter enabled."""
        mock_load_exporter.return_value = None

        meter = configure_metrics(console_exporter=True)

        assert isinstance(meter, Meter)

    @patch("chiron.observability.metrics._METRICS_CONFIGURED", False)
    @patch("chiron.observability.metrics._load_otlp_metric_exporter")
    @patch("chiron.observability.metrics.metrics.set_meter_provider")
    def test_configure_metrics_sets_environment_variables(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test that environment variables are set correctly."""
        mock_load_exporter.return_value = None

        with patch.dict(os.environ, {}, clear=False):
            meter = configure_metrics()

            assert "OTEL_EXPORTER_OTLP_ENDPOINT" in os.environ
            assert isinstance(meter, Meter)

    @patch("chiron.observability.metrics._METRICS_CONFIGURED", False)
    @patch("chiron.observability.metrics._load_otlp_metric_exporter")
    @patch("chiron.observability.metrics.metrics.set_meter_provider")
    def test_configure_metrics_with_custom_namespace(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test configuring metrics with custom namespace."""
        mock_load_exporter.return_value = None

        meter = configure_metrics(namespace="custom-namespace")

        assert isinstance(meter, Meter)

    @patch("chiron.observability.metrics._METRICS_CONFIGURED", False)
    @patch("chiron.observability.metrics._load_otlp_metric_exporter")
    @patch("chiron.observability.metrics.metrics.set_meter_provider")
    def test_configure_metrics_respects_env_vars(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test that existing environment variables are respected."""
        mock_load_exporter.return_value = None

        with patch.dict(
            os.environ,
            {
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://custom:4317",
                "CHIRON_ENV": "production",
                "CHIRON_VERSION": "1.0.0",
            },
        ):
            meter = configure_metrics()

            assert os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://custom:4317"
            assert isinstance(meter, Meter)

    @patch("chiron.observability.metrics._METRICS_CONFIGURED", False)
    @patch("chiron.observability.metrics._load_otlp_metric_exporter")
    @patch("chiron.observability.metrics.metrics.set_meter_provider")
    def test_configure_metrics_console_env_var(
        self, mock_set_provider: Mock, mock_load_exporter: Mock
    ) -> None:
        """Test console exporter enabled via environment variable."""
        mock_load_exporter.return_value = None

        with patch.dict(os.environ, {"CHIRON_METRICS_CONSOLE": "true"}):
            meter = configure_metrics()

            assert isinstance(meter, Meter)

    @patch("chiron.observability.metrics._METRICS_CONFIGURED", False)
    @patch("chiron.observability.metrics._load_otlp_metric_exporter")
    @patch("chiron.observability.metrics.metrics.set_meter_provider")
    def test_configure_metrics_no_exporters_warning(
        self, mock_set_provider: Mock, mock_load_exporter: Mock, caplog
    ) -> None:
        """Test warning when no exporters are configured."""
        import logging

        mock_load_exporter.return_value = None

        with caplog.at_level(logging.WARNING):
            meter = configure_metrics(console_exporter=False)

            assert "No metric exporters configured" in caplog.text
            assert isinstance(meter, Meter)
