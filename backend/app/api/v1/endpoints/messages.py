"""
API endpoints for message management and streaming.
"""
import asyncio
import json
import uuid as uuid_lib
from contextlib import aclosing
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_chat_or_404, get_current_user, get_db
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Chat, ChatSettings, Message, Project, ProjectFile, Settings, User
from app.db.session import AsyncSessionLocal
from app.schemas.message import (
    MessageCreate,
    MessageListResponse,
    MessageResponse,
    StreamMessageRequest,
)
from app.services.ollama_service import ollama_service
from app.utils.exceptions import OllamaConnectionError

router = APIRouter()
logger = get_logger(__name__)


# Hardcoded fallbacks used when no settings row exists yet.
_FALLBACK_TEMPERATURE = 0.7
_FALLBACK_MAX_TOKENS = 2048
_FALLBACK_NUM_CTX = 2048


@dataclass
class _Cascade:
    """Resolved generation parameters for a single stream invocation."""

    temperature: float
    max_tokens: int
    num_ctx: int
    title_model: Optional[str]


async def _load_cascade(session: AsyncSession, chat: Chat) -> _Cascade:
    """
    Resolve temperature, max_tokens, num_ctx from chat → project → global → defaults.
    Global settings are keyed by the chat's owning user. Also returns the
    title-generation model from the Settings row when present.
    """
    global_settings = (
        await session.execute(
            select(Settings).where(Settings.user_id == chat.user_id)
        )
    ).scalar_one_or_none()

    chat_settings = (
        await session.execute(
            select(ChatSettings).where(ChatSettings.chat_id == chat.id)
        )
    ).scalar_one_or_none()

    project: Optional[Project] = None
    if chat.project_id:
        project = (
            await session.execute(select(Project).where(Project.id == chat.project_id))
        ).scalar_one_or_none()

    # temperature cascade
    if chat_settings and chat_settings.temperature is not None:
        temperature = chat_settings.temperature
    elif project and project.temperature is not None:
        temperature = project.temperature
    elif global_settings:
        temperature = global_settings.default_temperature
    else:
        temperature = _FALLBACK_TEMPERATURE

    # max_tokens cascade (Ollama num_predict — max tokens to generate)
    if chat_settings and chat_settings.max_tokens is not None:
        max_tokens = chat_settings.max_tokens
    elif project and project.max_tokens is not None:
        max_tokens = project.max_tokens
    elif global_settings:
        max_tokens = global_settings.default_max_tokens
    else:
        max_tokens = _FALLBACK_MAX_TOKENS

    # num_ctx cascade (Ollama context window). Not yet overridable per-chat/per-project;
    # only the global setting and a hardcoded fallback apply.
    if global_settings:
        num_ctx = global_settings.num_ctx
    else:
        num_ctx = _FALLBACK_NUM_CTX

    title_model = global_settings.conversation_summarization_model if global_settings else None

    return _Cascade(
        temperature=temperature,
        max_tokens=max_tokens,
        num_ctx=num_ctx,
        title_model=title_model,
    )


