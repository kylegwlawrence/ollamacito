"""
FastAPI dependency injection functions.
"""

from typing import Annotated, AsyncGenerator
from uuid import UUID

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.db.models import DEFAULT_USER_ID, Chat, Project, User
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


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Resolve the user for the current request.

    With ``AUTH_ENABLED=false`` (default until Phase 7) every request maps
    to the seeded default user (``DEFAULT_USER_ID``). All downstream queries
    filter by ``user_id``, so single-user behavior is preserved while the
    multi-user data model is exercised.

    With ``AUTH_ENABLED=true`` this will validate a JWT cookie. Phase 7
    lands that wiring; until then we raise so a stray flag flip surfaces
    immediately instead of silently giving an unauthenticated request the
    default user's data.
    """
    if app_settings.auth_enabled:
        raise NotImplementedError(
            "AUTH_ENABLED=true requires Phase 7 (real auth). Set AUTH_ENABLED=false."
        )

    user = (
        await db.execute(select(User).where(User.id == DEFAULT_USER_ID))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Default user not seeded. Ensure migrations + lifespan seed "
                "have run; see PLAN_NEW.md Phase 3."
            ),
        )
    return user


async def get_chat_or_404(
    chat_id: Annotated[UUID, Path(description="Chat UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Chat:
    """
    Look up a chat by ID, but only if it belongs to the current user.
    Cross-user access returns 404 (not 403) to avoid leaking existence.
    """
    query = select(Chat).where(Chat.id == chat_id, Chat.user_id == current_user.id)
    chat = (await db.execute(query)).scalar_one_or_none()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat {chat_id} not found",
        )
    return chat


async def get_project_or_404(
    project_id: Annotated[UUID, Path(description="Project UUID")],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Project:
    """
    Look up a project by ID, but only if it belongs to the current user.
    Cross-user access returns 404 to avoid leaking existence.
    """
    query = select(Project).where(
        Project.id == project_id, Project.user_id == current_user.id
    )
    project = (await db.execute(query)).scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )
    return project
