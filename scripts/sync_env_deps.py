"""Utility to synchronize dependency tooling across devcontainer and CI.

This script keeps the following concerns aligned across environments:

* Dependency installation commands (`uv sync`, `pip install`, etc.)
* Python and uv tool versions in devcontainer images and workflows
* Optional dependency extras and dev dependencies
* Lockfile validation to ensure dependency versions are pinned

It is intentionally self-contained to avoid introducing packaging
dependencies into the runtime environment.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
# Default repo-level locations used by the CLI entrypoint. Instance methods
# operate on `self.*` paths so the synchronizer can be exercised against
# arbitrary repository roots during testing.
DEVCONTAINER_DIR = REPO_ROOT / ".devcontainer"
DEVCONTAINER_JSON = DEVCONTAINER_DIR / "devcontainer.json"
DEVCONTAINER_POST_CREATE = DEVCONTAINER_DIR / "post-create.sh"


@dataclass(slots=True)
class EnvSyncConfig:
    """Configuration extracted from pyproject for environment sync."""

    commands: dict[str, str] = field(default_factory=dict)
    default_manager: str = "uv"
    python_versions: tuple[str, ...] = ("3.12",)
    uv_version: str | None = None
    lockfile: Path | None = None

    @property
    def default_command(self) -> str:
        command = self.commands.get(self.default_manager)
        if command is None:
            return "uv sync"
        return command

    def iter_commands(self) -> Iterable[str]:
        yield from self.commands.values()


class EnvironmentSynchronizer:
    """Synchronize dependency tooling across environments."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.pyproject = self.root / "pyproject.toml"
        self.lockfile = self.root / "uv.lock"
        self.devcontainer_dir = self.root / ".devcontainer"
        self.post_create = self.devcontainer_dir / "post-create.sh"
        self.devcontainer_json = self.devcontainer_dir / "devcontainer.json"
        self.workflows_dir = self.root / ".github" / "workflows"
        self.workflows = list(self.workflows_dir.glob("*.yml"))

    # ------------------------------------------------------------------
    # Configuration loading & validation
    # ------------------------------------------------------------------
    def load_config(self) -> EnvSyncConfig:
        if not self.pyproject.exists():
            raise FileNotFoundError(f"pyproject.toml not found at {self.pyproject}")

        data = tomllib.loads(self.pyproject.read_text())
        tool_section: dict[str, Any] = data.get("tool", {}).get("chiron", {})
        env_sync_section: dict[str, Any] = tool_section.get("env_sync", {})

        commands = env_sync_section.get("commands", {})
        if not commands:
            # Fall back to sensible defaults: include dev + extras to keep parity
            commands = {"uv": "uv sync --all-extras --dev"}

        default_manager = env_sync_section.get("default_manager", "uv")

        python_versions = tuple(
            str(v)
            for v in env_sync_section.get("python_versions", ["3.12"])
        )

        uv_version = env_sync_section.get("uv_version")

        config = EnvSyncConfig(
            commands=commands,
            default_manager=default_manager,
            python_versions=python_versions,
            uv_version=uv_version,
            lockfile=self.lockfile if self.lockfile.exists() else None,
        )

        return config

    # ------------------------------------------------------------------
    # File update helpers
    # ------------------------------------------------------------------
    def update_post_create(self, config: EnvSyncConfig) -> bool:
        if not self.post_create.exists():
            logger.error("Post-create script not found: %s", self.post_create)
            return False

        content = self.post_create.read_text()
        lines = []
        changed = False
        for line in content.splitlines():
            if "uv sync" in line and "--group" not in line and "--locked" not in line:
                new_line = re.sub(
                    r"uv sync(?:\s+--all-extras\s+--dev)?",
                    config.default_command,
                    line,
                )
                changed |= new_line != line
                lines.append(new_line)
            else:
                lines.append(line)

        new_content = "\n".join(lines)
        if content.endswith("\n"):
            new_content += "\n"

        if changed:
            self.post_create.write_text(new_content)
            logger.info("Updated %s", self.post_create)
            return True

        logger.info("No changes needed for %s", self.post_create)
        return False

    def update_devcontainer_image(self, config: EnvSyncConfig) -> bool:
        if not self.devcontainer_json.exists():
            logger.warning(
                "Devcontainer definition missing: %s", self.devcontainer_json
            )
            return False

        data = json.loads(self.devcontainer_json.read_text())
        image = data.get("image")
        if not image:
            return False

        desired_version = config.python_versions[0]
        new_image = re.sub(r":\d+\.\d+", f":{desired_version}", image)
        if new_image != image:
            data["image"] = new_image
            self.devcontainer_json.write_text(json.dumps(data, indent=2) + "\n")
            logger.info("Aligned devcontainer Python image to %s", desired_version)
            return True
        return False

    def update_workflow(self, path: Path, config: EnvSyncConfig) -> bool:
        if not path.exists():
            logger.warning("Workflow not found: %s", path)
            return False

        original = path.read_text()
        updated = original

        # Update dependency commands (skip specialised invocations)
        command_pattern = re.compile(r"(run:\s*(?:\|)?\s*\n?\s*)(uv sync[^\n]*)")

        def _replace_command(match: re.Match[str]) -> str:
            prefix, existing = match.groups()
            if "--group" in existing or "--locked" in existing:
                return match.group(0)
            return f"{prefix}{config.default_command}"

        updated = command_pattern.sub(_replace_command, updated)

        # Update python-version matrices
        python_versions = list(dict.fromkeys(config.python_versions))
        matrix_pattern = re.compile(r"python-version:\s*\[([^\]]+)\]")

        def _replace_matrix(match: re.Match[str]) -> str:
            versions = ", ".join(f'"{v}"' for v in python_versions)
            return f"python-version: [{versions}]"

        updated = matrix_pattern.sub(_replace_matrix, updated)

        # Update explicit uv python install commands
        uv_install_pattern = re.compile(r"uv python install \d+\.\d+")
        updated = uv_install_pattern.sub(
            f"uv python install {python_versions[0]}", updated
        )

        if updated != original:
            path.write_text(updated)
            logger.info("Updated %s", path)
            return True

        logger.info("No changes needed for %s", path)
        return False

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def validate_commands(self, config: EnvSyncConfig) -> bool:
        issues = []

        # Ensure post-create contains the default command
        if self.post_create.exists():
            post_create_content = self.post_create.read_text()
            if config.default_command not in post_create_content:
                issues.append(
                    f"{self.post_create}: Missing '{config.default_command}'"
                )

        for workflow in (
            self.workflows_dir / "ci.yml",
            self.workflows_dir / "wheels.yml",
        ):
            if workflow.exists():
                text = workflow.read_text()
                if config.default_command not in text:
                    issues.append(f"{workflow}: Missing '{config.default_command}'")

        if issues:
            logger.error("Consistency issues detected:")
            for issue in issues:
                logger.error("  - %s", issue)
            return False
        return True

    def validate_lockfile(self, config: EnvSyncConfig) -> bool:
        if config.lockfile is None or not config.lockfile.exists():
            logger.warning("Lockfile not found; skipping dependency validation")
            return True

        lock_data = tomllib.loads(config.lockfile.read_text())
        lock_packages = {
            str(pkg["name"]).lower()
            for pkg in lock_data.get("package", [])
            if isinstance(pkg, dict) and "name" in pkg
        }

        project_data = tomllib.loads(self.pyproject.read_text()).get("project", {})
        dependencies = project_data.get("dependencies", [])
        extras = project_data.get("optional-dependencies", {})

        missing: list[str] = []

        def _check(requirements: Iterable[str]) -> None:
            for dep in requirements:
                requirement = Requirement(dep)
                name = requirement.name.lower()
                if name not in lock_packages:
                    missing.append(name)

        _check(dependencies)
        for values in extras.values():
            _check(values)

        if missing:
            logger.error(
                "Lockfile is missing dependencies: %s", ", ".join(sorted(set(missing)))
            )
            return False

        logger.info("Lockfile validation succeeded")
        return True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> bool:
        config = self.load_config()

        logger.info(
            "Synchronizing dependency commands with '%s'", config.default_command
        )

        changes = False
        changes |= self.update_post_create(config)
        changes |= self.update_devcontainer_image(config)

        for workflow in self.workflows:
            changes |= self.update_workflow(workflow, config)

        if not self.validate_commands(config):
            raise SystemExit(1)

        if not self.validate_lockfile(config):
            raise SystemExit(1)

        logger.info("Environment sync complete%s", " with changes" if changes else "")
        return changes


def main() -> int:
    synchronizer = EnvironmentSynchronizer(REPO_ROOT)
    try:
        synchronizer.run()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Environment synchronization failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
