"""Tests for feature flag utilities."""

from __future__ import annotations

import chiron.features as features


def _reset_feature_singleton() -> None:
    """Reset cached feature flags instance for test isolation."""
    features._feature_flags = None  # type: ignore[attr-defined]


def test_get_feature_flags_returns_singleton():
    """`get_feature_flags` should return a cached singleton."""
    _reset_feature_singleton()
    flags_one = features.get_feature_flags()
    flags_two = features.get_feature_flags()
    assert flags_one is flags_two
    _reset_feature_singleton()


def test_feature_flag_env_fallback(monkeypatch):
    """Environment variables should control flags when OpenFeature is unavailable."""
    original_available = features.OPENFEATURE_AVAILABLE
    monkeypatch.setattr(features, "OPENFEATURE_AVAILABLE", False, raising=False)
    _reset_feature_singleton()

    monkeypatch.setenv("CHIRON_FEATURE_ENABLE_MCP_AGENT", "true")
    flags = features.get_feature_flags()
    assert flags.is_enabled("enable_mcp_agent") is True

    monkeypatch.setenv("CHIRON_FEATURE_ENABLE_MCP_AGENT", "false")
    assert flags.is_enabled("enable_mcp_agent") is False

    _reset_feature_singleton()
    monkeypatch.delenv("CHIRON_FEATURE_ENABLE_MCP_AGENT", raising=False)
    monkeypatch.setattr(
        features, "OPENFEATURE_AVAILABLE", original_available, raising=False
    )
