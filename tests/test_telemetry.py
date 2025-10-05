"""Tests for chiron.telemetry module."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from chiron.telemetry import (
    ChironTelemetry,
    HAS_OTEL,
    OperationMetrics,
    get_telemetry,
    track_operation,
)


class TestOperationMetrics:
    """Tests for OperationMetrics dataclass."""

    def test_operation_metrics_creation(self) -> None:
        """Test creating an OperationMetrics instance."""
        started = datetime.now(UTC)
        metrics = OperationMetrics(
            operation="test_op", started_at=started, metadata={"key": "value"}
        )

        assert metrics.operation == "test_op"
        assert metrics.started_at == started
        assert metrics.completed_at is None
        assert metrics.duration_ms is None
        assert metrics.success is None
        assert metrics.error is None
        assert metrics.metadata == {"key": "value"}

    def test_mark_complete_success(self) -> None:
        """Test marking operation as successfully complete."""
        started = datetime.now(UTC)
        metrics = OperationMetrics(operation="test_op", started_at=started)

        metrics.mark_complete(success=True)

        assert metrics.success is True
        assert metrics.error is None
        assert metrics.completed_at is not None
        assert metrics.duration_ms is not None
        assert metrics.duration_ms >= 0

    def test_mark_complete_failure(self) -> None:
        """Test marking operation as failed."""
        started = datetime.now(UTC)
        metrics = OperationMetrics(operation="test_op", started_at=started)

        metrics.mark_complete(success=False, error="Test error")

        assert metrics.success is False
        assert metrics.error == "Test error"
        assert metrics.completed_at is not None
        assert metrics.duration_ms is not None

    def test_to_dict(self) -> None:
        """Test converting metrics to dictionary."""
        started = datetime.now(UTC)
        metrics = OperationMetrics(
            operation="test_op", started_at=started, metadata={"test": "data"}
        )
        metrics.mark_complete(success=True)

        result = metrics.to_dict()

        assert result["operation"] == "test_op"
        assert result["started_at"] == started.isoformat()
        assert result["completed_at"] is not None
        assert result["duration_ms"] is not None
        assert result["success"] is True
        assert result["error"] is None
        assert result["metadata"] == {"test": "data"}

    def test_to_dict_incomplete(self) -> None:
        """Test converting incomplete metrics to dictionary."""
        started = datetime.now(UTC)
        metrics = OperationMetrics(operation="test_op", started_at=started)

        result = metrics.to_dict()

        assert result["operation"] == "test_op"
        assert result["started_at"] == started.isoformat()
        assert result["completed_at"] is None
        assert result["duration_ms"] is None
        assert result["success"] is None


class TestChironTelemetry:
    """Tests for ChironTelemetry class."""

    def test_telemetry_initialization(self) -> None:
        """Test initializing telemetry collector."""
        telemetry = ChironTelemetry()

        assert telemetry._metrics == []
        assert telemetry._current_operations == {}

    def test_start_operation(self) -> None:
        """Test starting an operation."""
        telemetry = ChironTelemetry()

        metrics = telemetry.start_operation("test_op", key1="value1")

        assert metrics.operation == "test_op"
        assert metrics.metadata == {"key1": "value1"}
        assert "test_op" in telemetry._current_operations

    def test_complete_operation_success(self) -> None:
        """Test completing an operation successfully."""
        telemetry = ChironTelemetry()
        telemetry.start_operation("test_op")

        telemetry.complete_operation("test_op", success=True)

        assert "test_op" not in telemetry._current_operations
        assert len(telemetry._metrics) == 1
        assert telemetry._metrics[0].success is True

    def test_complete_operation_failure(self) -> None:
        """Test completing an operation with failure."""
        telemetry = ChironTelemetry()
        telemetry.start_operation("test_op")

        telemetry.complete_operation("test_op", success=False, error="Failed")

        assert len(telemetry._metrics) == 1
        assert telemetry._metrics[0].success is False
        assert telemetry._metrics[0].error == "Failed"

    def test_complete_operation_not_found(self, caplog) -> None:
        """Test completing an operation that wasn't started."""
        import logging

        telemetry = ChironTelemetry()

        with caplog.at_level(logging.WARNING):
            telemetry.complete_operation("nonexistent_op")

        assert "not found in tracking" in caplog.text

    def test_get_metrics(self) -> None:
        """Test getting all metrics."""
        telemetry = ChironTelemetry()
        telemetry.start_operation("op1")
        telemetry.complete_operation("op1", success=True)
        telemetry.start_operation("op2")
        telemetry.complete_operation("op2", success=False)

        metrics = telemetry.get_metrics()

        assert len(metrics) == 2
        # Should be a copy, not the original list
        assert metrics is not telemetry._metrics

    def test_clear_metrics(self) -> None:
        """Test clearing all metrics."""
        telemetry = ChironTelemetry()
        telemetry.start_operation("test_op")
        telemetry.complete_operation("test_op")

        assert len(telemetry._metrics) == 1

        telemetry.clear_metrics()

        assert len(telemetry._metrics) == 0

    def test_get_summary_empty(self) -> None:
        """Test getting summary with no metrics."""
        telemetry = ChironTelemetry()

        summary = telemetry.get_summary()

        assert summary["total"] == 0
        assert summary["success"] == 0
        assert summary["failure"] == 0
        assert summary["avg_duration_ms"] == 0

    def test_get_summary_with_metrics(self) -> None:
        """Test getting summary with metrics."""
        telemetry = ChironTelemetry()
        telemetry.start_operation("op1")
        telemetry.complete_operation("op1", success=True)
        telemetry.start_operation("op2")
        telemetry.complete_operation("op2", success=True)
        telemetry.start_operation("op3")
        telemetry.complete_operation("op3", success=False)

        summary = telemetry.get_summary()

        assert summary["total"] == 3
        assert summary["success"] == 2
        assert summary["failure"] == 1
        assert summary["avg_duration_ms"] > 0


