"""OpenFeature integration for Chiron feature flags.

This module provides feature flag management using OpenFeature,
a vendor-agnostic feature flag SDK.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

__all__ = ["FeatureFlags", "get_feature_flags", "is_feature_enabled"]

try:
    from openfeature import api
    from openfeature.evaluation_context import EvaluationContext
    from openfeature.provider.in_memory_provider import InMemoryFlag, InMemoryProvider

    OPENFEATURE_AVAILABLE = True
except ImportError:
    OPENFEATURE_AVAILABLE = False
    if TYPE_CHECKING:
        from openfeature import api
        from openfeature.evaluation_context import EvaluationContext
        from openfeature.provider.in_memory_provider import (
            InMemoryFlag,
            InMemoryProvider,
        )


class FeatureFlags:
    """Feature flag manager using OpenFeature."""

    if OPENFEATURE_AVAILABLE:
        DEFAULT_FLAGS: dict[str, InMemoryFlag[bool]] = {
            "allow_public_publish": InMemoryFlag(
                default_variant="off",
                variants={"on": True, "off": False},
            ),
            "require_slsa_provenance": InMemoryFlag(
                default_variant="on",
                variants={"on": True, "off": False},
            ),
            "enable_oci_distribution": InMemoryFlag(
                default_variant="off",
                variants={"on": True, "off": False},
            ),
            "enable_tuf_metadata": InMemoryFlag(
                default_variant="off",
                variants={"on": True, "off": False},
            ),
            "enable_mcp_agent": InMemoryFlag(
                default_variant="off",
                variants={"on": True, "off": False},
            ),
            "dry_run_by_default": InMemoryFlag(
                default_variant="on",
                variants={"on": True, "off": False},
            ),
            "require_code_signatures": InMemoryFlag(
                default_variant="on",
                variants={"on": True, "off": False},
            ),
            "enable_vulnerability_blocking": InMemoryFlag(
                default_variant="on",
                variants={"on": True, "off": False},
            ),
        }
    else:  # pragma: no cover - fallback when OpenFeature missing
        DEFAULT_FLAGS = {}

    def __init__(self, flags: dict[str, Any] | None = None):
        """Initialize feature flags.

        Args:
            flags: Custom flag definitions (overrides defaults)
        """
        self._initialized: bool = False

        if not OPENFEATURE_AVAILABLE:
            return

        # Merge custom flags with defaults
        all_flags = self.DEFAULT_FLAGS.copy()
        if flags:
            all_flags.update(flags)

        # Remove None values (from missing imports)
        all_flags = {k: v for k, v in all_flags.items() if v is not None}

        # Set up in-memory provider with default flags
        provider = InMemoryProvider(all_flags)
        api.set_provider(provider)
        self._initialized = True

    @property
    def client(self) -> Any:
        """Get the OpenFeature client."""
        if not OPENFEATURE_AVAILABLE:
            raise ImportError(
                "OpenFeature not available. Install with: pip install openfeature-sdk"
            )
        return api.get_client()

    def get_boolean(
        self,
        flag_key: str,
        default: bool = False,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Get a boolean feature flag value.

        Args:
            flag_key: Name of the feature flag
            default: Default value if flag not found
            context: Evaluation context for the flag

        Returns:
            Boolean flag value
        """
        if not OPENFEATURE_AVAILABLE or not self._initialized:
            env_key = f"CHIRON_FEATURE_{flag_key.upper()}"
            value = os.getenv(env_key)
            if value is None:
                return default
            return value.lower() in {"true", "1", "yes", "on"}

        eval_context = EvaluationContext(**context) if context else None
        return bool(self.client.get_boolean_value(flag_key, default, eval_context))

    def get_string(
        self, flag_key: str, default: str = "", context: dict[str, Any] | None = None
    ) -> str:
        """Get a string feature flag value.

        Args:
            flag_key: Name of the feature flag
            default: Default value if flag not found
            context: Evaluation context for the flag

        Returns:
            String flag value
        """
        if not OPENFEATURE_AVAILABLE or not self._initialized:
            env_key = f"CHIRON_FEATURE_{flag_key.upper()}"
            return os.getenv(env_key, default)

        eval_context = EvaluationContext(**context) if context else None
        return str(self.client.get_string_value(flag_key, default, eval_context))

    def is_enabled(self, flag_key: str, context: dict[str, Any] | None = None) -> bool:
        """Check if a feature flag is enabled.

        Convenience method for get_boolean with default False.

        Args:
            flag_key: Name of the feature flag
            context: Evaluation context for the flag

        Returns:
            True if flag is enabled, False otherwise
        """
        return self.get_boolean(flag_key, False, context)


# Global feature flags instance
_feature_flags: FeatureFlags | None = None


def get_feature_flags() -> FeatureFlags:
    """Get the global feature flags instance.

    Returns:
        FeatureFlags instance
    """
    global _feature_flags
    if _feature_flags is None:
        _feature_flags = FeatureFlags()
    return _feature_flags


def is_feature_enabled(flag_key: str, context: dict[str, Any] | None = None) -> bool:
    """Check if a feature is enabled.

    Convenience function for the global feature flags instance.

    Args:
        flag_key: Name of the feature flag
        context: Evaluation context for the flag

    Returns:
        True if feature is enabled, False otherwise
    """
    return get_feature_flags().is_enabled(flag_key, context)
