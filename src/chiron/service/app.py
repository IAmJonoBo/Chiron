"""FastAPI application factory and configuration."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel

from chiron import __version__
from chiron.core import ChironCore
from chiron.exceptions import ChironError, ChironValidationError
from chiron.service.middleware import LoggingMiddleware, SecurityMiddleware
from chiron.service.routes import api, health

logger = structlog.get_logger(__name__)


class AppConfig(BaseModel):
    """Application configuration model."""

    service_name: str = "chiron-service"
    version: str = __version__
    debug: bool = False
    cors_enabled: bool = True
    cors_origins: list[str] = ["*"]
    telemetry_enabled: bool = True
    security_enabled: bool = True
    otlp_endpoint: str = "http://localhost:4317"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("Starting Chiron service", version=__version__)

    # Initialize core components
    config = getattr(app.state, "config", {})
    core = ChironCore(
        config=config,
        enable_telemetry=config.get("telemetry_enabled", True),
        security_mode=config.get("security_enabled", True),
    )
    app.state.core = core

    # Validate configuration
    try:
        core.validate_config()
        logger.info("Configuration validated successfully")
    except ChironError as e:
        logger.error("Configuration validation failed", error=str(e))
        raise

    yield

    logger.info("Shutting down Chiron service")


def create_app(config: Optional[dict[str, Any]] = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: Optional configuration dictionary

    Returns:
        Configured FastAPI application
    """
    # Parse configuration
    app_config = AppConfig(**(config or {}))

    # Create FastAPI app
    app = FastAPI(
        title="Chiron API",
        description="Frontier-grade, production-ready Python service",
        version=__version__,
        docs_url="/docs" if app_config.debug else None,
        redoc_url="/redoc" if app_config.debug else None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Store configuration in app state
    app.state.config = config or {}
    app.state.app_config = app_config

    # Add CORS middleware
    if app_config.cors_enabled:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=app_config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Add custom middleware
    app.add_middleware(LoggingMiddleware)
    if app_config.security_enabled:
        app.add_middleware(SecurityMiddleware)

    # Exception handlers
    @app.exception_handler(ChironError)
    async def chiron_error_handler(request: Request, exc: ChironError) -> JSONResponse:
        """Handle Chiron-specific errors."""
        logger.error(
            "Chiron error occurred",
            error=str(exc),
            details=exc.details,
            path=request.url.path,
        )

        status_code = 400
        if isinstance(exc, ChironValidationError):
            status_code = 422

        return JSONResponse(
            status_code=status_code,
            content={
                "error": "ChironError",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle general exceptions."""
        logger.error(
            "Unhandled exception occurred",
            error=str(exc),
            error_type=type(exc).__name__,
            path=request.url.path,
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred",
            },
        )

    # Include routers
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(api.router, prefix="/api/v1", tags=["api"])

    # Root endpoint
    @app.get("/", summary="Root endpoint")
    async def root() -> dict[str, Any]:
        """Root endpoint with service information."""
        return {
            "service": "chiron",
            "version": __version__,
            "status": "healthy",
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    # Instrument with OpenTelemetry
    if app_config.telemetry_enabled:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("OpenTelemetry instrumentation enabled")

    logger.info("FastAPI application created", config=app_config.model_dump())
    return app
