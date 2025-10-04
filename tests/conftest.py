"""Test configuration and fixtures."""

import pytest
from unittest.mock import Mock

from chiron.core import ChironCore


@pytest.fixture
def basic_config():
    """Basic configuration for testing."""
    return {
        "service_name": "test-service",
        "telemetry": {"enabled": False},
        "security": {"enabled": True},
    }


@pytest.fixture
def core_instance(basic_config):
    """ChironCore instance for testing."""
    return ChironCore(config=basic_config, enable_telemetry=False)


@pytest.fixture
def mock_tracer():
    """Mock OpenTelemetry tracer."""
    tracer = Mock()
    span = Mock()
    span.__enter__ = Mock(return_value=span)
    span.__exit__ = Mock(return_value=None)
    tracer.start_as_current_span.return_value = span
    return tracer


@pytest.fixture
def sample_data():
    """Sample data for testing."""
    return {
        "key": "value",
        "number": 42,
        "nested": {"inner": "data"},
    }