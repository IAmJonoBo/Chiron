"""JSON Schema validation utilities for Chiron configurations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

try:
    from jsonschema import Draft202012Validator, ValidationError

    JSONSCHEMA_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    JSONSCHEMA_AVAILABLE = False
    Draft202012Validator = cast(Any, None)
    ValidationError = Exception


SCHEMAS_DIR = Path(__file__).parent / "schemas"
CONFIG_SCHEMA_PATH = SCHEMAS_DIR / "chiron-config.schema.json"


def load_schema(schema_name: str = "chiron-config") -> dict[str, Any]:
    """Load a JSON schema by name.

    Args:
        schema_name: Name of the schema file (without .schema.json extension)

    Returns:
        Loaded schema dictionary

    Raises:
        FileNotFoundError: If schema file doesn't exist
        json.JSONDecodeError: If schema is not valid JSON
    """
    schema_path = SCHEMAS_DIR / f"{schema_name}.schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")

    with open(schema_path) as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Schema {schema_name} must be a JSON object")

    return cast(dict[str, Any], data)


def validate_config(
    config: dict[str, Any], schema_name: str = "chiron-config"
) -> list[str]:
    """Validate a configuration against a JSON schema.

    Args:
        config: Configuration dictionary to validate
        schema_name: Name of the schema to validate against

    Returns:
        List of validation error messages (empty if valid)
    """
    if not JSONSCHEMA_AVAILABLE:
        return ["jsonschema package not available - skipping validation"]

    try:
        schema = load_schema(schema_name)
        validator = Draft202012Validator(schema)

        errors: list[str] = []
        for error in validator.iter_errors(config):
            path = ".".join(str(p) for p in error.path) if error.path else "root"
            errors.append(f"{path}: {error.message}")

        return errors
    except FileNotFoundError as e:
        return [f"Schema not found: {e}"]
    except json.JSONDecodeError as e:
        return [f"Invalid schema JSON: {e}"]
    except Exception as e:
        return [f"Validation error: {e}"]


def validate_config_file(
    config_path: Path, schema_name: str = "chiron-config"
) -> list[str]:
    """Validate a configuration file against a JSON schema.

    Args:
        config_path: Path to configuration file
        schema_name: Name of the schema to validate against

    Returns:
        List of validation error messages (empty if valid)
    """
    try:
        with open(config_path) as f:
            config = json.load(f)
        if not isinstance(config, dict):
            return [
                "Configuration file must contain a JSON object at the top level",
            ]
        return validate_config(cast(dict[str, Any], config), schema_name)
    except FileNotFoundError:
        return [f"Configuration file not found: {config_path}"]
    except json.JSONDecodeError as e:
        return [f"Invalid JSON in configuration file: {e}"]
    except Exception as e:
        return [f"Error reading configuration file: {e}"]


def get_schema_defaults(schema_name: str = "chiron-config") -> dict[str, Any]:
    """Extract default values from a schema.

    Args:
        schema_name: Name of the schema

    Returns:
        Dictionary of default values
    """
    try:
        schema = load_schema(schema_name)
        defaults: dict[str, Any] = {}

        if "properties" in schema:
            for prop, spec in schema["properties"].items():
                if "default" in spec:
                    defaults[prop] = spec["default"]
                elif spec.get("type") == "object" and "properties" in spec:
                    # Recursively get defaults for nested objects
                    nested_defaults: dict[str, Any] = {}
                    for nested_prop, nested_spec in spec["properties"].items():
                        if "default" in nested_spec:
                            nested_defaults[nested_prop] = nested_spec["default"]
                    if nested_defaults:
                        defaults[prop] = nested_defaults

        return defaults
    except Exception:
        return {}
