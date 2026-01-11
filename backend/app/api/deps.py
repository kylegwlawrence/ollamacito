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


async def get_project_or_404(
    project_id: Annotated[UUID, Path(description="Project UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Dependency to get a project by ID or raise 404.

    Args:
        project_id: Project UUID from path
        db: Database session

    Returns:
        Project: The project object

    Raises:
        HTTPException: 404 if project not found
    """
    from app.db.models import Project

    query = select(Project).where(Project.id == project_id)
    result = await db.execute(query)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    return project
