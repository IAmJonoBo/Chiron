from __future__ import annotations

import json
from pathlib import Path

from scripts.sync_env_deps import EnvironmentSynchronizer


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_environment_synchronizer_updates_commands_and_versions(tmp_path: Path) -> None:
    repo = tmp_path
    pyproject = """
[project]
dependencies = ["fastapi>=0.118.0"]

[project.optional-dependencies]
docs = ["mkdocs>=1.6.1"]

[tool.chiron.env_sync]
default_manager = "uv"
python_versions = ["3.12"]

[tool.chiron.env_sync.commands]
uv = "uv sync --all-extras --dev"
"""
    _write(repo / "pyproject.toml", pyproject.strip() + "\n")

    uv_lock = """
version = 1

[[package]]
name = "fastapi"

[[package]]
name = "mkdocs"
"""
    _write(repo / "uv.lock", uv_lock.strip() + "\n")

    post_create = """
#!/bin/bash
set -e
uv sync
uv sync --group dev --group test --extra test-speed
"""
    _write(repo / ".devcontainer" / "post-create.sh", post_create.strip() + "\n")

    _write(
        repo / ".devcontainer" / "devcontainer.json",
        "{\n  \"image\": \"mcr.microsoft.com/devcontainers/python:3.13\"\n}\n",
    )

    workflow = """
name: Tests

on:
  push:

jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v5
      - name: Install uv
        run: pip install uv
      - name: Install dependencies
        run: |
          uv sync
          uv sync --group dev --group test --extra test-speed
"""
    _write(
        repo / ".github" / "workflows" / "tests.yml",
        workflow.strip() + "\n",
    )

    synchronizer = EnvironmentSynchronizer(repo)
    changed = synchronizer.run()

    assert changed is True

    updated_post_create = (repo / ".devcontainer" / "post-create.sh").read_text()
    assert "uv sync --all-extras --dev" in updated_post_create
    assert "--group dev" in updated_post_create  # specialised command preserved

    updated_workflow = (repo / ".github" / "workflows" / "tests.yml").read_text()
    assert "uv sync --all-extras --dev" in updated_workflow
    assert "uv sync --group dev --group test --extra test-speed" in updated_workflow

    image_text = (repo / ".devcontainer" / "devcontainer.json").read_text()
    data = json.loads(image_text)
    assert data["image"].endswith(":3.12")
