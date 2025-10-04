"""
Chiron - Frontier-grade, production-ready Python library and service.

A comprehensive library focused on security, observability, and operational excellence.
"""

__version__ = "0.1.0"
__author__ = "Jonathan Bowers"
__email__ = "jonathan@example.com"

from chiron.core import ChironCore
from chiron.exceptions import ChironError, ChironValidationError

__all__ = [
    "ChironCore",
    "ChironError",
    "ChironValidationError",
    "__version__",
]
