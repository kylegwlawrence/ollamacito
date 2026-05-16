"""
CRUD tests for the chats endpoints (PLAN_NEW.md Phase 8 coverage).
"""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select
from uuid import uuid4

from app.db.models import DEFAULT_USER_ID, Chat, Project
from app.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_create_chat_returns_201_and_persists(
    async_client: httpx.AsyncClient,
) -> None:
    response = await async_client.post(
        "/api/v1/chats",
        json={"title": "Hello", "model": "test-model:1b"},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["title"] == "Hello"
    assert data["model"] == "test-model:1b"
    assert data["message_count"] == 0
    assert data["is_archived"] is False

    async with AsyncSessionLocal() as session:
        chat = (
            await session.execute(select(Chat).where(Chat.id == data["id"]))
        ).scalar_one()
    assert chat.user_id == DEFAULT_USER_ID
    assert chat.title == "Hello"


@pytest.mark.asyncio
async def test_list_chats_paginates(async_client: httpx.AsyncClient) -> None:
    ids = []
    for i in range(3):
        r = await async_client.post(
            "/api/v1/chats", json={"title": f"chat-{i}", "model": "test:1b"}
        )
        ids.append(r.json()["id"])

    try:
        page1 = (
            await async_client.get("/api/v1/chats", params={"page": 1, "page_size": 2})
        ).json()
        assert page1["total"] >= 3
        assert len(page1["chats"]) == 2
        assert page1["page"] == 1
        assert page1["page_size"] == 2
    finally:
        for cid in ids:
            await async_client.delete(f"/api/v1/chats/{cid}")


@pytest.mark.asyncio
async def test_get_chat_returns_messages(async_client: httpx.AsyncClient) -> None:
    r = await async_client.post(
        "/api/v1/chats", json={"title": "x", "model": "test:1b"}
    )
    cid = r.json()["id"]
    try:
        got = (await async_client.get(f"/api/v1/chats/{cid}")).json()
        assert got["id"] == cid
        assert got["messages"] == []
        assert got["message_count"] == 0
    finally:
        await async_client.delete(f"/api/v1/chats/{cid}")


@pytest.mark.asyncio
async def test_update_chat_changes_title(
    async_client: httpx.AsyncClient,
) -> None:
    r = await async_client.post(
        "/api/v1/chats", json={"title": "old", "model": "old:1b"}
    )
    cid = r.json()["id"]
    try:
        patched = (
            await async_client.patch(
                f"/api/v1/chats/{cid}",
                json={"title": "new"},
            )
        ).json()
        assert patched["title"] == "new"
        # Model is fixed at creation; it cannot be changed.
        assert patched["model"] == "old:1b"
    finally:
        await async_client.delete(f"/api/v1/chats/{cid}")


@pytest.mark.asyncio
async def test_update_chat_rejects_model_change(
    async_client: httpx.AsyncClient,
) -> None:
    """Once a chat is created, its model is locked. Supplying `model` in
    a PATCH must be rejected (422) and the stored model must be unchanged."""
    r = await async_client.post(
        "/api/v1/chats", json={"title": "old", "model": "old:1b"}
    )
    cid = r.json()["id"]
    try:
        rejected = await async_client.patch(
            f"/api/v1/chats/{cid}",
            json={"model": "new:7b"},
        )
        assert rejected.status_code == 422, rejected.text

        # And the stored model is unchanged.
        got = (await async_client.get(f"/api/v1/chats/{cid}")).json()
        assert got["model"] == "old:1b"
    finally:
        await async_client.delete(f"/api/v1/chats/{cid}")


@pytest.mark.asyncio
async def test_delete_chat_removes_row(async_client: httpx.AsyncClient) -> None:
    r = await async_client.post(
        "/api/v1/chats", json={"title": "tmp", "model": "x:1b"}
    )
    cid = r.json()["id"]

    delete_r = await async_client.delete(f"/api/v1/chats/{cid}")
    assert delete_r.status_code == 204

    get_r = await async_client.get(f"/api/v1/chats/{cid}")
    assert get_r.status_code == 404


@pytest.mark.asyncio
async def test_archive_chat(async_client: httpx.AsyncClient) -> None:
    r = await async_client.post(
        "/api/v1/chats", json={"title": "to-archive", "model": "x:1b"}
    )
    cid = r.json()["id"]
    try:
        archived = (await async_client.post(f"/api/v1/chats/{cid}/archive")).json()
        assert archived["is_archived"] is True

        # Default list excludes archived
        list_default = (await async_client.get("/api/v1/chats")).json()
        assert cid not in {c["id"] for c in list_default["chats"]}

        # Explicit include_archived=true brings it back
        list_all = (
            await async_client.get(
                "/api/v1/chats", params={"include_archived": "true"}
            )
        ).json()
        assert cid in {c["id"] for c in list_all["chats"]}
    finally:
        await async_client.delete(f"/api/v1/chats/{cid}")


@pytest.mark.asyncio
async def test_create_chat_in_owned_project(
    async_client: httpx.AsyncClient,
) -> None:
    """`project_id` must succeed when the project belongs to the current user."""
    project_id = uuid4()
    async with AsyncSessionLocal() as session:
        session.add(Project(id=project_id, user_id=DEFAULT_USER_ID, name="P"))
        await session.commit()

    try:
        r = await async_client.post(
            "/api/v1/chats",
            json={"title": "in proj", "model": "x:1b", "project_id": str(project_id)},
        )
        assert r.status_code == 201, r.text
        assert r.json()["project_id"] == str(project_id)
    finally:
        await async_client.delete(f"/api/v1/projects/{project_id}")
