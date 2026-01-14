"""
Pydantic schemas for Settings API.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SettingsBase(BaseModel):
    """Base settings schema."""

    default_model: str = Field(..., min_length=1, max_length=100)
    conversation_summarization_model: str = Field(..., min_length=1, max_length=100)
    default_temperature: float = Field(..., ge=0.0, le=2.0)
    default_max_tokens: int = Field(..., gt=0)
    num_ctx: int = Field(..., gt=0)
    theme: str = Field(..., pattern="^(dark|light)$")


class SettingsUpdate(BaseModel):
    """Schema for updating global settings."""

    default_model: Optional[str] = Field(None, min_length=1, max_length=100)
    conversation_summarization_model: Optional[str] = Field(None, min_length=1, max_length=100)
    default_temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    default_max_tokens: Optional[int] = Field(None, gt=0)
    num_ctx: Optional[int] = Field(None, gt=0)
    theme: Optional[str] = Field(None, pattern="^(dark|light)$")


class SettingsResponse(SettingsBase):
    """Schema for settings response."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatSettingsBase(BaseModel):
    """Base chat settings schema."""

    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    system_prompt: Optional[str] = None


class ChatSettingsUpdate(ChatSettingsBase):
    """Schema for updating chat settings."""

    pass


class ChatSettingsResponse(ChatSettingsBase):
    """Schema for chat settings response."""

    chat_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
