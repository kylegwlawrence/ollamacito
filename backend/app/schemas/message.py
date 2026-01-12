"""
Pydantic schemas for Message API.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class AttachedFileInfo(BaseModel):
    """Simplified file info for message attachments."""

    id: UUID
    filename: str
    file_type: str
    file_size: int


class MessageBase(BaseModel):
    """Base message schema with common attributes."""

    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)


class MessageCreate(BaseModel):
    """Schema for creating a new message (sending user message)."""

    content: str = Field(..., min_length=1)
    file_ids: List[UUID] = Field(default_factory=list, description="List of project file IDs to attach")


class MessageResponse(MessageBase):
    """Schema for message response."""

    id: UUID
    chat_id: UUID
    tokens_used: Optional[int] = None
    attached_files: List[AttachedFileInfo] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    """Schema for paginated message list response."""

    messages: List[MessageResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class StreamChunk(BaseModel):
    """Schema for streaming response chunk."""

    content: str
    done: bool = False
