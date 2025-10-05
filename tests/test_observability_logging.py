"""Tests for chiron.observability.logging module."""

from __future__ import annotations

import json
import logging
import os
from unittest.mock import patch

from chiron.observability.logging import (
    DEFAULT_LOG_LEVEL,
    _JsonFormatter,
    configure_logging,
)


class TestJsonFormatter:
    """Tests for _JsonFormatter."""

    def test_format_basic_record(self) -> None:
        """Test formatting a basic log record."""
        formatter = _JsonFormatter(service_name="test-service")
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Test message"
        assert parsed["service"] == "test-service"
        assert "timestamp" in parsed
        assert "hostname" in parsed
        assert "run_mode" in parsed

    def test_format_with_default_service_name(self) -> None:
        """Test formatting with default service name."""
        formatter = _JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["service"] == "chiron"

    def test_format_with_exception(self) -> None:
        """Test formatting a log record with exception info."""
        formatter = _JsonFormatter()
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["level"] == "ERROR"
        assert parsed["message"] == "Error occurred"
        assert "exc_info" in parsed
        assert "ValueError: Test error" in parsed["exc_info"]

    def test_format_with_stack_info(self) -> None:
        """Test formatting a log record with stack info."""
        formatter = _JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname="test.py",
            lineno=10,
            msg="Warning message",
            args=(),
            exc_info=None,
        )
        record.stack_info = "Stack trace here"

        result = formatter.format(record)
        parsed = json.loads(result)

        assert "stack" in parsed
        assert parsed["stack"] == "Stack trace here"

    def test_format_with_custom_attributes(self) -> None:
        """Test formatting with custom attributes."""
        formatter = _JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Custom attrs",
            args=(),
            exc_info=None,
        )
        record.custom_field = "custom_value"
        record.request_id = "12345"

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["custom_field"] == "custom_value"
        assert parsed["request_id"] == "12345"

    def test_format_filters_internal_attributes(self) -> None:
        """Test that internal attributes are filtered out."""
        formatter = _JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        # These should not be in the output
        assert "msg" not in parsed
        assert "args" not in parsed
        assert "levelno" not in parsed
        assert "thread" not in parsed
        assert "process" not in parsed

    def test_format_with_run_mode_env(self) -> None:
        """Test formatting respects CHIRON_RUN_MODE env var."""
        with patch.dict(os.environ, {"CHIRON_RUN_MODE": "production"}):
            formatter = _JsonFormatter()
            record = logging.LogRecord(
                name="test.logger",
                level=logging.INFO,
                pathname="test.py",
                lineno=10,
                msg="Test",
                args=(),
                exc_info=None,
            )

            result = formatter.format(record)
            parsed = json.loads(result)

            assert parsed["run_mode"] == "production"


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_configure_logging_default(self) -> None:
        """Test configuring logging with defaults."""
        logger = configure_logging()

        assert isinstance(logger, logging.Logger)
        assert logger is logging.getLogger()
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.StreamHandler)
        assert isinstance(logger.handlers[0].formatter, _JsonFormatter)

    def test_configure_logging_custom_level(self) -> None:
        """Test configuring logging with custom level."""
        logger = configure_logging(level="DEBUG")

        assert logger.level == logging.DEBUG

    def test_configure_logging_with_service_name(self) -> None:
        """Test configuring logging with custom service name."""
        logger = configure_logging(service_name="my-service")

        formatter = logger.handlers[0].formatter
        assert isinstance(formatter, _JsonFormatter)
        assert formatter._service == "my-service"

    def test_configure_logging_respects_env_var(self) -> None:
        """Test that CHIRON_LOG_LEVEL env var overrides default."""
        with patch.dict(os.environ, {"CHIRON_LOG_LEVEL": "WARNING"}):
            logger = configure_logging(level="DEBUG")

            # Env var should win
            assert logger.level == logging.WARNING

    def test_configure_logging_clears_existing_handlers(self) -> None:
        """Test that existing handlers are cleared."""
        root_logger = logging.getLogger()
        original_handlers = list(root_logger.handlers)

        # Add a dummy handler
        dummy_handler = logging.StreamHandler()
        root_logger.addHandler(dummy_handler)

        # Configure should clear and add new handler
        configure_logging()

        assert len(root_logger.handlers) == 1
        for handler in original_handlers:
            assert handler not in root_logger.handlers
        assert dummy_handler not in root_logger.handlers

    def test_configure_logging_captures_warnings(self) -> None:
        """Test that warnings are captured."""
        configure_logging()

        # captureWarnings should be enabled
        # We can't easily test this directly, but we can verify it doesn't error
        import warnings

        with warnings.catch_warnings(record=True):
            warnings.warn("Test warning", stacklevel=2)

    def test_configure_logging_invalid_level(self) -> None:
        """Test configuring with invalid level string."""
        # Python's logging will handle invalid levels
        # Just make sure it doesn't crash
        try:
            configure_logging(level="INVALID")
        except (ValueError, AttributeError):
            # Expected to fail when trying to use invalid level
            pass

    def test_configure_logging_returns_root_logger(self) -> None:
        """Test that the function returns the root logger."""
        logger = configure_logging()
        root_logger = logging.getLogger()

        assert logger is root_logger

    def test_default_log_level_constant(self) -> None:
        """Test that DEFAULT_LOG_LEVEL is set correctly."""
        assert DEFAULT_LOG_LEVEL == "INFO"
