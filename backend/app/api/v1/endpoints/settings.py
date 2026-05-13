"""
API endpoints for settings management.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_chat_or_404, get_current_user, get_db
from app.core.config import settings as app_settings
from app.core.logging import get_logger
from app.db.models import Chat, ChatSettings, Settings, User
from app.schemas.settings import (
    ChatSettingsResponse,
    ChatSettingsUpdate,
    SettingsResponse,
    SettingsUpdate,
)

router = APIRouter()
logger = get_logger(__name__)


@router.get("/settings", response_model=SettingsResponse)
async def get_global_settings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get the current user's settings. Creates a row from env-var seed defaults
    if the user does not have one yet.
    """
    try:
        settings = (
            await db.execute(
                select(Settings).where(Settings.user_id == current_user.id)
            )
        ).scalar_one_or_none()

        if not settings:
            settings = Settings(
                user_id=current_user.id,
                default_model=app_settings.default_model,
                conversation_summarization_model=app_settings.title_generation_model,
                default_temperature=0.7,
                default_max_tokens=2048,
                num_ctx=2048,
            )
            db.add(settings)
            await db.flush()
            await db.refresh(settings)
            logger.info(
                f"Created default settings for user {current_user.id} "
                f"with model: {app_settings.default_model}"
            )

        return SettingsResponse.model_validate(settings)

    except Exception as e:
        logger.error(f"Error retrieving settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving settings",
        )


@router.patch("/settings", response_model=SettingsResponse)
async def update_global_settings(
    settings_data: SettingsUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update the current user's settings."""
    try:
        settings = (
            await db.execute(
                select(Settings).where(Settings.user_id == current_user.id)
            )
        ).scalar_one_or_none()

        if not settings:
            settings = Settings(
                user_id=current_user.id,
                default_model=app_settings.default_model,
                conversation_summarization_model=app_settings.title_generation_model,
                default_temperature=0.7,
                default_max_tokens=2048,
                num_ctx=2048,
            )
            db.add(settings)

        if settings_data.default_model is not None:
            settings.default_model = settings_data.default_model
        if settings_data.conversation_summarization_model is not None:
            settings.conversation_summarization_model = settings_data.conversation_summarization_model
        if settings_data.default_temperature is not None:
            settings.default_temperature = settings_data.default_temperature
        if settings_data.default_max_tokens is not None:
            settings.default_max_tokens = settings_data.default_max_tokens
        if settings_data.num_ctx is not None:
            settings.num_ctx = settings_data.num_ctx

        await db.flush()
        await db.refresh(settings)

        logger.info(f"Updated settings for user {current_user.id}")

        return SettingsResponse.model_validate(settings)

    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating settings",
        )


@router.get("/{chat_id}/settings", response_model=ChatSettingsResponse)
async def get_chat_settings(
    chat: Annotated[Chat, Depends(get_chat_or_404)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get settings for a specific chat (ownership enforced by dep)."""
    settings_query = select(ChatSettings).where(ChatSettings.chat_id == chat.id)
    chat_settings = (await db.execute(settings_query)).scalar_one_or_none()

    if not chat_settings:
        chat_settings = ChatSettings(chat_id=chat.id)
        db.add(chat_settings)
        await db.flush()
        await db.refresh(chat_settings)
        logger.info(f"Created chat settings for chat {chat.id}")

    return ChatSettingsResponse.model_validate(chat_settings)


@router.patch("/{chat_id}/settings", response_model=ChatSettingsResponse)
async def update_chat_settings(
    settings_data: ChatSettingsUpdate,
    chat: Annotated[Chat, Depends(get_chat_or_404)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update settings for a specific chat (ownership enforced by dep)."""
    settings_query = select(ChatSettings).where(ChatSettings.chat_id == chat.id)
    chat_settings = (await db.execute(settings_query)).scalar_one_or_none()

    if not chat_settings:
        chat_settings = ChatSettings(chat_id=chat.id)
        db.add(chat_settings)

    if settings_data.temperature is not None:
        chat_settings.temperature = settings_data.temperature
    if settings_data.max_tokens is not None:
        chat_settings.max_tokens = settings_data.max_tokens
    if settings_data.system_prompt is not None:
        chat_settings.system_prompt = settings_data.system_prompt

    await db.flush()
    await db.refresh(chat_settings)

    logger.info(f"Updated chat settings for chat {chat.id}")

    return ChatSettingsResponse.model_validate(chat_settings)
