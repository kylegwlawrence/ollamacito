"""
Service for interacting with Ollama API.
"""
import json
from typing import AsyncGenerator, Dict, List, Optional

import httpx
import ollama
from ollama import AsyncClient

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.exceptions import OllamaConnectionError, OllamaModelNotFoundError

logger = get_logger(__name__)


class OllamaService:
    """Service for managing Ollama API interactions."""

    def __init__(self):
        """Initialize Ollama service with base URL from settings."""
        self.base_url = settings.ollama_base_url
        self.client = AsyncClient(host=self.base_url)
        logger.info(f"OllamaService initialized with base URL: {self.base_url}")

    async def check_health(self) -> bool:
        """
        Check if Ollama is accessible.

        Returns:
            bool: True if Ollama is accessible

        Raises:
            OllamaConnectionError: If unable to connect
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/tags",
                    timeout=5.0,
                )
                response.raise_for_status()
                logger.info("Ollama health check passed")
                return True
        except httpx.RequestError as e:
            logger.error(f"Ollama connection error: {e}")
            raise OllamaConnectionError(self.base_url, str(e))
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e}")
            raise OllamaConnectionError(self.base_url, f"HTTP {e.response.status_code}")

    async def get_models(self) -> List[Dict]:
        """
        Get list of available Ollama models.

        Returns:
            List[Dict]: List of model information

        Raises:
            OllamaConnectionError: If unable to connect to Ollama
        """
        try:
            response = await self.client.list()
            models = response.get("models", [])
            logger.info(f"Retrieved {len(models)} models from Ollama")
            return models
        except Exception as e:
            logger.error(f"Error retrieving models: {e}")
            raise OllamaConnectionError(self.base_url, str(e))

    async def check_model_exists(self, model_name: str) -> bool:
        """
        Check if a specific model exists.

        Args:
            model_name: Name of the model to check

        Returns:
            bool: True if model exists

        Raises:
            OllamaConnectionError: If unable to connect to Ollama
        """
        try:
            models = await self.get_models()
            model_names = [m.get("name", "").split(":")[0] for m in models]
            exists = model_name in model_names or any(
                model_name in m.get("name", "") for m in models
            )
            logger.debug(f"Model '{model_name}' exists: {exists}")
            return exists
        except OllamaConnectionError:
            raise
        except Exception as e:
            logger.error(f"Error checking model existence: {e}")
            return False

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict:
        """
        Send a non-streaming chat request to Ollama.

        Args:
            model: Model name to use
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate

        Returns:
            Dict: Response from Ollama

        Raises:
            OllamaConnectionError: If unable to connect
            OllamaModelNotFoundError: If model not found
        """
        try:
            options = {}
            if temperature is not None:
                options["temperature"] = temperature
            if max_tokens is not None:
                options["num_ctx"] = max_tokens

            logger.info(f"Sending chat request to model '{model}'")
            response = await self.client.chat(
                model=model,
                messages=messages,
                options=options if options else None,
                stream=False,
            )
            logger.info(f"Received response from model '{model}'")
            return response
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "does not exist" in error_str:
                logger.error(f"Model '{model}' not found")
                raise OllamaModelNotFoundError(model)
            logger.error(f"Error in chat request: {e}")
            raise OllamaConnectionError(self.base_url, str(e))

    async def stream_chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Send a streaming chat request to Ollama.

        Args:
            model: Model name to use
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate

        Yields:
            str: Content chunks from the streaming response

        Raises:
            OllamaConnectionError: If unable to connect
            OllamaModelNotFoundError: If model not found
        """
        try:
            options = {}
            if temperature is not None:
                options["temperature"] = temperature
            if max_tokens is not None:
                options["num_ctx"] = max_tokens

            logger.info(f"Starting streaming chat with model '{model}'")

            stream = await self.client.chat(
                model=model,
                messages=messages,
                options=options if options else None,
                stream=True,
            )

            async for chunk in stream:
                if "message" in chunk:
                    content = chunk["message"].get("content", "")
                    if content:
                        yield content

            logger.info(f"Streaming chat completed for model '{model}'")

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "does not exist" in error_str:
                logger.error(f"Model '{model}' not found")
                raise OllamaModelNotFoundError(model)
            logger.error(f"Error in streaming chat: {e}")
            raise OllamaConnectionError(self.base_url, str(e))


# Create global instance
ollama_service = OllamaService()
