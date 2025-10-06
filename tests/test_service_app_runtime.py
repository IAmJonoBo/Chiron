"""Runtime behaviour tests for the FastAPI application factory."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from chiron.exceptions import ChironError, ChironValidationError
from chiron.service.app import create_app


@pytest.fixture()
def service_factory(monkeypatch: pytest.MonkeyPatch):
    """Provide a factory that yields apps wired with a stubbed core."""

    created_instances: list[Any] = []
    instrument_calls: list[FastAPI] = []

    class StubCore:
        def __init__(
            self,
            *,
            config: dict[str, Any] | None = None,
            enable_telemetry: bool,
            security_mode: bool,
        ) -> None:
            self.config = config or {}
            self.enable_telemetry = enable_telemetry
            self.security_mode = security_mode
            self.validated = False
            created_instances.append(self)

        def validate_config(self) -> None:
            self.validated = True

        def process_data(self, payload: Any) -> Any:
            if isinstance(payload, dict) and payload.get("mode") == "chiron_error":
                raise ChironError("Pipeline failure", details={"reason": "bad input"})
            if isinstance(payload, dict) and payload.get("mode") == "validation":
                raise ChironValidationError("Invalid payload", field="mode")
            return {"echo": payload}

        def health_check(self) -> dict[str, Any]:
            return {
                "status": "healthy",
                "version": "0.1.0",
                "telemetry_enabled": self.enable_telemetry,
                "security_mode": self.security_mode,
                "timestamp": "2025-01-01T00:00:00Z",
                "checks": {},
            }

    monkeypatch.setattr("chiron.service.app.ChironCore", StubCore)
    monkeypatch.setattr("chiron.service.routes.api.ChironCore", StubCore)
    monkeypatch.setattr("chiron.service.routes.health.ChironCore", StubCore)

    def _instrument(app: FastAPI) -> None:
        instrument_calls.append(app)

    monkeypatch.setattr(
        "chiron.service.app.FastAPIInstrumentor.instrument_app", _instrument
    )

    def factory(config: dict[str, Any] | None = None) -> FastAPI:
        return create_app(config)

    return factory, created_instances, instrument_calls


def test_root_endpoint_and_telemetry(service_factory) -> None:
    factory, instances, instrument_calls = service_factory
    app = factory({"telemetry_enabled": True, "security_enabled": True})

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/")
        assert response.status_code == 200
        payload = response.json()
        assert payload["service"] == "chiron"
        assert payload["status"] == "healthy"

    assert instances and instances[0].validated is True
    assert instrument_calls, "Telemetry instrumentation should be invoked"


def test_process_data_error_handling(service_factory) -> None:
    factory, instances, _ = service_factory
    app = factory({"telemetry_enabled": False, "security_enabled": False})

    with TestClient(app) as client:
        error_response = client.post(
            "/api/v1/process",
            json={"data": {"mode": "chiron_error"}},
        )
        assert error_response.status_code == 400
        error_payload = error_response.json()
        assert error_payload["detail"]["error"] == "ProcessingError"
        assert "reason" in error_payload["detail"]["details"]

        validation_response = client.post(
            "/api/v1/process",
            json={"data": {"mode": "validation"}},
        )
        assert validation_response.status_code == 400
        payload = validation_response.json()["detail"]
        assert payload["error"] == "ProcessingError"

    assert instances and instances[0].validated is True


def test_general_exception_handler(service_factory) -> None:
    factory, _, _ = service_factory
    app = factory({"telemetry_enabled": False, "security_enabled": False})

    handler = app.exception_handlers[Exception]

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/process",
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 1234),
        "server": ("testserver", 80),
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.request"}

    request = Request(scope, receive=receive)
    response = asyncio.run(handler(request, ValueError("boom")))

    assert response.status_code == 500
    payload = json.loads(response.body.decode())
    assert payload["error"] == "InternalServerError"


def test_cors_and_health_routes(service_factory) -> None:
    factory, _, _ = service_factory
    app = factory({"telemetry_enabled": False, "security_enabled": False})

    # CORS middleware should be present by default.
    middleware_names = {mw.cls.__name__ for mw in app.user_middleware}
    assert "CORSMiddleware" in middleware_names

    with TestClient(app) as client:
        health = client.get("/health/")
        assert health.status_code == 200
        readiness = client.get("/health/ready")
        assert readiness.status_code == 200
        liveness = client.get("/health/live")
        assert liveness.status_code == 200
