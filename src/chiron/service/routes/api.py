"""API routes for Chiron service."""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from starlette.requests import Request

from chiron.core import ChironCore
from chiron.exceptions import ChironError

router = APIRouter()
logger = structlog.get_logger(__name__)


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


class WheelhouseRequest(BaseModel):
    """Request model for wheelhouse operations."""

    packages: list[str]
    include_deps: bool = True
    output_dir: str = "wheelhouse"


class AirgapBundleRequest(BaseModel):
    """Request model for airgap bundle creation."""

    bundle_name: str
    include_extras: bool = False
    include_security: bool = False


@router.get("/wheelhouse", summary="List wheelhouse packages")
async def list_wheelhouse() -> dict[str, list[str]]:
    """List packages in the wheelhouse.

    Returns:
        Dictionary containing list of package files in the wheelhouse.
    """
    from pathlib import Path

    wheelhouse_path = Path("wheelhouse")
    if not wheelhouse_path.exists():
        return {"packages": []}

    packages: list[str] = []
    for file in wheelhouse_path.iterdir():
        if file.suffix == ".whl" or file.name.endswith(".tar.gz"):
            packages.append(file.name)

    return {"packages": sorted(packages)}


@router.post("/wheelhouse/build", summary="Build wheelhouse")
async def build_wheelhouse(request: WheelhouseRequest) -> dict[str, Any]:
    """Build a wheelhouse for specified packages.

    Args:
        request: Wheelhouse build request with packages and options.

    Returns:
        Dictionary with build status and wheelhouse location.

    Raises:
        HTTPException: If build fails.
    """
    import subprocess
    from pathlib import Path

    if not request.packages:
        raise HTTPException(status_code=400, detail="No packages specified")

    try:
        wheelhouse_path = Path(request.output_dir)
        wheelhouse_path.mkdir(exist_ok=True)

        logger.info(
            "Building wheelhouse",
            packages=request.packages,
            output_dir=request.output_dir,
        )

        for package in request.packages:
            subprocess.run(
                ["uv", "pip", "download", "-d", str(wheelhouse_path), package],
                check=True,
                capture_output=True,
            )

        return {
            "status": "success",
            "message": f"Wheelhouse built with {len(request.packages)} packages",
            "output_dir": request.output_dir,
            "packages": request.packages,
        }

    except subprocess.CalledProcessError as e:
        logger.error("Wheelhouse build failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Build failed: {e}")


@router.get("/airgap/bundles", summary="List airgap bundles")
async def list_airgap_bundles() -> dict[str, list[str]]:
    """List available airgap bundles.

    Returns:
        Dictionary containing list of available airgap bundles.
    """
    from pathlib import Path

    bundles = []
    for bundle_file in Path(".").glob("*.tar.gz"):
        if "airgap" in bundle_file.name or "bundle" in bundle_file.name:
            bundles.append(bundle_file.name)

    return {"bundles": sorted(bundles)}


@router.post("/airgap/create", summary="Create airgap bundle")
async def create_airgap_bundle(request: AirgapBundleRequest) -> dict[str, Any]:
    """Create a new airgap bundle.

    Args:
        request: Airgap bundle creation request.

    Returns:
        Dictionary with creation status and bundle location.

    Raises:
        HTTPException: If creation fails.
    """
    import subprocess
    import tempfile
    from pathlib import Path

    if not request.bundle_name:
        raise HTTPException(status_code=400, detail="Bundle name is required")

    try:
        output_file = f"{request.bundle_name}-airgap-bundle.tar.gz"

        with tempfile.TemporaryDirectory() as temp_dir:
            wheelhouse_dir = Path(temp_dir) / "wheelhouse"
            wheelhouse_dir.mkdir()

            logger.info("Creating airgap bundle", bundle_name=request.bundle_name)

            # Download base packages
            cmd = ["uv", "pip", "download", "-d", str(wheelhouse_dir), "."]
            if request.include_extras:
                cmd[-1] = ".[all]"

            subprocess.run(cmd, check=True, capture_output=True)

            # Add security tools if requested
            if request.include_security:
                for tool in ["bandit", "safety", "semgrep"]:
                    subprocess.run(
                        ["uv", "pip", "download", "-d", str(wheelhouse_dir), tool],
                        check=True,
                        capture_output=True,
                    )

            # Create bundle
            subprocess.run(
                ["tar", "-czf", output_file, "-C", temp_dir, "wheelhouse/"], check=True
            )

        return {
            "status": "success",
            "message": f"Airgap bundle '{request.bundle_name}' created successfully",
            "bundle_file": output_file,
            "include_extras": request.include_extras,
            "include_security": request.include_security,
        }

    except subprocess.CalledProcessError as e:
        logger.error("Airgap bundle creation failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Bundle creation failed: {e}")
