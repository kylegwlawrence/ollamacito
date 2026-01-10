"""
API endpoints for Ollama model management.
"""
from fastapi import APIRouter, HTTPException, status

from app.core.logging import get_logger
from app.schemas.ollama import OllamaModelListResponse, OllamaStatusResponse
from app.services.ollama_service import ollama_service
from app.utils.exceptions import OllamaConnectionError

router = APIRouter()
logger = get_logger(__name__)


@router.get("/models", response_model=OllamaModelListResponse)
async def list_ollama_models():
    """
    Get list of available Ollama models.

    Returns:
        OllamaModelListResponse: List of available models

    Raises:
        HTTPException: If unable to connect to Ollama
    """
    try:
        models = await ollama_service.get_models()
        return OllamaModelListResponse(models=models)
    except OllamaConnectionError as e:
        logger.error(f"Error retrieving Ollama models: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Unable to connect to Ollama",
                "suggestion": "Please ensure Ollama is running locally",
                "url": ollama_service.base_url,
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error retrieving models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving models",
        )


@router.get("/status", response_model=OllamaStatusResponse)
async def check_ollama_status():
    """
    Check Ollama connection status.

    Returns:
        OllamaStatusResponse: Connection status and model count
    """
    try:
        await ollama_service.check_health()
        models = await ollama_service.get_models()
        return OllamaStatusResponse(
            connected=True,
            url=ollama_service.base_url,
            models_count=len(models),
        )
    except OllamaConnectionError as e:
        logger.warning(f"Ollama not available: {e}")
        return OllamaStatusResponse(
            connected=False,
            url=ollama_service.base_url,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Error checking Ollama status: {e}")
        return OllamaStatusResponse(
            connected=False,
            url=ollama_service.base_url,
            error="Unknown error",
        )
