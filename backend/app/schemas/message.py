"""
Pydantic schemas for Message API.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AttachedFileInfo(BaseModel):
    """Simplified file info for message attachments."""

    id: UUID
    filename: str
    file_type: str
    file_size: int

    model_config = {"from_attributes": True}


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
    truncated: bool = False
    attached_files: List[AttachedFileInfo] = Field(default_factory=list)
    rag_citations: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "RAG citation metadata for assistant messages where retrieval ran. "
            "Shape: {used_dense, corpus, server_base_url, article_url_template, hits: [{title, section, score}]}"
        ),
    )
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


class StreamMessageRequest(BaseModel):
    """Body for POST /chats/{id}/stream.

    `file_ids` is a hook for Phase 6 selective per-message attachment.
    When None (Phase 4 default), all project files are attached (preserving
    pre-Phase-6 behavior). When the list is present, Phase 6 will treat it
    as the source of truth.
    """

    content: str = Field(..., min_length=1, max_length=32000)
    file_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Selected file IDs to attach. None = auto-attach all (until phase 6).",
    )
