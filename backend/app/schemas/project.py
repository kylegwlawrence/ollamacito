"""
Pydantic schemas for project-related operations.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    """Base project schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    custom_instructions: Optional[str] = Field(
        None, description="Custom instructions for the AI in this project"
    )
    default_model: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Default model for new chats in this project",
    )
    temperature: Optional[float] = Field(
        None, ge=0.0, le=2.0, description="Temperature override for this project"
    )
    max_tokens: Optional[int] = Field(
        None, gt=0, description="Max tokens override for this project"
    )
    auto_attach_all_files: bool = Field(
        default=False,
        description=(
            "If true, the frontend pre-selects every project file when "
            "composing a new message. The backend always honors the explicit "
            "file_ids on each request; this flag is a UX hint only."
        ),
    )
    rag_enabled: bool = Field(
        default=False,
        description="When true, the backend retrieves context from the configured RAG server on every user message.",
    )
    rag_server_id: Optional[UUID] = Field(
        None,
        description="ID of a RagServer entry owned by the current user. Required when rag_enabled is true.",
    )
    rag_top_k: Optional[int] = Field(
        None,
        ge=1,
        le=50,
        description="Number of chunks to request per query.",
    )
    memory: Optional[str] = Field(
        None,
        description="User-curated project memory document. Injected as the first section of the system prompt on every turn in this project's chats.",
    )


class ProjectCreate(ProjectBase):
    """Schema for creating a new project."""

    pass


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    custom_instructions: Optional[str] = None
    is_archived: Optional[bool] = None
    default_model: Optional[str] = Field(None, min_length=1, max_length=100)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    auto_attach_all_files: Optional[bool] = None
    rag_enabled: Optional[bool] = None
    rag_server_id: Optional[UUID] = None
    rag_top_k: Optional[int] = Field(None, ge=1, le=50)
    memory: Optional[str] = Field(
        None, description="Set to a string to update, or null to clear."
    )


class ProjectFileResponse(BaseModel):
    """Schema for project file response."""

    id: UUID
    project_id: UUID
    filename: str
    file_type: str
    file_size: int
    content_preview: Optional[str]
    content: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectFileCreate(BaseModel):
    """Schema for creating a new project file."""

    filename: str = Field(..., min_length=1, max_length=255)
    file_type: str = Field(..., pattern="^(txt|json|csv|md)$")
    content: str = Field(..., min_length=1)


class ProjectResponse(ProjectBase):
    """Schema for project response."""

    id: UUID
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    chat_count: Optional[int] = Field(
        None, description="Number of chats in this project"
    )
    file_count: Optional[int] = Field(
        None, description="Number of files in this project"
    )

    model_config = {"from_attributes": True}


class ProjectWithDetails(ProjectResponse):
    """Schema for project with detailed information including files."""

    files: List[ProjectFileResponse] = Field(default_factory=list)


class ProjectListResponse(BaseModel):
    """Schema for paginated project list response."""

    projects: List[ProjectResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProjectMemoryGenerateResponse(BaseModel):
    """Response from POST /projects/{id}/memory/generate.

    Note: this endpoint does NOT persist the result — the client receives the
    generated text and submits it via PATCH /projects/{id} if the user clicks Save.
    """

    memory: str
