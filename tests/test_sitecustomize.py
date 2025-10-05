from __future__ import annotations

import importlib
import os
import sys
from unittest.mock import patch

_MODULE_NAME = "sitecustomize"


def _load_sitecustomize_env(env: dict[str, str]) -> dict[str, str]:
    """Reload ``sitecustomize`` with a temporary environment and capture it."""

    sys.modules.pop(_MODULE_NAME, None)

    # Set up the temporary environment
    original_env = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)

    # Ensure the project sitecustomize.py is loaded (not system one)
    import pathlib

    project_root = str(pathlib.Path(__file__).parent.parent)
    original_path = sys.path.copy()
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    try:
        # Re-import the module which will trigger _configure_pip_environment()
        importlib.import_module(_MODULE_NAME)
        # Capture the environment after module initialization
        snapshot = dict(os.environ)
    finally:
        # Clean up module
        sys.modules.pop(_MODULE_NAME, None)
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)
        # Restore original sys.path
        sys.path[:] = original_path

    return snapshot


def test_sitecustomize_disables_vendor_overrides_for_copilot() -> None:
    scenarios = [
        {
            "GITHUB_COPILOT_AGENT_ID": "abc123",
            "PIP_NO_INDEX": "1",
            "PIP_FIND_LINKS": "https://example",
        },
        {
            "GITHUB_ACTIONS": "true",
            "COPILOT_AGENT_ID": "xyz",
            "PIP_NO_INDEX": "1",
            "PIP_FIND_LINKS": "https://example",
        },
    ]

    for scenario in scenarios:
        environ = _load_sitecustomize_env(scenario)
        assert environ.get("CHIRON_DISABLE_VENDOR_WHEELHOUSE") == "1"
        assert "PIP_NO_INDEX" not in environ
        assert "PIP_FIND_LINKS" not in environ


def test_sitecustomize_configures_wheelhouse_for_offline_installs() -> None:
    import shutil
    import tempfile
    from pathlib import Path

    # Create a temporary vendor/wheelhouse directory
    project_root = Path(__file__).parent.parent
    vendor_dir = project_root / "vendor" / "wheelhouse"
    vendor_dir.mkdir(parents=True, exist_ok=True)

    try:
        environ = _load_sitecustomize_env({})
        find_links = environ.get("PIP_FIND_LINKS", "")
        assert "vendor/wheelhouse" in find_links or str(vendor_dir) in find_links
        assert environ.get("CHIRON_DISABLE_VENDOR_WHEELHOUSE") != "1"
    finally:
        # Clean up
        shutil.rmtree(project_root / "vendor", ignore_errors=True)


def test_sitecustomize_preserves_overrides_for_non_copilot_runs() -> None:
    import shutil
    from pathlib import Path

    # Create a temporary vendor/wheelhouse directory
    project_root = Path(__file__).parent.parent
    vendor_dir = project_root / "vendor" / "wheelhouse"
    vendor_dir.mkdir(parents=True, exist_ok=True)

    try:
        environ = _load_sitecustomize_env({"GITHUB_ACTIONS": "true"})
        find_links = environ.get("PIP_FIND_LINKS", "")
        assert "vendor/wheelhouse" in find_links or str(vendor_dir) in find_links
        assert environ.get("CHIRON_DISABLE_VENDOR_WHEELHOUSE") != "1"
    finally:
        # Clean up
        shutil.rmtree(project_root / "vendor", ignore_errors=True)


def test_sitecustomize_does_not_duplicate_existing_find_links() -> None:
    from pathlib import Path

    wheelhouse = str(Path(__file__).resolve().parent.parent / "vendor" / "wheelhouse")
    environ = _load_sitecustomize_env(
        {"PIP_FIND_LINKS": f"{wheelhouse} https://example"}
    )
    value = environ.get("PIP_FIND_LINKS", "")
    assert value.split().count(wheelhouse) == 1
