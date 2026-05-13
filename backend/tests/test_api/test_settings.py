"""
Tests for global settings + per-chat settings endpoints (Phase 8 coverage).
"""
from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.db.models import DEFAULT_USER_ID, Chat, ChatSettings, Settings
from app.db.session import AsyncSessionLocal


# ---------- Global settings ----------


@pytest.mark.asyncio
async def test_get_global_settings_returns_user_row(
    async_client: httpx.AsyncClient,
) -> None:
    r = await async_client.get("/api/v1/settings")
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == str(DEFAULT_USER_ID)
    for k in (
        "default_model",
        "conversation_summarization_model",
        "default_temperature",
        "default_max_tokens",
        "num_ctx",
    ):
        assert k in data


@pytest.mark.asyncio
async def test_patch_global_settings_updates_temperature_and_persists(
    async_client: httpx.AsyncClient,
) -> None:
    original = (await async_client.get("/api/v1/settings")).json()
    target = round(original["default_temperature"] + 0.05, 2)
    if target > 2.0:
        target = 1.0

    r = await async_client.patch(
        "/api/v1/settings", json={"default_temperature": target}
    )
    assert r.status_code == 200
    assert r.json()["default_temperature"] == target

    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(Settings).where(Settings.user_id == DEFAULT_USER_ID)
            )
        ).scalar_one()
    assert row.default_temperature == target

    # Restore so other tests don't see the drift
    await async_client.patch(
        "/api/v1/settings",
        json={"default_temperature": original["default_temperature"]},
    )


@pytest.mark.asyncio
async def test_patch_global_settings_rejects_out_of_range_temperature(
    async_client: httpx.AsyncClient,
) -> None:
    r = await async_client.patch(
        "/api/v1/settings", json={"default_temperature": 5.0}
    )
    assert r.status_code == 422


# ---------- Per-chat settings ----------


@pytest.mark.asyncio
async def test_get_chat_settings_creates_empty_row(
    async_client: httpx.AsyncClient,
) -> None:
    chat = (
        await async_client.post(
            "/api/v1/chats", json={"title": "cs", "model": "x:1b"}
        )
    ).json()
    cid = chat["id"]
    try:
        r = await async_client.get(f"/api/v1/chats/{cid}/settings")
        assert r.status_code == 200
        data = r.json()
        assert data["chat_id"] == cid
        assert data["temperature"] is None
        assert data["max_tokens"] is None
        assert data["system_prompt"] is None

        # Confirm a row exists in the DB
        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(
                    select(ChatSettings).where(ChatSettings.chat_id == cid)
                )
            ).scalar_one()
        assert str(row.chat_id) == cid
    finally:
        await async_client.delete(f"/api/v1/chats/{cid}")


@pytest.mark.asyncio
async def test_patch_chat_settings_updates_override(
    async_client: httpx.AsyncClient,
) -> None:
    chat = (
        await async_client.post(
            "/api/v1/chats", json={"title": "cs2", "model": "x:1b"}
        )
    ).json()
    cid = chat["id"]
    try:
        r = await async_client.patch(
            f"/api/v1/chats/{cid}/settings",
            json={
                "temperature": 1.2,
                "max_tokens": 512,
                "system_prompt": "be concise",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["temperature"] == 1.2
        assert data["max_tokens"] == 512
        assert data["system_prompt"] == "be concise"
    finally:
        await async_client.delete(f"/api/v1/chats/{cid}")
