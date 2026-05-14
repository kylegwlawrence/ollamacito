"""
Service for interacting with an external local-Wikipedia-style RAG server.

The RAG server is treated as a black-box HTTP service exposing:
  - GET  /rag/info
  - POST /rag/retrieve

See LOCAL_WIKIPEDIA_API.md at the repo root for the wire contract.
"""

from typing import Dict, Optional

import httpx

from app.core.logging import get_logger
from app.utils.exceptions import (
    RagConnectionError,
    RagCorpusNotFoundError,
    RagValidationError,
)

logger = get_logger(__name__)


class RagService:
    """Thin async HTTP wrapper around a configured RAG server."""

    def __init__(self, timeout: float = 30.0) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._timeout = timeout

    def _get_client(self) -> httpx.AsyncClient:
        # Lazy-init so the client binds to whichever event loop the first call runs on
        # (matches what pytest-asyncio tests expect and avoids "attached to different loop").
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        return base_url.rstrip("/")

    async def get_info(self, base_url: str) -> Dict:
        """
        Fetch /rag/info from the target server.

        Raises:
            RagConnectionError: connection refused / timeout / 5xx
            RagValidationError: 422 (defensive — shouldn't occur for GET)
        """
        url = self._normalize_base_url(base_url)
        client = self._get_client()
        try:
            response = await client.get(f"{url}/rag/info")
        except httpx.RequestError as e:
            logger.warning(f"RAG /rag/info request error at {url}: {e}")
            raise RagConnectionError(url, str(e)) from e

        if 500 <= response.status_code < 600:
            raise RagConnectionError(url, f"HTTP {response.status_code} from /rag/info")
        if response.status_code == 422:
            raise RagValidationError(response.text, url=url)
        if response.status_code >= 400:
            raise RagConnectionError(url, f"HTTP {response.status_code} from /rag/info")

        return response.json()

    async def retrieve(
        self,
        base_url: str,
        query: str,
        corpus: str,
        top_k: int,
    ) -> Dict:
        """
        Call POST /rag/retrieve on the target server.

        Returns the raw response dict: {"used_dense": bool, "hits": [...]}

        Raises:
            RagConnectionError: connection refused / timeout / 5xx
            RagCorpusNotFoundError: 404 (unknown corpus)
            RagValidationError: 422 (blank query, bad top_k, missing field)
        """
        url = self._normalize_base_url(base_url)
        client = self._get_client()
        payload = {"query": query, "corpus": corpus, "top_k": top_k}
        try:
            response = await client.post(f"{url}/rag/retrieve", json=payload)
        except httpx.RequestError as e:
            logger.warning(f"RAG /rag/retrieve request error at {url}: {e}")
            raise RagConnectionError(url, str(e)) from e

        if 500 <= response.status_code < 600:
            raise RagConnectionError(
                url, f"HTTP {response.status_code} from /rag/retrieve"
            )
        if response.status_code == 404:
            raise RagCorpusNotFoundError(corpus, url=url)
        if response.status_code == 422:
            raise RagValidationError(response.text, url=url)
        if response.status_code >= 400:
            raise RagConnectionError(
                url, f"HTTP {response.status_code} from /rag/retrieve"
            )

        return response.json()


# Module-level singleton (mirrors ollama_service pattern)
rag_service = RagService()
