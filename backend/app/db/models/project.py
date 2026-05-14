"""
Database models for projects and project files.
"""
import uuid
from typing import List, Optional

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    """Project model representing a collection of related chats."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    custom_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Project-specific model settings (override global defaults)
    default_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # When true, the frontend pre-selects every project file on each new
    # message (user can still deselect). When false (default), the user
    # opts in per message via the file chip selector. The backend always
    # honors the explicit `file_ids` from the request; this flag is a UX
    # hint only.
    auto_attach_all_files: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    memory: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # External RAG-server integration (per-project). See LOCAL_WIKIPEDIA_API.md.
    # When rag_enabled is true, the backend calls /rag/retrieve on rag_server_url
    # for every user message in this project's chats and injects the hits into
    # the system prompt. The three config fields must all be non-null when
    # rag_enabled is true; the request layer rejects half-configured projects.
    rag_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rag_server_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    rag_corpus_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rag_top_k: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="projects")
    chats: Mapped[List["Chat"]] = relationship(
        "Chat",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    files: Mapped[List["ProjectFile"]] = relationship(
        "ProjectFile",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            "temperature IS NULL OR (temperature >= 0.0 AND temperature <= 2.0)",
            name="valid_project_temperature",
        ),
        CheckConstraint(
            "max_tokens IS NULL OR max_tokens > 0",
            name="positive_project_tokens",
        ),
        CheckConstraint(
            "rag_top_k IS NULL OR (rag_top_k BETWEEN 1 AND 50)",
            name="valid_project_rag_top_k",
        ),
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name})>"


class ProjectFile(Base, TimestampMixin):
    """ProjectFile model representing an uploaded reference file."""

    __tablename__ = "project_files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="files")

    def __repr__(self) -> str:
        return f"<ProjectFile(id={self.id}, filename={self.filename}, project_id={self.project_id})>"
