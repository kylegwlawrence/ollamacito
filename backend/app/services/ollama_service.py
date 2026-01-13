"""
Service for interacting with Ollama API.
"""
import json
from pathlib import Path
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

    def _load_title_prompt(self) -> str:
        """
        Load title generation prompt from file.

        Returns:
            str: Prompt text for title generation

        Raises:
            None: Errors are caught and logged, returns fallback prompt
        """
        try:
            prompt_file = Path(settings.title_generation_prompt_file)
            if prompt_file.exists():
                prompt_text = prompt_file.read_text().strip()
                logger.debug(f"Loaded title prompt from {prompt_file}")
                return prompt_text
            else:
                logger.warning(f"Prompt file not found: {prompt_file}")
                return "Summarize the content from this chat in 3 to 5 words."
        except Exception as e:
            logger.error(f"Error loading prompt file: {e}")
            return "Summarize the content from this chat in 3 to 5 words."

    async def generate_chat_title(
        self,
        user_messages: List[str],
        assistant_messages: List[str],
    ) -> str:
        """
        Generate a chat title using SummLlama3.2 model.
        Dynamically loads prompt from make_chat_title_prompt.md file.

        Args:
            user_messages: List of user message contents (max 2)
            assistant_messages: List of assistant message contents (max 2)

        Returns:
            str: Generated title (3-5 words)

        Raises:
            OllamaConnectionError: If unable to connect
            OllamaModelNotFoundError: If model not found
        """
        try:
            # Load prompt from file
            system_prompt = self._load_title_prompt()

            # Build conversation context for title generation
            messages = []

            # Add system message with prompt
            messages.append({"role": "system", "content": system_prompt})

            # Interleave user and assistant messages
            for i in range(max(len(user_messages), len(assistant_messages))):
                if i < len(user_messages):
                    messages.append({"role": "user", "content": user_messages[i]})
                if i < len(assistant_messages):
                    messages.append({"role": "assistant", "content": assistant_messages[i]})

            # Ask for title generation
            messages.append({"role": "user", "content": "Generate a short title for this conversation."})

            logger.info(f"Generating title using model '{settings.title_generation_model}'")

            # Call Ollama with title generation settings
            options = {
                "num_ctx": 2048,
                "num_predict": 50,
                "temperature": 0.2,
            }

            response = await self.client.chat(
                model=settings.title_generation_model,
                messages=messages,
                options=options,
                stream=False,
            )

            # Extract title from response
            title = response.get("message", {}).get("content", "").strip()

            if not title:
                logger.warning("Empty title generated, using fallback")
                return "New Chat"

            # Clean up the title (remove quotes, extra whitespace, newlines)
            title = title.replace('"', '').replace("'", "").replace("\n", " ").strip()

            # Limit title length to 50 characters for safety
            if len(title) > 50:
                title = title[:50].strip()

            logger.info(f"Generated title: '{title}'")
            return title

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "does not exist" in error_str:
                logger.error(f"Title generation model '{settings.title_generation_model}' not found")
                raise OllamaModelNotFoundError(settings.title_generation_model)
            logger.error(f"Error in title generation: {e}")
            raise OllamaConnectionError(self.base_url, str(e))


# Create global instance
ollama_service = OllamaService()
