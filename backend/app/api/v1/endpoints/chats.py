"""
API endpoints for chat management.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_chat_or_404, get_current_user, get_db
from app.core.logging import get_logger
from app.db.models import Chat, Message, Project, User
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
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    include_archived: bool = Query(False, description="Include archived chats"),
    project_id: Optional[str] = Query(
        None, description="Filter by project ID (null for standalone chats)"
    ),
):
    """Get paginated list of chats for the current user."""
    try:
        query = select(Chat).where(Chat.user_id == current_user.id)
        if not include_archived:
            query = query.where(Chat.is_archived == False)  # noqa: E712

        if project_id is not None:
            if project_id.lower() == "null" or project_id == "":
                query = query.where(Chat.project_id.is_(None))
            else:
                query = query.where(Chat.project_id == project_id)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_query)).scalar() or 0

        query = (
            query.order_by(Chat.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(selectinload(Chat.messages))
        )

        chats = (await db.execute(query)).scalars().all()

        chat_responses = [
            ChatResponse(
                id=chat.id,
                title=chat.title,
                model=chat.model,
                is_archived=chat.is_archived,
                project_id=chat.project_id,
                agent_mode_enabled=chat.agent_mode_enabled,
                created_at=chat.created_at,
                updated_at=chat.updated_at,
                message_count=len(chat.messages),
            )
            for chat in chats
        ]

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
        ) from e


@router.get("/{chat_id}", response_model=ChatWithMessagesResponse)
async def get_chat(
    chat: Annotated[Chat, Depends(get_chat_or_404)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get a specific chat with all messages (ownership enforced by dep)."""
    query = select(Chat).where(Chat.id == chat.id).options(selectinload(Chat.messages))
    chat_with_messages = (await db.execute(query)).scalar_one()

    sorted_messages = sorted(chat_with_messages.messages, key=lambda m: m.created_at)

    return ChatWithMessagesResponse(
        id=chat_with_messages.id,
        title=chat_with_messages.title,
        model=chat_with_messages.model,
        is_archived=chat_with_messages.is_archived,
        project_id=chat_with_messages.project_id,
        agent_mode_enabled=chat_with_messages.agent_mode_enabled,
        created_at=chat_with_messages.created_at,
        updated_at=chat_with_messages.updated_at,
        message_count=len(sorted_messages),
        messages=sorted_messages,
    )


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_data: ChatCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new chat owned by the current user."""
    try:
        # If a project_id is supplied, verify it belongs to the current user
        # so we don't let users attach chats to projects they don't own.
        if chat_data.project_id is not None:
            owned_project = (
                await db.execute(
                    select(Project.id).where(
                        Project.id == chat_data.project_id,
                        Project.user_id == current_user.id,
                    )
                )
            ).scalar_one_or_none()
            if owned_project is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Project {chat_data.project_id} not found",
                )

        new_chat = Chat(
            user_id=current_user.id,
            title=chat_data.title,
            model=chat_data.model,
            project_id=chat_data.project_id,
            agent_mode_enabled=chat_data.agent_mode_enabled,
        )
        db.add(new_chat)
        await db.flush()
        await db.refresh(new_chat)

        logger.info(f"Created chat {new_chat.id} for user {current_user.id}")

        return ChatResponse(
            id=new_chat.id,
            title=new_chat.title,
            model=new_chat.model,
            is_archived=new_chat.is_archived,
            project_id=new_chat.project_id,
            agent_mode_enabled=new_chat.agent_mode_enabled,
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
        ) from e


@router.patch("/{chat_id}", response_model=ChatResponse)
async def update_chat(
    chat_data: ChatUpdate,
    chat: Annotated[Chat, Depends(get_chat_or_404)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a chat (ownership enforced by dep)."""
    if chat_data.title is not None:
        chat.title = chat_data.title
    if chat_data.model is not None:
        chat.model = chat_data.model
    if chat_data.is_archived is not None:
        chat.is_archived = chat_data.is_archived
    if chat_data.agent_mode_enabled is not None:
        chat.agent_mode_enabled = chat_data.agent_mode_enabled

    await db.flush()
    await db.refresh(chat)

    logger.info(f"Updated chat {chat.id}")

    message_count = (
        await db.execute(select(func.count()).where(Message.chat_id == chat.id))
    ).scalar() or 0

    return ChatResponse(
        id=chat.id,
        title=chat.title,
        model=chat.model,
        is_archived=chat.is_archived,
        project_id=chat.project_id,
        agent_mode_enabled=chat.agent_mode_enabled,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        message_count=message_count,
    )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat: Annotated[Chat, Depends(get_chat_or_404)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a chat and all its messages (ownership enforced by dep)."""
    chat_id = chat.id
    await db.delete(chat)
    await db.flush()
    logger.info(f"Deleted chat {chat_id}")


@router.post("/{chat_id}/archive", response_model=ChatResponse)
async def archive_chat(
    chat: Annotated[Chat, Depends(get_chat_or_404)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Archive a chat (ownership enforced by dep)."""
    chat.is_archived = True
    await db.flush()
    await db.refresh(chat)

    logger.info(f"Archived chat {chat.id}")

    message_count = (
        await db.execute(select(func.count()).where(Message.chat_id == chat.id))
    ).scalar() or 0

    return ChatResponse(
        id=chat.id,
        title=chat.title,
        model=chat.model,
        is_archived=chat.is_archived,
        project_id=chat.project_id,
        agent_mode_enabled=chat.agent_mode_enabled,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        message_count=message_count,
    )
