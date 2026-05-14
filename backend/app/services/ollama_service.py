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

    @staticmethod
    def _build_options(
        temperature: Optional[float],
        max_tokens: Optional[int],
        num_ctx: Optional[int],
    ) -> Optional[Dict]:
        """
        Build an Ollama options dict from independent generation and context params.

        max_tokens maps to Ollama's `num_predict` (max tokens to generate).
        num_ctx maps to Ollama's `num_ctx` (context window size).
        """
        options: Dict = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if num_ctx is not None:
            options["num_ctx"] = num_ctx
        return options or None

    async def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        num_ctx: Optional[int] = None,
    ) -> Dict:
        """
        Send a non-streaming chat request to Ollama.

        Args:
            model: Model name to use
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Max tokens to generate (Ollama option `num_predict`)
            num_ctx: Context window size (Ollama option `num_ctx`)

        Returns:
            Dict: Response from Ollama

        Raises:
            OllamaConnectionError: If unable to connect
            OllamaModelNotFoundError: If model not found
        """
        try:
            options = self._build_options(temperature, max_tokens, num_ctx)

            logger.info(f"Sending chat request to model '{model}'")
            response = await self.client.chat(
                model=model,
                messages=messages,
                options=options,
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
        num_ctx: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Send a streaming chat request to Ollama.

        Args:
            model: Model name to use
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Max tokens to generate (Ollama option `num_predict`)
            num_ctx: Context window size (Ollama option `num_ctx`)

        Yields:
            str: Content chunks from the streaming response

        Raises:
            OllamaConnectionError: If unable to connect
            OllamaModelNotFoundError: If model not found
        """
        stream = None
        try:
            options = self._build_options(temperature, max_tokens, num_ctx)
            logger.info(f"Starting streaming chat with model '{model}'")

            stream = await self.client.chat(
                model=model,
                messages=messages,
                options=options,
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
        finally:
            # Best-effort cleanup when the caller cancels mid-stream.
            close = getattr(stream, "aclose", None)
            if close is not None:
                try:
                    await close()
                except Exception:
                    pass

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
        model: Optional[str] = None,
    ) -> str:
        """
        Generate a chat title with the given model (or the env-var fallback).

        Args:
            user_messages: List of user message contents (max 2)
            assistant_messages: List of assistant message contents (max 2)
            model: Override the title-generation model. When None, falls back to
                settings.title_generation_model (the env-var seed). Callers should
                pass the DB-stored `Settings.conversation_summarization_model`.

        Returns:
            str: Generated title (3-5 words)

        Raises:
            OllamaConnectionError: If unable to connect
            OllamaModelNotFoundError: If model not found
        """
        title_model = model or settings.title_generation_model

        try:
            # Load prompt from file
            system_prompt = self._load_title_prompt()

            # Build conversation context for title generation
            messages: List[Dict[str, str]] = []

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

            logger.info(f"Generating title using model '{title_model}'")

            # Call Ollama with title generation settings
            options = {
                "num_ctx": 8000,
                "num_predict": 100,
                "temperature": 0.7,
            }

            response = await self.client.chat(
                model=title_model,
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
                logger.error(f"Title generation model '{title_model}' not found")
                raise OllamaModelNotFoundError(title_model)
            logger.error(f"Error in title generation: {e}")
            raise OllamaConnectionError(self.base_url, str(e))

    def _load_memory_prompt(self) -> str:
        """Load the memory-generation prompt template (with `{transcript}` placeholder)."""
        try:
            prompt_file = Path(settings.memory_generation_prompt_file)
            if prompt_file.exists():
                return prompt_file.read_text().strip()
            logger.warning(f"Memory prompt file not found: {prompt_file}")
        except Exception as e:
            logger.error(f"Error loading memory prompt file: {e}")
        return (
            "Extract key facts and decisions from these project chats. "
            "Output a concise markdown bullet list under 400 words.\n\n"
            "{transcript}"
        )

    async def generate_project_memory(
        self,
        transcript: str,
        model: Optional[str] = None,
    ) -> str:
        """
        Generate a project memory document from a formatted transcript.

        Args:
            transcript: Pre-formatted chat history (caller builds this).
            model: Override the generation model. When None, falls back to
                settings.title_generation_model (env-var seed). Callers should
                pass the DB-stored `Settings.conversation_summarization_model`.

        Returns:
            str: The generated memory text (cleaned).

        Raises:
            OllamaConnectionError: If unable to connect.
            OllamaModelNotFoundError: If model not found.
        """
        gen_model = model or settings.title_generation_model

        try:
            template = self._load_memory_prompt()
            prompt = template.replace("{transcript}", transcript)

            logger.info(f"Generating project memory using model '{gen_model}'")

            response = await self.client.chat(
                model=gen_model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "num_ctx": 16000,
                    "num_predict": 1500,
                    "temperature": 0.3,
                },
                stream=False,
            )

            raw = response.get("message", {}).get("content", "").strip()
            if not raw:
                logger.warning("Empty memory generated")
                return ""

            # Strip any prompt-echo preamble: drop lines until the first
            # bullet (markdown - or *) or markdown heading (#).
            lines = raw.split("\n")
            start = next(
                (
                    i
                    for i, line in enumerate(lines)
                    if line.strip().startswith(("-", "*", "#"))
                ),
                0,
            )
            cleaned = "\n".join(lines[start:]).strip()
            logger.info(f"Generated memory ({len(cleaned)} chars)")
            return cleaned

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "does not exist" in error_str:
                logger.error(f"Memory generation model '{gen_model}' not found")
                raise OllamaModelNotFoundError(gen_model)
            logger.error(f"Error in memory generation: {e}")
            raise OllamaConnectionError(self.base_url, str(e))


# Create global instance
ollama_service = OllamaService()
