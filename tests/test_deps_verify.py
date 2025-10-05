"""Tests for chiron.deps.verify module - dependency pipeline verification."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from chiron.deps.verify import (
    check_cli_commands,
    check_documentation,
    check_script_imports,
    check_workflow_integration,
)


class TestCheckScriptImports:
    """Tests for check_script_imports function."""

    @patch("chiron.deps.verify.REPO_ROOT", Path("/fake/repo"))
    def test_check_script_imports_all_missing(self) -> None:
        """Test check_script_imports when all scripts are missing."""
        with patch("pathlib.Path.exists", return_value=False):
            results = check_script_imports()

            # Should return results for all scripts
            assert len(results) > 0
            # All should be False since files don't exist
            assert all(not passed for passed in results.values())

    @patch("chiron.deps.verify.REPO_ROOT", Path("/fake/repo"))
    def test_check_script_imports_with_valid_scripts(self, tmp_path: Path) -> None:
        """Test check_script_imports with valid scripts."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        # Create a valid standalone script
        upgrade_guard = scripts_dir / "upgrade_guard.py"
        upgrade_guard.write_text('def main():\n    pass\n')

        # Create a valid library module
        deps_status = scripts_dir / "deps_status.py"
        deps_status.write_text('def generate_status():\n    pass\n')

        with patch("chiron.deps.verify.REPO_ROOT", tmp_path):
            results = check_script_imports()

            assert results["upgrade_guard.py (standalone)"] is True
            assert results["deps_status.py (library)"] is True

    @patch("chiron.deps.verify.REPO_ROOT", Path("/fake/repo"))
    def test_check_script_imports_invalid_content(self, tmp_path: Path) -> None:
        """Test check_script_imports with scripts missing required functions."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        # Create script without main() function
        upgrade_guard = scripts_dir / "upgrade_guard.py"
        upgrade_guard.write_text('def other_function():\n    pass\n')

        with patch("chiron.deps.verify.REPO_ROOT", tmp_path):
            results = check_script_imports()

            assert results["upgrade_guard.py (standalone)"] is False


class TestCheckCliCommands:
    """Tests for check_cli_commands function."""

    @patch("chiron.deps.verify.REPO_ROOT", Path("/fake/repo"))
    def test_check_cli_commands_no_cli_file(self) -> None:
        """Test check_cli_commands when cli.py doesn't exist."""
        with patch("pathlib.Path.exists", return_value=False):
            results = check_cli_commands()

            assert results == {"cli_module": False}

    @patch("chiron.deps.verify.REPO_ROOT")
    def test_check_cli_commands_with_valid_cli(
        self, mock_repo_root: Mock, tmp_path: Path
    ) -> None:
        """Test check_cli_commands with valid CLI file."""
        mock_repo_root.return_value = tmp_path

        chiron_dir = tmp_path / "chiron"
        chiron_dir.mkdir()
        cli_file = chiron_dir / "cli.py"

        # Create CLI file with command decorators
        cli_content = '''
@deps_app.command("status")
def status_command():
    pass

@deps_app.command("upgrade")
def upgrade_command():
    pass

@deps_app.command("guard")
def guard_command():
    pass
'''
        cli_file.write_text(cli_content)

        with patch("chiron.deps.verify.REPO_ROOT", tmp_path):
            results = check_cli_commands()

            assert results["deps status"] is True
            assert results["deps upgrade"] is True
            assert results["deps guard"] is True

    @patch("chiron.deps.verify.REPO_ROOT")
    def test_check_cli_commands_missing_commands(
        self, mock_repo_root: Mock, tmp_path: Path
    ) -> None:
        """Test check_cli_commands with CLI file missing some commands."""
        mock_repo_root.return_value = tmp_path

        chiron_dir = tmp_path / "chiron"
        chiron_dir.mkdir()
        cli_file = chiron_dir / "cli.py"

        # Create CLI file with only one command
        cli_content = '@deps_app.command("status")\ndef status():\n    pass\n'
        cli_file.write_text(cli_content)

        with patch("chiron.deps.verify.REPO_ROOT", tmp_path):
            results = check_cli_commands()

            assert results["deps status"] is True
            assert results["deps upgrade"] is False


