"""
FastAPI dependency injection functions.
"""
from typing import Annotated, AsyncGenerator
from uuid import UUID

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get database session.

    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_chat_or_404(
    chat_id: Annotated[UUID, Path(description="Chat UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Dependency to get a chat by ID or raise 404.

    Args:
        chat_id: Chat UUID from path
        db: Database session

    Returns:
        Chat: The chat object

    Raises:
        HTTPException: 404 if chat not found
    """
    from app.db.models import Chat

    query = select(Chat).where(Chat.id == chat_id)
    result = await db.execute(query)
    chat = result.scalar_one_or_none()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat {chat_id} not found",
        )

    return chat
