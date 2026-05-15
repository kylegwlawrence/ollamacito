"""
Tests for the agent endpoint POST /api/v1/chats/{id}/agent.

These tests bypass the real Ollama HTTP layer by monkeypatching
`ollama_service.client.chat` — the single entry point the agent loop now uses
(one streaming call per iteration). RAG is handled via the existing `fake_rag`
fixture from conftest.

What's covered:
- Happy path: model emits a tool_call, gets the result, then a final answer.
  Assistant message persists with content + rag_citations + tool_calls.
- Iteration cap: model keeps calling tools until the cap; the forced final
  answer is streamed (with tools omitted) and the message is marked truncated.
- Tool error on malformed args: the error frame surfaces and the error is
  fed back to the model so it can self-correct.
- RAG server down on `get_info`: the agent emits an error frame before any
  tool calls happen.
- Validation: 400 when the chat's project lacks RAG config; 404 when the
  chat doesn't exist.
- User-message persistence parity with /stream: an Ollama failure mid-loop
  leaves the user message intact.
- Empty-turn fallback: when an iteration emits neither content nor tool_calls,
  one tool-free streaming fallback fires.
- Interleaved chunks + tool_call in a single streaming turn: reasoning text
  streams before the tool_call frame, and final-answer chunks land after.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.db.models import Message
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


def _hit(
    title: str, section: Optional[str], text: str, page_id: int = 1, score: float = 0.5
) -> Dict[str, Any]:
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


# ---------- fake Ollama streaming client ----------


def _make_chat_response(chunk_data: Dict[str, Any]) -> Any:
    """Build something that quacks like ollama.ChatResponse for the agent's
    `getattr(chunk, "message", ...)` + `getattr(msg, "content"/"tool_calls", ...)`
    access pattern."""
    raw_calls = chunk_data.get("tool_calls") or []
    tool_calls = [
        SimpleNamespace(
            function=SimpleNamespace(
                name=tc.get("function", {}).get("name", ""),
                arguments=tc.get("function", {}).get("arguments", {}),
            )
        )
        for tc in raw_calls
    ] or None
    message = SimpleNamespace(
        content=chunk_data.get("content", ""),
        tool_calls=tool_calls,
    )
    return SimpleNamespace(message=message)


async def _async_iter(items: List[Any]) -> AsyncIterator[Any]:
    for item in items:
        yield item


class FakeAgentStream:
    """Scriptable replacement for `ollama_service.client.chat`.

    Configure:
      - turn_scripts: list of "turns". Each turn is a list of "chunks".
        Each chunk dict may have:
          {"content": str}                 -> contributes to message.content
          {"tool_calls": [{"function": {"name": str, "arguments": dict}}, ...]}
        Chunks are emitted in order.
      - error: exception raised on the next call (mimics Ollama failure).

    Inspect:
      - calls: list of kwargs each invocation received.
    """

    def __init__(self) -> None:
        self.turn_scripts: List[List[Dict[str, Any]]] = []
        self.error: Optional[Exception] = None
        self.calls: List[Dict[str, Any]] = []
        self._turn_idx = 0

    async def __call__(self, **kwargs: Any) -> AsyncIterator[Any]:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        if self._turn_idx >= len(self.turn_scripts):
            raise AssertionError(
                f"FakeAgentStream: ran out of scripted turns (idx={self._turn_idx})"
            )
        chunks = self.turn_scripts[self._turn_idx]
        self._turn_idx += 1
        return _async_iter([_make_chat_response(c) for c in chunks])


@pytest.fixture
def fake_agent(monkeypatch: pytest.MonkeyPatch) -> FakeAgentStream:
    fake = FakeAgentStream()
    # Patch on the singleton the agent imports. ollama_service is the
    # module-level instance shared with the non-agent path.
    monkeypatch.setattr(agent_service.ollama_service.client, "chat", fake)
    return fake


# ---------- helpers to build scripted turn entries ----------


def _tool_call_chunk(query: Any, name: str = "search_wikipedia") -> Dict[str, Any]:
    """Build a streaming chunk dict carrying one tool_call."""
    return {
        "tool_calls": [
            {"function": {"name": name, "arguments": {"query": query}}},
        ],
    }


# ---------- tests ----------


@pytest.mark.asyncio
async def test_happy_path_tool_call_then_answer(
    async_client: httpx.AsyncClient,
    fake_rag: FakeRag,
    fake_agent: FakeAgentStream,
) -> None:
    """Model emits one tool_call, gets results, then a final answer with no tools."""
    fake_rag.hits = [_hit("Photosynthesis", "Light reactions", "Photosynthesis is …")]
    fake_agent.turn_scripts = [
        [_tool_call_chunk("photosynthesis")],
        [{"content": "Photosynthesis is the process by which …"}],
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

        # Exactly two streaming calls — one per iteration
        assert len(fake_agent.calls) == 2
        # Both per-iteration calls carry tools= (only iteration-cap forced final
        # and the empty-turn fallback omit tools).
        assert fake_agent.calls[0].get("tools") is not None
        assert fake_agent.calls[1].get("tools") is not None

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
    fake_agent: FakeAgentStream,
) -> None:
    """If the model keeps calling tools, after 5 iterations we force a final
    streamed answer and persist truncated=True."""
    fake_rag.hits = [_hit("X", None, "x text")]
    fake_agent.turn_scripts = (
        # 5 iterations of tool-call-only turns
        [[_tool_call_chunk(f"q{i}")] for i in range(5)]
        # 6th call is the forced-final (tools omitted)
        + [[{"content": "sorry, "}, {"content": "I had to give up"}]]
    )

    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        status, frames = await _read_agent_stream(async_client, chat_id, "hmm")
        assert status == 200, frames

        tool_calls = [f for f in frames if f["type"] == "tool_call"]
        assert len(tool_calls) == 5

        done = [f for f in frames if f["type"] == "done"]
        assert done and done[0]["truncated"] is True

        # 5 per-iteration calls + 1 forced-final call
        assert len(fake_agent.calls) == 6
        # Iteration-cap forced final omits tools= entirely
        assert "tools" not in fake_agent.calls[-1]

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
async def test_malformed_tool_args_suppress_call_and_feed_back_to_model(
    async_client: httpx.AsyncClient,
    fake_rag: FakeRag,
    fake_agent: FakeAgentStream,
) -> None:
    """Model emits an empty-query tool_call → agent suppresses it (no
    tool_call/tool_result frames flash in the UI) but feeds the error back
    as a tool message so the model can self-correct on iteration 2. The
    audit log records both the suppressed attempt and the successful one."""
    fake_rag.hits = [_hit("Recovered", None, "ok now")]
    fake_agent.turn_scripts = [
        # Turn 1: malformed tool_call (null query) — should be suppressed
        [_tool_call_chunk(None)],
        # Turn 2: corrected tool_call — should dispatch normally
        [_tool_call_chunk("recovery")],
        # Turn 3: final answer (no tool_calls)
        [{"content": "I figured it out: ok now."}],
    ]

    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        status, frames = await _read_agent_stream(
            async_client, chat_id, "test recovery"
        )
        assert status == 200, frames

        # Only the successful call's frames make it to the UI.
        tool_calls = [f for f in frames if f["type"] == "tool_call"]
        results = [f for f in frames if f["type"] == "tool_result"]
        assert len(tool_calls) == 1
        assert len(results) == 1
        assert results[0]["ok"] is True

        # The second iteration's stream call must include a tool message
        # carrying the error (so the model could "see" what went wrong).
        second_call_messages = fake_agent.calls[1]["messages"]
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
        # Audit log records both attempts: the first marked suppressed,
        # the second successful.
        assert len(assistant.tool_calls) == 2
        assert assistant.tool_calls[0]["ok"] is False
        assert assistant.tool_calls[0].get("suppressed") is True
        assert assistant.tool_calls[1]["ok"] is True
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")


@pytest.mark.asyncio
async def test_rag_get_info_failure_emits_error_frame_and_skips_loop(
    async_client: httpx.AsyncClient,
    fake_rag: FakeRag,
    fake_agent: FakeAgentStream,
) -> None:
    """If /rag/info fails up front, the agent never enters the loop."""
    fake_rag.info_error = RagConnectionError("http://rag.local:8001", "refused")

    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        status, frames = await _read_agent_stream(async_client, chat_id, "anything")
        assert status == 200
        assert any(f["type"] == "error" for f in frames)

        # Ollama was never called
        assert len(fake_agent.calls) == 0

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
    fake_agent: FakeAgentStream,
) -> None:
    """Agent endpoint requires the project to have full RAG config."""
    project_id, chat_id = await _make_rag_chat(async_client, rag_enabled=False)
    try:
        r = await async_client.post(
            f"/api/v1/chats/{chat_id}/agent",
            json={"content": "anything", "file_ids": None},
        )
        assert r.status_code == 400
        assert "RAG" in r.json()["detail"]
        assert len(fake_agent.calls) == 0
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")


@pytest.mark.asyncio
async def test_404_when_chat_does_not_exist(
    async_client: httpx.AsyncClient,
    fake_rag: FakeRag,
    fake_agent: FakeAgentStream,
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
    fake_agent: FakeAgentStream,
) -> None:
    """An Ollama failure inside the loop leaves the user message intact."""
    fake_agent.error = RuntimeError("ollama exploded")

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


@pytest.mark.asyncio
async def test_empty_turn_triggers_tool_free_fallback(
    async_client: httpx.AsyncClient,
    fake_rag: FakeRag,
    fake_agent: FakeAgentStream,
) -> None:
    """Model emits empty content + no tool_calls in iteration 1. The agent
    should fire a tool-free fallback streaming call (preserving the prior
    code's safety net for tool-aware models that emit empty turns when given
    tools) and use its output as the answer."""
    fake_agent.turn_scripts = [
        [],  # Iteration 1: completely empty stream (no content, no tool_calls)
        [{"content": "Sure — here's a direct answer."}],  # Fallback (no tools=)
    ]

    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        status, frames = await _read_agent_stream(async_client, chat_id, "hi")
        assert status == 200

        # Two calls: the empty iteration + the tool-free fallback
        assert len(fake_agent.calls) == 2
        # First call has tools= (per-iteration default)
        assert fake_agent.calls[0].get("tools") is not None
        # Fallback call has tools= omitted
        assert "tools" not in fake_agent.calls[1]

        # Final answer made it to NDJSON + persisted
        types = [f["type"] for f in frames]
        assert "chunk" in types
        assert types[-1] == "done"
        assert frames[-1]["truncated"] is False

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
        assert "direct answer" in assistant.content
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")


@pytest.mark.asyncio
async def test_streams_content_then_tool_call_in_same_turn(
    async_client: httpx.AsyncClient,
    fake_rag: FakeRag,
    fake_agent: FakeAgentStream,
) -> None:
    """Single streaming turn can emit reasoning chunks AND a tool_call.
    Verifies frame ordering: chunks first, then tool_call/tool_result, then
    next-turn chunks."""
    fake_rag.hits = [_hit("X", None, "x text")]
    fake_agent.turn_scripts = [
        [
            {"content": "Let me look "},
            {"content": "this up."},
            _tool_call_chunk("x"),
        ],
        [{"content": "The answer is x."}],
    ]

    project_id, chat_id = await _make_rag_chat(async_client)
    try:
        status, frames = await _read_agent_stream(async_client, chat_id, "what is x?")
        assert status == 200

        types = [f["type"] for f in frames]
        first_tool_call_idx = types.index("tool_call")
        # At least the two "Let me look this up." chunks come before the tool_call
        assert types[:first_tool_call_idx].count("chunk") >= 2
        # And the final-answer chunk arrives after the tool_result
        first_tool_result_idx = types.index("tool_result")
        assert any(t == "chunk" for t in types[first_tool_result_idx + 1 :])

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
        assert "Let me look this up." in assistant.content
        assert "The answer is x." in assistant.content
        assert len(assistant.tool_calls) == 1
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")
