from __future__ import annotations

import importlib
import os
import sys
from unittest.mock import patch

_MODULE_NAME = "sitecustomize"


def _load_sitecustomize_env(env: dict[str, str]) -> dict[str, str]:
    """Reload ``sitecustomize`` with a temporary environment and capture it."""

    sys.modules.pop(_MODULE_NAME, None)
    try:
        with patch.dict(os.environ, env, clear=True):
            importlib.import_module(_MODULE_NAME)
            snapshot = dict(os.environ)
    finally:
        sys.modules.pop(_MODULE_NAME, None)

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
    environ = _load_sitecustomize_env({})
    find_links = environ.get("PIP_FIND_LINKS", "")
    assert "vendor/wheelhouse" in find_links
    assert environ.get("CHIRON_DISABLE_VENDOR_WHEELHOUSE") != "1"


def test_sitecustomize_preserves_overrides_for_non_copilot_runs() -> None:
    environ = _load_sitecustomize_env({"GITHUB_ACTIONS": "true"})
    find_links = environ.get("PIP_FIND_LINKS", "")
    assert "vendor/wheelhouse" in find_links
    assert environ.get("CHIRON_DISABLE_VENDOR_WHEELHOUSE") != "1"


def test_sitecustomize_does_not_duplicate_existing_find_links() -> None:
    from pathlib import Path

    wheelhouse = str(Path(__file__).resolve().parent.parent / "vendor" / "wheelhouse")
    environ = _load_sitecustomize_env(
        {"PIP_FIND_LINKS": f"{wheelhouse} https://example"}
    )
    value = environ.get("PIP_FIND_LINKS", "")
    assert value.split().count(wheelhouse) == 1
