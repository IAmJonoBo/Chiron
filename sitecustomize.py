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

_VENDOR_WHEELHOUSE = Path(__file__).resolve().parent / "vendor" / "wheelhouse"
_MANIFEST_FILENAME = "manifest.json"
_REQUIRED_EXTRAS = {"dev", "test"}
_DISABLE_ENV_VAR = "CHIRON_DISABLE_VENDOR_WHEELHOUSE"


def _iter_existing_values(value: str | None) -> Iterable[str]:
    if not value:
        return []
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


def _configure_pip_environment() -> None:
    if os.environ.get(_DISABLE_ENV_VAR):
        return

    if not _VENDOR_WHEELHOUSE.is_dir():
        return

    manifest_path = _VENDOR_WHEELHOUSE / _MANIFEST_FILENAME
    force_offline = _should_force_offline(manifest_path)

    existing_links = list(_iter_existing_values(os.environ.get("PIP_FIND_LINKS")))
    wheelhouse_path = str(_VENDOR_WHEELHOUSE)
    if wheelhouse_path not in existing_links:
        os.environ["PIP_FIND_LINKS"] = " ".join([wheelhouse_path, *existing_links])

    if force_offline and "PIP_NO_INDEX" not in os.environ:
        os.environ["PIP_NO_INDEX"] = "1"

    os.environ.setdefault("PIP_DEFAULT_TIMEOUT", "120")


_configure_pip_environment()
