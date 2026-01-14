"""
API endpoints for settings management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_chat_or_404, get_db
from app.core.config import settings as app_settings
from app.core.logging import get_logger
from app.db.models import Chat, ChatSettings, Settings
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
    db: AsyncSession = Depends(get_db),
):
    """
    Get global application settings.

    Args:
        db: Database session

    Returns:
        SettingsResponse: Global settings

    Raises:
        HTTPException: If settings not found
    """
    try:
        query = select(Settings).where(Settings.id == 1)
        result = await db.execute(query)
        settings = result.scalar_one_or_none()

        if not settings:
            # Create default settings if not exists, using config.py as source of truth
            settings = Settings(
                id=1,
                default_model=app_settings.default_model,
                conversation_summarization_model=app_settings.title_generation_model,
                default_temperature=0.7,
                default_max_tokens=2048,
                num_ctx=2048,
                theme="dark",
            )
            db.add(settings)
            await db.flush()
            await db.refresh(settings)
            logger.info(f"Created default settings with model: {app_settings.default_model}")

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
    db: AsyncSession = Depends(get_db),
):
    """
    Update global application settings.

    Args:
        settings_data: Settings update data
        db: Database session

    Returns:
        SettingsResponse: Updated settings
    """
    try:
        query = select(Settings).where(Settings.id == 1)
        result = await db.execute(query)
        settings = result.scalar_one_or_none()

        if not settings:
            settings = Settings(
                id=1,
                default_model=app_settings.default_model,
                conversation_summarization_model=app_settings.title_generation_model,
                default_temperature=0.7,
                default_max_tokens=2048,
                num_ctx=2048,
                theme="dark",
            )
            db.add(settings)

        # Update fields
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
        if settings_data.theme is not None:
            settings.theme = settings_data.theme

        await db.flush()
        await db.refresh(settings)

        logger.info("Updated global settings")

        return SettingsResponse.model_validate(settings)

    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating settings",
        )


@router.get("/{chat_id}/settings", response_model=ChatSettingsResponse)
async def get_chat_settings(
    chat: Chat = Depends(get_chat_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Get settings for a specific chat.

    Args:
        chat: Chat from dependency
        db: Database session

    Returns:
        ChatSettingsResponse: Chat-specific settings
    """
    # Get or create chat settings
    settings_query = select(ChatSettings).where(ChatSettings.chat_id == chat.id)
    result = await db.execute(settings_query)
    chat_settings = result.scalar_one_or_none()

    if not chat_settings:
        # Return empty chat settings
        chat_settings = ChatSettings(chat_id=chat.id)
        db.add(chat_settings)
        await db.flush()
        await db.refresh(chat_settings)
        logger.info(f"Created chat settings for chat {chat.id}")

    return ChatSettingsResponse.model_validate(chat_settings)


@router.patch("/{chat_id}/settings", response_model=ChatSettingsResponse)
async def update_chat_settings(
    settings_data: ChatSettingsUpdate,
    chat: Chat = Depends(get_chat_or_404),
    db: AsyncSession = Depends(get_db),
):
    """
    Update settings for a specific chat.

    Args:
        settings_data: Chat settings update data
        chat: Chat from dependency
        db: Database session

    Returns:
        ChatSettingsResponse: Updated chat settings
    """
    # Get or create chat settings
    settings_query = select(ChatSettings).where(ChatSettings.chat_id == chat.id)
    result = await db.execute(settings_query)
    chat_settings = result.scalar_one_or_none()

    if not chat_settings:
        chat_settings = ChatSettings(chat_id=chat.id)
        db.add(chat_settings)

    # Update fields
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
