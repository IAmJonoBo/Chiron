"""Tests for chiron.deps.preflight_summary module - preflight result rendering."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from chiron.deps.preflight_summary import (
    _coerce_list,
    _determine_exit_code,
    _emit_summary,
    _format_entry,
    _load_payload,
    _parse_args,
    _render_summary,
    main,
)


class TestParseArgs:
    """Tests for _parse_args function."""

    def test_parse_args_defaults(self) -> None:
        """Test parsing args with defaults."""
        args = _parse_args([])
        assert args.payload == "-"
        assert args.quiet is False
        assert args.fail_on_warn is False

    def test_parse_args_with_payload(self) -> None:
        """Test parsing args with payload path."""
        args = _parse_args(["results.json"])
        assert args.payload == "results.json"

    def test_parse_args_with_quiet(self) -> None:
        """Test parsing args with quiet flag."""
        args = _parse_args(["--quiet"])
        assert args.quiet is True

    def test_parse_args_with_fail_on_warn(self) -> None:
        """Test parsing args with fail-on-warn flag."""
        args = _parse_args(["--fail-on-warn"])
        assert args.fail_on_warn is True

    def test_parse_args_all_options(self) -> None:
        """Test parsing args with all options."""
        args = _parse_args(["preflight.json", "--quiet", "--fail-on-warn"])
        assert args.payload == "preflight.json"
        assert args.quiet is True
        assert args.fail_on_warn is True


class TestLoadPayload:
    """Tests for _load_payload function."""

    def test_load_payload_from_file(self, tmp_path: Path) -> None:
        """Test loading payload from file."""
        payload_file = tmp_path / "preflight.json"
        payload_data = [
            {"name": "pkg1", "status": "ok"},
            {"name": "pkg2", "status": "warn"},
        ]
        payload_file.write_text(json.dumps(payload_data))

        result = _load_payload(str(payload_file))

        assert len(result) == 2
        assert result[0]["name"] == "pkg1"
        assert result[1]["name"] == "pkg2"

    def test_load_payload_file_not_found(self, tmp_path: Path) -> None:
        """Test loading payload from non-existent file."""
        with pytest.raises(SystemExit) as exc_info:
            _load_payload(str(tmp_path / "missing.json"))

        assert "not found" in str(exc_info.value).lower()

    def test_load_payload_invalid_json(self, tmp_path: Path) -> None:
        """Test loading payload with invalid JSON."""
        payload_file = tmp_path / "invalid.json"
        payload_file.write_text("invalid json {")

        with pytest.raises(SystemExit) as exc_info:
            _load_payload(str(payload_file))

        assert "parse" in str(exc_info.value).lower()

    @patch("sys.stdin")
    def test_load_payload_from_stdin(self, mock_stdin: Mock) -> None:
        """Test loading payload from stdin."""
        payload_data = [{"name": "pkg1", "status": "ok"}]
        mock_stdin.read.return_value = json.dumps(payload_data)

        # Mock json.load to return our data
        with patch("json.load", return_value=payload_data):
            result = _load_payload("-")

        assert len(result) == 1
        assert result[0]["name"] == "pkg1"


class TestCoerceList:
    """Tests for _coerce_list function."""

    def test_coerce_list_valid(self) -> None:
        """Test coercing valid list."""
        data = [{"name": "pkg1"}, {"name": "pkg2"}]
        result = _coerce_list(data)
        assert result == data

    def test_coerce_list_filters_non_dicts(self) -> None:
        """Test that non-dict entries are filtered out."""
        data = [{"name": "pkg1"}, "not a dict", {"name": "pkg2"}, None]
        result = _coerce_list(data)
        assert len(result) == 2
        assert result[0]["name"] == "pkg1"
        assert result[1]["name"] == "pkg2"

    def test_coerce_list_not_a_list(self) -> None:
        """Test coercing non-list data."""
        with pytest.raises(SystemExit) as exc_info:
            _coerce_list({"not": "a list"})

        assert "must be a JSON list" in str(exc_info.value)


class TestRenderSummary:
    """Tests for _render_summary function."""

    def test_render_summary_no_issues(self) -> None:
        """Test rendering summary with no errors or warnings."""
        payload = [
            {"name": "pkg1", "status": "ok"},
            {"name": "pkg2", "status": "ok"},
        ]

        errors, warnings = _render_summary(payload)

        assert errors == []
        assert warnings == []

    def test_render_summary_with_errors(self) -> None:
        """Test rendering summary with errors."""
        payload = [
            {"name": "pkg2", "status": "error"},
            {"name": "pkg1", "status": "error"},
            {"name": "pkg3", "status": "ok"},
        ]

        errors, warnings = _render_summary(payload)

        assert len(errors) == 2
        assert errors[0]["name"] == "pkg1"  # Sorted alphabetically
        assert errors[1]["name"] == "pkg2"
        assert warnings == []

    def test_render_summary_with_warnings(self) -> None:
        """Test rendering summary with warnings."""
        payload = [
            {"name": "pkg2", "status": "warn"},
            {"name": "pkg1", "status": "warn"},
        ]

        errors, warnings = _render_summary(payload)

        assert errors == []
        assert len(warnings) == 2
        assert warnings[0]["name"] == "pkg1"  # Sorted alphabetically
        assert warnings[1]["name"] == "pkg2"

    def test_render_summary_mixed(self) -> None:
        """Test rendering summary with mixed statuses."""
        payload = [
            {"name": "pkg3", "status": "error"},
            {"name": "pkg1", "status": "warn"},
            {"name": "pkg2", "status": "ok"},
            {"name": "pkg4", "status": "error"},
        ]

        errors, warnings = _render_summary(payload)

        assert len(errors) == 2
        assert len(warnings) == 1
        assert errors[0]["name"] == "pkg3"
        assert warnings[0]["name"] == "pkg1"


class TestFormatEntry:
    """Tests for _format_entry function."""

    def test_format_entry_complete(self) -> None:
        """Test formatting complete entry."""
        entry = {
            "name": "example-pkg",
            "version": "1.2.3",
            "status": "error",
            "message": "Missing wheels",
            "missing": [
                {"python": "3.12", "platform": "linux"},
                {"python": "3.13", "platform": "macos"},
            ],
        }

        result = _format_entry(entry)

        assert "example-pkg" in result
        assert "1.2.3" in result
        assert "error" in result
        assert "Missing wheels" in result
        assert "py3.12@linux" in result
        assert "py3.13@macos" in result

    def test_format_entry_minimal(self) -> None:
        """Test formatting minimal entry."""
        entry = {}

        result = _format_entry(entry)

        assert "<unknown>" in result
        assert "no details" in result

    def test_format_entry_no_missing_targets(self) -> None:
        """Test formatting entry with no missing targets."""
        entry = {
            "name": "pkg",
            "version": "1.0.0",
            "status": "ok",
            "message": "All good",
        }

        result = _format_entry(entry)

        assert "targets: -" in result


class TestEmitSummary:
    """Tests for _emit_summary function."""

    @patch("builtins.print")
    def test_emit_summary_quiet_mode(self, mock_print: Mock) -> None:
        """Test emit_summary in quiet mode."""
        errors = [{"name": "pkg1", "status": "error"}]
        warnings = [{"name": "pkg2", "status": "warn"}]

        _emit_summary(errors, warnings, quiet=True)

        mock_print.assert_not_called()

    @patch("builtins.print")
    def test_emit_summary_no_issues(self, mock_print: Mock) -> None:
        """Test emit_summary with no issues."""
        _emit_summary([], [], quiet=False)

        assert mock_print.call_count >= 1
        # Should print success message
        calls_text = " ".join(str(call) for call in mock_print.call_args_list)
        assert "all dependencies satisfied" in calls_text.lower()

    @patch("builtins.print")
    def test_emit_summary_with_errors(self, mock_print: Mock) -> None:
        """Test emit_summary with errors."""
        errors = [{"name": "pkg1", "version": "1.0.0", "status": "error"}]

        _emit_summary(errors, [], quiet=False)

        assert mock_print.call_count >= 2


class TestDetermineExitCode:
    """Tests for _determine_exit_code function."""

    def test_determine_exit_code_no_issues(self) -> None:
        """Test exit code with no issues."""
        code = _determine_exit_code([], [], fail_on_warn=False)
        assert code == 0

    def test_determine_exit_code_with_errors(self) -> None:
        """Test exit code with errors."""
        errors = [{"name": "pkg1"}]
        code = _determine_exit_code(errors, [], fail_on_warn=False)
        assert code == 1

    def test_determine_exit_code_warnings_not_failing(self) -> None:
        """Test exit code with warnings when not failing on warnings."""
        warnings = [{"name": "pkg1"}]
        code = _determine_exit_code([], warnings, fail_on_warn=False)
        assert code == 0

    def test_determine_exit_code_warnings_failing(self) -> None:
        """Test exit code with warnings when failing on warnings."""
        warnings = [{"name": "pkg1"}]
        code = _determine_exit_code([], warnings, fail_on_warn=True)
        assert code == 1

    def test_determine_exit_code_errors_override_warnings(self) -> None:
        """Test that errors take precedence over warnings."""
        errors = [{"name": "pkg1"}]
        warnings = [{"name": "pkg2"}]
        code = _determine_exit_code(errors, warnings, fail_on_warn=False)
        assert code == 1


class TestMain:
    """Tests for main function."""

    def test_main_empty_payload(self, tmp_path: Path) -> None:
        """Test main with empty payload."""
        payload_file = tmp_path / "empty.json"
        payload_file.write_text("[]")

        code = main([str(payload_file), "--quiet"])

        assert code == 0

    def test_main_with_errors(self, tmp_path: Path) -> None:
        """Test main with errors in payload."""
        payload_file = tmp_path / "errors.json"
        payload = [{"name": "pkg1", "status": "error"}]
        payload_file.write_text(json.dumps(payload))

        code = main([str(payload_file), "--quiet"])

        assert code == 1

    def test_main_with_warnings_no_fail(self, tmp_path: Path) -> None:
        """Test main with warnings but not failing on them."""
        payload_file = tmp_path / "warnings.json"
        payload = [{"name": "pkg1", "status": "warn"}]
        payload_file.write_text(json.dumps(payload))

        code = main([str(payload_file), "--quiet"])

        assert code == 0

    def test_main_with_warnings_fail_on_warn(self, tmp_path: Path) -> None:
        """Test main with warnings and failing on them."""
        payload_file = tmp_path / "warnings.json"
        payload = [{"name": "pkg1", "status": "warn"}]
        payload_file.write_text(json.dumps(payload))

        code = main([str(payload_file), "--quiet", "--fail-on-warn"])

        assert code == 1

    def test_main_success_case(self, tmp_path: Path) -> None:
        """Test main with all checks passing."""
        payload_file = tmp_path / "success.json"
        payload = [
            {"name": "pkg1", "status": "ok"},
            {"name": "pkg2", "status": "ok"},
        ]
        payload_file.write_text(json.dumps(payload))

        code = main([str(payload_file), "--quiet"])

        assert code == 0
