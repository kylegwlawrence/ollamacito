"""
Shared pytest fixtures.

Tests run in-process against the FastAPI app via httpx.ASGITransport — no
network, no uvicorn. They hit the real configured database; each test that
needs persistence creates a fresh Chat row and cascade-deletes it on teardown.

The Ollama service is monkeypatched on the module-level singleton so tests
never actually call the host's Ollama process.
"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.db.models import Chat
from app.db.session import AsyncSessionLocal
from app.main import app
from app.services import ollama_service as ollama_module


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Session-scoped event loop.

    The app's `AsyncSessionLocal` / engine are module-level singletons whose
    asyncpg connection pool is bound to whatever loop first uses it. Without
    a session-scoped loop, each test gets a fresh loop and reuses pool
    connections from the previous loop, which raises "Future attached to a
    different loop" at fixture setup time.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP client wired to the FastAPI app via ASGI (no real network)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def test_chat() -> AsyncGenerator[Chat, None]:
    """Create a Chat row for a test; cascade-delete it on teardown."""
    chat_id = uuid4()
    async with AsyncSessionLocal() as session:
        chat = Chat(id=chat_id, title="New Chat", model="test-model:1b")
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

    try:
        yield chat
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Chat).where(Chat.id == chat_id))
            await session.commit()


class FakeOllama:
    """Replacement for the ollama_service singleton in tests.

    Configure behavior by setting attributes:
        - chunks: list of strings to yield from stream_chat
        - stream_error: exception to raise. With chunks_then_error=False (default)
          it's raised before any chunks yield; with chunks_then_error=True it's
          raised AFTER all chunks have yielded (simulates mid-stream failure).
        - chunks_then_error: see stream_error
        - title: string returned by generate_chat_title
        - title_error: exception to raise on generate_chat_title
        - stream_delay: per-chunk asyncio.sleep before yielding (lets tests
          race the client_disconnected check against the stream loop)

    After a call, inspect:
        - stream_calls: list of kwargs each stream_chat invocation received
        - title_calls: list of {model, user_messages, assistant_messages}
    """

    def __init__(self) -> None:
        self.chunks: List[str] = []
        self.stream_error: Optional[Exception] = None
        self.chunks_then_error: bool = False
        self.title: str = "Mock Title"
        self.title_error: Optional[Exception] = None
        self.stream_delay: float = 0.0
        self.stream_calls: List[Dict[str, Any]] = []
        self.title_calls: List[Dict[str, Any]] = []

    async def stream_chat(self, **kwargs: Any) -> AsyncGenerator[str, None]:
        self.stream_calls.append(kwargs)
        if self.stream_error is not None and not self.chunks_then_error:
            raise self.stream_error
        for chunk in self.chunks:
            if self.stream_delay:
                await asyncio.sleep(self.stream_delay)
            yield chunk
        if self.stream_error is not None and self.chunks_then_error:
            raise self.stream_error

    async def generate_chat_title(
        self,
        user_messages: List[str],
        assistant_messages: List[str],
        model: Optional[str] = None,
    ) -> str:
        self.title_calls.append(
            {
                "user_messages": user_messages,
                "assistant_messages": assistant_messages,
                "model": model,
            }
        )
        if self.title_error is not None:
            raise self.title_error
        return self.title


@pytest.fixture
def fake_ollama(monkeypatch: pytest.MonkeyPatch) -> FakeOllama:
    """Replace the ollama_service singleton's stream methods with FakeOllama."""
    fake = FakeOllama()
    real = ollama_module.ollama_service
    monkeypatch.setattr(real, "stream_chat", fake.stream_chat)
    monkeypatch.setattr(real, "generate_chat_title", fake.generate_chat_title)
    return fake
