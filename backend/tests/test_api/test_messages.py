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
from typing import List, Optional

import httpx
import pytest
from sqlalchemy import select

from app.db.models import Chat, Message, Project
from app.db.session import AsyncSessionLocal
from app.utils.exceptions import OllamaConnectionError, RagConnectionError

from tests.conftest import FakeOllama, FakeRag


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


# ---------- RAG-enabled streaming ----------


async def _make_rag_chat(
    async_client: httpx.AsyncClient,
    *,
    rag_enabled: bool = True,
    rag_corpus_id: str = "simplewiki",
    rag_top_k: int = 5,
    rag_server_url: str = "http://rag.local:8001",
) -> tuple[str, str]:
    """Create a project (optionally RAG-enabled) + a chat in it. Returns (project_id, chat_id)."""
    from tests.conftest import create_rag_server

    rag_server_id: Optional[str] = None
    if rag_enabled:
        from uuid import uuid4

        server = await create_rag_server(
            async_client,
            name=f"rag-stream-{uuid4().hex[:8]}",
            url=rag_server_url,
            corpus_id=rag_corpus_id,
        )
        rag_server_id = server["id"]
    project = (
        await async_client.post(
            "/api/v1/projects",
            json={
                "name": "rag-stream",
                "rag_enabled": rag_enabled,
                "rag_server_id": rag_server_id,
                "rag_top_k": rag_top_k if rag_enabled else None,
            },
        )
    ).json()
    chat = (
        await async_client.post(
            "/api/v1/chats",
            json={"title": "rag", "model": "x:1b", "project_id": project["id"]},
        )
    ).json()
    return project["id"], chat["id"]


@pytest.mark.asyncio
async def test_rag_hits_appear_in_system_prompt_and_citations_persist(
    async_client: httpx.AsyncClient, fake_ollama: FakeOllama, fake_rag: FakeRag
) -> None:
    """
    When the project has RAG enabled, retrieved hits land in the system message
    and the assistant message's rag_citations column captures the metadata.
    """
    fake_ollama.chunks = ["ok"]
    fake_rag.hits = [
        {
            "corpus": "simplewiki",
            "chunk_id": 1,
            "page_id": 1,
            "title": "Photosynthesis",
            "section": "Light reactions",
            "chunk_index": 0,
            "text": "Photosynthesis is the process …",
            "text_length": 30,
            "score": 0.5,
        }
    ]

    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        frames = await _read_stream(async_client, chat_id, "what is photosynthesis")
        assert any(f.get("type") == "done" for f in frames)

        # Ollama saw the retrieved chunk in its system message
        assert len(fake_ollama.stream_calls) == 1
        sys_msg = fake_ollama.stream_calls[0]["messages"][0]
        assert sys_msg["role"] == "system"
        assert "[Photosynthesis § Light reactions]" in sys_msg["content"]
        assert "Photosynthesis is the process" in sys_msg["content"]

        # RAG service was actually called with the right args
        assert len(fake_rag.retrieve_calls) == 1
        rcall = fake_rag.retrieve_calls[0]
        assert rcall["corpus"] == "simplewiki"
        assert rcall["top_k"] == 5
        assert rcall["query"] == "what is photosynthesis"

        # Citation metadata persists on the assistant message
        async with AsyncSessionLocal() as session:
            assistant = (
                (
                    await session.execute(
                        select(Message).where(
                            Message.chat_id == chat_id, Message.role == "assistant"
                        )
                    )
                )
                .scalars()
                .one()
            )
        cites = assistant.rag_citations
        assert cites is not None
        assert cites["used_dense"] is True
        assert cites["corpus"] == "simplewiki"
        assert cites["server_base_url"] == "http://rag.local:8001"
        assert cites["article_url_template"] == "/article/{title}"
        assert cites["hits"][0]["title"] == "Photosynthesis"
        assert cites["hits"][0]["section"] == "Light reactions"
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")


@pytest.mark.asyncio
async def test_rag_used_dense_false_is_persisted(
    async_client: httpx.AsyncClient, fake_ollama: FakeOllama, fake_rag: FakeRag
) -> None:
    """When the RAG server falls back to sparse-only, the flag rides along on citations."""
    fake_ollama.chunks = ["ok"]
    fake_rag.used_dense = False
    fake_rag.hits = [
        {
            "corpus": "simplewiki",
            "chunk_id": 1,
            "page_id": 1,
            "title": "X",
            "section": None,
            "chunk_index": 0,
            "text": "x",
            "text_length": 1,
            "score": 0.1,
        }
    ]

    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        await _read_stream(async_client, chat_id, "q")
        async with AsyncSessionLocal() as session:
            assistant = (
                (
                    await session.execute(
                        select(Message).where(
                            Message.chat_id == chat_id, Message.role == "assistant"
                        )
                    )
                )
                .scalars()
                .one()
            )
        assert assistant.rag_citations["used_dense"] is False
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")


