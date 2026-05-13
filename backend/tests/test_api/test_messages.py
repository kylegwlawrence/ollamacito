"""
Critical-path tests for the streaming endpoint.

Covers the Phase 1 correctness fixes (PLAN_NEW.md §3 Phase 1):
- User message survives Ollama errors / aborted streams.
- Partial assistant messages are persisted with `truncated=True`.
- Title generation runs as a background task and does not block `done`.
- `num_ctx` and `max_tokens` (Ollama `num_predict`) are passed independently.
"""
from __future__ import annotations

import asyncio
import json
from typing import List

import httpx
import pytest
from sqlalchemy import select

from app.db.models import Chat, Message
from app.db.session import AsyncSessionLocal
from app.utils.exceptions import OllamaConnectionError

from tests.conftest import FakeOllama


def _parse_sse_lines(text: str) -> List[dict]:
    """Decode a body containing one-or-more SSE `data:` frames."""
    out: List[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if not payload:
            continue
        out.append(json.loads(payload))
    return out


async def _read_stream(
    async_client: httpx.AsyncClient, chat_id, message: str
) -> List[dict]:
    """Consume the SSE stream and return the parsed frames."""
    async with async_client.stream(
        "GET",
        f"/api/v1/chats/{chat_id}/stream",
        params={"message": message},
    ) as response:
        assert response.status_code == 200
        body = b""
        async for chunk in response.aiter_bytes():
            body += chunk
    return _parse_sse_lines(body.decode("utf-8"))


@pytest.mark.asyncio
async def test_user_message_persists_when_ollama_fails(
    async_client: httpx.AsyncClient, test_chat: Chat, fake_ollama: FakeOllama
) -> None:
    """
    The user message must be saved BEFORE Ollama is invoked, so an Ollama
    failure does not lose what the user typed.
    """
    fake_ollama.stream_error = OllamaConnectionError("test", "ollama down")

    frames = await _read_stream(async_client, test_chat.id, "hello there")

    # The stream emitted an error frame, no assistant content.
    assert any("error" in f for f in frames), frames

    # The user message must still be in the DB.
    async with AsyncSessionLocal() as session:
        msgs = (
            (
                await session.execute(
                    select(Message)
                    .where(Message.chat_id == test_chat.id, Message.role == "user")
                    .order_by(Message.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
    assert len(msgs) == 1
    assert msgs[0].content == "hello there"


@pytest.mark.asyncio
async def test_truncated_assistant_message_on_stream_error_after_partial(
    async_client: httpx.AsyncClient, test_chat: Chat, fake_ollama: FakeOllama
) -> None:
    """
    When Ollama errors mid-stream after producing some content, the partial
    assistant response is persisted with `truncated=True` (no silent loss).
    """
    fake_ollama.chunks = ["Hello ", "world"]
    fake_ollama.chunks_then_error = True
    fake_ollama.stream_error = OllamaConnectionError("test", "ollama died mid-stream")

    frames = await _read_stream(async_client, test_chat.id, "say hi")

    # Two content chunks then an error frame.
    contents = [f.get("content") for f in frames if "content" in f and not f.get("done")]
    assert contents == ["Hello ", "world"]
    assert any("error" in f for f in frames)

    async with AsyncSessionLocal() as session:
        assistant = (
            (
                await session.execute(
                    select(Message)
                    .where(
                        Message.chat_id == test_chat.id,
                        Message.role == "assistant",
                    )
                    .order_by(Message.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
    assert len(assistant) == 1
    assert assistant[0].content == "Hello world"
    assert assistant[0].truncated is True


@pytest.mark.asyncio
async def test_num_ctx_and_max_tokens_pass_independently(
    async_client: httpx.AsyncClient, test_chat: Chat, fake_ollama: FakeOllama
) -> None:
    """
    The cascade must hand `max_tokens` (Ollama `num_predict`) and `num_ctx`
    to ollama_service.stream_chat as separate kwargs — not conflated.
    """
    fake_ollama.chunks = ["ok"]

    frames = await _read_stream(async_client, test_chat.id, "ping")
    assert any(f.get("done") for f in frames)

    assert len(fake_ollama.stream_calls) == 1
    call = fake_ollama.stream_calls[0]
    assert "max_tokens" in call
    assert "num_ctx" in call
    # max_tokens != num_ctx in the general case; specifically here they should
    # both be ints derived from the cascade, never None when the stream ran.
    assert isinstance(call["max_tokens"], int)
    assert isinstance(call["num_ctx"], int)


@pytest.mark.asyncio
async def test_title_generation_runs_as_background_task(
    async_client: httpx.AsyncClient, test_chat: Chat, fake_ollama: FakeOllama
) -> None:
    """
    Title generation is fired with asyncio.create_task after the stream finishes,
    so the `done` signal is not blocked by it. After the response body has been
    fully consumed, the task may or may not have run yet — but a short sleep
    must allow it to complete.
    """
    fake_ollama.chunks = ["Hi!"]
    fake_ollama.title = "Greeting Reply"

    frames = await _read_stream(async_client, test_chat.id, "hello")
    assert any(f.get("done") for f in frames)

    # Yield the loop so the background task can run.
    for _ in range(10):
        await asyncio.sleep(0.05)
        if fake_ollama.title_calls:
            break

    assert len(fake_ollama.title_calls) == 1, (
        "Expected generate_chat_title to be invoked as a background task"
    )

    async with AsyncSessionLocal() as session:
        chat = (
            await session.execute(select(Chat).where(Chat.id == test_chat.id))
        ).scalar_one()
    assert chat.title == "Greeting Reply"
