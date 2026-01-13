"""
API endpoints for message management and streaming.
"""
import asyncio
import json
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_chat_or_404, get_db
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import Chat, ChatSettings, Message, Project, ProjectFile, Settings
from app.schemas.message import MessageCreate, MessageListResponse, MessageResponse
from app.services.ollama_service import ollama_service
from app.utils.exceptions import OllamaConnectionError

router = APIRouter()
logger = get_logger(__name__)


async def generate_and_update_title(session: AsyncSession, chat_id: UUID) -> None:
    """
    Generate title for a chat after 1st assistant response.
    Uses first user message and first assistant message as context.
    Implements retry logic: retries once on failure.

    Args:
        session: Database session
        chat_id: Chat UUID
    """
    if not settings.enable_auto_title:
        logger.debug(f"Auto-title generation disabled, skipping for chat {chat_id}")
        return

    try:
        # First, check if the chat already has a custom title (not "New Chat")
        chat_query = select(Chat).where(Chat.id == chat_id)
        result = await session.execute(chat_query)
        chat = result.scalar_one_or_none()

        if not chat:
            logger.warning(f"Chat {chat_id} not found")
            return

        # Skip title generation if chat already has a custom title
        if chat.title != "New Chat":
            logger.info(f"Chat {chat_id} already has custom title '{chat.title}', skipping generation")
            return

        logger.info(f"Starting title generation for chat {chat_id}")

        # Query first user message
        user_messages_query = (
            select(Message)
            .where(Message.chat_id == chat_id, Message.role == "user")
            .order_by(Message.created_at.asc())
            .limit(1)
        )
        result = await session.execute(user_messages_query)
        user_messages = result.scalars().all()

        # Query first assistant message
        assistant_messages_query = (
            select(Message)
            .where(Message.chat_id == chat_id, Message.role == "assistant")
            .order_by(Message.created_at.asc())
            .limit(1)
        )
        result = await session.execute(assistant_messages_query)
        assistant_messages = result.scalars().all()

        # Extract content into lists
        user_contents = [msg.content for msg in user_messages]
        assistant_contents = [msg.content for msg in assistant_messages]

        if not user_contents or not assistant_contents:
            logger.warning(f"Insufficient messages for title generation in chat {chat_id}")
            return

        # Try generating title with retry logic
        title = None
        max_attempts = 2

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Title generation attempt {attempt}/{max_attempts} for chat {chat_id}")
                title = await ollama_service.generate_chat_title(user_contents, assistant_contents)
                break  # Success, exit retry loop
            except Exception as e:
                logger.error(f"Title generation failed (attempt {attempt}/{max_attempts}): {e}")
                if attempt < max_attempts:
                    # Wait 2 seconds before retry
                    logger.info(f"Retrying title generation in 2 seconds...")
                    await asyncio.sleep(2)
                else:
                    logger.error(f"Title generation failed after {max_attempts} attempts, keeping default title")
                    return

        # Update chat title in database
        if title and title != "New Chat":
            chat.title = title
            await session.flush()
            logger.info(f"Updated chat {chat_id} title to: '{title}'")
        else:
            logger.warning(f"Invalid title generated for chat {chat_id}, keeping default")

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
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message and stream the Ollama response in real-time.

    For project chats, all project files are automatically included as context.

    Args:
        chat_id: Chat UUID
        message: User message content
        db: Database session

    Returns:
        StreamingResponse: Server-sent events stream

    Raises:
        HTTPException: If chat not found or Ollama error
    """
    import uuid as uuid_lib
    request_id = str(uuid_lib.uuid4())[:8]  # Short request ID for tracking
    logger.info(f"[Req {request_id}] Stream endpoint called for chat {chat_id}, message: '{message[:50]}...'")

    async def event_generator():
        session: AsyncSession = None
        try:
            logger.info(f"[Req {request_id}] Starting event generator")
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

            # Get chat settings for temperature and max_tokens
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

            # Automatically load ALL project files for project chats and add to system prompt
            if chat.project_id:
                logger.info(f"[Req {request_id}] Chat {chat_id} belongs to project {chat.project_id}, loading project files")
                # Load all files from the project with explicit content loading
                files_query = select(ProjectFile).where(
                    ProjectFile.project_id == chat.project_id
                ).order_by(ProjectFile.created_at.asc())

                # Execute query and materialize results immediately
                result = await session.execute(files_query)
                files = list(result.scalars().all())

                logger.info(f"Loaded {len(files)} files from database for project {chat.project_id}")

                if files:
                    logger.info(f"Auto-attaching {len(files)} project file(s) to chat {chat_id}")

                    # Add all file contents to the system prompt
                    # Access all file attributes now while session is active
                    file_context_parts = []
                    total_file_chars = 0
                    for file in files:
                        # Access all attributes immediately to avoid lazy loading issues
                        filename = str(file.filename)
                        file_type = str(file.file_type)
                        file_content = str(file.content) if file.content is not None else ""
                        total_file_chars += len(file_content)
                        logger.info(
                            f"Including file {filename} ({file_type}, {len(file_content)} chars) "
                            f"as context for chat {chat_id}"
                        )
                        file_context_parts.append(f"[File: {filename}]\n{file_content}\n[End of File]")

                    # Add file context to system prompt
                    system_prompt_parts.append("Project Files:")
                    system_prompt_parts.append("\n\n".join(file_context_parts))
                    system_prompt_parts.append("")  # Empty line for spacing

                    logger.info(
                        f"Total context size: {total_file_chars} chars from {len(files)} files added to system prompt"
                    )
                else:
                    logger.info(f"No files found in project {chat.project_id} for chat {chat_id}")

            # Insert combined system prompt if we have any content
            if system_prompt_parts:
                combined_prompt = "\n".join(system_prompt_parts)
                ollama_messages.insert(0, {"role": "system", "content": combined_prompt})

                # Log the complete system prompt
                logger.info("=" * 80)
                logger.info("SYSTEM PROMPT:")
                logger.info("=" * 80)
                logger.info(combined_prompt)
                logger.info("=" * 80)

            # Add new user message (original message without file contents)
            ollama_messages.append({"role": "user", "content": message})

            # Log the full message content being sent to Ollama for debugging
            logger.info(
                f"Sending to Ollama - Chat {chat_id}, User message length: {len(message)} chars, "
                f"Number of messages in history: {len(ollama_messages)}"
            )

            # Debug: Log all messages being sent to Ollama
            logger.info("=" * 80)
            logger.info("MESSAGES BEING SENT TO OLLAMA:")
            logger.info("=" * 80)
            for idx, msg in enumerate(ollama_messages):
                logger.info(f"Message {idx + 1} - Role: {msg['role']}")
                content = msg['content']
                if len(content) > 1000:
                    logger.info(f"Content (first 500 chars): {content[:500]}")
                    logger.info(f"... [{len(content) - 1000} chars omitted] ...")
                    logger.info(f"Content (last 500 chars): {content[-500:]}")
                else:
                    logger.info(f"Content: {content}")
                logger.info("-" * 80)
            logger.info("=" * 80)

            # Save user message to database
            user_message = Message(
                chat_id=chat_id,
                role="user",
                content=message,  # Store original message without file contents
            )
            session.add(user_message)
            await session.flush()

            # Note: We don't need to associate files with the message in the database
            # since all project files are automatically included as context.
            # The message_files relationship is kept for potential future use
            # (e.g., selective file attachment or file change tracking).

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

            # Check if this is the 1st assistant response and trigger title generation
            message_count_query = select(func.count()).where(
                Message.chat_id == chat_id,
                Message.role == "assistant"
            )
            result = await session.execute(message_count_query)
            assistant_count = result.scalar() or 0

            if assistant_count == 1:
                logger.info(f"First assistant response completed for chat {chat_id}, triggering title generation")
                await generate_and_update_title(session, chat_id)
                await session.commit()  # Commit title update

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