@pytest.mark.asyncio
async def test_rag_server_down_returns_503_and_skips_user_message(
    async_client: httpx.AsyncClient, fake_ollama: FakeOllama, fake_rag: FakeRag
) -> None:
    """
    RAG retrieval happens before the user-message commit. If the RAG server is
    unreachable, the request returns 503 and NO user message is persisted.
    """
    fake_rag.retrieve_error = RagConnectionError("http://rag.local:8001", "refused")

    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        r = await async_client.post(
            f"/api/v1/chats/{chat_id}/stream",
            json={"content": "doomed query", "file_ids": None},
        )
        assert r.status_code == 503, r.text

        async with AsyncSessionLocal() as session:
            user_msgs = (
                (
                    await session.execute(
                        select(Message).where(
                            Message.chat_id == chat_id, Message.role == "user"
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert len(user_msgs) == 0
        # Ollama was never called
        assert len(fake_ollama.stream_calls) == 0
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")


@pytest.mark.asyncio
async def test_rag_enabled_with_orphan_server_skips_retrieval_gracefully(
    async_client: httpx.AsyncClient, fake_ollama: FakeOllama, fake_rag: FakeRag
) -> None:
    """
    If the project's rag_server FK has been NULLed (server was deleted), the
    chat continues without RAG rather than 400-ing. The user can rewire the
    project from settings; meanwhile their messages still go through.
    """
    fake_ollama.chunks = ["ok"]
    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        # Simulate the FK being NULLed by ON DELETE SET NULL.
        async with AsyncSessionLocal() as session:
            project = (
                await session.execute(select(Project).where(Project.id == project_id))
            ).scalar_one()
            project.rag_server_id = None
            await session.commit()

        frames = await _read_stream(async_client, chat_id, "anything")
        assert any(f.get("type") == "done" for f in frames)
        # RAG was skipped entirely — no retrieve call, no get_info call.
        assert fake_rag.retrieve_calls == []
        # Ollama was still invoked (chat works without RAG context).
        assert len(fake_ollama.stream_calls) == 1
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")


@pytest.mark.asyncio
async def test_rag_disabled_behaves_like_baseline(
    async_client: httpx.AsyncClient,
    test_chat: Chat,
    fake_ollama: FakeOllama,
    fake_rag: FakeRag,
) -> None:
    """A chat with no RAG-enabled project never touches the RAG service."""
    fake_ollama.chunks = ["ok"]
    frames = await _read_stream(async_client, test_chat.id, "no rag here")
    assert any(f.get("type") == "done" for f in frames)
    assert fake_rag.retrieve_calls == []
    assert fake_rag.get_info_calls == []

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
            .one()
        )
    assert assistant.rag_citations is None


@pytest.mark.asyncio
async def test_rag_dedupes_hits_by_page_id(
    async_client: httpx.AsyncClient, fake_ollama: FakeOllama, fake_rag: FakeRag
) -> None:
    """Multiple hits sharing a page_id collapse to at most 2 per page."""
    fake_ollama.chunks = ["ok"]
    # 3 hits all from page_id=1, plus 1 from page_id=2 → expect 2 + 1 = 3 deduped
    fake_rag.hits = [
        {
            "corpus": "simplewiki", "chunk_id": i, "page_id": pid,
            "title": f"T{pid}", "section": f"s{i}", "chunk_index": i,
            "text": f"chunk-{i}", "text_length": 8, "score": 1.0 - i * 0.1,
        }
        for i, pid in enumerate([1, 1, 1, 2])
    ]

    project_id, chat_id = await _make_rag_chat(async_client, rag_top_k=10)
    try:
        await _read_stream(async_client, chat_id, "q")
        async with AsyncSessionLocal() as session:
            assistant = (
                (
                    await session.execute(
                        select(Message).where(
                            Message.chat_id == chat_id, Message.role == "assistant"
                        )
                    )
                )
                .scalars()
                .one()
            )
        assert len(assistant.rag_citations["hits"]) == 3
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")
