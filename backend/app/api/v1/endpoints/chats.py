"""
API endpoints for chat management.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_chat_or_404, get_db
from app.core.logging import get_logger
from app.db.models import Chat, Message
from app.db.models.ollama_server import OllamaServer
from app.schemas.chat import (
    ChatCreate,
    ChatListResponse,
    ChatResponse,
    ChatUpdate,
    ChatWithMessagesResponse,
)

router = APIRouter()
logger = get_logger(__name__)


@router.get("", response_model=ChatListResponse)
async def list_chats(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    include_archived: bool = Query(False, description="Include archived chats"),
    project_id: str = Query(None, description="Filter by project ID (null for standalone chats)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated list of chats.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page
        include_archived: Include archived chats in results
        project_id: Filter by project ID (if None, returns standalone chats)
        db: Database session

    Returns:
        ChatListResponse: Paginated list of chats
    """
    try:
        # Build query
        query = select(Chat)
        if not include_archived:
            query = query.where(Chat.is_archived == False)

        # Filter by project_id if provided
        if project_id is not None:
            if project_id.lower() == "null" or project_id == "":
                # Return standalone chats only
                query = query.where(Chat.project_id.is_(None))
            else:
                # Return chats for specific project
                query = query.where(Chat.project_id == project_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        result = await db.execute(count_query)
        total = result.scalar() or 0

        # Get paginated results
        query = query.order_by(Chat.updated_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.options(selectinload(Chat.messages))

        result = await db.execute(query)
        chats = result.scalars().all()

        # Add message count to each chat
        chat_responses = []
        for chat in chats:
            chat_dict = {
                "id": chat.id,
                "title": chat.title,
                "model": chat.model,
                "is_archived": chat.is_archived,
                "project_id": chat.project_id,
                "ollama_server_id": chat.ollama_server_id,
                "created_at": chat.created_at,
                "updated_at": chat.updated_at,
                "message_count": len(chat.messages),
            }
            chat_responses.append(ChatResponse(**chat_dict))

        total_pages = (total + page_size - 1) // page_size

        return ChatListResponse(
            chats=chat_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"Error listing chats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving chats",
        )


@router.get("/{chat_id}", response_model=ChatWithMessagesResponse)
async def get_chat(
    chat: Chat = Depends(get_chat_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific chat with all messages.

    Args:
        chat: Chat from dependency
        db: Database session

    Returns:
        ChatWithMessagesResponse: Chat with messages
    """
    # Load messages for the chat
    query = select(Chat).where(Chat.id == chat.id).options(selectinload(Chat.messages))
    result = await db.execute(query)
    chat_with_messages = result.scalar_one()

    # Sort messages by created_at
    sorted_messages = sorted(chat_with_messages.messages, key=lambda m: m.created_at)

    return ChatWithMessagesResponse(
        id=chat_with_messages.id,
        title=chat_with_messages.title,
        model=chat_with_messages.model,
        is_archived=chat_with_messages.is_archived,
        project_id=chat_with_messages.project_id,
        created_at=chat_with_messages.created_at,
        updated_at=chat_with_messages.updated_at,
        message_count=len(sorted_messages),
        messages=sorted_messages,
    )


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_data: ChatCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new chat.

    Args:
        chat_data: Chat creation data (including optional ollama_server_id)
        db: Database session

    Returns:
        ChatResponse: Created chat

    Raises:
        HTTPException: If server ID is invalid or server not active
    """
    try:
        # Validate ollama_server_id if provided
        if chat_data.ollama_server_id:
            server_result = await db.execute(
                select(OllamaServer).where(OllamaServer.id == chat_data.ollama_server_id)
            )
            server = server_result.scalar_one_or_none()
            if not server:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ollama server with ID {chat_data.ollama_server_id} not found",
                )
            if not server.is_active:
                logger.warning(
                    f"Creating chat with inactive server '{server.name}' (ID: {server.id})"
                )

        new_chat = Chat(
            title=chat_data.title,
            model=chat_data.model,
            project_id=chat_data.project_id,
            ollama_server_id=chat_data.ollama_server_id,
        )
        db.add(new_chat)
        await db.flush()
        await db.refresh(new_chat)

        logger.info(
            f"Created chat {new_chat.id} with model '{new_chat.model}'"
            + (f" on server {new_chat.ollama_server_id}" if new_chat.ollama_server_id else "")
        )

        return ChatResponse(
            id=new_chat.id,
            title=new_chat.title,
            model=new_chat.model,
            is_archived=new_chat.is_archived,
            project_id=new_chat.project_id,
            ollama_server_id=new_chat.ollama_server_id,
            created_at=new_chat.created_at,
            updated_at=new_chat.updated_at,
            message_count=0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating chat",
        )


@router.patch("/{chat_id}", response_model=ChatResponse)
async def update_chat(
    chat_data: ChatUpdate,
    chat: Chat = Depends(get_chat_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a chat.

    Args:
        chat_data: Chat update data
        chat: Chat from dependency
        db: Database session

    Returns:
        ChatResponse: Updated chat
    """
    # Update fields
    if chat_data.title is not None:
        chat.title = chat_data.title
    if chat_data.model is not None:
        chat.model = chat_data.model
    if chat_data.is_archived is not None:
        chat.is_archived = chat_data.is_archived

    await db.flush()
    await db.refresh(chat)

    logger.info(f"Updated chat {chat.id}")

    # Get message count
    count_query = select(func.count()).where(Message.chat_id == chat.id)
    result = await db.execute(count_query)
    message_count = result.scalar() or 0

    return ChatResponse(
        id=chat.id,
        title=chat.title,
        model=chat.model,
        is_archived=chat.is_archived,
        project_id=chat.project_id,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        message_count=message_count,
    )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat: Chat = Depends(get_chat_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a chat and all its messages.

    Args:
        chat: Chat from dependency
        db: Database session
    """
    chat_id = chat.id
    await db.delete(chat)
    await db.flush()

    logger.info(f"Deleted chat {chat_id}")


@router.post("/{chat_id}/archive", response_model=ChatResponse)
async def archive_chat(
    chat: Chat = Depends(get_chat_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Archive a chat.

    Args:
        chat: Chat from dependency
        db: Database session

    Returns:
        ChatResponse: Archived chat
    """
    chat.is_archived = True
    await db.flush()
    await db.refresh(chat)

    logger.info(f"Archived chat {chat.id}")

    # Get message count
    count_query = select(func.count()).where(Message.chat_id == chat.id)
    result = await db.execute(count_query)
    message_count = result.scalar() or 0

    return ChatResponse(
        id=chat.id,
        title=chat.title,
        model=chat.model,
        is_archived=chat.is_archived,
        project_id=chat.project_id,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        message_count=message_count,
    )
