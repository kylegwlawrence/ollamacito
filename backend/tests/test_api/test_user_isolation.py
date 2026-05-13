"""
User-isolation tests for PLAN_NEW.md Phase 3.

With AUTH_ENABLED=false every request resolves to the seeded default user.
These tests verify:
- Settings responses are keyed by user_id (no stale `id: 1` shape leaking).
- Chats and projects belonging to a different user never leak through the
  list endpoints or the get-by-id paths (cross-user access returns 404).
"""
from __future__ import annotations

from typing import AsyncGenerator
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete

from app.db.models import DEFAULT_USER_ID, Chat, Project, User
from app.db.session import AsyncSessionLocal


@pytest_asyncio.fixture
async def other_user() -> AsyncGenerator[User, None]:
    """Insert a non-default user; cascade-delete on teardown."""
    user_id = uuid4()
    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=f"other-{user_id}@local",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    try:
        yield user
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


@pytest.mark.asyncio
async def test_settings_response_keyed_by_default_user_id(
    async_client: httpx.AsyncClient,
) -> None:
    """GET /api/v1/settings returns the default user's settings, with user_id."""
    response = await async_client.get("/api/v1/settings")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data.get("user_id") == str(DEFAULT_USER_ID)
    # The old singleton `id: int` field is gone post-Phase 3
    assert "id" not in data


@pytest.mark.asyncio
async def test_other_users_chat_does_not_leak_into_list(
    async_client: httpx.AsyncClient, other_user: User
) -> None:
    """A chat owned by another user must not appear in /api/v1/chats."""
    other_chat_id = uuid4()
    async with AsyncSessionLocal() as session:
        session.add(
            Chat(
                id=other_chat_id,
                user_id=other_user.id,
                title="Other user's chat",
                model="test-model:1b",
            )
        )
        await session.commit()

    try:
        response = await async_client.get("/api/v1/chats")
        assert response.status_code == 200, response.text
        ids = {c["id"] for c in response.json()["chats"]}
        assert str(other_chat_id) not in ids
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Chat).where(Chat.id == other_chat_id))
            await session.commit()


@pytest.mark.asyncio
async def test_other_users_chat_get_returns_404(
    async_client: httpx.AsyncClient, other_user: User
) -> None:
    """GET /api/v1/chats/{id} for a chat owned by another user must 404."""
    other_chat_id = uuid4()
    async with AsyncSessionLocal() as session:
        session.add(
            Chat(
                id=other_chat_id,
                user_id=other_user.id,
                title="Stranger's chat",
                model="test-model:1b",
            )
        )
        await session.commit()

    try:
        response = await async_client.get(f"/api/v1/chats/{other_chat_id}")
        assert response.status_code == 404, response.text
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Chat).where(Chat.id == other_chat_id))
            await session.commit()


@pytest.mark.asyncio
async def test_other_users_project_does_not_leak_into_list(
    async_client: httpx.AsyncClient, other_user: User
) -> None:
    """A project owned by another user must not appear in /api/v1/projects."""
    other_project_id = uuid4()
    async with AsyncSessionLocal() as session:
        session.add(
            Project(
                id=other_project_id,
                user_id=other_user.id,
                name="Other user's project",
            )
        )
        await session.commit()

    try:
        response = await async_client.get("/api/v1/projects")
        assert response.status_code == 200, response.text
        ids = {p["id"] for p in response.json()["projects"]}
        assert str(other_project_id) not in ids
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Project).where(Project.id == other_project_id))
            await session.commit()


@pytest.mark.asyncio
async def test_other_users_project_get_returns_404(
    async_client: httpx.AsyncClient, other_user: User
) -> None:
    """GET /api/v1/projects/{id} for a project owned by another user must 404."""
    other_project_id = uuid4()
    async with AsyncSessionLocal() as session:
        session.add(
            Project(
                id=other_project_id,
                user_id=other_user.id,
                name="Stranger's project",
            )
        )
        await session.commit()

    try:
        response = await async_client.get(f"/api/v1/projects/{other_project_id}")
        assert response.status_code == 404, response.text
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Project).where(Project.id == other_project_id))
            await session.commit()


@pytest.mark.asyncio
async def test_create_chat_in_other_users_project_returns_404(
    async_client: httpx.AsyncClient, other_user: User
) -> None:
    """
    Creating a chat with a project_id belonging to another user must 404,
    not silently attach the new chat to the stranger's project.
    """
    other_project_id = uuid4()
    async with AsyncSessionLocal() as session:
        session.add(
            Project(
                id=other_project_id,
                user_id=other_user.id,
                name="Stranger's project",
            )
        )
        await session.commit()

    try:
        response = await async_client.post(
            "/api/v1/chats",
            json={
                "title": "should fail",
                "model": "test-model:1b",
                "project_id": str(other_project_id),
            },
        )
        assert response.status_code == 404, response.text
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(Project).where(Project.id == other_project_id)
            )
            await session.commit()
