"""
API endpoints for Ollama model management.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.logging import get_logger
from app.db.models.ollama_server import OllamaServer
from app.schemas.ollama import OllamaModelListResponse, OllamaStatusResponse
from app.services.ollama_service import ollama_service
from app.utils.exceptions import OllamaConnectionError

router = APIRouter()
logger = get_logger(__name__)


@router.get("/models", response_model=OllamaModelListResponse)
async def list_ollama_models(
    server_id: str = Query(None, description="Optional server ID to fetch models from"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get list of available Ollama models from a specific server or first online server.

    Args:
        server_id: Optional UUID of specific server to query
        db: Database session

    Returns:
        OllamaModelListResponse: List of available models

    Raises:
        HTTPException: If unable to connect to any Ollama server
    """
    try:
        base_url = None

        # If server_id provided, use that server
        if server_id:
            result = await db.execute(select(OllamaServer).where(OllamaServer.id == server_id))
            server = result.scalar_one_or_none()
            if not server:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Server not found"
                )
            if not server.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Server is not active"
                )
            base_url = server.tailscale_url
        else:
            # Find first online server
            result = await db.execute(
                select(OllamaServer)
                .where(OllamaServer.is_active == True, OllamaServer.status == "online")
                .limit(1)
            )
            server = result.scalar_one_or_none()
            if not server:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="No online Ollama servers available. Please configure a server first.",
                )
            base_url = server.tailscale_url

        models = await ollama_service.get_models(base_url)
        return OllamaModelListResponse(models=models)
    except OllamaConnectionError as e:
        logger.error(f"Error retrieving Ollama models: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Unable to connect to Ollama",
                "suggestion": "Please ensure Ollama server is running and accessible",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error retrieving models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving models",
        )


@router.get("/status", response_model=OllamaStatusResponse)
async def check_ollama_status(db: AsyncSession = Depends(get_db)):
    """
    Check Ollama connection status using first available online server.

    Returns:
        OllamaStatusResponse: Connection status and model count
    """
    try:
        # Find first online server
        result = await db.execute(
            select(OllamaServer)
            .where(OllamaServer.is_active == True, OllamaServer.status == "online")
            .limit(1)
        )
        server = result.scalar_one_or_none()

        if not server:
            return OllamaStatusResponse(
                connected=False,
                url="No servers configured",
                error="No online Ollama servers available",
            )

        is_healthy, error = await ollama_service.check_health(server.tailscale_url)
        if is_healthy:
            models = await ollama_service.get_models(server.tailscale_url)
            return OllamaStatusResponse(
                connected=True,
                url=server.tailscale_url,
                models_count=len(models),
            )
        else:
            return OllamaStatusResponse(
                connected=False,
                url=server.tailscale_url,
                error=error or "Unknown error",
            )
    except OllamaConnectionError as e:
        logger.warning(f"Ollama not available: {e}")
        return OllamaStatusResponse(
            connected=False,
            url="",
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Error checking Ollama status: {e}")
        return OllamaStatusResponse(
            connected=False,
            url="",
            error="Unknown error",
        )
