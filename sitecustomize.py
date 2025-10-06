"""Project-level site customizations for pip bootstrapping.

This module is automatically imported by Python during interpreter start-up
when it can be found on ``sys.path``. Because ``pip`` executes as
``python -m pip`` and inserts the current working directory on ``sys.path``,
we can use this hook to influence pip's behaviour without requiring callers
to export additional environment variables.

The primary goal is to make ``pip install -e '.[dev,test]'`` succeed in
restricted or offline environments by default by pointing pip at the
pre-generated vendor wheelhouse that ships with the repository.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from pathlib import Path

from chiron.hardening import install_thinc_seed_guard

_VENDOR_WHEELHOUSE = Path(__file__).resolve().parent / "vendor" / "wheelhouse"
_MANIFEST_FILENAME = "manifest.json"
_REQUIRED_EXTRAS = {"dev", "test"}
_COPILOT_INDICATOR_KEYS: tuple[str, ...] = (
    "GITHUB_COPILOT_AGENT_ID",
    "GITHUB_COPILOT_WORKSPACE_ID",
    "GITHUB_COPILOT_CODING_AGENT",
    "GITHUB_COPILOT_RUN_ID",
    "COPILOT_AGENT_ID",
    "COPILOT_AGENT_VERSION",
    "COPILOT_WORKSPACE_ID",
)
_DISABLE_ENV_VAR = "CHIRON_DISABLE_VENDOR_WHEELHOUSE"


def _iter_existing_values(value: str | None) -> Iterable[str]:
    if not value:
        return
    # pip interprets both spaces and newlines as separators in find-links values
    for part in value.replace("\n", " ").split():
        cleaned = part.strip()
        if cleaned:
            yield cleaned


def _should_force_offline(manifest_path: Path) -> bool:
    if not manifest_path.is_file():
        return False

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False

    extras = {str(item) for item in payload.get("extras", []) if item}
    include_dev = bool(payload.get("include_dev"))

    if "all" in extras:
        return True

    return include_dev and _REQUIRED_EXTRAS.issubset(extras)


def _is_copilot_agent_environment() -> bool:
    for key in _COPILOT_INDICATOR_KEYS:
        if os.environ.get(key):
            return True

    if os.environ.get("GITHUB_ACTIONS") == "true":
        return any(
            key.startswith("COPILOT_") and os.environ.get(key) for key in os.environ
        )

    return False


def _configure_pip_environment() -> None:
    env = os.environ

    if _is_copilot_agent_environment():
        env[_DISABLE_ENV_VAR] = "1"
        env.pop("PIP_NO_INDEX", None)
        env.pop("PIP_FIND_LINKS", None)

    if env.get(_DISABLE_ENV_VAR):
        env.setdefault("PIP_DEFAULT_TIMEOUT", "120")
        return

    if not _VENDOR_WHEELHOUSE.is_dir():
        return

    manifest_path = _VENDOR_WHEELHOUSE / _MANIFEST_FILENAME
    force_offline = _should_force_offline(manifest_path)

    existing_links = list(_iter_existing_values(env.get("PIP_FIND_LINKS")))
    wheelhouse_path = str(_VENDOR_WHEELHOUSE)
    if wheelhouse_path not in existing_links:
        env["PIP_FIND_LINKS"] = " ".join([wheelhouse_path, *existing_links])

    if force_offline and "PIP_NO_INDEX" not in env:
        env["PIP_NO_INDEX"] = "1"

    env.setdefault("PIP_DEFAULT_TIMEOUT", "120")


_configure_pip_environment()
install_thinc_seed_guard()
