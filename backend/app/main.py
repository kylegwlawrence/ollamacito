"""
Main FastAPI application entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.services.health_monitor import health_monitor
from app.services.ollama_service import ollama_service
from app.utils.exceptions import (
    ChatNotFoundException,
    OllamaConnectionError,
    OllamaModelNotFoundError,
)

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for FastAPI application.
    Runs on startup and shutdown.
    """
    # Startup
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Debug mode: {settings.debug}")

    # Initialize database tables
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✓ Database tables initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize database: {e}")
        raise

    # Check for configured Ollama servers
    try:
        from sqlalchemy import select

        from app.db.models.ollama_server import OllamaServer

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(OllamaServer).where(OllamaServer.is_active == True)
            )
            servers = result.scalars().all()
            if servers:
                logger.info(f"✓ Found {len(servers)} configured Ollama server(s)")
            else:
                logger.warning("⚠ No Ollama servers configured")
                logger.warning("Add servers via POST /api/v1/ollama-servers")
    except Exception as e:
        logger.warning(f"⚠ Could not check Ollama servers: {e}")

    # Start health monitor
    try:
        await health_monitor.start()
        logger.info("✓ Health monitor started")
    except Exception as e:
        logger.error(f"✗ Failed to start health monitor: {e}")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")

    # Stop health monitor
    try:
        await health_monitor.stop()
        logger.info("✓ Health monitor stopped")
    except Exception as e:
        logger.error(f"✗ Error stopping health monitor: {e}")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Local AI chat application powered by Ollama",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handlers
@app.exception_handler(OllamaConnectionError)
async def ollama_connection_error_handler(request, exc: OllamaConnectionError):
    """Handle Ollama connection errors."""
    logger.error(f"Ollama connection error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "Ollama Connection Error",
            "detail": str(exc),
            "suggestion": "Ensure Ollama is running locally and accessible",
            "url": exc.url,
        },
    )


@app.exception_handler(OllamaModelNotFoundError)
async def ollama_model_not_found_handler(request, exc: OllamaModelNotFoundError):
    """Handle Ollama model not found errors."""
    logger.error(f"Ollama model not found: {exc.model}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "Model Not Found",
            "detail": f"Model '{exc.model}' is not available",
            "suggestion": "Check available models with GET /api/v1/ollama/models",
        },
    )


@app.exception_handler(ChatNotFoundException)
async def chat_not_found_handler(request, exc: ChatNotFoundException):
    """Handle chat not found errors."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "Chat Not Found",
            "detail": f"Chat with ID '{exc.chat_id}' does not exist",
        },
    )


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint for container orchestration.

    Returns:
        dict: Health status with Ollama server count
    """
    try:
        from sqlalchemy import select

        from app.db.models.ollama_server import OllamaServer

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(OllamaServer).where(
                    OllamaServer.is_active == True, OllamaServer.status == "online"
                )
            )
            online_servers = len(result.scalars().all())

        return {
            "status": "healthy",
            "online_servers": online_servers,
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "degraded",
            "online_servers": 0,
        }


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint with API information.

    Returns:
        dict: API information
    """
    return {
        "app": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs",
        "api": "/api/v1",
    }


# Include API router
app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level,
    )
