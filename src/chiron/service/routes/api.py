"""API routes for core functionality."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from chiron.core import ChironCore
from chiron.exceptions import ChironError


logger = structlog.get_logger(__name__)
router = APIRouter()


class ProcessRequest(BaseModel):
    """Request model for data processing."""

    data: Any
    options: dict[str, Any] = {}


class ProcessResponse(BaseModel):
    """Response model for data processing."""

    success: bool
    result: Any
    metadata: dict[str, Any] = {}


def get_core(request: Request) -> ChironCore:
    """Dependency to get the ChironCore instance."""
    if not hasattr(request.app.state, "core"):
        raise HTTPException(status_code=500, detail="Core not initialized")
    return request.app.state.core


@router.post("/process", response_model=ProcessResponse, summary="Process data")
async def process_data(
    request: ProcessRequest,
    core: ChironCore = Depends(get_core),
) -> ProcessResponse:
    """Process data through the core engine."""
    try:
        result = core.process_data(request.data)
        
        return ProcessResponse(
            success=True,
            result=result,
            metadata={
                "input_type": type(request.data).__name__,
                "options": request.options,
            },
        )
        
    except ChironError as e:
        logger.error("Data processing failed", error=str(e), details=e.details)
        raise HTTPException(
            status_code=400,
            detail={
                "error": "ProcessingError",
                "message": str(e),
                "details": e.details,
            },
        ) from e


@router.get("/info", summary="Service information")
async def service_info() -> dict[str, Any]:
    """Get service information and capabilities."""
    return {
        "service": "chiron",
        "description": "Frontier-grade, production-ready Python service",
        "capabilities": [
            "data_processing",
            "health_monitoring",
            "security_validation",
            "telemetry_collection",
        ],
        "endpoints": {
            "health": "/health",
            "api": "/api/v1",
            "docs": "/docs",
            "openapi": "/openapi.json",
        },
    }