"""
Critical-path tests for the streaming endpoint.

Covers the Phase 4 POST + NDJSON transport while preserving the Phase 1
correctness guarantees (PLAN_NEW.md):

- User message survives Ollama errors / aborted streams.
- Partial assistant messages are persisted with `truncated=True`.
- Title generation runs as a background task and does not block `done`.
- `num_ctx` and `max_tokens` (Ollama `num_predict`) are passed independently.
- The endpoint shape itself: POST with JSON body, NDJSON response framing.
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


def _parse_ndjson(text: str) -> List[dict]:
    """Decode a body containing one JSON object per `\\n`-terminated line."""
    out: List[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


async def _read_stream(
    async_client: httpx.AsyncClient, chat_id, message: str
) -> List[dict]:
    """POST to the stream endpoint and return parsed NDJSON frames."""
    async with async_client.stream(
        "POST",
        f"/api/v1/chats/{chat_id}/stream",
        json={"content": message, "file_ids": None},
    ) as response:
        assert response.status_code == 200, response.status_code
        body = b""
        async for chunk in response.aiter_bytes():
            body += chunk
    return _parse_ndjson(body.decode("utf-8"))


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

    assert any(f.get("type") == "error" for f in frames), frames

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
    assistant response is persisted with `truncated=True`.
    """
    fake_ollama.chunks = ["Hello ", "world"]
    fake_ollama.chunks_then_error = True
    fake_ollama.stream_error = OllamaConnectionError("test", "died mid-stream")

    frames = await _read_stream(async_client, test_chat.id, "say hi")

    contents = [f["content"] for f in frames if f.get("type") == "chunk"]
    assert contents == ["Hello ", "world"]
    assert any(f.get("type") == "error" for f in frames)

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
async def test_done_frame_carries_truncated_false_on_success(
    async_client: httpx.AsyncClient, test_chat: Chat, fake_ollama: FakeOllama
) -> None:
    """A clean stream ends with a `done` frame whose truncated flag is false."""
    fake_ollama.chunks = ["ok"]

    frames = await _read_stream(async_client, test_chat.id, "ping")
    done_frames = [f for f in frames if f.get("type") == "done"]
    assert len(done_frames) == 1
    assert done_frames[0]["truncated"] is False

    async with AsyncSessionLocal() as session:
        assistant = (
            (
                await session.execute(
                    select(Message).where(
                        Message.chat_id == test_chat.id, Message.role == "assistant"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(assistant) == 1
    assert assistant[0].truncated is False


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
    assert any(f.get("type") == "done" for f in frames)

    assert len(fake_ollama.stream_calls) == 1
    call = fake_ollama.stream_calls[0]
    assert "max_tokens" in call
    assert "num_ctx" in call
    assert isinstance(call["max_tokens"], int)
    assert isinstance(call["num_ctx"], int)


@pytest.mark.asyncio
async def test_title_generation_runs_as_background_task(
    async_client: httpx.AsyncClient, test_chat: Chat, fake_ollama: FakeOllama
) -> None:
    """
    Title generation is fired with asyncio.create_task after the stream
    finishes, so the `done` frame is not blocked by it.
    """
    fake_ollama.chunks = ["Hi!"]
    fake_ollama.title = "Greeting Reply"

    frames = await _read_stream(async_client, test_chat.id, "hello")
    assert any(f.get("type") == "done" for f in frames)

    for _ in range(10):
        await asyncio.sleep(0.05)
        if fake_ollama.title_calls:
            break

    assert len(fake_ollama.title_calls) == 1

    async with AsyncSessionLocal() as session:
        chat = (
            await session.execute(select(Chat).where(Chat.id == test_chat.id))
        ).scalar_one()
    assert chat.title == "Greeting Reply"


@pytest.mark.asyncio
async def test_chat_not_found_emits_error_frame(
    async_client: httpx.AsyncClient, fake_ollama: FakeOllama
) -> None:
    """Streaming against a non-existent chat returns a single error frame."""
    from uuid import uuid4

    bogus = uuid4()
    frames = await _read_stream(async_client, bogus, "hi")
    assert len(frames) == 1
    assert frames[0]["type"] == "error"
    assert "not found" in frames[0]["message"].lower()
