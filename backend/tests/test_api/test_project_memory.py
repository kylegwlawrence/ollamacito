"""
Tests for the project-memory feature:
- POST /projects/{id}/memory/generate
- PATCH /projects/{id} with `memory`
- Memory injection into the chat stream's system prompt.
"""
from __future__ import annotations

from typing import AsyncGenerator
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.db.models import DEFAULT_USER_ID, Chat, Message, Project, User
from app.db.session import AsyncSessionLocal

from tests.conftest import FakeOllama


@pytest_asyncio.fixture
async def other_user() -> AsyncGenerator[User, None]:
    """Insert a non-default user; cascade-delete on teardown."""
    user_id = uuid4()
    async with AsyncSessionLocal() as session:
        user = User(id=user_id, email=f"other-{user_id}@local", is_active=True)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    try:
        yield user
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


# ---------- /memory/generate ----------


@pytest.mark.asyncio
async def test_generate_memory_returns_text(
    async_client: httpx.AsyncClient, fake_ollama: FakeOllama
) -> None:
    """Happy path: project with chats → 200 + memory string."""
    fake_ollama.memory = "- Uses FastAPI\n- Postgres for storage"

    p = (await async_client.post("/api/v1/projects", json={"name": "m1"})).json()
    pid = p["id"]
    try:
        # Create a chat in the project with a user + assistant message
        chat = (
            await async_client.post(
                "/api/v1/chats",
                json={"title": "ideas", "model": "x:1b", "project_id": pid},
            )
        ).json()
        async with AsyncSessionLocal() as session:
            session.add(Message(chat_id=chat["id"], role="user", content="what stack?"))
            session.add(
                Message(chat_id=chat["id"], role="assistant", content="FastAPI + Postgres")
            )
            await session.commit()

        r = await async_client.post(f"/api/v1/projects/{pid}/memory/generate")
        assert r.status_code == 200
        assert r.json()["memory"] == "- Uses FastAPI\n- Postgres for storage"
        assert len(fake_ollama.memory_calls) == 1
        assert "FastAPI + Postgres" in fake_ollama.memory_calls[0]["transcript"]
    finally:
        await async_client.delete(f"/api/v1/projects/{pid}")


@pytest.mark.asyncio
async def test_generate_memory_empty_project_returns_422(
    async_client: httpx.AsyncClient, fake_ollama: FakeOllama
) -> None:
    p = (await async_client.post("/api/v1/projects", json={"name": "empty"})).json()
    pid = p["id"]
    try:
        r = await async_client.post(f"/api/v1/projects/{pid}/memory/generate")
        assert r.status_code == 422
        assert len(fake_ollama.memory_calls) == 0
    finally:
        await async_client.delete(f"/api/v1/projects/{pid}")


@pytest.mark.asyncio
async def test_generate_memory_other_user_project_returns_404(
    async_client: httpx.AsyncClient, fake_ollama: FakeOllama, other_user: User
) -> None:
    """Project belonging to a non-default user → 404 via get_project_or_404."""
    other_pid = uuid4()
    async with AsyncSessionLocal() as session:
        session.add(Project(id=other_pid, user_id=other_user.id, name="not-yours"))
        await session.commit()

    try:
        r = await async_client.post(f"/api/v1/projects/{other_pid}/memory/generate")
        assert r.status_code == 404
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Project).where(Project.id == other_pid))
            await session.commit()


# ---------- PATCH persistence ----------


@pytest.mark.asyncio
async def test_patch_memory_persists(async_client: httpx.AsyncClient) -> None:
    p = (await async_client.post("/api/v1/projects", json={"name": "persist"})).json()
    pid = p["id"]
    try:
        patched = (
            await async_client.patch(
                f"/api/v1/projects/{pid}", json={"memory": "- one\n- two"}
            )
        ).json()
        assert patched["memory"] == "- one\n- two"

        got = (await async_client.get(f"/api/v1/projects/{pid}")).json()
        assert got["memory"] == "- one\n- two"
    finally:
        await async_client.delete(f"/api/v1/projects/{pid}")


@pytest.mark.asyncio
async def test_patch_memory_to_null_clears(async_client: httpx.AsyncClient) -> None:
    p = (await async_client.post("/api/v1/projects", json={"name": "clear"})).json()
    pid = p["id"]
    try:
        await async_client.patch(f"/api/v1/projects/{pid}", json={"memory": "x"})
        cleared = (
            await async_client.patch(f"/api/v1/projects/{pid}", json={"memory": None})
        ).json()
        assert cleared["memory"] is None
    finally:
        await async_client.delete(f"/api/v1/projects/{pid}")


# ---------- System-prompt injection ----------


@pytest.mark.asyncio
async def test_memory_appears_in_system_prompt(
    async_client: httpx.AsyncClient, fake_ollama: FakeOllama
) -> None:
    """
    A project with memory set → that memory appears as the first section of the
    system prompt on /stream, before custom_instructions.
    """
    fake_ollama.chunks = ["ok"]

    p = (
        await async_client.post(
            "/api/v1/projects",
            json={
                "name": "withmem",
                "memory": "PROJECT-MEMORY-SENTINEL",
                "custom_instructions": "PROJECT-INSTR-SENTINEL",
            },
        )
    ).json()
    pid = p["id"]

    chat = (
        await async_client.post(
            "/api/v1/chats",
            json={"title": "t", "model": "x:1b", "project_id": pid},
        )
    ).json()

    try:
        async with async_client.stream(
            "POST",
            f"/api/v1/chats/{chat['id']}/stream",
            json={"content": "hi", "file_ids": None},
        ) as response:
            assert response.status_code == 200
            async for _ in response.aiter_bytes():
                pass

        assert len(fake_ollama.stream_calls) == 1
        messages = fake_ollama.stream_calls[0]["messages"]
        system = next(m for m in messages if m["role"] == "system")["content"]
        # Memory present
        assert "PROJECT-MEMORY-SENTINEL" in system
        # Custom instructions also present
        assert "PROJECT-INSTR-SENTINEL" in system
        # Memory comes before custom_instructions
        assert system.index("PROJECT-MEMORY-SENTINEL") < system.index("PROJECT-INSTR-SENTINEL")
    finally:
        await async_client.delete(f"/api/v1/projects/{pid}")
