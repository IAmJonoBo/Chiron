"""Core functionality for Chiron."""

import os
from typing import Any

import structlog

from chiron import __version__
from chiron.exceptions import ChironConfigurationError, ChironError


class ChironCore:
    """Core Chiron functionality with observability and security features."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        enable_telemetry: bool = True,
        security_mode: bool = True,
    ) -> None:
        """Initialize ChironCore.

        Args:
            config: Configuration dictionary
            enable_telemetry: Whether to enable OpenTelemetry instrumentation
            security_mode: Whether to enable security features
        """
        self.config = config or {}
        self.enable_telemetry = enable_telemetry
        self.security_mode = security_mode
        self.tracer: Any | None = None

        # Configure structured logging
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        self.logger = structlog.get_logger(__name__)

        if self.enable_telemetry:
            self._setup_telemetry()

        if self.security_mode:
            self._setup_security()

    def _resolve_opentelemetry(
        self,
    ) -> tuple[Any | None, ...]:  # pragma: no cover - import helper
        """Resolve OpenTelemetry modules at runtime."""
        try:
            from opentelemetry import trace as ot_trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter as exporter_cls,
            )
            from opentelemetry.sdk.trace import TracerProvider as provider_cls
            from opentelemetry.sdk.trace.export import (
                BatchSpanProcessor as processor_cls,
            )
        except ImportError:
            return (None, None, None, None)

        return (ot_trace, exporter_cls, provider_cls, processor_cls)

    def _setup_telemetry(self) -> None:
        """Set up OpenTelemetry instrumentation."""
        if os.getenv("CHIRON_DISABLE_TELEMETRY", "false").lower() in (
            "1",
            "true",
            "yes",
            "on",
        ):
            self.logger.info("Telemetry disabled via environment toggle")
            self.tracer = None
            return

        (
            ot_trace,
            exporter_cls,
            provider_cls,
            processor_cls,
        ) = self._resolve_opentelemetry()

        if not all((ot_trace, exporter_cls, provider_cls, processor_cls)):
            self.logger.warning(
                "OpenTelemetry not available, telemetry disabled",
                error="missing dependency",
            )
            self.tracer = None
            return

        assert ot_trace is not None
        assert exporter_cls is not None
        assert provider_cls is not None
        assert processor_cls is not None

        try:
            telemetry_config = self.config.get("telemetry", {})
            exporter_enabled = telemetry_config.get("exporter_enabled", True)

            endpoint = (
                telemetry_config.get("otlp_endpoint")
                or self.config.get("otlp_endpoint")
                or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            )

            placeholder_endpoints = {
                "http://localhost:4317",
                "http://127.0.0.1:4317",
                "grpc://localhost:4317",
                "grpc://127.0.0.1:4317",
            }

            assume_local_collector = telemetry_config.get(
                "assume_local_collector",
                os.getenv("CHIRON_ASSUME_LOCAL_COLLECTOR", "false").lower()
                in {"1", "true", "yes", "on"},
            )

            endpoint_is_placeholder = endpoint in placeholder_endpoints if endpoint else False

            if endpoint_is_placeholder and not assume_local_collector:
                self.logger.info(
                    "Skipping OTLP exporter due to placeholder endpoint",
                    endpoint=endpoint,
                )
                endpoint = None

            provider = provider_cls()
            ot_trace.set_tracer_provider(provider)
            tracer = ot_trace.get_tracer(__name__)

            if exporter_enabled and endpoint:
                otlp_exporter = exporter_cls(endpoint=endpoint)
                span_processor = processor_cls(otlp_exporter)
                provider.add_span_processor(span_processor)
                self.logger.info(
                    "OpenTelemetry instrumentation enabled", exporter="otlp"
                )
            else:
                self.logger.info(
                    "OpenTelemetry instrumentation enabled", exporter="disabled"
                )

            self.tracer = tracer
        except Exception as exc:  # pragma: no cover - defensive guard
            self.logger.warning(
                "Failed to initialize OpenTelemetry, telemetry disabled",
                error=str(exc),
            )
            self.tracer = None

    def _setup_security(self) -> None:
        """Set up security features."""
        self.logger.info("Security mode enabled")
        # Security setup would go here
        # - Input validation
        # - Authentication/authorization
        # - Audit logging
        # - Rate limiting

    def validate_config(self) -> bool:
        """Validate the configuration.

        Returns:
            True if configuration is valid

        Raises:
            ChironConfigurationError: If configuration is invalid
        """
        required_fields = ["service_name"]

        for field in required_fields:
            if field not in self.config:
                raise ChironConfigurationError(
                    f"Required configuration field '{field}' is missing"
                )

        return True

    def health_check(self) -> dict[str, Any]:
        """Perform a health check.

        Returns:
            Health check status and details
        """
        status = {
            "status": "healthy",
            "version": __version__,
            "telemetry_enabled": self.enable_telemetry,
            "security_mode": self.security_mode,
            "timestamp": structlog.processors.TimeStamper(fmt="iso")(
                logger=None, name="", event_dict={}
            )["timestamp"],
        }

        self.logger.info("Health check performed", **status)
        return status

    def process_data(self, data: Any) -> Any:
        """Process data with observability and security checks.

        Args:
            data: Input data to process

        Returns:
            Processed data

        Raises:
            ChironError: If processing fails
        """
        if self.tracer:
            with self.tracer.start_as_current_span("process_data") as span:
                span.set_attribute("data.type", type(data).__name__)
                return self._process_data_internal(data)
        else:
            return self._process_data_internal(data)

    def _process_data_internal(self, data: Any) -> Any:
        """Internal data processing logic."""
        try:
            # Security validation
            if self.security_mode:
                self._validate_input(data)

            # Process the data
            self.logger.info("Processing data", data_type=type(data).__name__)

            # For now, just return the data as-is
            # In a real implementation, this would contain the core business logic
            return {"processed": True, "original": data}

        except Exception as e:
            self.logger.error("Data processing failed", error=str(e))
            raise ChironError(f"Failed to process data: {e}") from e

    def _validate_input(self, data: Any) -> None:
        """Validate input data for security."""
        if data is None:
            raise ChironError("Input data cannot be None")

        # Additional security validations would go here
        # - Input sanitization
        # - Schema validation
        # - Size limits
        # - Content filtering