class TestGetTelemetry:
    """Tests for get_telemetry function."""

    def test_get_telemetry_returns_singleton(self) -> None:
        """Test that get_telemetry returns the same instance."""
        tel1 = get_telemetry()
        tel2 = get_telemetry()

        assert tel1 is tel2


class TestTrackOperation:
    """Tests for track_operation context manager."""

    def test_track_operation_success(self) -> None:
        """Test tracking a successful operation."""
        telemetry = get_telemetry()
        telemetry.clear_metrics()

        with track_operation("test_op", metadata_key="value"):
            pass

        metrics = telemetry.get_metrics()
        assert len(metrics) >= 1
        # Find our operation
        our_metrics = [m for m in metrics if m.operation == "test_op"]
        assert len(our_metrics) >= 1
        assert our_metrics[-1].success is True

    def test_track_operation_failure(self) -> None:
        """Test tracking a failed operation."""
        telemetry = get_telemetry()
        telemetry.clear_metrics()

        with pytest.raises(ValueError):
            with track_operation("test_op"):
                raise ValueError("Test error")

        metrics = telemetry.get_metrics()
        our_metrics = [m for m in metrics if m.operation == "test_op"]
        assert len(our_metrics) >= 1
        assert our_metrics[-1].success is False
        assert "Test error" in our_metrics[-1].error

    def test_track_operation_with_metadata(self) -> None:
        """Test tracking operation with metadata."""
        telemetry = get_telemetry()
        telemetry.clear_metrics()

        with track_operation("test_op", key1="value1", key2="value2"):
            pass

        metrics = telemetry.get_metrics()
        our_metrics = [m for m in metrics if m.operation == "test_op"]
        assert len(our_metrics) >= 1
        assert our_metrics[-1].metadata["key1"] == "value1"
        assert our_metrics[-1].metadata["key2"] == "value2"

    def test_track_operation_yields_metrics(self) -> None:
        """Test that track_operation yields metrics object."""
        with track_operation("test_op") as metrics:
            assert isinstance(metrics, OperationMetrics)
            assert metrics.operation == "test_op"

    @pytest.mark.skipif(not HAS_OTEL, reason="OpenTelemetry not available")
    @patch("chiron.telemetry.trace.get_tracer")
    def test_track_operation_with_otel_success(
        self, mock_get_tracer: Mock
    ) -> None:
        """Test tracking operation with OpenTelemetry span."""
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        with track_operation("test_op", key="value"):
            pass

        mock_tracer.start_span.assert_called_once_with("test_op")
        mock_span.set_attribute.assert_called()
        mock_span.set_status.assert_called()
        mock_span.end.assert_called_once()

    @pytest.mark.skipif(not HAS_OTEL, reason="OpenTelemetry not available")
    @patch("chiron.telemetry.trace.get_tracer")
    def test_track_operation_with_otel_failure(
        self, mock_get_tracer: Mock
    ) -> None:
        """Test tracking failed operation with OpenTelemetry span."""
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        with pytest.raises(ValueError):
            with track_operation("test_op"):
                raise ValueError("Test error")

        mock_span.record_exception.assert_called()
        mock_span.end.assert_called_once()

    @patch("chiron.telemetry.HAS_OTEL", False)
    def test_track_operation_without_otel(self) -> None:
        """Test tracking operation when OpenTelemetry is not available."""
        telemetry = get_telemetry()
        telemetry.clear_metrics()

        with track_operation("test_op"):
            pass

        # Should still work without OpenTelemetry
        metrics = telemetry.get_metrics()
        our_metrics = [m for m in metrics if m.operation == "test_op"]
        assert len(our_metrics) >= 1
        assert our_metrics[-1].success is True
