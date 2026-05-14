"""
Pydantic schemas for user-owned RAG server entries.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


def _strip_trailing_slash(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.rstrip("/")
    return stripped or None


class RagServerBase(BaseModel):
    """Base schema with the editable fields of a RAG server entry."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name shown in the project dropdown (unique per user).",
    )
    url: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Base URL of the RAG server (e.g. http://127.0.0.1:8001).",
    )
    corpus_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Corpus ID hosted on that server (e.g. simplewiki).",
    )

    @field_validator("url")
    @classmethod
    def _normalize_url(cls, value: str) -> str:
        return value.rstrip("/")


class RagServerCreate(RagServerBase):
    """Schema for creating a new RAG server entry."""

    pass


class RagServerUpdate(BaseModel):
    """Schema for partial updates to a RAG server entry."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    url: Optional[str] = Field(None, min_length=1, max_length=512)
    corpus_id: Optional[str] = Field(None, min_length=1, max_length=100)

    @field_validator("url")
    @classmethod
    def _normalize_url(cls, value: Optional[str]) -> Optional[str]:
        return _strip_trailing_slash(value)


class RagServerResponse(BaseModel):
    """Server-side representation returned to the client."""

    id: UUID
    name: str
    url: str
    corpus_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RagServerListResponse(BaseModel):
    """List wrapper (no pagination — these are user-managed and small)."""

    servers: List[RagServerResponse]


class RagServerTestRequest(BaseModel):
    """Body for POST /rag-servers/test — verify a (url, corpus_id) pair."""

    url: str = Field(..., min_length=1, max_length=512)
    corpus_id: str = Field(..., min_length=1, max_length=100)

    @field_validator("url")
    @classmethod
    def _normalize_url(cls, value: str) -> str:
        return value.rstrip("/")


class RagServerTestResponse(BaseModel):
    """Result of testing a (url, corpus_id) pair against the live server."""

    server_name: Optional[str] = None
    server_version: Optional[str] = None
    description: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_dim: Optional[int] = None
    default_top_k: Optional[int] = None
    max_top_k: Optional[int] = None
    article_url_template: Optional[str] = None
    available_corpora: List[str] = Field(default_factory=list)
    corpus_found: bool
