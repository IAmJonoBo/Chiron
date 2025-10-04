"""Tests for Chiron package initialization."""

import chiron


def test_version() -> None:
    """Test that version is defined."""
    assert hasattr(chiron, "__version__")
    assert isinstance(chiron.__version__, str)
    assert chiron.__version__ == "0.1.0"
