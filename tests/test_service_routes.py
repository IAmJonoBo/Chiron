"""Integration tests for FastAPI service routes."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from chiron.service.app import create_app


@pytest.fixture()
def service_client(tmp_path, monkeypatch):
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
    # Use context manager to properly initialize lifespan
    with TestClient(app) as client:
        yield client


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
        **kwargs: Any,
    ):  # type: ignore[override]
        captured_commands.append(cmd)

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    # Mock at the service routes api level where run_subprocess is imported
    import chiron.service.routes.api
    monkeypatch.setattr(chiron.service.routes.api, "run_subprocess", fake_run)

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

    def fake_run(cmd, **kwargs):  # type: ignore[override]
        captured_commands.append(cmd)

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    class FakeTempDir:
        def __enter__(self):
            return str(tmp_path)

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    # Mock at the service routes api level where run_subprocess is imported
    import chiron.service.routes.api
    monkeypatch.setattr(chiron.service.routes.api, "run_subprocess", fake_run)
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
    assert any("tar" in str(cmd) for cmd in captured_commands)


def test_create_airgap_bundle_requires_name(service_client: TestClient) -> None:
    response = service_client.post(
        "/api/v1/airgap/create",
        json={"bundle_name": ""},
    )
    assert response.status_code == 400


def test_health_check(service_client: TestClient) -> None:
    """Test basic health check endpoint."""
    response = service_client.get("/health/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "telemetry_enabled" in data
    assert "security_mode" in data
    assert "timestamp" in data


def test_liveness_check(service_client: TestClient) -> None:
    """Test liveness check endpoint."""
    response = service_client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"


def test_readiness_check(service_client: TestClient) -> None:
    """Test readiness check endpoint."""
    response = service_client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "checks" in data
    assert "config_valid" in data["checks"]
    assert "dependencies" in data["checks"]


def test_health_check_error_handling(monkeypatch, tmp_path) -> None:
    """Test health check error handling when core fails."""
    from chiron.service.app import create_app
    from chiron.exceptions import ChironError
    
    config: dict[str, Any] = {
        "service_name": "test-service",
        "telemetry_enabled": False,
        "security_enabled": False,
        "cors_enabled": False,
    }
    app = create_app(config=config)
    
    with TestClient(app) as client:
        # Mock health_check to raise an error
        def mock_health_check(*args, **kwargs):
            raise ChironError("Health check failed")
        
        monkeypatch.setattr(client.app.state.core, "health_check", mock_health_check)
        
        response = client.get("/health/")
        assert response.status_code == 503
        assert "unhealthy" in response.json()["detail"].lower()


def test_readiness_check_config_invalid(monkeypatch, tmp_path) -> None:
    """Test readiness check when config validation fails."""
    from chiron.service.app import create_app
    from chiron.exceptions import ChironError
    
    config: dict[str, Any] = {
        "service_name": "test-service",
        "telemetry_enabled": False,
        "security_enabled": False,
        "cors_enabled": False,
    }
    app = create_app(config=config)
    
    with TestClient(app) as client:
        # Mock validate_config to raise an error
        def mock_validate_config(*args, **kwargs):
            raise ChironError("Config invalid")
        
        monkeypatch.setattr(client.app.state.core, "validate_config", mock_validate_config)
        
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert "not ready" in response.json()["detail"].lower()


def test_process_data_success(service_client: TestClient) -> None:
    """Test successful data processing."""
    response = service_client.post(
        "/api/v1/process",
        json={"data": {"test": "data"}, "options": {"verbose": True}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "result" in data
    assert "metadata" in data


def test_process_data_error_handling(monkeypatch, service_client: TestClient) -> None:
    """Test data processing error handling."""
    from chiron.exceptions import ChironError
    
    def mock_process_data(*args, **kwargs):
        raise ChironError("Processing failed", details={"reason": "test"})
    
    monkeypatch.setattr(service_client.app.state.core, "process_data", mock_process_data)
    
    response = service_client.post(
        "/api/v1/process",
        json={"data": {"test": "data"}, "options": {}},
    )
    assert response.status_code == 400
    error_data = response.json()["detail"]
    assert error_data["error"] == "ProcessingError"
    assert "Processing failed" in error_data["message"]


def test_build_wheelhouse_subprocess_error(monkeypatch, service_client: TestClient) -> None:
    """Test wheelhouse build with subprocess error."""
    import subprocess
    
    def fake_run(cmd, **kwargs):  # type: ignore[override]
        raise subprocess.CalledProcessError(1, cmd, stderr="Build failed")
    
    # Mock at the service routes api level where run_subprocess is imported
    import chiron.service.routes.api
    monkeypatch.setattr(chiron.service.routes.api, "run_subprocess", fake_run)
    
    response = service_client.post(
        "/api/v1/wheelhouse/build",
        json={"packages": ["requests"], "output_dir": "wheelhouse"},
    )
    assert response.status_code == 500
    assert "Build failed" in response.json()["detail"]


def test_list_airgap_bundles_with_bundles(service_client: TestClient, tmp_path) -> None:
    """Test listing airgap bundles when bundles exist."""
    # Create some test bundle files
    (tmp_path / "test-airgap-bundle.tar.gz").touch()
    (tmp_path / "another-bundle.tar.gz").touch()
    (tmp_path / "not-a-bundle.txt").touch()  # Should be ignored
    
    response = service_client.get("/api/v1/airgap/bundles")
    assert response.status_code == 200
    data = response.json()
    assert "bundles" in data
    assert len(data["bundles"]) == 2
    assert "test-airgap-bundle.tar.gz" in data["bundles"]
    assert "another-bundle.tar.gz" in data["bundles"]
    assert "not-a-bundle.txt" not in data["bundles"]


def test_create_airgap_bundle_subprocess_error(monkeypatch, tmp_path, service_client: TestClient) -> None:
    """Test airgap bundle creation with subprocess error."""
    from chiron.subprocess_utils import ExecutableNotFoundError
    
    def fake_run(cmd, **kwargs):  # type: ignore[override]
        raise ExecutableNotFoundError("tar")
    
    class FakeTempDir:
        def __enter__(self):
            return str(tmp_path)
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            return False
    
    # Mock at the service routes api level
    import chiron.service.routes.api
    monkeypatch.setattr(chiron.service.routes.api, "run_subprocess", fake_run)
    monkeypatch.setattr(tempfile, "TemporaryDirectory", lambda: FakeTempDir())
    
    response = service_client.post(
        "/api/v1/airgap/create",
        json={"bundle_name": "test", "include_security": True},
    )
    assert response.status_code == 500
    assert "failed" in response.json()["detail"].lower()
