"""
Tests for the agent endpoint POST /api/v1/chats/{id}/agent.

These tests bypass the real Ollama HTTP layer by monkeypatching the helpers
inside `agent_service` (`_ollama_chat_nonstream`, `_ollama_chat_stream`).
RAG is handled via the existing `fake_rag` fixture from conftest.

What's covered:
- Happy path: model emits a tool_call, gets the result, then a final answer.
  Assistant message persists with content + rag_citations + tool_calls.
- Iteration cap: model keeps calling tools until the cap; the forced final
  answer is streamed and the message is marked truncated.
- Tool error on malformed args: the error frame surfaces and the error is
  fed back to the model so it can self-correct.
- RAG server down on `get_info`: the agent emits an error frame before any
  tool calls happen.
- Validation: 400 when the chat's project lacks RAG config; 404 when the
  chat doesn't exist.
- User-message persistence parity with /stream: an Ollama failure mid-loop
  leaves the user message intact.
"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.db.models import Chat, Message, Project
from app.db.session import AsyncSessionLocal
from app.services import agent_service
from app.utils.exceptions import RagConnectionError

from tests.conftest import FakeRag


# ---------- helpers ----------


def _parse_ndjson(text: str) -> List[dict]:
    out: List[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


async def _read_agent_stream(
    async_client: httpx.AsyncClient, chat_id, message: str
) -> tuple[int, List[dict]]:
    """POST to the agent endpoint and return (status_code, parsed frames).

    On a non-200 response, frames will be empty and the caller can inspect
    the status code (e.g. for the 400/404 validation tests).
    """
    async with async_client.stream(
        "POST",
        f"/api/v1/chats/{chat_id}/agent",
        json={"content": message, "file_ids": None},
    ) as response:
        status = response.status_code
        body = b""
        if status == 200:
            async for chunk in response.aiter_bytes():
                body += chunk
    if status != 200:
        return status, []
    return status, _parse_ndjson(body.decode("utf-8"))


async def _make_rag_chat(
    async_client: httpx.AsyncClient,
    *,
    rag_enabled: bool = True,
    rag_corpus_id: str = "simplewiki",
    rag_top_k: int = 5,
    rag_server_url: str = "http://rag.local:8001",
    agent_mode_enabled: bool = True,
) -> tuple[str, str]:
    """Create a (optionally RAG-enabled) project + a chat in it.

    Returns (project_id, chat_id). The chat is created with
    agent_mode_enabled set so the FE-side flag is in sync.
    """
    from uuid import uuid4

    from tests.conftest import create_rag_server

    rag_server_id: Optional[str] = None
    if rag_enabled:
        server = await create_rag_server(
            async_client,
            name=f"agent-test-{uuid4().hex[:8]}",
            url=rag_server_url,
            corpus_id=rag_corpus_id,
        )
        rag_server_id = server["id"]
    project = (
        await async_client.post(
            "/api/v1/projects",
            json={
                "name": "agent-test",
                "rag_enabled": rag_enabled,
                "rag_server_id": rag_server_id,
                "rag_top_k": rag_top_k if rag_enabled else None,
            },
        )
    ).json()
    chat = (
        await async_client.post(
            "/api/v1/chats",
            json={
                "title": "agent",
                "model": "x:1b",
                "project_id": project["id"],
                "agent_mode_enabled": agent_mode_enabled,
            },
        )
    ).json()
    return project["id"], chat["id"]


def _hit(title: str, section: Optional[str], text: str, page_id: int = 1, score: float = 0.5) -> Dict[str, Any]:
    return {
        "corpus": "simplewiki",
        "chunk_id": page_id,
        "page_id": page_id,
        "title": title,
        "section": section,
        "chunk_index": 0,
        "text": text,
        "text_length": len(text),
        "score": score,
    }


# ---------- fake Ollama (driven by a scripted sequence of responses) ----------


class FakeAgentOllama:
    """Scriptable replacement for agent_service.{_ollama_chat_nonstream, _ollama_chat_stream}.

    Configure:
      - nonstream_responses: list of dicts to return on consecutive non-stream calls.
        Each dict is the value of `response.json()` from Ollama — typically
        `{"message": {"role": "assistant", "content": "...", "tool_calls": [...]}}`.
      - stream_chunks: list of strings to yield from the final stream call.
      - stream_error / nonstream_error: exception to raise instead of returning.

    Inspect:
      - nonstream_calls / stream_calls: list of kwargs dicts each call received.
    """

    def __init__(self) -> None:
        self.nonstream_responses: List[Dict[str, Any]] = []
        self.stream_chunks: List[str] = []
        self.nonstream_error: Optional[Exception] = None
        self.stream_error: Optional[Exception] = None
        self.nonstream_calls: List[Dict[str, Any]] = []
        self.stream_calls: List[Dict[str, Any]] = []
        self._nonstream_idx = 0

    async def nonstream(self, **kwargs: Any) -> Dict[str, Any]:
        self.nonstream_calls.append(kwargs)
        if self.nonstream_error is not None:
            raise self.nonstream_error
        if self._nonstream_idx >= len(self.nonstream_responses):
            raise AssertionError(
                f"FakeAgentOllama: ran out of scripted non-stream responses "
                f"(idx={self._nonstream_idx})"
            )
        resp = self.nonstream_responses[self._nonstream_idx]
        self._nonstream_idx += 1
        return resp

    async def stream(self, **kwargs: Any) -> AsyncGenerator[str, None]:
        self.stream_calls.append(kwargs)
        if self.stream_error is not None:
            raise self.stream_error
        for piece in self.stream_chunks:
            yield piece


@pytest.fixture
def fake_agent(monkeypatch: pytest.MonkeyPatch) -> FakeAgentOllama:
    fake = FakeAgentOllama()
    monkeypatch.setattr(agent_service, "_ollama_chat_nonstream", fake.nonstream)
    monkeypatch.setattr(agent_service, "_ollama_chat_stream", fake.stream)
    return fake


# ---------- helpers to build scripted responses ----------


def _model_tool_call(query: str, content: str = "") -> Dict[str, Any]:
    """Build a non-stream response that has a search_wikipedia tool call."""
    return {
        "message": {
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {"function": {"name": "search_wikipedia", "arguments": {"query": query}}},
            ],
        },
        "done": True,
    }


def _model_final(content: str) -> Dict[str, Any]:
    """Build a non-stream response with no tool_calls — model is done."""
    return {
        "message": {"role": "assistant", "content": content, "tool_calls": []},
        "done": True,
    }


# ---------- tests ----------


@pytest.mark.asyncio
async def test_happy_path_tool_call_then_answer(
    async_client: httpx.AsyncClient,
    fake_rag: FakeRag,
    fake_agent: FakeAgentOllama,
) -> None:
    """Model emits one tool_call, gets results, then a final answer with no tools."""
    fake_rag.hits = [_hit("Photosynthesis", "Light reactions", "Photosynthesis is …")]
    fake_agent.nonstream_responses = [
        _model_tool_call("photosynthesis"),
        _model_final("Photosynthesis is the process by which …"),
    ]

    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        status, frames = await _read_agent_stream(
            async_client, chat_id, "What is photosynthesis?"
        )
        assert status == 200, frames

        types = [f["type"] for f in frames]
        assert "tool_call" in types
        assert "tool_result" in types
        assert "chunk" in types
        assert types[-1] == "done"
        assert frames[-1]["truncated"] is False

        # Tool was actually dispatched to the RAG service
        assert len(fake_rag.retrieve_calls) == 1
        assert fake_rag.retrieve_calls[0]["query"] == "photosynthesis"
        # top_k capped at 3 in agent mode regardless of project setting
        assert fake_rag.retrieve_calls[0]["top_k"] == 3

        # Persisted assistant message captures content + citations + tool_calls
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
        assert "Photosynthesis is the process" in assistant.content
        assert assistant.rag_citations is not None
        assert assistant.rag_citations["hits"][0]["title"] == "Photosynthesis"
        assert assistant.tool_calls is not None
        assert len(assistant.tool_calls) == 1
        assert assistant.tool_calls[0]["name"] == "search_wikipedia"
        assert assistant.tool_calls[0]["ok"] is True
        assert assistant.truncated is False
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")


@pytest.mark.asyncio
async def test_iteration_cap_forces_final_answer_and_marks_truncated(
    async_client: httpx.AsyncClient,
    fake_rag: FakeRag,
    fake_agent: FakeAgentOllama,
) -> None:
    """If the model keeps calling tools, after 5 iterations we force a final
    streamed answer and persist truncated=True."""
    fake_rag.hits = [_hit("X", None, "x text")]
    # 5 tool calls in a row, no final answer
    fake_agent.nonstream_responses = [_model_tool_call(f"q{i}") for i in range(5)]
    fake_agent.stream_chunks = ["sorry, ", "I had to give up"]

    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        status, frames = await _read_agent_stream(async_client, chat_id, "hmm")
        assert status == 200, frames

        tool_calls = [f for f in frames if f["type"] == "tool_call"]
        assert len(tool_calls) == 5

        done = [f for f in frames if f["type"] == "done"]
        assert done and done[0]["truncated"] is True

        # The forced final call was a stream call
        assert len(fake_agent.stream_calls) == 1

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
        assert assistant.truncated is True
        assert "sorry, I had to give up" in assistant.content
        assert len(assistant.tool_calls) == 5
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")


@pytest.mark.asyncio
async def test_malformed_tool_args_surface_error_and_feed_back_to_model(
    async_client: httpx.AsyncClient,
    fake_rag: FakeRag,
    fake_agent: FakeAgentOllama,
) -> None:
    """Model passes null query → tool emits an ok:false frame, error is fed
    back as a tool message so the model can self-correct on iteration 2."""
    fake_rag.hits = [_hit("Recovered", None, "ok now")]
    bad_call = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "search_wikipedia", "arguments": {"query": None}}},
            ],
        },
        "done": True,
    }
    fake_agent.nonstream_responses = [
        bad_call,
        _model_tool_call("recovery"),
        _model_final("I figured it out: ok now."),
    ]

    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        status, frames = await _read_agent_stream(async_client, chat_id, "test recovery")
        assert status == 200, frames

        results = [f for f in frames if f["type"] == "tool_result"]
        assert len(results) == 2
        assert results[0]["ok"] is False
        assert "query" in results[0]["error"].lower()
        assert results[1]["ok"] is True

        # The second non-stream call's messages must include a tool message
        # carrying the error (so the model could "see" what went wrong).
        second_call_messages = fake_agent.nonstream_calls[1]["messages"]
        assert any(
            m["role"] == "tool" and "tool error" in m["content"].lower()
            for m in second_call_messages
        )

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
        # Both attempts logged on the message
        assert len(assistant.tool_calls) == 2
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")


@pytest.mark.asyncio
async def test_rag_get_info_failure_emits_error_frame_and_skips_loop(
    async_client: httpx.AsyncClient,
    fake_rag: FakeRag,
    fake_agent: FakeAgentOllama,
) -> None:
    """If /rag/info fails up front, the agent never enters the loop."""
    fake_rag.info_error = RagConnectionError("http://rag.local:8001", "refused")

    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        status, frames = await _read_agent_stream(async_client, chat_id, "anything")
        assert status == 200
        assert any(f["type"] == "error" for f in frames)

        # Ollama was never called
        assert len(fake_agent.nonstream_calls) == 0
        assert len(fake_agent.stream_calls) == 0

        # The user message must still have been persisted (parity with /stream)
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
        assert len(user_msgs) == 1
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")


@pytest.mark.asyncio
async def test_400_when_project_lacks_rag_config(
    async_client: httpx.AsyncClient,
    fake_rag: FakeRag,
    fake_agent: FakeAgentOllama,
) -> None:
    """Agent endpoint requires the project to have full RAG config."""
    project_id, chat_id = await _make_rag_chat(
        async_client, rag_enabled=False
    )
    try:
        r = await async_client.post(
            f"/api/v1/chats/{chat_id}/agent",
            json={"content": "anything", "file_ids": None},
        )
        assert r.status_code == 400
        assert "RAG" in r.json()["detail"]
        assert len(fake_agent.nonstream_calls) == 0
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")


@pytest.mark.asyncio
async def test_404_when_chat_does_not_exist(
    async_client: httpx.AsyncClient,
    fake_rag: FakeRag,
    fake_agent: FakeAgentOllama,
) -> None:
    """Bogus chat id → 404 before streaming starts."""
    bogus = uuid4()
    r = await async_client.post(
        f"/api/v1/chats/{bogus}/agent",
        json={"content": "anything", "file_ids": None},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_user_message_persists_when_ollama_fails_mid_loop(
    async_client: httpx.AsyncClient,
    fake_rag: FakeRag,
    fake_agent: FakeAgentOllama,
) -> None:
    """An Ollama failure inside the loop leaves the user message intact."""
    fake_agent.nonstream_error = RuntimeError("ollama exploded")

    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        status, frames = await _read_agent_stream(async_client, chat_id, "hi")
        assert status == 200
        assert any(f["type"] == "error" for f in frames)

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
        assert len(user_msgs) == 1
        assert user_msgs[0].content == "hi"
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")
