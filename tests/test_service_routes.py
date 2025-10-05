"""Integration tests for FastAPI service routes."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from chiron.service.app import create_app


@pytest.fixture()
def service_client(tmp_path, monkeypatch) -> TestClient:
    """Provide a TestClient bound to a temporary workspace."""
    config: dict[str, Any] = {
        "service_name": "test-service",
        "telemetry": {"enabled": False},
        "telemetry_enabled": False,
        "security": {"enabled": False},
        "security_enabled": False,
        "cors_enabled": False,
    }
    app = create_app(config=config)
    monkeypatch.chdir(tmp_path)
    return TestClient(app)


def test_list_wheelhouse_empty(service_client: TestClient) -> None:
    response = service_client.get("/api/v1/wheelhouse")
    assert response.status_code == 200
    assert response.json() == {"packages": []}


def test_list_wheelhouse_with_files(service_client: TestClient) -> None:
    wheelhouse_dir = Path("wheelhouse")
    wheelhouse_dir.mkdir(parents=True, exist_ok=True)
    (wheelhouse_dir / "package-1.0.0-py3-none-any.whl").touch()
    (wheelhouse_dir / "bundle.tar.gz").touch()

    response = service_client.get("/api/v1/wheelhouse")
    data = response.json()

    assert response.status_code == 200
    assert sorted(data["packages"]) == [
        "bundle.tar.gz",
        "package-1.0.0-py3-none-any.whl",
    ]


def test_build_wheelhouse_invokes_subprocess(
    monkeypatch, service_client: TestClient
) -> None:
    captured_commands: list[list[str]] = []

    def fake_run(
        cmd: list[str],
        check: bool,
        capture_output: bool = False,
        text: bool = False,
    ):  # type: ignore[override]
        captured_commands.append(cmd)

        class Result:
            returncode = 0
            stdout = "" if text else b""
            stderr = "" if text else b""

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    response = service_client.post(
        "/api/v1/wheelhouse/build",
        json={"packages": ["requests", "numpy"], "output_dir": "wheelhouse"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert any("requests" in " ".join(cmd) for cmd in captured_commands)
    assert any("numpy" in " ".join(cmd) for cmd in captured_commands)


def test_build_wheelhouse_missing_packages(service_client: TestClient) -> None:
    response = service_client.post(
        "/api/v1/wheelhouse/build",
        json={"packages": []},
    )
    assert response.status_code == 400


def test_create_airgap_bundle_success(
    monkeypatch, tmp_path, service_client: TestClient
) -> None:
    captured_commands: list[list[str]] = []

    def fake_run(cmd, check, capture_output=False, text=False):  # type: ignore[override]
        captured_commands.append(cmd)

        class Result:
            returncode = 0

        return Result()

    class FakeTempDir:
        def __enter__(self):
            return str(tmp_path)

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(tempfile, "TemporaryDirectory", lambda: FakeTempDir())

    response = service_client.post(
        "/api/v1/airgap/create",
        json={"bundle_name": "bundle", "include_security": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["bundle_file"] == "bundle-airgap-bundle.tar.gz"
    # Ensure tar command executed
    assert any(cmd and cmd[0] == "tar" for cmd in captured_commands)


def test_create_airgap_bundle_requires_name(service_client: TestClient) -> None:
    response = service_client.post(
        "/api/v1/airgap/create",
        json={"bundle_name": ""},
    )
    assert response.status_code == 400
