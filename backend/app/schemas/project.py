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


class ProjectCreate(ProjectBase):
    """Schema for creating a new project."""

    pass


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    custom_instructions: Optional[str] = None
    is_archived: Optional[bool] = None


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
    file_type: str = Field(..., pattern="^(txt|json|csv)$")
    content: str = Field(..., min_length=1)


class ProjectResponse(ProjectBase):
    """Schema for project response."""

    id: UUID
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    chat_count: Optional[int] = Field(None, description="Number of chats in this project")
    file_count: Optional[int] = Field(None, description="Number of files in this project")

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