async def _build_ollama_messages(
    session: AsyncSession,
    chat: Chat,
    user_message_content: str,
    attached_files: List[ProjectFile],
) -> List[Dict[str, str]]:
    """
    Build the message list for Ollama: system prompt (project custom
    instructions + ONLY the explicitly-attached project files) + chat
    history + the new user message.

    `attached_files` is the pre-resolved, pre-ownership-checked set of
    project files the user selected for this turn. The caller is
    responsible for verifying that each file belongs to the chat's
    project (see `_resolve_attached_files`).
    """
    # Load chat history
    history_query = (
        select(Message)
        .where(Message.chat_id == chat.id)
        .order_by(Message.created_at.asc())
    )
    history = (await session.execute(history_query)).scalars().all()
    ollama_messages: List[Dict[str, str]] = [
        {"role": msg.role, "content": msg.content} for msg in history
    ]

    # Build system prompt
    system_prompt_parts: List[str] = []

    if chat.project_id:
        project = (
            await session.execute(select(Project).where(Project.id == chat.project_id))
        ).scalar_one_or_none()
        if project and project.custom_instructions:
            system_prompt_parts.append("Project Context:")
            system_prompt_parts.append(project.custom_instructions)
            system_prompt_parts.append("")

    if attached_files:
        file_context_parts = []
        for file in attached_files:
            filename = str(file.filename)
            file_content = str(file.content) if file.content is not None else ""
            file_context_parts.append(
                f"[File: {filename}]\n{file_content}\n[End of File]"
            )
        system_prompt_parts.append("Project Files:")
        system_prompt_parts.append("\n\n".join(file_context_parts))
        system_prompt_parts.append("")

    if system_prompt_parts:
        ollama_messages.insert(
            0, {"role": "system", "content": "\n".join(system_prompt_parts)}
        )

    ollama_messages.append({"role": "user", "content": user_message_content})
    return ollama_messages


async def _resolve_attached_files(
    session: AsyncSession, chat: Chat, file_ids: Optional[List[UUID]]
) -> List[ProjectFile]:
    """
    Resolve the user's requested file_ids to ProjectFile rows.

    Phase 6: no automatic fallback to all project files — the request is
    the source of truth. Empty/None means no files. Cross-project IDs are
    silently dropped (filtered by `ProjectFile.project_id == chat.project_id`)
    so a request can't pull files from a project the chat doesn't belong to.
    """
    if not file_ids or chat.project_id is None:
        return []
    query = (
        select(ProjectFile)
        .where(
            ProjectFile.id.in_(file_ids),
            ProjectFile.project_id == chat.project_id,
        )
        .order_by(ProjectFile.created_at.asc())
    )
    return list((await session.execute(query)).scalars().all())


async def generate_and_update_title(chat_id: UUID, title_model: Optional[str]) -> None:
    """
    Generate a chat title from the first user/assistant exchange.

    Designed to be fired with `asyncio.create_task` after the stream completes —
    so it opens its own session and never touches the request-scoped session.
    Implements retry logic: retries once on failure.
    """
    if not settings.enable_auto_title:
        logger.debug(f"Auto-title generation disabled, skipping for chat {chat_id}")
        return

    try:
        async with AsyncSessionLocal() as session:
            chat = (
                await session.execute(select(Chat).where(Chat.id == chat_id))
            ).scalar_one_or_none()

            if not chat:
                logger.warning(f"Title-gen: chat {chat_id} not found")
                return

            if chat.title != "New Chat":
                logger.info(
                    f"Title-gen: chat {chat_id} already has custom title "
                    f"'{chat.title}', skipping"
                )
                return

            logger.info(f"Starting title generation for chat {chat_id}")

            user_messages = (
                (
                    await session.execute(
                        select(Message)
                        .where(Message.chat_id == chat_id, Message.role == "user")
                        .order_by(Message.created_at.asc())
                        .limit(1)
                    )
                )
                .scalars()
                .all()
            )
            assistant_messages = (
                (
                    await session.execute(
                        select(Message)
                        .where(Message.chat_id == chat_id, Message.role == "assistant")
                        .order_by(Message.created_at.asc())
                        .limit(1)
                    )
                )
                .scalars()
                .all()
            )

            user_contents = [m.content for m in user_messages]
            assistant_contents = [m.content for m in assistant_messages]

            if not user_contents or not assistant_contents:
                logger.warning(
                    f"Title-gen: insufficient messages in chat {chat_id}"
                )
                return

            title: Optional[str] = None
            max_attempts = 2
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.info(
                        f"Title generation attempt {attempt}/{max_attempts} for chat {chat_id}"
                    )
                    title = await ollama_service.generate_chat_title(
                        user_contents,
                        assistant_contents,
                        model=title_model,
                    )
                    break
                except Exception as e:
                    logger.error(
                        f"Title generation failed (attempt {attempt}/{max_attempts}): {e}"
                    )
                    if attempt < max_attempts:
                        await asyncio.sleep(2)
                    else:
                        logger.error(
                            f"Title generation gave up after {max_attempts} attempts; "
                            f"keeping default title"
                        )
                        return

            if title and title != "New Chat":
                chat.title = title
                await session.commit()
                logger.info(f"Updated chat {chat_id} title to: '{title}'")
            else:
                logger.warning(
                    f"Title-gen: invalid title for chat {chat_id}; keeping default"
                )
    except Exception as e:
        logger.error(f"Unexpected error in generate_and_update_title for chat {chat_id}: {e}")


