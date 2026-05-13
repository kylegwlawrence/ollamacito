"""
CRUD tests for projects + files (PLAN_NEW.md Phase 8 coverage).
"""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.db.models import DEFAULT_USER_ID, Project, ProjectFile
from app.db.session import AsyncSessionLocal


# ---------- Projects CRUD ----------


@pytest.mark.asyncio
async def test_create_project_minimal(async_client: httpx.AsyncClient) -> None:
    r = await async_client.post("/api/v1/projects", json={"name": "p1"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "p1"
    assert data["chat_count"] == 0
    assert data["file_count"] == 0
    assert data["auto_attach_all_files"] is False

    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(select(Project).where(Project.id == data["id"]))
        ).scalar_one()
    assert row.user_id == DEFAULT_USER_ID

    await async_client.delete(f"/api/v1/projects/{data['id']}")


@pytest.mark.asyncio
async def test_create_project_with_all_optional_fields(
    async_client: httpx.AsyncClient,
) -> None:
    body = {
        "name": "with-overrides",
        "custom_instructions": "be terse",
        "default_model": "test:7b",
        "temperature": 0.3,
        "max_tokens": 4096,
        "auto_attach_all_files": True,
    }
    r = await async_client.post("/api/v1/projects", json=body)
    assert r.status_code == 201
    data = r.json()
    assert data["custom_instructions"] == "be terse"
    assert data["temperature"] == 0.3
    assert data["max_tokens"] == 4096
    assert data["auto_attach_all_files"] is True

    await async_client.delete(f"/api/v1/projects/{data['id']}")


@pytest.mark.asyncio
async def test_get_project_returns_details(async_client: httpx.AsyncClient) -> None:
    r = await async_client.post("/api/v1/projects", json={"name": "details"})
    pid = r.json()["id"]
    try:
        got = (await async_client.get(f"/api/v1/projects/{pid}")).json()
        assert got["id"] == pid
        assert got["files"] == []
        assert got["chat_count"] == 0
    finally:
        await async_client.delete(f"/api/v1/projects/{pid}")


@pytest.mark.asyncio
async def test_update_project_toggles_auto_attach_all_files(
    async_client: httpx.AsyncClient,
) -> None:
    r = await async_client.post("/api/v1/projects", json={"name": "togglable"})
    pid = r.json()["id"]
    try:
        patched = (
            await async_client.patch(
                f"/api/v1/projects/{pid}",
                json={"auto_attach_all_files": True},
            )
        ).json()
        assert patched["auto_attach_all_files"] is True

        patched_back = (
            await async_client.patch(
                f"/api/v1/projects/{pid}",
                json={"auto_attach_all_files": False},
            )
        ).json()
        assert patched_back["auto_attach_all_files"] is False
    finally:
        await async_client.delete(f"/api/v1/projects/{pid}")


@pytest.mark.asyncio
async def test_delete_project_cascades_to_chats_and_files(
    async_client: httpx.AsyncClient,
) -> None:
    p = (await async_client.post("/api/v1/projects", json={"name": "cascade"})).json()
    pid = p["id"]

    # Add a chat in the project
    chat = (
        await async_client.post(
            "/api/v1/chats",
            json={"title": "c", "model": "x:1b", "project_id": pid},
        )
    ).json()

    # Add a file to the project
    await async_client.post(
        f"/api/v1/projects/{pid}/files",
        json={"filename": "f.txt", "file_type": "txt", "content": "hello"},
    )

    # Delete the project
    assert (await async_client.delete(f"/api/v1/projects/{pid}")).status_code == 204

    # Chat is gone too (CASCADE FK)
    assert (await async_client.get(f"/api/v1/chats/{chat['id']}")).status_code == 404
    # Project is gone
    assert (await async_client.get(f"/api/v1/projects/{pid}")).status_code == 404


@pytest.mark.asyncio
async def test_get_project_chats_endpoint(async_client: httpx.AsyncClient) -> None:
    p = (await async_client.post("/api/v1/projects", json={"name": "pchats"})).json()
    pid = p["id"]
    chat_a = (
        await async_client.post(
            "/api/v1/chats",
            json={"title": "a", "model": "x:1b", "project_id": pid},
        )
    ).json()
    chat_b = (
        await async_client.post(
            "/api/v1/chats",
            json={"title": "b", "model": "x:1b", "project_id": pid},
        )
    ).json()

    try:
        data = (await async_client.get(f"/api/v1/projects/{pid}/chats")).json()
        ids = {c["id"] for c in data["chats"]}
        assert {chat_a["id"], chat_b["id"]} <= ids
        assert data["total"] >= 2
    finally:
        await async_client.delete(f"/api/v1/projects/{pid}")


# ---------- Project files ----------


@pytest.mark.asyncio
async def test_upload_file_to_project(async_client: httpx.AsyncClient) -> None:
    p = (await async_client.post("/api/v1/projects", json={"name": "files"})).json()
    pid = p["id"]
    try:
        r = await async_client.post(
            f"/api/v1/projects/{pid}/files",
            json={
                "filename": "notes.txt",
                "file_type": "txt",
                "content": "line one\nline two",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["filename"] == "notes.txt"
        assert data["file_type"] == "txt"
        assert data["file_size"] == len("line one\nline two")
        assert data["content_preview"].startswith("line one")
    finally:
        await async_client.delete(f"/api/v1/projects/{pid}")


@pytest.mark.asyncio
async def test_get_and_delete_file(async_client: httpx.AsyncClient) -> None:
    p = (await async_client.post("/api/v1/projects", json={"name": "delfiles"})).json()
    pid = p["id"]
    file_r = await async_client.post(
        f"/api/v1/projects/{pid}/files",
        json={"filename": "go.csv", "file_type": "csv", "content": "a,b,c"},
    )
    fid = file_r.json()["id"]

    try:
        got = (await async_client.get(f"/api/v1/projects/{pid}/files/{fid}")).json()
        assert got["filename"] == "go.csv"
        assert got["content"] == "a,b,c"

        assert (
            await async_client.delete(f"/api/v1/projects/{pid}/files/{fid}")
        ).status_code == 204
        assert (
            await async_client.get(f"/api/v1/projects/{pid}/files/{fid}")
        ).status_code == 404
    finally:
        await async_client.delete(f"/api/v1/projects/{pid}")


@pytest.mark.asyncio
async def test_upload_invalid_file_type_rejected(
    async_client: httpx.AsyncClient,
) -> None:
    p = (await async_client.post("/api/v1/projects", json={"name": "invalid"})).json()
    pid = p["id"]
    try:
        r = await async_client.post(
            f"/api/v1/projects/{pid}/files",
            json={"filename": "x.exe", "file_type": "exe", "content": "MZ..."},
        )
        # The schema restricts file_type to txt|json|csv|md → 422
        assert r.status_code == 422
    finally:
        await async_client.delete(f"/api/v1/projects/{pid}")


@pytest.mark.asyncio
async def test_project_file_db_link(async_client: httpx.AsyncClient) -> None:
    """The uploaded file is linked to the project via FK."""
    p = (await async_client.post("/api/v1/projects", json={"name": "linkcheck"})).json()
    pid = p["id"]
    f = (
        await async_client.post(
            f"/api/v1/projects/{pid}/files",
            json={"filename": "a.md", "file_type": "md", "content": "# hello"},
        )
    ).json()
    fid = f["id"]
    try:
        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(
                    select(ProjectFile).where(ProjectFile.id == fid)
                )
            ).scalar_one()
        assert str(row.project_id) == pid
        assert row.content == "# hello"
    finally:
        await async_client.delete(f"/api/v1/projects/{pid}")
