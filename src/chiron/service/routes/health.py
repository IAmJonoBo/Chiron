"""Health check routes."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from chiron.core import ChironCore
from chiron.exceptions import ChironError


logger = structlog.get_logger(__name__)
router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str
    telemetry_enabled: bool
    security_mode: bool
    timestamp: str
    checks: dict[str, Any] = {}


def get_core(request: Request) -> ChironCore:
    """Dependency to get the ChironCore instance."""
    if not hasattr(request.app.state, "core"):
        raise HTTPException(status_code=500, detail="Core not initialized")
    return request.app.state.core


@router.get("/", response_model=HealthResponse, summary="Basic health check")
async def health_check(core: ChironCore = Depends(get_core)) -> HealthResponse:
    """Basic health check endpoint."""
    try:
        health_data = core.health_check()
        return HealthResponse(**health_data)
    except ChironError as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unhealthy") from e


@router.get("/ready", response_model=HealthResponse, summary="Readiness check")
async def readiness_check(core: ChironCore = Depends(get_core)) -> HealthResponse:
    """Readiness check for Kubernetes/load balancer probes."""
    try:
        # Perform more thorough checks
        health_data = core.health_check()
        
        # Add readiness-specific checks
        checks = {
            "config_valid": True,
            "dependencies": "ok",
        }
        
        # Validate configuration
        try:
            core.validate_config()
        except ChironError:
            checks["config_valid"] = False
        
        health_data["checks"] = checks
        
        # Return unhealthy if any critical checks fail
        if not checks["config_valid"]:
            raise HTTPException(status_code=503, detail="Service not ready")
        
        return HealthResponse(**health_data)
        
    except ChironError as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service not ready") from e


@router.get("/live", summary="Liveness check")
async def liveness_check() -> dict[str, str]:
    """Liveness check for Kubernetes probes."""
    return {"status": "alive"}