"""Coverage-focused tests for chiron.deps.constraints."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from chiron.deps import constraints


class DummyResult(SimpleNamespace):
    """Helper for subprocess results."""


@pytest.fixture()
def sample_config(tmp_path: Path) -> constraints.ConstraintsConfig:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname='demo'\nversion='0.0.1'\n")
    output = tmp_path / "constraints.txt"
    return constraints.ConstraintsConfig(
        project_root=tmp_path,
        pyproject_path=pyproject,
        output_path=output,
        include_extras=["dev"],
        python_version="3.11",
    )


def test_generate_with_uv_success(monkeypatch: pytest.MonkeyPatch, sample_config: constraints.ConstraintsConfig) -> None:
    recorded: dict[str, object] = {}

    def fake_which(binary: str) -> str:
        assert binary == "uv"
        return "/usr/bin/uv"

    def fake_run(cmd: list[str], **kwargs: object) -> DummyResult:
        recorded["cmd"] = cmd
        sample_config.output_path.write_text("package==1.0 --hash=sha256:deadbeef\n")
        return DummyResult(returncode=0, stderr="")

    monkeypatch.setattr(constraints.shutil, "which", fake_which)
    monkeypatch.setattr(constraints, "run_subprocess", fake_run)

    generator = constraints.ConstraintsGenerator(sample_config)
    assert generator.generate() is True
    assert generator.verify_hashes() is True
    assert recorded["cmd"] == [
        "/usr/bin/uv",
        "pip",
        "compile",
        str(sample_config.pyproject_path),
        "-o",
        str(sample_config.output_path),
        "--generate-hashes",
        "--extra",
        "dev",
        "--python-version",
        "3.11",
    ]


def test_generate_with_uv_missing_binary(monkeypatch: pytest.MonkeyPatch, sample_config: constraints.ConstraintsConfig) -> None:
    monkeypatch.setattr(constraints.shutil, "which", lambda name: None)
    generator = constraints.ConstraintsGenerator(sample_config)
    assert generator.generate() is False


def test_generate_with_uv_failure(monkeypatch: pytest.MonkeyPatch, sample_config: constraints.ConstraintsConfig) -> None:
    def fake_which(binary: str) -> str:
        return "/usr/bin/uv"

    def fake_run(cmd: list[str], **kwargs: object) -> DummyResult:
        return DummyResult(returncode=1, stderr="boom")

    monkeypatch.setattr(constraints.shutil, "which", fake_which)
    monkeypatch.setattr(constraints, "run_subprocess", fake_run)

    generator = constraints.ConstraintsGenerator(sample_config)
    assert generator.generate() is False


def test_generate_with_pip_tools_success(monkeypatch: pytest.MonkeyPatch, sample_config: constraints.ConstraintsConfig) -> None:
    sample_config.tool = "pip-tools"

    def fake_which(binary: str) -> str:
        assert binary == "pip-compile"
        return "/usr/bin/pip-compile"

    def fake_run(cmd: list[str], **kwargs: object) -> DummyResult:
        sample_config.output_path.write_text("package==1.0 --hash=sha256:feedface\n")
        return DummyResult(returncode=0, stderr="")

    monkeypatch.setattr(constraints.shutil, "which", fake_which)
    monkeypatch.setattr(constraints, "run_subprocess", fake_run)

    generator = constraints.ConstraintsGenerator(sample_config)
    assert generator.generate() is True
    assert generator.verify_hashes() is True


def test_generate_with_pip_tools_missing_binary(monkeypatch: pytest.MonkeyPatch, sample_config: constraints.ConstraintsConfig) -> None:
    sample_config.tool = "pip-tools"
    monkeypatch.setattr(constraints.shutil, "which", lambda name: None)
    generator = constraints.ConstraintsGenerator(sample_config)
    assert generator.generate() is False


def test_generate_with_unknown_tool(sample_config: constraints.ConstraintsConfig) -> None:
    sample_config.tool = "unknown"  # type: ignore[assignment]
    generator = constraints.ConstraintsGenerator(sample_config)
    with pytest.raises(ValueError):
        generator.generate()


def test_verify_hashes_handles_missing_and_plain_files(tmp_path: Path) -> None:
    config = constraints.ConstraintsConfig(
        project_root=tmp_path,
        pyproject_path=tmp_path / "pyproject.toml",
        output_path=tmp_path / "constraints.txt",
    )
    generator = constraints.ConstraintsGenerator(config)

    assert generator.verify_hashes() is False

    config.output_path.write_text("package==1.0\n")
    assert generator.verify_hashes() is False

    config.output_path.write_text("package==1.0 --hash=sha256:cafe\n")
    assert generator.verify_hashes() is True


def test_generate_constraints_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_root = tmp_path
    (project_root / "pyproject.toml").write_text("[project]\nname='demo'\nversion='0.0.1'\n")
    generated: dict[str, object] = {}

    def fake_which(binary: str) -> str:
        return "/usr/bin/uv"

    def fake_run(cmd: list[str], **kwargs: object) -> DummyResult:
        generated["cmd"] = cmd
        (project_root / "constraints.txt").write_text("package==1.0 --hash=sha256:bead\n")
        return DummyResult(returncode=0, stderr="")

    monkeypatch.setattr(constraints.shutil, "which", fake_which)
    monkeypatch.setattr(constraints, "run_subprocess", fake_run)

    assert constraints.generate_constraints(project_root) is True
    assert (project_root / "constraints.txt").read_text().strip().endswith("--hash=sha256:bead")
    assert generated["cmd"][3] == str(project_root / "pyproject.toml")
