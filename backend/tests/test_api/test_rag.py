"""
Tests for the RAG-server integration: the /projects/{id}/rag/info proxy
endpoint and the per-project RAG config fields on Project CRUD.

The streaming-side RAG behavior is covered in test_messages.py.
"""
from __future__ import annotations

import httpx
import pytest

from app.utils.exceptions import RagConnectionError, RagCorpusNotFoundError

from tests.conftest import FakeRag


@pytest.mark.asyncio
async def test_rag_info_endpoint_proxies_server_payload(
    async_client: httpx.AsyncClient, fake_rag: FakeRag
) -> None:
    project = (
        await async_client.post("/api/v1/projects", json={"name": "rag-info"})
    ).json()
    try:
        r = await async_client.post(
            f"/api/v1/projects/{project['id']}/rag/info",
            json={"rag_server_url": "http://rag.local:8001"},
        )
        assert r.status_code == 200
        payload = r.json()
        assert payload["server_name"] == "test-rag"
        assert payload["corpora"][0]["id"] == "simplewiki"
        assert fake_rag.get_info_calls == ["http://rag.local:8001"]
    finally:
        await async_client.delete(f"/api/v1/projects/{project['id']}")


@pytest.mark.asyncio
async def test_rag_info_endpoint_strips_trailing_slash(
    async_client: httpx.AsyncClient, fake_rag: FakeRag
) -> None:
    project = (
        await async_client.post("/api/v1/projects", json={"name": "rag-slash"})
    ).json()
    try:
        r = await async_client.post(
            f"/api/v1/projects/{project['id']}/rag/info",
            json={"rag_server_url": "http://rag.local:8001/"},
        )
        assert r.status_code == 200
        assert fake_rag.get_info_calls == ["http://rag.local:8001"]
    finally:
        await async_client.delete(f"/api/v1/projects/{project['id']}")


@pytest.mark.asyncio
async def test_rag_info_endpoint_surfaces_connection_error_as_503(
    async_client: httpx.AsyncClient, fake_rag: FakeRag
) -> None:
    fake_rag.info_error = RagConnectionError("http://rag.local:8001", "refused")
    project = (
        await async_client.post("/api/v1/projects", json={"name": "rag-down"})
    ).json()
    try:
        r = await async_client.post(
            f"/api/v1/projects/{project['id']}/rag/info",
            json={"rag_server_url": "http://rag.local:8001"},
        )
        assert r.status_code == 503
        body = r.json()
        assert "RAG" in body["error"]
        assert body["url"] == "http://rag.local:8001"
    finally:
        await async_client.delete(f"/api/v1/projects/{project['id']}")


@pytest.mark.asyncio
async def test_create_project_with_rag_config(
    async_client: httpx.AsyncClient,
) -> None:
    body = {
        "name": "rag-enabled",
        "rag_enabled": True,
        "rag_server_url": "http://rag.local:8001/",
        "rag_corpus_id": "simplewiki",
        "rag_top_k": 7,
    }
    r = await async_client.post("/api/v1/projects", json=body)
    assert r.status_code == 201
    data = r.json()
    assert data["rag_enabled"] is True
    # Trailing slash stripped by validator
    assert data["rag_server_url"] == "http://rag.local:8001"
    assert data["rag_corpus_id"] == "simplewiki"
    assert data["rag_top_k"] == 7
    await async_client.delete(f"/api/v1/projects/{data['id']}")


@pytest.mark.asyncio
async def test_update_project_rag_fields(
    async_client: httpx.AsyncClient,
) -> None:
    r = await async_client.post("/api/v1/projects", json={"name": "rag-update"})
    pid = r.json()["id"]
    try:
        patched = (
            await async_client.patch(
                f"/api/v1/projects/{pid}",
                json={
                    "rag_enabled": True,
                    "rag_server_url": "http://rag.local:8001",
                    "rag_corpus_id": "enwiki",
                    "rag_top_k": 3,
                },
            )
        ).json()
        assert patched["rag_enabled"] is True
        assert patched["rag_corpus_id"] == "enwiki"
        assert patched["rag_top_k"] == 3
    finally:
        await async_client.delete(f"/api/v1/projects/{pid}")


@pytest.mark.asyncio
async def test_create_project_rejects_out_of_range_top_k(
    async_client: httpx.AsyncClient,
) -> None:
    body = {"name": "bad-topk", "rag_top_k": 99}
    r = await async_client.post("/api/v1/projects", json=body)
    assert r.status_code == 422
