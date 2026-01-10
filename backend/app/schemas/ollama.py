"""
Pydantic schemas for Ollama API.
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class OllamaModel(BaseModel):
    """Schema for an Ollama model."""

    name: str
    size: Optional[int] = None
    digest: Optional[str] = None
    modified_at: Optional[str] = None


class OllamaModelListResponse(BaseModel):
    """Schema for Ollama model list response."""

    models: List[OllamaModel]


class OllamaStatusResponse(BaseModel):
    """Schema for Ollama connection status."""

    connected: bool
    url: str
    models_count: Optional[int] = None
    error: Optional[str] = None
