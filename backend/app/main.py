"""
Main FastAPI application entry point.
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.models import Settings as DBSettings
from app.db.session import AsyncSessionLocal
from app.services.ollama_service import ollama_service
from app.utils.exceptions import (
    ChatNotFoundException,
    OllamaConnectionError,
    OllamaModelNotFoundError,
)

# Setup logging
setup_logging()
logger = get_logger(__name__)


def _run_alembic_upgrade() -> None:
    """
    Run `alembic upgrade head` synchronously. Resolves `alembic.ini` relative
    to the backend root (the parent of the `app/` package) so it works
    regardless of the process cwd.
    """
    alembic_ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    if not alembic_ini.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")
    cfg = AlembicConfig(str(alembic_ini))
    command.upgrade(cfg, "head")


async def _seed_settings_row() -> None:
    """
    Insert the single Settings row if missing. Env vars seed the values at
    install time; subsequent edits via the UI persist to the DB and are
    canonical.
    """
    async with AsyncSessionLocal() as session:
        existing = (
            await session.execute(select(DBSettings).where(DBSettings.id == 1))
        ).scalar_one_or_none()
        if existing is not None:
            return
        session.add(
            DBSettings(
                id=1,
                default_model=settings.default_model,
                conversation_summarization_model=settings.title_generation_model,
                default_temperature=0.7,
                default_max_tokens=2048,
                num_ctx=2048,
            )
        )
        await session.commit()
        logger.info("✓ Seeded initial Settings row")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for FastAPI application.
    Runs on startup and shutdown.
    """
    # Startup
    logger.info(f"Starting {settings.app_name}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Ollama URL: {settings.ollama_base_url}")

    # Apply database migrations. Alembic owns the schema; `Base.metadata.create_all`
    # is deliberately not called here anymore (it was a silent secondary source of
    # truth that masked schema drift from `postgres/init.sql`).
    if settings.run_migrations_on_startup:
        try:
            await asyncio.to_thread(_run_alembic_upgrade)
            logger.info("✓ Alembic migrations applied (upgrade head)")
        except Exception as e:
            logger.error(f"✗ Failed to apply migrations: {e}")
            raise
    else:
        logger.info("Skipping migrations on startup (RUN_MIGRATIONS_ON_STARTUP=false)")

    # Seed the global Settings row from env-var defaults if it does not yet
    # exist. After this, the DB row is canonical.
    try:
        await _seed_settings_row()
    except Exception as e:
        logger.error(f"✗ Failed to seed Settings row: {e}")
        raise

    # Check Ollama connection
    try:
        await ollama_service.check_health()
        models = await ollama_service.get_models()
        logger.info(f"✓ Connected to Ollama ({len(models)} models available)")
    except OllamaConnectionError as e:
        logger.warning(f"⚠ Ollama not available: {e}")
        logger.warning("Application will start but chat functionality may not work")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")


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
        dict: Health status
    """
    try:
        ollama_connected = await ollama_service.check_health()
        return {
            "status": "healthy",
            "ollama_connected": True,
        }
    except Exception:
        return {
            "status": "degraded",
            "ollama_connected": False,
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
