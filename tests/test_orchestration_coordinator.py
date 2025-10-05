"""Tests for chiron.orchestration.coordinator module - workflow coordination."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from chiron.orchestration.coordinator import (
    OrchestrationContext,
    OrchestrationCoordinator,
)


class TestOrchestrationContext:
    """Tests for OrchestrationContext dataclass."""

    def test_initialization_defaults(self) -> None:
        """Test OrchestrationContext initialization with defaults."""
        context = OrchestrationContext()
        assert context.mode == "hybrid"
        assert context.dry_run is False
        assert context.verbose is False
        assert context.dependencies_synced is False
        assert context.wheelhouse_built is False
        assert context.models_cached is False
        assert context.containers_ready is False
        assert context.validation_passed is False
        assert isinstance(context.metadata, dict)
        assert context.metadata == {}

    def test_initialization_with_custom_values(self) -> None:
        """Test OrchestrationContext initialization with custom values."""
        context = OrchestrationContext(
            mode="local",
            dry_run=True,
            verbose=True,
            dependencies_synced=True,
        )
        assert context.mode == "local"
        assert context.dry_run is True
        assert context.verbose is True
        assert context.dependencies_synced is True

    def test_to_dict_serialization(self) -> None:
        """Test OrchestrationContext to_dict serialization."""
        context = OrchestrationContext(
            mode="remote",
            dry_run=True,
            dependencies_synced=True,
            wheelhouse_built=True,
        )
        context.metadata["key"] = "value"

        result = context.to_dict()
        assert result["mode"] == "remote"
        assert result["dry_run"] is True
        assert result["dependencies_synced"] is True
        assert result["wheelhouse_built"] is True
        assert result["metadata"] == {"key": "value"}
        assert "timestamp" in result

    def test_timestamp_is_utc(self) -> None:
        """Test that timestamp is in UTC."""
        context = OrchestrationContext()
        assert context.timestamp.tzinfo == UTC


class TestOrchestrationCoordinator:
    """Tests for OrchestrationCoordinator class."""

    def test_initialization_default_context(self, tmp_path: Path) -> None:
        """Test coordinator initialization with default context."""
        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            coordinator = OrchestrationCoordinator()
            assert coordinator.context is not None
            assert coordinator.context.mode == "hybrid"
            assert coordinator._state_file == tmp_path / "orchestration-state.json"

    def test_initialization_custom_context(self, tmp_path: Path) -> None:
        """Test coordinator initialization with custom context."""
        context = OrchestrationContext(mode="local", dry_run=True)
        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            coordinator = OrchestrationCoordinator(context)
            assert coordinator.context.mode == "local"
            assert coordinator.context.dry_run is True

    def test_load_state_no_file(self, tmp_path: Path) -> None:
        """Test loading state when no state file exists."""
        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            coordinator = OrchestrationCoordinator()
            assert coordinator.context.metadata == {}

    def test_load_state_with_existing_file(self, tmp_path: Path) -> None:
        """Test loading state from existing file."""
        state_file = tmp_path / "orchestration-state.json"
        state_data = {
            "mode": "local",
            "metadata": {"key": "value", "count": 42},
        }
        state_file.write_text(json.dumps(state_data))

        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            coordinator = OrchestrationCoordinator()
            assert coordinator.context.metadata["key"] == "value"
            assert coordinator.context.metadata["count"] == 42

    def test_load_state_with_invalid_json(self, tmp_path: Path) -> None:
        """Test loading state with invalid JSON (should not crash)."""
        state_file = tmp_path / "orchestration-state.json"
        state_file.write_text("invalid json")

        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            coordinator = OrchestrationCoordinator()
            assert coordinator.context.metadata == {}

    def test_save_state(self, tmp_path: Path) -> None:
        """Test saving orchestration state."""
        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            context = OrchestrationContext(mode="local", dry_run=True)
            context.metadata["test"] = "data"
            coordinator = OrchestrationCoordinator(context)

            coordinator._save_state()

            state_file = tmp_path / "orchestration-state.json"
            assert state_file.exists()
            saved_data = json.loads(state_file.read_text())
            assert saved_data["mode"] == "local"
            assert saved_data["dry_run"] is True
            assert saved_data["metadata"]["test"] == "data"

    @patch("chiron.orchestration.coordinator.subprocess.run")
    def test_run_command_success(
        self, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test running a command successfully."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["test"], returncode=0, stdout=b"output", stderr=b""
        )

        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            coordinator = OrchestrationCoordinator()
            result = coordinator._run_command(
                ["test", "command"], "Test command"
            )

            assert result.returncode == 0
            assert result.stdout == b"output"
            mock_run.assert_called_once()

    @patch("chiron.orchestration.coordinator.subprocess.run")
    def test_run_command_dry_run(
        self, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test running a command in dry-run mode."""
        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            context = OrchestrationContext(dry_run=True)
            coordinator = OrchestrationCoordinator(context)
            result = coordinator._run_command(
                ["test", "command"], "Test command"
            )

            assert result.returncode == 0
            mock_run.assert_not_called()

    @patch("chiron.orchestration.coordinator.subprocess.run")
    def test_run_command_verbose(
        self, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test running a command in verbose mode."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["test"], returncode=0, stdout=b"", stderr=b""
        )

        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            context = OrchestrationContext(verbose=True)
            coordinator = OrchestrationCoordinator(context)
            coordinator._run_command(["test", "command"], "Test command")

            mock_run.assert_called_once()

    @patch("chiron.orchestration.coordinator.subprocess.run")
    def test_run_command_with_check_false(
        self, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test running a command with check=False."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["test"], returncode=1, stdout=b"", stderr=b"error"
        )

        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            coordinator = OrchestrationCoordinator()
            result = coordinator._run_command(
                ["test", "command"], "Test command", check=False
            )

            assert result.returncode == 1
            assert result.stderr == b"error"

    @patch("chiron.orchestration.coordinator.subprocess.run")
    def test_deps_preflight(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test dependency preflight operation."""
        preflight_data = {"status": "ok", "packages": []}
        mock_run.return_value = subprocess.CompletedProcess(
            args=["poetry", "run", "chiron", "deps", "preflight", "--json"],
            returncode=0,
            stdout=json.dumps(preflight_data).encode(),
            stderr=b"",
        )

        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            coordinator = OrchestrationCoordinator()
            result = coordinator.deps_preflight()

            assert result == preflight_data
            assert coordinator.context.metadata["preflight"] == preflight_data
            output_file = tmp_path / "dependency-preflight" / "latest.json"
            assert output_file.exists()

    @patch("chiron.orchestration.coordinator.subprocess.run")
    def test_deps_preflight_empty_output(
        self, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test dependency preflight with empty output."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["poetry", "run", "chiron", "deps", "preflight", "--json"],
            returncode=1,
            stdout=b"",
            stderr=b"error",
        )

        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            coordinator = OrchestrationCoordinator()
            result = coordinator.deps_preflight()

            assert result == {}
            assert coordinator.context.metadata["preflight"] == {}

    @patch("chiron.orchestration.coordinator.subprocess.run")
    def test_deps_guard(self, mock_run: Mock, tmp_path: Path) -> None:
        """Test upgrade guard operation."""
        # Create a mock preflight file
        preflight_dir = tmp_path / "dependency-preflight"
        preflight_dir.mkdir(parents=True)
        preflight_file = preflight_dir / "latest.json"
        preflight_file.write_text('{"status": "ok"}')

        # Create output directory and file
        output_dir = tmp_path / "upgrade-guard"
        output_dir.mkdir(parents=True)
        output_file = output_dir / "assessment.json"
        guard_data = {"risk": "safe", "packages": []}
        output_file.write_text(json.dumps(guard_data))

        mock_run.return_value = subprocess.CompletedProcess(
            args=["poetry", "run", "chiron", "deps", "guard"],
            returncode=0,
            stdout=b"",
            stderr=b"",
        )

        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            coordinator = OrchestrationCoordinator()
            result = coordinator.deps_guard()

            assert result == guard_data
            assert output_file.exists()

    @patch("chiron.orchestration.coordinator.subprocess.run")
    def test_deps_guard_with_custom_preflight_path(
        self, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test upgrade guard with custom preflight path."""
        custom_preflight = tmp_path / "custom-preflight.json"
        custom_preflight.write_text('{"status": "custom"}')

        # Create output directory and file
        output_dir = tmp_path / "upgrade-guard"
        output_dir.mkdir(parents=True)
        output_file = output_dir / "assessment.json"
        guard_data = {"risk": "needs-review"}
        output_file.write_text(json.dumps(guard_data))

        mock_run.return_value = subprocess.CompletedProcess(
            args=["poetry", "run", "chiron", "deps", "guard"],
            returncode=0,
            stdout=b"",
            stderr=b"",
        )

        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            coordinator = OrchestrationCoordinator()
            result = coordinator.deps_guard(preflight_path=custom_preflight)

            assert result == guard_data


class TestOrchestrationWorkflows:
    """Tests for orchestration workflow combinations."""

    @patch("chiron.orchestration.coordinator.subprocess.run")
    def test_full_dependency_workflow(
        self, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test running a full dependency management workflow."""

        def mock_subprocess(args, **kwargs):
            return subprocess.CompletedProcess(
                args=args, returncode=0, stdout=b"", stderr=b""
            )

        mock_run.side_effect = mock_subprocess

        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            # Create necessary output directories and files
            preflight_dir = tmp_path / "dependency-preflight"
            preflight_dir.mkdir(parents=True)
            preflight_file = preflight_dir / "latest.json"
            preflight_data = {"status": "ok"}
            preflight_file.write_text(json.dumps(preflight_data))

            guard_dir = tmp_path / "upgrade-guard"
            guard_dir.mkdir(parents=True)
            guard_file = guard_dir / "assessment.json"
            guard_data = {"risk": "safe"}
            guard_file.write_text(json.dumps(guard_data))

            coordinator = OrchestrationCoordinator()

            # Run preflight
            # Mock the output by writing to the file before calling
            result = coordinator.deps_preflight()
            # After preflight runs, it would have written the file
            # But since we're mocking, we update it
            preflight_file.write_text(json.dumps(preflight_data))
            
            # Run guard
            guard_result = coordinator.deps_guard()
            assert guard_result["risk"] == "safe"

    def test_state_persistence_across_operations(
        self, tmp_path: Path
    ) -> None:
        """Test that state persists across multiple operations."""
        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            # First coordinator instance
            context1 = OrchestrationContext(mode="local")
            coordinator1 = OrchestrationCoordinator(context1)
            coordinator1.context.metadata["test"] = "value1"
            coordinator1.context.dependencies_synced = True
            coordinator1._save_state()

            # Second coordinator instance
            coordinator2 = OrchestrationCoordinator()
            assert coordinator2.context.metadata["test"] == "value1"

    def test_dry_run_mode_workflow(self, tmp_path: Path) -> None:
        """Test workflow in dry-run mode."""
        with patch("chiron.orchestration.coordinator.VAR_ROOT", tmp_path):
            with patch("chiron.orchestration.coordinator.subprocess.run") as mock_run:
                context = OrchestrationContext(dry_run=True)
                coordinator = OrchestrationCoordinator(context)

                # Run operations in dry-run mode
                coordinator._run_command(["test", "command"], "Test")

                # Verify no subprocess calls were made
                mock_run.assert_not_called()
