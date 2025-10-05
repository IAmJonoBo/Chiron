"""Tests for chiron.schema_validator module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from chiron.schema_validator import (
    JSONSCHEMA_AVAILABLE,
    get_schema_defaults,
    load_schema,
    validate_config,
    validate_config_file,
)


class TestLoadSchema:
    """Tests for load_schema function."""

    def test_load_schema_not_found(self) -> None:
        """Test loading a non-existent schema."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_schema("nonexistent-schema")

        assert "Schema not found" in str(exc_info.value)

    @patch("chiron.schema_validator.SCHEMAS_DIR")
    @patch("builtins.open", new_callable=mock_open)
    def test_load_schema_success(
        self, mock_file: Mock, mock_schemas_dir: Mock
    ) -> None:
        """Test loading a schema successfully."""
        mock_schemas_dir.__truediv__.return_value.exists.return_value = True
        schema_data = {"type": "object", "properties": {}}
        mock_file.return_value.read.return_value = json.dumps(schema_data)

        # We need to mock json.load instead
        with patch("json.load", return_value=schema_data):
            result = load_schema("test-schema")

        assert result == schema_data


class TestValidateConfig:
    """Tests for validate_config function."""

    @pytest.mark.skipif(
        not JSONSCHEMA_AVAILABLE, reason="jsonschema not available"
    )
    def test_validate_config_valid(self) -> None:
        """Test validating a valid configuration."""
        config = {"project_name": "test"}

        # Since we need actual schema, let's mock load_schema
        with patch("chiron.schema_validator.load_schema") as mock_load:
            mock_load.return_value = {
                "type": "object",
                "properties": {"project_name": {"type": "string"}},
            }
            errors = validate_config(config)

        assert errors == []

    @pytest.mark.skipif(
        not JSONSCHEMA_AVAILABLE, reason="jsonschema not available"
    )
    def test_validate_config_invalid(self) -> None:
        """Test validating an invalid configuration."""
        config = {"project_name": 123}  # Should be string

        with patch("chiron.schema_validator.load_schema") as mock_load:
            mock_load.return_value = {
                "type": "object",
                "properties": {"project_name": {"type": "string"}},
            }
            errors = validate_config(config)

        assert len(errors) > 0
        assert "project_name" in errors[0]

    @pytest.mark.skipif(
        not JSONSCHEMA_AVAILABLE, reason="jsonschema not available"
    )
    def test_validate_config_schema_not_found(self) -> None:
        """Test validation when schema is not found."""
        with patch(
            "chiron.schema_validator.load_schema",
            side_effect=FileNotFoundError("Not found"),
        ):
            errors = validate_config({})

        assert len(errors) > 0
        assert "Schema not found" in errors[0]

    @pytest.mark.skipif(
        not JSONSCHEMA_AVAILABLE, reason="jsonschema not available"
    )
    def test_validate_config_invalid_schema_json(self) -> None:
        """Test validation with invalid schema JSON."""
        with patch(
            "chiron.schema_validator.load_schema",
            side_effect=json.JSONDecodeError("Bad JSON", "doc", 0),
        ):
            errors = validate_config({})

        assert len(errors) > 0
        assert "Invalid schema JSON" in errors[0]

    @pytest.mark.skipif(
        not JSONSCHEMA_AVAILABLE, reason="jsonschema not available"
    )
    def test_validate_config_with_nested_errors(self) -> None:
        """Test validation with nested property errors."""
        config = {"nested": {"field": "wrong_type"}}

        with patch("chiron.schema_validator.load_schema") as mock_load:
            mock_load.return_value = {
                "type": "object",
                "properties": {
                    "nested": {
                        "type": "object",
                        "properties": {"field": {"type": "integer"}},
                    }
                },
            }
            errors = validate_config(config)

        assert len(errors) > 0

    @patch("chiron.schema_validator.JSONSCHEMA_AVAILABLE", False)
    def test_validate_config_jsonschema_not_available(self) -> None:
        """Test validation when jsonschema is not available."""
        errors = validate_config({})

        assert len(errors) == 1
        assert "jsonschema package not available" in errors[0]


