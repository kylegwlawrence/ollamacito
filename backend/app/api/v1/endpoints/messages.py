"""
API endpoints for message management and streaming.
"""
import json
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_chat_or_404, get_db
from app.core.logging import get_logger
from app.db.models import Chat, ChatSettings, Message, Project, ProjectFile, Settings
from app.schemas.message import MessageCreate, MessageListResponse, MessageResponse
from app.services.ollama_service import ollama_service
from app.utils.exceptions import OllamaConnectionError

router = APIRouter()
logger = get_logger(__name__)


@router.get("/{chat_id}/messages", response_model=MessageListResponse)
async def list_messages(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    chat: Chat = Depends(get_chat_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated list of messages for a chat.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page
        chat: Chat from dependency
        db: Database session

    Returns:
        MessageListResponse: Paginated list of messages
    """
    # Get total count
    count_query = select(func.count()).where(Message.chat_id == chat.id)
    result = await db.execute(count_query)
    total = result.scalar() or 0

    # Get paginated messages
    query = (
        select(Message)
        .where(Message.chat_id == chat.id)
        .order_by(Message.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    messages = result.scalars().all()

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

    Args:
        message_data: Message creation data
        chat: Chat from dependency
        db: Database session

    Returns:
        MessageResponse: Created message
    """
    # Create user message
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


@router.get("/{chat_id}/stream")
async def stream_chat_response(
    chat_id: UUID,
    message: str = Query(..., min_length=1, max_length=32000, description="User message"),
    file_ids: List[UUID] = Query(default=[], description="List of project file IDs to attach"),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message and stream the Ollama response in real-time.

    Args:
        chat_id: Chat UUID
        message: User message content
        file_ids: List of project file IDs to attach
        db: Database session

    Returns:
        StreamingResponse: Server-sent events stream

    Raises:
        HTTPException: If chat not found or Ollama error
    """

    async def event_generator():
        session: AsyncSession = None
        try:
            # Create new session for streaming
            from app.db.session import AsyncSessionLocal

            session = AsyncSessionLocal()

            # Get chat and verify it exists
            chat_query = select(Chat).where(Chat.id == chat_id)
            result = await session.execute(chat_query)
            chat = result.scalar_one_or_none()

            if not chat:
                error_data = json.dumps({"error": f"Chat {chat_id} not found"})
                yield f"data: {error_data}\n\n"
                return

            # Get global settings
            settings_query = select(Settings).where(Settings.id == 1)
            result = await session.execute(settings_query)
            global_settings = result.scalar_one_or_none()

            # Get chat settings
            chat_settings_query = select(ChatSettings).where(
                ChatSettings.chat_id == chat_id
            )
            result = await session.execute(chat_settings_query)
            chat_settings = result.scalar_one_or_none()

            # Get project settings if chat belongs to a project (query executed later for custom_instructions)
            project = None
            if chat.project_id:
                project_query = select(Project).where(Project.id == chat.project_id)
                result = await session.execute(project_query)
                project = result.scalar_one_or_none()

            # Determine temperature: chat → project → global → hardcoded default
            temperature = None
            if chat_settings and chat_settings.temperature is not None:
                temperature = chat_settings.temperature
            elif project and project.temperature is not None:
                temperature = project.temperature
            elif global_settings:
                temperature = global_settings.default_temperature
            else:
                temperature = 0.7

            # Determine max_tokens: chat → project → global → hardcoded default
            max_tokens = None
            if chat_settings and chat_settings.max_tokens is not None:
                max_tokens = chat_settings.max_tokens
            elif project and project.max_tokens is not None:
                max_tokens = project.max_tokens
            elif global_settings:
                max_tokens = global_settings.default_max_tokens
            else:
                max_tokens = 2048

            # Get chat history
            messages_query = (
                select(Message)
                .where(Message.chat_id == chat_id)
                .order_by(Message.created_at.asc())
            )
            result = await session.execute(messages_query)
            history = result.scalars().all()

            # Build message history for Ollama
            ollama_messages = [
                {"role": msg.role, "content": msg.content} for msg in history
            ]

            # Build system prompt with project context
            system_prompt_parts = []

            # Add project context if project exists and has custom instructions
            if project and project.custom_instructions:
                system_prompt_parts.append("Project Context:")
                system_prompt_parts.append(project.custom_instructions)
                system_prompt_parts.append("")  # Empty line for spacing

            # Add chat-specific system prompt if exists
            if chat_settings and chat_settings.system_prompt:
                system_prompt_parts.append(chat_settings.system_prompt)

            # Insert combined system prompt if we have any content
            if system_prompt_parts:
                combined_prompt = "\n".join(system_prompt_parts)
                ollama_messages.insert(0, {"role": "system", "content": combined_prompt})

            # Build message content with file attachments
            message_content = message
            attached_files = []

            # Load and append file contents if file_ids provided
            if file_ids:
                files_query = select(ProjectFile).where(ProjectFile.id.in_(file_ids))
                result = await session.execute(files_query)
                files = result.scalars().all()

                for file in files:
                    attached_files.append(file)
                    # Append file content to message
                    message_content += f"\n\n[File: {file.filename}]\n{file.content}\n[End of File]"

            # Add new user message with file contents
            ollama_messages.append({"role": "user", "content": message_content})

            # Save user message to database
            user_message = Message(
                chat_id=chat_id,
                role="user",
                content=message,  # Store original message without file contents
            )
            session.add(user_message)
            await session.flush()

            # Associate files with the message
            if attached_files:
                for file in attached_files:
                    user_message.attached_files.append(file)
                await session.flush()

            logger.info(f"Starting stream for chat {chat_id}")

            # Stream response from Ollama
            full_response = ""
            async for chunk in ollama_service.stream_chat(
                model=chat.model,
                messages=ollama_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                full_response += chunk
                chunk_data = json.dumps({"content": chunk, "done": False})
                yield f"data: {chunk_data}\n\n"

            # Save assistant message to database
            assistant_message = Message(
                chat_id=chat_id,
                role="assistant",
                content=full_response,
            )
            session.add(assistant_message)
            await session.commit()

            logger.info(f"Completed stream for chat {chat_id}")

            # Send completion signal
            done_data = json.dumps({"content": "", "done": True})
            yield f"data: {done_data}\n\n"

        except OllamaConnectionError as e:
            logger.error(f"Ollama connection error: {e}")
            error_data = json.dumps(
                {
                    "error": "Unable to connect to Ollama",
                    "detail": "Please ensure Ollama is running",
                }
            )
            yield f"data: {error_data}\n\n"
        except Exception as e:
            logger.error(f"Error in stream: {e}")
            error_data = json.dumps({"error": "Internal server error", "detail": str(e)})
            yield f"data: {error_data}\n\n"
        finally:
            if session:
                await session.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
