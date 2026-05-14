"""
Tests for the RAG-server CRUD + test endpoints under /api/v1/rag-servers,
plus the per-project rag_server_id FK on Project CRUD.

The streaming-side RAG behavior is covered in test_messages.py.
"""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy import delete, select

from app.db.models import DEFAULT_USER_ID, Project, RagServer
from app.db.session import AsyncSessionLocal
from app.utils.exceptions import RagConnectionError
from tests.conftest import FakeRag


@pytest.fixture(autouse=True)
async def _wipe_rag_servers():
    """Each test starts with a clean slate of RAG servers for the default user."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(RagServer).where(RagServer.user_id == DEFAULT_USER_ID)
        )
        await session.commit()
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(RagServer).where(RagServer.user_id == DEFAULT_USER_ID)
        )
        await session.commit()


# ---------- CRUD ----------


@pytest.mark.asyncio
async def test_create_and_list_rag_server(async_client: httpx.AsyncClient) -> None:
    r = await async_client.post(
        "/api/v1/rag-servers",
        json={
            "name": "enwiki",
            "url": "http://rag.local:8001",
            "corpus_id": "enwiki",
        },
    )
    assert r.status_code == 201
    server = r.json()
    assert server["name"] == "enwiki"
    assert server["url"] == "http://rag.local:8001"
    assert server["corpus_id"] == "enwiki"

    listing = (await async_client.get("/api/v1/rag-servers")).json()
    assert len(listing["servers"]) == 1
    assert listing["servers"][0]["id"] == server["id"]


@pytest.mark.asyncio
async def test_create_rag_server_strips_trailing_slash(
    async_client: httpx.AsyncClient,
) -> None:
    r = await async_client.post(
        "/api/v1/rag-servers",
        json={
            "name": "trailing",
            "url": "http://rag.local:8001/",
            "corpus_id": "simplewiki",
        },
    )
    assert r.status_code == 201
    assert r.json()["url"] == "http://rag.local:8001"


@pytest.mark.asyncio
async def test_create_rag_server_rejects_duplicate_name(
    async_client: httpx.AsyncClient,
) -> None:
    body = {"name": "dup", "url": "http://a:1", "corpus_id": "c1"}
    assert (await async_client.post("/api/v1/rag-servers", json=body)).status_code == 201
    second = await async_client.post("/api/v1/rag-servers", json=body)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_update_rag_server(async_client: httpx.AsyncClient) -> None:
    server = (
        await async_client.post(
            "/api/v1/rag-servers",
            json={
                "name": "before",
                "url": "http://rag.local:8001",
                "corpus_id": "simplewiki",
            },
        )
    ).json()
    r = await async_client.patch(
        f"/api/v1/rag-servers/{server['id']}",
        json={"name": "after", "corpus_id": "enwiki"},
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["name"] == "after"
    assert updated["corpus_id"] == "enwiki"
    assert updated["url"] == "http://rag.local:8001"


@pytest.mark.asyncio
async def test_delete_rag_server_nulls_project_link(
    async_client: httpx.AsyncClient,
) -> None:
    server = (
        await async_client.post(
            "/api/v1/rag-servers",
            json={
                "name": "to-delete",
                "url": "http://rag.local:8001",
                "corpus_id": "simplewiki",
            },
        )
    ).json()
    project = (
        await async_client.post(
            "/api/v1/projects",
            json={
                "name": "linked",
                "rag_enabled": True,
                "rag_server_id": server["id"],
                "rag_top_k": 5,
            },
        )
    ).json()

    try:
        r = await async_client.delete(f"/api/v1/rag-servers/{server['id']}")
        assert r.status_code == 204

        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(
                    select(Project).where(Project.id == project["id"])
                )
            ).scalar_one()
            assert row.rag_server_id is None
            assert row.rag_enabled is True  # left as user set it
    finally:
        await async_client.delete(f"/api/v1/projects/{project['id']}")


@pytest.mark.asyncio
async def test_get_rag_server_404_when_missing(
    async_client: httpx.AsyncClient,
) -> None:
    from uuid import uuid4

    r = await async_client.get(f"/api/v1/rag-servers/{uuid4()}")
    assert r.status_code == 404


# ---------- Test endpoint ----------


@pytest.mark.asyncio
async def test_rag_server_test_endpoint_finds_corpus(
    async_client: httpx.AsyncClient, fake_rag: FakeRag
) -> None:
    r = await async_client.post(
        "/api/v1/rag-servers/test",
        json={"url": "http://rag.local:8001", "corpus_id": "simplewiki"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["server_name"] == "test-rag"
    assert body["available_corpora"] == ["simplewiki"]
    assert body["corpus_found"] is True
    assert fake_rag.get_info_calls == ["http://rag.local:8001"]


@pytest.mark.asyncio
async def test_rag_server_test_endpoint_reports_corpus_missing(
    async_client: httpx.AsyncClient, fake_rag: FakeRag
) -> None:
    r = await async_client.post(
        "/api/v1/rag-servers/test",
        json={"url": "http://rag.local:8001", "corpus_id": "not-on-server"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["corpus_found"] is False
    assert "not-on-server" not in body["available_corpora"]


@pytest.mark.asyncio
async def test_rag_server_test_endpoint_strips_trailing_slash(
    async_client: httpx.AsyncClient, fake_rag: FakeRag
) -> None:
    r = await async_client.post(
        "/api/v1/rag-servers/test",
        json={"url": "http://rag.local:8001/", "corpus_id": "simplewiki"},
    )
    assert r.status_code == 200
    assert fake_rag.get_info_calls == ["http://rag.local:8001"]


@pytest.mark.asyncio
async def test_rag_server_test_endpoint_surfaces_connection_error_as_503(
    async_client: httpx.AsyncClient, fake_rag: FakeRag
) -> None:
    fake_rag.info_error = RagConnectionError("http://rag.local:8001", "refused")
    r = await async_client.post(
        "/api/v1/rag-servers/test",
        json={"url": "http://rag.local:8001", "corpus_id": "simplewiki"},
    )
    assert r.status_code == 503
    body = r.json()
    assert "RAG" in body["error"]


# ---------- Project FK ----------


@pytest.mark.asyncio
async def test_create_project_with_rag_server_id(
    async_client: httpx.AsyncClient,
) -> None:
    server = (
        await async_client.post(
            "/api/v1/rag-servers",
            json={
                "name": "for-project",
                "url": "http://rag.local:8001",
                "corpus_id": "simplewiki",
            },
        )
    ).json()
    body = {
        "name": "rag-enabled",
        "rag_enabled": True,
        "rag_server_id": server["id"],
        "rag_top_k": 7,
    }
    r = await async_client.post("/api/v1/projects", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["rag_enabled"] is True
    assert data["rag_server_id"] == server["id"]
    assert data["rag_top_k"] == 7
    await async_client.delete(f"/api/v1/projects/{data['id']}")


@pytest.mark.asyncio
async def test_update_project_rag_server_id(
    async_client: httpx.AsyncClient,
) -> None:
    server = (
        await async_client.post(
            "/api/v1/rag-servers",
            json={
                "name": "patched",
                "url": "http://rag.local:8001",
                "corpus_id": "simplewiki",
            },
        )
    ).json()
    project = (
        await async_client.post("/api/v1/projects", json={"name": "rag-update"})
    ).json()
    try:
        patched = (
            await async_client.patch(
                f"/api/v1/projects/{project['id']}",
                json={
                    "rag_enabled": True,
                    "rag_server_id": server["id"],
                    "rag_top_k": 3,
                },
            )
        ).json()
        assert patched["rag_enabled"] is True
        assert patched["rag_server_id"] == server["id"]
        assert patched["rag_top_k"] == 3
    finally:
        await async_client.delete(f"/api/v1/projects/{project['id']}")


@pytest.mark.asyncio
async def test_create_project_rejects_unknown_rag_server_id(
    async_client: httpx.AsyncClient,
) -> None:
    from uuid import uuid4

    r = await async_client.post(
        "/api/v1/projects",
        json={
            "name": "bad-fk",
            "rag_enabled": True,
            "rag_server_id": str(uuid4()),
            "rag_top_k": 5,
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_project_rejects_out_of_range_top_k(
    async_client: httpx.AsyncClient,
) -> None:
    body = {"name": "bad-topk", "rag_top_k": 99}
    r = await async_client.post("/api/v1/projects", json=body)
    assert r.status_code == 422
