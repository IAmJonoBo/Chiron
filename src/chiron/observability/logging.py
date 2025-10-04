"""Structured logging helpers aligned with Chiron's observability stack."""

from __future__ import annotations

import json
import logging
import os
import socket
from datetime import UTC, datetime
from typing import Any

DEFAULT_LOG_LEVEL = "INFO"


class _JsonFormatter(logging.Formatter):
    """Emit JSON log records without requiring external dependencies."""

    def __init__(self, service_name: str | None = None) -> None:
        super().__init__()
        self._service = service_name or "chiron"

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - stdlib signature
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self._service,
            "hostname": socket.gethostname(),
            "run_mode": os.getenv("CHIRON_RUN_MODE", "unknown"),
        }

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = record.stack_info

        for key, value in record.__dict__.items():
            if key.startswith("_") or key in payload:
                continue
            if key in {
                "msg",
                "args",
                "levelname",
                "levelno",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "process",
                "processName",
                "exc_info",
                "stack_info",
            }:
                continue
            payload[key] = value

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(
    level: str = DEFAULT_LOG_LEVEL, *, service_name: str | None = None
) -> logging.Logger:
    """Configure root logging to emit JSON records.

    Parameters
    ----------
    level:
        Default log level when no environment override is supplied.
    service_name:
        Optional service identifier injected into log records.

    Returns
    -------
    logging.Logger
        Configured root logger instance.
    """

    resolved_level = os.getenv("CHIRON_LOG_LEVEL", level).upper()
    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)
    root_logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter(service_name=service_name))
    root_logger.addHandler(handler)

    logging.captureWarnings(True)
    return root_logger
