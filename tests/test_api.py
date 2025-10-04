"""Tests for FastAPI adapter."""

from fastapi.testclient import TestClient

from chiron.api import app

client = TestClient(app)


def test_root() -> None:
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Chiron API"
    assert data["version"] == "0.1.0"


def test_health() -> None:
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_list_wheelhouse() -> None:
    """Test wheelhouse listing endpoint."""
    response = client.get("/wheelhouse")
    assert response.status_code == 200
    data = response.json()
    assert "packages" in data
    assert isinstance(data["packages"], list)


def test_build_wheelhouse_success() -> None:
    """Test wheelhouse build endpoint with valid input."""
    response = client.post("/wheelhouse/build", json=["requests", "numpy"])
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "2 packages" in data["message"]


def test_build_wheelhouse_empty() -> None:
    """Test wheelhouse build endpoint with empty package list."""
    response = client.post("/wheelhouse/build", json=[])
    assert response.status_code == 400
    data = response.json()
    assert "No packages specified" in data["detail"]


def test_list_airgap_bundles() -> None:
    """Test airgap bundle listing endpoint."""
    response = client.get("/airgap/bundles")
    assert response.status_code == 200
    data = response.json()
    assert "bundles" in data
    assert isinstance(data["bundles"], list)


def test_create_airgap_bundle_success() -> None:
    """Test airgap bundle creation endpoint with valid input."""
    response = client.post("/airgap/create?bundle_name=test-bundle")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "test-bundle" in data["message"]


def test_create_airgap_bundle_empty_name() -> None:
    """Test airgap bundle creation endpoint with empty name."""
    response = client.post("/airgap/create?bundle_name=")
    assert response.status_code == 400
    data = response.json()
    assert "Bundle name is required" in data["detail"]
