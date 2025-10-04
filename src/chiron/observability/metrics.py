"""OpenTelemetry metrics helpers for Chiron."""

from __future__ import annotations

import importlib
import logging
import os
from collections.abc import Mapping

from opentelemetry import metrics
from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    MetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource

LOGGER = logging.getLogger(__name__)

_METRICS_CONFIGURED = False


def _load_otlp_metric_exporter() -> type[MetricExporter] | None:
    """Return the OTLP metric exporter class when available."""

    try:
        module = importlib.import_module(
            "opentelemetry.exporter.otlp.proto.grpc.metric_exporter"
        )
    except ModuleNotFoundError:  # pragma: no cover - optional dependency
        return None

    exporter = getattr(module, "OTLPMetricExporter", None)
    if exporter is None:
        LOGGER.warning("OTLPMetricExporter not found in exporter module.")
        return None
    if not isinstance(exporter, type):
        LOGGER.warning("OTLPMetricExporter is not a class; ignoring exporter.")
        return None
    if not issubclass(exporter, MetricExporter):
        LOGGER.warning("OTLPMetricExporter is not a MetricExporter subclass.")
        return None

    return exporter


def _create_metric_readers(
    exporter_cls: type[MetricExporter] | None,
    *,
    enable_console: bool,
) -> list[PeriodicExportingMetricReader]:
    readers: list[PeriodicExportingMetricReader] = []

    if exporter_cls is not None:
        readers.append(PeriodicExportingMetricReader(exporter_cls()))

    if enable_console:
        readers.append(PeriodicExportingMetricReader(ConsoleMetricExporter()))

    return readers


def configure_metrics(
    namespace: str = "chiron",
    *,
    service_name: str | None = None,
    resource_attributes: Mapping[str, str] | None = None,
    console_exporter: bool | None = None,
) -> Meter:
    """Configure OTEL metrics and return a meter for the requested namespace."""

    global _METRICS_CONFIGURED
    if not _METRICS_CONFIGURED:
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        if endpoint.startswith("http://"):
            os.environ.setdefault("OTEL_METRIC_EXPORT_INTERVAL", "60000")
            os.environ.setdefault("OTEL_EXPORTER_OTLP_INSECURE", "true")
        os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", endpoint)

        attributes: dict[str, str] = {
            "service.name": service_name or namespace,
            "service.namespace": "chiron",
            "service.instance.id": os.getenv("HOSTNAME", "local"),
            "service.version": os.getenv("CHIRON_VERSION", "0.1.0"),
            "deployment.environment": os.getenv("CHIRON_ENV", "development"),
        }
        if resource_attributes:
            attributes.update(resource_attributes)

        exporter_cls = _load_otlp_metric_exporter()
        enable_console = (
            console_exporter
            if console_exporter is not None
            else os.getenv("CHIRON_METRICS_CONSOLE", "false").lower()
            in {"1", "true", "yes"}
        )
        readers = _create_metric_readers(exporter_cls, enable_console=enable_console)

        if not readers:
            LOGGER.warning(
                "No metric exporters configured; metrics will be collected but not exported."
            )

        provider = MeterProvider(
            metric_readers=readers,
            resource=Resource.create(attributes),
        )
        metrics.set_meter_provider(provider)
        _METRICS_CONFIGURED = True

    return metrics.get_meter(namespace)
