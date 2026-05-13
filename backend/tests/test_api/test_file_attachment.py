"""
Selective per-message file attachment tests (PLAN_NEW.md Phase 6).

Verifies the POST stream endpoint behavior around `body.file_ids`:
- Empty/None file_ids -> no project files in the prompt, even if the chat
  belongs to a project that has files.
- Specific file_ids -> only those files appear in the system prompt and
  the message_files junction is populated.
- Cross-project file_ids -> silently dropped (no ownership leak).
"""
from __future__ import annotations

from typing import AsyncGenerator
import json
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.db.models import (
    DEFAULT_USER_ID,
    Chat,
    Message,
    Project,
    ProjectFile,
)
from app.db.session import AsyncSessionLocal

from tests.conftest import FakeOllama


@pytest_asyncio.fixture
async def project_with_files() -> AsyncGenerator[dict, None]:
    """Create a project with two files and a chat inside it for the default user."""
    project_id = uuid4()
    file_a_id = uuid4()
    file_b_id = uuid4()
    chat_id = uuid4()

    async with AsyncSessionLocal() as session:
        session.add(
            Project(
                id=project_id,
                user_id=DEFAULT_USER_ID,
                name="Phase6 Project",
            )
        )
        session.add(
            ProjectFile(
                id=file_a_id,
                project_id=project_id,
                filename="alpha.txt",
                file_path=f"project_{project_id}/alpha.txt",
                file_type="txt",
                file_size=11,
                content="ALPHA-CONTENT",
            )
        )
        session.add(
            ProjectFile(
                id=file_b_id,
                project_id=project_id,
                filename="beta.txt",
                file_path=f"project_{project_id}/beta.txt",
                file_type="txt",
                file_size=10,
                content="BETA-CONTENT",
            )
        )
        session.add(
            Chat(
                id=chat_id,
                user_id=DEFAULT_USER_ID,
                project_id=project_id,
                title="New Chat",
                model="test-model:1b",
            )
        )
        await session.commit()

    try:
        yield {
            "project_id": project_id,
            "chat_id": chat_id,
            "file_a_id": file_a_id,
            "file_b_id": file_b_id,
        }
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Chat).where(Chat.id == chat_id))
            await session.execute(delete(Project).where(Project.id == project_id))
            await session.commit()


async def _post_stream(
    async_client: httpx.AsyncClient, chat_id, message: str, file_ids
) -> None:
    """Consume the stream body, discarding frames (we only care about side effects)."""
    async with async_client.stream(
        "POST",
        f"/api/v1/chats/{chat_id}/stream",
        json={"content": message, "file_ids": file_ids},
    ) as response:
        assert response.status_code == 200, response.status_code
        body = b""
        async for chunk in response.aiter_bytes():
            body += chunk
        # NDJSON: ensure we got at least one frame
        assert body.strip(), "expected non-empty stream body"


def _system_prompt_from_fake(fake_ollama: FakeOllama) -> str:
    """Pull the system message that was handed to ollama_service.stream_chat."""
    assert len(fake_ollama.stream_calls) == 1
    messages = fake_ollama.stream_calls[0]["messages"]
    system_msgs = [m for m in messages if m["role"] == "system"]
    return system_msgs[0]["content"] if system_msgs else ""


@pytest.mark.asyncio
async def test_no_file_ids_means_no_files_attached(
    async_client: httpx.AsyncClient,
    fake_ollama: FakeOllama,
    project_with_files: dict,
) -> None:
    """file_ids=None -> the project's files do NOT appear in the system prompt."""
    fake_ollama.chunks = ["ok"]
    await _post_stream(async_client, project_with_files["chat_id"], "hi", None)

    system_prompt = _system_prompt_from_fake(fake_ollama)
    assert "ALPHA-CONTENT" not in system_prompt
    assert "BETA-CONTENT" not in system_prompt


@pytest.mark.asyncio
async def test_specific_file_ids_attach_only_those_files(
    async_client: httpx.AsyncClient,
    fake_ollama: FakeOllama,
    project_with_files: dict,
) -> None:
    """file_ids=[fileA] -> only fileA appears; message_files records the link."""
    fake_ollama.chunks = ["ok"]
    file_a_id = project_with_files["file_a_id"]
    await _post_stream(
        async_client,
        project_with_files["chat_id"],
        "summarize alpha",
        [str(file_a_id)],
    )

    system_prompt = _system_prompt_from_fake(fake_ollama)
    assert "ALPHA-CONTENT" in system_prompt
    assert "BETA-CONTENT" not in system_prompt

    # message_files junction should hold the link
    async with AsyncSessionLocal() as session:
        user_msg = (
            (
                await session.execute(
                    select(Message)
                    .where(
                        Message.chat_id == project_with_files["chat_id"],
                        Message.role == "user",
                    )
                    .options(selectinload(Message.attached_files))
                )
            )
            .scalars()
            .first()
        )
    assert user_msg is not None
    attached_ids = {f.id for f in user_msg.attached_files}
    assert attached_ids == {file_a_id}


@pytest.mark.asyncio
async def test_cross_project_file_ids_are_dropped(
    async_client: httpx.AsyncClient,
    fake_ollama: FakeOllama,
    project_with_files: dict,
) -> None:
    """A file_id from a different project is silently dropped (no leak)."""
    other_project_id = uuid4()
    other_file_id = uuid4()
    async with AsyncSessionLocal() as session:
        session.add(
            Project(id=other_project_id, user_id=DEFAULT_USER_ID, name="Other")
        )
        session.add(
            ProjectFile(
                id=other_file_id,
                project_id=other_project_id,
                filename="leak.txt",
                file_path=f"project_{other_project_id}/leak.txt",
                file_type="txt",
                file_size=12,
                content="LEAK-CONTENT",
            )
        )
        await session.commit()

    try:
        fake_ollama.chunks = ["ok"]
        await _post_stream(
            async_client,
            project_with_files["chat_id"],
            "try to leak",
            [str(other_file_id), str(project_with_files["file_a_id"])],
        )

        system_prompt = _system_prompt_from_fake(fake_ollama)
        assert "LEAK-CONTENT" not in system_prompt
        # The legitimate file from the chat's own project still goes through
        assert "ALPHA-CONTENT" in system_prompt
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(Project).where(Project.id == other_project_id)
            )
            await session.commit()