class TestCheckWorkflowIntegration:
    """Tests for check_workflow_integration function."""

    @patch("chiron.deps.verify.REPO_ROOT")
    def test_check_workflow_integration_no_workflows(
        self, mock_repo_root: Mock, tmp_path: Path
    ) -> None:
        """Test check_workflow_integration when workflow files don't exist."""
        mock_repo_root.return_value = tmp_path

        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        with patch("chiron.deps.verify.REPO_ROOT", tmp_path):
            results = check_workflow_integration()

            # All checks should be False when files don't exist
            assert results["dependency-preflight uses CLI"] is False
            assert results["dependency-contract-check uses CLI"] is False
            assert results["offline-packaging uses CLI"] is False

    @patch("chiron.deps.verify.REPO_ROOT")
    def test_check_workflow_integration_with_valid_workflows(
        self, mock_repo_root: Mock, tmp_path: Path
    ) -> None:
        """Test check_workflow_integration with valid workflow files."""
        mock_repo_root.return_value = tmp_path

        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        # Create preflight workflow
        preflight = workflows_dir / "dependency-preflight.yml"
        preflight.write_text('''
steps:
  - run: chiron deps preflight
  - run: chiron deps guard
  - run: chiron deps snapshot ensure
''')

        # Create contract check workflow
        contract = workflows_dir / "dependency-contract-check.yml"
        contract.write_text('steps:\n  - run: chiron deps sync\n')

        # Create offline packaging workflow
        packaging = workflows_dir / "offline-packaging-optimized.yml"
        packaging.write_text('steps:\n  - run: chiron offline-package\n')

        with patch("chiron.deps.verify.REPO_ROOT", tmp_path):
            results = check_workflow_integration()

            assert results["dependency-preflight uses CLI"] is True
            assert results["dependency-contract-check uses CLI"] is True
            assert results["offline-packaging uses CLI"] is True

    @patch("chiron.deps.verify.REPO_ROOT")
    def test_check_workflow_integration_incomplete_workflows(
        self, mock_repo_root: Mock, tmp_path: Path
    ) -> None:
        """Test check_workflow_integration with incomplete workflow files."""
        mock_repo_root.return_value = tmp_path

        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        # Create preflight workflow missing some commands
        preflight = workflows_dir / "dependency-preflight.yml"
        preflight.write_text('steps:\n  - run: chiron deps preflight\n')

        with patch("chiron.deps.verify.REPO_ROOT", tmp_path):
            results = check_workflow_integration()

            # Should be False because it's missing guard and snapshot commands
            assert results["dependency-preflight uses CLI"] is False


class TestCheckDocumentation:
    """Tests for check_documentation function."""

    @patch("chiron.deps.verify.REPO_ROOT")
    def test_check_documentation_no_docs(
        self, mock_repo_root: Mock, tmp_path: Path
    ) -> None:
        """Test check_documentation when docs don't exist."""
        mock_repo_root.return_value = tmp_path

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        with patch("chiron.deps.verify.REPO_ROOT", tmp_path):
            results = check_documentation()

            assert results["dependency-governance.md exists"] is False
            assert results["packaging workflow linked"] is False

    @patch("chiron.deps.verify.REPO_ROOT")
    def test_check_documentation_with_valid_docs(
        self, mock_repo_root: Mock, tmp_path: Path
    ) -> None:
        """Test check_documentation with valid documentation."""
        mock_repo_root.return_value = tmp_path

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        governance_doc = docs_dir / "dependency-governance.md"
        governance_doc.write_text('''
# Dependency Governance

See [packaging-workflow-integration.md](packaging-workflow-integration.md)
for details.
''')

        with patch("chiron.deps.verify.REPO_ROOT", tmp_path):
            results = check_documentation()

            assert results["dependency-governance.md exists"] is True
            assert results["packaging workflow linked"] is True

    @patch("chiron.deps.verify.REPO_ROOT")
    def test_check_documentation_missing_link(
        self, mock_repo_root: Mock, tmp_path: Path
    ) -> None:
        """Test check_documentation with doc missing workflow link."""
        mock_repo_root.return_value = tmp_path

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        governance_doc = docs_dir / "dependency-governance.md"
        governance_doc.write_text('# Dependency Governance\n\nSome content.\n')

        with patch("chiron.deps.verify.REPO_ROOT", tmp_path):
            results = check_documentation()

            assert results["dependency-governance.md exists"] is True
            assert results["packaging workflow linked"] is False
