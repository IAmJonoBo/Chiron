"""OpenTelemetry tracing helpers for Chiron."""

from __future__ import annotations

import importlib
import logging
import os
from collections.abc import Mapping

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)

LOGGER = logging.getLogger(__name__)

_TRACING_CONFIGURED = False


def _load_otlp_exporter() -> type[SpanExporter] | None:
    """Return the OTLP span exporter if the optional dependency is installed."""

    try:
        module = importlib.import_module(
            "opentelemetry.exporter.otlp.proto.grpc.trace_exporter"
        )
    except ModuleNotFoundError:  # pragma: no cover - optional dependency
        return None

    exporter = getattr(module, "OTLPSpanExporter", None)
    if exporter is None:
        LOGGER.warning("OTLPSpanExporter not found in exporter module.")
        return None
    if not isinstance(exporter, type):
        LOGGER.warning("OTLPSpanExporter is not a class; ignoring exporter.")
        return None
    if not issubclass(exporter, SpanExporter):
        LOGGER.warning("OTLPSpanExporter is not a SpanExporter subclass.")
        return None

    return exporter


def configure_tracing(
    service_name: str,
    *,
    resource_attributes: Mapping[str, str] | None = None,
    console_exporter: bool | None = None,
) -> trace.TracerProvider:
    """Configure tracing with OTLP export (when available).

    Subsequent calls are idempotent and simply return the active tracer provider.
    """

    global _TRACING_CONFIGURED
    if _TRACING_CONFIGURED:
        return trace.get_tracer_provider()

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    if endpoint.startswith("http://"):
        os.environ.setdefault("OTEL_EXPORTER_OTLP_INSECURE", "true")
    os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", endpoint)

    attributes: dict[str, str] = {
        "service.name": service_name,
        "service.namespace": "chiron",
        "service.version": os.getenv("CHIRON_VERSION", "0.1.0"),
        "deployment.environment": os.getenv("CHIRON_ENV", "development"),
    }
    if resource_attributes:
        attributes.update(resource_attributes)

    provider = SdkTracerProvider(resource=Resource.create(attributes))

    exporter_cls = _load_otlp_exporter()
    if exporter_cls is None:
        LOGGER.warning(
            "OTLP span exporter unavailable; enable with `pip install opentelemetry-exporter-otlp`."
        )
    else:
        provider.add_span_processor(BatchSpanProcessor(exporter_cls()))

    enable_console = (
        console_exporter
        if console_exporter is not None
        else os.getenv("CHIRON_TRACE_CONSOLE", "false").lower() in {"1", "true", "yes"}
    )
    if enable_console:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _TRACING_CONFIGURED = True
    return provider
