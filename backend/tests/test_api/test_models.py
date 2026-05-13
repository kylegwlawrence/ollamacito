"""
Tests for the Ollama models + status endpoints (Phase 8 coverage).

These endpoints call out to the host's Ollama service, so we monkeypatch
the singleton's get_models / check_health methods rather than the
class itself — that matches how the endpoint resolves the dependency.
"""
from __future__ import annotations

from typing import List

import httpx
import pytest

from app.services import ollama_service as ollama_module
from app.utils.exceptions import OllamaConnectionError


@pytest.fixture
def stub_ollama_models(monkeypatch: pytest.MonkeyPatch):
    """Stub get_models + check_health on the real singleton."""
    state: dict = {
        "models": [{"name": "mistral:7b"}, {"name": "qwen2.5:3b"}],
        "health_ok": True,
    }

    async def fake_get_models() -> List[dict]:
        if not state["health_ok"]:
            raise OllamaConnectionError("http://test:11434", "down")
        return state["models"]

    async def fake_check_health() -> bool:
        if not state["health_ok"]:
            raise OllamaConnectionError("http://test:11434", "down")
        return True

    real = ollama_module.ollama_service
    monkeypatch.setattr(real, "get_models", fake_get_models)
    monkeypatch.setattr(real, "check_health", fake_check_health)
    return state


@pytest.mark.asyncio
async def test_list_ollama_models_returns_models(
    async_client: httpx.AsyncClient, stub_ollama_models: dict
) -> None:
    r = await async_client.get("/api/v1/ollama/models")
    assert r.status_code == 200
    data = r.json()
    names = {m["name"] for m in data["models"]}
    assert names == {"mistral:7b", "qwen2.5:3b"}


@pytest.mark.asyncio
async def test_list_ollama_models_503_when_ollama_down(
    async_client: httpx.AsyncClient, stub_ollama_models: dict
) -> None:
    stub_ollama_models["health_ok"] = False
    r = await async_client.get("/api/v1/ollama/models")
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_status_endpoint_reports_connected(
    async_client: httpx.AsyncClient, stub_ollama_models: dict
) -> None:
    r = await async_client.get("/api/v1/ollama/status")
    assert r.status_code == 200
    data = r.json()
    assert data["connected"] is True
    assert data["models_count"] == 2


@pytest.mark.asyncio
async def test_status_endpoint_reports_disconnected_without_raising(
    async_client: httpx.AsyncClient, stub_ollama_models: dict
) -> None:
    """Unlike /models, /status swallows the connection error and reports it."""
    stub_ollama_models["health_ok"] = False
    r = await async_client.get("/api/v1/ollama/status")
    assert r.status_code == 200
    data = r.json()
    assert data["connected"] is False
    assert data["error"]
