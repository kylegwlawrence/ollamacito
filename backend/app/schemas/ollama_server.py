"""
Pydantic schemas for Ollama server management.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class OllamaServerBase(BaseModel):
    """Base schema for Ollama server with common attributes."""

    name: str = Field(..., min_length=1, max_length=255, description="Server name")
    tailscale_url: str = Field(
        ..., min_length=1, max_length=512, description="Tailscale URL for the server"
    )
    description: Optional[str] = Field(None, description="Optional server description")


class OllamaServerCreate(OllamaServerBase):
    """Schema for creating a new Ollama server."""

    is_active: bool = Field(True, description="Whether the server is active")


class OllamaServerUpdate(BaseModel):
    """Schema for updating an existing Ollama server."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    tailscale_url: Optional[str] = Field(None, min_length=1, max_length=512)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class OllamaServerResponse(OllamaServerBase):
    """Schema for Ollama server response."""

    id: UUID
    is_active: bool
    status: str = Field(..., description="Server status: online, offline, unknown, error")
    last_checked_at: Optional[datetime] = Field(None, description="Last health check time")
    last_error: Optional[str] = Field(None, description="Last error message if any")
    models_count: int = Field(..., description="Number of models available on server")
    average_response_time_ms: Optional[int] = Field(
        None, description="Average response time in milliseconds"
    )
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OllamaServerListResponse(BaseModel):
    """Schema for list of Ollama servers."""

    servers: list[OllamaServerResponse]