@router.get("/{chat_id}/messages", response_model=MessageListResponse)
async def list_messages(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    chat: Chat = Depends(get_chat_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated list of messages for a chat.
    """
    count_query = select(func.count()).where(Message.chat_id == chat.id)
    total = (await db.execute(count_query)).scalar() or 0

    query = (
        select(Message)
        .where(Message.chat_id == chat.id)
        .order_by(Message.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    messages = (await db.execute(query)).scalars().all()

    total_pages = (total + page_size - 1) // page_size

    return MessageListResponse(
        messages=[MessageResponse.model_validate(m) for m in messages],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/{chat_id}/messages", response_model=MessageResponse)
async def create_message(
    message_data: MessageCreate,
    chat: Chat = Depends(get_chat_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new user message (does not trigger Ollama response).
    Use the /stream endpoint for interactive chat.
    """
    new_message = Message(
        chat_id=chat.id,
        role="user",
        content=message_data.content,
    )
    db.add(new_message)
    await db.flush()
    await db.refresh(new_message)

    logger.info(f"Created message in chat {chat.id}")

    return MessageResponse.model_validate(new_message)


async def _prepare_stream(
    chat_id: UUID,
    user_id: UUID,
    user_message: str,
    file_ids: Optional[List[UUID]],
) -> Tuple[Optional[Chat], Optional[_Cascade], Optional[List[Dict[str, str]]], Optional[str]]:
    """
    Open a setup session, load cascade + history, resolve attached files,
    persist the user message (and message_files junction rows) in one
    transaction.

    The user-message commit lives in its own transaction so it survives any
    later Ollama stream failure. Returns (None, ...) when the chat does not
    exist or does not belong to the requesting user.
    """
    async with AsyncSessionLocal() as session:
        chat = (
            await session.execute(
                select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
            )
        ).scalar_one_or_none()
        if not chat:
            return None, None, None, None

        cascade = await _load_cascade(session, chat)
        attached_files = await _resolve_attached_files(session, chat, file_ids)
        ollama_messages = await _build_ollama_messages(
            session, chat, user_message, attached_files
        )

        new_user_message = Message(
            chat_id=chat_id,
            role="user",
            content=user_message,
            attached_files=attached_files,  # populates message_files junction
        )
        session.add(new_user_message)
        await session.commit()

        model_name = chat.model

    return chat, cascade, ollama_messages, model_name


async def _persist_assistant_message(
    chat_id: UUID, content: str, truncated: bool
) -> int:
    """
    Save the assistant message in its own transaction and return the post-save
    assistant message count for the chat (used to gate title generation).
    """
    async with AsyncSessionLocal() as session:
        assistant_message = Message(
            chat_id=chat_id,
            role="assistant",
            content=content,
            truncated=truncated,
        )
        session.add(assistant_message)
        await session.commit()

        count = (
            await session.execute(
                select(func.count()).where(
                    Message.chat_id == chat_id, Message.role == "assistant"
                )
            )
        ).scalar() or 0
        return count


@router.post("/{chat_id}/stream")
async def stream_chat_response(
    chat_id: UUID,
    body: StreamMessageRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Send a message and stream the Ollama response in real-time.

    Transport (Phase 4): POST with a JSON body, response is NDJSON — one JSON
    object per line. Frame types:

    - `{"type": "chunk", "content": "..."}` — a token-or-fragment from Ollama
    - `{"type": "done", "truncated": false}` — successful end of stream
    - `{"type": "error", "message": "..."}` — terminal error; no more frames

    Correctness guarantees:
    - The user message is committed in its own transaction before invoking
      Ollama, so it survives any later stream failure.
    - On client disconnect or Ollama error, the partial assistant message is
      persisted with `truncated=True` and surfaced in the `done` frame.
    - Title generation runs as an asyncio task with its own session, so the
      `done` frame is not blocked.

    `body.file_ids` selects which project files to include in the system
    prompt for this turn (Phase 6). Empty/None = no files. Cross-project
    IDs are silently dropped. Selections are persisted to the
    `message_files` junction so the UI can show which files were attached
    to past messages.
    """
    request_id = str(uuid_lib.uuid4())[:8]
    logger.info(
        f"[Req {request_id}] Stream endpoint called for chat {chat_id}, "
        f"message: '{body.content[:50]}...'"
    )

    chat, cascade, ollama_messages, model_name = await _prepare_stream(
        chat_id, current_user.id, body.content, body.file_ids
    )

    async def event_generator() -> AsyncGenerator[bytes, None]:
        if chat is None or cascade is None or ollama_messages is None or model_name is None:
            yield _ndjson({"type": "error", "message": f"Chat {chat_id} not found"})
            return

        full_response = ""
        client_disconnected = False
        stream_error: Optional[str] = None

        try:
            async with aclosing(
                ollama_service.stream_chat(
                    model=model_name,
                    messages=ollama_messages,
                    temperature=cascade.temperature,
                    max_tokens=cascade.max_tokens,
                    num_ctx=cascade.num_ctx,
                )
            ) as stream:
                async for chunk in stream:
                    if await request.is_disconnected():
                        client_disconnected = True
                        logger.info(
                            f"[Req {request_id}] Client disconnected mid-stream; "
                            f"breaking out of generator"
                        )
                        break

                    full_response += chunk
                    yield _ndjson({"type": "chunk", "content": chunk})

        except OllamaConnectionError as e:
            logger.error(f"[Req {request_id}] Ollama connection error: {e}")
            stream_error = (
                "Unable to connect to Ollama. Please ensure Ollama is running."
            )
        except Exception as e:
            logger.error(f"[Req {request_id}] Streaming error: {e}")
            stream_error = f"Internal server error: {e}"

        # Persist whatever the assistant produced, marking truncated when the
        # stream did not complete cleanly. Use a fresh session — the setup
        # session is already closed and the request-scoped one would close
        # before the streaming response finishes.
        is_truncated = client_disconnected or stream_error is not None
        assistant_count = 0
        try:
            if full_response:
                assistant_count = await _persist_assistant_message(
                    chat_id, full_response, is_truncated
                )
                logger.info(
                    f"[Req {request_id}] Persisted assistant message "
                    f"(truncated={is_truncated})"
                )
        except Exception as e:
            logger.error(
                f"[Req {request_id}] Failed to persist assistant message: {e}"
            )

        # Emit final frame. Errors are terminal; success carries the truncated
        # flag so the FE can render a "regenerate" affordance on partial responses.
        if stream_error is not None:
            yield _ndjson({"type": "error", "message": stream_error})
        else:
            yield _ndjson({"type": "done", "truncated": is_truncated})

        # First successful assistant turn → kick off title generation in the
        # background so it never blocks the `done` frame above.
        if assistant_count == 1 and not is_truncated:
            asyncio.create_task(
                generate_and_update_title(chat_id, cascade.title_model)
            )

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _ndjson(payload: dict) -> bytes:
    """Encode one NDJSON line (single JSON object + newline)."""
    return (json.dumps(payload) + "\n").encode("utf-8")
