#!/usr/bin/env python3
"""Sync dependencies between devcontainer and CI workflows.

This script ensures that the devcontainer configuration and GitHub Actions
workflows use consistent dependency installation commands.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
DEVCONTAINER_JSON = REPO_ROOT / ".devcontainer" / "devcontainer.json"
DEVCONTAINER_POST_CREATE = REPO_ROOT / ".devcontainer" / "post-create.sh"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
WHEELS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "wheels.yml"
AIRGAP_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "airgap.yml"


def extract_uv_sync_command(pyproject_toml_path: Path) -> str:
    """Extract the appropriate uv sync command from pyproject.toml.
    
    Returns:
        The uv sync command to use
    """
    # For this project, we use core deps by default
    return "uv sync"


def update_devcontainer_post_create(uv_sync_cmd: str) -> bool:
    """Update post-create.sh with the correct uv sync command.
    
    Args:
        uv_sync_cmd: The uv sync command to use
        
    Returns:
        True if changes were made
    """
    if not DEVCONTAINER_POST_CREATE.exists():
        logger.error(f"Post-create script not found: {DEVCONTAINER_POST_CREATE}")
        return False
    
    content = DEVCONTAINER_POST_CREATE.read_text()
    
    # Find and replace uv sync command
    pattern = r'uv sync[^\n]*'
    new_content = re.sub(pattern, uv_sync_cmd, content)
    
    if content != new_content:
        DEVCONTAINER_POST_CREATE.write_text(new_content)
        logger.info(f"Updated {DEVCONTAINER_POST_CREATE}")
        return True
    
    logger.info(f"No changes needed for {DEVCONTAINER_POST_CREATE}")
    return False


def update_workflow_file(workflow_path: Path, uv_sync_cmd: str) -> bool:
    """Update a GitHub Actions workflow with the correct uv sync command.
    
    Args:
        workflow_path: Path to the workflow file
        uv_sync_cmd: The uv sync command to use
        
    Returns:
        True if changes were made
    """
    if not workflow_path.exists():
        logger.warning(f"Workflow not found: {workflow_path}")
        return False
    
    content = workflow_path.read_text()
    
    # Find and replace uv sync commands in run sections
    # Handle both single-line and multi-line formats
    pattern = r'(run:\s*(?:\|)?\s*\n?\s*)uv sync[^\n]*'
    
    def replace_func(match):
        prefix = match.group(1)
        return f"{prefix}{uv_sync_cmd}"
    
    new_content = re.sub(pattern, replace_func, content)
    
    if content != new_content:
        workflow_path.write_text(new_content)
        logger.info(f"Updated {workflow_path}")
        return True
    
    logger.info(f"No changes needed for {workflow_path}")
    return False


def validate_consistency() -> bool:
    """Validate that all environments use consistent dependency commands.
    
    Returns:
        True if all are consistent
    """
    issues = []
    
    # Check post-create.sh
    if DEVCONTAINER_POST_CREATE.exists():
        content = DEVCONTAINER_POST_CREATE.read_text()
        if "uv sync" not in content:
            issues.append(f"{DEVCONTAINER_POST_CREATE}: No 'uv sync' command found")
    
    # Check CI workflows that should have uv sync
    # Note: airgap.yml uses 'uv pip download' for offline bundles, not 'uv sync'
    workflows_requiring_sync = [CI_WORKFLOW, WHEELS_WORKFLOW]
    for workflow in workflows_requiring_sync:
        if workflow.exists():
            content = workflow.read_text()
            if "uv sync" not in content and "uv" in content:
                # Check if it's using uv for something other than downloads
                if "uv pip download" not in content:
                    issues.append(f"{workflow}: Uses uv but no 'uv sync' command found")
    
    if issues:
        logger.error("Consistency issues found:")
        for issue in issues:
            logger.error(f"  - {issue}")
        return False
    
    logger.info("All environments use consistent dependency commands")
    return True


def main() -> int:
    """Main entry point."""
    logger.info("Syncing dependency commands between dev and CI environments...")
    
    # Extract the canonical uv sync command
    uv_sync_cmd = extract_uv_sync_command(REPO_ROOT / "pyproject.toml")
    logger.info(f"Using command: {uv_sync_cmd}")
    
    changes_made = False
    
    # Update devcontainer post-create
    if update_devcontainer_post_create(uv_sync_cmd):
        changes_made = True
    
    # Update CI workflows
    for workflow in [CI_WORKFLOW, WHEELS_WORKFLOW, AIRGAP_WORKFLOW]:
        if update_workflow_file(workflow, uv_sync_cmd):
            changes_made = True
    
    # Validate consistency
    if not validate_consistency():
        logger.error("Validation failed after updates")
        return 1
    
    if changes_made:
        logger.info("✓ Successfully synchronized dependency commands")
        logger.info("Please review changes and commit them")
    else:
        logger.info("✓ All environments already synchronized")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
