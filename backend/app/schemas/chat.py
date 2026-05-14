"""
Pydantic schemas for Chat API.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatBase(BaseModel):
    """Base chat schema with common attributes."""

    title: str = Field(..., min_length=1, max_length=255)
    model: str = Field(..., min_length=1, max_length=100)


class ChatCreate(ChatBase):
    """Schema for creating a new chat."""

    project_id: Optional[UUID] = Field(None, description="Optional project ID to associate chat with")
    agent_mode_enabled: bool = Field(
        default=False,
        description="When true, use the agentic chat endpoint (search_wikipedia tool)."
        " Requires the chat's project to have RAG configured.",
    )


class ChatUpdate(BaseModel):
    """Schema for updating a chat."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    model: Optional[str] = Field(None, min_length=1, max_length=100)
    is_archived: Optional[bool] = None
    agent_mode_enabled: Optional[bool] = None


class ChatResponse(ChatBase):
    """Schema for chat response."""

    id: UUID
    is_archived: bool
    project_id: Optional[UUID] = Field(None, description="Project ID if chat belongs to a project")
    agent_mode_enabled: bool = False
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = Field(None, description="Number of messages in chat")

    model_config = {"from_attributes": True}


class ChatWithMessagesResponse(ChatResponse):
    """Schema for chat response with messages included."""

    messages: List["MessageResponse"] = []

    model_config = {"from_attributes": True}


class ChatListResponse(BaseModel):
    """Schema for paginated chat list response."""

    chats: List[ChatResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Forward reference resolution
from app.schemas.message import MessageResponse

ChatWithMessagesResponse.model_rebuild()
