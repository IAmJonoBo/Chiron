"""Core exceptions for Chiron."""

from collections.abc import Mapping
from typing import Any


class ChironError(Exception):
    """Base exception class for Chiron."""

    def __init__(self, message: str, details: Mapping[str, Any] | None = None) -> None:
        """Initialize ChironError.

        Args:
            message: Error message
            details: Optional additional error details
        """
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = dict(details or {})


class ChironValidationError(ChironError):
    """Raised when validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: object = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        """Initialize ChironValidationError.

        Args:
            message: Error message
            field: Field that failed validation
            value: Value that failed validation
            details: Optional additional error details
        """
        super().__init__(message, details)
        self.field = field
        self.value = value


class ChironConfigurationError(ChironError):
    """Raised when configuration is invalid."""


class ChironServiceError(ChironError):
    """Raised when service operations fail."""


class ChironSecurityError(ChironError):
    """Raised when security violations are detected."""
