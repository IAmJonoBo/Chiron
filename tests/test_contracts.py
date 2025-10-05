"""Contract testing with Pact for Chiron API.

This module provides contract tests for the Chiron service API
using Pact consumer-driven contracts.
"""

from __future__ import annotations

import contextlib
import socket

import pytest
import requests

try:
    from pact import Consumer, Like, Provider, Term

    PACT_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency guard
    PACT_AVAILABLE = False
    pytest.skip("Pact not available", allow_module_level=True)


def _can_bind_localhost(port: int) -> bool:
    """Return True when we can bind the provided localhost port."""
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


@pytest.fixture(scope="module")
def pact():
    """Create a Pact instance for testing."""
    if not _can_bind_localhost(8000):
        pytest.skip(
            "Pact mock service cannot bind to localhost:8000 in this environment"
        )

    pact = Consumer("chiron-consumer").has_pact_with(
        Provider("chiron-service"),
        host_name="localhost",
        port=8000,
        pact_dir="pacts",
    )
    pact.start_service()
    yield pact
    pact.stop_service()


class TestChironAPIContract:
    """Contract tests for Chiron API endpoints."""

    def test_health_check_contract(self, pact):
        """Test health check endpoint contract."""
        expected_response = {
            "ok": True,
            "service": "chiron",
            "version": Like("0.1.0"),
            "timestamp": Term(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "2024-01-01T00:00:00"
            ),
        }

        (
            pact.given("service is healthy")
            .upon_receiving("a health check request")
            .with_request("GET", "/healthz")
            .will_respond_with(200, body=expected_response)
        )

        with pact:
            response = requests.get(f"{pact.uri}/healthz", timeout=5)
            assert response.status_code == 200

    def test_wheelhouse_list_contract(self, pact):
        """Test wheelhouse list endpoint contract."""
        expected_response = {
            "wheelhouses": Like(
                [
                    {
                        "name": Like("wheelhouse-linux"),
                        "platform": Like("linux"),
                        "python_version": Like("3.12"),
                        "wheel_count": Like(145),
                        "size_bytes": Like(157286400),
                        "created_at": Term(
                            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
                            "2024-01-01T00:00:00",
                        ),
                    }
                ]
            )
        }

        (
            pact.given("wheelhouses exist")
            .upon_receiving("a wheelhouse list request")
            .with_request("GET", "/api/v1/wheelhouses")
            .will_respond_with(200, body=expected_response)
        )

        with pact:
            response = requests.get(f"{pact.uri}/api/v1/wheelhouses", timeout=5)
            assert response.status_code == 200

    def test_verify_artifact_contract(self, pact):
        """Test artifact verification endpoint contract."""
        expected_response = {
            "artifact": Like("wheelhouse.tar.gz"),
            "verified": True,
            "checks": Like(
                {
                    "signature": {"status": "verified", "algorithm": "sigstore"},
                    "sbom": {"status": "valid", "format": "cyclonedx"},
                    "provenance": {"status": "valid", "level": "SLSA3"},
                    "checksums": {"status": "matched", "algorithm": "sha256"},
                }
            ),
            "timestamp": Term(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "2024-01-01T00:00:00"
            ),
        }

        (
            pact.given("artifact exists and is signed")
            .upon_receiving("a verification request")
            .with_request(
                "POST", "/api/v1/verify", body={"artifact": "wheelhouse.tar.gz"}
            )
            .will_respond_with(200, body=expected_response)
        )

        with pact:
            response = requests.post(
                f"{pact.uri}/api/v1/verify",
                json={"artifact": "wheelhouse.tar.gz"},
                timeout=5,
            )
            assert response.status_code == 200

    def test_sbom_generation_contract(self, pact):
        """Test SBOM generation endpoint contract."""
        expected_response = {
            "sbom": Like(
                {
                    "bomFormat": "CycloneDX",
                    "specVersion": "1.5",
                    "serialNumber": Term(
                        r"urn:uuid:[a-f0-9-]+",
                        "urn:uuid:12345678-1234-1234-1234-123456789abc",
                    ),
                    "version": Like(1),
                    "components": Like([]),
                }
            ),
            "generated_at": Term(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "2024-01-01T00:00:00"
            ),
        }

        (
            pact.given("project has dependencies")
            .upon_receiving("an SBOM generation request")
            .with_request("POST", "/api/v1/sbom/generate")
            .will_respond_with(200, body=expected_response)
        )

        with pact:
            response = requests.post(f"{pact.uri}/api/v1/sbom/generate", timeout=5)
            assert response.status_code == 200

    def test_policy_check_contract(self, pact):
        """Test policy check endpoint contract."""
        expected_response = {
            "passed": True,
            "violations": Like([]),
            "warnings": Like([]),
            "policy_version": Like("1.0.0"),
            "checked_at": Term(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "2024-01-01T00:00:00"
            ),
        }

        (
            pact.given("dependencies meet policy")
            .upon_receiving("a policy check request")
            .with_request(
                "POST",
                "/api/v1/policy/check",
                body={"dependencies": [{"name": "example-pkg", "version": "1.0.0"}]},
            )
            .will_respond_with(200, body=expected_response)
        )

        with pact:
            response = requests.post(
                f"{pact.uri}/api/v1/policy/check",
                json={"dependencies": [{"name": "example-pkg", "version": "1.0.0"}]},
                timeout=5,
            )
            assert response.status_code == 200


class TestChironFeatureFlagContract:
    """Contract tests for feature flag endpoints."""

    def test_feature_flags_list_contract(self, pact):
        """Test feature flags list endpoint contract."""
        expected_response = {
            "flags": Like(
                [
                    {
                        "name": Like("allow_public_publish"),
                        "enabled": Like(False),
                        "description": Like("Allow publishing to public PyPI"),
                        "default": Like(False),
                    }
                ]
            )
        }

        (
            pact.given("feature flags are configured")
            .upon_receiving("a feature flags list request")
            .with_request("GET", "/api/v1/features")
            .will_respond_with(200, body=expected_response)
        )

        with pact:
            response = requests.get(f"{pact.uri}/api/v1/features", timeout=5)
            assert response.status_code == 200