class TestValidateConfigFile:
    """Tests for validate_config_file function."""

    def test_validate_config_file_not_found(self, tmp_path: Path) -> None:
        """Test validating a non-existent file."""
        nonexistent = tmp_path / "nonexistent.json"
        errors = validate_config_file(nonexistent)

        assert len(errors) > 0
        assert "not found" in errors[0].lower()

    def test_validate_config_file_invalid_json(self, tmp_path: Path) -> None:
        """Test validating a file with invalid JSON."""
        config_file = tmp_path / "bad.json"
        config_file.write_text("{ invalid json }")

        errors = validate_config_file(config_file)

        assert len(errors) > 0
        assert "Invalid JSON" in errors[0]

    @pytest.mark.skipif(
        not JSONSCHEMA_AVAILABLE, reason="jsonschema not available"
    )
    def test_validate_config_file_valid(self, tmp_path: Path) -> None:
        """Test validating a valid config file."""
        config_file = tmp_path / "config.json"
        config_data = {"project_name": "test"}
        config_file.write_text(json.dumps(config_data))

        with patch("chiron.schema_validator.validate_config") as mock_validate:
            mock_validate.return_value = []
            errors = validate_config_file(config_file)

        assert errors == []
        mock_validate.assert_called_once()

    def test_validate_config_file_generic_error(self, tmp_path: Path) -> None:
        """Test handling of generic errors during file validation."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with patch(
            "builtins.open", side_effect=PermissionError("Permission denied")
        ):
            errors = validate_config_file(config_file)

        assert len(errors) > 0
        assert "Error reading configuration file" in errors[0]


class TestGetSchemaDefaults:
    """Tests for get_schema_defaults function."""

    def test_get_schema_defaults_with_defaults(self) -> None:
        """Test extracting defaults from schema."""
        with patch("chiron.schema_validator.load_schema") as mock_load:
            mock_load.return_value = {
                "type": "object",
                "properties": {
                    "field1": {"type": "string", "default": "value1"},
                    "field2": {"type": "integer", "default": 42},
                    "field3": {"type": "string"},  # No default
                },
            }
            defaults = get_schema_defaults()

        assert defaults == {"field1": "value1", "field2": 42}
        assert "field3" not in defaults

    def test_get_schema_defaults_with_nested_objects(self) -> None:
        """Test extracting defaults from nested schema."""
        with patch("chiron.schema_validator.load_schema") as mock_load:
            mock_load.return_value = {
                "type": "object",
                "properties": {
                    "nested": {
                        "type": "object",
                        "properties": {
                            "nested_field": {"type": "string", "default": "nested_val"}
                        },
                    }
                },
            }
            defaults = get_schema_defaults()

        assert "nested" in defaults
        assert defaults["nested"]["nested_field"] == "nested_val"

    def test_get_schema_defaults_no_defaults(self) -> None:
        """Test extracting defaults when none are defined."""
        with patch("chiron.schema_validator.load_schema") as mock_load:
            mock_load.return_value = {
                "type": "object",
                "properties": {"field1": {"type": "string"}},
            }
            defaults = get_schema_defaults()

        assert defaults == {}

    def test_get_schema_defaults_error_handling(self) -> None:
        """Test error handling in get_schema_defaults."""
        with patch(
            "chiron.schema_validator.load_schema",
            side_effect=Exception("Load error"),
        ):
            defaults = get_schema_defaults()

        assert defaults == {}

    def test_get_schema_defaults_no_properties(self) -> None:
        """Test extracting defaults from schema without properties."""
        with patch("chiron.schema_validator.load_schema") as mock_load:
            mock_load.return_value = {"type": "object"}
            defaults = get_schema_defaults()

        assert defaults == {}

    def test_get_schema_defaults_custom_schema(self) -> None:
        """Test extracting defaults from a custom schema."""
        with patch("chiron.schema_validator.load_schema") as mock_load:
            mock_load.return_value = {
                "type": "object",
                "properties": {"custom_field": {"type": "boolean", "default": True}},
            }
            defaults = get_schema_defaults("custom-schema")

        assert defaults == {"custom_field": True}
        mock_load.assert_called_once_with("custom-schema")
