"""FastAPI adapter for Chiron wheelhouse management."""

from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="Chiron API",
    description="Air-gapped Python wheelhouse management API",
    version="0.1.0",
)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint returning API information."""
    return {
        "name": "Chiron API",
        "version": "0.1.0",
        "description": "Air-gapped Python wheelhouse management",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/wheelhouse")
async def list_wheelhouse() -> dict[str, list[str]]:
    """List packages in the wheelhouse.

    Returns:
        Dictionary containing list of package files in the wheelhouse.
    """
    # Stub implementation - to be implemented
    return {"packages": []}


@app.post("/wheelhouse/build")
async def build_wheelhouse(packages: list[str]) -> dict[str, str]:
    """Build a wheelhouse for specified packages.

    Args:
        packages: List of package specifications to include.

    Returns:
        Dictionary with build status and wheelhouse location.

    Raises:
        HTTPException: If build fails.
    """
    # Stub implementation - to be implemented
    if not packages:
        raise HTTPException(status_code=400, detail="No packages specified")

    return {
        "status": "success",
        "message": f"Wheelhouse build initiated for {len(packages)} packages",
    }


@app.get("/airgap/bundles")
async def list_airgap_bundles() -> dict[str, list[str]]:
    """List available airgap bundles.

    Returns:
        Dictionary containing list of available airgap bundles.
    """
    # Stub implementation - to be implemented
    return {"bundles": []}


@app.post("/airgap/create")
async def create_airgap_bundle(bundle_name: str) -> dict[str, str]:
    """Create a new airgap bundle.

    Args:
        bundle_name: Name for the airgap bundle.

    Returns:
        Dictionary with creation status and bundle location.

    Raises:
        HTTPException: If creation fails.
    """
    # Stub implementation - to be implemented
    if not bundle_name:
        raise HTTPException(status_code=400, detail="Bundle name is required")

    return {
        "status": "success",
        "message": f"Airgap bundle '{bundle_name}' creation initiated",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
